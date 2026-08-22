"""Application workflows for GHG source and area/equipment allocation governance."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import delete, select

from app.domain.carbon import models as carbon_models
from app.domain.ghg_inventory.domain.allocation import (
    CATEGORY_ALLOCATION_POLICY_BY_CODE,
    validate_allocation,
    validate_allocation_ratios,
)
from app.domain.ghg_inventory.models import GhgActivityAllocation, GhgActivityRecord, GhgEmissionSource
from app.domain.metering.models import MeasurementBoundary
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ReplaceActivityAllocations:
    """Replace the complete allocation set for one activity in one transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self,
        *,
        inventory_code: str,
        record_code: str,
        allocations: list[dict[str, Any]],
        commit: bool = True,
    ) -> list[GhgActivityAllocation]:
        require_session_tenant_id(self.session)
        activity = await self.session.scalar(
            select(GhgActivityRecord).where(
                GhgActivityRecord.inventory_code == inventory_code,
                GhgActivityRecord.record_code == record_code,
            )
        )
        if activity is None:
            msg = "温室气体活动记录不存在"
            raise ValueError(msg)
        validate_allocation_ratios(Decimal(str(item["allocation_ratio"])) for item in allocations)
        source = await self._ensure_source(activity)
        prepared: list[GhgActivityAllocation] = []
        for index, item in enumerate(allocations, 1):
            prepared.append(await self._prepare(activity, source, item, index))
        await self.session.execute(
            delete(GhgActivityAllocation).where(GhgActivityAllocation.activity_id == activity.id)
        )
        self.session.add_all(prepared)
        first = prepared[0]
        source.default_area_id = first.area_id
        source.default_equipment_id = first.equipment_id
        source.default_measurement_boundary_id = first.measurement_boundary_id
        source.default_allocation_role = first.allocation_role
        activity.emission_source_id = source.id
        if source.organization_boundary_id is not None:
            activity.organization_boundary_id = source.organization_boundary_id
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        return prepared

    async def _ensure_source(self, activity: GhgActivityRecord) -> GhgEmissionSource:
        if activity.emission_source_id is not None:
            current = await self.session.get(GhgEmissionSource, activity.emission_source_id)
            if current is not None:
                return current
        current = await self.session.scalar(
            select(GhgEmissionSource).where(
                GhgEmissionSource.inventory_code == activity.inventory_code,
                GhgEmissionSource.source_code == activity.source_code,
            )
        )
        if current is None:
            source_payload: dict[str, Any] = activity.source_payload or {}
            source_definition_value = source_payload.get("source_definition")
            source_definition = (
                cast("dict[str, Any]", source_definition_value) if isinstance(source_definition_value, dict) else {}
            )
            current = GhgEmissionSource(
                inventory_code=activity.inventory_code,
                organization_boundary_id=activity.organization_boundary_id,
                reporting_period_id=activity.reporting_period_id,
                organization_code=activity.organization_code,
                facility_code=activity.facility_code,
                source_code=activity.source_code,
                source_name=str(source_definition.get("source_name") or activity.activity_name),
                iso_category_code=activity.iso_category_code,
                source_mechanism=activity.source_mechanism,
                origin_kind="internal" if activity.value_chain_position == "own" else "external",
                default_allocation_role=CATEGORY_ALLOCATION_POLICY_BY_CODE[activity.iso_category_code].default_role,
                source_system=activity.source_system,
                source_payload=source_definition,
                status="active",
            )
            self.session.add(current)
            await self.session.flush()
        activity.emission_source_id = current.id
        return current

    async def _prepare(
        self,
        activity: GhgActivityRecord,
        source: GhgEmissionSource,
        item: dict[str, Any],
        index: int,
    ) -> GhgActivityAllocation:
        area = await self.session.get(carbon_models.MonitorSector, int(item["area_id"]))
        if area is None:
            msg = "归集区域不存在或不属于当前租户"
            raise ValueError(msg)
        equipment = None
        if item.get("equipment_id") is not None:
            equipment = await self.session.get(carbon_models.MonitorEquipment, int(item["equipment_id"]))
            if equipment is None:
                msg = "归集设备不存在或不属于当前租户"
                raise ValueError(msg)
            if equipment.sector_id is None or not await self._area_contains(area.id, equipment.sector_id):
                msg = "归集设备必须属于所选区域或其下级区域"
                raise ValueError(msg)
        measurement_boundary = None
        if item.get("measurement_boundary_id") is not None:
            measurement_boundary = await self.session.get(MeasurementBoundary, int(item["measurement_boundary_id"]))
            if measurement_boundary is None:
                msg = "计量边界不存在或不属于当前租户"
                raise ValueError(msg)
        external_code = _text(item.get("external_facility_code"))
        role = str(item["allocation_role"])
        validate_allocation(
            category_code=activity.iso_category_code,
            role=role,
            area_present=True,
            equipment_present=equipment is not None,
            external_present=external_code is not None,
        )
        await self._validate_organization_boundary(
            activity.organization_boundary_id, area.id, equipment.id if equipment else None
        )
        return GhgActivityAllocation(
            activity_id=activity.id,
            emission_source_id=source.id,
            allocation_code=str(item.get("allocation_code") or f"{activity.record_code}-A{index:02d}"),
            area_id=area.id,
            equipment_id=equipment.id if equipment else None,
            measurement_boundary_id=measurement_boundary.id if measurement_boundary else None,
            allocation_role=role,
            allocation_ratio=Decimal(str(item["allocation_ratio"])),
            external_facility_code=external_code,
            external_facility_name=_text(item.get("external_facility_name")),
            area_code_snapshot=area.code,
            area_name_snapshot=area.name or area.code,
            area_path_snapshot=await self._canonical_area_path(area),
            equipment_code_snapshot=equipment.code if equipment else None,
            equipment_name_snapshot=equipment.name if equipment else None,
            source_kind=str(item.get("source_kind") or "manual"),
            valid_from=_date(item.get("valid_from")),
            valid_to=_date(item.get("valid_to")),
            status="active",
        )

    async def _validate_organization_boundary(
        self,
        boundary_id: int | None,
        area_id: int,
        equipment_id: int | None,
    ) -> None:
        if boundary_id is None:
            return
        boundary = await self.session.get(carbon_models.OrganizationBoundary, boundary_id)
        if boundary is None or boundary.status != "published":
            msg = "活动必须引用已发布的组织边界"
            raise ValueError(msg)
        facilities = list(
            (
                await self.session.scalars(
                    select(carbon_models.BoundaryFacility).where(
                        carbon_models.BoundaryFacility.boundary_id == boundary_id,
                        carbon_models.BoundaryFacility.included.is_(True),
                    )
                )
            ).all()
        )
        concrete = [item for item in facilities if item.area_id is not None or item.equipment_id is not None]
        if not concrete:
            msg = "已发布组织边界尚未关联区域或设备, 请创建新版本后再归集"
            raise ValueError(msg)
        if equipment_id is not None and any(item.equipment_id == equipment_id for item in concrete):
            return
        for facility in concrete:
            if facility.area_id is not None and await self._area_contains(facility.area_id, area_id):
                return
        msg = "所选区域或设备不在已发布组织边界内"
        raise ValueError(msg)

    async def _area_contains(self, ancestor_id: int, area_id: int) -> bool:
        current_id: int | None = area_id
        seen: set[int] = set()
        while current_id is not None and current_id not in seen:
            if current_id == ancestor_id:
                return True
            seen.add(current_id)
            current = await self.session.get(carbon_models.MonitorSector, current_id)
            current_id = current.parent_id if current is not None else None
        return False

    async def _canonical_area_path(self, area: carbon_models.MonitorSector) -> str:
        codes: list[str] = []
        current: carbon_models.MonitorSector | None = area
        seen: set[int] = set()
        while current is not None and current.id not in seen:
            seen.add(current.id)
            codes.append(current.code)
            current = (
                await self.session.get(carbon_models.MonitorSector, current.parent_id) if current.parent_id else None
            )
        return "/" + "/".join(reversed(codes))


def _text(value: Any) -> str | None:
    return None if value in (None, "") else str(value).strip() or None


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, date) else date.fromisoformat(str(value))
