"""Microgrid scenario and flexibility configuration API."""

from __future__ import annotations

# ruff: noqa: TC001 - Litestar resolves request DTO annotations at runtime.
from typing import TYPE_CHECKING, Any

from litestar import Controller, patch, post
from litestar.exceptions import ClientException

from app.domain.accounts.guards import requires_permission
from app.domain.microgrid.domain.exceptions import MicrogridDomainError
from app.domain.microgrid.queries import MicrogridQueryService
from app.domain.microgrid.schemas import BootstrapDemoRequest, CreateFlexibilityContractRequest
from app.domain.microgrid.usecases.configuration import PublishScenario, UpsertFlexibilityContract
from app.domain.microgrid.usecases.operations import BootstrapXiangtaiDemo, RunForecast, RunOptimization

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MicrogridConfigurationController(Controller):
    """Maintain versioned asset assumptions and flexibility contracts."""

    path = "/api/microgrid"
    tags = ["Microgrid"]
    guards = [requires_permission("microgrid.configure")]

    @post("/demo/bootstrap", operation_id="MicrogridBootstrapXiangtaiDemo")
    async def bootstrap_demo(self, db_session: AsyncSession, data: BootstrapDemoRequest) -> dict[str, Any]:
        if data.site_code != "xiangtai-taizhou":
            raise ClientException(status_code=400, detail="Only the Xiangtai demo preset is available")
        site = await BootstrapXiangtaiDemo(db_session).execute()
        query = MicrogridQueryService(db_session)
        forecast_runs = await query.forecast_runs(site_id=site.id, limit=1)
        if forecast_runs:
            forecast_run_id = int(forecast_runs[0]["id"])
        else:
            forecast_run_id = (await RunForecast(db_session).execute(site_id=site.id)).id
        optimization_runs = await query.optimization_runs(site_id=site.id, limit=1)
        if optimization_runs:
            optimization_run_id = int(optimization_runs[0]["id"])
        else:
            optimization_run_id = (await RunOptimization(db_session).execute(forecast_run_id=forecast_run_id)).id
        return {
            "siteId": site.id,
            "siteCode": site.code,
            "forecastRunId": forecast_run_id,
            "optimizationRunId": optimization_run_id,
            "status": "ready",
        }

    @post("/scenarios/{scenario_id:int}/publish", operation_id="MicrogridPublishScenario")
    async def publish_scenario(self, db_session: AsyncSession, scenario_id: int) -> dict[str, Any]:
        try:
            scenario = await PublishScenario(db_session).execute(scenario_id)
        except MicrogridDomainError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        rows = await MicrogridQueryService(db_session).scenarios(site_id=scenario.site_id)
        return next(row for row in rows if row["id"] == scenario.id)

    @patch("/flexibility-contracts/{contract_id:int}", operation_id="MicrogridUpdateFlexibilityContract")
    async def update_contract(
        self, db_session: AsyncSession, contract_id: int, data: CreateFlexibilityContractRequest
    ) -> dict[str, Any]:
        contract = await self._upsert_contract(db_session, data, contract_id=contract_id)
        rows = await MicrogridQueryService(db_session).flexibility_contracts(scenario_id=contract.scenario_id)
        return next(row for row in rows if row["id"] == contract.id)

    @staticmethod
    async def _upsert_contract(
        db_session: AsyncSession,
        data: CreateFlexibilityContractRequest,
        *,
        contract_id: int | None = None,
    ) -> Any:
        try:
            return await UpsertFlexibilityContract(db_session).execute(
                contract_id=contract_id,
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
                enabled=data.enabled,
            )
        except (MicrogridDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
