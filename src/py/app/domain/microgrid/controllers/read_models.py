"""Read-only microgrid API for workbench pages."""

from __future__ import annotations

# ruff: noqa: TC001 - Litestar resolves request DTO annotations at runtime.
from datetime import datetime
from typing import TYPE_CHECKING, Any

from litestar import Controller, get, post
from litestar.exceptions import ClientException, NotFoundException
from litestar.response import Response

from app.domain.accounts.guards import requires_permission
from app.domain.microgrid.domain.exceptions import MicrogridDomainError
from app.domain.microgrid.queries import MicrogridQueryService
from app.domain.microgrid.schemas import (
    CreateFlexibilityContractRequest,
    CreateScenarioRequest,
    RunForecastRequest,
    RunOptimizationRequest,
)
from app.domain.microgrid.usecases import RunForecast, RunOptimization
from app.domain.microgrid.usecases.configuration import CreateScenario, UpsertFlexibilityContract

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MicrogridReadController(Controller):
    """Serve page-oriented microgrid projections."""

    path = "/api/microgrid"
    tags = ["Microgrid"]
    guards = [requires_permission("microgrid.view")]

    @get("/overview", operation_id="MicrogridGetOverview")
    async def overview(self, db_session: AsyncSession, site_id: int | None = None) -> dict[str, Any]:
        return await MicrogridQueryService(db_session).overview(site_id=site_id)

    @get("/topology", operation_id="MicrogridGetTopology")
    async def topology(self, db_session: AsyncSession, site_id: int | None = None) -> dict[str, Any]:
        return await MicrogridQueryService(db_session).topology(site_id=site_id)

    @get("/assets", operation_id="MicrogridListAssets")
    async def assets(self, db_session: AsyncSession, site_id: int | None = None) -> dict[str, Any]:
        return {"items": await MicrogridQueryService(db_session).assets(site_id=site_id)}

    @get("/assets/{asset_id:int}/series", operation_id="MicrogridGetAssetSeries")
    async def asset_series(
        self,
        db_session: AsyncSession,
        asset_id: int,
        metric_code: str = "active_power_kw",
        limit: int = 192,
    ) -> dict[str, Any]:
        return {
            "items": await MicrogridQueryService(db_session).asset_series(
                asset_id=asset_id, metric_code=metric_code, limit=limit
            )
        }

    @get("/events", operation_id="MicrogridListEvents")
    async def events(self, db_session: AsyncSession, site_id: int | None = None) -> dict[str, Any]:
        return {"items": await MicrogridQueryService(db_session).events(site_id=site_id)}

    @get("/sites/{site_id:int}/data-readiness", operation_id="MicrogridGetDataReadiness")
    async def data_readiness(self, db_session: AsyncSession, site_id: int) -> dict[str, Any]:
        return await MicrogridQueryService(db_session).data_readiness(site_id=site_id)

    @get("/economic-input-options", operation_id="MicrogridGetEconomicInputOptions")
    async def economic_input_options(self, db_session: AsyncSession) -> dict[str, Any]:
        return await MicrogridQueryService(db_session).economic_input_options()

    @get("/scenarios", operation_id="MicrogridListScenarios")
    async def scenarios(self, db_session: AsyncSession, site_id: int | None = None) -> dict[str, Any]:
        return {"items": await MicrogridQueryService(db_session).scenarios(site_id=site_id)}

    @post("/scenarios", operation_id="MicrogridCreateScenario", guards=[requires_permission("microgrid.configure")])
    async def create_scenario(self, db_session: AsyncSession, data: CreateScenarioRequest) -> dict[str, Any]:
        try:
            scenario = await CreateScenario(db_session).execute(
                site_id=data.site_id,
                code=data.code,
                name=data.name,
                parameters=data.parameters,
                source_name=data.source_name,
                confidence_level=data.confidence_level,
            )
        except MicrogridDomainError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        rows = await MicrogridQueryService(db_session).scenarios(site_id=scenario.site_id)
        return next(row for row in rows if row["id"] == scenario.id)

    @get("/flexibility-contracts", operation_id="MicrogridListFlexibilityContracts")
    async def flexibility_contracts(self, db_session: AsyncSession, scenario_id: int | None = None) -> dict[str, Any]:
        return {"items": await MicrogridQueryService(db_session).flexibility_contracts(scenario_id=scenario_id)}

    @post(
        "/flexibility-contracts",
        operation_id="MicrogridCreateFlexibilityContract",
        guards=[requires_permission("microgrid.configure")],
    )
    async def create_contract(self, db_session: AsyncSession, data: CreateFlexibilityContractRequest) -> dict[str, Any]:
        try:
            contract = await UpsertFlexibilityContract(db_session).execute(
                scenario_id=data.scenario_id,
                asset_id=data.asset_id,
                contract_type=data.contract_type,
                start_minute=data.start_minute,
                end_minute=data.end_minute,
                minimum_power_kw=data.minimum_power_kw,
                maximum_power_kw=data.maximum_power_kw,
                target_energy_kwh=data.target_energy_kwh,
                priority=data.priority,
                penalty_cny_per_kwh=data.penalty_cny_per_kwh,
                hard_constraint=data.hard_constraint,
                enabled=data.enabled,
            )
        except (MicrogridDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        rows = await MicrogridQueryService(db_session).flexibility_contracts(scenario_id=contract.scenario_id)
        return next(row for row in rows if row["id"] == contract.id)

    @get("/forecast-runs", operation_id="MicrogridListForecastRuns")
    async def forecast_runs(self, db_session: AsyncSession, site_id: int | None = None) -> dict[str, Any]:
        return {"items": await MicrogridQueryService(db_session).forecast_runs(site_id=site_id)}

    @post(
        "/forecast-runs",
        operation_id="MicrogridRunForecast",
        status_code=202,
        guards=[requires_permission("microgrid.forecast.run")],
    )
    async def run_forecast(self, db_session: AsyncSession, data: RunForecastRequest) -> Response[dict[str, Any]]:
        try:
            start = datetime.fromisoformat(data.start) if data.start else None
            run = await RunForecast(db_session).execute(site_id=data.site_id, scenario_id=data.scenario_id, start=start)
            result = await MicrogridQueryService(db_session).forecast_run(run.id)
            return Response(content=result or {"id": run.id, "status": run.status}, status_code=202)
        except (MicrogridDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @get("/forecast-runs/{run_id:int}", operation_id="MicrogridGetForecastRun")
    async def forecast_run(self, db_session: AsyncSession, run_id: int) -> dict[str, Any]:
        result = await MicrogridQueryService(db_session).forecast_run(run_id)
        if result is None:
            raise NotFoundException(detail="Forecast run not found")
        return result

    @get("/optimization-runs", operation_id="MicrogridListOptimizationRuns")
    async def optimization_runs(self, db_session: AsyncSession, site_id: int | None = None) -> dict[str, Any]:
        return {"items": await MicrogridQueryService(db_session).optimization_runs(site_id=site_id)}

    @post(
        "/optimization-runs",
        operation_id="MicrogridRunOptimization",
        status_code=202,
        guards=[requires_permission("microgrid.optimize.run")],
    )
    async def run_optimization(
        self, db_session: AsyncSession, data: RunOptimizationRequest
    ) -> Response[dict[str, Any]]:
        try:
            run = await RunOptimization(db_session).execute(
                forecast_run_id=data.forecast_run_id,
                scenario_id=data.scenario_id,
                purpose=data.purpose,
                acknowledge_quality_warning=data.acknowledge_quality_warning,
            )
            result = await MicrogridQueryService(db_session).optimization_run(run.id)
            return Response(content=result or {"id": run.id, "status": run.status}, status_code=202)
        except (MicrogridDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @get("/optimization-runs/{run_id:int}", operation_id="MicrogridGetOptimizationRun")
    async def optimization_run(self, db_session: AsyncSession, run_id: int) -> dict[str, Any]:
        result = await MicrogridQueryService(db_session).optimization_run(run_id)
        if result is None:
            raise NotFoundException(detail="Optimization run not found")
        return result

    @get("/optimization-comparison", operation_id="MicrogridGetOptimizationComparison")
    async def optimization_comparison(self, db_session: AsyncSession, run_ids: str) -> dict[str, Any]:
        try:
            ids = [int(value) for value in run_ids.split(",") if value]
            return await MicrogridQueryService(db_session).optimization_comparison(run_ids=ids)
        except (MicrogridDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @get("/dispatch-batches/{batch_id:int}", operation_id="MicrogridGetDispatchBatch")
    async def dispatch_batch(self, db_session: AsyncSession, batch_id: int) -> dict[str, Any]:
        result = await MicrogridQueryService(db_session).dispatch_batch(batch_id)
        if result is None:
            raise NotFoundException(detail="Dispatch batch not found")
        return result
