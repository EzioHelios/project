from __future__ import annotations

import datetime
from datetime import UTC, date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.product_footprint.domain.policies import (
    inventory_calc_status,
    result_status,
    validate_allocation_payload,
    validate_boundary_type,
    validate_inventory_payload,
    validate_period_range,
    validate_stage_payload,
    validate_study_payload,
    validate_study_status,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


STUDY_FIELDS = {
    "study_code",
    "study_name",
    "product_id",
    "product_code",
    "product_name",
    "product_spec",
    "product_category",
    "standard_code",
    "standard_name",
    "pcr_code",
    "functional_unit",
    "declared_unit",
    "period_start",
    "period_end",
    "boundary_type",
    "status",
    "source_name",
    "confidence_level",
    "remark",
}
BOUNDARY_FIELDS = {
    "study_id",
    "boundary_type",
    "included_stages",
    "excluded_stages",
    "cutoff_rule",
    "geography",
    "technology_scope",
    "temporal_scope",
    "assumption",
    "standard_code",
    "source_name",
}
STAGE_FIELDS = {"study_id", "stage_code", "stage_name", "sequence", "included", "description"}
INVENTORY_FIELDS = {
    "study_id",
    "stage_id",
    "item_no",
    "activity_type",
    "item_name",
    "activity_amount",
    "activity_unit",
    "factor_id",
    "factor_value",
    "factor_unit",
    "factor_source",
    "supplier_pcf_value",
    "supplier_pcf_unit",
    "supplier_name",
    "allocation_ratio",
    "data_quality",
    "source_type",
    "source_ref",
    "evidence_path",
    "included",
    "remark",
}
ALLOCATION_FIELDS = {
    "study_id",
    "process_code",
    "process_name",
    "allocation_method",
    "basis",
    "ratio",
    "source_name",
    "remark",
}
DATE_FIELDS = {"period_start", "period_end"}
DECIMAL_FIELDS = {"activity_amount", "factor_value", "supplier_pcf_value", "allocation_ratio", "ratio"}
INTEGER_FIELDS = {"product_id", "study_id", "stage_id", "factor_id", "sequence"}
BOOLEAN_FIELDS = {"included"}
SUPPLIER_IMPORT_FIELDS = {"supplier_data_id", "stage_id", "item_no", "allocation_ratio", "included"}
SUPPLIER_SOURCE_TYPE = "supplier_chain"


class ProductFootprintUseCase:
    """Application workflows for product carbon footprint commands."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_study(self, data: dict[str, Any]) -> m.ProductFootprintStudy:
        payload = _payload(data, STUDY_FIELDS, required={"study_code", "study_name", "product_code", "period_start", "period_end"})
        payload.setdefault("standard_code", "ISO 14067")
        payload.setdefault("status", "draft")
        payload.setdefault("boundary_type", "cradle_to_gate")
        await self._hydrate_product(payload)
        validate_study_payload(payload)
        obj = m.ProductFootprintStudy(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_study(self, study_id: int, data: dict[str, Any]) -> m.ProductFootprintStudy:
        obj = await self._get_or_raise(m.ProductFootprintStudy, study_id, "产品碳足迹研究不存在")
        payload = _payload(data, STUDY_FIELDS - {"study_code"})
        if "product_id" in payload or "product_code" in payload:
            await self._hydrate_product(payload)
        period_start = payload.get("period_start", obj.period_start)
        period_end = payload.get("period_end", obj.period_end)
        validate_period_range(period_start, period_end)
        if "status" in payload:
            validate_study_status(str(payload["status"]))
        if "boundary_type" in payload:
            validate_boundary_type(str(payload["boundary_type"]))
        if not payload.get("functional_unit", obj.functional_unit) and not payload.get("declared_unit", obj.declared_unit):
            msg = "functional_unit or declared_unit is required"
            raise ValueError(msg)
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def upsert_boundary(self, study_id: int, data: dict[str, Any]) -> m.ProductSystemBoundary:
        await self._get_or_raise(m.ProductFootprintStudy, study_id, "产品碳足迹研究不存在")
        payload = _payload({**data, "study_id": study_id}, BOUNDARY_FIELDS, required={"study_id"})
        payload.setdefault("boundary_type", "cradle_to_gate")
        validate_boundary_type(str(payload["boundary_type"]))
        obj = await self._session.scalar(select(m.ProductSystemBoundary).where(m.ProductSystemBoundary.study_id == study_id))
        if obj is None:
            obj = m.ProductSystemBoundary(**payload)
            self._session.add(obj)
        else:
            _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def create_stage(self, data: dict[str, Any]) -> m.ProductLifeCycleStage:
        payload = _payload(data, STAGE_FIELDS, required={"study_id", "stage_code", "stage_name"})
        await self._get_or_raise(m.ProductFootprintStudy, int(payload["study_id"]), "产品碳足迹研究不存在")
        validate_stage_payload(payload)
        obj = m.ProductLifeCycleStage(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_stage(self, stage_id: int, data: dict[str, Any]) -> m.ProductLifeCycleStage:
        obj = await self._get_or_raise(m.ProductLifeCycleStage, stage_id, "生命周期阶段不存在")
        payload = _payload(data, STAGE_FIELDS - {"study_id"})
        next_payload = {**{key: getattr(obj, key) for key in STAGE_FIELDS if hasattr(obj, key)}, **payload}
        validate_stage_payload(next_payload)
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def delete_stage(self, stage_id: int) -> None:
        obj = await self._get_or_raise(m.ProductLifeCycleStage, stage_id, "生命周期阶段不存在")
        await self._session.delete(obj)
        await self._session.commit()

    async def create_inventory_item(self, data: dict[str, Any]) -> m.ProductFootprintInventoryItem:
        if data.get("source_type") == "material_allocation":
            msg = "请通过物资分摊引用入口维护"
            raise ValueError(msg)
        payload = _payload(data, INVENTORY_FIELDS, required={"study_id", "item_no", "activity_type", "item_name"})
        await self._validate_inventory_refs(payload)
        validate_inventory_payload(payload)
        await self._hydrate_factor(payload)
        payload["calc_status"] = inventory_calc_status(payload)
        payload["computed_co2e"] = _compute_item_co2e(payload)
        obj = m.ProductFootprintInventoryItem(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def import_supplier_data(self, study_id: int, data: dict[str, Any]) -> m.ProductFootprintInventoryItem:
        study = await self._get_or_raise(m.ProductFootprintStudy, study_id, "产品碳足迹研究不存在")
        payload = _payload(data, SUPPLIER_IMPORT_FIELDS, required={"supplier_data_id"})
        supplier_data = await self._get_or_raise(m.SupplierCarbonData, int(payload["supplier_data_id"]), "供应商碳数据不存在")
        task = await self._get_or_raise(m.SupplierDisclosureTask, supplier_data.task_id, "供应商填报任务不存在")
        if task.status != "approved" or supplier_data.status != "approved" or not supplier_data.verified:
            msg = "只能引用已审核通过的供应商数据"
            raise ValueError(msg)
        if supplier_data.pcf_value in (None, ""):
            msg = "供应商数据缺少PCF值"
            raise ValueError(msg)
        if not _period_overlaps(study.period_start, study.period_end, supplier_data.validity_start, supplier_data.validity_end):
            msg = "供应商数据有效期不覆盖研究周期"
            raise ValueError(msg)
        source_ref = f"supplier_carbon_data:{supplier_data.id}"
        obj = await self._session.scalar(
            select(m.ProductFootprintInventoryItem).where(
                m.ProductFootprintInventoryItem.study_id == study_id,
                m.ProductFootprintInventoryItem.source_type == SUPPLIER_SOURCE_TYPE,
                m.ProductFootprintInventoryItem.source_ref == source_ref,
            )
        )
        supplier = await self._get_or_raise(m.SupplyChainSupplier, supplier_data.supplier_id, "供应商不存在")
        item_payload = {
            "study_id": study_id,
            "stage_id": payload.get("stage_id"),
            "item_no": payload.get("item_no") or (obj.item_no if obj is not None else await self._next_supplier_item_no(study_id, supplier_data.id)),
            "activity_type": "supplier_pcf",
            "item_name": supplier_data.product_name
            or supplier_data.material_name
            or task.product_name
            or supplier_data.data_no,
            "activity_amount": supplier_data.activity_amount,
            "activity_unit": supplier_data.activity_unit,
            "supplier_pcf_value": supplier_data.pcf_value,
            "supplier_pcf_unit": supplier_data.pcf_unit or "kgCO2e",
            "supplier_name": supplier.name,
            "allocation_ratio": payload.get("allocation_ratio") or Decimal(1),
            "data_quality": supplier_data.data_quality or "supplier_reported",
            "source_type": SUPPLIER_SOURCE_TYPE,
            "source_ref": source_ref,
            "included": payload.get("included", True),
            "remark": f"供应链审核数据引用: {task.task_no}/{supplier_data.data_no}",
        }
        await self._validate_inventory_refs(item_payload)
        validate_inventory_payload(item_payload)
        item_payload["calc_status"] = inventory_calc_status(item_payload)
        item_payload["computed_co2e"] = _compute_item_co2e(item_payload)
        if obj is None:
            obj = m.ProductFootprintInventoryItem(**item_payload)
            self._session.add(obj)
        else:
            _assign(obj, item_payload)
        supplier_data.published_to_pcf = True
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_inventory_item(self, item_id: int, data: dict[str, Any]) -> m.ProductFootprintInventoryItem:
        obj = await self._get_or_raise(m.ProductFootprintInventoryItem, item_id, "活动数据不存在")
        if obj.source_type == "material_allocation" or data.get("source_type") == "material_allocation":
            msg = "派生清单请在物资作业中修改后同步引用"
            raise ValueError(msg)
        payload = _payload(data, INVENTORY_FIELDS - {"study_id", "item_no"})
        next_payload = {**{key: getattr(obj, key) for key in INVENTORY_FIELDS if hasattr(obj, key)}, **payload}
        await self._validate_inventory_refs(next_payload)
        validate_inventory_payload(next_payload)
        await self._hydrate_factor(next_payload)
        next_payload["calc_status"] = inventory_calc_status(next_payload)
        next_payload["computed_co2e"] = _compute_item_co2e(next_payload)
        _assign(obj, {key: next_payload[key] for key in next_payload if key in (INVENTORY_FIELDS | {"calc_status", "computed_co2e"})})
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def delete_inventory_item(self, item_id: int) -> None:
        obj = await self._get_or_raise(m.ProductFootprintInventoryItem, item_id, "活动数据不存在")
        if obj.source_type == "material_allocation":
            msg = "请使用取消物资分摊引用操作"
            raise ValueError(msg)
        await self._session.delete(obj)
        await self._session.commit()

    async def create_allocation_rule(self, data: dict[str, Any]) -> m.ProductFootprintAllocationRule:
        payload = _payload(data, ALLOCATION_FIELDS, required={"study_id", "process_name"})
        await self._get_or_raise(m.ProductFootprintStudy, int(payload["study_id"]), "产品碳足迹研究不存在")
        validate_allocation_payload(payload)
        obj = m.ProductFootprintAllocationRule(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_allocation_rule(self, rule_id: int, data: dict[str, Any]) -> m.ProductFootprintAllocationRule:
        obj = await self._get_or_raise(m.ProductFootprintAllocationRule, rule_id, "分配规则不存在")
        payload = _payload(data, ALLOCATION_FIELDS - {"study_id"})
        next_payload = {**{key: getattr(obj, key) for key in ALLOCATION_FIELDS if hasattr(obj, key)}, **payload}
        validate_allocation_payload(next_payload)
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def delete_allocation_rule(self, rule_id: int) -> None:
        obj = await self._get_or_raise(m.ProductFootprintAllocationRule, rule_id, "分配规则不存在")
        await self._session.delete(obj)
        await self._session.commit()

    async def calculate_study(self, study_id: int) -> m.ProductFootprintResult:
        from app.domain.product_footprint.usecases.material_import import MaterialResultImportUseCase

        await MaterialResultImportUseCase(self._session).validate_study(study_id)
        study = await self._get_or_raise(m.ProductFootprintStudy, study_id, "产品碳足迹研究不存在")
        boundary = await self._session.scalar(select(m.ProductSystemBoundary).where(m.ProductSystemBoundary.study_id == study_id))
        if boundary is None:
            msg = "生命周期边界不存在"
            raise ValueError(msg)
        items = (
            await self._session.execute(
                select(m.ProductFootprintInventoryItem)
                .where(m.ProductFootprintInventoryItem.study_id == study_id)
                .order_by(m.ProductFootprintInventoryItem.id)
            )
        ).scalars().all()
        stage_by_id = {
            stage.id: stage
            for stage in (
                await self._session.execute(select(m.ProductLifeCycleStage).where(m.ProductLifeCycleStage.study_id == study_id))
            ).scalars().all()
        }
        stage_totals: dict[str, dict[str, Any]] = {}
        total = Decimal(0)
        missing_count = 0
        included_count = 0
        for item in items:
            payload = {key: getattr(item, key) for key in INVENTORY_FIELDS if hasattr(item, key)}
            await self._hydrate_factor(payload)
            item.factor_value = payload.get("factor_value")
            item.factor_unit = payload.get("factor_unit")
            item.factor_source = payload.get("factor_source")
            item.calc_status = inventory_calc_status(payload)
            item.computed_co2e = _compute_item_co2e(payload)
            if not item.included:
                continue
            included_count += 1
            if item.calc_status != "ready" or item.computed_co2e is None:
                missing_count += 1
                continue
            total += item.computed_co2e
            stage = stage_by_id.get(item.stage_id) if item.stage_id else None
            stage_code = stage.stage_code if stage else "unassigned"
            stage_name = stage.stage_name if stage else "未分配阶段"
            bucket = stage_totals.setdefault(
                stage_code,
                {"stage_code": stage_code, "stage_name": stage_name, "kg_co2e": Decimal(0), "item_count": 0},
            )
            bucket["kg_co2e"] += item.computed_co2e
            bucket["item_count"] += 1
        version = await self._next_result_version(study_id)
        status = result_status(included_count, missing_count)
        stage_payload = [
            {**bucket, "kg_co2e": float(bucket["kg_co2e"])}
            for bucket in sorted(stage_totals.values(), key=lambda row: str(row["stage_code"]))
        ]
        result = m.ProductFootprintResult(
            study_id=study_id,
            result_version=version,
            total_co2e=total,
            unit="kgCO2e",
            footprint_per_declared_unit=(
                total if (study.declared_unit or study.functional_unit)
                and not any(item.included and item.source_type == "material_allocation" for item in items)
                else None
            ),
            result_status=status,
            calculated_at=_utc_now_naive(),
            inventory_count=included_count,
            missing_factor_count=missing_count,
            stage_payload=stage_payload,
            result_payload={
                "product_code": study.product_code,
                "product_name": study.product_name,
                "functional_unit": study.functional_unit,
                "declared_unit": study.declared_unit,
                "boundary_type": study.boundary_type,
            },
        )
        study.result_status = status
        if status == "calculated":
            study.status = "calculated"
        self._session.add(result)
        await self._session.commit()
        await self._session.refresh(result)
        return result

    async def _hydrate_product(self, payload: dict[str, Any]) -> None:
        product = None
        if payload.get("product_id"):
            product = await self._session.get(m.ProductionProduct, int(payload["product_id"]))
            if product is None:
                msg = "产品不存在"
                raise ValueError(msg)
        elif payload.get("product_code"):
            product = await self._session.scalar(select(m.ProductionProduct).where(m.ProductionProduct.code == payload["product_code"]))
        if product is not None:
            payload.setdefault("product_id", product.id)
            payload.setdefault("product_code", product.code)
            payload.setdefault("product_name", product.name)
            payload.setdefault("product_spec", product.spec)
            payload.setdefault("product_category", product.category)

    async def _hydrate_factor(self, payload: dict[str, Any]) -> None:
        if payload.get("factor_id") in (None, ""):
            return
        factor = await self._session.get(m.EmissionFactor, int(payload["factor_id"]))
        if factor is None:
            msg = "排放因子不存在"
            raise ValueError(msg)
        if payload.get("factor_value") in (None, ""):
            payload["factor_value"] = factor.factor_value
        if payload.get("factor_unit") in (None, ""):
            payload["factor_unit"] = factor.factor_unit
        if payload.get("factor_source") in (None, ""):
            payload["factor_source"] = factor.source

    async def _validate_inventory_refs(self, payload: dict[str, Any]) -> None:
        await self._get_or_raise(m.ProductFootprintStudy, int(payload["study_id"]), "产品碳足迹研究不存在")
        if payload.get("stage_id") not in (None, ""):
            stage = await self._get_or_raise(m.ProductLifeCycleStage, int(payload["stage_id"]), "生命周期阶段不存在")
            if stage.study_id != int(payload["study_id"]):
                msg = "生命周期阶段不属于当前研究"
                raise ValueError(msg)

    async def _next_result_version(self, study_id: int) -> int:
        current = await self._session.scalar(
            select(func.max(m.ProductFootprintResult.result_version)).where(m.ProductFootprintResult.study_id == study_id)
        )
        return int(current or 0) + 1

    async def _next_supplier_item_no(self, study_id: int, supplier_data_id: int) -> str:
        base = f"SCI-{supplier_data_id}"
        existing = set(
            (
                await self._session.execute(
                    select(m.ProductFootprintInventoryItem.item_no).where(
                        m.ProductFootprintInventoryItem.study_id == study_id,
                        m.ProductFootprintInventoryItem.item_no.like(f"{base}%"),
                    )
                )
            ).scalars()
        )
        if base not in existing:
            return base
        suffix = 2
        while f"{base}-{suffix}" in existing:
            suffix += 1
        return f"{base}-{suffix}"

    async def _get_or_raise(self, model: type[Any], item_id: int, message: str) -> Any:
        obj = await self._session.get(model, item_id)
        if obj is None:
            raise ValueError(message)
        return obj


def _payload(data: dict[str, Any], fields: set[str], required: set[str] | None = None) -> dict[str, Any]:
    payload = {key: _coerce_value(key, value) for key, value in data.items() if key in fields and value is not None}
    for key in required or set():
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)
    return payload


def _coerce_value(key: str, value: Any) -> Any:
    if value == "":
        return None
    if key in DATE_FIELDS and isinstance(value, str):
        return date.fromisoformat(value)
    if key in DECIMAL_FIELDS and value not in (None, ""):
        return Decimal(str(value))
    if key in INTEGER_FIELDS and value not in (None, ""):
        return int(value)
    if key in BOOLEAN_FIELDS and isinstance(value, str):
        return value.lower() == "true"
    return value


def _assign(obj: Any, payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        setattr(obj, key, value)


def _compute_item_co2e(payload: dict[str, Any]) -> Decimal | None:
    if payload.get("included") is False:
        return None
    ratio = payload.get("allocation_ratio") or Decimal(1)
    if payload.get("supplier_pcf_value") not in (None, ""):
        return (Decimal(str(payload["supplier_pcf_value"])) * Decimal(str(ratio))).quantize(Decimal("0.000001"))
    if payload.get("activity_amount") in (None, "") or payload.get("factor_value") in (None, ""):
        return None
    return (Decimal(str(payload["activity_amount"])) * Decimal(str(payload["factor_value"])) * Decimal(str(ratio))).quantize(Decimal("0.000001"))


def _utc_now_naive() -> datetime.datetime:
    return datetime.datetime.now(UTC).replace(tzinfo=None)


def _period_overlaps(
    study_start: date,
    study_end: date,
    validity_start: date | None,
    validity_end: date | None,
) -> bool:
    if validity_start is not None and validity_start > study_end:
        return False
    return not (validity_end is not None and validity_end < study_start)
