"""HTTP API for material handling carbon allocation."""

from __future__ import annotations

from litestar import Controller, Request, delete, get, patch, post
from litestar.response import Response
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.domain.accounts.guards import has_permission, requires_active_user, requires_permission
from app.domain.energy.controllers._utils import model_to_dict, ok_data
from app.domain.material_allocation.queries import MaterialAllocationQueryService
from app.domain.material_allocation.schemas import HourCalculation, OperationCreate, OperationUpdate  # noqa: TC001
from app.domain.material_allocation.usecases import (
    CalculateMaterialCarbonAllocation,
    MaterialAllocationError,
    MaterialHandlingOperationUseCase,
)


class MaterialAllocationController(Controller):
    tags = ["Material Allocation"]
    guards = [requires_active_user]

    @get("/api/material-allocation/options")
    async def options(self, db_session: AsyncSession, request: Request) -> Response[dict]:
        data = await MaterialAllocationQueryService(db_session).options()
        data["can_manage"] = has_permission(request.user, "material_operations:write")
        data["can_calculate"] = has_permission(request.user, "material_allocation:calculate")
        return Response(content=ok_data(data))

    @get("/api/material-allocation/summary")
    async def summary(self, db_session: AsyncSession) -> Response[dict]:
        data = await MaterialAllocationQueryService(db_session).summary()
        return Response(content=ok_data(data))

    @get("/api/material-allocation/operations")
    async def list_operations(
        self,
        db_session: AsyncSession,
        keyword: str | None = None,
        operation_type: str | None = None,
        equipment_type: str | None = None,
        material_code: str | None = None,
        batch_no: str | None = None,
        operation_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_field: str = "period_start",
        sort_order: str = "desc",
    ) -> Response[dict]:
        data = await MaterialAllocationQueryService(db_session).operations(
            {
                "keyword": keyword,
                "operation_type": operation_type,
                "equipment_type": equipment_type,
                "material_code": material_code,
                "batch_no": batch_no,
                "operation_status": operation_status,
                "limit": limit,
                "offset": offset,
                "sort_field": sort_field,
                "sort_order": sort_order,
            }
        )
        return Response(content=ok_data(data))

    @post("/api/material-allocation/operations", guards=[requires_permission("material_operations:write")])
    async def create_operation(self, db_session: AsyncSession, data: OperationCreate) -> Response[dict]:
        try:
            obj = await MaterialHandlingOperationUseCase(db_session).create(data)
            await db_session.commit()
        except MaterialAllocationError as exc:
            await db_session.rollback()
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch(
        "/api/material-allocation/operations/{operation_id:int}",
        guards=[requires_permission("material_operations:write")],
    )
    async def update_operation(
        self, db_session: AsyncSession, operation_id: int, data: OperationUpdate
    ) -> Response[dict]:
        try:
            obj = await MaterialHandlingOperationUseCase(db_session).update(operation_id, data)
            await db_session.commit()
        except MaterialAllocationError as exc:
            await db_session.rollback()
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @delete(
        "/api/material-allocation/operations/{operation_id:int}",
        status_code=200,
        guards=[requires_permission("material_operations:write")],
    )
    async def delete_operation(self, db_session: AsyncSession, operation_id: int) -> Response[dict]:
        try:
            await MaterialHandlingOperationUseCase(db_session).delete(operation_id)
            await db_session.commit()
        except MaterialAllocationError as exc:
            await db_session.rollback()
            return _error(exc)
        return Response(content=ok_data({"deleted": True}))

    @get("/api/material-allocation/runs")
    async def list_runs(
        self,
        db_session: AsyncSession,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_field: str = "created_at",
        sort_order: str = "desc",
    ) -> Response[dict]:
        data = await MaterialAllocationQueryService(db_session).runs(
            {"status": status, "limit": limit, "offset": offset, "sort_field": sort_field, "sort_order": sort_order}
        )
        return Response(content=ok_data(data))

    @post("/api/material-allocation/runs/calculate", guards=[requires_permission("material_allocation:calculate")])
    async def calculate(self, db_session: AsyncSession, data: HourCalculation) -> Response[dict]:
        try:
            run = await CalculateMaterialCarbonAllocation(db_session).execute(data)
            await db_session.commit()
        except MaterialAllocationError as exc:
            await db_session.rollback()
            return _error(exc)
        return Response(content=ok_data({"items": [model_to_dict(row) for row in run]}))

    @get("/api/material-allocation/operations/{operation_id:int}")
    async def detail(self, db_session: AsyncSession, operation_id: int) -> Response[dict]:
        try:
            return Response(
                content=ok_data(model_to_dict(await MaterialHandlingOperationUseCase(db_session).get(operation_id)))
            )
        except MaterialAllocationError as exc:
            return _error(exc)

    @post(
        "/api/material-allocation/operations/{operation_id:int}/confirm",
        guards=[requires_permission("material_operations:write")],
    )
    async def confirm(self, db_session: AsyncSession, operation_id: int) -> Response[dict]:
        try:
            row = await MaterialHandlingOperationUseCase(db_session).confirm(operation_id)
            await db_session.commit()
            return Response(content=ok_data(model_to_dict(row)))
        except MaterialAllocationError as exc:
            await db_session.rollback()
            return _error(exc)

    @post(
        "/api/material-allocation/operations/{operation_id:int}/withdraw",
        guards=[requires_permission("material_operations:write")],
    )
    async def withdraw(self, db_session: AsyncSession, operation_id: int) -> Response[dict]:
        try:
            row = await MaterialHandlingOperationUseCase(db_session).withdraw(operation_id)
            await db_session.commit()
            return Response(content=ok_data(model_to_dict(row)))
        except MaterialAllocationError as exc:
            await db_session.rollback()
            return _error(exc)

    @get("/api/material-allocation/results")
    async def list_results(
        self,
        db_session: AsyncSession,
        run_id: int | None = None,
        run_code: str | None = None,
        material_code: str | None = None,
        batch_no: str | None = None,
        equipment_code: str | None = None,
        study_id: int | None = None,
        data_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_field: str = "created_at",
        sort_order: str = "desc",
    ) -> Response[dict]:
        data = await MaterialAllocationQueryService(db_session).results(
            {
                "run_id": run_id,
                "run_code": run_code,
                "material_code": material_code,
                "batch_no": batch_no,
                "equipment_code": equipment_code,
                "study_id": study_id,
                "data_status": data_status,
                "limit": limit,
                "offset": offset,
                "sort_field": sort_field,
                "sort_order": sort_order,
            }
        )
        return Response(content=ok_data(data))


def _error(exc: Exception) -> Response[dict]:
    return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
