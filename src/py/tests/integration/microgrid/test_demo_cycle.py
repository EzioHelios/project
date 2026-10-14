"""Persisted Xiangtai demo cycle and tenant-isolation test."""

from __future__ import annotations

from datetime import time
from decimal import Decimal
from threading import get_ident
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.db import models as m
from app.domain.microgrid.domain.exceptions import InfeasibleDispatchError, ScenarioNotReadyError
from app.domain.microgrid.infrastructure.weather import demo_weather
from app.domain.microgrid.usecases import (
    BootstrapXiangtaiDemo,
    CreateDispatchBatch,
    RunForecast,
    RunOptimization,
    operations,
)
from app.domain.microgrid.usecases.bindings import BindingTemplate
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


class FakeWeatherAdapter:
    """Deterministic weather adapter for integration tests."""

    async def forecast(self, **kwargs: Any):
        return demo_weather(start=kwargs["start"], periods=kwargs["periods"])


async def test_xiangtai_demo_persists_full_shadow_dispatch_cycle(session, monkeypatch) -> None:
    event_loop_thread = get_ident()
    prediction_threads = []
    original_forecast = operations.forecast_load_quantiles

    def tracked_forecast(**kwargs):
        prediction_threads.append(get_ident())
        return original_forecast(**kwargs)

    monkeypatch.setattr(operations, "forecast_load_quantiles", tracked_forecast)
    team = m.Team(name="Woheng Test", slug="woheng-taizhou-production-base", is_active=True)
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id

    tariff = m.EnergyTariffPlan(
        team_id=team.id,
        code="default_electricity_tou",
        name="测试分时电价",
        energy_type_code="electricity",
        is_enabled=True,
    )
    factor = m.EmissionFactor(
        scope="scope2",
        category="electricity",
        sub_category="grid_electricity_jiangsu",
        unit="kWh",
        factor_value=Decimal("0.5827"),
        factor_unit="kgCO2e/kWh",
        year=2023,
        source="测试台账",
        is_active=True,
    )
    session.add_all([tariff, factor])
    await session.flush()
    session.add(
        m.EnergyTariffSegment(
            team_id=team.id,
            plan_id=tariff.id,
            segment_type="flat",
            start_time=time(0),
            end_time=time(23, 59, 59),
            price=Decimal("0.76"),
            sort_index=0,
        )
    )
    await session.commit()

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
    with pytest.raises(ScenarioNotReadyError, match="only applies to the Xiangtai site"):
        await BindingTemplate(session).execute(site.id)

    forecast = await RunForecast(session, weather=FakeWeatherAdapter()).execute(site_id=site.id)
    assert prediction_threads and all(thread != event_loop_thread for thread in prediction_threads)
    assert forecast.quality_status == "warning"
    with pytest.raises(ScenarioNotReadyError, match="acknowledged risk trial"):
        await RunOptimization(session).execute(forecast_run_id=forecast.id)
    trial = await RunOptimization(session).execute(
        forecast_run_id=forecast.id,
        purpose="trial",
        acknowledge_quality_warning=True,
    )
    with pytest.raises(InfeasibleDispatchError, match="trial optimization runs cannot be dispatched"):
        await CreateDispatchBatch(session).execute(optimization_run_id=trial.id)

    forecast.quality_status = "pass"
    await session.commit()
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
