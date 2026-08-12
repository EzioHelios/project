"""Read models for the four microgrid workbench pages."""

from __future__ import annotations

# ruff: noqa: PERF401, RUF001, TC003
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import desc, select

from app.db import models as m

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _number(value: Decimal | float | None) -> float | None:
    return None if value is None else float(value)


def _time(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


class MicrogridQueryService:
    """Optimized query boundary used by dashboard and analysis routes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def overview(self, *, site_id: int | None = None) -> dict[str, Any]:
        site = await self._site(site_id)
        if site is None:
            return {"configured": False, "mode": "shadow", "sites": []}
        assets = await self.assets(site_id=site.id)
        states = {item["assetType"]: item for item in assets}
        optimization = await self._session.scalar(
            select(m.OptimizationRun)
            .where(m.OptimizationRun.site_id == site.id)
            .order_by(desc(m.OptimizationRun.created_at))
        )
        forecast = await self._session.scalar(
            select(m.ForecastRun).where(m.ForecastRun.site_id == site.id).order_by(desc(m.ForecastRun.created_at))
        )
        trend = await self._combined_trend(
            forecast_run_id=forecast.id if forecast else None,
            optimization_run_id=optimization.id if optimization else None,
        )
        pcc = states.get("grid", {})
        pv = states.get("pv", {})
        storage = states.get("storage", {})
        return {
            "configured": True,
            "mode": "shadow",
            "site": self._site_dict(site),
            "scenario": await self._published_scenario(site.id),
            "metrics": {
                "pccPowerKw": pcc.get("activePowerKw", 0),
                "pvPowerKw": pv.get("activePowerKw", 0),
                "socPct": storage.get("socPct", 0),
                "onlineAssets": sum(bool(item["online"]) for item in assets),
                "totalAssets": len(assets),
                "savingsCny": _number(optimization.savings_cny) if optimization else 0,
                "peakReductionKw": _number(optimization.peak_reduction_kw) if optimization else 0,
                "carbonReductionKg": _number(optimization.carbon_reduction_kg) if optimization else 0,
                "alarmCount": sum(item["alarmLevel"] != "normal" for item in assets),
            },
            "trend": trend,
            "assets": assets,
            "forecastRun": self._forecast_summary(forecast) if forecast else None,
            "optimizationRun": self._optimization_summary(optimization) if optimization else None,
        }

    async def topology(self, *, site_id: int | None = None) -> dict[str, Any]:
        site = await self._site(site_id)
        if site is None:
            return {"configured": False, "nodes": [], "edges": []}
        topology = dict(site.topology or {})
        topology.update(
            {
                "configured": True,
                "site": self._site_dict(site),
                "mode": "shadow",
                "assets": await self.assets(site_id=site.id),
            }
        )
        return topology

    async def assets(self, *, site_id: int | None = None) -> list[dict[str, Any]]:
        conditions = []
        if site_id is not None:
            conditions.append(m.MicrogridAsset.site_id == site_id)
        rows = (
            await self._session.execute(
                select(m.MicrogridAsset, m.MicrogridAssetState)
                .outerjoin(m.MicrogridAssetState, m.MicrogridAssetState.asset_id == m.MicrogridAsset.id)
                .where(*conditions)
                .order_by(m.MicrogridAsset.asset_type, m.MicrogridAsset.code)
            )
        ).all()
        return [
            {
                "id": asset.id,
                "siteId": asset.site_id,
                "code": asset.code,
                "name": asset.name,
                "assetType": asset.asset_type,
                "ratedPowerKw": _number(asset.rated_power_kw),
                "ratedEnergyKwh": _number(asset.rated_energy_kwh),
                "controllable": asset.controllable,
                "parameters": asset.parameters,
                "sourceKind": asset.source_kind,
                "sourceName": asset.source_name,
                "confidenceLevel": _number(asset.confidence_level),
                "online": state.online if state else False,
                "operatingMode": state.operating_mode if state else "unknown",
                "activePowerKw": _number(state.active_power_kw) if state else None,
                "socPct": _number(state.soc_pct) if state else None,
                "temperatureC": _number(state.temperature_c) if state else None,
                "alarmLevel": state.alarm_level if state else "unknown",
                "observedAt": _time(state.observed_at) if state else None,
            }
            for asset, state in rows
        ]

    async def asset_series(
        self, *, asset_id: int, metric_code: str = "active_power_kw", limit: int = 192
    ) -> list[dict[str, Any]]:
        rows = (
            (
                await self._session.execute(
                    select(m.MicrogridTelemetryFact)
                    .where(
                        m.MicrogridTelemetryFact.asset_id == asset_id,
                        m.MicrogridTelemetryFact.metric_code == metric_code,
                    )
                    .order_by(desc(m.MicrogridTelemetryFact.observed_at))
                    .limit(min(max(limit, 1), 1000))
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "observedAt": _time(row.observed_at),
                "value": _number(row.value),
                "unit": row.unit,
                "sourceKind": row.source_kind,
                "quality": row.quality,
            }
            for row in reversed(rows)
        ]

    async def events(self, *, site_id: int | None = None) -> list[dict[str, Any]]:
        site = await self._site(site_id)
        if site is None:
            return []
        runs = (
            (
                await self._session.execute(
                    select(m.OptimizationRun)
                    .where(m.OptimizationRun.site_id == site.id)
                    .order_by(desc(m.OptimizationRun.created_at))
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )
        events: list[dict[str, Any]] = []
        for run in runs:
            events.append(
                {
                    "id": f"optimization-{run.id}",
                    "eventType": "optimization",
                    "level": "success" if run.status in {"optimal", "feasible"} else "warning",
                    "title": f"优化运行 {run.status}",
                    "occurredAt": _time(run.completed_at or run.created_at),
                    "detail": f"基线 ¥{_number(run.baseline_cost_cny) or 0:.2f}，节省 ¥{_number(run.savings_cny) or 0:.2f}",
                }
            )
        return events

    async def scenarios(self, *, site_id: int | None = None) -> list[dict[str, Any]]:
        conditions = [m.MicrogridScenario.site_id == site_id] if site_id is not None else []
        rows = (
            (
                await self._session.execute(
                    select(m.MicrogridScenario)
                    .where(*conditions)
                    .order_by(m.MicrogridScenario.site_id, desc(m.MicrogridScenario.version))
                )
            )
            .scalars()
            .all()
        )
        return [self._scenario_dict(row) for row in rows]

    async def flexibility_contracts(self, *, scenario_id: int | None = None) -> list[dict[str, Any]]:
        conditions = [m.FlexibilityContract.scenario_id == scenario_id] if scenario_id is not None else []
        rows = (
            await self._session.execute(
                select(m.FlexibilityContract, m.MicrogridAsset)
                .join(m.MicrogridAsset, m.MicrogridAsset.id == m.FlexibilityContract.asset_id)
                .where(*conditions)
                .order_by(desc(m.FlexibilityContract.priority))
            )
        ).all()
        return [
            {
                "id": contract.id,
                "scenarioId": contract.scenario_id,
                "assetId": contract.asset_id,
                "assetCode": asset.code,
                "assetName": asset.name,
                "contractType": contract.contract_type,
                "startMinute": contract.start_minute,
                "endMinute": contract.end_minute,
                "minimumPowerKw": _number(contract.minimum_power_kw),
                "maximumPowerKw": _number(contract.maximum_power_kw),
                "targetEnergyKwh": _number(contract.target_energy_kwh),
                "priority": contract.priority,
                "enabled": contract.enabled,
            }
            for contract, asset in rows
        ]

    async def forecast_runs(self, *, site_id: int | None = None, limit: int = 20) -> list[dict[str, Any]]:
        conditions = [m.ForecastRun.site_id == site_id] if site_id is not None else []
        rows = (
            (
                await self._session.execute(
                    select(m.ForecastRun).where(*conditions).order_by(desc(m.ForecastRun.created_at)).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [self._forecast_summary(row) for row in rows]

    async def forecast_run(self, run_id: int) -> dict[str, Any] | None:
        run = await self._session.get(m.ForecastRun, run_id)
        if run is None:
            return None
        points = (
            (
                await self._session.execute(
                    select(m.ForecastPoint).where(m.ForecastPoint.run_id == run.id).order_by(m.ForecastPoint.valid_at)
                )
            )
            .scalars()
            .all()
        )
        result = self._forecast_summary(run)
        result["points"] = [
            {
                "seriesCode": point.series_code,
                "validAt": _time(point.valid_at),
                "p10": _number(point.p10),
                "p50": _number(point.p50),
                "p90": _number(point.p90),
                "unit": point.unit,
            }
            for point in points
        ]
        return result

    async def optimization_runs(self, *, site_id: int | None = None, limit: int = 20) -> list[dict[str, Any]]:
        conditions = [m.OptimizationRun.site_id == site_id] if site_id is not None else []
        rows = (
            (
                await self._session.execute(
                    select(m.OptimizationRun)
                    .where(*conditions)
                    .order_by(desc(m.OptimizationRun.created_at))
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [self._optimization_summary(row) for row in rows]

    async def optimization_run(self, run_id: int) -> dict[str, Any] | None:
        run = await self._session.get(m.OptimizationRun, run_id)
        if run is None:
            return None
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
        result = self._optimization_summary(run)
        result["schedule"] = [
            {
                "validAt": _time(point.valid_at),
                "loadKw": _number(point.load_kw),
                "pvKw": _number(point.pv_kw),
                "gridImportKw": _number(point.grid_import_kw),
                "gridExportKw": _number(point.grid_export_kw),
                "batteryChargeKw": _number(point.battery_charge_kw),
                "batteryDischargeKw": _number(point.battery_discharge_kw),
                "chargerKw": _number(point.charger_kw),
                "lightingKw": _number(point.lighting_kw),
                "generatorKw": _number(point.generator_kw),
                "curtailedPvKw": _number(point.curtailed_pv_kw),
                "socPct": _number(point.soc_pct),
                "tariffCnyPerKwh": _number(point.tariff_cny_per_kwh),
                "intervalCostCny": _number(point.interval_cost_cny),
            }
            for point in points
        ]
        return result

    async def dispatch_batch(self, batch_id: int) -> dict[str, Any] | None:
        batch = await self._session.get(m.DispatchBatch, batch_id)
        if batch is None:
            return None
        receipts = (
            (
                await self._session.execute(
                    select(m.DispatchReceipt)
                    .where(m.DispatchReceipt.batch_id == batch.id)
                    .order_by(m.DispatchReceipt.scheduled_at, m.DispatchReceipt.asset_code)
                )
            )
            .scalars()
            .all()
        )
        return {
            "id": batch.id,
            "optimizationRunId": batch.optimization_run_id,
            "status": batch.status,
            "adapterCode": batch.adapter_code,
            "expiresAt": _time(batch.expires_at),
            "commandCount": batch.command_count,
            "acceptedCount": batch.accepted_count,
            "rejectedCount": batch.rejected_count,
            "completedAt": _time(batch.completed_at),
            "receipts": [
                {
                    "commandKey": row.command_key,
                    "assetCode": row.asset_code,
                    "scheduledAt": _time(row.scheduled_at),
                    "receivedAt": _time(row.received_at),
                    "targetPowerKw": _number(row.target_power_kw),
                    "executedPowerKw": _number(row.executed_power_kw),
                    "status": row.status,
                    "reason": row.reason,
                }
                for row in receipts
            ],
        }

    async def _site(self, site_id: int | None) -> m.MicrogridSite | None:
        statement = select(m.MicrogridSite)
        if site_id is not None:
            statement = statement.where(m.MicrogridSite.id == site_id)
        return await self._session.scalar(statement.order_by(m.MicrogridSite.id).limit(1))

    async def _published_scenario(self, site_id: int) -> dict[str, Any] | None:
        scenario = await self._session.scalar(
            select(m.MicrogridScenario)
            .where(m.MicrogridScenario.site_id == site_id, m.MicrogridScenario.status == "published")
            .order_by(desc(m.MicrogridScenario.version))
        )
        return self._scenario_dict(scenario) if scenario else None

    async def _combined_trend(
        self, *, forecast_run_id: int | None, optimization_run_id: int | None
    ) -> list[dict[str, Any]]:
        if forecast_run_id is None:
            return []
        forecast_points = (
            (
                await self._session.execute(
                    select(m.ForecastPoint)
                    .where(m.ForecastPoint.run_id == forecast_run_id, m.ForecastPoint.series_code.in_(["load", "pv"]))
                    .order_by(m.ForecastPoint.valid_at)
                )
            )
            .scalars()
            .all()
        )
        by_time: dict[datetime, dict[str, Any]] = {}
        for point in forecast_points:
            item = by_time.setdefault(point.valid_at, {"period": point.valid_at.isoformat()})
            item[f"{point.series_code}Kw"] = _number(point.p50)
        if optimization_run_id is not None:
            schedule = (
                (
                    await self._session.execute(
                        select(m.OptimizationSchedulePoint)
                        .where(m.OptimizationSchedulePoint.run_id == optimization_run_id)
                        .order_by(m.OptimizationSchedulePoint.valid_at)
                    )
                )
                .scalars()
                .all()
            )
            for point in schedule:
                item = by_time.setdefault(point.valid_at, {"period": point.valid_at.isoformat()})
                item["gridImportKw"] = _number(point.grid_import_kw)
                item["socPct"] = _number(point.soc_pct)
        return list(by_time.values())

    @staticmethod
    def _site_dict(site: m.MicrogridSite) -> dict[str, Any]:
        return {
            "id": site.id,
            "code": site.code,
            "name": site.name,
            "timezone": site.timezone,
            "latitude": _number(site.latitude),
            "longitude": _number(site.longitude),
            "pccCapacityKw": _number(site.pcc_capacity_kw),
            "status": site.status,
            "sourceName": site.source_name,
        }

    @staticmethod
    def _scenario_dict(scenario: m.MicrogridScenario) -> dict[str, Any]:
        return {
            "id": scenario.id,
            "siteId": scenario.site_id,
            "code": scenario.code,
            "name": scenario.name,
            "version": scenario.version,
            "status": scenario.status,
            "parameters": scenario.parameters,
            "assetSnapshot": scenario.asset_snapshot,
            "sourceKind": scenario.source_kind,
            "sourceName": scenario.source_name,
            "confidenceLevel": _number(scenario.confidence_level),
            "validFrom": _time(scenario.valid_from),
            "publishedAt": _time(scenario.published_at),
        }

    @staticmethod
    def _forecast_summary(run: m.ForecastRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "siteId": run.site_id,
            "scenarioId": run.scenario_id,
            "status": run.status,
            "horizonStart": _time(run.horizon_start),
            "horizonEnd": _time(run.horizon_end),
            "intervalMinutes": run.interval_minutes,
            "modelVersion": run.model_version,
            "metrics": run.metrics,
            "inputSnapshot": run.input_snapshot,
            "completedAt": _time(run.completed_at),
            "errorMessage": run.error_message,
        }

    @staticmethod
    def _optimization_summary(run: m.OptimizationRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "siteId": run.site_id,
            "scenarioId": run.scenario_id,
            "forecastRunId": run.forecast_run_id,
            "status": run.status,
            "solver": run.solver,
            "solverSeconds": _number(run.solver_seconds),
            "mipGap": _number(run.mip_gap),
            "objectiveCny": _number(run.objective_cny),
            "baselineCostCny": _number(run.baseline_cost_cny),
            "savingsCny": _number(run.savings_cny),
            "peakReductionKw": _number(run.peak_reduction_kw),
            "carbonReductionKg": _number(run.carbon_reduction_kg),
            "costBreakdown": run.cost_breakdown,
            "diagnostics": run.diagnostics,
            "inputSnapshot": run.input_snapshot,
            "completedAt": _time(run.completed_at),
            "errorMessage": run.error_message,
        }
