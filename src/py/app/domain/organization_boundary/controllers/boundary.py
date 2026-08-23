from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, delete, get, patch, post, put
from litestar.exceptions import ClientException
from litestar.params import Body
from litestar.response import Response

from app.domain.accounts.guards import requires_permission
from app.domain.energy.controllers._utils import model_to_dict, ok_data
from app.domain.organization_boundary.queries.boundary import (
    OrganizationBoundaryQuery,
    OrganizationBoundaryQueryService,
)
from app.domain.organization_boundary.schemas import (
    BoundaryDiffResponse,  # noqa: TC001 - Litestar resolves runtime annotations
    BoundarySelectionResponse,  # noqa: TC001 - Litestar resolves runtime annotations
    SaveBoundarySelectionRequest,  # noqa: TC001 - Litestar resolves runtime annotations
)
from app.domain.organization_boundary.usecases.boundary import OrganizationBoundaryUseCase
from app.lib.schema import Message

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


BOUNDARY_BODY = Body()


class OrganizationBoundaryController(Controller):
    tags = ["Organization Boundary"]
    guards = [requires_permission("carbon.inventory.view")]

    @get("/api/carbon/organization-boundary/summary", operation_id="OrganizationBoundaryGetSummary")
    async def get_summary(self, db_session: AsyncSession) -> Response[dict[str, object]]:
        data = await OrganizationBoundaryQueryService(db_session).summary()
        return Response(content=ok_data(data))

    @get("/api/carbon/organization-boundary/organizations", operation_id="OrganizationBoundaryListOrganizations")
    async def list_organizations(
        self,
        db_session: AsyncSession,
        status: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict[str, object]]:
        data = await OrganizationBoundaryQueryService(db_session).organizations(
            _query(status=status, keyword=keyword, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post(
        "/api/carbon/organization-boundary/organizations",
        operation_id="OrganizationBoundaryCreateOrganization",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def create_organization(
        self, db_session: AsyncSession, data: dict[str, object] = BOUNDARY_BODY
    ) -> Response[dict[str, object]]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).create_organization(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch(
        "/api/carbon/organization-boundary/organizations/{organization_id:int}",
        operation_id="OrganizationBoundaryUpdateOrganization",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def update_organization(
        self,
        db_session: AsyncSession,
        organization_id: int,
        data: dict[str, object] = BOUNDARY_BODY,
    ) -> Response[dict[str, object]]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).update_organization(organization_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/organization-boundary/periods", operation_id="OrganizationBoundaryListPeriods")
    async def list_periods(
        self,
        db_session: AsyncSession,
        reporting_org_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict[str, object]]:
        data = await OrganizationBoundaryQueryService(db_session).periods(
            _query(reporting_org_id=reporting_org_id, status=status, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post(
        "/api/carbon/organization-boundary/periods",
        operation_id="OrganizationBoundaryCreatePeriod",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def create_period(
        self, db_session: AsyncSession, data: dict[str, object] = BOUNDARY_BODY
    ) -> Response[dict[str, object]]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).create_period(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch(
        "/api/carbon/organization-boundary/periods/{period_id:int}",
        operation_id="OrganizationBoundaryUpdatePeriod",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def update_period(
        self,
        db_session: AsyncSession,
        period_id: int,
        data: dict[str, object] = BOUNDARY_BODY,
    ) -> Response[dict[str, object]]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).update_period(period_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/organization-boundary/boundaries", operation_id="OrganizationBoundaryListBoundaries")
    async def list_boundaries(
        self,
        db_session: AsyncSession,
        reporting_org_id: int | None = None,
        period_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict[str, object]]:
        data = await OrganizationBoundaryQueryService(db_session).boundaries(
            _query(
                reporting_org_id=reporting_org_id,
                period_id=period_id,
                status=status,
                keyword=keyword,
                limit=limit,
                offset=offset,
            )
        )
        return Response(content=ok_data(data))

    @post(
        "/api/carbon/organization-boundary/boundaries",
        operation_id="OrganizationBoundaryCreateBoundary",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def create_boundary(
        self, db_session: AsyncSession, data: dict[str, object] = BOUNDARY_BODY
    ) -> Response[dict[str, object]]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).create_boundary(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch(
        "/api/carbon/organization-boundary/boundaries/{boundary_id:int}",
        operation_id="OrganizationBoundaryUpdateBoundary",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def update_boundary(
        self,
        db_session: AsyncSession,
        boundary_id: int,
        data: dict[str, object] = BOUNDARY_BODY,
    ) -> Response[dict[str, object]]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).update_boundary(boundary_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @post(
        "/api/carbon/organization-boundary/boundaries/{boundary_id:int}/publish",
        operation_id="OrganizationBoundaryPublish",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def publish_boundary(self, db_session: AsyncSession, boundary_id: int) -> Response[dict[str, object]]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).publish_boundary(boundary_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get(
        "/api/carbon/organization-boundary/boundaries/{boundary_id:int}/selection",
        operation_id="OrganizationBoundaryGetSelection",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def get_selection(self, db_session: AsyncSession, boundary_id: int) -> BoundarySelectionResponse:
        try:
            return await OrganizationBoundaryQueryService(db_session).selection(boundary_id)
        except ValueError as exc:
            raise _client_error(exc) from exc

    @post(
        "/api/carbon/organization-boundary/boundaries/{boundary_id:int}/working-copy",
        operation_id="OrganizationBoundaryCreateWorkingCopy",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def create_working_copy(self, db_session: AsyncSession, boundary_id: int) -> BoundarySelectionResponse:
        try:
            draft = await OrganizationBoundaryUseCase(db_session).create_working_copy(boundary_id)
            return await OrganizationBoundaryQueryService(db_session).selection(draft.id)
        except ValueError as exc:
            raise _client_error(exc) from exc

    @put(
        "/api/carbon/organization-boundary/boundaries/{boundary_id:int}/selection",
        operation_id="OrganizationBoundarySaveSelection",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def save_selection(
        self,
        db_session: AsyncSession,
        boundary_id: int,
        data: SaveBoundarySelectionRequest,
    ) -> BoundarySelectionResponse:
        try:
            boundary = await OrganizationBoundaryUseCase(db_session).save_selection(boundary_id, data)
            return await OrganizationBoundaryQueryService(db_session).selection(boundary.id)
        except ValueError as exc:
            raise _client_error(exc) from exc

    @get(
        "/api/carbon/organization-boundary/boundaries/{boundary_id:int}/diff",
        operation_id="OrganizationBoundaryGetDiff",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def get_diff(
        self,
        db_session: AsyncSession,
        boundary_id: int,
        against_boundary_id: int | None = None,
    ) -> BoundaryDiffResponse:
        try:
            return await OrganizationBoundaryQueryService(db_session).diff(boundary_id, against_boundary_id)
        except ValueError as exc:
            raise _client_error(exc) from exc

    @delete(
        "/api/carbon/organization-boundary/boundaries/{boundary_id:int}/draft",
        operation_id="OrganizationBoundaryDiscardDraft",
        guards=[requires_permission("carbon.inventory.calculate")],
        status_code=200,
    )
    async def discard_draft(self, db_session: AsyncSession, boundary_id: int) -> Message:
        try:
            await OrganizationBoundaryUseCase(db_session).discard_draft(boundary_id)
        except ValueError as exc:
            raise _client_error(exc) from exc
        return Message(message="工作草稿已放弃")

    @post(
        "/api/carbon/organization-boundary/boundaries/{boundary_id:int}/source-facility",
        operation_id="OrganizationBoundaryCreateSourceFacility",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def create_source_facility(self, db_session: AsyncSession, boundary_id: int) -> Response[dict[str, object]]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).create_source_facility(boundary_id)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @get("/api/carbon/organization-boundary/facilities", operation_id="OrganizationBoundaryListFacilities")
    async def list_facilities(
        self,
        db_session: AsyncSession,
        boundary_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict[str, object]]:
        data = await OrganizationBoundaryQueryService(db_session).facilities(
            _query(boundary_id=boundary_id, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @post(
        "/api/carbon/organization-boundary/facilities",
        operation_id="OrganizationBoundaryCreateFacility",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def create_facility(
        self, db_session: AsyncSession, data: dict[str, object] = BOUNDARY_BODY
    ) -> Response[dict[str, object]]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).create_facility(data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @patch(
        "/api/carbon/organization-boundary/facilities/{facility_id:int}",
        operation_id="OrganizationBoundaryUpdateFacility",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def update_facility(
        self,
        db_session: AsyncSession,
        facility_id: int,
        data: dict[str, object] = BOUNDARY_BODY,
    ) -> Response[dict[str, object]]:
        try:
            obj = await OrganizationBoundaryUseCase(db_session).update_facility(facility_id, data)
        except ValueError as exc:
            return _error(exc)
        return Response(content=ok_data(model_to_dict(obj)))

    @delete(
        "/api/carbon/organization-boundary/facilities/{facility_id:int}",
        operation_id="OrganizationBoundaryDeleteFacility",
        guards=[requires_permission("carbon.inventory.calculate")],
        status_code=200,
    )
    async def delete_facility(self, db_session: AsyncSession, facility_id: int) -> Response[dict[str, object]]:
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


def _error(exc: ValueError) -> Response[dict[str, object]]:
    message = str(exc)
    status_code = 404 if "不存在" in message else 400
    return Response(content={"code": status_code, "msg": message}, status_code=status_code)


def _client_error(exc: ValueError) -> ClientException:
    message = str(exc)
    return ClientException(detail=message, status_code=404 if "不存在" in message else 422)
