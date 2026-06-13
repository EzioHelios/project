from __future__ import annotations

import datetime
from datetime import UTC, date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.db import models as m
from app.domain.supply_chain_carbon.domain.policies import (
    data_status_for_task,
    ensure_task_transition,
    validate_carbon_data,
    validate_evidence,
    validate_period,
    validate_site,
    validate_supplier,
    validate_task,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


SUPPLIER_FIELDS = {
    "supplier_code",
    "name",
    "industry",
    "supplier_type",
    "contact_name",
    "contact_email",
    "country_region",
    "status",
    "risk_level",
    "source_name",
    "standard_code",
    "remark",
}
SITE_FIELDS = {"supplier_id", "site_code", "site_name", "country_region", "address", "facility_scope", "status", "remark"}
TASK_FIELDS = {
    "task_no",
    "task_name",
    "supplier_id",
    "task_type",
    "product_id",
    "product_code",
    "product_name",
    "period_start",
    "period_end",
    "due_date",
    "status",
    "requested_by",
    "standard_code",
    "source_name",
    "confidence_level",
    "remark",
}
DATA_FIELDS = {
    "task_id",
    "data_no",
    "data_type",
    "scope_category",
    "product_id",
    "product_code",
    "product_name",
    "material_code",
    "material_name",
    "activity_amount",
    "activity_unit",
    "pcf_value",
    "pcf_unit",
    "co2e_amount",
    "factor_source",
    "boundary_type",
    "data_quality",
    "verified",
    "validity_start",
    "validity_end",
    "source_type",
    "source_ref",
    "status",
    "published_to_scope3",
    "published_to_pcf",
    "remark",
}
EVIDENCE_FIELDS = {
    "task_id",
    "evidence_no",
    "evidence_type",
    "file_name",
    "file_path",
    "file_sha256",
    "file_size_bytes",
    "review_status",
    "submitted_by",
    "remark",
}
RELEASE_FIELDS = {"release_no", "task_id", "release_type", "recipient_name", "status", "payload", "remark"}
DATE_FIELDS = {"period_start", "period_end", "due_date", "validity_start", "validity_end"}
DECIMAL_FIELDS = {"activity_amount", "pcf_value", "co2e_amount"}
INTEGER_FIELDS = {"supplier_id", "task_id", "product_id", "file_size_bytes"}
BOOLEAN_FIELDS = {"verified", "published_to_scope3", "published_to_pcf"}


class SupplyChainCarbonUseCase:
    """Application workflows for supply-chain carbon commands."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_supplier(self, data: dict[str, Any]) -> m.SupplyChainSupplier:
        payload = _payload(data, SUPPLIER_FIELDS, required={"supplier_code", "name"})
        payload.setdefault("status", "active")
        payload.setdefault("risk_level", "medium")
        validate_supplier(payload)
        obj = m.SupplyChainSupplier(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_supplier(self, supplier_id: int, data: dict[str, Any]) -> m.SupplyChainSupplier:
        obj = await self._get_or_raise(m.SupplyChainSupplier, supplier_id, "供应商不存在")
        payload = _payload(data, SUPPLIER_FIELDS - {"supplier_code"})
        next_payload = {**{key: getattr(obj, key) for key in SUPPLIER_FIELDS if hasattr(obj, key)}, **payload}
        validate_supplier(next_payload)
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def create_site(self, data: dict[str, Any]) -> m.SupplierSite:
        payload = _payload(data, SITE_FIELDS, required={"supplier_id", "site_code", "site_name"})
        await self._get_or_raise(m.SupplyChainSupplier, int(payload["supplier_id"]), "供应商不存在")
        validate_site(payload)
        obj = m.SupplierSite(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_site(self, site_id: int, data: dict[str, Any]) -> m.SupplierSite:
        obj = await self._get_or_raise(m.SupplierSite, site_id, "供应商场站不存在")
        payload = _payload(data, SITE_FIELDS - {"supplier_id"})
        next_payload = {**{key: getattr(obj, key) for key in SITE_FIELDS if hasattr(obj, key)}, **payload}
        validate_site(next_payload)
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def create_task(self, data: dict[str, Any]) -> m.SupplierDisclosureTask:
        payload = _payload(data, TASK_FIELDS, required={"task_no", "task_name", "supplier_id", "period_start", "period_end"})
        await self._get_or_raise(m.SupplyChainSupplier, int(payload["supplier_id"]), "供应商不存在")
        payload.setdefault("task_type", "mixed")
        payload.setdefault("status", "draft")
        await self._hydrate_product(payload)
        validate_task(payload)
        obj = m.SupplierDisclosureTask(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_task(self, task_id: int, data: dict[str, Any]) -> m.SupplierDisclosureTask:
        obj = await self._get_or_raise(m.SupplierDisclosureTask, task_id, "填报任务不存在")
        if obj.status == "approved":
            msg = "已审核通过任务不可直接修改"
            raise ValueError(msg)
        payload = _payload(data, TASK_FIELDS - {"task_no", "supplier_id", "status"})
        await self._hydrate_product(payload)
        period_start = payload.get("period_start", obj.period_start)
        period_end = payload.get("period_end", obj.period_end)
        validate_period(period_start, period_end)
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def decide_task(self, task_id: int, decision: str, data: dict[str, Any] | None = None) -> m.SupplierDisclosureTask:
        payload = data or {}
        obj = await self._get_or_raise(m.SupplierDisclosureTask, task_id, "填报任务不存在")
        reason = str(payload.get("reason") or "").strip() or None
        next_status = ensure_task_transition(obj.status, decision, reason=reason)
        obj.status = next_status
        now = _utc_now_naive()
        if decision == "submit":
            obj.submitted_at = now
        elif decision == "approve":
            obj.approved_at = now
            await self._sync_data_after_review(obj, next_status)
            await self._sync_evidence_after_review(obj, "accepted")
        elif decision == "reject":
            obj.rejected_at = now
            await self._sync_data_after_review(obj, next_status)
            await self._sync_evidence_after_review(obj, "rejected")
        elif decision == "request_revision":
            await self._sync_data_after_review(obj, next_status)
        self._session.add(
            m.SupplierReviewDecision(
                task_id=obj.id,
                decision=decision,
                reason=reason,
                reviewed_by=payload.get("reviewed_by"),
                decided_at=now,
            )
        )
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def create_carbon_data(self, task_id: int, data: dict[str, Any]) -> m.SupplierCarbonData:
        task = await self._get_or_raise(m.SupplierDisclosureTask, task_id, "填报任务不存在")
        if task.status == "approved":
            msg = "已审核通过任务不可新增数据"
            raise ValueError(msg)
        payload = _payload({**data, "task_id": task_id}, DATA_FIELDS, required={"task_id", "data_no", "data_type"})
        payload["supplier_id"] = task.supplier_id
        await self._hydrate_product(payload, task=task)
        payload.setdefault("status", data_status_for_task(task.status))
        payload.setdefault("verified", False)
        validate_carbon_data(payload)
        obj = m.SupplierCarbonData(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_carbon_data(self, data_id: int, data: dict[str, Any]) -> m.SupplierCarbonData:
        obj = await self._get_or_raise(m.SupplierCarbonData, data_id, "供应商碳数据不存在")
        task = await self._get_or_raise(m.SupplierDisclosureTask, obj.task_id, "填报任务不存在")
        if task.status == "approved":
            msg = "已审核通过任务不可修改数据"
            raise ValueError(msg)
        payload = _payload(data, DATA_FIELDS - {"task_id", "supplier_id", "data_no", "verified", "status"})
        next_payload = {**{key: getattr(obj, key) for key in DATA_FIELDS if hasattr(obj, key)}, **payload}
        await self._hydrate_product(next_payload, task=task)
        validate_carbon_data(next_payload)
        _assign(obj, payload)
        obj.status = data_status_for_task(task.status)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def create_evidence(self, task_id: int, data: dict[str, Any]) -> m.SupplierEvidence:
        task = await self._get_or_raise(m.SupplierDisclosureTask, task_id, "填报任务不存在")
        if task.status == "approved":
            msg = "已审核通过任务不可新增证据"
            raise ValueError(msg)
        payload = _payload({**data, "task_id": task_id}, EVIDENCE_FIELDS, required={"task_id", "evidence_no", "evidence_type", "file_name"})
        payload.setdefault("review_status", "pending")
        validate_evidence(payload)
        obj = m.SupplierEvidence(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def create_release(self, task_id: int, data: dict[str, Any]) -> m.SupplierDisclosureRelease:
        task = await self._get_or_raise(m.SupplierDisclosureTask, task_id, "填报任务不存在")
        if task.status != "approved":
            msg = "只有已审核通过任务可以生成披露记录"
            raise ValueError(msg)
        payload = _payload({**data, "task_id": task_id}, RELEASE_FIELDS, required={"release_no", "task_id"})
        payload.setdefault("release_type", "customer_disclosure")
        payload.setdefault("status", "released")
        if payload["status"] == "released":
            payload["released_at"] = _utc_now_naive()
        if not payload.get("payload"):
            payload["payload"] = await self._release_payload(task_id)
        obj = m.SupplierDisclosureRelease(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def _sync_data_after_review(self, task: m.SupplierDisclosureTask, task_status: str) -> None:
        rows = (
            await self._session.execute(select(m.SupplierCarbonData).where(m.SupplierCarbonData.task_id == task.id))
        ).scalars().all()
        status = data_status_for_task(task_status)
        for row in rows:
            row.status = status
            row.verified = task_status == "approved"

    async def _sync_evidence_after_review(self, task: m.SupplierDisclosureTask, review_status: str) -> None:
        rows = (
            await self._session.execute(select(m.SupplierEvidence).where(m.SupplierEvidence.task_id == task.id))
        ).scalars().all()
        for row in rows:
            row.review_status = review_status
            row.reviewed_at = _utc_now_naive()

    async def _release_payload(self, task_id: int) -> dict[str, Any]:
        task = await self._get_or_raise(m.SupplierDisclosureTask, task_id, "填报任务不存在")
        data_items = (
            await self._session.execute(select(m.SupplierCarbonData).where(m.SupplierCarbonData.task_id == task_id))
        ).scalars().all()
        return {
            "task_no": task.task_no,
            "task_name": task.task_name,
            "supplier_id": task.supplier_id,
            "product_code": task.product_code,
            "period_start": task.period_start.isoformat(),
            "period_end": task.period_end.isoformat(),
            "data_count": len(data_items),
            "verified_count": sum(1 for item in data_items if item.verified),
        }

    async def _hydrate_product(self, payload: dict[str, Any], *, task: m.SupplierDisclosureTask | None = None) -> None:
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
        elif task is not None:
            payload.setdefault("product_id", task.product_id)
            payload.setdefault("product_code", task.product_code)
            payload.setdefault("product_name", task.product_name)

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


def _utc_now_naive() -> datetime.datetime:
    return datetime.datetime.now(UTC).replace(tzinfo=None)
