"""Application workflows for maintaining canonical GHG sources and activities."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, select

from app.db import models as m
from app.domain.ghg_inventory.domain.activity_fields import CATEGORY_ACTIVITY_FIELDS
from app.domain.ghg_inventory.domain.catalog import CATEGORY_BY_CODE, CategoryDefinition
from app.domain.ghg_inventory.models import (
    GhgActivityAllocation,
    GhgActivityRecord,
    GhgCalculationResult,
    GhgEmissionSource,
    GhgEvidenceLink,
)
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class GhgInventoryMaintenance:
    """Maintain canonical emission sources and activity data without adding workflow state."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_source(self, payload: dict[str, Any]) -> GhgEmissionSource:
        require_session_tenant_id(self.session)
        category = _category(str(payload["iso_category_code"]))
        duplicate = await self.session.scalar(
            select(GhgEmissionSource.id).where(
                GhgEmissionSource.inventory_code == payload["inventory_code"],
                GhgEmissionSource.source_code == payload["source_code"],
            )
        )
        if duplicate is not None:
            msg = "同一盘查任务下排放源编号已存在"
            raise ValueError(msg)
        source = GhgEmissionSource(**_source_values(payload, category.source_mechanism))
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def update_source(self, source_code: str, payload: dict[str, Any]) -> GhgEmissionSource:
        require_session_tenant_id(self.session)
        source = await self._source(inventory_code=str(payload["inventory_code"]), source_code=source_code)
        category = _category(str(payload["iso_category_code"]))
        if source_code != payload["source_code"]:
            duplicate = await self.session.scalar(
                select(GhgEmissionSource.id).where(
                    GhgEmissionSource.inventory_code == payload["inventory_code"],
                    GhgEmissionSource.source_code == payload["source_code"],
                    GhgEmissionSource.id != source.id,
                )
            )
            if duplicate is not None:
                msg = "同一盘查任务下排放源编号已存在"
                raise ValueError(msg)
        for key, value in _source_values(payload, category.source_mechanism).items():
            setattr(source, key, value)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def delete_source(self, *, inventory_code: str, source_code: str) -> GhgEmissionSource | None:
        require_session_tenant_id(self.session)
        source = await self._source(inventory_code=inventory_code, source_code=source_code)
        activity_count = await self.session.scalar(
            select(func.count()).select_from(GhgActivityRecord).where(
                GhgActivityRecord.inventory_code == inventory_code,
                GhgActivityRecord.source_code == source_code,
            )
        )
        if activity_count:
            source.status = "inactive"
            await self.session.commit()
            await self.session.refresh(source)
            return source
        await self.session.delete(source)
        await self.session.commit()
        return None

    async def create_activity(self, payload: dict[str, Any]) -> GhgActivityRecord:
        require_session_tenant_id(self.session)
        duplicate = await self.session.scalar(
            select(GhgActivityRecord.id).where(
                GhgActivityRecord.inventory_code == payload["inventory_code"],
                GhgActivityRecord.record_code == payload["record_code"],
            )
        )
        if duplicate is not None:
            msg = "同一盘查任务下活动记录编号已存在"
            raise ValueError(msg)
        values, source = await self._activity_values(payload)
        activity = GhgActivityRecord(**values)
        activity.emission_source_id = source.id
        self.session.add(activity)
        await self.session.commit()
        await self.session.refresh(activity)
        return activity

    async def update_activity(self, record_code: str, payload: dict[str, Any]) -> GhgActivityRecord:
        require_session_tenant_id(self.session)
        activity = await self._activity(inventory_code=str(payload["inventory_code"]), record_code=record_code)
        if record_code != payload["record_code"]:
            duplicate = await self.session.scalar(
                select(GhgActivityRecord.id).where(
                    GhgActivityRecord.inventory_code == payload["inventory_code"],
                    GhgActivityRecord.record_code == payload["record_code"],
                    GhgActivityRecord.id != activity.id,
                )
            )
            if duplicate is not None:
                msg = "同一盘查任务下活动记录编号已存在"
                raise ValueError(msg)
        values, source = await self._activity_values(payload)
        for key, value in values.items():
            setattr(activity, key, value)
        activity.emission_source_id = source.id
        await self.session.commit()
        await self.session.refresh(activity)
        return activity

    async def delete_activity(self, *, inventory_code: str, record_code: str) -> GhgActivityRecord | None:
        require_session_tenant_id(self.session)
        activity = await self._activity(inventory_code=inventory_code, record_code=record_code)
        result_count = await self.session.scalar(
            select(func.count()).select_from(GhgCalculationResult).where(GhgCalculationResult.activity_id == activity.id)
        )
        if result_count:
            activity.status = "archived"
            await self.session.commit()
            await self.session.refresh(activity)
            return activity
        await self.session.execute(delete(GhgActivityAllocation).where(GhgActivityAllocation.activity_id == activity.id))
        await self.session.execute(
            delete(GhgEvidenceLink).where(GhgEvidenceLink.record_type == "activity", GhgEvidenceLink.record_code == activity.record_code)
        )
        await self.session.delete(activity)
        await self.session.commit()
        return None

    async def generate_activities(
        self,
        *,
        inventory_code: str,
        reporting_period_id: int,
        organization_boundary_id: int | None,
        source_types: list[str],
    ) -> dict[str, Any]:
        require_session_tenant_id(self.session)
        period = await self.session.get(m.ReportingPeriod, reporting_period_id)
        if period is None:
            msg = "报告期不存在或不属于当前租户"
            raise ValueError(msg)
        organization = await self.session.get(m.ReportingOrganization, period.reporting_org_id)
        if organization is None:
            msg = "报告主体不存在或不属于当前租户"
            raise ValueError(msg)
        boundary = None
        if organization_boundary_id is not None:
            boundary = await self.session.get(m.OrganizationBoundary, organization_boundary_id)
            if boundary is None or boundary.period_id != period.id:
                msg = "组织边界不存在或不属于所选报告期"
                raise ValueError(msg)
        counters = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
        messages: list[str] = []
        for source_type in source_types:
            if source_type == "energy_electricity":
                await self._generate_purchased_electricity(period, organization, boundary, inventory_code, counters, messages)
            elif source_type == "employee_commute":
                await self._generate_employee_commute(period, organization, boundary, inventory_code, counters, messages)
            else:
                counters["skipped"] += 1
                messages.append(f"{source_type} 暂未配置可执行生成规则")
        await self.session.commit()
        return {
            "inventoryCode": inventory_code,
            "createdCount": counters["created"],
            "updatedCount": counters["updated"],
            "skippedCount": counters["skipped"],
            "failedCount": counters["failed"],
            "messages": messages,
        }

    async def _activity_values(self, payload: dict[str, Any]) -> tuple[dict[str, Any], GhgEmissionSource]:
        category = _category(str(payload["iso_category_code"]))
        period_start = _date(payload["period_start"], "开始日期")
        period_end = _date(payload["period_end"], "结束日期")
        if period_end < period_start:
            msg = "结束日期不能早于开始日期"
            raise ValueError(msg)
        activity_amount = _decimal(payload["activity_amount"], "活动量")
        source_payload = dict(payload.get("source_payload") or {})
        _validate_activity_payload(category.package_code, source_payload)
        source = await self._source(inventory_code=str(payload["inventory_code"]), source_code=str(payload["source_code"]))
        if source.iso_category_code != category.code:
            msg = "活动数据分类必须与排放源分类一致"
            raise ValueError(msg)
        return (
            {
                "record_code": payload["record_code"],
                "inventory_code": payload["inventory_code"],
                "reporting_period_id": payload.get("reporting_period_id"),
                "organization_boundary_id": payload.get("organization_boundary_id"),
                "organization_code": payload["organization_code"],
                "facility_code": payload["facility_code"],
                "source_code": payload["source_code"],
                "activity_code": payload["activity_code"],
                "activity_name": payload["activity_name"],
                "period_start": period_start,
                "period_end": period_end,
                "iso_category_code": category.code,
                "ghg_scope": category.ghg_scope,
                "scope3_category": category.scope3_category,
                "source_mechanism": category.source_mechanism,
                "value_chain_position": category.value_chain_position,
                "boundary_status": "included",
                "activity_amount": activity_amount,
                "activity_unit": payload["activity_unit"],
                "data_source_type": payload["data_source_type"],
                "measurement_method": payload["measurement_method"],
                "quality_status": payload.get("quality_status") or "pass",
                "parameter_set_code": payload.get("parameter_set_code"),
                "source_payload": source_payload,
                "remarks": payload.get("remarks"),
                "status": payload.get("status") or "approved",
                "source_system": payload.get("source_system") or "manual",
                "source_record_type": payload.get("source_record_type"),
                "source_record_id": payload.get("source_record_id"),
            },
            source,
        )

    async def _source(self, *, inventory_code: str, source_code: str) -> GhgEmissionSource:
        source = await self.session.scalar(
            select(GhgEmissionSource).where(
                GhgEmissionSource.inventory_code == inventory_code,
                GhgEmissionSource.source_code == source_code,
            )
        )
        if source is None:
            msg = "排放源不存在, 请先维护排放源"
            raise ValueError(msg)
        return source

    async def _activity(self, *, inventory_code: str, record_code: str) -> GhgActivityRecord:
        activity = await self.session.scalar(
            select(GhgActivityRecord).where(
                GhgActivityRecord.inventory_code == inventory_code,
                GhgActivityRecord.record_code == record_code,
            )
        )
        if activity is None:
            msg = "活动记录不存在"
            raise ValueError(msg)
        return activity

    async def _ensure_generated_source(
        self,
        *,
        inventory_code: str,
        organization: m.ReportingOrganization,
        period: m.ReportingPeriod,
        boundary: m.OrganizationBoundary | None,
        source_code: str,
        source_name: str,
        category_code: str,
        facility_code: str,
        source_payload: dict[str, Any],
        default_area_id: int | None = None,
        default_equipment_id: int | None = None,
        default_measurement_boundary_id: int | None = None,
    ) -> GhgEmissionSource:
        category = CATEGORY_BY_CODE[category_code]
        source = await self.session.scalar(
            select(GhgEmissionSource).where(
                GhgEmissionSource.inventory_code == inventory_code,
                GhgEmissionSource.source_code == source_code,
            )
        )
        if source is None:
            source = GhgEmissionSource(
                inventory_code=inventory_code,
                organization_code=organization.code,
                facility_code=facility_code,
                source_code=source_code,
                source_name=source_name,
                iso_category_code=category_code,
                source_mechanism=category.source_mechanism,
                origin_kind="internal" if category.value_chain_position == "own" else "external",
            )
            self.session.add(source)
            await self.session.flush()
        source.organization_boundary_id = boundary.id if boundary else None
        source.reporting_period_id = period.id
        source.organization_code = organization.code
        source.facility_code = facility_code
        source.source_name = source_name
        source.iso_category_code = category_code
        source.source_mechanism = category.source_mechanism
        source.origin_kind = "internal" if category.value_chain_position == "own" else "external"
        source.default_area_id = default_area_id
        source.default_equipment_id = default_equipment_id
        source.default_measurement_boundary_id = default_measurement_boundary_id
        source.default_allocation_role = "responsibility"
        source.source_system = "generated"
        source.source_payload = source_payload
        source.status = "active"
        return source

    async def _upsert_generated_activity(
        self,
        *,
        inventory_code: str,
        organization: m.ReportingOrganization,
        period: m.ReportingPeriod,
        boundary: m.OrganizationBoundary | None,
        source: GhgEmissionSource,
        record_code: str,
        activity_name: str,
        category_code: str,
        activity_amount: Decimal,
        activity_unit: str,
        data_source_type: str,
        measurement_method: str,
        source_payload: dict[str, Any],
        source_record_type: str,
        source_record_id: int | None,
        counters: dict[str, int],
    ) -> GhgActivityRecord:
        category = CATEGORY_BY_CODE[category_code]
        activity = await self.session.scalar(
            select(GhgActivityRecord).where(
                GhgActivityRecord.inventory_code == inventory_code,
                GhgActivityRecord.record_code == record_code,
            )
        )
        created = activity is None
        if activity is None:
            activity = GhgActivityRecord(record_code=record_code, inventory_code=inventory_code)
            self.session.add(activity)
        activity.reporting_period_id = period.id
        activity.organization_boundary_id = boundary.id if boundary else None
        activity.emission_source_id = source.id
        activity.organization_code = organization.code
        activity.facility_code = source.facility_code
        activity.source_code = source.source_code
        activity.activity_code = source_record_type
        activity.activity_name = activity_name
        activity.period_start = period.period_start
        activity.period_end = period.period_end
        activity.iso_category_code = category_code
        activity.ghg_scope = category.ghg_scope
        activity.scope3_category = category.scope3_category
        activity.source_mechanism = category.source_mechanism
        activity.value_chain_position = category.value_chain_position
        activity.boundary_status = "included"
        activity.activity_amount = activity_amount
        activity.activity_unit = activity_unit
        activity.data_source_type = data_source_type
        activity.measurement_method = measurement_method
        activity.quality_status = "pass"
        activity.source_payload = source_payload
        activity.status = "approved"
        activity.source_system = "generated"
        activity.source_record_type = source_record_type
        activity.source_record_id = source_record_id
        counters["created" if created else "updated"] += 1
        return activity

    async def _generate_purchased_electricity(
        self,
        period: m.ReportingPeriod,
        organization: m.ReportingOrganization,
        boundary: m.OrganizationBoundary | None,
        inventory_code: str,
        counters: dict[str, int],
        messages: list[str],
    ) -> None:
        period_start = datetime.combine(period.period_start, time.min)
        period_end = datetime.combine(period.period_end, time.max)
        rows = list(
            (
                await self.session.execute(
                    select(
                        m.EnergyIntervalFact.equipment_id,
                        m.EnergyIntervalFact.equipment_code,
                        m.EnergyIntervalFact.equipment_name,
                        m.EnergyIntervalFact.measurement_boundary_id,
                        func.coalesce(func.sum(m.EnergyIntervalFact.amount), 0),
                    )
                    .where(
                        m.EnergyIntervalFact.is_current.is_(True),
                        m.EnergyIntervalFact.energy_type_code == "purchased_electricity",
                        m.EnergyIntervalFact.period_start >= period_start,
                        m.EnergyIntervalFact.period_end <= period_end,
                    )
                    .group_by(
                        m.EnergyIntervalFact.equipment_id,
                        m.EnergyIntervalFact.equipment_code,
                        m.EnergyIntervalFact.equipment_name,
                        m.EnergyIntervalFact.measurement_boundary_id,
                    )
                )
            ).all()
        )
        if not rows:
            counters["skipped"] += 1
            messages.append("购入电力未找到报告期内能源事实")
            return
        for equipment_id, equipment_code, equipment_name, boundary_id, amount in rows:
            equipment = await self.session.get(m.MonitorEquipment, equipment_id) if equipment_id else None
            area = await self.session.get(m.MonitorSector, equipment.sector_id) if equipment and equipment.sector_id else None
            facility_code = area.code if area else "ELECTRICITY"
            source_code = f"GEN-ELEC-{equipment_code or boundary_id or 'TOTAL'}"
            source = await self._ensure_generated_source(
                inventory_code=inventory_code,
                organization=organization,
                period=period,
                boundary=boundary,
                source_code=source_code,
                source_name=f"{equipment_name or equipment_code or '购入电力'}用电",
                category_code="2.1",
                facility_code=facility_code,
                default_area_id=area.id if area else None,
                default_equipment_id=equipment.id if equipment else None,
                default_measurement_boundary_id=boundary_id,
                source_payload={"energy_type": "electricity", "meter_point": equipment_code or str(boundary_id or "")},
            )
            await self._upsert_generated_activity(
                inventory_code=inventory_code,
                organization=organization,
                period=period,
                boundary=boundary,
                source=source,
                record_code=f"GEN-{period.code}-ELEC-{equipment_code or boundary_id or 'TOTAL'}",
                activity_name=f"{period.name}{equipment_name or equipment_code or '购入电力'}",
                category_code="2.1",
                activity_amount=Decimal(str(amount)),
                activity_unit="kWh",
                data_source_type="measured",
                measurement_method="能源计量事实按报告期汇总",
                source_payload={
                    "energy_type": "electricity",
                    "supplier_name": "电网购电",
                    "meter_point": equipment_code or str(boundary_id or ""),
                    "scope2_method": "location",
                },
                source_record_type="energy_interval_fact",
                source_record_id=equipment_id,
                counters=counters,
            )

    async def _generate_employee_commute(
        self,
        period: m.ReportingPeriod,
        organization: m.ReportingOrganization,
        boundary: m.OrganizationBoundary | None,
        inventory_code: str,
        counters: dict[str, int],
        messages: list[str],
    ) -> None:
        rows = list((await self.session.scalars(select(m.EmployeeCommute).order_by(m.EmployeeCommute.id))).all())
        if not rows:
            counters["skipped"] += 1
            messages.append("员工通勤台账为空")
            return
        for row in rows:
            distance = Decimal(str(row.mileage or 0))
            if distance <= 0:
                counters["skipped"] += 1
                continue
            mode = {0: "柴油乘用车", 1: "汽油乘用车", 2: "电动乘用车"}.get(row.car_power_type or 1, "乘用车")
            source = await self._ensure_generated_source(
                inventory_code=inventory_code,
                organization=organization,
                period=period,
                boundary=boundary,
                source_code=f"GEN-COMMUTE-{row.id}",
                source_name=f"{row.name}通勤",
                category_code="3.3",
                facility_code="COMMUTE",
                source_payload={"transport_direction": "commute", "transport_mode": mode},
            )
            await self._upsert_generated_activity(
                inventory_code=inventory_code,
                organization=organization,
                period=period,
                boundary=boundary,
                source=source,
                record_code=f"GEN-{period.code}-COMMUTE-{row.id}",
                activity_name=f"{period.name}{row.name}通勤里程",
                category_code="3.3",
                activity_amount=distance,
                activity_unit="km",
                data_source_type="ledger",
                measurement_method="员工通勤台账按报告期生成",
                source_payload={
                    "transport_direction": "commute",
                    "transport_mode": mode,
                    "distance_km": str(distance),
                    "passenger_count": "1",
                    "origin": "居住地",
                    "destination": organization.name,
                },
                source_record_type="employee_commute",
                source_record_id=row.id,
                counters=counters,
            )


def _source_values(payload: dict[str, Any], default_mechanism: str) -> dict[str, Any]:
    return {
        "inventory_code": payload["inventory_code"],
        "organization_boundary_id": payload.get("organization_boundary_id"),
        "reporting_period_id": payload.get("reporting_period_id"),
        "organization_code": payload["organization_code"],
        "facility_code": payload["facility_code"],
        "source_code": payload["source_code"],
        "source_name": payload["source_name"],
        "iso_category_code": payload["iso_category_code"],
        "source_mechanism": payload.get("source_mechanism") or default_mechanism,
        "origin_kind": payload.get("origin_kind") or "internal",
        "default_area_id": payload.get("default_area_id"),
        "default_equipment_id": payload.get("default_equipment_id"),
        "default_measurement_boundary_id": payload.get("default_measurement_boundary_id"),
        "default_allocation_role": payload.get("default_allocation_role") or "responsibility",
        "external_facility_code": _text(payload.get("external_facility_code")),
        "external_facility_name": _text(payload.get("external_facility_name")),
        "valid_from": _optional_date(payload.get("valid_from"), "有效期起"),
        "valid_to": _optional_date(payload.get("valid_to"), "有效期止"),
        "source_system": payload.get("source_system") or "manual",
        "source_payload": dict(payload.get("source_payload") or {}),
        "status": payload.get("status") or "active",
    }


def _category(code: str) -> CategoryDefinition:
    category = CATEGORY_BY_CODE.get(code)
    if category is None:
        msg = "不支持的 ISO 二级分类"
        raise ValueError(msg)
    return category


def _validate_activity_payload(package_code: str, payload: dict[str, Any]) -> None:
    for field in CATEGORY_ACTIVITY_FIELDS.get(package_code, ()):
        value = payload.get(field.code)
        if field.required and (value is None or str(value).strip() == ""):
            msg = f"{field.label}不能为空"
            raise ValueError(msg)
        if field.choices and value not in (None, "") and str(value) not in field.choices:
            msg = f"{field.label}不在允许范围内"
            raise ValueError(msg)


def _date(value: Any, label: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        msg = f"{label}格式无效"
        raise ValueError(msg) from exc


def _optional_date(value: Any, label: str) -> date | None:
    if value in (None, ""):
        return None
    return _date(value, label)


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        msg = f"{label}必须为数字"
        raise ValueError(msg) from exc
    if result < 0:
        msg = f"{label}不能为负数"
        raise ValueError(msg)
    return result


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
