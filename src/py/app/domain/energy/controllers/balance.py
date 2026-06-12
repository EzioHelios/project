from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from litestar import Controller, get, post
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import func, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict, ok_data
from app.domain.energy.queries.balance import SCENARIOS, EnergyBalanceQuery, EnergyBalanceQueryService

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
        result = await EnergyBalanceQueryService(db_session).simulate(data)
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
        payload = _record_payload(data)
        if isinstance(payload, Response):
            return payload
        obj = m.EnergyOptimizationRecord(**payload)
        db_session.add(obj)
        await db_session.commit()
        await db_session.refresh(obj)
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


def _record_payload(data: dict[str, Any]) -> dict[str, Any] | Response[dict]:
    scenario_type = _str(data.get("scenario_type"))
    if scenario_type not in SCENARIOS:
        return Response(content={"code": 400, "msg": "优化场景无效", "data": None}, status_code=400)
    scenario = SCENARIOS[scenario_type]
    return {
        "balance_object_type": _str(data.get("balance_object_type")) or "enterprise",
        "balance_object_code": _str(data.get("balance_object_code")),
        "balance_object_name": _str(data.get("balance_object_name")),
        "period_start": _date_or_none(data.get("period_start")),
        "period_end": _date_or_none(data.get("period_end")),
        "scenario_type": scenario_type,
        "scenario_name": _str(data.get("scenario_name")) or scenario["name"],
        "before_parameters": _dict_or_none(data.get("before_parameters")),
        "after_parameters": _dict_or_none(data.get("after_parameters")),
        "baseline_energy": _decimal_or_none(data.get("baseline_energy")),
        "expected_energy": _decimal_or_none(data.get("expected_energy")),
        "saving_energy": _decimal_or_none(data.get("saving_energy")),
        "saving_rate_pct": _decimal_or_none(data.get("saving_rate_pct")),
        "cost_delta_cny": _decimal_or_none(data.get("cost_delta_cny")),
        "method": _str(data.get("method")),
        "assumptions": _dict_or_none(data.get("assumptions")),
        "source_name": _str(data.get("source_name")),
        "source_type": _str(data.get("source_type")),
        "confidence_level": _str(data.get("confidence_level")),
        "status": _str(data.get("status")) or "simulated",
        "remark": _str(data.get("remark")),
    }


def _page(items: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _limit(value: int) -> int:
    return max(1, min(int(value or 20), 200))


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date_or_none(value: Any) -> date | None:
    text = _str(value)
    if not text:
        return None
    return date.fromisoformat(text[:10])


def _decimal_or_none(value: Any) -> Decimal | None:
    text = _str(value)
    if text is None:
        return None
    return Decimal(text)


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None
