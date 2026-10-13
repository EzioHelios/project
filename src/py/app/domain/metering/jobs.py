"""Refresh energy projections from persisted readings, independently of acquisition."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.config import alchemy
from app.db import models as m
from app.domain.metering.projection import PROJECTION_VERSION, ElectricityProjectionUseCase
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from saq.types import Context
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


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
                m.EnergyProjectionRun.status == "completed", m.EnergyProjectionRun.mapping_version == PROJECTION_VERSION
            )
            .order_by(m.EnergyProjectionRun.id.desc())
        )
    ).all()
    watermarks: dict[str, int] = {}
    for run in runs:
        if not (run.run_config or {}).get("area_id"):
            watermarks.setdefault(run.period_start.strftime("%Y-%m"), int(run.source_high_watermark or 0))
    return [period for period, watermark in rows if int(watermark) > watermarks.get(period, 0)]


async def refresh_electricity_projections(_: Context) -> dict[str, int]:
    """Run tenant-isolated catch-up in bounded batches; retry unfinished months next cycle."""
    async with alchemy.get_session() as session:
        team_ids = (await session.scalars(select(m.Team.id).where(m.Team.is_active.is_(True)))).all()
    failures = []
    summary = {"tenants": len(team_ids), "months": 0, "reused": 0, "hourly_facts": 0, "pending_months": 0}
    for team_id in team_ids:
        async with alchemy.get_session() as session:
            session.info[TENANT_ID_SESSION_KEY] = team_id
            try:
                pending = await pending_projection_months(session)
                summary["pending_months"] += max(len(pending) - 3, 0)
                for month in pending[:3]:
                    result = await ElectricityProjectionUseCase(session).rebuild_month(month)
                    summary["months"] += 1
                    summary["reused"] += int(result.reused)
                    summary["hourly_facts"] += result.hourly_facts
                    logger.info(
                        "Energy projection team=%s month=%s facts=%s reused=%s",
                        team_id,
                        month,
                        result.hourly_facts,
                        result.reused,
                    )
            except Exception:
                await session.rollback()
                logger.exception("Energy projection failed for team=%s", team_id)
                failures.append(str(team_id))
    if failures:
        msg = f"Energy projection failed for {len(failures)} tenant(s); see worker log"
        raise RuntimeError(msg)
    return summary
