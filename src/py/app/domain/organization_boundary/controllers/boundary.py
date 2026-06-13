from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, delete, get, patch, post
from litestar.params import Body
from litestar.response import Response

from app.domain.energy.controllers._utils import model_to_dict, ok_data
from app.domain.organization_boundary.queries.boundary import (
    OrganizationBoundaryQuery,
    OrganizationBoundaryQueryService,
)
from app.domain.organization_boundary.usecases.boundary import OrganizationBoundaryUseCase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


BOUNDARY_BODY = Body()


class OrganizationBoundaryController(Controller):
    tags = ["Organization Boundary"]

    @get("/api/carbon/organization-boundary/summary")
    async def get_summary(self, db_session: AsyncSession) -> Response[dict]:
        data = await OrganizationBoundaryQueryService(db_session).summary()
        return Response(content=ok_data(data))

    @get("/api/carbon/organization-boundary/organizations")
    async def list_organizations(
        self,
        db_session: AsyncSession,
        status: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await OrganizationBoundaryQueryService(db_session).organizations(_query(status=status, keyword=keyword, limit=limit, offset=offset))
        return Response(content=ok_data(data))

    @post("/api/carbon/organization-boundary/organizations")
    async def create_organization(self, db_session: AsyncSession, data: dict = BOUNDARY_BODY) -> Response[dict]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).create_organization(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/organization-boundary/organizations/{organization_id:int}")
    async def update_organization(self, db_session: AsyncSession, organization_id: int, data: dict = BOUNDARY_BODY) -> Response[dict]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).update_organization(organization_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/organization-boundary/periods")
    async def list_periods(
        self,
        db_session: AsyncSession,
        reporting_org_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await OrganizationBoundaryQueryService(db_session).periods(
            _query(reporting_org_id=reporting_org_id, status=status, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/organization-boundary/periods")
    async def create_period(self, db_session: AsyncSession, data: dict = BOUNDARY_BODY) -> Response[dict]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).create_period(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/organization-boundary/periods/{period_id:int}")
    async def update_period(self, db_session: AsyncSession, period_id: int, data: dict = BOUNDARY_BODY) -> Response[dict]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).update_period(period_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/organization-boundary/boundaries")
    async def list_boundaries(
        self,
        db_session: AsyncSession,
        reporting_org_id: int | None = None,
        period_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await OrganizationBoundaryQueryService(db_session).boundaries(
            _query(reporting_org_id=reporting_org_id, period_id=period_id, status=status, keyword=keyword, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/organization-boundary/boundaries")
    async def create_boundary(self, db_session: AsyncSession, data: dict = BOUNDARY_BODY) -> Response[dict]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).create_boundary(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/organization-boundary/boundaries/{boundary_id:int}")
    async def update_boundary(self, db_session: AsyncSession, boundary_id: int, data: dict = BOUNDARY_BODY) -> Response[dict]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).update_boundary(boundary_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @post("/api/carbon/organization-boundary/boundaries/{boundary_id:int}/publish")
    async def publish_boundary(self, db_session: AsyncSession, boundary_id: int) -> Response[dict]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).publish_boundary(boundary_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/organization-boundary/facilities")
    async def list_facilities(
        self,
        db_session: AsyncSession,
        boundary_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await OrganizationBoundaryQueryService(db_session).facilities(_query(boundary_id=boundary_id, limit=limit, offset=offset))
        return Response(content=ok_data(data))

    @post("/api/carbon/organization-boundary/facilities")
    async def create_facility(self, db_session: AsyncSession, data: dict = BOUNDARY_BODY) -> Response[dict]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).create_facility(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch("/api/carbon/organization-boundary/facilities/{facility_id:int}")
    async def update_facility(self, db_session: AsyncSession, facility_id: int, data: dict = BOUNDARY_BODY) -> Response[dict]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).update_facility(facility_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @delete("/api/carbon/organization-boundary/facilities/{facility_id:int}")
    async def delete_facility(self, db_session: AsyncSession, facility_id: int) -> Response[dict]:
        try:
            await OrganizationBoundaryUseCase(db_session).delete_facility(facility_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data({"deleted": True}))


def _query(
    *,
    reporting_org_id: int | None = None,
    period_id: int | None = None,
    boundary_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> OrganizationBoundaryQuery:
    return OrganizationBoundaryQuery(
        reporting_org_id=reporting_org_id,
        period_id=period_id,
        boundary_id=boundary_id,
        status=status,
        keyword=keyword,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
    )


def _error(exc: ValueError) -> Response[dict]:
    message = str(exc)
    status_code = 404 if "不存在" in message else 400
    return Response(content={"code": status_code, "msg": message}, status_code=status_code)
