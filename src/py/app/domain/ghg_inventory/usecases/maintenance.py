"""Application workflows for maintaining canonical GHG sources and activities."""

from __future__ import annotations

# ruff: noqa: RUF001 - Chinese business messages are intentional.
import calendar
import hashlib
import json
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, select

from app.db import models as m
from app.domain.energy.queries.consumption import EnergyConsumptionQuery
from app.domain.ghg_inventory.domain.activity_fields import CATEGORY_ACTIVITY_FIELDS
from app.domain.ghg_inventory.domain.allocation import CATEGORY_ALLOCATION_POLICY_BY_CODE
from app.domain.ghg_inventory.domain.catalog import CATEGORY_BY_CODE, METHOD_BY_CODE, CategoryDefinition
from app.domain.ghg_inventory.models import (
    GhgActivityAllocation,
    GhgActivityRecord,
    GhgCalculationResult,
    GhgEmissionSource,
    GhgEvidenceLink,
)
from app.domain.ghg_inventory.queries.inventory import GhgInventoryQueryService, activity_summary
from app.domain.ghg_inventory.usecases.allocations import ReplaceActivityAllocations
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class GhgInventoryMaintenance:
    """Maintain canonical emission sources and activity data without adding workflow state."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.generated_records: list[GhgActivityRecord] = []

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
            select(func.count())
            .select_from(GhgActivityRecord)
            .where(
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
            if key in {"source_system", "source_record_type", "source_record_id"}:
                continue
            if key == "source_payload":
                value = {**(activity.source_payload or {}), **value}
            if key == "parameter_set_code" and value is None:
                continue
            setattr(activity, key, value)
        activity.emission_source_id = source.id
        await self.session.commit()
        await self.session.refresh(activity)
        return activity

    async def delete_activity(self, *, inventory_code: str, record_code: str) -> GhgActivityRecord | None:
        require_session_tenant_id(self.session)
        activity = await self._activity(inventory_code=inventory_code, record_code=record_code)
        result_count = await self.session.scalar(
            select(func.count())
            .select_from(GhgCalculationResult)
            .where(GhgCalculationResult.activity_id == activity.id)
        )
        if result_count:
            activity.status = "archived"
            await self.session.commit()
            await self.session.refresh(activity)
            return activity
        await self.session.execute(
            delete(GhgActivityAllocation).where(GhgActivityAllocation.activity_id == activity.id)
        )
        await self.session.execute(
            delete(GhgEvidenceLink).where(
                GhgEvidenceLink.record_type == "activity", GhgEvidenceLink.record_code == activity.record_code
            )
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
        facility_code: str | None = None,
        iso_category_code: str | None = None,
        source_code: str | None = None,
    ) -> dict[str, Any]:
        require_session_tenant_id(self.session)
        self.generated_records = []
        period = await self.session.scalar(
            select(m.ReportingPeriod).where(m.ReportingPeriod.id == reporting_period_id).with_for_update()
        )
        if period is None:
            msg = "报告期不存在或不属于当前租户"
            raise ValueError(msg)
        if period.status == "locked" or period.locked_at is not None:
            msg = "报告期已锁定，不能重新生成活动数据"
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
        for source_type in dict.fromkeys(source_types):
            if source_type in {"energy_electricity", "energy_natural_gas", "energy_diesel"}:
                energy_type = {
                    "energy_electricity": "purchased_electricity",
                    "energy_natural_gas": "natural_gas",
                    "energy_diesel": "diesel",
                }[source_type]
                await self._generate_energy(
                    period,
                    organization,
                    boundary,
                    inventory_code,
                    counters,
                    messages,
                    energy_type=energy_type,
                    facility_code=facility_code,
                    category_filter=iso_category_code,
                    requested_source_code=source_code,
                )
            elif source_type == "employee_commute":
                await self._generate_employee_commute(
                    period, organization, boundary, inventory_code, counters, messages
                )
            else:
                counters["skipped"] += 1
                messages.append(f"{source_type} 暂未配置可执行生成规则")
        await self.session.commit()
        query = GhgInventoryQueryService(self.session)
        records = [
            await query.activity(inventory_code=inventory_code, record_code=row.record_code)
            for row in self.generated_records
        ]
        missing_parameters = sum(not row.parameter_set_code for row in self.generated_records)
        if missing_parameters:
            messages.append(f"{missing_parameters}条活动尚未选择排放因子，可在活动记录中选择适用因子后核算")
        return {
            "records": records,
            "recordCodes": [row["recordCode"] for row in records],
            "summary": activity_summary(records),
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
        source = await self._source(
            inventory_code=str(payload["inventory_code"]), source_code=str(payload["source_code"])
        )
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
        if source is not None:
            # The source's names, boundary and defaults may have been maintained manually.
            return source
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
        source.default_allocation_role = CATEGORY_ALLOCATION_POLICY_BY_CODE[category_code].default_role
        source.source_system = "generated"
        source.source_payload = {**(source.source_payload or {}), **source_payload}
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
        period_start: date | None = None,
        period_end: date | None = None,
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
        if activity.organization_boundary_id is None:
            activity.organization_boundary_id = source.organization_boundary_id or (boundary.id if boundary else None)
        activity.emission_source_id = source.id
        activity.organization_code = organization.code
        activity.facility_code = source.facility_code
        activity.source_code = source.source_code
        activity.activity_code = source_record_type
        activity.activity_name = activity_name
        activity.period_start = period_start or period.period_start
        activity.period_end = period_end or period.period_end
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
        # Keep an explicitly applied factor/method when refreshing the source quantity.
        activity.source_payload = {
            **source_payload,
            **{
                key: value
                for key, value in (activity.source_payload or {}).items()
                if key
                in {
                    "method_code",
                    "factor_selection",
                    "gas_code",
                    "factor_id",
                    "factor_source",
                    "factor_year",
                    "factor_unit",
                }
            },
        }
        if not activity.parameter_set_code and source_payload.get("parameter_set_code"):
            activity.parameter_set_code = str(source_payload["parameter_set_code"])
        activity.status = "approved"
        activity.source_system = "generated"
        activity.source_record_type = source_record_type
        activity.source_record_id = source_record_id
        await self.session.flush()
        existing_allocation_id = await self.session.scalar(
            select(GhgActivityAllocation.id).where(GhgActivityAllocation.activity_id == activity.id).limit(1)
        )
        if source.default_area_id is not None and existing_allocation_id is None:
            await ReplaceActivityAllocations(self.session).execute(
                inventory_code=inventory_code,
                record_code=record_code,
                allocations=[
                    {
                        "area_id": source.default_area_id,
                        "equipment_id": source.default_equipment_id,
                        "measurement_boundary_id": source.default_measurement_boundary_id,
                        "allocation_role": source.default_allocation_role,
                        "allocation_ratio": "1",
                        "source_kind": "source_default",
                    }
                ],
                commit=False,
            )
        self.generated_records.append(activity)
        counters["created" if created else "updated"] += 1
        return activity

    async def _generate_energy(  # noqa: C901, PLR0915 - validate and group canonical energy sources
        self,
        period: m.ReportingPeriod,
        organization: m.ReportingOrganization,
        boundary: m.OrganizationBoundary | None,
        inventory_code: str,
        counters: dict[str, int],
        messages: list[str],
        *,
        energy_type: str,
        facility_code: str | None,
        category_filter: str | None,
        requested_source_code: str | None,
    ) -> None:
        rows = list(
            (
                await self.session.scalars(
                    select(m.EnergyIntervalFact)
                    .where(
                        m.EnergyIntervalFact.is_current.is_(True),
                        m.EnergyIntervalFact.energy_type_code == energy_type,
                        # Match the default energy consumption ledger: current monthly facts only.
                        m.EnergyIntervalFact.granularity == EnergyConsumptionQuery().granularity,
                        m.EnergyIntervalFact.period_start >= datetime.combine(period.period_start, time.min),
                        m.EnergyIntervalFact.period_end <= datetime.combine(period.period_end, time.max),
                    )
                    .order_by(m.EnergyIntervalFact.period_start, m.EnergyIntervalFact.id)
                )
            ).all()
        )
        areas = {row.id: row for row in (await self.session.scalars(select(m.MonitorSector))).all()}
        equipment = {row.id: row for row in (await self.session.scalars(select(m.MonitorEquipment))).all()}
        boundaries = {row.id: row for row in (await self.session.scalars(select(m.MeasurementBoundary))).all()}
        selected_area = next((row for row in areas.values() if row.code == facility_code), None)
        if facility_code and selected_area is None:
            msg = "所选工厂或区域不存在"
            raise ValueError(msg)
        configured_sources = list(
            (
                await self.session.scalars(
                    select(GhgEmissionSource).where(
                        GhgEmissionSource.inventory_code == inventory_code,
                        GhgEmissionSource.organization_code == organization.code,
                        GhgEmissionSource.status == "active",
                    )
                )
            ).all()
        )
        source_by_fact: dict[int, GhgEmissionSource | None] = {}
        groups: dict[tuple[Any, ...], list[m.EnergyIntervalFact]] = {}
        for row in rows:
            device = equipment.get(row.equipment_id) if row.equipment_id is not None else None
            area = areas.get(device.sector_id) if device and device.sector_id is not None else None
            if area is None:
                area = next(
                    (item for item in areas.values() if str(item.id) == row.area_id or item.code == row.area_id), None
                )
            if selected_area and not _area_within(area, selected_area.id, areas):
                continue
            meter_boundary = (
                boundaries.get(row.measurement_boundary_id) if row.measurement_boundary_id is not None else None
            )
            if energy_type == "purchased_electricity" and meter_boundary is None and row.equipment_id is not None:
                matches = [
                    item
                    for item in boundaries.values()
                    if item.meter_equipment_id == row.equipment_id
                    and item.status == "active"
                    and (item.valid_from is None or item.valid_from <= row.period_start.date())
                    and (item.valid_to is None or item.valid_to >= row.period_end.date())
                ]
                if len(matches) > 1:
                    counters["failed"] += 1
                    messages.append(f"{row.equipment_name or row.source_record_id}匹配多个计量边界，本条未生成")
                    continue
                meter_boundary = matches[0] if matches else None
            if (
                energy_type == "purchased_electricity"
                and meter_boundary
                and (
                    not meter_boundary.include_in_scope2
                    or meter_boundary.energy_direction != "import"
                    or meter_boundary.status != "active"
                    or (meter_boundary.valid_from and row.period_start.date() < meter_boundary.valid_from)
                    or (meter_boundary.valid_to and row.period_end.date() > meter_boundary.valid_to)
                )
            ):
                counters["skipped"] += 1
                messages.append(f"{row.equipment_name or row.source_record_id}未纳入购电计量边界，已跳过")
                continue
            snapshot = row.source_snapshot or {}
            if snapshot.get("organization_code") not in (None, "", organization.code):
                continue
            eligible_categories = {"2.1"} if energy_type == "purchased_electricity" else {"1.1", "1.2"}
            candidates = _matching_energy_sources(
                configured_sources,
                row,
                area,
                areas,
                period.id,
                eligible_categories,
                requested_source_code=requested_source_code,
            )
            if len(candidates) > 1:
                counters["failed"] += 1
                messages.append(
                    f"{row.equipment_name or row.source_record_id}匹配多个排放源："
                    + "、".join(item.source_name for item in candidates)
                    + "；请明确选择排放源"
                )
                continue
            configured_source = candidates[0] if candidates else None
            if requested_source_code and configured_source is None:
                counters["failed"] += 1
                messages.append(f"{row.equipment_name or row.source_record_id}与所选排放源的设备、设施或期间不匹配")
                continue
            source_by_fact[row.id] = configured_source
            category = (
                configured_source.iso_category_code
                if configured_source
                else "2.1"
                if energy_type == "purchased_electricity"
                else str(snapshot.get("iso_category_code") or "")
            )
            if not category and energy_type == "natural_gas":
                category = "1.1"
            if category not in ({"2.1"} if energy_type == "purchased_electricity" else {"1.1", "1.2"}):
                counters["skipped"] += 1
                messages.append(f"{row.equipment_name or row.source_record_id}未确定固定源或移动源分类，已跳过")
                continue
            if category_filter and category != category_filter:
                continue
            if row.period_start.strftime("%Y-%m") != row.period_end.strftime("%Y-%m"):
                counters["skipped"] += 1
                messages.append(f"{row.source_record_id}跨越多个月份，请先在能源台账中明确月度用量")
                continue
            if not row.amount.is_finite() or row.amount < 0 or not row.unit:
                counters["failed"] += 1
                messages.append(f"{row.source_record_id}的数量或单位无效")
                continue
            key = (
                row.period_start.strftime("%Y-%m"),
                energy_type,
                category,
                area.id if area else None,
                row.equipment_id,
                row.equipment_code if row.equipment_id is None else None,
                meter_boundary.id if meter_boundary else row.measurement_boundary_id,
                row.unit,
            )
            groups.setdefault(key, []).append(row)
        for key, facts in groups.items():
            if _overlapping_facts(facts):
                counters["failed"] += len(facts)
                messages.append(
                    f"{key[0]} {facts[0].equipment_name or facts[0].equipment_code or '能源记录'}存在重复月度能源记录，本组未生成"
                )
                continue
            fact = facts[0]
            area = areas.get(key[3])
            device = equipment.get(fact.equipment_id) if fact.equipment_id is not None else None
            category = str(key[2])
            name = fact.equipment_name or (device.name if device else None) or (area.name if area else None)
            if not name:
                counters["skipped"] += len(facts)
                messages.append(f"{fact.source_record_id}缺少活动对象，请补充区域或设备")
                continue
            source_digest = _generation_digest(list(key[1:7]))
            record_code = "GEN-ENERGY-" + _generation_digest([period.id, *key])
            protected = await self._protected_generation_activity(inventory_code, record_code)
            if protected is not None:
                retained_activity, protected_reason = protected
                self.generated_records.append(retained_activity)
                counters["skipped"] += 1
                messages.append(f"{key[0]} {name}：{protected_reason}，已保留原记录")
                continue
            amount = sum((row.amount for row in facts), Decimal(0))
            energy_name = {"purchased_electricity": "购入电力", "natural_gas": "天然气", "diesel": "柴油"}[energy_type]
            configured_source = source_by_fact.get(fact.id)
            if (
                len({item.id if item is not None else None for item in (source_by_fact.get(row.id) for row in facts)})
                > 1
            ):
                counters["failed"] += len(facts)
                messages.append(f"{name}本月记录匹配不同排放源，本组未生成")
                continue
            payload = (
                {**dict(fact.source_snapshot or {}), **dict(configured_source.source_payload or {})}
                if configured_source
                else dict(fact.source_snapshot or {})
            )
            allowed = {field.code for field in CATEGORY_ACTIVITY_FIELDS[CATEGORY_BY_CODE[category].package_code]}
            details = {key: value for key, value in payload.items() if key in allowed}
            if category == "2.1":
                details.update(
                    energy_type="electricity",
                    meter_point=fact.equipment_code or name,
                    scope2_method=details.get("scope2_method") or "location",
                )
                method_code = "F08_PURCHASED_ENERGY"
            else:
                details.update(fuel_or_material=energy_type)
                details["vehicle_or_machine" if category == "1.2" else "facility_or_device"] = name
                method_code = CATEGORY_BY_CODE[category].default_methods[0]
            selected_method = str(payload.get("method_code") or method_code)
            allowed_methods = set(CATEGORY_BY_CODE[category].default_methods)
            if category in {"1.1", "1.2"}:
                # The existing factor application use case also supports a direct fuel emission factor.
                allowed_methods.add("F02_EF")
            if selected_method not in METHOD_BY_CODE or selected_method not in allowed_methods:
                counters["failed"] += len(facts)
                messages.append(f"{name}的计算方法不适用于所选能源分类，本组未生成")
                continue
            details.update(method_code=selected_method, source_fact_ids=[row.id for row in facts])
            if payload.get("parameter_set_code"):
                details["parameter_set_code"] = payload["parameter_set_code"]
            source = configured_source or await self._ensure_generated_source(
                inventory_code=inventory_code,
                organization=organization,
                period=period,
                boundary=boundary,
                source_code=f"GEN-ENERGY-{source_digest}",
                source_name=f"{name}{energy_name}",
                category_code=category,
                facility_code=area.code if area else organization.code,
                source_payload=details,
                default_area_id=area.id if area else None,
                default_equipment_id=device.id if device else None,
                default_measurement_boundary_id=key[6],
            )
            month_start = date.fromisoformat(f"{key[0]}-01")
            month_end = date(
                month_start.year, month_start.month, calendar.monthrange(month_start.year, month_start.month)[1]
            )
            await self._upsert_generated_activity(
                inventory_code=inventory_code,
                organization=organization,
                period=period,
                boundary=boundary,
                source=source,
                record_code=record_code,
                activity_name=f"{key[0]} {name}{energy_name}",
                category_code=category,
                activity_amount=amount,
                activity_unit=fact.unit,
                data_source_type="estimated"
                if any(row.data_quality in {"estimated", "simulated"} for row in facts)
                else "ledger",
                measurement_method="能源台账按月汇总",
                source_payload=details,
                source_record_type="energy_interval_fact",
                source_record_id=fact.id if len(facts) == 1 else None,
                counters=counters,
                period_start=max(period.period_start, month_start),
                period_end=min(period.period_end, month_end),
            )
        if not groups:
            counters["skipped"] += 1
            messages.append("未找到所选期间、工厂和分类下可生成的能源数据")

    async def _protected_generation_activity(
        self,
        inventory_code: str,
        record_code: str,
    ) -> tuple[GhgActivityRecord, str] | None:
        activity = await self.session.scalar(
            select(GhgActivityRecord)
            .where(
                GhgActivityRecord.inventory_code == inventory_code,
                GhgActivityRecord.record_code == record_code,
            )
            .with_for_update()
        )
        if activity is None:
            return None
        if activity.status in {"locked", "archived"}:
            return activity, "活动已锁定或归档"
        # Each calculation run freezes its own values and formula snapshot.
        # References protect deletion, not corrections to the current activity.
        return None

    async def _generate_employee_commute(
        self,
        period: m.ReportingPeriod,
        organization: m.ReportingOrganization,
        boundary: m.OrganizationBoundary | None,
        inventory_code: str,
        counters: dict[str, int],
        messages: list[str],
    ) -> None:
        # This existing ledger has no date, frequency, or reporting-period fields.
        # Reusing its mileage for every selected period would invent consumption.
        count = int(await self.session.scalar(select(func.count()).select_from(m.EmployeeCommute)) or 0)
        counters["skipped"] += count or 1
        messages.append("员工通勤台账没有日期或报告期字段，不能生成本期活动；请在通勤分类填报实际期间和里程")


def _matching_energy_sources(
    sources: list[GhgEmissionSource],
    fact: m.EnergyIntervalFact,
    area: m.MonitorSector | None,
    areas: dict[int, m.MonitorSector],
    reporting_period_id: int,
    categories: set[str],
    *,
    requested_source_code: str | None,
) -> list[GhgEmissionSource]:
    """Resolve explicit resource bindings, never infer purpose from equipment names."""
    eligible = [
        source
        for source in sources
        if source.iso_category_code in categories
        and source.reporting_period_id in (None, reporting_period_id)
        and (source.valid_from is None or source.valid_from <= fact.period_start.date())
        and (source.valid_to is None or source.valid_to >= fact.period_end.date())
        and (
            source.source_code == requested_source_code
            if requested_source_code
            else source.source_system != "generated"
        )
    ]
    equipment_matches = [
        source
        for source in eligible
        if fact.equipment_id is not None and source.default_equipment_id == fact.equipment_id
    ]
    if equipment_matches:
        return equipment_matches
    return [
        source
        for source in eligible
        if source.default_equipment_id is None
        and area is not None
        and (
            (source.default_area_id is not None and _area_within(area, source.default_area_id, areas))
            or source.facility_code == area.code
        )
    ]


def _generation_digest(values: list[Any]) -> str:
    return hashlib.sha256(json.dumps(values, default=str).encode()).hexdigest()[:24].upper()


def _overlapping_facts(facts: list[m.EnergyIntervalFact]) -> bool:
    ordered = sorted(facts, key=lambda row: row.period_start)
    return any(
        left.period_end > right.period_start or left.period_start == right.period_start
        for left, right in pairwise(ordered)
    )


def _area_within(area: m.MonitorSector | None, selected_id: int, areas: dict[int, m.MonitorSector]) -> bool:
    seen: set[int] = set()
    while area is not None and area.id not in seen:
        if area.id == selected_id:
            return True
        seen.add(area.id)
        area = areas.get(area.parent_id) if area.parent_id is not None else None
    return False


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
    if not result.is_finite() or result < 0:
        msg = f"{label}不能为负数"
        raise ValueError(msg)
    return result


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
