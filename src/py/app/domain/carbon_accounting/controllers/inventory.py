from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get, patch, post
from litestar.params import Body
from litestar.response import File, Response

from app.domain.carbon_accounting.queries.inventory import CarbonAccountingInventoryQueryService, InventoryQuery
from app.domain.carbon_accounting.usecases.inventory import CarbonAccountingInventoryUseCase
from app.domain.carbon_accounting.usecases.revision_export import CarbonAccountingRevisionExportUseCase
from app.domain.energy.controllers._utils import model_to_dict, ok_data

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


INVENTORY_BODY = Body()


class CarbonAccountingInventoryController(Controller):
    tags = ["Carbon Accounting"]

    @get("/api/carbon/accounting/batches")
    async def list_batches(
        self,
        db_session: AsyncSession,
        boundary_id: int | None = None,
        reporting_org_id: int | None = None,
        period_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonAccountingInventoryQueryService(db_session).batches(
            _query(boundary_id=boundary_id, reporting_org_id=reporting_org_id, period_id=period_id, status=status, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/accounting/batches")
    async def create_batch(self, db_session: AsyncSession, data: dict = INVENTORY_BODY) -> Response[dict]:
        try:
            obj = await CarbonAccountingInventoryUseCase(db_session).create_batch(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @post("/api/carbon/accounting/batches/{batch_id:int}/rebuild-inventory")
    async def rebuild_inventory(self, db_session: AsyncSession, batch_id: int) -> Response[dict]:
        try:
            obj = await CarbonAccountingInventoryUseCase(db_session).rebuild_inventory(batch_id)
            summary = await CarbonAccountingInventoryQueryService(db_session).inventory_summary(obj.id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(summary))

    @patch("/api/carbon/accounting/batches/{batch_id:int}/lock")
    async def lock_batch(self, db_session: AsyncSession, batch_id: int) -> Response[dict]:
        try:
            obj = await CarbonAccountingInventoryUseCase(db_session).lock_batch(batch_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @post("/api/carbon/accounting/batches/{batch_id:int}/create-revision")
    async def create_revision(self, db_session: AsyncSession, batch_id: int, data: dict = INVENTORY_BODY) -> Response[dict]:
        try:
            obj = await CarbonAccountingInventoryUseCase(db_session).create_revision(batch_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @post("/api/carbon/accounting/batches/{batch_id:int}/submit-revision")
    async def submit_revision(self, db_session: AsyncSession, batch_id: int) -> Response[dict]:
        try:
            obj = await CarbonAccountingInventoryUseCase(db_session).submit_revision(batch_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @post("/api/carbon/accounting/batches/{batch_id:int}/approve-revision")
    async def approve_revision(self, db_session: AsyncSession, batch_id: int) -> Response[dict]:
        try:
            obj = await CarbonAccountingInventoryUseCase(db_session).approve_revision(batch_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @post("/api/carbon/accounting/batches/{batch_id:int}/reject-revision")
    async def reject_revision(self, db_session: AsyncSession, batch_id: int, data: dict = INVENTORY_BODY) -> Response[dict]:
        try:
            obj = await CarbonAccountingInventoryUseCase(db_session).reject_revision(batch_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/accounting/batches/{batch_id:int}/summary")
    async def get_inventory_summary(self, db_session: AsyncSession, batch_id: int) -> Response[dict]:
        try:
            data = await CarbonAccountingInventoryQueryService(db_session).inventory_summary(batch_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(data))

    @get("/api/carbon/accounting/batches/{batch_id:int}/revision-diff")
    async def get_revision_diff(self, db_session: AsyncSession, batch_id: int) -> Response[dict]:
        try:
            data = await CarbonAccountingInventoryQueryService(db_session).revision_diff(batch_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(data))

    @post("/api/carbon/accounting/batches/{batch_id:int}/export-revision-explanation")
    async def export_revision_explanation(self, db_session: AsyncSession, batch_id: int) -> File | Response[dict]:
        try:
            exported = await CarbonAccountingRevisionExportUseCase(db_session).export_revision_explanation(batch_id)
        except ValueError as exc:
            return _error(exc)
        return File(path=exported.path, filename=exported.filename, media_type="application/zip")

    @get("/api/carbon/accounting/inventories")
    async def list_inventory_items(
        self,
        db_session: AsyncSession,
        batch_id: int | None = None,
        scope: str | None = None,
        quality_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonAccountingInventoryQueryService(db_session).inventory_items(
            _query(batch_id=batch_id, scope=scope, quality_status=quality_status, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))


def _query(
    *,
    batch_id: int | None = None,
    boundary_id: int | None = None,
    reporting_org_id: int | None = None,
    period_id: int | None = None,
    scope: str | None = None,
    status: str | None = None,
    quality_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> InventoryQuery:
    return InventoryQuery(
        batch_id=batch_id,
        boundary_id=boundary_id,
        reporting_org_id=reporting_org_id,
        period_id=period_id,
        scope=scope,
        status=status,
        quality_status=quality_status,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
    )


def _error(exc: ValueError) -> Response[dict]:
    message = str(exc)
    status_code = 404 if "不存在" in message else 400
    return Response(content={"code": status_code, "msg": message}, status_code=status_code)
