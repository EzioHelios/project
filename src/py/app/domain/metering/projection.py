"""Versioned electricity interval projection and Scope 2 reconciliation."""

from __future__ import annotations

# ruff: noqa: PLR0915
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


MAX_INTERVAL_DELTA_KWH = Decimal(100000)
MAX_EXPECTED_GAP = timedelta(hours=6)
FIXED_VALUE_THRESHOLD = timedelta(hours=6)
MONTHS_PER_YEAR = 12
MINIMUM_INTERVAL_SAMPLES = 2


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    run_id: int
    run_code: str
    source_count: int
    hourly_facts: int
    daily_facts: int
    scope2_aggregates: int
    quality_issues: int
    reused: bool = False


@dataclass(frozen=True, slots=True)
class ReadingSample:
    fact: m.MeterReadingFact
    equipment: m.MonitorEquipment
    area: m.MonitorSector | None


@dataclass(frozen=True, slots=True)
class UseSystemMapping:
    code: str
    name: str
    valid_from: date | None
    valid_to: date | None


def month_window(billing_month: str) -> tuple[datetime, datetime]:
    try:
        start = datetime.fromisoformat(f"{billing_month}-01T00:00:00")
    except ValueError as exc:
        msg = "billing_month must use YYYY-MM"
        raise ValueError(msg) from exc
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == MONTHS_PER_YEAR
        else start.replace(month=start.month + 1)
    )
    return start, end


def iter_billing_months(from_month: str, to_month: str) -> list[str]:
    """Return an inclusive ordered month range."""
    start, _ = month_window(from_month)
    end, _ = month_window(to_month)
    if start > end:
        msg = "from_month must not be later than to_month"
        raise ValueError(msg)
    months: list[str] = []
    current = start
    while current <= end:
        months.append(current.strftime("%Y-%m"))
        current = (
            current.replace(year=current.year + 1, month=1)
            if current.month == MONTHS_PER_YEAR
            else current.replace(month=current.month + 1)
        )
    return months


class ElectricityProjectionUseCase:
    """Project canonical cumulative register readings into immutable interval revisions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        tenant_id = session.info.get(TENANT_ID_SESSION_KEY)
        if tenant_id is None:
            msg = "Electricity projection requires an active tenant"
            raise ValueError(msg)
        self.team_id: UUID = tenant_id

    async def rebuild_month(self, billing_month: str, *, area_id: str | None = None) -> ProjectionResult:
        period_start, period_end = month_window(billing_month)
        period_samples = await self._load_period_samples(period_start, period_end, area_id)
        previous_samples = await self._load_previous_samples(period_samples, period_start)
        boundaries, members = await self._load_boundaries(period_start.date(), period_end.date())
        use_systems = await self._load_use_system_bindings(period_start.date(), period_end.date())
        checksum = _projection_checksum(period_samples, previous_samples, boundaries, members, use_systems)
        run_code = f"electricity:{billing_month}:{area_id or 'all'}:{checksum[:16]}"

        existing_run = await self.session.scalar(
            select(m.EnergyProjectionRun).where(
                m.EnergyProjectionRun.run_code == run_code,
                m.EnergyProjectionRun.status == "completed",
            )
        )
        if existing_run is not None:
            aggregate_count = int(
                await self.session.scalar(
                    select(func.count(m.Scope2MeterAggregate.id)).where(
                        m.Scope2MeterAggregate.billing_month == billing_month,
                        m.Scope2MeterAggregate.projection_run_id == existing_run.id,
                    )
                )
                or 0
            )
            return ProjectionResult(
                run_id=existing_run.id,
                run_code=run_code,
                source_count=existing_run.source_count,
                hourly_facts=await self._fact_count(existing_run.id, "hour"),
                daily_facts=await self._fact_count(existing_run.id, "day"),
                scope2_aggregates=aggregate_count,
                quality_issues=existing_run.issue_count,
                reused=True,
            )

        run = m.EnergyProjectionRun(
            team_id=self.team_id,
            run_code=run_code,
            projection_type="electricity_interval",
            period_start=period_start,
            period_end=period_end,
            status="running",
            mapping_version="boundary_v1",
            source_high_watermark=str(max((sample.fact.id for sample in period_samples), default=0)),
            source_count=len(period_samples),
            source_checksum=checksum,
            started_at=datetime.now(UTC).replace(tzinfo=None),
            run_config={
                "area_id": area_id,
                "max_delta_kwh": str(MAX_INTERVAL_DELTA_KWH),
                "max_gap_hours": MAX_EXPECTED_GAP.total_seconds() / 3600,
            },
        )
        self.session.add(run)
        await self.session.commit()
        run_id = run.id

        try:
            hourly, issues, meter_ranges = await self._calculate_intervals(
                period_samples,
                previous_samples,
                boundaries,
                members,
                use_systems,
            )
            daily = _roll_up_daily(hourly)
            hourly_count = await self._write_interval_revisions(run, hourly, "hour")
            daily_count = await self._write_interval_revisions(run, daily, "day")
            issue_count = await self._write_quality_issues(run, issues)
            aggregates = await self._write_scope2_aggregate_revisions(
                run,
                billing_month,
                hourly,
                meter_ranges,
                boundaries,
            )
            await reconcile_scope2_electricity(
                self.session,
                billing_month,
                projection_run_id=run.id,
                auto_commit=False,
            )
            run.output_count = hourly_count + daily_count
            run.issue_count = issue_count
            run.status = "completed"
            run.finished_at = datetime.now(UTC).replace(tzinfo=None)
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            failed_run = await self.session.scalar(
                select(m.EnergyProjectionRun).where(m.EnergyProjectionRun.id == run_id)
            )
            if failed_run is not None:
                failed_run.status = "failed"
                failed_run.error_detail = str(exc)[:4000]
                failed_run.finished_at = datetime.now(UTC).replace(tzinfo=None)
                await self.session.commit()
            raise

        return ProjectionResult(
            run_id=run.id,
            run_code=run_code,
            source_count=len(period_samples),
            hourly_facts=hourly_count,
            daily_facts=daily_count,
            scope2_aggregates=len(aggregates),
            quality_issues=issue_count,
        )

    async def _load_period_samples(
        self, period_start: datetime, period_end: datetime, area_id: str | None
    ) -> list[ReadingSample]:
        stmt = (
            select(m.MeterReadingFact, m.MonitorEquipment, m.MonitorSector)
            .join(m.MonitorEquipment, m.MonitorEquipment.id == m.MeterReadingFact.equipment_id)
            .outerjoin(m.MonitorSector, m.MonitorSector.id == m.MonitorEquipment.sector_id)
            .where(
                m.MeterReadingFact.reading_time >= period_start,
                m.MeterReadingFact.reading_time < period_end,
                m.MeterReadingFact.point_code == "forward_active_total",
                m.MeterReadingFact.value_kind == "register_index",
                m.MeterReadingFact.normalized_value.is_not(None),
                m.MonitorEquipment.is_enable.is_(True),
            )
            .order_by(m.MeterReadingFact.equipment_id, m.MeterReadingFact.reading_time, m.MeterReadingFact.id)
        )
        if area_id:
            if area_id.isdigit():
                stmt = stmt.where(m.MonitorSector.id == int(area_id))
            else:
                stmt = stmt.where(m.MonitorSector.code == area_id)
        return [
            ReadingSample(fact=fact, equipment=equipment, area=area)
            for fact, equipment, area in (await self.session.execute(stmt)).all()
        ]

    async def _load_boundaries(
        self, period_start: date, period_end: date
    ) -> tuple[dict[int, m.MeasurementBoundary], dict[int, list[m.MeasurementBoundaryMember]]]:
        rows = (
            await self.session.scalars(
                select(m.MeasurementBoundary)
                .where(
                    m.MeasurementBoundary.status == "active",
                    (m.MeasurementBoundary.valid_from.is_(None) | (m.MeasurementBoundary.valid_from < period_end)),
                    (m.MeasurementBoundary.valid_to.is_(None) | (m.MeasurementBoundary.valid_to >= period_start)),
                )
                .order_by(m.MeasurementBoundary.code)
            )
        ).all()
        by_meter = {row.meter_equipment_id: row for row in rows if row.meter_equipment_id is not None}
        boundary_ids = [row.id for row in rows]
        confirmed_members: list[m.MeasurementBoundaryMember] = (
            list(
                (
                    await self.session.scalars(
                        select(m.MeasurementBoundaryMember).where(
                            m.MeasurementBoundaryMember.boundary_id.in_(boundary_ids),
                            m.MeasurementBoundaryMember.confirmation_status == "confirmed",
                            (
                                m.MeasurementBoundaryMember.valid_from.is_(None)
                                | (m.MeasurementBoundaryMember.valid_from < period_end)
                            ),
                            (
                                m.MeasurementBoundaryMember.valid_to.is_(None)
                                | (m.MeasurementBoundaryMember.valid_to >= period_start)
                            ),
                        )
                    )
                ).all()
            )
            if boundary_ids
            else []
        )
        members: dict[int, list[m.MeasurementBoundaryMember]] = defaultdict(list)
        for member in confirmed_members:
            members[member.boundary_id].append(member)
        return by_meter, members

    async def _load_use_system_bindings(self, period_start: date, period_end: date) -> dict[int, UseSystemMapping]:
        rows = (
            await self.session.execute(
                select(m.EnergyUseSystemBinding, m.EnergyUseSystem.name)
                .join(m.EnergyUseSystem, m.EnergyUseSystem.code == m.EnergyUseSystemBinding.system_code)
                .where(
                    m.EnergyUseSystemBinding.equipment_id.is_not(None),
                    m.EnergyUseSystemBinding.is_primary.is_(True),
                    m.EnergyUseSystem.is_enabled.is_(True),
                    (
                        m.EnergyUseSystemBinding.valid_from.is_(None)
                        | (m.EnergyUseSystemBinding.valid_from < period_end)
                    ),
                    (m.EnergyUseSystemBinding.valid_to.is_(None) | (m.EnergyUseSystemBinding.valid_to >= period_start)),
                )
            )
        ).all()
        return {
            binding.equipment_id: UseSystemMapping(
                code=binding.system_code,
                name=system_name,
                valid_from=binding.valid_from,
                valid_to=binding.valid_to,
            )
            for binding, system_name in rows
            if binding.equipment_id is not None
        }

    async def _calculate_intervals(
        self,
        period_samples: list[ReadingSample],
        previous_samples: dict[int, ReadingSample],
        boundaries: dict[int, m.MeasurementBoundary],
        members: dict[int, list[m.MeasurementBoundaryMember]],
        use_systems: dict[int, UseSystemMapping],
    ) -> tuple[
        dict[tuple[int, datetime], dict[str, Any]], list[dict[str, Any]], dict[int, tuple[ReadingSample, ReadingSample]]
    ]:
        by_meter: dict[int, list[ReadingSample]] = defaultdict(list)
        for sample in period_samples:
            by_meter[sample.equipment.id].append(sample)

        hourly: dict[tuple[int, datetime], dict[str, Any]] = {}
        issues: list[dict[str, Any]] = []
        meter_ranges: dict[int, tuple[ReadingSample, ReadingSample]] = {}
        for equipment_id, samples in by_meter.items():
            previous = previous_samples.get(equipment_id)
            deduplicated: list[ReadingSample] = []
            for sample in samples:
                if deduplicated and sample.fact.reading_time == deduplicated[-1].fact.reading_time:
                    issues.append(
                        _issue(sample, "duplicate_timestamp", "Duplicate timestamp; highest source id retained")
                    )
                    deduplicated[-1] = sample
                else:
                    deduplicated.append(sample)
            chain = ([previous] if previous else []) + deduplicated
            if len(chain) < MINIMUM_INTERVAL_SAMPLES:
                if deduplicated:
                    issues.append(_issue(deduplicated[0], "insufficient_data", "No preceding valid register reading"))
                continue

            fixed_since: datetime | None = None
            for before, current in pairwise(chain):
                if current.fact.quality_status != "valid":
                    issues.append(_issue(current, "invalid_quality", f"Source quality={current.fact.quality_status}"))
                    continue
                before_value = Decimal(str(before.fact.normalized_value))
                current_value = Decimal(str(current.fact.normalized_value))
                delta = current_value - before_value
                elapsed = current.fact.reading_time - before.fact.reading_time
                if delta < 0:
                    issues.append(_issue(current, "register_reset", "Cumulative register decreased; interval excluded"))
                    fixed_since = None
                    continue
                if delta > MAX_INTERVAL_DELTA_KWH:
                    issues.append(_issue(current, "abnormal_spike", "Interval delta exceeded the configured limit"))
                    fixed_since = None
                    continue
                data_quality = "measured"
                if elapsed > MAX_EXPECTED_GAP:
                    issues.append(
                        _issue(current, "reading_gap", f"Reading gap is {elapsed.total_seconds() / 3600:.2f} hours")
                    )
                    fixed_since = None
                    continue
                if delta == 0:
                    fixed_since = fixed_since or before.fact.reading_time
                    if current.fact.reading_time - fixed_since >= FIXED_VALUE_THRESHOLD:
                        issues.append(
                            _issue(current, "fixed_value", "Cumulative register remained unchanged for six hours")
                        )
                        fixed_since = current.fact.reading_time
                else:
                    fixed_since = None

                hour_start = current.fact.reading_time.replace(minute=0, second=0, microsecond=0)
                key = (equipment_id, hour_start)
                snapshot = _mapping_snapshot(
                    current, boundaries.get(equipment_id), members, use_systems.get(equipment_id)
                )
                item = hourly.setdefault(
                    key,
                    {
                        "sample": current,
                        "period_start": hour_start,
                        "period_end": hour_start + timedelta(hours=1),
                        "amount": Decimal(0),
                        "reading_count": 0,
                        "data_quality": data_quality,
                        "snapshot": snapshot,
                    },
                )
                item["amount"] += delta
                item["reading_count"] += 1
                if data_quality != "measured":
                    item["data_quality"] = data_quality

            meter_ranges[equipment_id] = (chain[0], chain[-1])
        return hourly, issues, meter_ranges

    async def _load_previous_samples(
        self, period_samples: list[ReadingSample], period_start: datetime
    ) -> dict[int, ReadingSample]:
        first_by_meter: dict[int, ReadingSample] = {}
        for sample in period_samples:
            first_by_meter.setdefault(sample.equipment.id, sample)

        previous_samples: dict[int, ReadingSample] = {}
        for equipment_id, fallback in first_by_meter.items():
            fact = await self.session.scalar(
                select(m.MeterReadingFact)
                .where(
                    m.MeterReadingFact.equipment_id == equipment_id,
                    m.MeterReadingFact.reading_time < period_start,
                    m.MeterReadingFact.point_code == "forward_active_total",
                    m.MeterReadingFact.value_kind == "register_index",
                    m.MeterReadingFact.normalized_value.is_not(None),
                    m.MeterReadingFact.quality_status == "valid",
                )
                .order_by(m.MeterReadingFact.reading_time.desc(), m.MeterReadingFact.id.desc())
                .limit(1)
            )
            if fact is not None:
                previous_samples[equipment_id] = ReadingSample(
                    fact=fact,
                    equipment=fallback.equipment,
                    area=fallback.area,
                )
        return previous_samples

    async def _write_interval_revisions(
        self, run: m.EnergyProjectionRun, intervals: dict[tuple[int, datetime], dict[str, Any]], granularity: str
    ) -> int:
        source_ids = [f"meter:{equipment_id}:{granularity}:{period.isoformat()}" for equipment_id, period in intervals]
        histories: list[m.EnergyIntervalFact] = (
            list(
                (
                    await self.session.scalars(
                        select(m.EnergyIntervalFact)
                        .where(
                            m.EnergyIntervalFact.source_system == "meter_projection",
                            m.EnergyIntervalFact.source_record_id.in_(source_ids),
                        )
                        .execution_options(include_revision_history=True)
                    )
                ).all()
            )
            if source_ids
            else []
        )
        by_source: dict[str, list[m.EnergyIntervalFact]] = defaultdict(list)
        for history in histories:
            by_source[history.source_record_id].append(history)

        for (equipment_id, period), item in intervals.items():
            source_record_id = f"meter:{equipment_id}:{granularity}:{period.isoformat()}"
            previous_rows = by_source[source_record_id]
            previous_current = next((row for row in previous_rows if row.is_current), None)
            if previous_current is None:
                previous_current = await self.session.scalar(
                    select(m.EnergyIntervalFact).where(
                        m.EnergyIntervalFact.equipment_id == equipment_id,
                        m.EnergyIntervalFact.granularity == granularity,
                        m.EnergyIntervalFact.period_start == item["period_start"],
                        m.EnergyIntervalFact.source_system.in_(["meter_hourly", "meter_daily"]),
                    )
                )
            if previous_current is not None:
                previous_current.is_current = False
            sample: ReadingSample = item["sample"]
            snapshot = item["snapshot"]
            self.session.add(
                m.EnergyIntervalFact(
                    team_id=self.team_id,
                    source_system="meter_projection",
                    source_record_id=source_record_id,
                    energy_type_code="electricity",
                    equipment_id=equipment_id,
                    equipment_code=sample.equipment.code,
                    equipment_name=sample.equipment.name,
                    area_id=sample.area.code if sample.area else None,
                    area_name=sample.area.name if sample.area else None,
                    use_system_code=snapshot.get("use_system_code"),
                    use_system_name=snapshot.get("use_system_name"),
                    granularity=granularity,
                    period_start=item["period_start"],
                    period_end=item["period_end"],
                    amount=item["amount"],
                    unit="kWh",
                    cost_cny=None,
                    reading_count=item["reading_count"],
                    data_quality=item["data_quality"],
                    projection_run_id=run.id,
                    measurement_boundary_id=snapshot.get("boundary_id"),
                    revision_no=max((row.revision_no for row in previous_rows), default=0) + 1,
                    is_current=True,
                    supersedes_id=previous_current.id if previous_current else None,
                    source_snapshot=snapshot,
                )
            )
        await self.session.flush()
        return len(intervals)

    async def _write_quality_issues(self, run: m.EnergyProjectionRun, issues: list[dict[str, Any]]) -> int:
        for index, issue in enumerate(issues):
            sample: ReadingSample = issue.pop("sample")
            issue_key = f"{run.run_code}:{sample.equipment.id}:{issue['issue_type']}:{sample.fact.id}:{index}"
            self.session.add(
                m.MeteringQualityIssue(
                    team_id=self.team_id,
                    issue_key=issue_key,
                    projection_run_id=run.id,
                    equipment_id=sample.equipment.id,
                    point_code=sample.fact.point_code,
                    reading_time=sample.fact.reading_time,
                    issue_type=issue["issue_type"],
                    severity=issue.get("severity", "warning"),
                    status="open",
                    detail=issue["detail"],
                    issue_payload={"source_fact_id": sample.fact.id},
                )
            )
        await self.session.flush()
        return len(issues)

    async def _write_scope2_aggregate_revisions(
        self,
        run: m.EnergyProjectionRun,
        billing_month: str,
        hourly: dict[tuple[int, datetime], dict[str, Any]],
        meter_ranges: dict[int, tuple[ReadingSample, ReadingSample]],
        boundaries: dict[int, m.MeasurementBoundary],
    ) -> list[m.Scope2MeterAggregate]:
        totals: dict[int, Decimal] = defaultdict(Decimal)
        for (equipment_id, _period), item in hourly.items():
            totals[equipment_id] += item["amount"]

        use_boundary_filter = bool(boundaries)
        created: list[m.Scope2MeterAggregate] = []
        for equipment_id, total_kwh in totals.items():
            boundary = boundaries.get(equipment_id)
            if use_boundary_filter and (boundary is None or not boundary.include_in_scope2):
                continue
            first, last = meter_ranges[equipment_id]
            previous_rows = (
                await self.session.scalars(
                    select(m.Scope2MeterAggregate)
                    .where(
                        m.Scope2MeterAggregate.ammeter_id == first.equipment.code,
                        m.Scope2MeterAggregate.billing_month == billing_month,
                    )
                    .execution_options(include_revision_history=True)
                )
            ).all()
            previous_current = next((row for row in previous_rows if row.is_current), None)
            if previous_current is not None:
                previous_current.is_current = False
            snapshot = {
                "projection_run_id": run.id,
                "boundary_code": boundary.code if boundary else None,
                "coverage_status": "configured" if boundary else "provisional_meter_total",
            }
            aggregate = m.Scope2MeterAggregate(
                team_id=self.team_id,
                source_kind="meter_aggregate",
                ammeter_id=first.equipment.code,
                ammeter_name=first.equipment.name,
                area_id=first.area.code if first.area else None,
                area_name=first.area.name if first.area else None,
                billing_month=billing_month,
                first_reading_time=first.fact.reading_time,
                last_reading_time=last.fact.reading_time,
                start_total_energy=first.fact.normalized_value,
                end_total_energy=last.fact.normalized_value,
                total_kwh=total_kwh,
                status="provisional",
                calc_status="not_applicable",
                factor_source=None,
                factor_year=None,
                factor_unit=None,
                activity_amount=total_kwh,
                activity_unit="kWh",
                computed_co2e=None,
                computation_note="组织温室气体排放由统一盘查运行计算。",
                aggregation_note=None,
                projection_run_id=run.id,
                measurement_boundary_id=boundary.id if boundary else None,
                revision_no=max((row.revision_no for row in previous_rows), default=0) + 1,
                is_current=True,
                supersedes_id=previous_current.id if previous_current else None,
                source_snapshot=snapshot,
            )
            self.session.add(aggregate)
            created.append(aggregate)
        await self.session.flush()
        return created

    async def _fact_count(self, run_id: int, granularity: str) -> int:
        return int(
            await self.session.scalar(
                select(func.count(m.EnergyIntervalFact.id)).where(
                    m.EnergyIntervalFact.projection_run_id == run_id,
                    m.EnergyIntervalFact.granularity == granularity,
                )
            )
            or 0
        )


async def reconcile_scope2_electricity(
    session: AsyncSession,
    billing_month: str,
    *,
    projection_run_id: int | None = None,
    auto_commit: bool = True,
) -> m.Scope2ElectricityReconciliation:
    """Prefer approved canonical inventory electricity activity over meter totals."""
    tenant_id = session.info.get(TENANT_ID_SESSION_KEY)
    if tenant_id is None:
        msg = "Scope 2 reconciliation requires an active tenant"
        raise ValueError(msg)

    aggregate_rows: list[m.Scope2MeterAggregate] = list(
        (
            await session.scalars(
                select(m.Scope2MeterAggregate).where(
                    m.Scope2MeterAggregate.billing_month == billing_month,
                    m.Scope2MeterAggregate.total_kwh.is_not(None),
                )
            )
        ).all()
    )
    meter_total = sum((Decimal(str(row.total_kwh or 0)) for row in aggregate_rows), Decimal(0))
    month_start = date.fromisoformat(f"{billing_month}-01")
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    activity_rows: list[m.GhgActivityRecord] = list(
        (
            await session.scalars(
                select(m.GhgActivityRecord).where(
                    m.GhgActivityRecord.ghg_scope == "scope2",
                    m.GhgActivityRecord.status == "approved",
                    m.GhgActivityRecord.boundary_status == "included",
                    m.GhgActivityRecord.activity_unit.in_(["kWh", "MWh"]),
                    m.GhgActivityRecord.period_start <= month_end,
                    m.GhgActivityRecord.period_end >= month_start,
                )
            )
        ).all()
    )
    bill_total = (
        sum(
            (
                Decimal(str(row.activity_amount)) * (Decimal(1000) if row.activity_unit == "MWh" else Decimal(1))
                for row in activity_rows
            ),
            Decimal(0),
        )
        if activity_rows
        else None
    )
    organization_total = bill_total if bill_total is not None else meter_total
    allocated = min(meter_total, organization_total)
    unallocated = max(organization_total - allocated, Decimal(0))
    source_priority = "ghg_activity" if activity_rows else "meter_aggregate"
    snapshot = {
        "aggregate_ids": sorted(row.id for row in aggregate_rows),
        "activity_ids": sorted(row.id for row in activity_rows),
        "source_priority": source_priority,
    }
    snapshot["digest"] = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()

    current = await session.scalar(
        select(m.Scope2ElectricityReconciliation).where(
            m.Scope2ElectricityReconciliation.billing_month == billing_month
        )
    )
    if current is not None and (current.source_snapshot or {}).get("digest") == snapshot["digest"]:
        return current

    histories = (
        await session.scalars(
            select(m.Scope2ElectricityReconciliation)
            .where(m.Scope2ElectricityReconciliation.billing_month == billing_month)
            .execution_options(include_revision_history=True)
        )
    ).all()
    if current is not None:
        current.is_current = False
    reconciliation = m.Scope2ElectricityReconciliation(
        team_id=tenant_id,
        billing_month=billing_month,
        projection_run_id=projection_run_id,
        activity_record_id=activity_rows[0].id if len(activity_rows) == 1 else None,
        source_priority=source_priority,
        organization_total_kwh=organization_total,
        meter_total_kwh=meter_total,
        bill_total_kwh=bill_total,
        allocated_kwh=allocated,
        unallocated_kwh=unallocated,
        revision_no=max((row.revision_no for row in histories), default=0) + 1,
        is_current=True,
        supersedes_id=current.id if current else None,
        status="ready",
        source_snapshot=snapshot,
    )
    session.add(reconciliation)
    if auto_commit:
        await session.commit()
        await session.refresh(reconciliation)
    else:
        await session.flush()
    return reconciliation


def _projection_checksum(
    samples: list[ReadingSample],
    previous_samples: dict[int, ReadingSample],
    boundaries: dict[int, m.MeasurementBoundary],
    members: dict[int, list[m.MeasurementBoundaryMember]],
    use_systems: dict[int, UseSystemMapping],
) -> str:
    digest = hashlib.sha256()
    for sample in samples:
        digest.update(
            f"{sample.fact.id}|{sample.fact.reading_time.isoformat()}|{sample.fact.normalized_value}|"
            f"{sample.fact.quality_status}|{sample.fact.mapping_version}\n".encode()
        )
    for equipment_id, sample in sorted(previous_samples.items()):
        digest.update(
            f"anchor|{equipment_id}|{sample.fact.id}|{sample.fact.reading_time.isoformat()}|"
            f"{sample.fact.normalized_value}|{sample.fact.quality_status}|{sample.fact.mapping_version}\n".encode()
        )
    for equipment_id, boundary in sorted(boundaries.items()):
        digest.update(
            f"boundary|{equipment_id}|{boundary.id}|{boundary.mapping_version}|{boundary.include_in_scope2}|"
            f"{boundary.valid_from}|{boundary.valid_to}\n".encode()
        )
        for member in sorted(members.get(boundary.id, []), key=lambda item: item.member_code):
            digest.update(
                f"member|{member.member_code}|{member.member_type}|{member.sector_id}|{member.equipment_id}|"
                f"{member.allocation_weight}\n".encode()
            )
    for equipment_id, mapping in sorted(use_systems.items()):
        digest.update(
            f"system|{equipment_id}|{mapping.code}|{mapping.name}|{mapping.valid_from}|{mapping.valid_to}\n".encode()
        )
    return digest.hexdigest()


def _mapping_snapshot(
    sample: ReadingSample,
    boundary: m.MeasurementBoundary | None,
    members: dict[int, list[m.MeasurementBoundaryMember]],
    use_system_mapping: UseSystemMapping | None,
) -> dict[str, Any]:
    use_system_code = boundary.use_system_code if boundary and boundary.use_system_code else None
    use_system_name = use_system_mapping.name if use_system_mapping is not None else None
    if use_system_code is None and use_system_mapping is not None:
        use_system_code = use_system_mapping.code
    return {
        "equipment_code": sample.equipment.code,
        "area_code": sample.area.code if sample.area else None,
        "area_name": sample.area.name if sample.area else None,
        "boundary_id": boundary.id if boundary else None,
        "boundary_code": boundary.code if boundary else None,
        "mapping_version": boundary.mapping_version if boundary else None,
        "use_system_code": use_system_code,
        "use_system_name": use_system_name,
        "confirmed_member_codes": [member.member_code for member in members.get(boundary.id, [])] if boundary else [],
    }


def _issue(sample: ReadingSample, issue_type: str, detail: str) -> dict[str, Any]:
    return {"sample": sample, "issue_type": issue_type, "detail": detail, "severity": "warning"}


def _roll_up_daily(hourly: dict[tuple[int, datetime], dict[str, Any]]) -> dict[tuple[int, datetime], dict[str, Any]]:
    daily: dict[tuple[int, datetime], dict[str, Any]] = {}
    for (equipment_id, _hour), item in hourly.items():
        day_start = item["period_start"].replace(hour=0, minute=0, second=0, microsecond=0)
        key = (equipment_id, day_start)
        target = daily.setdefault(
            key,
            {
                "sample": item["sample"],
                "period_start": day_start,
                "period_end": day_start + timedelta(days=1),
                "amount": Decimal(0),
                "reading_count": 0,
                "data_quality": "measured",
                "snapshot": item["snapshot"],
            },
        )
        target["amount"] += item["amount"]
        target["reading_count"] += item["reading_count"]
        if item["data_quality"] != "measured":
            target["data_quality"] = item["data_quality"]
    return daily
