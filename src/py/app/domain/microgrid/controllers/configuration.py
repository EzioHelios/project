"""Microgrid scenario and flexibility configuration API."""

from __future__ import annotations

# ruff: noqa: TC001 - Litestar resolves request DTO annotations at runtime.
from typing import TYPE_CHECKING, Any

from litestar import Controller, delete, get, patch, post, put
from litestar.exceptions import ClientException

from app.domain.accounts.guards import requires_permission
from app.domain.microgrid.domain.exceptions import MicrogridDomainError
from app.domain.microgrid.queries import MicrogridQueryService
from app.domain.microgrid.schemas import (
    ApplyBindingTemplateRequest,
    BootstrapDemoRequest,
    CreateFlexibilityContractRequest,
    ReplaceMeterBindingsRequest,
    UpdateScenarioRequest,
)
from app.domain.microgrid.usecases.bindings import (
    ApplyXiangtaiBindingTemplate,
    BindingTemplate,
    ReplaceMeterBindings,
)
from app.domain.microgrid.usecases.configuration import (
    CreateWorkingCopy,
    DiscardScenarioDraft,
    PublishScenario,
    RestoreScenario,
    UpdateWorkingScenario,
    UpsertFlexibilityContract,
)
from app.domain.microgrid.usecases.operations import BootstrapXiangtaiDemo, RunForecast, RunOptimization

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MicrogridConfigurationController(Controller):
    """Maintain versioned asset assumptions and flexibility contracts."""

    path = "/api/microgrid"
    tags = ["Microgrid"]

    @get(
        "/sites/{site_id:int}/bindings",
        operation_id="MicrogridListMeterBindings",
        guards=[requires_permission("microgrid.view")],
    )
    async def bindings(self, db_session: AsyncSession, site_id: int) -> dict[str, Any]:
        return {"items": await MicrogridQueryService(db_session).bindings(site_id=site_id)}

    @get(
        "/sites/{site_id:int}/binding-template",
        operation_id="MicrogridGetBindingTemplate",
        guards=[requires_permission("microgrid.view")],
    )
    async def binding_template(self, db_session: AsyncSession, site_id: int) -> dict[str, Any]:
        try:
            return await BindingTemplate(db_session).execute(site_id)
        except MicrogridDomainError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @put(
        "/sites/{site_id:int}/bindings",
        operation_id="MicrogridReplaceMeterBindings",
        guards=[requires_permission("microgrid.configure")],
    )
    async def replace_bindings(
        self, db_session: AsyncSession, site_id: int, data: ReplaceMeterBindingsRequest
    ) -> dict[str, Any]:
        try:
            await ReplaceMeterBindings(db_session).execute(
                site_id=site_id,
                monitor_sector_id=data.monitor_sector_id,
                bindings=[
                    {
                        "asset_id": row.asset_id,
                        "equipment_id": row.equipment_id,
                        "role": row.role,
                        "point_code": row.point_code,
                        "direction": row.direction,
                        "sign": row.sign,
                        "enabled": row.enabled,
                    }
                    for row in data.bindings
                ],
            )
        except (MicrogridDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        query = MicrogridQueryService(db_session)
        return {
            "items": await query.bindings(site_id=site_id),
            "readiness": await query.data_readiness(site_id=site_id),
        }

    @post(
        "/sites/{site_id:int}/bindings/apply-template",
        operation_id="MicrogridApplyBindingTemplate",
        guards=[requires_permission("microgrid.configure")],
    )
    async def apply_binding_template(
        self, db_session: AsyncSession, site_id: int, data: ApplyBindingTemplateRequest
    ) -> dict[str, Any]:
        try:
            await ApplyXiangtaiBindingTemplate(db_session).execute(site_id, confirm=data.confirm)
        except (MicrogridDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        query = MicrogridQueryService(db_session)
        return {
            "items": await query.bindings(site_id=site_id),
            "readiness": await query.data_readiness(site_id=site_id),
        }

    @post(
        "/demo/bootstrap",
        operation_id="MicrogridBootstrapXiangtaiDemo",
        guards=[requires_permission("microgrid.configure")],
    )
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

    @post(
        "/scenarios/{scenario_id:int}/publish",
        operation_id="MicrogridPublishScenario",
        guards=[requires_permission("microgrid.configure")],
    )
    async def publish_scenario(self, db_session: AsyncSession, scenario_id: int) -> dict[str, Any]:
        try:
            scenario = await PublishScenario(db_session).execute(scenario_id)
        except MicrogridDomainError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        rows = await MicrogridQueryService(db_session).scenarios(site_id=scenario.site_id)
        return next(row for row in rows if row["id"] == scenario.id)

    @post(
        "/scenarios/{scenario_id:int}/working-copy",
        operation_id="MicrogridCreateWorkingCopy",
        guards=[requires_permission("microgrid.configure")],
    )
    async def create_working_copy(self, db_session: AsyncSession, scenario_id: int) -> dict[str, Any]:
        try:
            scenario = await CreateWorkingCopy(db_session).execute(scenario_id)
        except MicrogridDomainError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        rows = await MicrogridQueryService(db_session).scenarios(site_id=scenario.site_id)
        return next(row for row in rows if row["id"] == scenario.id)

    @patch(
        "/scenarios/{scenario_id:int}",
        operation_id="MicrogridUpdateScenario",
        guards=[requires_permission("microgrid.configure")],
    )
    async def update_scenario(
        self, db_session: AsyncSession, scenario_id: int, data: UpdateScenarioRequest
    ) -> dict[str, Any]:
        try:
            scenario = await UpdateWorkingScenario(db_session).execute(
                scenario_id,
                parameters=data.parameters,
                name=data.name,
                tariff_plan_id=data.tariff_plan_id,
                grid_emission_factor_id=data.grid_emission_factor_id,
                change_summary=data.change_summary,
            )
        except MicrogridDomainError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        rows = await MicrogridQueryService(db_session).scenarios(site_id=scenario.site_id)
        return next(row for row in rows if row["id"] == scenario.id)

    @post(
        "/scenarios/{scenario_id:int}/restore",
        operation_id="MicrogridRestoreScenario",
        guards=[requires_permission("microgrid.configure")],
    )
    async def restore_scenario(self, db_session: AsyncSession, scenario_id: int) -> dict[str, Any]:
        try:
            scenario = await RestoreScenario(db_session).execute(scenario_id)
        except MicrogridDomainError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        rows = await MicrogridQueryService(db_session).scenarios(site_id=scenario.site_id)
        return next(row for row in rows if row["id"] == scenario.id)

    @delete(
        "/scenarios/{scenario_id:int}/draft",
        operation_id="MicrogridDiscardScenarioDraft",
        status_code=204,
        guards=[requires_permission("microgrid.configure")],
    )
    async def discard_scenario_draft(self, db_session: AsyncSession, scenario_id: int) -> None:
        try:
            await DiscardScenarioDraft(db_session).execute(scenario_id)
        except MicrogridDomainError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @patch(
        "/flexibility-contracts/{contract_id:int}",
        operation_id="MicrogridUpdateFlexibilityContract",
        guards=[requires_permission("microgrid.configure")],
    )
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
                hard_constraint=data.hard_constraint,
                enabled=data.enabled,
            )
        except (MicrogridDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
