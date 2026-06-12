from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from app.db import models as m

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


PRODUCTION_BINDING_TYPES = {"primary", "optional", "shared"}
PRODUCTION_OUTPUT_KINDS = {"product", "material_storage", "material_handling", "operation_workload"}
PRODUCTION_PRICE_TYPES = {"actual_average_price", "standard_price", "base_period_price"}
PRODUCTION_RECORD_STATUSES = {"draft", "confirmed", "rejected"}


class ProductionDenominatorValidationError(ValueError):
    """Raised when production denominator payloads violate business constraints."""


def validate_amount_non_negative(value: Any, field_label: str) -> None:
    if Decimal(str(value)) < 0:
        msg = f"{field_label}不能为负数。"
        raise ProductionDenominatorValidationError(msg)


def normalize_price_type(value: str | None, default: str = "standard_price") -> str:
    price_type = (value or default).strip()
    if price_type not in PRODUCTION_PRICE_TYPES:
        msg = "价格口径必须为实际均价、标准价或基期价。"
        raise ProductionDenominatorValidationError(msg)
    return price_type


def normalize_production_record_status(value: str | None, default: str = "confirmed") -> str:
    record_status = (value or default).strip()
    if record_status not in PRODUCTION_RECORD_STATUSES:
        msg = "生产记录状态必须为 draft、confirmed 或 rejected。"
        raise ProductionDenominatorValidationError(msg)
    return record_status


def normalize_production_output_kind(value: str | None, default: str = "product") -> str:
    output_kind = (value or default).strip()
    if output_kind not in PRODUCTION_OUTPUT_KINDS:
        msg = "业务类型必须为产品产量、库存量、出入库处理量或作业量。"
        raise ProductionDenominatorValidationError(msg)
    return output_kind


def normalize_production_product_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = payload_without_none(dict(data))
    strip_string_fields(payload, ["code", "name", "spec", "category", "output_kind", "default_unit", "standard_unit", "remark"])
    if not payload.get("code") or not payload.get("name"):
        msg = "产品编码和产品名称不能为空。"
        raise ProductionDenominatorValidationError(msg)
    payload["output_kind"] = normalize_production_output_kind(payload.get("output_kind"))
    payload.setdefault("is_enabled", True)
    return payload


def normalize_product_price_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = payload_without_none(dict(data))
    strip_string_fields(payload, ["product_code", "price_type", "currency", "source_system", "source_record_id", "remark"])
    if not payload.get("product_code"):
        msg = "产品编码不能为空。"
        raise ProductionDenominatorValidationError(msg)
    payload["price_type"] = normalize_price_type(payload.get("price_type"))
    coerce_date_fields(payload, ["valid_from", "valid_to"])
    coerce_decimal_fields(payload, ["price"])
    if payload.get("price") is None:
        msg = "产品价格不能为空。"
        raise ProductionDenominatorValidationError(msg)
    validate_amount_non_negative(payload["price"], "产品价格")
    payload.setdefault("currency", "CNY")
    payload.setdefault("tax_included", False)
    payload.setdefault("valid_from", datetime.datetime.now(datetime.UTC).date())
    return payload


async def normalize_production_output_payload(data: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    payload = payload_without_none(dict(data))
    strip_string_fields(
        payload,
        [
            "source_system",
            "source_record_id",
            "production_order_no",
            "batch_no",
            "product_code",
            "product_name",
            "product_spec",
            "output_kind",
            "unit",
            "standard_unit",
            "quality_status",
            "record_status",
            "work_center_code",
            "line_code",
            "area_name",
            "equipment_code",
            "equipment_name",
            "remark",
        ],
    )
    if not payload.get("product_code"):
        msg = "产品编码不能为空。"
        raise ProductionDenominatorValidationError(msg)
    requested_output_kind = payload.get("output_kind")
    coerce_date_fields(payload, ["period_start", "period_end"])
    coerce_decimal_fields(payload, ["good_qty", "scrap_qty", "rework_qty", "standard_qty"])
    coerce_int_fields(payload, ["area_id"])
    if payload.get("period_start") is None:
        msg = "生产期间不能为空。"
        raise ProductionDenominatorValidationError(msg)
    payload.setdefault("period_end", payload.get("period_start"))
    payload.setdefault("source_system", "manual")
    payload.setdefault("source_record_id", f"manual:{uuid4().hex}")
    payload["record_status"] = normalize_production_record_status(payload.get("record_status"))
    product = await production_product_snapshot(session, payload.get("product_code"))
    if product:
        payload.setdefault("product_name", product.name)
        payload.setdefault("product_spec", product.spec)
        payload.setdefault("output_kind", product.output_kind)
        payload.setdefault("unit", product.default_unit)
        payload.setdefault("standard_unit", product.standard_unit or product.default_unit)
    payload["output_kind"] = normalize_production_output_kind(requested_output_kind or payload.get("output_kind"))
    if not payload.get("unit"):
        msg = "产量单位不能为空。"
        raise ProductionDenominatorValidationError(msg)
    payload.setdefault("standard_unit", payload.get("unit"))
    payload.setdefault("standard_qty", payload.get("good_qty"))
    payload.setdefault("scrap_qty", Decimal(0))
    payload.setdefault("rework_qty", Decimal(0))
    if payload.get("good_qty") is None:
        msg = "产量不能为空。"
        raise ProductionDenominatorValidationError(msg)
    validate_amount_non_negative(payload["good_qty"], "产量")
    validate_amount_non_negative(payload.get("standard_qty") or 0, "标准产量")
    return payload


def normalize_production_binding_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = payload_without_none(dict(data))
    strip_string_fields(payload, ["product_code", "work_center_code", "line_code", "binding_type", "confidence_level", "remark"])
    if not payload.get("product_code"):
        msg = "产品编码不能为空。"
        raise ProductionDenominatorValidationError(msg)
    binding_type = (payload.get("binding_type") or "primary").strip()
    if binding_type not in PRODUCTION_BINDING_TYPES:
        msg = "挂接类型必须为 primary、optional 或 shared。"
        raise ProductionDenominatorValidationError(msg)
    payload["binding_type"] = binding_type
    coerce_date_fields(payload, ["valid_from", "valid_to"])
    coerce_int_fields(payload, ["area_id", "equipment_id"])
    return payload


async def production_product_snapshot(session: AsyncSession, product_code: str | None) -> m.ProductionProduct | None:
    if not product_code:
        return None
    return await session.scalar(select(m.ProductionProduct).where(m.ProductionProduct.code == product_code))


def payload_without_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def strip_string_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        value = data.get(field)
        if isinstance(value, str):
            data[field] = value.strip()


def coerce_date_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        value = data.get(field)
        if isinstance(value, str) and value:
            data[field] = datetime.date.fromisoformat(value[:10])


def coerce_decimal_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        value = data.get(field)
        if value not in (None, ""):
            data[field] = Decimal(str(value))


def coerce_int_fields(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        value = data.get(field)
        if value not in (None, ""):
            data[field] = int(value)
