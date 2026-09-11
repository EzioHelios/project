from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.carbon.services._bigscreen import (
    BigscreenCarbonService,
    BigscreenOverviewService,
    BigscreenPowerService,
)

pytestmark = [pytest.mark.anyio, pytest.mark.unit]


def result(rows=(), scalar=0):
    value = MagicMock()
    value.all.return_value = rows
    value.scalar_one.return_value = scalar
    value.scalars.return_value.all.return_value = rows
    return value


async def test_overview_keeps_independent_energy_and_carbon_periods():
    session = AsyncMock()
    session.execute.side_effect = [result([("2025-12", 12)]), result(scalar=1), result(scalar=2), result()]
    with patch("app.domain.carbon.services._bigscreen._canonical_monthly_carbon", return_value={"2026-06": 42}):
        payload = await BigscreenOverviewService(session).build()
    assert payload.energy_kpis[1].label == "2025年累计用电"
    assert payload.carbon_kpis[0].value == 42
    assert payload.carbon_kpis[0].emphasis == "核算期 2026-06"
    assert payload.carbon_kpis[1].value == 42
    assert payload.production_trend[0].carbon_co2e is None


async def test_missing_overview_data_is_not_zero():
    session = AsyncMock()
    session.execute.side_effect = [result(), result()]
    with patch("app.domain.carbon.services._bigscreen._canonical_monthly_carbon", return_value={}):
        payload = await BigscreenOverviewService(session).build()
    assert all(metric.value is None for metric in payload.energy_kpis)
    assert all(metric.value is None for metric in payload.carbon_kpis[:2])
    assert payload.carbon_kpis[2].value == 0
    assert payload.carbon_kpis[2].label == "已启用区域"


async def test_actual_zero_reading_and_carbon_result_remain_zero():
    session = AsyncMock()
    session.execute.side_effect = [result([("2026-06", 0)]), result(scalar=1), result(), result()]
    with patch("app.domain.carbon.services._bigscreen._canonical_monthly_carbon", return_value={"2026-06": 0}):
        payload = await BigscreenOverviewService(session).build()
    assert payload.energy_kpis[0].value == 0
    assert payload.carbon_kpis[0].value == 0
    assert payload.production_trend[0].carbon_co2e == 0


async def test_missing_power_aggregate_preserves_known_device_count():
    session = AsyncMock()
    session.execute.side_effect = [result(), result(), result(scalar=8), result(scalar=8)]
    with patch("app.domain.carbon.services._bigscreen._canonical_monthly_carbon", return_value={}):
        payload = await BigscreenPowerService(session).build()
    assert payload.hero_metrics[1].value == 8
    assert payload.hero_metrics[2].value is None


async def test_missing_carbon_results_do_not_fabricate_scope_charts():
    session = AsyncMock()
    session.scalar.return_value = None
    session.execute.side_effect = [result(), result()]
    payload = await BigscreenCarbonService(session).build()
    assert payload.hero_metrics[0].value is None
    assert payload.hero_metrics[1].value is None
    assert payload.carbon_compare == []
    assert payload.production_share == []
    assert payload.carbon_flow.nodes == []
