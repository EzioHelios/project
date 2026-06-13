from __future__ import annotations

import datetime
from datetime import UTC, date, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import delete, select

from app.db import models as m
from app.domain.carbon.controllers import (
    _record_source_kind,
    _scope_display_name,
    _scope_group_label,
    _scope_record_label,
    _scope_record_period,
    _serialize_scope_record,
)
from app.domain.carbon_accounting.domain.policies import inventory_quality, inventory_status, validate_batch_status

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


BATCH_FIELDS = {"boundary_id", "batch_no", "batch_name", "status", "standard_code", "source_name", "remark"}
STATUS_APPROVED = "approved"


class CarbonAccountingInventoryUseCase:
    """Application workflows for organization-carbon accounting inventory."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_batch(self, data: dict[str, Any]) -> m.CarbonAccountingBatch:
        payload = {key: value for key, value in data.items() if key in BATCH_FIELDS and value not in (None, "")}
        boundary_id = int(payload.get("boundary_id") or 0)
        boundary = await self._get_or_raise(m.OrganizationBoundary, boundary_id, "组织边界不存在")
        if boundary.status != "published":
            msg = "只能基于已发布组织边界创建核算批次"
            raise ValueError(msg)
        period = await self._get_or_raise(m.ReportingPeriod, boundary.period_id, "报告期不存在")
        if "status" in payload:
            validate_batch_status(str(payload["status"]))
        batch = m.CarbonAccountingBatch(
            batch_no=str(payload.get("batch_no") or _batch_no(boundary)),
            batch_name=str(payload.get("batch_name") or f"{period.name}-{boundary.boundary_name}-组织排放清单"),
            reporting_org_id=boundary.reporting_org_id,
            period_id=boundary.period_id,
            boundary_id=boundary.id,
            status=str(payload.get("status") or "draft"),
            inventory_status="empty",
            standard_code=payload.get("standard_code") or boundary.standard_code or period.standard_code,
            source_name=payload.get("source_name") or "organization_inventory",
            remark=payload.get("remark"),
        )
        self._session.add(batch)
        await self._session.commit()
        await self._session.refresh(batch)
        return batch

    async def rebuild_inventory(self, batch_id: int) -> m.CarbonAccountingBatch:
        batch = await self._get_or_raise(m.CarbonAccountingBatch, batch_id, "核算批次不存在")
        if batch.status == "locked":
            msg = "已锁定核算批次不可重建"
            raise ValueError(msg)
        boundary = await self._get_or_raise(m.OrganizationBoundary, batch.boundary_id, "组织边界不存在")
        period = await self._get_or_raise(m.ReportingPeriod, batch.period_id, "报告期不存在")
        await self._session.execute(delete(m.CarbonEmissionInventoryItem).where(m.CarbonEmissionInventoryItem.batch_id == batch.id))
        records = await self._load_period_records(period)
        facilities = await self._boundary_facilities(boundary.id)
        area_ids = {str(item.area_id) for item in facilities if item.included and item.area_id is not None}
        items: list[m.CarbonEmissionInventoryItem] = []
        total = Decimal(0)
        included_count = 0
        missing_count = 0
        for record in records:
            payload = await self._inventory_payload(record, area_ids)
            if payload["included"]:
                included_count += 1
                if payload["computed_co2e"] is None:
                    missing_count += 1
                else:
                    total += payload["computed_co2e"]
            items.append(m.CarbonEmissionInventoryItem(batch_id=batch.id, **payload))
        self._session.add_all(items)
        batch.status = "rebuilt"
        batch.inventory_status = inventory_status(missing_result_count=missing_count)
        batch.record_count = len(items)
        batch.included_record_count = included_count
        batch.missing_result_count = missing_count
        batch.total_co2e = total
        batch.inventory_payload = _inventory_payload_summary(items, total=total)
        batch.rebuilt_at = _utc_now_naive()
        await self._session.commit()
        await self._session.refresh(batch)
        return batch

    async def lock_batch(self, batch_id: int) -> m.CarbonAccountingBatch:
        batch = await self._get_or_raise(m.CarbonAccountingBatch, batch_id, "核算批次不存在")
        if batch.inventory_status == "empty":
            msg = "核算批次尚未生成清单"
            raise ValueError(msg)
        batch.status = "locked"
        batch.inventory_status = "locked"
        batch.locked_at = _utc_now_naive()
        await self._session.commit()
        await self._session.refresh(batch)
        return batch

    async def _load_period_records(self, period: m.ReportingPeriod) -> list[Any]:
        start_dt = datetime.datetime.combine(period.period_start, time.min)
        end_dt = datetime.datetime.combine(period.period_end, time.max)
        specs = [
            (m.Scope1MobileCombustion, m.Scope1MobileCombustion.record_date >= period.period_start, m.Scope1MobileCombustion.record_date <= period.period_end),
            (
                m.Scope1StationaryCombustion,
                m.Scope1StationaryCombustion.period_start <= period.period_end,
                m.Scope1StationaryCombustion.period_end >= period.period_start,
            ),
            (m.Scope1RefrigerantLeak, m.Scope1RefrigerantLeak.fill_date >= period.period_start, m.Scope1RefrigerantLeak.fill_date <= period.period_end),
            (
                m.Scope2ElectricityBill,
                m.Scope2ElectricityBill.billing_month >= _month(period.period_start),
                m.Scope2ElectricityBill.billing_month <= _month(period.period_end),
            ),
            (
                m.Scope2MeterAggregate,
                m.Scope2MeterAggregate.billing_month >= _month(period.period_start),
                m.Scope2MeterAggregate.billing_month <= _month(period.period_end),
            ),
            (
                m.Scope2PurchasedEnergy,
                m.Scope2PurchasedEnergy.period_start <= period.period_end,
                m.Scope2PurchasedEnergy.period_end >= period.period_start,
            ),
            (m.Scope3WasteDisposal, m.Scope3WasteDisposal.date >= period.period_start, m.Scope3WasteDisposal.date <= period.period_end),
            (m.Scope3ThirdPartyTransport, m.Scope3ThirdPartyTransport.created_at >= start_dt, m.Scope3ThirdPartyTransport.created_at <= end_dt),
        ]
        records: list[Any] = []
        for model, *conditions in specs:
            rows = (
                await self._session.execute(
                    select(model)
                    .where(model.status == STATUS_APPROVED, *conditions)
                    .order_by(model.id.asc())
                )
            ).scalars().all()
            records.extend(rows)
        return records

    async def _inventory_payload(self, record: Any, area_ids: set[str]) -> dict[str, Any]:
        serialized = await _serialize_scope_record(record, self._session, source_kind=_record_source_kind(record, None))
        included, exclusion_reason = _boundary_inclusion(record, area_ids)
        quality = inventory_quality(serialized, included=included)
        return {
            "record_type": type(record).__name__,
            "record_id": record.id,
            "scope": _scope_group_label(type(record).__name__),
            "record_label": _scope_record_label(type(record).__name__),
            "display_name": _scope_display_name(record),
            "period": _scope_record_period(record),
            "source_kind": serialized.get("source_kind"),
            "activity_amount": _decimal_or_none(serialized.get("activity_amount")),
            "activity_unit": serialized.get("activity_unit"),
            "computed_co2e": _decimal_or_none(serialized.get("computed_co2e")),
            "factor_source": serialized.get("factor_source"),
            "factor_year": serialized.get("factor_year"),
            "factor_unit": serialized.get("factor_unit"),
            "calc_status": serialized.get("calc_status"),
            "quality_status": quality,
            "included": included,
            "exclusion_reason": exclusion_reason,
            "source_payload": _jsonable(serialized),
        }

    async def _boundary_facilities(self, boundary_id: int) -> list[m.BoundaryFacility]:
        return (await self._session.execute(select(m.BoundaryFacility).where(m.BoundaryFacility.boundary_id == boundary_id))).scalars().all()

    async def _get_or_raise(self, model: type[Any], item_id: int, message: str) -> Any:
        obj = await self._session.get(model, item_id)
        if obj is None:
            raise ValueError(message)
        return obj


def _batch_no(boundary: m.OrganizationBoundary) -> str:
    return f"INV-{boundary.boundary_no}-V{boundary.version}-{datetime.datetime.now(UTC):%Y%m%d%H%M%S}"


def _boundary_inclusion(record: Any, area_ids: set[str]) -> tuple[bool, str | None]:
    if not area_ids:
        return True, None
    area_id = getattr(record, "area_id", None)
    if area_id in (None, ""):
        return True, None
    included = str(area_id) in area_ids
    return included, None if included else "记录区域不在当前组织边界纳入设施范围内"


def _month(value: date) -> str:
    return value.strftime("%Y-%m")


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _inventory_payload_summary(items: list[m.CarbonEmissionInventoryItem], *, total: Decimal) -> dict[str, Any]:
    scope_totals: dict[str, dict[str, Any]] = {}
    for item in items:
        bucket = scope_totals.setdefault(item.scope, {"scope": item.scope, "record_count": 0, "included_record_count": 0, "kg_co2e": 0.0})
        bucket["record_count"] += 1
        if item.included:
            bucket["included_record_count"] += 1
            bucket["kg_co2e"] += float(item.computed_co2e or 0)
    for bucket in scope_totals.values():
        bucket["t_co2e"] = bucket["kg_co2e"] / 1000
    return {"total_kg_co2e": float(total), "total_t_co2e": float(total / Decimal(1000)), "scope_summary": list(scope_totals.values())}


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def _utc_now_naive() -> datetime.datetime:
    return datetime.datetime.now(UTC).replace(tzinfo=None)
