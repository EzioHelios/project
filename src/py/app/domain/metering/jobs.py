"""Refresh energy projections from persisted readings, independently of acquisition."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

from sqlalchemy import func, select

from app.config import alchemy
from app.db import models as m
from app.domain.metering.projection import PROJECTION_VERSION, ElectricityProjectionUseCase, ProjectionUnavailableError
from app.domain.metering.projection_guard import ProjectionGuard
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from saq.queue.redis import RedisQueue
    from saq.types import Context
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
MONTHS_PER_CYCLE = 3


async def pending_projection_months(session: AsyncSession) -> list[str]:
    """Find new or late-arriving immutable readings not covered by a completed run."""
    month = func.to_char(m.MeterReadingFact.reading_time, "YYYY-MM")
    rows = (
        await session.execute(
            select(month, func.max(m.MeterReadingFact.id))
            .join(m.MonitorEquipment, m.MonitorEquipment.id == m.MeterReadingFact.equipment_id)
            .where(
                m.MeterReadingFact.point_code == "forward_active_total",
                m.MeterReadingFact.value_kind == "register_index",
                m.MeterReadingFact.normalized_value.is_not(None),
                ~m.MeterReadingFact.source_system.like("demo%"),
                m.MonitorEquipment.is_enable.is_(True),
            )
            .group_by(month)
            .order_by(month.desc())
        )
    ).all()
    runs = (
        await session.scalars(
            select(m.EnergyProjectionRun)
            .where(
                m.EnergyProjectionRun.status == "completed",
                m.EnergyProjectionRun.mapping_version == PROJECTION_VERSION,
                m.EnergyProjectionRun.run_config["area_id"].as_string().is_(None),
            )
            .distinct(m.EnergyProjectionRun.period_start)
            .order_by(m.EnergyProjectionRun.period_start, m.EnergyProjectionRun.id.desc())
        )
    ).all()
    watermarks: dict[str, int] = {}
    due: set[str] = set()
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
    for run in runs:
        if not (run.run_config or {}).get("area_id"):
            period = run.period_start.strftime("%Y-%m")
            if period not in watermarks:
                watermarks[period] = int(run.source_high_watermark or 0)
                checked = (run.run_config or {}).get("last_checked_at")
                finished = datetime.fromisoformat(checked) if checked else getattr(run, "finished_at", None)
                if finished is not None and finished.replace(tzinfo=None) < cutoff:
                    due.add(period)
    sources = {str(period): int(watermark) for period, watermark in rows}
    return sorted(
        {period for period, watermark in rows if int(watermark) > watermarks.get(period, 0)}
        | due
        | {period for period, watermark in watermarks.items() if watermark and period not in sources},
        reverse=True,
    )


async def refresh_electricity_projections(ctx: Context) -> dict[str, int]:
    """Catch up current statistics; failed/killed attempts cool down across worker restarts."""
    if os.getenv("METERING_PROJECTION_ENABLED", "true").lower() not in {"true", "1", "yes"}:
        return {"disabled": 1}
    queue = cast("RedisQueue", ctx["queue"] if "queue" in ctx else ctx["worker"].queue)
    redis = queue.redis
    async with alchemy.get_session() as session:
        team_ids = (await session.scalars(select(m.Team.id).where(m.Team.is_active.is_(True)))).all()
    summary = {
        "tenants": len(team_ids),
        "months": 0,
        "reused": 0,
        "hourly_facts": 0,
        "pending_months": 0,
        "deferred": 0,
        "failed": 0,
    }
    for team_id in team_ids:
        async with alchemy.get_session() as session:
            session.info[TENANT_ID_SESSION_KEY] = team_id
            pending = await pending_projection_months(session)
            await session.commit()
            attempted = 0
            for month in pending:
                if attempted >= MONTHS_PER_CYCLE:
                    summary["pending_months"] += 1
                    continue
                guard = ProjectionGuard(redis, str(team_id), month)
                status = await guard.claim()
                if status != "claimed":
                    summary["deferred"] += 1
                    logger.warning("Projection deferred team=%s month=%s status=%s", team_id, month, status)
                    continue
                attempted += 1
                try:
                    result = await ElectricityProjectionUseCase(session).rebuild_month(month)
                except ProjectionUnavailableError:
                    await session.rollback()
                    await guard.finish("busy")
                    summary["deferred"] += 1
                except BaseException:
                    await session.rollback()
                    await guard.finish("failed")
                    summary["failed"] += 1
                    logger.exception("Energy projection failed team=%s month=%s", team_id, month)
                    # Cancellation must still reach SAQ. Ordinary failures are handled by the breaker.
                    import sys

                    if not isinstance(sys.exception(), Exception):
                        raise
                else:
                    await guard.finish("success")
                    summary["months"] += 1
                    summary["reused"] += int(result.reused)
                    summary["hourly_facts"] += result.hourly_facts
    return summary
