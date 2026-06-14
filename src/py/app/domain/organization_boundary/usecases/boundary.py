from __future__ import annotations

import datetime
from datetime import UTC, date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

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

    async def create_boundary(self, data: dict[str, Any]) -> m.OrganizationBoundary:
        payload = _payload(data, BOUNDARY_FIELDS, required={"reporting_org_id", "period_id", "boundary_no", "boundary_name"})
        await self._get_or_raise(m.ReportingOrganization, int(payload["reporting_org_id"]), "报告主体不存在")
        period = await self._get_or_raise(m.ReportingPeriod, int(payload["period_id"]), "报告期不存在")
        if period.reporting_org_id != int(payload["reporting_org_id"]):
            msg = "报告期不属于所选报告主体"
            raise ValueError(msg)
        validate_boundary_method(str(payload.get("boundary_method") or "operational_control"))
        validate_boundary_status(str(payload.get("status") or "draft"))
        obj = m.OrganizationBoundary(**payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update_boundary(self, boundary_id: int, data: dict[str, Any]) -> m.OrganizationBoundary:
        obj = await self._get_or_raise(m.OrganizationBoundary, boundary_id, "组织边界不存在")
        if obj.status == "published":
            msg = "已发布边界不可直接修改, 请创建新版本"
            raise ValueError(msg)
        payload = _payload(data, BOUNDARY_FIELDS - {"reporting_org_id", "period_id"})
        if "boundary_method" in payload:
            validate_boundary_method(str(payload["boundary_method"]))
        if "status" in payload:
            validate_boundary_status(str(payload["status"]))
        _assign(obj, payload)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

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
        obj.status = "published"
        obj.published_at = _utc_now_naive()
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

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

    async def _get_or_raise(self, model: type[Any], item_id: int, message: str) -> Any:
        obj = await self._session.get(model, item_id)
        if obj is None:
            raise ValueError(message)
        return obj


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
