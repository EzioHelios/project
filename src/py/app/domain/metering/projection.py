"""Bounded, current-only electricity projection and Scope 2 reconciliation."""

from __future__ import annotations

# ruff: noqa: PLR0915
import asyncio
import hashlib
import json
import logging
import os
import pickle
import resource
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import groupby
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import cast, delete, func, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import raiseload

from app.db import models as m
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from _hashlib import HASH
    from collections.abc import AsyncIterator, Iterator
    from typing import BinaryIO
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


MAX_INTERVAL_DELTA_KWH = Decimal(100000)
MAX_EXPECTED_GAP = timedelta(hours=6)
FIXED_VALUE_THRESHOLD = timedelta(hours=6)
MONTHS_PER_YEAR = 12
PROJECTION_VERSION = "current_v1"
BATCH_SIZE = min(1000, max(1, int(os.getenv("METERING_PROJECTION_BATCH_SIZE", "1000"))))
MAX_METERS = 10000
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
    fact: m.MeterReadingFact | FactValue
    equipment: m.MonitorEquipment | EquipmentValue
    area: m.MonitorSector | AreaValue | None


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
    """Project canonical cumulative readings into bounded current statistics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        tenant_id = session.info.get(TENANT_ID_SESSION_KEY)
        if tenant_id is None:
            msg = "Electricity projection requires an active tenant"
            raise ValueError(msg)
        self.team_id: UUID = tenant_id

    async def rebuild_month(self, billing_month: str, *, area_id: str | None = None) -> ProjectionResult:
        """Publish one complete month atomically, without retaining derived revisions."""
        if os.getenv("METERING_PROJECTION_ENABLED", "true").lower() not in {"true", "1", "yes"}:
            msg = "Electricity projection is disabled"
            raise ProjectionUnavailableError(msg)
        period_start, period_end = month_window(billing_month)
        lock_key = int.from_bytes(hashlib.sha256(f"electricity:{self.team_id}".encode()).digest()[:8], signed=True)
        if not await self.session.scalar(select(func.pg_try_advisory_xact_lock(lock_key))):
            msg = "Another projection or cleanup owns this tenant"
            raise ProjectionUnavailableError(msg)
        monitor = ProjectionMonitor(self.team_id, billing_month)
        run_data: dict[str, Any] = {
            "team_id": self.team_id,
            "run_code": f"electricity:{billing_month}:{uuid4().hex}",
            "projection_type": "electricity_interval",
            "period_start": period_start,
            "period_end": period_end,
            "status": "running",
            "mapping_version": PROJECTION_VERSION,
            "started_at": datetime.now(UTC).replace(tzinfo=None),
            "run_config": {"area_id": area_id},
        }
        try:
            # A private, bounded disk spool fixes the input for both checksum and calculation.
            # No published results or historical versions are stored here.
            with tempfile.TemporaryFile() as spool:
                boundaries, members = await self._load_boundaries(period_start.date(), period_end.date())
                systems = await self._load_use_system_bindings(period_start.date(), period_end.date())
                first_by_meter: dict[int, ReadingSample] = {}
                digest = hashlib.sha256(PROJECTION_VERSION.encode())
                source_count = watermark = 0
                async for sample in self._stream_period_samples(period_start, period_end, area_id):
                    first_by_meter.setdefault(sample.equipment.id, sample)
                    if len(first_by_meter) > MAX_METERS:
                        msg = "Projection meter count exceeds 10000"
                        raise ProjectionBudgetExceededError(msg)  # noqa: TRY301
                    _hash_sample(digest, sample)
                    pickle.dump(sample, spool, protocol=pickle.HIGHEST_PROTOCOL)
                    source_count += 1
                    watermark = max(watermark, sample.fact.id)
                    if source_count % BATCH_SIZE == 0:
                        monitor.check("read", source_count)
                        if spool.tell() > int(os.getenv("METERING_PROJECTION_SPOOL_MB", "1024")) * 1024**2:
                            msg = "Projection input exceeds disk spool budget"
                            raise ProjectionBudgetExceededError(msg)  # noqa: TRY301
                previous = await self._load_previous_samples(list(first_by_meter.values()), period_start)
                checksum = _projection_checksum([], previous, boundaries, members, systems, digest=digest)
                monitor.check("read_complete", source_count)
                run_data.update(
                    source_count=source_count, source_high_watermark=str(watermark), source_checksum=checksum
                )
                existing = await self.session.scalar(
                    select(m.EnergyProjectionRun)
                    .where(
                        m.EnergyProjectionRun.period_start == period_start,
                        m.EnergyProjectionRun.status == "completed",
                        m.EnergyProjectionRun.mapping_version == PROJECTION_VERSION,
                        m.EnergyProjectionRun.run_config["area_id"].as_string() == area_id
                        if area_id
                        else m.EnergyProjectionRun.run_config["area_id"].as_string().is_(None),
                    )
                    .order_by(m.EnergyProjectionRun.id.desc())
                    .limit(1)
                )
                if existing is not None and existing.source_checksum == checksum:
                    # Bills may change while meter input remains unchanged.
                    await reconcile_scope2_electricity(self.session, billing_month, auto_commit=False)
                    config = existing.run_config or {}
                    counts: list[int] = config["counts"]
                    result = ProjectionResult(existing.id, existing.run_code, source_count, *counts, reused=True)
                    existing.run_config = {**config, "last_checked_at": datetime.now(UTC).isoformat()}
                    await self.session.commit()
                    return result
                run = m.EnergyProjectionRun(**run_data)
                self.session.add(run)
                await self.session.flush()
                await self.session.execute(
                    text(
                        "CREATE TEMP TABLE projection_current_seen (kind text, key text, PRIMARY KEY(kind,key)) ON COMMIT DROP"
                    )
                )
                hourly_count = daily_count = aggregate_count = issue_count = 0
                spool.seek(0)
                for equipment_id, samples in groupby(_spooled_samples(spool), lambda sample: sample.equipment.id):
                    acc = IntervalAccumulator(previous.get(equipment_id), boundaries, members, systems)
                    for index, sample in enumerate(samples, 1):
                        acc.feed(sample)
                        if len(acc.issues) >= BATCH_SIZE:
                            issue_count += await self._write_quality_issues(run, acc.issues)
                            acc.issues.clear()
                        if index % BATCH_SIZE == 0:
                            monitor.check("calculate", index)
                            await asyncio.sleep(0)
                    acc.finish()
                    issue_count += await self._write_quality_issues(run, acc.issues)
                    hourly_count += await self._write_intervals(run, acc.hourly, "hour")
                    daily_count += await self._write_intervals(run, _roll_up_daily(acc.hourly), "day")
                    ranges = (
                        {equipment_id: (acc.first, acc.before)}
                        if acc.has_range and acc.first is not None and acc.before is not None
                        else {}
                    )
                    aggregates = await self._write_scope2_aggregates(run, billing_month, acc.hourly, ranges, boundaries)
                    aggregate_count += len(aggregates)
                    monitor.check("write_meter", hourly_count + daily_count)
                await self._delete_absent_results(run, billing_month)
                await reconcile_scope2_electricity(
                    self.session, billing_month, projection_run_id=run.id, auto_commit=False
                )
                run.status = "completed"
                run.output_count = hourly_count + daily_count
                run.issue_count = issue_count
                run.finished_at = datetime.now(UTC).replace(tzinfo=None)
                run.run_config = {
                    "area_id": area_id,
                    "counts": [hourly_count, daily_count, aggregate_count, issue_count],
                    "peak_rss_mb": monitor.peak_mb,
                }
                result = ProjectionResult(
                    run.id, run.run_code, source_count, hourly_count, daily_count, aggregate_count, issue_count
                )
                monitor.check("before_commit", run.output_count)
                await self.session.commit()
                return result
        except BaseException as exc:
            await self.session.rollback()
            # Recreate only the execution log after rollback, never reattach partial outputs.
            if isinstance(exc, Exception):
                self.session.add(
                    m.EnergyProjectionRun(
                        **{
                            **run_data,
                            "status": "failed",
                            "error_detail": str(exc)[:4000],
                            "finished_at": datetime.now(UTC).replace(tzinfo=None),
                        }
                    )
                )
                await self.session.commit()
            raise

    async def _stream_period_samples(
        self, period_start: datetime, period_end: datetime, area_id: str | None
    ) -> AsyncIterator[ReadingSample]:
        stmt = (
            select(m.MeterReadingFact, m.MonitorEquipment, m.MonitorSector)
            .join(m.MonitorEquipment, m.MonitorEquipment.id == m.MeterReadingFact.equipment_id)
            .outerjoin(m.MonitorSector, m.MonitorSector.id == m.MonitorEquipment.sector_id)
            .options(raiseload("*"))
            .where(
                m.MeterReadingFact.reading_time >= period_start,
                m.MeterReadingFact.reading_time < period_end,
                m.MeterReadingFact.point_code == "forward_active_total",
                m.MeterReadingFact.value_kind == "register_index",
                m.MeterReadingFact.normalized_value.is_not(None),
                m.MonitorEquipment.is_enable.is_(True),
            )
            .order_by(m.MeterReadingFact.equipment_id, m.MeterReadingFact.reading_time, m.MeterReadingFact.id)
            .execution_options(yield_per=BATCH_SIZE)
        )
        if area_id:
            stmt = stmt.where(
                m.MonitorSector.id == int(area_id) if area_id.isdigit() else m.MonitorSector.code == area_id
            )
        rows = await self.session.stream(stmt)
        try:
            async for fact, equipment, area in rows:
                yield ReadingSample(
                    fact=FactValue(
                        fact.id,
                        fact.reading_time,
                        Decimal(str(fact.normalized_value)),
                        fact.quality_status,
                        fact.mapping_version,
                        fact.source_system,
                        fact.point_code,
                    ),
                    equipment=EquipmentValue(equipment.id, equipment.code, equipment.name, equipment.sector_id),
                    area=AreaValue(area.code, area.name) if area else None,
                )
        finally:
            await rows.close()

    async def _mark_seen(self, kind: str, keys: list[str]) -> None:
        if keys:
            await self.session.execute(
                text("INSERT INTO projection_current_seen VALUES (:kind, :key) ON CONFLICT DO NOTHING"),
                [{"kind": kind, "key": key} for key in keys],
            )

    async def _delete_absent_results(self, run: m.EnergyProjectionRun, billing_month: str) -> None:
        area_id = (run.run_config or {}).get("area_id")
        area_code = None
        if area_id:
            area_code = await self.session.scalar(
                select(m.MonitorSector.code).where(
                    m.MonitorSector.id == int(area_id) if area_id.isdigit() else m.MonitorSector.code == area_id
                )
            )
            if area_code is None:
                msg = "Unknown projection area"
                raise ValueError(msg)
        for model, kind, key, conditions in (
            (
                m.EnergyIntervalFact,
                "interval",
                m.EnergyIntervalFact.source_record_id,
                [
                    m.EnergyIntervalFact.source_system.in_(["meter_projection", "meter_hourly", "meter_daily"]),
                    m.EnergyIntervalFact.granularity.in_(["hour", "day"]),
                    m.EnergyIntervalFact.period_start >= run.period_start,
                    m.EnergyIntervalFact.period_start < run.period_end,
                ],
            ),
            (
                m.Scope2MeterAggregate,
                "aggregate",
                m.Scope2MeterAggregate.ammeter_id,
                [
                    m.Scope2MeterAggregate.billing_month == billing_month,
                    m.Scope2MeterAggregate.projection_run_id.is_not(None),
                ],
            ),
        ):
            seen = select(text("key")).select_from(text("projection_current_seen")).where(text("kind = :kind"))
            stmt = delete(model).where(model.team_id == self.team_id, *conditions, key.not_in(seen))
            if area_id:
                stmt = stmt.where(model.area_id == area_code)
            await self.session.execute(stmt.execution_options(synchronize_session=False), {"kind": kind})

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
                .limit(MAX_METERS + 1)
            )
        ).all()
        _check_metadata_size(len(rows))
        by_meter: dict[int, m.MeasurementBoundary] = {}
        for row in rows:
            if row.meter_equipment_id is None:
                continue
            if row.meter_equipment_id in by_meter:
                msg = f"本月电表匹配多个计量边界: {by_meter[row.meter_equipment_id].code}、{row.code}"
                raise ValueError(msg)
            by_meter[row.meter_equipment_id] = row
        boundary_ids = [row.id for row in rows]
        confirmed_members: list[m.MeasurementBoundaryMember] = (
            list(
                (
                    await self.session.scalars(
                        select(m.MeasurementBoundaryMember)
                        .limit(MAX_METERS + 1)
                        .where(
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
        _check_metadata_size(len(confirmed_members))
        members: dict[int, list[m.MeasurementBoundaryMember]] = defaultdict(list)
        for member in confirmed_members:
            members[member.boundary_id].append(member)
        return by_meter, members

    async def _load_use_system_bindings(self, period_start: date, period_end: date) -> dict[int, UseSystemMapping]:
        rows = (
            await self.session.execute(
                select(m.EnergyUseSystemBinding, m.EnergyUseSystem.name)
                .limit(MAX_METERS + 1)
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
        _check_metadata_size(len(rows))
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
        """Small-input adapter for callers/tests; production consumes the accumulator incrementally."""
        hourly: dict[tuple[int, datetime], dict[str, Any]] = {}
        issues: list[dict[str, Any]] = []
        ranges: dict[int, tuple[ReadingSample, ReadingSample]] = {}
        for equipment_id, samples in groupby(period_samples, lambda sample: sample.equipment.id):
            acc = IntervalAccumulator(previous_samples.get(equipment_id), boundaries, members, use_systems)
            for sample in samples:
                acc.feed(sample)
            acc.finish()
            hourly.update(acc.hourly)
            issues.extend(acc.issues)
            if acc.has_range and acc.first is not None and acc.before is not None:
                ranges[equipment_id] = (acc.first, acc.before)
        return hourly, issues, ranges

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
                    fact=FactValue(
                        fact.id,
                        fact.reading_time,
                        Decimal(str(fact.normalized_value)),
                        fact.quality_status,
                        fact.mapping_version,
                        fact.source_system,
                        fact.point_code,
                    ),
                    equipment=fallback.equipment,
                    area=fallback.area,
                )
        return previous_samples

    async def _write_intervals(
        self, run: m.EnergyProjectionRun, intervals: dict[tuple[int, datetime], dict[str, Any]], granularity: str
    ) -> int:
        rows: list[dict[str, Any]] = []
        for (equipment_id, period), item in intervals.items():
            source_record_id = f"meter:{equipment_id}:{granularity}:{period.isoformat()}"
            sample: ReadingSample = item["sample"]
            snapshot = item["snapshot"]
            rows.append(
                {
                    "team_id": self.team_id,
                    "source_system": "meter_projection",
                    "source_record_id": source_record_id,
                    "energy_type_code": "purchased_electricity",
                    "equipment_id": equipment_id,
                    "equipment_code": sample.equipment.code,
                    "equipment_name": sample.equipment.name,
                    "area_id": sample.area.code if sample.area else None,
                    "area_name": sample.area.name if sample.area else None,
                    "use_system_code": snapshot.get("use_system_code"),
                    "use_system_name": snapshot.get("use_system_name"),
                    "granularity": granularity,
                    "period_start": item["period_start"],
                    "period_end": item["period_end"],
                    "amount": item["amount"],
                    "unit": "kWh",
                    "cost_cny": None,
                    "reading_count": item["reading_count"],
                    "data_quality": item["data_quality"],
                    "projection_run_id": run.id,
                    "measurement_boundary_id": snapshot.get("boundary_id"),
                    "revision_no": 1,
                    "is_current": True,
                    "supersedes_id": None,
                    "source_snapshot": snapshot,
                }
            )
        for offset in range(0, len(rows), BATCH_SIZE):
            batch = rows[offset : offset + BATCH_SIZE]
            await _upsert_current(
                self.session, m.EnergyIntervalFact, batch, ["team_id", "source_system", "source_record_id"]
            )
            await self._mark_seen("interval", [row["source_record_id"] for row in batch])
        # Legacy sources are superseded only inside the successfully rebuilt scope.
        if rows:
            await self.session.execute(
                delete(m.EnergyIntervalFact)
                .where(
                    m.EnergyIntervalFact.team_id == self.team_id,
                    m.EnergyIntervalFact.equipment_id == next(iter(intervals))[0],
                    m.EnergyIntervalFact.granularity == granularity,
                    m.EnergyIntervalFact.period_start >= run.period_start,
                    m.EnergyIntervalFact.period_start < run.period_end,
                    m.EnergyIntervalFact.source_system.in_(["meter_hourly", "meter_daily"]),
                )
                .execution_options(synchronize_session=False)
            )
        return len(intervals)

    async def _write_quality_issues(self, run: m.EnergyProjectionRun, issues: list[dict[str, Any]]) -> int:
        rows: list[dict[str, Any]] = []
        for issue in issues:
            sample: ReadingSample = issue["sample"]
            issue_key = f"electricity:{sample.equipment.id}:{issue['issue_type']}:{sample.fact.id}"
            rows.append(
                {
                    "team_id": self.team_id,
                    "issue_key": issue_key,
                    "projection_run_id": run.id,
                    "equipment_id": sample.equipment.id,
                    "point_code": sample.fact.point_code,
                    "reading_time": sample.fact.reading_time,
                    "issue_type": issue["issue_type"],
                    "severity": issue.get("severity", "warning"),
                    "status": "open",
                    "detail": issue["detail"],
                    "issue_payload": {"source_fact_id": sample.fact.id},
                }
            )
        if rows:
            stmt = insert(m.MeteringQualityIssue).values(rows)
            await self.session.execute(stmt.on_conflict_do_nothing(index_elements=["team_id", "issue_key"]))
        return len(issues)

    async def _write_scope2_aggregates(
        self,
        run: m.EnergyProjectionRun,
        billing_month: str,
        hourly: dict[tuple[int, datetime], dict[str, Any]],
        meter_ranges: dict[int, tuple[ReadingSample, ReadingSample]],
        boundaries: dict[int, m.MeasurementBoundary],
    ) -> list[dict[str, Any]]:
        totals: dict[int, Decimal] = defaultdict(Decimal)
        for (equipment_id, _period), item in hourly.items():
            boundary = boundaries.get(equipment_id)
            day = item["sample"].fact.reading_time.date()
            if (
                boundary is None
                or not boundary.include_in_scope2
                or boundary.energy_direction != "import"
                or (boundary.valid_from is not None and day < boundary.valid_from)
                or (boundary.valid_to is not None and day > boundary.valid_to)
                or item["data_quality"] == "simulated"
            ):
                continue
            totals[equipment_id] += item["amount"]

        created: list[dict[str, Any]] = []
        for equipment_id, total_kwh in totals.items():
            boundary = boundaries[equipment_id]
            first, last = meter_ranges[equipment_id]
            snapshot = {
                "boundary_code": boundary.code,
                "coverage_status": "configured",
            }
            aggregate = {
                "team_id": self.team_id,
                "source_kind": "meter_aggregate",
                "ammeter_id": first.equipment.code,
                "ammeter_name": first.equipment.name,
                "area_id": first.area.code if first.area else None,
                "area_name": first.area.name if first.area else None,
                "billing_month": billing_month,
                "first_reading_time": first.fact.reading_time,
                "last_reading_time": last.fact.reading_time,
                "start_total_energy": first.fact.normalized_value,
                "end_total_energy": last.fact.normalized_value,
                "total_kwh": total_kwh,
                "status": "provisional",
                "calc_status": "not_applicable",
                "factor_source": None,
                "factor_year": None,
                "factor_unit": None,
                "activity_amount": total_kwh,
                "activity_unit": "kWh",
                "computed_co2e": None,
                "computation_note": "组织温室气体排放由统一盘查运行计算。",
                "aggregation_note": None,
                "projection_run_id": run.id,
                "measurement_boundary_id": boundary.id,
                "revision_no": 1,
                "is_current": True,
                "supersedes_id": None,
                "source_snapshot": snapshot,
            }
            created.append(aggregate)
        await _upsert_current(self.session, m.Scope2MeterAggregate, created, ["team_id", "ammeter_id", "billing_month"])
        await self._mark_seen("aggregate", [row["ammeter_id"] for row in created])
        return created


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

    month_start = date.fromisoformat(f"{billing_month}-01")
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    aggregate_rows: list[m.Scope2MeterAggregate] = list(
        (
            await session.scalars(
                select(m.Scope2MeterAggregate)
                .limit(MAX_METERS + 1)
                .execution_options(populate_existing=True)
                .join(m.MeasurementBoundary, m.MeasurementBoundary.id == m.Scope2MeterAggregate.measurement_boundary_id)
                .where(
                    m.Scope2MeterAggregate.billing_month == billing_month,
                    m.Scope2MeterAggregate.total_kwh.is_not(None),
                    m.MeasurementBoundary.status == "active",
                    m.MeasurementBoundary.include_in_scope2.is_(True),
                    m.MeasurementBoundary.energy_direction == "import",
                    m.MeasurementBoundary.valid_from.is_(None) | (m.MeasurementBoundary.valid_from <= month_end),
                    m.MeasurementBoundary.valid_to.is_(None) | (m.MeasurementBoundary.valid_to >= month_start),
                )
            )
        ).all()
    )
    _check_metadata_size(len(aggregate_rows))
    meter_total = sum((Decimal(str(row.total_kwh or 0)) for row in aggregate_rows), Decimal(0))
    activity_rows: list[m.GhgActivityRecord] = list(
        (
            await session.scalars(
                select(m.GhgActivityRecord)
                .limit(MAX_METERS + 1)
                .where(
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
    _check_metadata_size(len(activity_rows))
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
    source_priority = "ghg_activity" if activity_rows else "meter_aggregate" if aggregate_rows else "none"
    snapshot = {
        "aggregate_ids": sorted(row.id for row in aggregate_rows),
        "activity_ids": sorted(row.id for row in activity_rows),
        "source_priority": source_priority,
        "meter_total": str(meter_total),
        "bill_total": str(bill_total),
        "aggregates": sorted((row.id, str(row.total_kwh)) for row in aggregate_rows),
        "activities": sorted((row.id, str(row.activity_amount), row.activity_unit) for row in activity_rows),
    }
    snapshot["digest"] = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()

    current = await session.scalar(
        select(m.Scope2ElectricityReconciliation).where(
            m.Scope2ElectricityReconciliation.billing_month == billing_month
        )
    )
    if current is not None and (current.source_snapshot or {}).get("digest") == snapshot["digest"]:
        return current

    values = {
        "team_id": tenant_id,
        "billing_month": billing_month,
        "projection_run_id": projection_run_id,
        "activity_record_id": activity_rows[0].id if len(activity_rows) == 1 else None,
        "source_priority": source_priority,
        "organization_total_kwh": organization_total,
        "meter_total_kwh": meter_total,
        "bill_total_kwh": bill_total,
        "allocated_kwh": allocated,
        "unallocated_kwh": unallocated,
        "revision_no": 1,
        "is_current": True,
        "supersedes_id": None,
        "status": "ready" if activity_rows or aggregate_rows else "incomplete",
        "source_snapshot": snapshot,
    }
    reconciliation = current or m.Scope2ElectricityReconciliation(**values)
    if current is not None:
        for key, value in values.items():
            if key != "revision_no":
                setattr(current, key, value)
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
    *,
    digest: HASH | None = None,
) -> str:
    digest = digest if digest is not None else hashlib.sha256(PROJECTION_VERSION.encode())
    for sample in samples:
        _hash_sample(digest, sample)
    for equipment_id, sample in sorted(previous_samples.items()):
        digest.update(
            f"anchor|{equipment_id}|{sample.fact.id}|{sample.fact.reading_time.isoformat()}|"
            f"{sample.fact.normalized_value}|{sample.fact.quality_status}|{sample.fact.mapping_version}\n".encode()
        )
    for equipment_id, boundary in sorted(boundaries.items()):
        digest.update(
            f"boundary|{equipment_id}|{boundary.id}|{boundary.mapping_version}|{boundary.include_in_scope2}|"
            f"{boundary.valid_from}|{boundary.valid_to}|{boundary.energy_direction}|"
            f"{boundary.code}|{boundary.use_system_code}\n".encode()
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
        "reading_source_system": sample.fact.source_system,
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


class ProjectionUnavailableError(RuntimeError):
    """Projection is disabled or the tenant is already being processed."""


class ProjectionBudgetExceededError(RuntimeError):
    """Abort before a bounded projection consumes the worker's resource budget."""


@dataclass(frozen=True, slots=True)
class FactValue:
    id: int
    reading_time: datetime
    normalized_value: Decimal
    quality_status: str
    mapping_version: str
    source_system: str
    point_code: str


@dataclass(frozen=True, slots=True)
class EquipmentValue:
    id: int
    code: str
    name: str | None
    sector_id: int | None


@dataclass(frozen=True, slots=True)
class AreaValue:
    code: str
    name: str | None


def _hash_sample(digest: HASH, sample: ReadingSample) -> None:
    digest.update(
        f"{sample.fact.id}|{sample.fact.reading_time.isoformat()}|{sample.fact.normalized_value}|"
        f"{sample.fact.quality_status}|{sample.fact.mapping_version}|{sample.fact.source_system}|"
        f"{sample.equipment.sector_id}|{sample.equipment.code}|{getattr(sample.equipment, 'name', None)}|"
        f"{sample.area.code if sample.area else ''}|{sample.area.name if sample.area else ''}\n".encode()
    )


def _spooled_samples(spool: BinaryIO) -> Iterator[ReadingSample]:
    while True:
        try:
            yield pickle.load(spool)  # noqa: S301 - private TemporaryFile, written only by this process.
        except EOFError:
            return


async def _upsert_current(
    session: AsyncSession,
    model: type[m.EnergyIntervalFact | m.Scope2MeterAggregate],
    rows: list[dict[str, Any]],
    keys: list[str],
) -> None:
    if not rows:
        return
    stmt = insert(model).values(rows)
    updates = {key: getattr(stmt.excluded, key) for key in rows[0] if key not in keys and key != "revision_no"}
    changes = [
        (
            cast(getattr(model, key), JSONB).is_distinct_from(cast(value, JSONB))
            if key == "source_snapshot"
            else getattr(model, key).is_distinct_from(value)
        )
        for key, value in updates.items()
        if key != "projection_run_id"
    ]
    updates["updated_at"] = datetime.now(UTC)
    result = await session.scalars(
        stmt.on_conflict_do_update(index_elements=keys, set_=updates, where=or_(*changes)).returning(model),
        execution_options={"populate_existing": True},
    )
    result.all()


class ProjectionMonitor:
    def __init__(self, team_id: UUID, month: str) -> None:
        self.team_id, self.month = team_id, month
        self.started = monotonic()
        self.baseline_mb = self.last_mb = _current_rss_mb()
        self.peak_mb = _peak_rss_mb()

    def check(self, stage: str, rows: int) -> None:
        rss = _current_rss_mb()
        self.peak_mb = max(self.peak_mb, _peak_rss_mb())
        job_growth = max(0.0, rss - self.baseline_mb)
        logger.info(
            "projection_stage team=%s month=%s stage=%s rows=%s rss_mb=%.1f job_growth_mb=%.1f "
            "delta_mb=%.1f peak_mb=%.1f seconds=%.2f",
            self.team_id,
            self.month,
            stage,
            rows,
            rss,
            job_growth,
            rss - self.last_mb,
            self.peak_mb,
            monotonic() - self.started,
        )
        self.last_mb = rss
        if job_growth > int(os.getenv("METERING_PROJECTION_RSS_MB", "768")):
            msg = f"Projection RSS growth budget exceeded at {stage}: {job_growth:.1f} MiB"
            raise ProjectionBudgetExceededError(msg)


def _peak_rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024**2 if sys.platform == "darwin" else 1024)


def _current_rss_mb() -> float:
    if sys.platform == "linux":
        with Path("/proc/self/statm").open() as statm:
            return int(statm.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1024**2
    return _peak_rss_mb()


class IntervalAccumulator:
    """One meter's monthly buckets, with constant-size endpoint/deduplication state."""

    def __init__(
        self,
        previous: ReadingSample | None,
        boundaries: dict[int, m.MeasurementBoundary],
        members: dict[int, list[m.MeasurementBoundaryMember]],
        systems: dict[int, UseSystemMapping],
    ) -> None:
        self.before = self.first = previous
        self.pending: ReadingSample | None = None
        self.fixed_since: datetime | None = None
        self.boundaries, self.members, self.systems = boundaries, members, systems
        self.hourly: dict[tuple[int, datetime], dict[str, Any]] = {}
        self.issues: list[dict[str, Any]] = []
        self.has_range = False

    def feed(self, sample: ReadingSample) -> None:
        if self.pending is not None:
            if sample.fact.reading_time == self.pending.fact.reading_time:
                self.issues.append(
                    _issue(sample, "duplicate_timestamp", "Duplicate timestamp; highest source id retained")
                )
                self.pending = sample
                return
            self._accept(self.pending)
        self.pending = sample

    def finish(self) -> None:
        if self.pending is not None:
            self._accept(self.pending)
        if not self.has_range and self.before is not None:
            self.issues.append(_issue(self.before, "insufficient_data", "No preceding valid register reading"))

    def _accept(self, current: ReadingSample) -> None:
        before = self.before
        self.first = self.first or current
        self.before = current
        if before is None:
            return
        self.has_range = True
        if current.fact.quality_status != "valid" or before.fact.quality_status != "valid":
            self.issues.append(_issue(current, "invalid_quality", "Interval endpoint has invalid source quality"))
            return
        delta = Decimal(str(current.fact.normalized_value)) - Decimal(str(before.fact.normalized_value))
        elapsed = current.fact.reading_time - before.fact.reading_time
        if delta < 0:
            self.issues.append(_issue(current, "register_reset", "Cumulative register decreased; interval excluded"))
            self.fixed_since = None
            return
        if delta > MAX_INTERVAL_DELTA_KWH:
            self.issues.append(_issue(current, "abnormal_spike", "Interval delta exceeded the configured limit"))
            self.fixed_since = None
            return
        quality = "simulated" if any(s.fact.source_system.startswith("demo") for s in (before, current)) else "measured"
        if elapsed > MAX_EXPECTED_GAP:
            self.issues.append(
                _issue(current, "reading_gap", f"Reading gap is {elapsed.total_seconds() / 3600:.2f} hours")
            )
            self.fixed_since = None
            return
        if delta == 0:
            self.fixed_since = self.fixed_since or before.fact.reading_time
            if current.fact.reading_time - self.fixed_since >= FIXED_VALUE_THRESHOLD:
                self.issues.append(
                    _issue(current, "fixed_value", "Cumulative register remained unchanged for six hours")
                )
                self.fixed_since = current.fact.reading_time
        else:
            self.fixed_since = None
        equipment_id = current.equipment.id
        hour = current.fact.reading_time.replace(minute=0, second=0, microsecond=0)
        item = self.hourly.setdefault(
            (equipment_id, hour),
            {
                "sample": current,
                "period_start": hour,
                "period_end": hour + timedelta(hours=1),
                "amount": Decimal(0),
                "reading_count": 0,
                "data_quality": quality,
                "snapshot": _mapping_snapshot(
                    current, self.boundaries.get(equipment_id), self.members, self.systems.get(equipment_id)
                ),
            },
        )
        item["amount"] += delta
        item["reading_count"] += 1
        if quality != "measured":
            item["data_quality"] = quality


def _check_metadata_size(count: int) -> None:
    if count > MAX_METERS:
        msg = f"Projection metadata exceeds {MAX_METERS} rows"
        raise ProjectionBudgetExceededError(msg)
