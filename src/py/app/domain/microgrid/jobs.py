"""SAQ jobs for rolling microgrid forecasts and optimization."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import desc, select

from app.config import alchemy
from app.db import models as m
from app.domain.microgrid.infrastructure.metering import MicrogridMeterProjection
from app.domain.microgrid.usecases import RunForecast, RunOptimization
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY

if TYPE_CHECKING:
    from saq.types import Context

logger = logging.getLogger(__name__)


async def project_microgrid_meter_history(_: Context) -> None:
    """Refresh the latest 21-day measured projections for explicitly bound sites."""
    async with alchemy.get_session() as session:
        session.info[TENANT_BYPASS_SESSION_KEY] = True
        site_ids = (
            await session.scalars(
                select(m.MicrogridAssetMeterBinding.site_id)
                .where(m.MicrogridAssetMeterBinding.enabled.is_(True))
                .distinct()
            )
        ).all()
        for site_id in site_ids:
            try:
                await MicrogridMeterProjection(session).project(site_id=site_id)
            except Exception:
                logger.exception("Microgrid meter projection failed for site %s", site_id)


async def run_microgrid_forecast_cycle(_: Context) -> None:
    """Refresh every published microgrid site's 24-hour forecast."""
    async with alchemy.get_session() as session:
        session.info[TENANT_BYPASS_SESSION_KEY] = True
        sites = (
            (await session.execute(select(m.MicrogridSite).where(m.MicrogridSite.status == "shadow"))).scalars().all()
        )
        for site in sites:
            try:
                await RunForecast(session).execute(site_id=site.id)
            except Exception:
                logger.exception("Microgrid forecast failed for site %s", site.code)


async def run_microgrid_optimization_cycle(_: Context) -> None:
    """Optimize the newest forecast not yet linked to an optimization run."""
    async with alchemy.get_session() as session:
        session.info[TENANT_BYPASS_SESSION_KEY] = True
        sites = (
            (await session.execute(select(m.MicrogridSite).where(m.MicrogridSite.status == "shadow"))).scalars().all()
        )
        for site in sites:
            forecast = await session.scalar(
                select(m.ForecastRun)
                .where(
                    m.ForecastRun.site_id == site.id,
                    m.ForecastRun.status == "completed",
                    m.ForecastRun.quality_status == "pass",
                )
                .order_by(desc(m.ForecastRun.created_at))
            )
            if forecast is None:
                continue
            existing = await session.scalar(
                select(m.OptimizationRun.id).where(m.OptimizationRun.forecast_run_id == forecast.id).limit(1)
            )
            if existing is not None:
                continue
            try:
                await RunOptimization(session).execute(forecast_run_id=forecast.id)
            except Exception:
                logger.exception("Microgrid optimization failed for site %s", site.code)


async def refresh_microgrid_load_models(context: Context) -> None:
    """Nightly model refresh; the run promotes quantile models over the calendar fallback."""
    await run_microgrid_forecast_cycle(context)
