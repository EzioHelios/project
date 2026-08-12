"""Persisted Xiangtai demo cycle and tenant-isolation test."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.db import models as m
from app.domain.microgrid.infrastructure.weather import demo_weather
from app.domain.microgrid.usecases import BootstrapXiangtaiDemo, CreateDispatchBatch, RunForecast, RunOptimization
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


class FakeWeatherAdapter:
    """Deterministic weather adapter for integration tests."""

    async def forecast(self, **kwargs: Any):
        return demo_weather(start=kwargs["start"], periods=kwargs["periods"])


async def test_xiangtai_demo_persists_full_shadow_dispatch_cycle(session) -> None:
    team = m.Team(name="Xiangtai Test", slug="xiangtai-test")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id

    site = await BootstrapXiangtaiDemo(session).execute()
    assert (
        await session.scalar(
            select(func.count())
            .select_from(m.MicrogridTelemetryFact)
            .where(m.MicrogridTelemetryFact.site_id == site.id)
        )
        == 576
    )
    await BootstrapXiangtaiDemo(session).execute()
    assert (
        await session.scalar(
            select(func.count())
            .select_from(m.MicrogridTelemetryFact)
            .where(m.MicrogridTelemetryFact.site_id == site.id)
        )
        == 576
    )
    forecast = await RunForecast(session, weather=FakeWeatherAdapter()).execute(site_id=site.id)
    optimization = await RunOptimization(session).execute(forecast_run_id=forecast.id)
    dispatch = await CreateDispatchBatch(session).execute(optimization_run_id=optimization.id)

    assert forecast.status == "completed"
    assert optimization.status == "optimal"
    assert dispatch.status == "completed"
    assert (
        await session.scalar(
            select(func.count()).select_from(m.ForecastPoint).where(m.ForecastPoint.run_id == forecast.id)
        )
        == 288
    )
    assert (
        await session.scalar(
            select(func.count())
            .select_from(m.OptimizationSchedulePoint)
            .where(m.OptimizationSchedulePoint.run_id == optimization.id)
        )
        == 96
    )
    assert (
        await session.scalar(
            select(func.count()).select_from(m.DispatchReceipt).where(m.DispatchReceipt.batch_id == dispatch.id)
        )
        == 288
    )
    schedule = (
        (
            await session.execute(
                select(m.OptimizationSchedulePoint)
                .where(m.OptimizationSchedulePoint.run_id == optimization.id)
                .order_by(m.OptimizationSchedulePoint.valid_at)
            )
        )
        .scalars()
        .all()
    )
    assert float(schedule[-1].soc_pct) >= 52
    assert all(
        float(point.charger_kw) == 0
        for point in schedule
        if not 7 <= point.valid_at.astimezone(ZoneInfo("Asia/Shanghai")).hour < 22
    )
    assert len(optimization.input_snapshot["flexibilityContractIds"]) == 2

    other_team = m.Team(name="Other Tenant", slug="other-tenant")
    session.info.clear()
    session.add(other_team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = other_team.id
    assert (await session.scalars(select(m.MicrogridSite))).all() == []
