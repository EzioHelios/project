from __future__ import annotations

import datetime
from datetime import UTC, date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypeVar, cast

from sqlalchemy import delete, func, select

from app.db import models as m
from app.domain.organization_boundary.domain.policies import (
    validate_boundary_method,
    validate_boundary_status,
    validate_facility,
    validate_period_range,
    validate_period_status,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.organization_boundary.schemas import BoundaryEquipmentSelection, SaveBoundarySelectionRequest


ORG_FIELDS = {
    "code",
    "name",
    "enterprise_id",
    "organization_type",
    "legal_entity_code",
    "control_method",
    "equity_share_pct",
    "status",
    "source_name",
    "standard_code",
    "remark",
}
PERIOD_FIELDS = {
    "reporting_org_id",
    "code",
    "name",
    "period_type",
    "period_start",
    "period_end",
    "base_year",
    "status",
    "source_name",
    "standard_code",
    "remark",
}
BOUNDARY_FIELDS = {
    "reporting_org_id",
    "period_id",
    "boundary_no",
    "boundary_name",
    "boundary_type",
    "boundary_method",
    "operational_boundary",
    "version",
    "status",
    "source_name",
    "standard_code",
    "confidence_level",
    "remark",
}
FACILITY_FIELDS = {
    "boundary_id",
    "facility_type",
    "area_id",
    "equipment_id",
    "facility_code",
    "facility_name",
    "facility_role",
    "included",
    "exclusion_reason",
    "valid_from",
    "valid_to",
    "source_name",
    "remark",
}
DATE_FIELDS = {"period_start", "period_end", "valid_from", "valid_to"}
DECIMAL_FIELDS = {"equity_share_pct"}
MAX_SCOPE3_CATEGORY = 15
ModelT = TypeVar("ModelT")


class OrganizationBoundaryUseCase:
    """Application workflows for organization boundary commands."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_organization(self, data: dict[str, Any]) -> m.ReportingOrganization:
        payload = _payload(data, ORG_FIELDS, required={"code", "name"})
        validate_boundary_method(str(payload.get("control_method") or "operational_control"))
        obj = m.ReportingOrganization(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_organization(self, organization_id: int, data: dict[str, Any]) -> m.ReportingOrganization:
        obj = await self._get_or_raise(m.ReportingOrganization, organization_id, "报告主体不存在")
        payload = _payload(data, ORG_FIELDS)
        if "control_method" in payload:
            validate_boundary_method(str(payload["control_method"]))
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def delete_organization(self, organization_id: int) -> None:
        obj = await self._get_or_raise(m.ReportingOrganization, organization_id, "报告主体不存在")
        if await self._has_refs(m.ReportingPeriod, m.ReportingPeriod.reporting_org_id == obj.id):
            msg = "报告主体已有报告期, 请先清理报告期或将主体停用"
            raise ValueError(msg)
        if await self._has_refs(m.GhgCalculationRun, m.GhgCalculationRun.reporting_org_id == obj.id):
            msg = "报告主体已有核算运行引用, 请将主体停用"
            raise ValueError(msg)
        if await self._has_refs(m.GhgInventoryReport, m.GhgInventoryReport.reporting_org_id == obj.id):
            msg = "报告主体已有盘查报告引用, 请将主体停用"
            raise ValueError(msg)
        if await self._has_refs(m.CarbonVerificationProject, m.CarbonVerificationProject.reporting_org_id == obj.id):
            msg = "报告主体已有核查项目引用, 请将主体停用"
            raise ValueError(msg)
        await self._session.delete(obj)
        await self._session.commit()

    async def create_period(self, data: dict[str, Any]) -> m.ReportingPeriod:
        payload = _payload(data, PERIOD_FIELDS, required={"reporting_org_id", "code", "name", "period_start", "period_end"})
        await self._get_or_raise(m.ReportingOrganization, int(payload["reporting_org_id"]), "报告主体不存在")
        validate_period_range(payload["period_start"], payload["period_end"])
        validate_period_status(str(payload.get("status") or "draft"))
        obj = m.ReportingPeriod(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_period(self, period_id: int, data: dict[str, Any]) -> m.ReportingPeriod:
        obj = await self._get_or_raise(m.ReportingPeriod, period_id, "报告期不存在")
        if obj.status == "locked":
            msg = "已锁定报告期不可修改"
            raise ValueError(msg)
        payload = _payload(data, PERIOD_FIELDS - {"reporting_org_id"})
        period_start = payload.get("period_start", obj.period_start)
        period_end = payload.get("period_end", obj.period_end)
        validate_period_range(period_start, period_end)
        if "status" in payload:
            validate_period_status(str(payload["status"]))
            if payload["status"] == "locked":
                obj.locked_at = _utc_now_naive()
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def delete_period(self, period_id: int) -> None:
        obj = await self._get_or_raise(m.ReportingPeriod, period_id, "报告期不存在")
        if obj.status == "locked":
            msg = "已锁定报告期不可删除"
            raise ValueError(msg)
        if await self._has_refs(m.OrganizationBoundary, m.OrganizationBoundary.period_id == obj.id):
            msg = "报告期已有组织边界, 请先清理边界版本或归档报告期"
            raise ValueError(msg)
        if await self._has_refs(m.GhgActivityRecord, m.GhgActivityRecord.reporting_period_id == obj.id):
            msg = "报告期已有活动数据引用, 请归档报告期"
            raise ValueError(msg)
        if await self._has_refs(m.GhgCalculationRun, m.GhgCalculationRun.reporting_period_id == obj.id):
            msg = "报告期已有核算运行引用, 请归档报告期"
            raise ValueError(msg)
        if await self._has_refs(m.GhgInventoryReport, m.GhgInventoryReport.reporting_period_id == obj.id):
            msg = "报告期已有盘查报告引用, 请归档报告期"
            raise ValueError(msg)
        if await self._has_refs(m.CarbonVerificationProject, m.CarbonVerificationProject.period_id == obj.id):
            msg = "报告期已有核查项目引用, 请归档报告期"
            raise ValueError(msg)
        await self._session.delete(obj)
        await self._session.commit()

    async def create_boundary(self, data: dict[str, Any]) -> m.OrganizationBoundary:
        payload = _payload(data, BOUNDARY_FIELDS, required={"reporting_org_id", "period_id", "boundary_no", "boundary_name"})
        await self._get_or_raise(m.ReportingOrganization, int(payload["reporting_org_id"]), "报告主体不存在")
        period = await self._get_or_raise(m.ReportingPeriod, int(payload["period_id"]), "报告期不存在")
        if period.reporting_org_id != int(payload["reporting_org_id"]):
            msg = "报告期不属于所选报告主体"
            raise ValueError(msg)
        validate_boundary_method(str(payload.get("boundary_method") or "operational_control"))
        validate_boundary_status(str(payload.get("status") or "draft"))
        payload.setdefault("operational_boundary", _default_operational_boundary())
        if "version" not in payload:
            payload["version"] = await self._next_version(
                int(payload["reporting_org_id"]),
                int(payload["period_id"]),
                str(payload.get("boundary_type") or "organization"),
            )
        obj = m.OrganizationBoundary(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_boundary(self, boundary_id: int, data: dict[str, Any]) -> m.OrganizationBoundary:
        obj = await self._get_or_raise(m.OrganizationBoundary, boundary_id, "组织边界不存在")
        payload = _payload(data, BOUNDARY_FIELDS - {"reporting_org_id", "period_id"})
        if obj.status == "published" and set(payload) != {"status"}:
            msg = "已发布边界不可直接修改, 请创建新版本"
            raise ValueError(msg)
        if "boundary_method" in payload:
            validate_boundary_method(str(payload["boundary_method"]))
        if "status" in payload:
            validate_boundary_status(str(payload["status"]))
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def delete_boundary(self, boundary_id: int) -> None:
        obj = await self._get_or_raise(m.OrganizationBoundary, boundary_id, "组织边界不存在")
        if obj.status == "published":
            msg = "已发布边界不可删除, 请创建新版本或归档"
            raise ValueError(msg)
        if await self._has_refs(m.GhgActivityRecord, m.GhgActivityRecord.organization_boundary_id == obj.id):
            msg = "组织边界已有活动数据引用, 请归档边界版本"
            raise ValueError(msg)
        if await self._has_refs(m.GhgCalculationRun, m.GhgCalculationRun.organization_boundary_id == obj.id):
            msg = "组织边界已有核算运行引用, 请归档边界版本"
            raise ValueError(msg)
        if await self._has_refs(m.GhgInventoryReport, m.GhgInventoryReport.organization_boundary_id == obj.id):
            msg = "组织边界已有盘查报告引用, 请归档边界版本"
            raise ValueError(msg)
        if await self._has_refs(m.CarbonVerificationProject, m.CarbonVerificationProject.boundary_id == obj.id):
            msg = "组织边界已有核查项目引用, 请归档边界版本"
            raise ValueError(msg)
        await self._session.delete(obj)
        await self._session.commit()

    async def publish_boundary(self, boundary_id: int) -> m.OrganizationBoundary:
        obj = await self._get_or_raise(m.OrganizationBoundary, boundary_id, "组织边界不存在")
        if obj.status == "published":
            return obj
        facilities = (
            await self._session.execute(
                select(m.BoundaryFacility).where(m.BoundaryFacility.boundary_id == obj.id, m.BoundaryFacility.included.is_(True))
            )
        ).scalars().all()
        if not facilities:
            msg = "发布组织边界前至少需要一个纳入设施"
            raise ValueError(msg)
        _validate_operational_boundary(obj.operational_boundary)
        previous = (
            await self._session.execute(
                select(m.OrganizationBoundary).where(
                    m.OrganizationBoundary.reporting_org_id == obj.reporting_org_id,
                    m.OrganizationBoundary.period_id == obj.period_id,
                    m.OrganizationBoundary.boundary_type == obj.boundary_type,
                    m.OrganizationBoundary.status == "published",
                    m.OrganizationBoundary.id != obj.id,
                )
            )
        ).scalars().all()
        for item in previous:
            item.status = "superseded"
        obj.status = "published"
        obj.published_at = _utc_now_naive()
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def create_working_copy(self, boundary_id: int) -> m.OrganizationBoundary:
        """Return an existing draft or copy a published boundary into a new version."""
        source = await self._get_or_raise(m.OrganizationBoundary, boundary_id, "组织边界不存在")
        if source.status == "draft":
            return source
        existing = await self._session.scalar(
            select(m.OrganizationBoundary)
            .where(
                m.OrganizationBoundary.reporting_org_id == source.reporting_org_id,
                m.OrganizationBoundary.period_id == source.period_id,
                m.OrganizationBoundary.boundary_type == source.boundary_type,
                m.OrganizationBoundary.status == "draft",
            )
            .order_by(m.OrganizationBoundary.version.desc())
            .limit(1)
        )
        if existing is not None:
            return existing
        latest_version = await self._session.scalar(
            select(func.max(m.OrganizationBoundary.version)).where(
                m.OrganizationBoundary.reporting_org_id == source.reporting_org_id,
                m.OrganizationBoundary.period_id == source.period_id,
                m.OrganizationBoundary.boundary_type == source.boundary_type,
            )
        )
        next_version = int(latest_version or source.version) + 1
        draft = m.OrganizationBoundary(
            reporting_org_id=source.reporting_org_id,
            period_id=source.period_id,
            boundary_no=_next_boundary_no(source.boundary_no, next_version),
            boundary_name=source.boundary_name,
            boundary_type=source.boundary_type,
            boundary_method=source.boundary_method,
            operational_boundary=dict(source.operational_boundary or {}),
            version=next_version,
            status="draft",
            source_name=source.source_name,
            standard_code=source.standard_code,
            confidence_level=source.confidence_level,
            remark=source.remark,
        )
        self._session.add(draft)
        await self._session.flush()
        facilities = (
            await self._session.execute(
                select(m.BoundaryFacility).where(m.BoundaryFacility.boundary_id == source.id)
            )
        ).scalars().all()
        for item in facilities:
            self._session.add(
                m.BoundaryFacility(
                    boundary_id=draft.id,
                    facility_type=item.facility_type,
                    area_id=item.area_id,
                    equipment_id=item.equipment_id,
                    facility_code=item.facility_code,
                    facility_name=item.facility_name,
                    facility_role=item.facility_role,
                    included=item.included,
                    exclusion_reason=item.exclusion_reason,
                    valid_from=item.valid_from,
                    valid_to=item.valid_to,
                    source_name=item.source_name,
                    remark=item.remark,
                )
            )
        await self._session.commit()
        await self._session.refresh(draft)
        return draft

    async def save_selection(
        self,
        boundary_id: int,
        data: SaveBoundarySelectionRequest,
    ) -> m.OrganizationBoundary:
        """Replace the resource and standards selection of one draft atomically."""
        boundary = await self._get_or_raise(m.OrganizationBoundary, boundary_id, "组织边界不存在")
        if boundary.status != "draft":
            msg = "已发布边界不可修改, 请先创建工作草稿"
            raise ValueError(msg)
        operational_boundary = _operational_boundary_payload(data)
        _validate_operational_boundary(operational_boundary)
        if not any(area_item.included for area_item in data.areas) and not any(
            equipment_item.included for equipment_item in data.equipment
        ):
            msg = "核算边界至少需要一个纳入区域或设备"
            raise ValueError(msg)

        areas: dict[int, m.MonitorSector] = {}
        for area_item in data.areas:
            area = await self._get_or_raise(m.MonitorSector, area_item.area_id, "区域不存在")
            if not area_item.included and not str(area_item.exclusion_reason or "").strip():
                msg = "排除区域必须填写排除原因"
                raise ValueError(msg)
            areas[area.id] = area

        equipment_rows: list[tuple[BoundaryEquipmentSelection, m.MonitorEquipment, m.MonitorSector]] = []
        for equipment_item in data.equipment:
            equipment = await self._get_or_raise(m.MonitorEquipment, equipment_item.equipment_id, "设备不存在")
            equipment_area = areas.get(equipment_item.area_id)
            if equipment_area is None:
                equipment_area = await self._get_or_raise(m.MonitorSector, equipment_item.area_id, "区域不存在")
            if equipment.sector_id != equipment_area.id:
                msg = "设备不属于所选区域"
                raise ValueError(msg)
            if not equipment_item.included and not str(equipment_item.exclusion_reason or "").strip():
                msg = "排除设备必须填写排除原因"
                raise ValueError(msg)
            equipment_rows.append((equipment_item, equipment, equipment_area))

        await self._session.execute(delete(m.BoundaryFacility).where(m.BoundaryFacility.boundary_id == boundary.id))
        boundary.operational_boundary = operational_boundary
        period = await self._get_or_raise(m.ReportingPeriod, boundary.period_id, "报告期不存在")
        for area_item in data.areas:
            area = areas[area_item.area_id]
            self._session.add(
                m.BoundaryFacility(
                    boundary_id=boundary.id,
                    facility_type="area",
                    area_id=area.id,
                    facility_code=area.code,
                    facility_name=area.name or area.code,
                    facility_role="operational_boundary",
                    included=area_item.included,
                    exclusion_reason=area_item.exclusion_reason,
                    valid_from=period.period_start,
                    valid_to=period.period_end,
                    source_name="组织碳核算边界配置",
                )
            )
        for equipment_item, equipment, area in equipment_rows:
            self._session.add(
                m.BoundaryFacility(
                    boundary_id=boundary.id,
                    facility_type="equipment",
                    area_id=area.id,
                    equipment_id=equipment.id,
                    facility_code=equipment.code,
                    facility_name=equipment.name or equipment.code,
                    facility_role="operational_boundary",
                    included=equipment_item.included,
                    exclusion_reason=equipment_item.exclusion_reason,
                    valid_from=period.period_start,
                    valid_to=period.period_end,
                    source_name="组织碳核算边界配置",
                )
            )
        await self._session.commit()
        await self._session.refresh(boundary)
        return boundary

    async def discard_draft(self, boundary_id: int) -> None:
        boundary = await self._get_or_raise(m.OrganizationBoundary, boundary_id, "组织边界不存在")
        if boundary.status != "draft":
            msg = "只能放弃工作草稿"
            raise ValueError(msg)
        await self._session.delete(boundary)
        await self._session.commit()

    async def create_source_facility(self, boundary_id: int) -> m.BoundaryFacility:
        boundary = await self._get_or_raise(m.OrganizationBoundary, boundary_id, "组织边界不存在")
        if boundary.status == "published":
            msg = "已发布边界不可新增设施, 请创建新版本"
            raise ValueError(msg)
        existing = (
            await self._session.execute(
                select(m.BoundaryFacility).where(
                    m.BoundaryFacility.boundary_id == boundary.id,
                    m.BoundaryFacility.facility_code == boundary.boundary_no,
                    m.BoundaryFacility.included.is_(True),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        facility = m.BoundaryFacility(
            boundary_id=boundary.id,
            facility_type="enterprise",
            facility_code=boundary.boundary_no,
            facility_name=boundary.boundary_name,
            facility_role="source_boundary",
            included=True,
            valid_from=boundary.period.period_start if boundary.period else None,
            valid_to=boundary.period.period_end if boundary.period else None,
            source_name=boundary.source_name,
            remark="由资料包边界生成的纳入设施",
        )
        self._session.add(facility)
        await self._session.commit()
        await self._session.refresh(facility)
        return facility

    async def create_facility(self, data: dict[str, Any]) -> m.BoundaryFacility:
        payload = _payload(data, FACILITY_FIELDS, required={"boundary_id"})
        boundary = await self._get_or_raise(m.OrganizationBoundary, int(payload["boundary_id"]), "组织边界不存在")
        if boundary.status == "published":
            msg = "已发布边界不可新增设施, 请创建新版本"
            raise ValueError(msg)
        validate_facility(payload)
        obj = m.BoundaryFacility(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_facility(self, facility_id: int, data: dict[str, Any]) -> m.BoundaryFacility:
        obj = await self._get_or_raise(m.BoundaryFacility, facility_id, "边界设施不存在")
        boundary = await self._get_or_raise(m.OrganizationBoundary, obj.boundary_id, "组织边界不存在")
        if boundary.status == "published":
            msg = "已发布边界不可修改设施, 请创建新版本"
            raise ValueError(msg)
        payload = _payload(data, FACILITY_FIELDS - {"boundary_id"})
        next_payload = {**{key: getattr(obj, key) for key in FACILITY_FIELDS if hasattr(obj, key)}, **payload}
        validate_facility(next_payload)
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def delete_facility(self, facility_id: int) -> None:
        obj = await self._get_or_raise(m.BoundaryFacility, facility_id, "边界设施不存在")
        boundary = await self._get_or_raise(m.OrganizationBoundary, obj.boundary_id, "组织边界不存在")
        if boundary.status == "published":
            msg = "已发布边界不可删除设施, 请创建新版本"
            raise ValueError(msg)
        await self._session.delete(obj)
        await self._session.commit()

    async def _get_or_raise(self, model: type[ModelT], item_id: int, message: str) -> ModelT:
        obj = await self._session.get(model, item_id)
        if obj is None:
            raise ValueError(message)
        return obj

    async def _has_refs(self, model: type[Any], *conditions: Any) -> bool:
        count = await self._session.scalar(select(func.count()).select_from(model).where(*conditions))
        return bool(count)

    async def _next_version(self, reporting_org_id: int, period_id: int, boundary_type: str) -> int:
        latest_version = await self._session.scalar(
            select(func.max(m.OrganizationBoundary.version)).where(
                m.OrganizationBoundary.reporting_org_id == reporting_org_id,
                m.OrganizationBoundary.period_id == period_id,
                m.OrganizationBoundary.boundary_type == boundary_type,
            )
        )
        return int(latest_version or 0) + 1


def _payload(data: dict[str, Any], fields: set[str], required: set[str] | None = None) -> dict[str, Any]:
    payload = {key: _coerce_value(key, value) for key, value in data.items() if key in fields and value is not None}
    for key in required or set():
        if payload.get(key) in (None, ""):
            msg = f"{key} 不能为空"
            raise ValueError(msg)
    return payload


def _coerce_value(key: str, value: Any) -> Any:
    if key in DATE_FIELDS and isinstance(value, str):
        return date.fromisoformat(value)
    if key in DECIMAL_FIELDS and value not in (None, ""):
        return Decimal(str(value))
    return value


def _assign(obj: Any, payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        setattr(obj, key, value)


def _utc_now_naive() -> datetime.datetime:
    return datetime.datetime.now(UTC).replace(tzinfo=None)


def _next_boundary_no(current: str, version: int) -> str:
    base = current.rsplit("-V", maxsplit=1)[0]
    return f"{base}-V{version}"


def _operational_boundary_payload(data: SaveBoundarySelectionRequest) -> dict[str, Any]:
    selection = data.operational_boundary
    return {
        "schemaVersion": selection.schema_version,
        "scopes": list(dict.fromkeys(selection.scopes)),
        "scope2Methods": list(dict.fromkeys(selection.scope2_methods)),
        "isoCategories": list(dict.fromkeys(selection.iso_categories)),
        "scope3Categories": list(dict.fromkeys(selection.scope3_categories)),
    }


def _validate_operational_boundary(value: dict[str, Any] | None) -> None:
    payload = value or {}
    scopes = _string_values(payload.get("scopes"))
    if not scopes:
        msg = "核算边界至少需要一个Scope"
        raise ValueError(msg)
    if not scopes <= {"scope1", "scope2", "scope3"}:
        msg = "Scope取值不支持"
        raise ValueError(msg)
    scope2_methods = _string_values(payload.get("scope2Methods"))
    if not scope2_methods <= {"location", "market"}:
        msg = "Scope 2方法取值不支持"
        raise ValueError(msg)
    if "scope2" in scopes and not scope2_methods:
        msg = "选择Scope 2时至少需要一种核算方法"
        raise ValueError(msg)
    iso_categories = _string_values(payload.get("isoCategories"))
    if not iso_categories <= {"1", "2", "3", "4", "5", "6"}:
        msg = "ISO 14064-1类别取值不支持"
        raise ValueError(msg)
    raw_scope3_categories = payload.get("scope3Categories")
    scope3_categories = cast("list[object]", raw_scope3_categories) if isinstance(raw_scope3_categories, list) else []
    if any(not isinstance(item, int) or item < 1 or item > MAX_SCOPE3_CATEGORY for item in scope3_categories):
        msg = "Scope 3类别取值应为1至15"
        raise ValueError(msg)


def _default_operational_boundary() -> dict[str, Any]:
    return {
        "schemaVersion": "organization-boundary-v1",
        "scopes": ["scope1", "scope2", "scope3"],
        "scope2Methods": ["location"],
        "isoCategories": ["1", "2", "3", "4", "5", "6"],
        "scope3Categories": [1, 2, 3, 4, 5, 6],
    }


def _string_values(value: Any) -> set[str]:
    items = cast("list[object]", value) if isinstance(value, list) else []
    return {str(item) for item in items}
