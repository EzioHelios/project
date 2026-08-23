from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import func, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict
from app.domain.organization_boundary.schemas import (
    BoundaryAreaResponse,
    BoundaryDiffResponse,
    BoundaryEquipmentResponse,
    BoundarySelectionChange,
    BoundarySelectionResponse,
    BoundaryVersionResponse,
    OperationalBoundarySelection,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement


@dataclass(frozen=True, slots=True)
class OrganizationBoundaryQuery:
    reporting_org_id: int | None = None
    period_id: int | None = None
    boundary_id: int | None = None
    status: str | None = None
    keyword: str | None = None
    limit: int = 50
    offset: int = 0


class OrganizationBoundaryQueryService:
    """Read models for organization boundary management."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def organizations(self, query: OrganizationBoundaryQuery) -> dict[str, Any]:
        conditions: list[ColumnElement[bool]] = []
        if query.status and query.status != "all":
            conditions.append(m.ReportingOrganization.status == query.status)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append((m.ReportingOrganization.name.ilike(pattern)) | (m.ReportingOrganization.code.ilike(pattern)))
        stmt = select(m.ReportingOrganization).where(*conditions).order_by(m.ReportingOrganization.id.desc())
        return await self._page(stmt, m.ReportingOrganization, query)

    async def periods(self, query: OrganizationBoundaryQuery) -> dict[str, Any]:
        conditions: list[ColumnElement[bool]] = []
        if query.reporting_org_id is not None:
            conditions.append(m.ReportingPeriod.reporting_org_id == query.reporting_org_id)
        if query.status and query.status != "all":
            conditions.append(m.ReportingPeriod.status == query.status)
        stmt = select(m.ReportingPeriod).where(*conditions).order_by(m.ReportingPeriod.period_start.desc(), m.ReportingPeriod.id.desc())
        return await self._page(stmt, m.ReportingPeriod, query)

    async def boundaries(self, query: OrganizationBoundaryQuery) -> dict[str, Any]:
        conditions: list[ColumnElement[bool]] = []
        if query.reporting_org_id is not None:
            conditions.append(m.OrganizationBoundary.reporting_org_id == query.reporting_org_id)
        if query.period_id is not None:
            conditions.append(m.OrganizationBoundary.period_id == query.period_id)
        if query.status and query.status != "all":
            conditions.append(m.OrganizationBoundary.status == query.status)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append((m.OrganizationBoundary.boundary_name.ilike(pattern)) | (m.OrganizationBoundary.boundary_no.ilike(pattern)))
        stmt = select(m.OrganizationBoundary).where(*conditions).order_by(m.OrganizationBoundary.id.desc())
        page = await self._page(stmt, m.OrganizationBoundary, query, include_rows=True)
        page["items"] = [await self._boundary_payload(row) for row in page.pop("_rows")]
        page["data"] = page["items"]
        return page

    async def facilities(self, query: OrganizationBoundaryQuery) -> dict[str, Any]:
        conditions: list[ColumnElement[bool]] = []
        if query.boundary_id is not None:
            conditions.append(m.BoundaryFacility.boundary_id == query.boundary_id)
        stmt = select(m.BoundaryFacility).where(*conditions).order_by(m.BoundaryFacility.included.desc(), m.BoundaryFacility.id.desc())
        return await self._page(stmt, m.BoundaryFacility, query)

    async def summary(self) -> dict[str, Any]:
        org_count = await self._count(m.ReportingOrganization)
        period_count = await self._count(m.ReportingPeriod)
        boundary_count = await self._count(m.OrganizationBoundary)
        published_count = await self._count(m.OrganizationBoundary, m.OrganizationBoundary.status == "published")
        facility_count = await self._count(m.BoundaryFacility)
        active_boundary = await self._session.scalar(
            select(m.OrganizationBoundary).where(m.OrganizationBoundary.status == "published").order_by(m.OrganizationBoundary.id.desc()).limit(1)
        )
        return {
            "organization_count": org_count,
            "period_count": period_count,
            "boundary_count": boundary_count,
            "published_boundary_count": published_count,
            "facility_count": facility_count,
            "active_boundary": await self._boundary_payload(active_boundary) if active_boundary else None,
        }

    async def selection(self, boundary_id: int) -> BoundarySelectionResponse:
        boundary = await self._session.get(m.OrganizationBoundary, boundary_id)
        if boundary is None:
            msg = "组织边界不存在"
            raise ValueError(msg)
        facilities = (
            await self._session.execute(
                select(m.BoundaryFacility)
                .where(m.BoundaryFacility.boundary_id == boundary.id)
                .order_by(m.BoundaryFacility.facility_type, m.BoundaryFacility.id)
            )
        ).scalars().all()
        operational = boundary.operational_boundary or {}
        return BoundarySelectionResponse(
            boundary=_boundary_version_response(boundary),
            operational_boundary=OperationalBoundarySelection(
                schema_version=str(operational.get("schemaVersion") or "organization-boundary-v1"),
                scopes=_string_list(operational.get("scopes")),
                scope2_methods=_string_list(operational.get("scope2Methods")),
                iso_categories=_string_list(operational.get("isoCategories")),
                scope3_categories=_int_list(operational.get("scope3Categories")),
            ),
            areas=[
                BoundaryAreaResponse(
                    area_id=int(item.area_id),
                    code=item.facility_code or str(item.area_id),
                    name=item.facility_name or item.facility_code or str(item.area_id),
                    included=item.included,
                    exclusion_reason=item.exclusion_reason,
                )
                for item in facilities
                if item.facility_type == "area" and item.area_id is not None
            ],
            equipment=[
                BoundaryEquipmentResponse(
                    equipment_id=int(item.equipment_id),
                    area_id=int(item.area_id),
                    code=item.facility_code or str(item.equipment_id),
                    name=item.facility_name or item.facility_code or str(item.equipment_id),
                    included=item.included,
                    exclusion_reason=item.exclusion_reason,
                )
                for item in facilities
                if item.facility_type == "equipment" and item.equipment_id is not None and item.area_id is not None
            ],
        )

    async def diff(self, boundary_id: int, against_boundary_id: int | None = None) -> BoundaryDiffResponse:
        current = await self._session.get(m.OrganizationBoundary, boundary_id)
        if current is None:
            msg = "组织边界不存在"
            raise ValueError(msg)
        against = await self._session.get(m.OrganizationBoundary, against_boundary_id) if against_boundary_id else None
        if against_boundary_id is None:
            against = await self._session.scalar(
                select(m.OrganizationBoundary)
                .where(
                    m.OrganizationBoundary.reporting_org_id == current.reporting_org_id,
                    m.OrganizationBoundary.period_id == current.period_id,
                    m.OrganizationBoundary.boundary_type == current.boundary_type,
                    m.OrganizationBoundary.version < current.version,
                )
                .order_by(m.OrganizationBoundary.version.desc())
                .limit(1)
            )
        if against_boundary_id is not None and against is None:
            msg = "对比边界不存在"
            raise ValueError(msg)
        changes: list[BoundarySelectionChange] = []
        current_operational = current.operational_boundary or {}
        against_operational = (against.operational_boundary or {}) if against is not None else {}
        operational_keys = ("scopes", "scope2Methods", "isoCategories", "scope3Categories")
        for key in operational_keys:
            operational_before = _operational_values(against_operational, key)
            operational_after = _operational_values(current_operational, key)
            if operational_before != operational_after:
                changes.append(
                    BoundarySelectionChange(
                        key=f"operationalBoundary.{key}",
                        change_type="changed",
                        before=operational_before,
                        after=operational_after,
                    )
                )
        current_facilities = await self._facility_map(current.id)
        against_facilities = await self._facility_map(against.id) if against is not None else {}
        for key in sorted(current_facilities.keys() | against_facilities.keys()):
            facility_before = against_facilities.get(key)
            facility_after = current_facilities.get(key)
            if facility_before is None:
                changes.append(BoundarySelectionChange(key=key, change_type="added", before=None, after=facility_after))
            elif facility_after is None:
                changes.append(BoundarySelectionChange(key=key, change_type="removed", before=facility_before, after=None))
            elif facility_before != facility_after:
                changes.append(BoundarySelectionChange(key=key, change_type="changed", before=facility_before, after=facility_after))
        return BoundaryDiffResponse(
            boundary_id=current.id,
            against_boundary_id=against.id if against is not None else None,
            changes=changes,
        )

    async def _page(self, stmt: Any, model: type[Any], query: OrganizationBoundaryQuery, *, include_rows: bool = False) -> dict[str, Any]:
        total = int((await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await self._session.execute(stmt.limit(_limit(query.limit)).offset(max(0, query.offset)))).scalars().all()
        items = [model_to_dict(row) for row in rows]
        page: dict[str, Any] = {
            "items": items,
            "data": items,
            "total": total,
            "limit": _limit(query.limit),
            "offset": max(0, query.offset),
        }
        if include_rows:
            page["_rows"] = rows
        return page

    async def _boundary_payload(self, row: m.OrganizationBoundary | None) -> dict[str, Any]:
        if row is None:
            return {}
        payload = model_to_dict(row)
        payload["facility_count"] = await self._count(m.BoundaryFacility, m.BoundaryFacility.boundary_id == row.id)
        payload["included_facility_count"] = await self._count(
            m.BoundaryFacility,
            m.BoundaryFacility.boundary_id == row.id,
            m.BoundaryFacility.included.is_(True),
        )
        payload["excluded_facility_count"] = await self._count(
            m.BoundaryFacility,
            m.BoundaryFacility.boundary_id == row.id,
            m.BoundaryFacility.included.is_(False),
        )
        return payload

    async def _count(self, model: type[Any], *conditions: Any) -> int:
        return int((await self._session.execute(select(func.count()).select_from(model).where(*conditions))).scalar_one() or 0)

    async def _facility_map(self, boundary_id: int) -> dict[str, str]:
        facilities = (
            await self._session.execute(select(m.BoundaryFacility).where(m.BoundaryFacility.boundary_id == boundary_id))
        ).scalars().all()
        return {
            f"{item.facility_type}:{item.equipment_id if item.facility_type == 'equipment' else item.area_id}": (
                f"{item.included}:{item.exclusion_reason or ''}"
            )
            for item in facilities
            if item.facility_type in {"area", "equipment"}
        }


def _limit(value: int) -> int:
    return max(1, min(int(value or 50), 200))


def _boundary_version_response(boundary: m.OrganizationBoundary) -> BoundaryVersionResponse:
    return BoundaryVersionResponse(
        id=boundary.id,
        reporting_org_id=boundary.reporting_org_id,
        period_id=boundary.period_id,
        boundary_no=boundary.boundary_no,
        boundary_name=boundary.boundary_name,
        boundary_type=boundary.boundary_type,
        boundary_method=boundary.boundary_method,
        version=boundary.version,
        status=boundary.status,
        published_at=boundary.published_at.isoformat() if boundary.published_at else None,
    )


def _operational_values(payload: dict[str, Any], key: str) -> list[str]:
    return _string_list(payload.get(key))


def _string_list(value: Any) -> list[str]:
    items = cast("list[object]", value) if isinstance(value, list) else []
    return [str(item) for item in items]


def _int_list(value: Any) -> list[int]:
    items = cast("list[object]", value) if isinstance(value, list) else []
    return [int(str(item)) for item in items]
