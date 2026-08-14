"""Forecast and MILP acceptance tests."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.microgrid.infrastructure.forecasting import forecast_load_quantiles, forecast_pv_quantiles
from app.domain.microgrid.infrastructure.metering import RegisterReading, project_register_series
from app.domain.microgrid.infrastructure.optimization import optimize_dispatch
from app.domain.microgrid.infrastructure.weather import demo_weather, history_for_training

pytestmark = pytest.mark.unit


def _parameters() -> dict:
    return {
        "interval_minutes": 15,
        "grid": {"pcc_capacity_kw": 1250, "export_capacity_kw": 300},
        "storage": {
            "capacity_kwh": 1000,
            "power_kw": 500,
            "initial_soc_pct": 52,
            "minimum_soc_pct": 15,
            "maximum_soc_pct": 90,
            "charging_efficiency": 0.95,
            "discharging_efficiency": 0.95,
        },
        "charger": {
            "minimum_power_kw": 0,
            "maximum_power_kw": 240,
            "target_energy_kwh": 720,
            "start_interval": 28,
            "end_interval": 88,
        },
        "lighting": {"baseline_power_kw": 80, "minimum_power_kw": 44},
        "generator": {"maximum_power_kw": 0, "fuel_cny_per_kwh": 1.8},
        "economics": {
            "battery_degradation_cny_per_kwh": 0.08,
            "export_cny_per_kwh": 0.25,
            "demand_cny_per_kw_day": 0.35,
            "grid_carbon_kg_per_kwh": 0.5703,
            "carbon_cny_per_kg": 0.08,
            "curtailment_cny_per_kwh": 0.02,
        },
    }


def test_quantile_forecast_is_ordered_and_complete() -> None:
    start = datetime(2026, 8, 12, tzinfo=ZoneInfo("Asia/Shanghai"))
    history_index, load, temperature = history_for_training(end=start)
    target = [start + timedelta(minutes=15 * index) for index in range(96)]
    points, metrics = forecast_load_quantiles(
        history_index=history_index,
        history_kw=load,
        history_temperature_c=temperature,
        forecast_index=target,
        forecast_temperature_c=[31.0] * 96,
    )

    assert len(points) == 96
    assert all(point.p10 <= point.p50 <= point.p90 for point in points)
    assert metrics["model"] == "hist-gradient-boosting-quantile-v1"


def test_pv_model_is_zero_at_night_and_bounded_by_inverter() -> None:
    start = datetime(2026, 8, 12, tzinfo=ZoneInfo("Asia/Shanghai"))
    points = forecast_pv_quantiles(
        latitude=32.42,
        longitude=119.89,
        dc_capacity_kw=600,
        ac_capacity_kw=500,
        tilt_deg=18,
        azimuth_deg=180,
        weather=demo_weather(start=start),
    )

    assert len(points) == 96
    assert points[0].p50 == 0
    assert max(point.p90 for point in points) <= 500


def test_milp_returns_balanced_96_point_schedule_with_savings() -> None:
    start = datetime(2026, 8, 12, tzinfo=ZoneInfo("Asia/Shanghai"))
    index = [start + timedelta(minutes=15 * position) for position in range(96)]
    pv = [max(0.0, 420 - (position - 48) ** 2) for position in range(96)]
    tariff = [
        0.42 if position < 28 or position > 88 else 1.26 if 36 < position < 80 else 0.76 for position in range(96)
    ]
    result = optimize_dispatch(
        index=index,
        fixed_load_kw=[450] * 96,
        pv_available_kw=pv,
        tariff_cny_per_kwh=tariff,
        parameters=_parameters(),
    )

    assert result.status == "optimal"
    assert len(result.schedule) == 96
    assert result.savings_cny is not None and result.savings_cny > 0
    assert result.objective_cny == pytest.approx(sum(result.cost_breakdown.values()), abs=1e-4)
    assert result.schedule[-1].soc_pct >= 52
    assert sum(point.charger_kw * 0.25 for point in result.schedule) >= 720
    for point in result.schedule:
        assert 15 <= point.soc_pct <= 90
        assert point.lighting_kw >= 44
        supply = point.grid_import_kw + point.pv_kw + point.battery_discharge_kw + point.generator_kw
        demand = point.load_kw + point.charger_kw + point.lighting_kw + point.battery_charge_kw + point.grid_export_kw
        assert supply == pytest.approx(demand, abs=1e-4)


def test_infeasible_charging_deadline_produces_no_dispatchable_schedule() -> None:
    start = datetime(2026, 8, 12, tzinfo=ZoneInfo("Asia/Shanghai"))
    index = [start + timedelta(minutes=15 * position) for position in range(96)]
    parameters = _parameters()
    parameters["charger"]["target_energy_kwh"] = 10_000

    result = optimize_dispatch(
        index=index,
        fixed_load_kw=[450] * 96,
        pv_available_kw=[0] * 96,
        tariff_cny_per_kwh=[0.76] * 96,
        parameters=parameters,
    )

    assert result.status == "infeasible"
    assert result.schedule == []
    assert result.diagnostics[0]["constraint"] == "charger_energy_deadline"
    assert result.diagnostics[-1]["constraint"] == "system_feasibility"


def test_soft_charging_deadline_returns_penalized_shortfall() -> None:
    start = datetime(2026, 8, 12, tzinfo=ZoneInfo("Asia/Shanghai"))
    index = [start + timedelta(minutes=15 * position) for position in range(96)]
    parameters = _parameters()
    parameters["charger"]["target_energy_kwh"] = 10_000
    parameters["charger"]["hard_constraint"] = False
    parameters["charger"]["penalty_cny_per_kwh"] = 8

    result = optimize_dispatch(
        index=index,
        fixed_load_kw=[450] * 96,
        pv_available_kw=[0] * 96,
        tariff_cny_per_kwh=[0.76] * 96,
        parameters=parameters,
    )

    assert result.status == "optimal"
    assert result.cost_breakdown["flexibility_penalty_cny"] > 0
    assert result.diagnostics[-1]["constraint"] == "charger_energy_deadline"


def test_register_projection_rejects_reset_gap_duplicate_and_jump() -> None:
    start = datetime(2026, 8, 12, tzinfo=UTC)
    readings = [
        RegisterReading(start, 100),
        RegisterReading(start + timedelta(minutes=15), 110),
        RegisterReading(start + timedelta(minutes=15), 110),
        RegisterReading(start + timedelta(minutes=30), 2),
        RegisterReading(start + timedelta(hours=2), 3),
        RegisterReading(start + timedelta(hours=2, minutes=15), 10_000),
        RegisterReading(start + timedelta(hours=2, minutes=30), 10_010),
    ]

    projected = project_register_series(readings, sign=-1, rated_power_kw=100)

    assert [(point.observed_at, point.power_kw) for point in projected] == [
        (start + timedelta(minutes=15), -40),
        (start + timedelta(hours=2, minutes=30), -40),
    ]
