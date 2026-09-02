from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, delete, get, patch, post
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import func, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict, ok_data
from app.domain.energy_budget.queries.budget import EnergyBudgetQuery, EnergyBudgetQueryService
from app.domain.energy_budget.usecases.budget import EnergyBudgetUseCase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


BUDGET_BODY = Body()


class EnergyBudgetController(Controller):
    tags = ["Energy"]

    @get("/api/energy/budget/plans")
    async def list_energy_budget_plans(
        self,
        db_session: AsyncSession,
        budget_year: int | None = None,
        status: str | None = None,
        target_scope: str | None = None,
        target_code: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        conditions = []
        if budget_year is not None:
            conditions.append(m.EnergyCarbonBudgetPlan.budget_year == budget_year)
        if status and status != "all":
            conditions.append(m.EnergyCarbonBudgetPlan.status == status)
        if target_scope and target_scope != "all":
            conditions.append(m.EnergyCarbonBudgetPlan.target_scope == target_scope)
        if target_code:
            conditions.append(m.EnergyCarbonBudgetPlan.target_code == target_code)
        if keyword:
            value = f"%{keyword.strip()}%"
            conditions.append((m.EnergyCarbonBudgetPlan.name.ilike(value)) | (m.EnergyCarbonBudgetPlan.code.ilike(value)))
        stmt = select(m.EnergyCarbonBudgetPlan).where(*conditions).order_by(m.EnergyCarbonBudgetPlan.id.desc())
        total = int((await db_session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await db_session.execute(stmt.limit(_limit(limit)).offset(max(0, offset)))).scalars().all()
        return Response(content=_page([model_to_dict(row) for row in rows], total, _limit(limit), max(0, offset)))

    @post("/api/energy/budget/plans")
    async def create_energy_budget_plan(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = BUDGET_BODY,
    ) -> Response[dict]:
        try:
            obj = await EnergyBudgetUseCase(db_session).create_plan(data)
        except ValueError as exc:
            return _bad_request(str(exc))
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/energy/budget/plans/{plan_id:int}")
    async def update_energy_budget_plan(
        self,
        db_session: AsyncSession,
        plan_id: int,
        data: dict[str, Any] = BUDGET_BODY,
    ) -> Response[dict]:
        try:
            obj = await EnergyBudgetUseCase(db_session).update_plan(plan_id, data)
        except ValueError as exc:
            return _not_found_or_bad_request(str(exc))
        return Response(content=ok_data(model_to_dict(obj)))

    @delete("/api/energy/budget/plans/{plan_id:int}", status_code=200)
    async def delete_energy_budget_plan(self, db_session: AsyncSession, plan_id: int) -> Response[dict]:
        try:
            await EnergyBudgetUseCase(db_session).delete_plan(plan_id)
        except ValueError as exc:
            return _not_found_or_bad_request(str(exc))
        return Response(content={"code": 200, "msg": "已删除"})

    @post("/api/energy/budget/plans/{plan_id:int}/generate-allocations")
    async def generate_energy_budget_allocations(
        self,
        db_session: AsyncSession,
        plan_id: int,
        data: dict[str, Any] = BUDGET_BODY,
    ) -> Response[dict]:
        try:
            result = await EnergyBudgetUseCase(db_session).generate_allocations(plan_id, data)
        except ValueError as exc:
            return _not_found_or_bad_request(str(exc))
        return Response(content=ok_data(result))

    @get("/api/energy/budget/allocations")
    async def list_energy_budget_allocations(
        self,
        db_session: AsyncSession,
        plan_id: int | None = None,
        budget_year: int | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Response[dict]:
        conditions = []
        if plan_id is not None:
            conditions.append(m.EnergyCarbonBudgetAllocation.plan_id == plan_id)
        if status and status != "all":
            conditions.append(m.EnergyCarbonBudgetAllocation.status == status)
        if budget_year is not None:
            conditions.append(m.EnergyCarbonBudgetPlan.budget_year == budget_year)
            stmt = (
                select(m.EnergyCarbonBudgetAllocation)
                .join(m.EnergyCarbonBudgetPlan, m.EnergyCarbonBudgetPlan.id == m.EnergyCarbonBudgetAllocation.plan_id)
                .where(*conditions)
                .order_by(m.EnergyCarbonBudgetAllocation.period_month.asc())
            )
        else:
            stmt = (
                select(m.EnergyCarbonBudgetAllocation)
                .where(*conditions)
                .order_by(m.EnergyCarbonBudgetAllocation.period_month.asc())
            )
        total = int((await db_session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await db_session.execute(stmt.limit(_limit(limit)).offset(max(0, offset)))).scalars().all()
        return Response(content=_page([model_to_dict(row) for row in rows], total, _limit(limit), max(0, offset)))

    @patch("/api/energy/budget/allocations/{allocation_id:int}")
    async def update_energy_budget_allocation(
        self,
        db_session: AsyncSession,
        allocation_id: int,
        data: dict[str, Any] = BUDGET_BODY,
    ) -> Response[dict]:
        try:
            obj = await EnergyBudgetUseCase(db_session).update_allocation(allocation_id, data)
        except ValueError as exc:
            return _not_found_or_bad_request(str(exc))
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/energy/budget/progress")
    async def get_energy_budget_progress(
        self,
        db_session: AsyncSession,
        plan_id: int | None = None,
        budget_year: int | None = None,
        status: str | None = None,
        target_scope: str | None = None,
        target_code: str | None = None,
    ) -> Response[dict]:
        data = await EnergyBudgetQueryService(db_session).progress(_query(plan_id, budget_year, status, target_scope, target_code))
        return Response(content=ok_data(data))

    @get("/api/energy/budget/alerts")
    async def get_energy_budget_alerts(
        self,
        db_session: AsyncSession,
        plan_id: int | None = None,
        budget_year: int | None = None,
        status: str | None = None,
        target_scope: str | None = None,
        target_code: str | None = None,
    ) -> Response[dict]:
        data = await EnergyBudgetQueryService(db_session).alerts(_query(plan_id, budget_year, status, target_scope, target_code))
        return Response(content=ok_data(data))

    @get("/api/energy/budget/forecast")
    async def get_energy_budget_forecast(
        self,
        db_session: AsyncSession,
        plan_id: int | None = None,
        budget_year: int | None = None,
        status: str | None = None,
        target_scope: str | None = None,
        target_code: str | None = None,
    ) -> Response[dict]:
        data = await EnergyBudgetQueryService(db_session).forecast(_query(plan_id, budget_year, status, target_scope, target_code))
        return Response(content=ok_data(data))

    @get("/api/energy/budget/recommendations")
    async def get_energy_budget_recommendations(
        self,
        db_session: AsyncSession,
        plan_id: int | None = None,
        budget_year: int | None = None,
        status: str | None = None,
        target_scope: str | None = None,
        target_code: str | None = None,
    ) -> Response[dict]:
        data = await EnergyBudgetQueryService(db_session).recommendations(_query(plan_id, budget_year, status, target_scope, target_code))
        return Response(content=ok_data(data))

    @get("/api/energy/budget/report")
    async def get_energy_budget_report(
        self,
        db_session: AsyncSession,
        plan_id: int | None = None,
        budget_year: int | None = None,
        status: str | None = None,
        target_scope: str | None = None,
        target_code: str | None = None,
    ) -> Response[dict]:
        data = await EnergyBudgetQueryService(db_session).report(_query(plan_id, budget_year, status, target_scope, target_code))
        return Response(content=ok_data(data))

    @get("/api/energy/budget/adjustments")
    async def list_energy_budget_adjustments(
        self,
        db_session: AsyncSession,
        plan_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        conditions = []
        if plan_id is not None:
            conditions.append(m.EnergyCarbonBudgetAdjustment.plan_id == plan_id)
        if status and status != "all":
            conditions.append(m.EnergyCarbonBudgetAdjustment.status == status)
        stmt = select(m.EnergyCarbonBudgetAdjustment).where(*conditions).order_by(m.EnergyCarbonBudgetAdjustment.id.desc())
        total = int((await db_session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await db_session.execute(stmt.limit(_limit(limit)).offset(max(0, offset)))).scalars().all()
        return Response(content=_page([model_to_dict(row) for row in rows], total, _limit(limit), max(0, offset)))

    @post("/api/energy/budget/adjustments")
    async def create_energy_budget_adjustment(
        self,
        db_session: AsyncSession,
        data: dict[str, Any] = BUDGET_BODY,
    ) -> Response[dict]:
        try:
            obj = await EnergyBudgetUseCase(db_session).create_adjustment(data)
        except ValueError as exc:
            return _not_found_or_bad_request(str(exc))
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/energy/budget/adjustments/{adjustment_id:int}")
    async def update_energy_budget_adjustment(
        self,
        db_session: AsyncSession,
        adjustment_id: int,
        data: dict[str, Any] = BUDGET_BODY,
    ) -> Response[dict]:
        try:
            obj = await EnergyBudgetUseCase(db_session).update_adjustment(adjustment_id, data)
        except ValueError as exc:
            return _not_found_or_bad_request(str(exc))
        return Response(content=ok_data(model_to_dict(obj)))

    @delete("/api/energy/budget/adjustments/{adjustment_id:int}", status_code=200)
    async def delete_energy_budget_adjustment(self, db_session: AsyncSession, adjustment_id: int) -> Response[dict]:
        try:
            await EnergyBudgetUseCase(db_session).delete_adjustment(adjustment_id)
        except ValueError as exc:
            return _not_found_or_bad_request(str(exc))
        return Response(content={"code": 200, "msg": "已删除"})


def _query(
    plan_id: int | None,
    budget_year: int | None,
    status: str | None,
    target_scope: str | None,
    target_code: str | None,
) -> EnergyBudgetQuery:
    return EnergyBudgetQuery(
        plan_id=plan_id,
        budget_year=budget_year,
        status=status,
        target_scope=target_scope,
        target_code=target_code,
    )


def _page(items: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _limit(value: int) -> int:
    return max(1, min(int(value or 50), 200))


def _bad_request(message: str) -> Response[dict]:
    return Response(content={"code": 400, "msg": message, "data": None}, status_code=400)


def _not_found_or_bad_request(message: str) -> Response[dict]:
    status_code = 404 if "不存在" in message else 400
    return Response(content={"code": status_code, "msg": message, "data": None}, status_code=status_code)
