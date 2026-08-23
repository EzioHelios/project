"""Carbon asset ledger, compliance, market, and cost APIs."""

from __future__ import annotations

# ruff: noqa: TC003
from datetime import date
from typing import TYPE_CHECKING, Any

import msgspec
from litestar import Controller, get, post
from litestar.exceptions import ClientException

from app.db import models as m
from app.domain.accounts.guards import requires_permission
from app.domain.carbon_assets.queries.assets import AssetQuery, CarbonAssetQueryService, model_payload
from app.domain.carbon_assets.schemas import (
    AccountRequest,
    AssetOverviewResponse,
    ComplianceCycleRequest,
    CostRunResponse,
    CostScenarioRequest,
    EnvironmentalUsageRequest,
    InstrumentRequest,
    LotRequest,
    MarketQuoteRequest,
    MovementRequest,
    PageResponse,
    ReversalRequest,
    RuleVersionRequest,
    SettlementRequest,
)
from app.domain.carbon_assets.usecases.assets import CarbonAssetUseCase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CarbonAssetsController(Controller):
    path = "/api/carbon/assets"
    tags = ["Carbon Assets"]

    @get("/overview", operation_id="CarbonAssetsGetOverview", guards=[requires_permission("carbon.assets.view")])
    async def overview(self, db_session: AsyncSession) -> AssetOverviewResponse:
        return msgspec.convert(await CarbonAssetQueryService(db_session).overview(), type=AssetOverviewResponse)

    @get("/instruments", operation_id="CarbonAssetsListInstruments", guards=[requires_permission("carbon.assets.view")])
    async def instruments(self, db_session: AsyncSession, status: str | None = None, instrument_class: str | None = None, keyword: str | None = None, limit: int = 50, offset: int = 0) -> PageResponse:
        return await _page(db_session, m.CarbonAssetInstrument, status=status, instrument_class=instrument_class, keyword=keyword, limit=limit, offset=offset)

    @post("/instruments", operation_id="CarbonAssetsCreateInstrument", guards=[requires_permission("carbon.assets.configure")])
    async def create_instrument(self, db_session: AsyncSession, data: InstrumentRequest) -> dict[str, Any]:
        return await _execute(CarbonAssetUseCase(db_session).create_instrument(data))

    @get("/accounts", operation_id="CarbonAssetsListAccounts", guards=[requires_permission("carbon.assets.view")])
    async def accounts(self, db_session: AsyncSession, instrument_id: int | None = None, status: str | None = None, keyword: str | None = None, limit: int = 50, offset: int = 0) -> PageResponse:
        return await _page(db_session, m.CarbonAssetAccount, instrument_id=instrument_id, status=status, keyword=keyword, limit=limit, offset=offset)

    @post("/accounts", operation_id="CarbonAssetsCreateAccount", guards=[requires_permission("carbon.assets.configure")])
    async def create_account(self, db_session: AsyncSession, data: AccountRequest) -> dict[str, Any]:
        return await _execute(CarbonAssetUseCase(db_session).create_account(data))

    @get("/lots", operation_id="CarbonAssetsListLots", guards=[requires_permission("carbon.assets.view")])
    async def lots(self, db_session: AsyncSession, instrument_id: int | None = None, account_id: int | None = None, status: str | None = None, keyword: str | None = None, limit: int = 50, offset: int = 0) -> PageResponse:
        return await _page(db_session, m.CarbonAssetLot, instrument_id=instrument_id, account_id=account_id, status=status, keyword=keyword, limit=limit, offset=offset)

    @post("/lots", operation_id="CarbonAssetsCreateLot", guards=[requires_permission("carbon.assets.ledger.post")])
    async def create_lot(self, db_session: AsyncSession, data: LotRequest) -> dict[str, Any]:
        return await _execute(CarbonAssetUseCase(db_session).create_lot(data))

    @get("/movements", operation_id="CarbonAssetsListMovements", guards=[requires_permission("carbon.assets.view")])
    async def movements(self, db_session: AsyncSession, instrument_id: int | None = None, account_id: int | None = None, lot_id: int | None = None, date_from: date | None = None, date_to: date | None = None, limit: int = 50, offset: int = 0) -> PageResponse:
        return await _page(db_session, m.CarbonAssetMovement, instrument_id=instrument_id, account_id=account_id, lot_id=lot_id, date_from=date_from, date_to=date_to, limit=limit, offset=offset)

    @post("/movements", operation_id="CarbonAssetsPostMovement", guards=[requires_permission("carbon.assets.ledger.post")])
    async def post_movement(self, db_session: AsyncSession, data: MovementRequest) -> dict[str, Any]:
        return await _execute(CarbonAssetUseCase(db_session).post_movement(data))

    @post("/movements/{movement_id:int}/reversal", operation_id="CarbonAssetsReverseMovement", guards=[requires_permission("carbon.assets.ledger.post")])
    async def reverse_movement(self, db_session: AsyncSession, movement_id: int, data: ReversalRequest) -> dict[str, Any]:
        return await _execute(CarbonAssetUseCase(db_session).reverse_movement(movement_id, data))

    @get("/rules", operation_id="CarbonAssetsListRules", guards=[requires_permission("carbon.assets.view")])
    async def rules(self, db_session: AsyncSession, status: str | None = None, keyword: str | None = None, limit: int = 50, offset: int = 0) -> PageResponse:
        return await _page(db_session, m.CarbonComplianceRuleVersion, status=status, keyword=keyword, limit=limit, offset=offset)

    @post("/rules", operation_id="CarbonAssetsCreateRule", guards=[requires_permission("carbon.assets.configure")])
    async def create_rule(self, db_session: AsyncSession, data: RuleVersionRequest) -> dict[str, Any]:
        return await _execute(CarbonAssetUseCase(db_session).create_rule(data))

    @get("/cycles", operation_id="CarbonAssetsListCycles", guards=[requires_permission("carbon.assets.view")])
    async def cycles(self, db_session: AsyncSession, status: str | None = None, keyword: str | None = None, limit: int = 50, offset: int = 0) -> PageResponse:
        return await _page(db_session, m.CarbonComplianceCycle, status=status, keyword=keyword, limit=limit, offset=offset)

    @post("/cycles", operation_id="CarbonAssetsCreateCycle", guards=[requires_permission("carbon.assets.compliance.manage")])
    async def create_cycle(self, db_session: AsyncSession, data: ComplianceCycleRequest) -> dict[str, Any]:
        return await _execute(CarbonAssetUseCase(db_session).create_cycle(data))

    @get("/compliance-position", operation_id="CarbonAssetsGetCompliancePosition", guards=[requires_permission("carbon.assets.view")])
    async def compliance_position(self, db_session: AsyncSession, cycle_id: int | None = None) -> dict[str, Any]:
        return (await CarbonAssetQueryService(db_session).compliance_position(cycle_id)) or {}

    @get("/settlements", operation_id="CarbonAssetsListSettlements", guards=[requires_permission("carbon.assets.view")])
    async def settlements(self, db_session: AsyncSession, cycle_id: int | None = None, status: str | None = None, limit: int = 50, offset: int = 0) -> PageResponse:
        return await _page(db_session, m.CarbonComplianceSettlement, cycle_id=cycle_id, status=status, limit=limit, offset=offset)

    @post("/settlements", operation_id="CarbonAssetsCreateSettlement", guards=[requires_permission("carbon.assets.compliance.manage")])
    async def create_settlement(self, db_session: AsyncSession, data: SettlementRequest) -> dict[str, Any]:
        return await _execute(CarbonAssetUseCase(db_session).create_settlement(data))

    @post("/settlements/{settlement_id:int}/post", operation_id="CarbonAssetsPostSettlement", guards=[requires_permission("carbon.assets.compliance.manage")])
    async def post_settlement(self, db_session: AsyncSession, settlement_id: int) -> dict[str, Any]:
        return await _execute(CarbonAssetUseCase(db_session).post_settlement(settlement_id))

    @get("/environmental-usages", operation_id="CarbonAssetsListEnvironmentalUsages", guards=[requires_permission("carbon.assets.view")])
    async def environmental_usages(self, db_session: AsyncSession, lot_id: int | None = None, limit: int = 50, offset: int = 0) -> PageResponse:
        return await _page(db_session, m.EnvironmentalAssetUsage, lot_id=lot_id, limit=limit, offset=offset)

    @post("/environmental-usages", operation_id="CarbonAssetsRecordEnvironmentalUsage", guards=[requires_permission("carbon.assets.ledger.post")])
    async def record_environmental_usage(self, db_session: AsyncSession, data: EnvironmentalUsageRequest) -> dict[str, Any]:
        return await _execute(CarbonAssetUseCase(db_session).record_usage(data))

    @get("/quotes", operation_id="CarbonAssetsListQuotes", guards=[requires_permission("carbon.assets.view")])
    async def quotes(self, db_session: AsyncSession, instrument_id: int | None = None, date_from: date | None = None, date_to: date | None = None, limit: int = 100, offset: int = 0) -> PageResponse:
        return await _page(db_session, m.CarbonMarketQuote, instrument_id=instrument_id, date_from=date_from, date_to=date_to, limit=limit, offset=offset)

    @post("/quotes", operation_id="CarbonAssetsCreateQuote", guards=[requires_permission("carbon.assets.market.manage")])
    async def create_quote(self, db_session: AsyncSession, data: MarketQuoteRequest) -> dict[str, Any]:
        return await _execute(CarbonAssetUseCase(db_session).create_quote(data))

    @get("/cost-scenarios", operation_id="CarbonAssetsListCostScenarios", guards=[requires_permission("carbon.assets.view")])
    async def cost_scenarios(self, db_session: AsyncSession, status: str | None = None, keyword: str | None = None, limit: int = 50, offset: int = 0) -> PageResponse:
        return await _page(db_session, m.CarbonCostScenario, status=status, keyword=keyword, limit=limit, offset=offset)

    @post("/cost-scenarios", operation_id="CarbonAssetsCreateCostScenario", guards=[requires_permission("carbon.assets.cost.run")])
    async def create_cost_scenario(self, db_session: AsyncSession, data: CostScenarioRequest) -> dict[str, Any]:
        return await _execute(CarbonAssetUseCase(db_session).create_scenario(data))

    @get("/cost-runs", operation_id="CarbonAssetsListCostRuns", guards=[requires_permission("carbon.assets.view")])
    async def cost_runs(self, db_session: AsyncSession, limit: int = 50, offset: int = 0) -> PageResponse:
        return await _page(db_session, m.CarbonCostRun, limit=limit, offset=offset)

    @post("/cost-scenarios/{scenario_id:int}/runs", operation_id="CarbonAssetsRunCostScenario", guards=[requires_permission("carbon.assets.cost.run")])
    async def run_cost_scenario(self, db_session: AsyncSession, scenario_id: int) -> CostRunResponse:
        row = await _execute(CarbonAssetUseCase(db_session).run_scenario(scenario_id))
        return msgspec.convert(row, type=CostRunResponse)


async def _page(session: AsyncSession, model: type[Any], **kwargs: Any) -> PageResponse:
    kwargs["limit"] = max(1, min(int(kwargs.get("limit", 50)), 200))
    kwargs["offset"] = max(0, int(kwargs.get("offset", 0)))
    return msgspec.convert(await CarbonAssetQueryService(session).page(model, AssetQuery(**kwargs)), type=PageResponse)


async def _execute(awaitable: Any) -> dict[str, Any]:
    try:
        row = await awaitable
    except ValueError as exc:
        raise ClientException(status_code=422, detail=str(exc)) from exc
    return model_payload(row)
