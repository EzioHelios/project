from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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
        conditions = []
        if query.status and query.status != "all":
            conditions.append(m.ReportingOrganization.status == query.status)
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append((m.ReportingOrganization.name.ilike(pattern)) | (m.ReportingOrganization.code.ilike(pattern)))
        stmt = select(m.ReportingOrganization).where(*conditions).order_by(m.ReportingOrganization.id.desc())
        return await self._page(stmt, m.ReportingOrganization, query)

    async def periods(self, query: OrganizationBoundaryQuery) -> dict[str, Any]:
        conditions = []
        if query.reporting_org_id is not None:
            conditions.append(m.ReportingPeriod.reporting_org_id == query.reporting_org_id)
        if query.status and query.status != "all":
            conditions.append(m.ReportingPeriod.status == query.status)
        stmt = select(m.ReportingPeriod).where(*conditions).order_by(m.ReportingPeriod.period_start.desc(), m.ReportingPeriod.id.desc())
        return await self._page(stmt, m.ReportingPeriod, query)

    async def boundaries(self, query: OrganizationBoundaryQuery) -> dict[str, Any]:
        conditions = []
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
        conditions = []
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

    async def _page(self, stmt: Any, model: type[Any], query: OrganizationBoundaryQuery, *, include_rows: bool = False) -> dict[str, Any]:
        total = int((await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
        rows = (await self._session.execute(stmt.limit(_limit(query.limit)).offset(max(0, query.offset)))).scalars().all()
        items = [model_to_dict(row) for row in rows]
        page = {"items": items, "data": items, "total": total, "limit": _limit(query.limit), "offset": max(0, query.offset)}
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


def _limit(value: int) -> int:
    return max(1, min(int(value or 50), 200))
