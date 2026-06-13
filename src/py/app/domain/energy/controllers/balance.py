from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, get, post
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import func, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict, ok_data
from app.domain.energy.queries.balance import EnergyBalanceQuery, EnergyBalanceQueryService
from app.domain.energy.usecases.balance import EnergyBalanceOptimizationUseCase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


BALANCE_BODY = Body()


class EnergyBalanceController(Controller):
    tags = ["Energy"]

    @get("/api/energy/balance/overview")
    async def get_energy_balance_overview(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "day",
        balance_object_type: str = "enterprise",
        balance_object_code: str | None = None,
        energy_type_code: str | None = None,
        area_keyword: str | None = None,
        use_system_code: str | None = None,
    ) -> Response[dict]:
        data = await EnergyBalanceQueryService(db_session).overview(
            _query(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                balance_object_type=balance_object_type,
                balance_object_code=balance_object_code,
                energy_type_code=energy_type_code,
                area_keyword=area_keyword,
                use_system_code=use_system_code,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/balance/table")
    async def get_energy_balance_table(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "day",
        balance_object_type: str = "enterprise",
        balance_object_code: str | None = None,
        energy_type_code: str | None = None,
        area_keyword: str | None = None,
        use_system_code: str | None = None,
    ) -> Response[dict]:
        data = await EnergyBalanceQueryService(db_session).table(
            _query(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                balance_object_type=balance_object_type,
                balance_object_code=balance_object_code,
                energy_type_code=energy_type_code,
                area_keyword=area_keyword,
                use_system_code=use_system_code,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/balance/data-quality")
    async def get_energy_balance_data_quality(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "day",
        balance_object_type: str = "enterprise",
        balance_object_code: str | None = None,
        energy_type_code: str | None = None,
        area_keyword: str | None = None,
        use_system_code: str | None = None,
    ) -> Response[dict]:
        data = await EnergyBalanceQueryService(db_session).data_quality(
            _query(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                balance_object_type=balance_object_type,
                balance_object_code=balance_object_code,
                energy_type_code=energy_type_code,
                area_keyword=area_keyword,
                use_system_code=use_system_code,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/balance/optimization-scenarios")
    async def list_energy_balance_optimization_scenarios(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "day",
        balance_object_type: str = "enterprise",
        balance_object_code: str | None = None,
        energy_type_code: str | None = None,
        area_keyword: str | None = None,
        use_system_code: str | None = None,
    ) -> Response[dict]:
        data = await EnergyBalanceQueryService(db_session).scenarios(
            _query(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                balance_object_type=balance_object_type,
                balance_object_code=balance_object_code,
                energy_type_code=energy_type_code,
                area_keyword=area_keyword,
                use_system_code=use_system_code,
            )
        )
        return Response(content=ok_data(data))

    @post("/api/energy/balance/simulate")
    async def simulate_energy_balance_optimization(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = BALANCE_BODY,
    ) -> Response[dict]:
        try:
            result = await EnergyBalanceOptimizationUseCase(db_session).simulate(data)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc), "data": None}, status_code=400)
        return Response(content=ok_data(result))

    @get("/api/energy/balance/records")
    async def list_energy_balance_optimization_records(
        self,
        db_session: AsyncSession,
        scenario_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        conditions = []
        if scenario_type and scenario_type != "all":
            conditions.append(m.EnergyOptimizationRecord.scenario_type == scenario_type)
        stmt = select(m.EnergyOptimizationRecord).where(*conditions).order_by(m.EnergyOptimizationRecord.id.desc())
        total = int((await db_session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await db_session.execute(stmt.limit(_limit(limit)).offset(max(0, offset)))).scalars().all()
        return Response(content=_page([model_to_dict(row) for row in rows], total, _limit(limit), max(0, offset)))

    @post("/api/energy/balance/records")
    async def create_energy_balance_optimization_record(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = BALANCE_BODY,
    ) -> Response[dict]:
        try:
            obj = await EnergyBalanceOptimizationUseCase(db_session).create_record(data)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc), "data": None}, status_code=400)
        return Response(content=ok_data(model_to_dict(obj)))


def _query(
    *,
    period_start: str | None,
    period_end: str | None,
    granularity: str,
    balance_object_type: str,
    balance_object_code: str | None,
    energy_type_code: str | None,
    area_keyword: str | None,
    use_system_code: str | None,
) -> EnergyBalanceQuery:
    return EnergyBalanceQuery(
        period_start=period_start,
        period_end=period_end,
        granularity=granularity,
        balance_object_type=balance_object_type,
        balance_object_code=balance_object_code,
        energy_type_code=energy_type_code,
        area_keyword=area_keyword,
        use_system_code=use_system_code,
    )


def _page(items: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _limit(value: int) -> int:
    return max(1, min(int(value or 20), 200))
