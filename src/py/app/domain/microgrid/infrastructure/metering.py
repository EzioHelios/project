"""Meter-binding projection adapter for microgrid forecasting and operations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select

from app.db import models as m

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

EXPECTED_INTERVALS = 21 * 24 * 4
MINIMUM_INTERVALS = 864
MINIMUM_COVERAGE_PCT = 80.0
MAX_GAP = timedelta(hours=1)
MAX_STALENESS = timedelta(minutes=30)
SOURCE_REF_PREFIX = "meter-binding-projection-v1"


@dataclass(frozen=True)
class ProjectionReadiness:
    """Auditable readiness result for measured microgrid history."""

    ready: bool
    valid_intervals: int
    expected_intervals: int
    coverage_pct: float
    latest_at: datetime | None
    stale: bool
    binding_count: int
    equipment_ids: list[int]
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "validIntervals": self.valid_intervals,
            "expectedIntervals": self.expected_intervals,
            "coveragePct": self.coverage_pct,
            "latestAt": self.latest_at.isoformat() if self.latest_at else None,
            "stale": self.stale,
            "bindingCount": self.binding_count,
            "equipmentIds": self.equipment_ids,
            "reasons": self.reasons,
            "sourceKind": "measured_projection" if self.ready else "simulated_fallback",
        }


@dataclass(frozen=True)
class RegisterReading:
    """Minimal cumulative-register input used by the deterministic projector."""

    observed_at: datetime
    value_kwh: float


@dataclass(frozen=True)
class ProjectedPower:
    """Validated interval power calculated from two cumulative readings."""

    observed_at: datetime
    power_kw: float


def project_register_series(
    readings: list[RegisterReading], *, sign: float, rated_power_kw: float | None
) -> list[ProjectedPower]:
    """Project cumulative kWh into interval power while rejecting resets, gaps, and jumps."""
    projected: list[ProjectedPower] = []
    previous: RegisterReading | None = None
    rated_limit = max(float(rated_power_kw or 0) * 2.5, 1000.0)
    for current in sorted(readings, key=lambda item: item.observed_at):
        if previous is None:
            previous = current
            continue
        previous_at = _aware_utc(previous.observed_at)
        current_at = _aware_utc(current.observed_at)
        duration = current_at - previous_at
        delta = current.value_kwh - previous.value_kwh
        previous = current
        if duration <= timedelta(0) or duration > MAX_GAP or delta < 0:
            continue
        power_kw = delta / (duration.total_seconds() / 3600) * sign
        if abs(power_kw) > rated_limit:
            continue
        interval_at = current_at.replace(minute=(current_at.minute // 15) * 15, second=0, microsecond=0)
        projected.append(ProjectedPower(observed_at=interval_at, power_kw=power_kw))
    return projected


class MicrogridMeterProjection:
    """Convert cumulative platform meter registers into 15-minute power facts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def project(self, *, site_id: int, end: datetime | None = None) -> ProjectionReadiness:
        site = await self._session.get(m.MicrogridSite, site_id)
        if site is None:
            msg = "microgrid site not found"
            raise ValueError(msg)
        end_at = (end or datetime.now(UTC)).astimezone(UTC)
        start_at = end_at - timedelta(days=21)
        bindings = await self._bindings(site_id)
        if not bindings:
            return self._empty_readiness(["尚未绑定平台电表"])

        equipment_ids = sorted({binding.equipment_id for binding, _, _ in bindings})
        point_codes = sorted({binding.point_code for binding, _, _ in bindings})
        reading_rows = (
            (
                await self._session.execute(
                    select(m.MeterReadingFact)
                    .where(
                        m.MeterReadingFact.equipment_id.in_(equipment_ids),
                        m.MeterReadingFact.point_code.in_(point_codes),
                        m.MeterReadingFact.value_kind == "register_index",
                        m.MeterReadingFact.reading_time >= (start_at - MAX_GAP).replace(tzinfo=None),
                        m.MeterReadingFact.reading_time <= end_at.replace(tzinfo=None),
                        m.MeterReadingFact.normalized_value.is_not(None),
                    )
                    .order_by(
                        m.MeterReadingFact.equipment_id,
                        m.MeterReadingFact.point_code,
                        m.MeterReadingFact.reading_time,
                        m.MeterReadingFact.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        by_meter: dict[tuple[int, str], list[m.MeterReadingFact]] = defaultdict(list)
        for row in reading_rows:
            by_meter[(row.equipment_id, row.point_code)].append(row)

        asset_values: dict[tuple[int, datetime], float] = defaultdict(float)
        for binding, asset, _equipment in bindings:
            rows = by_meter.get((binding.equipment_id, binding.point_code), [])
            series = [
                RegisterReading(observed_at=row.reading_time, value_kwh=float(row.normalized_value or 0))
                for row in rows
            ]
            direction_sign = -1.0 if binding.direction == "export" else 1.0
            for point in project_register_series(
                series,
                sign=float(binding.sign) * direction_sign,
                rated_power_kw=float(asset.rated_power_kw) if asset.rated_power_kw is not None else None,
            ):
                if point.observed_at < start_at:
                    continue
                asset_values[(asset.id, point.observed_at)] += point.power_kw

        source_ref = f"{SOURCE_REF_PREFIX}:{site.id}"
        await self._session.execute(
            delete(m.MicrogridTelemetryFact).where(
                m.MicrogridTelemetryFact.site_id == site.id,
                m.MicrogridTelemetryFact.source_kind == "measured_projection",
                m.MicrogridTelemetryFact.source_ref == source_ref,
                m.MicrogridTelemetryFact.observed_at >= start_at,
            )
        )
        facts = [
            m.MicrogridTelemetryFact(
                team_id=site.team_id,
                site_id=site.id,
                asset_id=asset_id,
                metric_code="active_power_kw",
                value=Decimal(str(round(value, 6))),
                unit="kW",
                observed_at=observed_at,
                source_kind="measured_projection",
                source_ref=source_ref,
                quality="A",
            )
            for (asset_id, observed_at), value in asset_values.items()
        ]
        self._session.add_all(facts)
        await self._session.commit()
        return await self.readiness(site_id=site.id, end=end_at)

    async def readiness(self, *, site_id: int, end: datetime | None = None) -> ProjectionReadiness:
        end_at = (end or datetime.now(UTC)).astimezone(UTC)
        start_at = end_at - timedelta(days=21)
        bindings = await self._bindings(site_id)
        fixed_load_asset_ids = sorted({asset.id for binding, asset, _ in bindings if binding.role == "fixed_load"})
        equipment_ids = sorted({binding.equipment_id for binding, _, _ in bindings})
        if not fixed_load_asset_ids:
            return self._empty_readiness(["尚未绑定固定负荷电表"], len(bindings), equipment_ids)
        rows = (
            (
                await self._session.execute(
                    select(m.MicrogridTelemetryFact.observed_at)
                    .where(
                        m.MicrogridTelemetryFact.site_id == site_id,
                        m.MicrogridTelemetryFact.asset_id.in_(fixed_load_asset_ids),
                        m.MicrogridTelemetryFact.metric_code == "active_power_kw",
                        m.MicrogridTelemetryFact.source_kind == "measured_projection",
                        m.MicrogridTelemetryFact.observed_at >= start_at,
                        m.MicrogridTelemetryFact.observed_at <= end_at,
                    )
                    .distinct()
                    .order_by(m.MicrogridTelemetryFact.observed_at)
                )
            )
            .scalars()
            .all()
        )
        valid = len(rows)
        coverage = min(valid / EXPECTED_INTERVALS * 100, 100.0)
        latest = _aware_utc(rows[-1]) if rows else None
        stale = latest is None or end_at - latest > MAX_STALENESS
        reasons: list[str] = []
        if valid < MINIMUM_INTERVALS:
            reasons.append(f"有效15分钟点不足{MINIMUM_INTERVALS}个")
        if coverage < MINIMUM_COVERAGE_PCT:
            reasons.append(f"最近21天覆盖率低于{MINIMUM_COVERAGE_PCT:.0f}%")
        if stale:
            reasons.append("最新固定负荷数据超过30分钟")
        return ProjectionReadiness(
            ready=not reasons,
            valid_intervals=valid,
            expected_intervals=EXPECTED_INTERVALS,
            coverage_pct=round(coverage, 2),
            latest_at=latest,
            stale=stale,
            binding_count=len(bindings),
            equipment_ids=equipment_ids,
            reasons=reasons,
        )

    async def _bindings(
        self, site_id: int
    ) -> list[tuple[m.MicrogridAssetMeterBinding, m.MicrogridAsset, m.MonitorEquipment]]:
        return list(
            (
                await self._session.execute(
                    select(m.MicrogridAssetMeterBinding, m.MicrogridAsset, m.MonitorEquipment)
                    .join(m.MicrogridAsset, m.MicrogridAsset.id == m.MicrogridAssetMeterBinding.asset_id)
                    .join(m.MonitorEquipment, m.MonitorEquipment.id == m.MicrogridAssetMeterBinding.equipment_id)
                    .where(
                        m.MicrogridAssetMeterBinding.site_id == site_id,
                        m.MicrogridAssetMeterBinding.enabled.is_(True),
                    )
                )
            ).all()
        )

    @staticmethod
    def _empty_readiness(
        reasons: list[str], binding_count: int = 0, equipment_ids: list[int] | None = None
    ) -> ProjectionReadiness:
        return ProjectionReadiness(
            False, 0, EXPECTED_INTERVALS, 0, None, True, binding_count, equipment_ids or [], reasons
        )


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


__all__ = (
    "MicrogridMeterProjection",
    "ProjectedPower",
    "ProjectionReadiness",
    "RegisterReading",
    "project_register_series",
)
