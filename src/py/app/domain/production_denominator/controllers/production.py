from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, Request, delete, get, patch, post
from litestar.params import Body
from litestar.response import Response

from app.db import models as m
from app.domain.accounts.guards import requires_superuser
from app.domain.admin.deps import provide_audit_log_service
from app.domain.admin.services import AuditLogService  # noqa: TC001
from app.domain.carbon import services  # noqa: TC001
from app.domain.carbon.deps import (
    provide_product_price_service,
    provide_production_output_fact_service,
    provide_production_product_service,
    provide_production_resource_binding_service,
)
from app.domain.energy.controllers._utils import model_to_dict, ok_data
from app.domain.production_denominator.controllers._utils import list_page, log_admin_data_event
from app.domain.production_denominator.policies import (
    ProductionDenominatorValidationError,
    coerce_date_fields,
    coerce_decimal_fields,
    normalize_price_type,
    normalize_product_price_payload,
    normalize_production_binding_payload,
    normalize_production_output_kind,
    normalize_production_output_payload,
    normalize_production_product_payload,
    payload_without_none,
    strip_string_fields,
    validate_amount_non_negative,
)
from app.domain.production_denominator.queries import ProductionDenominatorQueryService, ProductionOutputQuery

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


ADMIN_BODY = Body()


class ProductionDenominatorController(Controller):
    tags = ["Production Denominator"]
    dependencies = {
        "production_product_service": provide_production_product_service,
        "product_price_service": provide_product_price_service,
        "production_output_fact_service": provide_production_output_fact_service,
        "production_resource_binding_service": provide_production_resource_binding_service,
        "security_audit_service": provide_audit_log_service,
    }

    @get("/api/production/products")
    async def list_production_products(
        self,
        production_product_service: services.ProductionProductService,
        keyword: str | None = None,
        search: str | None = None,
        category: str | None = None,
        output_kind: str | None = None,
        is_enabled: bool | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if category:
            conditions.append(m.ProductionProduct.category == category)
        if output_kind and output_kind != "all":
            conditions.append(m.ProductionProduct.output_kind == normalize_production_output_kind(output_kind))
        if is_enabled is not None:
            conditions.append(m.ProductionProduct.is_enabled.is_(is_enabled))
        page = await list_page(
            production_product_service,
            m.ProductionProduct,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["code", "name", "spec", "category", "output_kind", "default_unit", "standard_unit", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/production/products", guards=[requires_superuser])
    async def create_production_product(
        self,
        request: Request[Any, Any, Any],
        production_product_service: services.ProductionProductService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        try:
            payload = normalize_production_product_payload(data)
        except ProductionDenominatorValidationError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        obj = await production_product_service.create(payload, auto_commit=True)
        await log_admin_data_event(
            security_audit_service,
            request,
            action="production.product.create",
            target_type="ProductionProduct",
            target_id=obj.id,
            target_label=obj.code,
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/production/products/{record_id:int}", guards=[requires_superuser])
    async def update_production_product(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        production_product_service: services.ProductionProductService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = await production_product_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        payload = payload_without_none(dict(data))
        strip_string_fields(payload, ["code", "name", "spec", "category", "output_kind", "default_unit", "standard_unit", "remark"])
        if ("code" in payload and not payload["code"]) or ("name" in payload and not payload["name"]):
            return Response(content={"code": 400, "msg": "产品编码和产品名称不能为空。"}, status_code=400)
        if "output_kind" in payload:
            try:
                payload["output_kind"] = normalize_production_output_kind(payload.get("output_kind"))
            except ProductionDenominatorValidationError as exc:
                return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        await production_product_service.update(item_id=record_id, data=payload, auto_commit=True)
        fresh = await production_product_service.get_one(id=record_id)
        await log_admin_data_event(
            security_audit_service,
            request,
            action="production.product.update",
            target_type="ProductionProduct",
            target_id=record_id,
            target_label=fresh.code,
            details={"updated_fields": sorted(payload.keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功", "data": model_to_dict(fresh)})

    @delete("/api/production/products/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_production_product(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        production_product_service: services.ProductionProductService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await production_product_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await production_product_service.delete(record_id, auto_commit=True)
        await log_admin_data_event(
            security_audit_service,
            request,
            action="production.product.delete",
            target_type="ProductionProduct",
            target_id=record_id,
            target_label=obj.code,
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/production/product-prices")
    async def list_product_prices(
        self,
        product_price_service: services.ProductPriceService,
        keyword: str | None = None,
        search: str | None = None,
        product_code: str | None = None,
        price_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if product_code:
            conditions.append(m.ProductPrice.product_code == product_code)
        if price_type and price_type != "all":
            conditions.append(m.ProductPrice.price_type == price_type)
        page = await list_page(
            product_price_service,
            m.ProductPrice,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["product_code", "price_type", "currency", "source_system", "source_record_id", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/production/product-prices", guards=[requires_superuser])
    async def create_product_price(
        self,
        request: Request[Any, Any, Any],
        product_price_service: services.ProductPriceService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        try:
            payload = normalize_product_price_payload(data)
        except ProductionDenominatorValidationError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        obj = await product_price_service.create(payload, auto_commit=True)
        await log_admin_data_event(
            security_audit_service,
            request,
            action="production.product-price.create",
            target_type="ProductPrice",
            target_id=obj.id,
            target_label=obj.product_code,
            details={"price_type": obj.price_type},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/production/product-prices/{record_id:int}", guards=[requires_superuser])
    async def update_product_price(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        product_price_service: services.ProductPriceService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = await product_price_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        payload = payload_without_none(dict(data))
        strip_string_fields(payload, ["product_code", "price_type", "currency", "source_system", "source_record_id", "remark"])
        coerce_date_fields(payload, ["valid_from", "valid_to"])
        coerce_decimal_fields(payload, ["price"])
        if "product_code" in payload and not payload["product_code"]:
            return Response(content={"code": 400, "msg": "产品编码不能为空。"}, status_code=400)
        try:
            if "price_type" in payload:
                payload["price_type"] = normalize_price_type(payload["price_type"])
            if "price" in payload and payload["price"] is not None:
                validate_amount_non_negative(payload["price"], "产品价格")
        except ProductionDenominatorValidationError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        await product_price_service.update(item_id=record_id, data=payload, auto_commit=True)
        fresh = await product_price_service.get_one(id=record_id)
        await log_admin_data_event(
            security_audit_service,
            request,
            action="production.product-price.update",
            target_type="ProductPrice",
            target_id=record_id,
            target_label=fresh.product_code,
            details={"updated_fields": sorted(payload.keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功", "data": model_to_dict(fresh)})

    @delete("/api/production/product-prices/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_product_price(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        product_price_service: services.ProductPriceService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await product_price_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await product_price_service.delete(record_id, auto_commit=True)
        await log_admin_data_event(
            security_audit_service,
            request,
            action="production.product-price.delete",
            target_type="ProductPrice",
            target_id=record_id,
            target_label=obj.product_code,
            details={"price_type": obj.price_type},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/production/output-facts")
    async def list_production_output_facts(
        self,
        production_output_fact_service: services.ProductionOutputFactService,
        keyword: str | None = None,
        search: str | None = None,
        product_code: str | None = None,
        output_kind: str | None = None,
        line_code: str | None = None,
        area_id: int | None = None,
        equipment_code: str | None = None,
        record_status: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "period_start",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if product_code:
            conditions.append(m.ProductionOutputFact.product_code == product_code)
        if output_kind and output_kind != "all":
            conditions.append(m.ProductionOutputFact.output_kind == normalize_production_output_kind(output_kind))
        if line_code:
            conditions.append(m.ProductionOutputFact.line_code == line_code)
        if area_id is not None:
            conditions.append(m.ProductionOutputFact.area_id == area_id)
        if equipment_code:
            conditions.append(m.ProductionOutputFact.equipment_code == equipment_code)
        if record_status and record_status != "all":
            conditions.append(m.ProductionOutputFact.record_status == record_status)
        page = await list_page(
            production_output_fact_service,
            m.ProductionOutputFact,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=[
                "source_system",
                "source_record_id",
                "production_order_no",
                "batch_no",
                "product_code",
                "product_name",
                "output_kind",
                "line_code",
                "area_name",
                "equipment_code",
                "equipment_name",
            ],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/production/output-facts", guards=[requires_superuser])
    async def create_production_output_fact(
        self,
        request: Request[Any, Any, Any],
        production_output_fact_service: services.ProductionOutputFactService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        try:
            payload = await normalize_production_output_payload(data, production_output_fact_service.repository.session)
        except ProductionDenominatorValidationError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        obj = await production_output_fact_service.create(payload, auto_commit=True)
        await log_admin_data_event(
            security_audit_service,
            request,
            action="production.output-fact.create",
            target_type="ProductionOutputFact",
            target_id=obj.id,
            target_label=obj.source_record_id,
            details={"product_code": obj.product_code, "record_status": obj.record_status},
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/production/output-facts/{record_id:int}", guards=[requires_superuser])
    async def update_production_output_fact(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        production_output_fact_service: services.ProductionOutputFactService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = await production_output_fact_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        merged = model_to_dict(obj)
        merged.update(data)
        merged.pop("id", None)
        merged.pop("created_at", None)
        merged.pop("updated_at", None)
        try:
            normalized = await normalize_production_output_payload(merged, production_output_fact_service.repository.session)
        except ProductionDenominatorValidationError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        payload = {
            key: normalized[key]
            for key in normalized
            if key in data or key in {"product_name", "product_spec", "standard_unit", "standard_qty"}
        }
        await production_output_fact_service.update(item_id=record_id, data=payload, auto_commit=True)
        fresh = await production_output_fact_service.get_one(id=record_id)
        await log_admin_data_event(
            security_audit_service,
            request,
            action="production.output-fact.update",
            target_type="ProductionOutputFact",
            target_id=record_id,
            target_label=fresh.source_record_id,
            details={"updated_fields": sorted(payload.keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功", "data": model_to_dict(fresh)})

    @delete("/api/production/output-facts/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_production_output_fact(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        production_output_fact_service: services.ProductionOutputFactService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await production_output_fact_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await production_output_fact_service.delete(record_id, auto_commit=True)
        await log_admin_data_event(
            security_audit_service,
            request,
            action="production.output-fact.delete",
            target_type="ProductionOutputFact",
            target_id=record_id,
            target_label=obj.source_record_id,
            details={"product_code": obj.product_code},
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/production/resource-bindings")
    async def list_production_resource_bindings(
        self,
        production_resource_binding_service: services.ProductionResourceBindingService,
        keyword: str | None = None,
        search: str | None = None,
        product_code: str | None = None,
        binding_type: str | None = None,
        line_code: str | None = None,
        area_id: int | None = None,
        equipment_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "id",
        sort_order: str = "desc",
    ) -> Response[dict]:
        conditions = []
        if product_code:
            conditions.append(m.ProductionResourceBinding.product_code == product_code)
        if binding_type and binding_type != "all":
            conditions.append(m.ProductionResourceBinding.binding_type == binding_type)
        if line_code:
            conditions.append(m.ProductionResourceBinding.line_code == line_code)
        if area_id is not None:
            conditions.append(m.ProductionResourceBinding.area_id == area_id)
        if equipment_id is not None:
            conditions.append(m.ProductionResourceBinding.equipment_id == equipment_id)
        page = await list_page(
            production_resource_binding_service,
            m.ProductionResourceBinding,
            limit=limit,
            offset=offset,
            search=search,
            keyword=keyword,
            search_fields=["product_code", "work_center_code", "line_code", "binding_type", "confidence_level", "remark"],
            sort_field=sort_field,
            sort_order=sort_order,
            conditions=conditions,
        )
        return Response(content=page)

    @post("/api/production/resource-bindings", guards=[requires_superuser])
    async def create_production_resource_binding(
        self,
        request: Request[Any, Any, Any],
        production_resource_binding_service: services.ProductionResourceBindingService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        try:
            payload = normalize_production_binding_payload(data)
        except ProductionDenominatorValidationError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        obj = await production_resource_binding_service.create(payload, auto_commit=True)
        await log_admin_data_event(
            security_audit_service,
            request,
            action="production.resource-binding.create",
            target_type="ProductionResourceBinding",
            target_id=obj.id,
            target_label=obj.product_code,
        )
        return Response(content={"code": 200, "msg": "创建成功", "data": model_to_dict(obj)})

    @patch("/api/production/resource-bindings/{record_id:int}", guards=[requires_superuser])
    async def update_production_resource_binding(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        production_resource_binding_service: services.ProductionResourceBindingService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = ADMIN_BODY,
    ) -> Response[dict]:
        obj = await production_resource_binding_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        payload = payload_without_none(dict(data))
        strip_string_fields(payload, ["product_code", "work_center_code", "line_code", "binding_type", "confidence_level", "remark"])
        try:
            if "binding_type" in payload:
                payload["binding_type"] = normalize_production_binding_payload({**model_to_dict(obj), **payload})["binding_type"]
        except ProductionDenominatorValidationError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        await production_resource_binding_service.update(item_id=record_id, data=payload, auto_commit=True)
        fresh = await production_resource_binding_service.get_one(id=record_id)
        await log_admin_data_event(
            security_audit_service,
            request,
            action="production.resource-binding.update",
            target_type="ProductionResourceBinding",
            target_id=record_id,
            target_label=fresh.product_code,
            details={"updated_fields": sorted(payload.keys())},
        )
        return Response(content={"code": 200, "msg": "更新成功", "data": model_to_dict(fresh)})

    @delete("/api/production/resource-bindings/{record_id:int}", guards=[requires_superuser], status_code=200)
    async def delete_production_resource_binding(
        self,
        request: Request[Any, Any, Any],
        record_id: int,
        production_resource_binding_service: services.ProductionResourceBindingService,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        obj = await production_resource_binding_service.get_one_or_none(id=record_id)
        if not obj:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        await production_resource_binding_service.delete(record_id, auto_commit=True)
        await log_admin_data_event(
            security_audit_service,
            request,
            action="production.resource-binding.delete",
            target_type="ProductionResourceBinding",
            target_id=record_id,
            target_label=obj.product_code,
        )
        return Response(content={"code": 200, "msg": "已删除"})

    @get("/api/production/output/summary")
    async def get_production_output_summary(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "month",
        product_code: str | None = None,
        category: str | None = None,
        output_kind: str | None = None,
        line_code: str | None = None,
        area_id: str | None = None,
        equipment_code: str | None = None,
        record_status: str | None = "confirmed",
    ) -> Response[dict]:
        data = await ProductionDenominatorQueryService(db_session).summary(
            ProductionOutputQuery(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                product_code=product_code,
                category=category,
                output_kind=output_kind,
                line_code=line_code,
                area_id=area_id,
                equipment_code=equipment_code,
                record_status=record_status,
            )
        )
        return Response(content=ok_data(data))
