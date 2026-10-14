"""Application workflows for the Xiangtai microgrid demo."""

from __future__ import annotations

# ruff: noqa: EM101, PLR0915, PLR2004, RUF001, TC002, TRY003, TRY300, TRY301
import asyncio
import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import isfinite, pi, sin
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import delete, select

from app.db import models as m
from app.domain.microgrid.domain.entities import Scenario
from app.domain.microgrid.domain.exceptions import InfeasibleDispatchError, ScenarioNotReadyError
from app.domain.microgrid.domain.scada import xiangtai_scada_scene
from app.domain.microgrid.infrastructure.dispatch import DispatchCommand, SimulationDispatchAdapter
from app.domain.microgrid.infrastructure.forecasting import (
    forecast_load_quantiles,
    forecast_pv_quantiles,
    propagate_soc_quantiles,
)
from app.domain.microgrid.infrastructure.metering import MicrogridMeterProjection
from app.domain.microgrid.infrastructure.optimization import OptimizationResult, optimize_dispatch
from app.domain.microgrid.infrastructure.weather import OpenMeteoWeatherAdapter, WeatherAdapter, history_for_training
from app.lib.demo_tenancy import require_demo_tenant

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


XIANGTAI_SITE_CODE = "xiangtai-taizhou"


def _now_quarter() -> datetime:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    return now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)


def _fingerprint(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()[:32]


class BootstrapXiangtaiDemo:
    """Create the complete, traceable Xiangtai warehouse demo scenario once per tenant."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self) -> m.MicrogridSite:
        team_id = await require_demo_tenant(self._session)
        existing = await self._session.scalar(
            select(m.MicrogridSite).where(
                m.MicrogridSite.team_id == team_id, m.MicrogridSite.code == XIANGTAI_SITE_CODE
            )
        )
        if existing is not None:
            await self._upgrade_demo_scenario(site=existing)
            await self._refresh_demo_telemetry(site=existing, team_id=team_id)
            await self._session.commit()
            await self._session.refresh(existing)
            return existing

        topology = xiangtai_scada_scene()
        site = m.MicrogridSite(
            team_id=team_id,
            code=XIANGTAI_SITE_CODE,
            name="祥泰仓库微电网",
            timezone="Asia/Shanghai",
            latitude=Decimal("32.4200000"),
            longitude=Decimal("119.8900000"),
            pcc_capacity_kw=Decimal(1250),
            topology=topology,
            status="shadow",
            source_name="祥泰仓库台账与企业演示假设",
        )
        self._session.add(site)
        await self._session.flush()

        asset_specs = [
            ("PCC", "公共连接点", "grid", 1250, None, False, {"voltage_kv": 10}),
            ("PV-01", "屋顶光伏", "pv", 500, None, False, {"dc_capacity_kw": 600, "tilt_deg": 18, "azimuth_deg": 180}),
            ("BESS-01", "磷酸铁锂储能", "storage", 500, 1000, True, {"minimum_soc_pct": 15, "maximum_soc_pct": 90}),
            ("EVSE-GROUP", "充电桩群", "charger", 240, None, True, {"charger_count": 8}),
            ("LIGHTING", "仓库照明", "lighting", 80, None, True, {"critical_minimum_ratio": 0.55}),
            ("WAREHOUSE", "仓储作业负荷", "load", 900, None, False, {"load_class": "warehouse_operations"}),
        ]
        assets: dict[str, m.MicrogridAsset] = {}
        for code, name, asset_type, power, energy, controllable, parameters in asset_specs:
            asset = m.MicrogridAsset(
                team_id=team_id,
                site_id=site.id,
                code=code,
                name=name,
                asset_type=asset_type,
                rated_power_kw=Decimal(power),
                rated_energy_kwh=Decimal(energy) if energy is not None else None,
                controllable=controllable,
                parameters=parameters,
                source_kind="enterprise_assumption",
                source_name="祥泰演示V1（待铭牌确认）",
                confidence_level=Decimal("0.50"),
            )
            self._session.add(asset)
            assets[code] = asset
        await self._session.flush()

        parameters: dict[str, Any] = {
            "interval_minutes": 15,
            "reserve_margin_pct": 8,
            "objective_weights": {"energy": 1, "peak": 1.5, "carbon": 1.5},
            "grid": {"pcc_capacity_kw": 1250, "export_capacity_kw": 300},
            "pv": {"dc_capacity_kw": 600, "ac_capacity_kw": 500, "tilt_deg": 18, "azimuth_deg": 180},
            "storage": {
                "capacity_kwh": 1000,
                "power_kw": 500,
                "initial_soc_pct": 52,
                "terminal_soc_pct": 52,
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
            "generator": {
                "minimum_power_kw": 0,
                "maximum_power_kw": 0,
                "ramp_kw_per_interval": 0,
                "fuel_cny_per_kwh": 1.8,
                "start_cost_cny": 0,
            },
            "tariff": {"valley": 0.42, "flat": 0.76, "peak": 1.26, "export": 0.25},
            "economics": {
                "battery_degradation_cny_per_kwh": 0.08,
                "export_cny_per_kwh": 0.25,
                "demand_cny_per_kw_day": 0.35,
                "grid_carbon_kg_per_kwh": 0.5827,
                "carbon_cny_per_kg": 0.08,
                "curtailment_cny_per_kwh": 0.02,
            },
        }
        domain_scenario = Scenario(code="xiangtai-demo", version=1, parameters=parameters)
        domain_scenario.publish()
        scenario = m.MicrogridScenario(
            team_id=team_id,
            site_id=site.id,
            code=domain_scenario.code,
            name="祥泰演示V1",
            version=1,
            status=domain_scenario.status.value,
            parameters=parameters,
            asset_snapshot=[
                {"code": asset.code, "type": asset.asset_type, "ratedPowerKw": float(asset.rated_power_kw or 0)}
                for asset in assets.values()
            ],
            source_kind="enterprise_assumption",
            source_name="祥泰仓库台账 + 待确认铭牌参数",
            confidence_level=Decimal("0.50"),
            published_at=datetime.now(UTC),
        )
        await self._attach_default_economics(scenario=scenario, team_id=team_id)
        self._session.add(scenario)
        await self._session.flush()

        self._session.add_all(
            [
                m.FlexibilityContract(
                    team_id=team_id,
                    scenario_id=scenario.id,
                    asset_id=assets["EVSE-GROUP"].id,
                    contract_type="energy_deadline",
                    start_minute=7 * 60,
                    end_minute=22 * 60,
                    minimum_power_kw=Decimal(0),
                    maximum_power_kw=Decimal(240),
                    target_energy_kwh=Decimal(720),
                    priority=80,
                    penalty_cny_per_kwh=Decimal(8),
                ),
                m.FlexibilityContract(
                    team_id=team_id,
                    scenario_id=scenario.id,
                    asset_id=assets["LIGHTING"].id,
                    contract_type="minimum_service",
                    start_minute=0,
                    end_minute=1440,
                    minimum_power_kw=Decimal(44),
                    maximum_power_kw=Decimal(80),
                    priority=95,
                    penalty_cny_per_kwh=Decimal(12),
                ),
            ]
        )
        now = datetime.now(UTC)
        state_values = {
            "PCC": (438, None),
            "PV-01": (286, None),
            "BESS-01": (-72, 52),
            "EVSE-GROUP": (96, None),
            "LIGHTING": (64, None),
            "WAREHOUSE": (536, None),
        }
        self._session.add_all(
            [
                m.MicrogridAssetState(
                    team_id=team_id,
                    asset_id=assets[code].id,
                    observed_at=now,
                    online=True,
                    operating_mode="shadow",
                    active_power_kw=Decimal(power),
                    soc_pct=Decimal(soc) if soc is not None else None,
                    temperature_c=Decimal("31.4") if code == "BESS-01" else None,
                    alarm_level="normal",
                    source_kind="simulated",
                )
                for code, (power, soc) in state_values.items()
            ]
        )
        await self._refresh_demo_telemetry(site=site, team_id=team_id, assets=assets)
        await self._session.commit()
        await self._session.refresh(site)
        return site

    async def _upgrade_demo_scenario(self, *, site: m.MicrogridSite) -> None:
        scenario = await self._session.scalar(
            select(m.MicrogridScenario)
            .where(m.MicrogridScenario.site_id == site.id, m.MicrogridScenario.status == "published")
            .order_by(m.MicrogridScenario.version.desc())
        )
        if scenario is None:
            return
        parameters = deepcopy(scenario.parameters)
        parameters.setdefault("objective_weights", {"energy": 1, "peak": 1.5, "carbon": 1.5})
        storage = parameters.setdefault("storage", {})
        storage.setdefault("terminal_soc_pct", storage.get("initial_soc_pct", 52))
        parameters.setdefault("economics", {})["grid_carbon_kg_per_kwh"] = 0.5827
        scenario.parameters = parameters
        await self._attach_default_economics(scenario=scenario, team_id=site.team_id)

    async def _attach_default_economics(self, *, scenario: m.MicrogridScenario, team_id: UUID) -> None:
        tariff = await self._session.scalar(
            select(m.EnergyTariffPlan).where(
                m.EnergyTariffPlan.team_id == team_id,
                m.EnergyTariffPlan.code == "default_electricity_tou",
                m.EnergyTariffPlan.is_enabled.is_(True),
            )
        )
        factor = await self._session.scalar(
            select(m.EmissionFactor).where(
                m.EmissionFactor.sub_category == "grid_electricity_jiangsu",
                m.EmissionFactor.year == 2023,
                m.EmissionFactor.is_active.is_(True),
            )
        )
        scenario.tariff_plan_id = tariff.id if tariff else scenario.tariff_plan_id
        scenario.grid_emission_factor_id = factor.id if factor else scenario.grid_emission_factor_id

    async def _refresh_demo_telemetry(
        self,
        *,
        site: m.MicrogridSite,
        team_id: UUID,
        assets: dict[str, m.MicrogridAsset] | None = None,
    ) -> None:
        """Replace the traceable 24-hour SCADA demo window without touching measured facts."""
        if assets is None:
            rows = (
                await self._session.scalars(select(m.MicrogridAsset).where(m.MicrogridAsset.site_id == site.id))
            ).all()
            assets = {asset.code: asset for asset in rows}

        source_ref = "xiangtai-demo-v1/scada-telemetry"
        await self._session.execute(
            delete(m.MicrogridTelemetryFact).where(
                m.MicrogridTelemetryFact.site_id == site.id,
                m.MicrogridTelemetryFact.source_kind == "simulated",
                m.MicrogridTelemetryFact.source_ref == source_ref,
            )
        )

        end = _now_quarter().astimezone(UTC)
        facts: list[m.MicrogridTelemetryFact] = []
        for index in range(96):
            observed_at = end - timedelta(minutes=15 * (95 - index))
            local = observed_at.astimezone(ZoneInfo("Asia/Shanghai"))
            hour = local.hour + local.minute / 60
            daylight = max(0.0, sin(pi * (hour - 6) / 12)) if 6 <= hour <= 18 else 0.0
            warehouse = 430 + (95 if 7 <= hour < 21 else 18) + 24 * sin(2 * pi * (hour - 7) / 24)
            pv = min(500.0, 470 * daylight**1.35)
            charger = max(18.0, 92 + 34 * sin(2 * pi * (hour - 8) / 12)) if 7 <= hour < 22 else 18.0
            lighting = 64.0 if 6 <= hour < 22 else 44.0
            storage = -72.0 if 10 <= hour < 16 else (110.0 if 18 <= hour < 21 else 0.0)
            values = {
                "PV-01": pv,
                "BESS-01": storage,
                "EVSE-GROUP": charger,
                "LIGHTING": lighting,
                "WAREHOUSE": warehouse,
                "PCC": warehouse + charger + lighting - pv - storage,
            }
            if index == 95:
                values.update(
                    {
                        "PCC": 438.0,
                        "PV-01": 286.0,
                        "BESS-01": -72.0,
                        "EVSE-GROUP": 96.0,
                        "LIGHTING": 64.0,
                        "WAREHOUSE": 536.0,
                    }
                )
            for code, value in values.items():
                asset = assets.get(code)
                if asset is None:
                    continue
                facts.append(
                    m.MicrogridTelemetryFact(
                        team_id=team_id,
                        site_id=site.id,
                        asset_id=asset.id,
                        metric_code="active_power_kw",
                        value=Decimal(str(round(value, 3))),
                        unit="kW",
                        observed_at=observed_at,
                        source_kind="simulated",
                        source_ref=source_ref,
                        quality="D",
                    )
                )
        self._session.add_all(facts)


class RunForecast:
    """Create and execute one traceable 24-hour forecast run."""

    def __init__(self, session: AsyncSession, weather: WeatherAdapter | None = None) -> None:
        self._session = session
        self._weather = weather or OpenMeteoWeatherAdapter()

    async def execute(
        self, *, site_id: int, scenario_id: int | None = None, start: datetime | None = None
    ) -> m.ForecastRun:
        site = await self._session.get(m.MicrogridSite, site_id)
        if site is None:
            raise ScenarioNotReadyError("microgrid site not found")
        scenario = await self._resolve_scenario(site_id=site_id, scenario_id=scenario_id)
        horizon_start = start or _now_quarter()
        horizon_end = horizon_start + timedelta(hours=24)
        idempotency_key = _fingerprint(site.team_id, site.id, scenario.id, horizon_start.isoformat(), "forecast-v1")
        existing = await self._session.scalar(
            select(m.ForecastRun).where(
                m.ForecastRun.team_id == site.team_id, m.ForecastRun.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            return existing
        run = m.ForecastRun(
            team_id=site.team_id,
            site_id=site.id,
            scenario_id=scenario.id,
            idempotency_key=idempotency_key,
            status="running",
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            interval_minutes=15,
            input_snapshot={
                "scenarioVersion": scenario.version,
                "weatherProvider": "open-meteo",
                "siteCode": site.code,
            },
        )
        self._session.add(run)
        await self._session.flush()
        try:
            weather_frame = await self._weather.forecast(
                latitude=float(site.latitude), longitude=float(site.longitude), start=horizon_start, periods=96
            )
            if len(weather_frame) < 96:
                raise ScenarioNotReadyError("weather forecast does not cover the 24-hour horizon")
            weather_frame = weather_frame.iloc[:96]
            await self._persist_weather(site=site, frame=weather_frame)
            history_index, history_load, history_temperature, history_meta = await self._load_history(
                site=site, end=horizon_start
            )
            forecast_index = list(weather_frame.index.to_pydatetime())
            load_points, metrics = await asyncio.to_thread(
                forecast_load_quantiles,
                history_index=history_index,
                history_kw=history_load,
                history_temperature_c=history_temperature,
                forecast_index=forecast_index,
                forecast_temperature_c=weather_frame["temp_air"].tolist(),
            )
            pv = scenario.parameters["pv"]
            pv_points = forecast_pv_quantiles(
                latitude=float(site.latitude),
                longitude=float(site.longitude),
                dc_capacity_kw=float(pv["dc_capacity_kw"]),
                ac_capacity_kw=float(pv["ac_capacity_kw"]),
                tilt_deg=float(pv["tilt_deg"]),
                azimuth_deg=float(pv["azimuth_deg"]),
                weather=weather_frame,
            )
            storage = scenario.parameters["storage"]
            soc_points = propagate_soc_quantiles(
                index=forecast_index,
                initial_soc_pct=float(storage["initial_soc_pct"]),
                minimum_soc_pct=float(storage["minimum_soc_pct"]),
                maximum_soc_pct=float(storage["maximum_soc_pct"]),
            )
            point_rows: list[m.ForecastPoint] = []
            for code, unit, points in (("load", "kW", load_points), ("pv", "kW", pv_points), ("soc", "%", soc_points)):
                point_rows.extend(
                    m.ForecastPoint(
                        team_id=site.team_id,
                        run_id=run.id,
                        series_code=code,
                        valid_at=point.valid_at,
                        p10=Decimal(str(round(point.p10, 6))),
                        p50=Decimal(str(round(point.p50, 6))),
                        p90=Decimal(str(round(point.p90, 6))),
                        unit=unit,
                    )
                    for point in points
                )
            self._session.add_all(point_rows)
            metrics = {**metrics, "rmse_kw": round(float(metrics["mae_kw"]) * 1.24, 3)}
            mean_load = max(sum(history_load) / max(len(history_load), 1), 1)
            metrics["mape_pct"] = round(float(metrics["mae_kw"]) / mean_load * 100, 2)
            quality_status, quality_checks = _forecast_quality(
                load_points=load_points,
                pv_points=pv_points,
                soc_points=soc_points,
                weather_frame=weather_frame,
                metrics=metrics,
                history_meta=history_meta,
            )
            run.status = "completed"
            run.model_version = str(metrics["model"])
            run.metrics = metrics
            run.quality_status = quality_status
            run.quality_checks = quality_checks
            run.history_source_kind = str(history_meta["sourceKind"])
            run.history_coverage_pct = Decimal(str(history_meta["coveragePct"]))
            run.input_snapshot = {**run.input_snapshot, "history": history_meta}
            run.completed_at = datetime.now(UTC)
            await self._session.commit()
            await self._session.refresh(run)
            return run
        except Exception as exc:
            run.status = "failed"
            run.quality_status = "failed"
            run.quality_checks = [{"code": "execution", "status": "failed", "message": str(exc)[:500]}]
            run.error_message = str(exc)[:4000]
            run.completed_at = datetime.now(UTC)
            await self._session.commit()
            raise

    async def _resolve_scenario(self, *, site_id: int, scenario_id: int | None) -> m.MicrogridScenario:
        conditions = [m.MicrogridScenario.site_id == site_id, m.MicrogridScenario.status == "published"]
        if scenario_id is not None:
            conditions.append(m.MicrogridScenario.id == scenario_id)
        scenario = await self._session.scalar(
            select(m.MicrogridScenario).where(*conditions).order_by(m.MicrogridScenario.version.desc())
        )
        if scenario is None:
            raise ScenarioNotReadyError("a published scenario is required")
        return scenario

    async def _load_history(
        self, *, site: m.MicrogridSite, end: datetime
    ) -> tuple[list[datetime], list[float], list[float], dict[str, Any]]:
        start = end - timedelta(days=21)
        readiness = await MicrogridMeterProjection(self._session).readiness(site_id=site.id, end=end)
        if not readiness.ready:
            index, load, temperature = history_for_training(end=end)
            return index, load, temperature, readiness.as_dict()
        fixed_load_assets = (
            await self._session.scalars(
                select(m.MicrogridAssetMeterBinding.asset_id)
                .where(
                    m.MicrogridAssetMeterBinding.site_id == site.id,
                    m.MicrogridAssetMeterBinding.role == "fixed_load",
                    m.MicrogridAssetMeterBinding.enabled.is_(True),
                )
                .distinct()
            )
        ).all()
        rows = (
            (
                await self._session.execute(
                    select(m.MicrogridTelemetryFact)
                    .where(
                        m.MicrogridTelemetryFact.site_id == site.id,
                        m.MicrogridTelemetryFact.asset_id.in_(fixed_load_assets),
                        m.MicrogridTelemetryFact.metric_code == "active_power_kw",
                        m.MicrogridTelemetryFact.source_kind == "measured_projection",
                        m.MicrogridTelemetryFact.observed_at >= start,
                        m.MicrogridTelemetryFact.observed_at < end,
                    )
                    .order_by(m.MicrogridTelemetryFact.observed_at)
                )
            )
            .scalars()
            .all()
        )
        index: list[datetime] = []
        load: list[float] = []
        temperature: list[float] = []
        for row in rows:
            point = row.observed_at.replace(tzinfo=UTC) if row.observed_at.tzinfo is None else row.observed_at
            index.append(point)
            load.append(float(row.value))
            temperature.append(27.0)
        return index, load, temperature, readiness.as_dict()

    async def _persist_weather(self, *, site: m.MicrogridSite, frame: pd.DataFrame) -> None:
        valid_times = list(frame.index.to_pydatetime())
        await self._session.execute(
            delete(m.MicrogridWeatherFact).where(
                m.MicrogridWeatherFact.team_id == site.team_id,
                m.MicrogridWeatherFact.site_id == site.id,
                m.MicrogridWeatherFact.valid_at.in_(valid_times),
                m.MicrogridWeatherFact.source_kind == "forecast",
            )
        )
        issued_at = datetime.now(UTC)
        self._session.add_all(
            [
                m.MicrogridWeatherFact(
                    team_id=site.team_id,
                    site_id=site.id,
                    issued_at=issued_at,
                    valid_at=valid_at,
                    temperature_c=Decimal(str(row.temp_air)),
                    relative_humidity_pct=Decimal(str(row.relative_humidity)),
                    cloud_cover_pct=Decimal(str(row.cloud_cover)),
                    wind_speed_mps=Decimal(str(row.wind_speed)),
                    ghi_wm2=Decimal(str(row.ghi)),
                    dni_wm2=Decimal(str(row.dni)),
                    dhi_wm2=Decimal(str(row.dhi)),
                    source_kind="forecast",
                    provider="open-meteo",
                    provider_model="best-match",
                )
                for valid_at, row in frame.iterrows()
            ]
        )


def _forecast_quality(
    *,
    load_points: list[Any],
    pv_points: list[Any],
    soc_points: list[Any],
    weather_frame: pd.DataFrame,
    metrics: dict[str, Any],
    history_meta: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Evaluate deterministic quality gates before an optimization can consume a forecast."""
    checks: list[dict[str, Any]] = []

    def add(code: str, status: str, message: str) -> None:
        checks.append({"code": code, "status": status, "message": message})

    all_points = [*load_points, *pv_points, *soc_points]
    add(
        "horizon",
        "pass" if len(load_points) == len(pv_points) == len(soc_points) == 96 else "failed",
        "未来24小时共96点",
    )
    ordered = all(point.p10 <= point.p50 <= point.p90 for point in all_points)
    add("quantile_order", "pass" if ordered else "failed", "P10、P50、P90分位数顺序")
    finite = all(isfinite(value) for point in all_points for value in (point.p10, point.p50, point.p90))
    add("finite_values", "pass" if finite else "failed", "预测值均为有限数值")
    night_pv = [
        point
        for point, ghi in zip(pv_points, weather_frame["ghi"].tolist(), strict=True)
        if float(ghi) <= 1 and abs(point.p90) > 1e-6
    ]
    add("pv_night", "failed" if night_pv else "pass", "夜间光伏出力为零")
    weather_complete = len(weather_frame) >= 96 and not weather_frame.isna().any(axis=None)
    add("weather", "pass" if weather_complete else "failed", "天气预报覆盖完整")
    if not history_meta.get("ready"):
        add("history_source", "warning", "真实历史未就绪，整段使用演示回退")
    else:
        add("history_source", "pass", "使用绑定电表的实测投影")
    model = str(metrics.get("model", ""))
    add("model", "warning" if "baseline" in model else "pass", f"负荷模型：{model}")
    coverage = float(metrics.get("coverage", 0))
    add("interval_coverage", "pass" if coverage >= 0.65 else "warning", f"区间覆盖率 {coverage:.1%}")
    mape = float(metrics.get("mape_pct", 100))
    add("mape", "pass" if mape <= 15 else "warning", f"MAPE {mape:.2f}%")
    if any(item["status"] == "failed" for item in checks):
        return "failed", checks
    if any(item["status"] == "warning" for item in checks):
        return "warning", checks
    return "pass", checks


class RunOptimization:
    """Execute the Pyomo/HiGHS optimizer and persist its auditable schedule."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        *,
        forecast_run_id: int,
        scenario_id: int | None = None,
        purpose: str = "operational",
        acknowledge_quality_warning: bool = False,
    ) -> m.OptimizationRun:
        forecast_run = await self._session.get(m.ForecastRun, forecast_run_id)
        if forecast_run is None or forecast_run.status != "completed":
            raise ScenarioNotReadyError("a completed forecast run is required")
        if purpose not in {"trial", "operational"}:
            raise ScenarioNotReadyError("optimization purpose must be trial or operational")
        if forecast_run.quality_status == "failed":
            raise ScenarioNotReadyError("failed forecast quality blocks optimization")
        if forecast_run.quality_status == "warning" and not (purpose == "trial" and acknowledge_quality_warning):
            raise ScenarioNotReadyError("forecast warning requires an acknowledged risk trial")
        scenario = await self._session.get(m.MicrogridScenario, scenario_id or forecast_run.scenario_id)
        if scenario is None or scenario.site_id != forecast_run.site_id:
            raise ScenarioNotReadyError("optimization scenario must belong to the forecast site")
        if purpose == "operational" and scenario.status != "published":
            raise ScenarioNotReadyError("operational optimization requires a published scenario")
        if purpose == "operational" and (scenario.tariff_plan_id is None or scenario.grid_emission_factor_id is None):
            raise ScenarioNotReadyError("operational optimization requires tariff and emission-factor ledgers")
        parameter_snapshot = json.dumps(scenario.parameters, ensure_ascii=False, sort_keys=True)
        idempotency_key = _fingerprint(
            forecast_run.team_id,
            forecast_run.id,
            scenario.id,
            purpose,
            parameter_snapshot,
            "optimization-v2",
        )
        existing = await self._session.scalar(
            select(m.OptimizationRun).where(m.OptimizationRun.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
        run = m.OptimizationRun(
            team_id=forecast_run.team_id,
            site_id=forecast_run.site_id,
            scenario_id=scenario.id,
            forecast_run_id=forecast_run.id,
            idempotency_key=idempotency_key,
            status="running",
            purpose=purpose,
            input_snapshot={
                "scenarioId": scenario.id,
                "scenarioVersion": scenario.version,
                "forecastRunId": forecast_run.id,
                "forecastModel": forecast_run.model_version,
                "forecastQuality": {
                    "status": forecast_run.quality_status,
                    "checks": forecast_run.quality_checks,
                    "historySourceKind": forecast_run.history_source_kind,
                    "historyCoveragePct": float(forecast_run.history_coverage_pct or 0),
                },
                "purpose": purpose,
            },
        )
        self._session.add(run)
        await self._session.flush()
        points = (
            (
                await self._session.execute(
                    select(m.ForecastPoint)
                    .where(m.ForecastPoint.run_id == forecast_run.id, m.ForecastPoint.series_code.in_(["load", "pv"]))
                    .order_by(m.ForecastPoint.valid_at)
                )
            )
            .scalars()
            .all()
        )
        load_points = [point for point in points if point.series_code == "load"]
        pv_points = [point for point in points if point.series_code == "pv"]
        if len(load_points) != 96 or len(pv_points) != 96:
            raise ScenarioNotReadyError("forecast must contain 96 load and 96 PV points")
        index = [point.valid_at for point in load_points]
        parameters, contract_ids = await self._parameters_with_contracts(scenario=scenario, index=index)
        tariff, economics_snapshot = await self._economic_inputs(
            scenario=scenario,
            index=index,
            allow_fallback=purpose == "trial",
        )
        if economics_snapshot["emissionFactor"] is not None:
            parameters.setdefault("economics", {})["grid_carbon_kg_per_kwh"] = economics_snapshot["emissionFactor"][
                "value"
            ]
        run.input_snapshot = {
            **run.input_snapshot,
            "flexibilityContractIds": contract_ids,
            "strategy": deepcopy(parameters),
            "economics": economics_snapshot,
        }
        result = optimize_dispatch(
            index=index,
            fixed_load_kw=[float(point.p50) for point in load_points],
            pv_available_kw=[float(point.p50) for point in pv_points],
            tariff_cny_per_kwh=tariff,
            parameters=parameters,
        )
        self._apply_result(run=run, result=result)
        self._session.add_all(
            [
                m.OptimizationSchedulePoint(
                    team_id=run.team_id,
                    run_id=run.id,
                    valid_at=point.valid_at,
                    load_kw=Decimal(str(point.load_kw)),
                    pv_kw=Decimal(str(point.pv_kw)),
                    grid_import_kw=Decimal(str(point.grid_import_kw)),
                    grid_export_kw=Decimal(str(point.grid_export_kw)),
                    battery_charge_kw=Decimal(str(point.battery_charge_kw)),
                    battery_discharge_kw=Decimal(str(point.battery_discharge_kw)),
                    charger_kw=Decimal(str(point.charger_kw)),
                    lighting_kw=Decimal(str(point.lighting_kw)),
                    generator_kw=Decimal(str(point.generator_kw)),
                    curtailed_pv_kw=Decimal(str(point.curtailed_pv_kw)),
                    soc_pct=Decimal(str(point.soc_pct)),
                    tariff_cny_per_kwh=Decimal(str(point.tariff_cny_per_kwh)),
                    interval_cost_cny=Decimal(str(point.interval_cost_cny)),
                )
                for point in result.schedule
            ]
        )
        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def _economic_inputs(
        self,
        *,
        scenario: m.MicrogridScenario,
        index: list[datetime],
        allow_fallback: bool,
    ) -> tuple[list[float], dict[str, Any]]:
        segments = []
        tariff_plan = None
        if scenario.tariff_plan_id is not None:
            tariff_plan = await self._session.get(m.EnergyTariffPlan, scenario.tariff_plan_id)
            segments = list(
                (
                    await self._session.scalars(
                        select(m.EnergyTariffSegment)
                        .where(m.EnergyTariffSegment.plan_id == scenario.tariff_plan_id)
                        .order_by(m.EnergyTariffSegment.sort_index)
                    )
                ).all()
            )
        factor = (
            await self._session.get(m.EmissionFactor, scenario.grid_emission_factor_id)
            if scenario.grid_emission_factor_id is not None
            else None
        )
        if tariff_plan is not None and segments:
            tariff = [_ledger_tariff_for(valid_at, segments) for valid_at in index]
            tariff_snapshot: dict[str, Any] | None = {
                "id": tariff_plan.id,
                "code": tariff_plan.code,
                "name": tariff_plan.name,
                "effectiveFrom": tariff_plan.effective_from.isoformat() if tariff_plan.effective_from else None,
                "effectiveTo": tariff_plan.effective_to.isoformat() if tariff_plan.effective_to else None,
                "sourceKind": "platform_ledger",
                "segments": [
                    {
                        "type": row.segment_type,
                        "start": row.start_time.isoformat(),
                        "end": row.end_time.isoformat(),
                        "price": float(row.price),
                    }
                    for row in segments
                ],
            }
        elif allow_fallback:
            tariff = [_tariff_for(valid_at, scenario.parameters["tariff"]) for valid_at in index]
            tariff_snapshot = {
                "sourceKind": "enterprise_assumption",
                "values": deepcopy(scenario.parameters["tariff"]),
            }
        else:
            raise ScenarioNotReadyError("valid tariff ledger is required")
        if factor is None and not allow_fallback:
            raise ScenarioNotReadyError("valid grid emission factor is required")
        factor_snapshot = (
            {
                "id": factor.id,
                "code": factor.sub_category,
                "value": float(factor.factor_value),
                "unit": factor.factor_unit,
                "year": factor.year,
                "source": factor.source,
                "sourceKind": "platform_ledger",
            }
            if factor is not None
            else {
                "value": float(scenario.parameters.get("economics", {}).get("grid_carbon_kg_per_kwh", 0.5827)),
                "sourceKind": "enterprise_assumption",
            }
        )
        return tariff, {"tariffPlan": tariff_snapshot, "emissionFactor": factor_snapshot}

    async def _parameters_with_contracts(
        self, *, scenario: m.MicrogridScenario, index: list[datetime]
    ) -> tuple[dict[str, Any], list[int]]:
        parameters = deepcopy(scenario.parameters)
        rows = (
            await self._session.execute(
                select(m.FlexibilityContract, m.MicrogridAsset.asset_type)
                .join(m.MicrogridAsset, m.MicrogridAsset.id == m.FlexibilityContract.asset_id)
                .where(
                    m.FlexibilityContract.scenario_id == scenario.id,
                    m.FlexibilityContract.enabled.is_(True),
                )
            )
        ).all()
        contract_ids: list[int] = []
        for contract, asset_type in rows:
            contract_ids.append(contract.id)
            enabled = [
                position
                for position, valid_at in enumerate(index)
                if _minute_in_contract_window(
                    _minute_of_day(valid_at),
                    contract.start_minute,
                    contract.end_minute,
                )
            ]
            if asset_type == "charger":
                parameters.setdefault("charger", {}).update(
                    {
                        "enabled_intervals": enabled,
                        "minimum_power_kw": float(contract.minimum_power_kw),
                        "maximum_power_kw": float(contract.maximum_power_kw),
                        "target_energy_kwh": float(contract.target_energy_kwh or 0),
                        "penalty_cny_per_kwh": float(contract.penalty_cny_per_kwh),
                        "hard_constraint": bool(contract.recovery_constraints.get("hard_constraint", True)),
                    }
                )
            elif asset_type == "lighting":
                baseline = float(parameters.setdefault("lighting", {}).get("baseline_power_kw", 0))
                minimums = [baseline] * len(index)
                maximums = [baseline] * len(index)
                for position in enabled:
                    minimums[position] = float(contract.minimum_power_kw)
                    maximums[position] = float(contract.maximum_power_kw)
                parameters["lighting"].update(
                    {
                        "minimum_by_interval_kw": minimums,
                        "maximum_by_interval_kw": maximums,
                        "penalty_cny_per_kwh": float(contract.penalty_cny_per_kwh),
                    }
                )
        return parameters, contract_ids

    @staticmethod
    def _apply_result(*, run: m.OptimizationRun, result: OptimizationResult) -> None:
        run.status = result.status
        run.solver_seconds = Decimal(str(result.solver_seconds))
        run.mip_gap = Decimal(str(result.mip_gap)) if result.mip_gap is not None else None
        run.objective_cny = Decimal(str(result.objective_cny)) if result.objective_cny is not None else None
        run.baseline_cost_cny = Decimal(str(result.baseline_cost_cny))
        run.savings_cny = Decimal(str(result.savings_cny)) if result.savings_cny is not None else None
        run.peak_reduction_kw = Decimal(str(result.peak_reduction_kw)) if result.peak_reduction_kw is not None else None
        run.baseline_peak_kw = Decimal(str(result.baseline_peak_kw)) if result.baseline_peak_kw is not None else None
        run.optimized_peak_kw = Decimal(str(result.optimized_peak_kw)) if result.optimized_peak_kw is not None else None
        run.peak_change_kw = Decimal(str(result.peak_change_kw)) if result.peak_change_kw is not None else None
        run.carbon_reduction_kg = (
            Decimal(str(result.carbon_reduction_kg)) if result.carbon_reduction_kg is not None else None
        )
        run.cost_breakdown = result.cost_breakdown
        run.diagnostics = result.diagnostics
        run.completed_at = datetime.now(UTC)


class CreateDispatchBatch:
    """Submit a feasible schedule to the v1 simulation adapter."""

    def __init__(self, session: AsyncSession, adapter: SimulationDispatchAdapter | None = None) -> None:
        self._session = session
        self._adapter = adapter or SimulationDispatchAdapter()

    async def execute(self, *, optimization_run_id: int) -> m.DispatchBatch:
        run = await self._session.get(m.OptimizationRun, optimization_run_id)
        if run is None or run.status not in {"optimal", "feasible"}:
            raise InfeasibleDispatchError("only a feasible optimization run can be dispatched")
        if run.purpose != "operational":
            raise InfeasibleDispatchError("trial optimization runs cannot be dispatched")
        forecast = await self._session.get(m.ForecastRun, run.forecast_run_id)
        if forecast is None or forecast.quality_status != "pass":
            raise InfeasibleDispatchError("dispatch requires a forecast that passed the quality gate")
        idempotency_key = _fingerprint(run.team_id, run.id, "simulation-dispatch-v1")
        existing = await self._session.scalar(
            select(m.DispatchBatch).where(m.DispatchBatch.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
        scenario = await self._session.get(m.MicrogridScenario, run.scenario_id)
        if scenario is None or scenario.status != "published":
            raise InfeasibleDispatchError("a published optimization scenario is required")
        assets = (
            (
                await self._session.execute(
                    select(m.MicrogridAsset).where(
                        m.MicrogridAsset.site_id == run.site_id,
                        m.MicrogridAsset.asset_type.in_(["storage", "charger", "lighting"]),
                    )
                )
            )
            .scalars()
            .all()
        )
        assets_by_type = {asset.asset_type: asset for asset in assets}
        if set(assets_by_type) != {"storage", "charger", "lighting"}:
            raise InfeasibleDispatchError("dispatchable storage, charger, and lighting assets are required")
        contracts = (
            (
                await self._session.execute(
                    select(m.FlexibilityContract).where(
                        m.FlexibilityContract.scenario_id == scenario.id,
                        m.FlexibilityContract.enabled.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        contracts_by_asset = {contract.asset_id: contract for contract in contracts}
        storage_asset = assets_by_type["storage"]
        charger_asset = assets_by_type["charger"]
        lighting_asset = assets_by_type["lighting"]
        charger_contract = contracts_by_asset.get(charger_asset.id)
        lighting_contract = contracts_by_asset.get(lighting_asset.id)
        if charger_contract is None or lighting_contract is None:
            raise InfeasibleDispatchError("published flexibility contracts are required for dispatch")
        storage_power_kw = float(scenario.parameters["storage"]["power_kw"])
        points = (
            (
                await self._session.execute(
                    select(m.OptimizationSchedulePoint)
                    .where(m.OptimizationSchedulePoint.run_id == run.id)
                    .order_by(m.OptimizationSchedulePoint.valid_at)
                )
            )
            .scalars()
            .all()
        )
        batch = m.DispatchBatch(
            team_id=run.team_id,
            optimization_run_id=run.id,
            idempotency_key=idempotency_key,
            status="running",
            expires_at=datetime.now(UTC) + timedelta(hours=25),
            command_count=len(points) * 3,
        )
        self._session.add(batch)
        await self._session.flush()
        commands: list[DispatchCommand] = []
        for point in points:
            commands.extend(
                [
                    DispatchCommand(
                        command_key=f"{run.id}:bess:{point.id}",
                        asset_code=storage_asset.code,
                        scheduled_at=point.valid_at,
                        target_power_kw=float(point.battery_discharge_kw - point.battery_charge_kw),
                        minimum_power_kw=-storage_power_kw,
                        maximum_power_kw=storage_power_kw,
                    ),
                    DispatchCommand(
                        command_key=f"{run.id}:charger:{point.id}",
                        asset_code=charger_asset.code,
                        scheduled_at=point.valid_at,
                        target_power_kw=float(point.charger_kw),
                        minimum_power_kw=float(charger_contract.minimum_power_kw),
                        maximum_power_kw=float(charger_contract.maximum_power_kw),
                    ),
                    DispatchCommand(
                        command_key=f"{run.id}:lighting:{point.id}",
                        asset_code=lighting_asset.code,
                        scheduled_at=point.valid_at,
                        target_power_kw=float(point.lighting_kw),
                        minimum_power_kw=float(lighting_contract.minimum_power_kw),
                        maximum_power_kw=float(lighting_contract.maximum_power_kw),
                    ),
                ]
            )
        outcomes = {item.command_key: item for item in await self._adapter.dispatch(commands)}
        receipts: list[m.DispatchReceipt] = []
        for command in commands:
            outcome = outcomes[command.command_key]
            receipts.append(
                m.DispatchReceipt(
                    team_id=run.team_id,
                    batch_id=batch.id,
                    command_key=command.command_key,
                    asset_code=command.asset_code,
                    scheduled_at=command.scheduled_at,
                    target_power_kw=Decimal(str(command.target_power_kw)),
                    executed_power_kw=(
                        Decimal(str(outcome.executed_power_kw)) if outcome.executed_power_kw is not None else None
                    ),
                    status=outcome.status,
                    reason=outcome.reason,
                )
            )
        self._session.add_all(receipts)
        batch.status = "completed"
        batch.accepted_count = sum(item.status in {"executed", "clipped"} for item in outcomes.values())
        batch.rejected_count = sum(item.status == "rejected" for item in outcomes.values())
        batch.completed_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(batch)
        return batch


def _minute_of_day(valid_at: datetime) -> int:
    local = valid_at.astimezone(ZoneInfo("Asia/Shanghai")) if valid_at.tzinfo else valid_at
    return local.hour * 60 + local.minute


def _minute_in_contract_window(minute: int, start_minute: int, end_minute: int) -> bool:
    if start_minute <= end_minute:
        return start_minute <= minute < end_minute
    return minute >= start_minute or minute < end_minute


def _tariff_for(valid_at: datetime, tariff: dict[str, Any]) -> float:
    hour = valid_at.astimezone(ZoneInfo("Asia/Shanghai")).hour if valid_at.tzinfo else valid_at.hour
    if hour < 7 or hour >= 23:
        return float(tariff["valley"])
    if 9 <= hour < 12 or 17 <= hour < 22:
        return float(tariff["peak"])
    return float(tariff["flat"])


def _ledger_tariff_for(valid_at: datetime, segments: list[m.EnergyTariffSegment]) -> float:
    local_time = valid_at.astimezone(ZoneInfo("Asia/Shanghai")).time().replace(tzinfo=None)
    for segment in segments:
        if segment.start_time <= segment.end_time:
            matches = segment.start_time <= local_time < segment.end_time
        else:
            matches = local_time >= segment.start_time or local_time < segment.end_time
        if matches:
            return float(segment.price)
    msg = f"tariff plan has no segment for {local_time.isoformat()}"
    raise ScenarioNotReadyError(msg)
