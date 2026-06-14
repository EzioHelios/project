from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, get, patch, post
from litestar.params import Body
from litestar.response import Response

from app.domain.carbon_assets.queries.assets import CarbonAssetsQuery, CarbonAssetsQueryService
from app.domain.carbon_assets.usecases.assets import CarbonAssetLedgerImportUseCase, CarbonAssetsUseCase
from app.domain.energy.controllers._utils import model_to_dict, ok_data

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


ASSETS_BODY = Body()


class CarbonAssetsController(Controller):
    tags = ["Carbon Assets"]

    @get("/api/carbon/assets/summary")
    async def get_summary(self, db_session: AsyncSession) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).summary()
        return Response(content=ok_data(data))

    @get("/api/carbon/assets/source-readiness")
    async def get_source_readiness(self, db_session: AsyncSession) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).source_readiness()
        return Response(content=ok_data(data))

    @post("/api/carbon/assets/imports/ledger")
    async def import_asset_ledger(self, db_session: AsyncSession, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        result = await CarbonAssetLedgerImportUseCase(db_session).import_rows(
            rows=list(data.get("rows") or []),
            source_name=data.get("source_name"),
        )
        return Response(
            content=ok_data(
                {
                    "received_count": result.received_count,
                    "imported_count": result.imported_count,
                    "skipped_count": result.skipped_count,
                    "errors": result.errors,
                }
            )
        )

    @get("/api/carbon/assets/compliance-periods")
    async def list_periods(
        self,
        db_session: AsyncSession,
        status: str | None = None,
        market: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).periods(_query(status=status, market=market, keyword=keyword, limit=limit, offset=offset))
        return Response(content=ok_data(data))

    @post("/api/carbon/assets/compliance-periods")
    async def create_period(self, db_session: AsyncSession, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        try:
            obj = await CarbonAssetsUseCase(db_session).create_period(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/assets/compliance-periods/{period_id:int}")
    async def update_period(self, db_session: AsyncSession, period_id: int, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        try:
            obj = await CarbonAssetsUseCase(db_session).update_period(period_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/assets/accounts")
    async def list_accounts(
        self,
        db_session: AsyncSession,
        asset_type: str | None = None,
        status: str | None = None,
        market: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).accounts(
            _query(asset_type=asset_type, status=status, market=market, keyword=keyword, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/assets/accounts")
    async def create_account(self, db_session: AsyncSession, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        try:
            obj = await CarbonAssetsUseCase(db_session).create_account(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/assets/accounts/{account_id:int}")
    async def update_account(self, db_session: AsyncSession, account_id: int, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        try:
            obj = await CarbonAssetsUseCase(db_session).update_account(account_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/assets/allowances")
    async def list_allowances(
        self,
        db_session: AsyncSession,
        period_id: int | None = None,
        account_id: int | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).allowances(
            _query(period_id=period_id, account_id=account_id, keyword=keyword, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/assets/allowances")
    async def create_allowance(self, db_session: AsyncSession, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        try:
            obj = await CarbonAssetsUseCase(db_session).create_allowance(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/assets/allowances/{allocation_id:int}")
    async def update_allowance(self, db_session: AsyncSession, allocation_id: int, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        try:
            obj = await CarbonAssetsUseCase(db_session).update_allowance(allocation_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/assets/credits")
    async def list_credits(
        self,
        db_session: AsyncSession,
        account_id: int | None = None,
        asset_type: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).credits(
            _query(account_id=account_id, asset_type=asset_type, status=status, keyword=keyword, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/assets/credits")
    async def create_credit(self, db_session: AsyncSession, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        try:
            obj = await CarbonAssetsUseCase(db_session).create_credit(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/assets/credits/{credit_id:int}")
    async def update_credit(self, db_session: AsyncSession, credit_id: int, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        try:
            obj = await CarbonAssetsUseCase(db_session).update_credit(credit_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/assets/transactions")
    async def list_transactions(
        self,
        db_session: AsyncSession,
        account_id: int | None = None,
        asset_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).transactions(
            _query(account_id=account_id, asset_type=asset_type, status=status, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/assets/transactions/simulate")
    async def simulate_transaction(self, db_session: AsyncSession, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        try:
            result = await CarbonAssetsUseCase(db_session).simulate_transaction(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(result))

    @get("/api/carbon/assets/surrenders")
    async def list_surrenders(
        self,
        db_session: AsyncSession,
        period_id: int | None = None,
        account_id: int | None = None,
        asset_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).surrenders(
            _query(period_id=period_id, account_id=account_id, asset_type=asset_type, status=status, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/assets/surrenders")
    async def create_surrender(self, db_session: AsyncSession, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        try:
            obj = await CarbonAssetsUseCase(db_session).create_surrender(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/assets/forecast-scenarios")
    async def list_forecast_scenarios(
        self,
        db_session: AsyncSession,
        period_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).forecast_scenarios(
            _query(period_id=period_id, status=status, keyword=keyword, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/assets/forecast-scenarios")
    async def create_forecast_scenario(self, db_session: AsyncSession, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        try:
            obj = await CarbonAssetsUseCase(db_session).create_forecast_scenario(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/assets/forecast-scenarios/{scenario_id:int}")
    async def update_forecast_scenario(self, db_session: AsyncSession, scenario_id: int, data: dict[str, Any] = ASSETS_BODY) -> Response[dict]:
        try:
            obj = await CarbonAssetsUseCase(db_session).update_forecast_scenario(scenario_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/assets/forecast")
    async def get_forecast(
        self,
        db_session: AsyncSession,
        period_id: int | None = None,
        scenario_id: int | None = None,
    ) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).forecast(period_id=period_id, scenario_id=scenario_id)
        return Response(content=ok_data(data))

    @get("/api/carbon/assets/compliance-position")
    async def get_compliance_position(self, db_session: AsyncSession, period_id: int | None = None) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).compliance_position(period_id)
        return Response(content=ok_data(data))

    @get("/api/carbon/assets/alerts")
    async def get_alerts(self, db_session: AsyncSession, status: str | None = None) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).alerts(_query(status=status))
        return Response(content=ok_data(data))

    @get("/api/carbon/assets/recommendations")
    async def get_recommendations(self, db_session: AsyncSession, period_id: int | None = None) -> Response[dict]:
        data = await CarbonAssetsQueryService(db_session).recommendations(period_id)
        return Response(content=ok_data(data))


def _query(
    *,
    period_id: int | None = None,
    scenario_id: int | None = None,
    account_id: int | None = None,
    asset_type: str | None = None,
    status: str | None = None,
    market: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> CarbonAssetsQuery:
    return CarbonAssetsQuery(
        period_id=period_id,
        scenario_id=scenario_id,
        account_id=account_id,
        asset_type=asset_type,
        status=status,
        market=market,
        keyword=keyword,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
    )


def _error(exc: ValueError) -> Response[dict]:
    message = str(exc)
    status_code = 404 if "不存在" in message else 400
    return Response(content={"code": status_code, "msg": message, "data": None}, status_code=status_code)
