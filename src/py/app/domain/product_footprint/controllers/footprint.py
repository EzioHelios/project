from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, delete, get, patch, post
from litestar.params import Body
from litestar.response import File, Response

from app.domain.accounts.guards import requires_permission
from app.domain.energy.controllers._utils import model_to_dict, ok_data
from app.domain.material_allocation.schemas import MaterialResultImport  # noqa: TC001
from app.domain.product_footprint.queries.footprint import (
    ProductFootprintQuery,
    ProductFootprintQueryService,
)
from app.domain.product_footprint.usecases.footprint import ProductFootprintUseCase
from app.domain.product_footprint.usecases.material_import import MaterialResultImportUseCase
from app.domain.product_footprint.usecases.report_export import ProductFootprintReportExportUseCase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


FOOTPRINT_BODY = Body()


class ProductFootprintController(Controller):
    tags = ["Product Footprint"]

    @post("/api/carbon/product-footprint/studies/{study_id:int}/material-results", guards=[requires_permission("product_footprint:write")])
    async def import_material(self, db_session: AsyncSession, study_id: int, data: MaterialResultImport) -> Response[dict]:
        try:
            item = await MaterialResultImportUseCase(db_session).import_result(study_id, data.result_id, data.stage_id)
            await db_session.commit()
            return Response(content=ok_data(model_to_dict(item)))
        except ValueError as exc:
            await db_session.rollback()
            return Response(content={"msg":str(exc)}, status_code=400)

    @delete("/api/carbon/product-footprint/material-references/{item_id:int}", status_code=200, guards=[requires_permission("product_footprint:write")])
    async def unlink_material(self, db_session: AsyncSession, item_id: int) -> Response[dict]:
        await MaterialResultImportUseCase(db_session).unlink(item_id)
        await db_session.commit()
        return Response(content=ok_data({"deleted":True}))

    @get("/api/carbon/product-footprint/summary")
    async def get_summary(self, db_session: AsyncSession) -> Response[dict]:
        data = await ProductFootprintQueryService(db_session).summary()
        return Response(content=ok_data(data))

    @get("/api/carbon/product-footprint/source-readiness")
    async def get_source_readiness(self, db_session: AsyncSession) -> Response[dict]:
        data = await ProductFootprintQueryService(db_session).source_readiness()
        return Response(content=ok_data(data))

    @get("/api/carbon/product-footprint/studies")
    async def list_studies(
        self,
        db_session: AsyncSession,
        status: str | None = None,
        result_status: str | None = None,
        product_code: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await ProductFootprintQueryService(db_session).studies(
            _query(status=status, result_status=result_status, product_code=product_code, keyword=keyword, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/product-footprint/studies")
    async def create_study(self, db_session: AsyncSession, data: dict = FOOTPRINT_BODY) -> Response[dict]:
        try:
            obj = await ProductFootprintUseCase(db_session).create_study(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/product-footprint/studies/{study_id:int}")
    async def update_study(self, db_session: AsyncSession, study_id: int, data: dict = FOOTPRINT_BODY) -> Response[dict]:
        try:
            obj = await ProductFootprintUseCase(db_session).update_study(study_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/product-footprint/studies/{study_id:int}/boundary")
    async def get_boundary(self, db_session: AsyncSession, study_id: int) -> Response[dict]:
        data = await ProductFootprintQueryService(db_session).boundary(study_id)
        return Response(content=ok_data(data or {}))

    @patch("/api/carbon/product-footprint/studies/{study_id:int}/boundary")
    async def upsert_boundary(self, db_session: AsyncSession, study_id: int, data: dict = FOOTPRINT_BODY) -> Response[dict]:
        try:
            obj = await ProductFootprintUseCase(db_session).upsert_boundary(study_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/product-footprint/stages")
    async def list_stages(self, db_session: AsyncSession, study_id: int | None = None, limit: int = 50, offset: int = 0) -> Response[dict]:
        data = await ProductFootprintQueryService(db_session).stages(_query(study_id=study_id, limit=limit, offset=offset))
        return Response(content=ok_data(data))

    @post("/api/carbon/product-footprint/stages")
    async def create_stage(self, db_session: AsyncSession, data: dict = FOOTPRINT_BODY) -> Response[dict]:
        try:
            obj = await ProductFootprintUseCase(db_session).create_stage(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/product-footprint/stages/{stage_id:int}")
    async def update_stage(self, db_session: AsyncSession, stage_id: int, data: dict = FOOTPRINT_BODY) -> Response[dict]:
        try:
            obj = await ProductFootprintUseCase(db_session).update_stage(stage_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @delete("/api/carbon/product-footprint/stages/{stage_id:int}", status_code=200)
    async def delete_stage(self, db_session: AsyncSession, stage_id: int) -> Response[dict]:
        try:
            await ProductFootprintUseCase(db_session).delete_stage(stage_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data({"deleted": True}))

    @get("/api/carbon/product-footprint/inventory-items")
    async def list_inventory_items(
        self,
        db_session: AsyncSession,
        study_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await ProductFootprintQueryService(db_session).inventory_items(_query(study_id=study_id, limit=limit, offset=offset))
        return Response(content=ok_data(data))

    @post("/api/carbon/product-footprint/inventory-items")
    async def create_inventory_item(self, db_session: AsyncSession, data: dict = FOOTPRINT_BODY) -> Response[dict]:
        try:
            obj = await ProductFootprintUseCase(db_session).create_inventory_item(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/product-footprint/inventory-items/{item_id:int}")
    async def update_inventory_item(self, db_session: AsyncSession, item_id: int, data: dict = FOOTPRINT_BODY) -> Response[dict]:
        try:
            obj = await ProductFootprintUseCase(db_session).update_inventory_item(item_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @delete("/api/carbon/product-footprint/inventory-items/{item_id:int}", status_code=200)
    async def delete_inventory_item(self, db_session: AsyncSession, item_id: int) -> Response[dict]:
        try:
            await ProductFootprintUseCase(db_session).delete_inventory_item(item_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data({"deleted": True}))

    @get("/api/carbon/product-footprint/studies/{study_id:int}/supplier-data-candidates")
    async def list_supplier_data_candidates(
        self,
        db_session: AsyncSession,
        study_id: int,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await ProductFootprintQueryService(db_session).supplier_data_candidates(
            study_id,
            _query(keyword=keyword, limit=limit, offset=offset),
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/product-footprint/studies/{study_id:int}/import-supplier-data")
    async def import_supplier_data(self, db_session: AsyncSession, study_id: int, data: dict = FOOTPRINT_BODY) -> Response[dict]:
        try:
            obj = await ProductFootprintUseCase(db_session).import_supplier_data(study_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/product-footprint/allocation-rules")
    async def list_allocation_rules(
        self,
        db_session: AsyncSession,
        study_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await ProductFootprintQueryService(db_session).allocation_rules(_query(study_id=study_id, limit=limit, offset=offset))
        return Response(content=ok_data(data))

    @post("/api/carbon/product-footprint/allocation-rules")
    async def create_allocation_rule(self, db_session: AsyncSession, data: dict = FOOTPRINT_BODY) -> Response[dict]:
        try:
            obj = await ProductFootprintUseCase(db_session).create_allocation_rule(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/product-footprint/allocation-rules/{rule_id:int}")
    async def update_allocation_rule(self, db_session: AsyncSession, rule_id: int, data: dict = FOOTPRINT_BODY) -> Response[dict]:
        try:
            obj = await ProductFootprintUseCase(db_session).update_allocation_rule(rule_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @delete("/api/carbon/product-footprint/allocation-rules/{rule_id:int}", status_code=200)
    async def delete_allocation_rule(self, db_session: AsyncSession, rule_id: int) -> Response[dict]:
        try:
            await ProductFootprintUseCase(db_session).delete_allocation_rule(rule_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data({"deleted": True}))

    @post("/api/carbon/product-footprint/studies/{study_id:int}/calculate")
    async def calculate_study(self, db_session: AsyncSession, study_id: int) -> Response[dict]:
        try:
            obj = await ProductFootprintUseCase(db_session).calculate_study(study_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/product-footprint/results")
    async def list_results(
        self,
        db_session: AsyncSession,
        study_id: int | None = None,
        result_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await ProductFootprintQueryService(db_session).results(
            _query(study_id=study_id, result_status=result_status, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/product-footprint/studies/{study_id:int}/report")
    async def get_report(self, db_session: AsyncSession, study_id: int) -> Response[dict]:
        data = await ProductFootprintQueryService(db_session).report(study_id)
        status_code = 404 if not data else 200
        if not data:
            return Response(content={"code": 404, "msg": "产品碳足迹研究不存在"}, status_code=status_code)
        return Response(content=ok_data(data))

    @post("/api/carbon/product-footprint/studies/{study_id:int}/export-report")
    async def export_report(self, db_session: AsyncSession, study_id: int) -> File | Response[dict]:
        try:
            exported = await ProductFootprintReportExportUseCase(db_session).export_report(study_id)
        except ValueError as exc:
            return _error(exc)
        return File(path=exported.path, filename=exported.filename, media_type="application/zip")


def _query(
    *,
    study_id: int | None = None,
    status: str | None = None,
    result_status: str | None = None,
    product_code: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ProductFootprintQuery:
    return ProductFootprintQuery(
        study_id=study_id,
        status=status,
        result_status=result_status,
        product_code=product_code,
        keyword=keyword,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
    )


def _error(exc: ValueError) -> Response[dict]:
    message = str(exc)
    status_code = 404 if "不存在" in message else 400
    return Response(content={"code": status_code, "msg": message}, status_code=status_code)
