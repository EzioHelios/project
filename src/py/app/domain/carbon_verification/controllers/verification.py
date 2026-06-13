from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get, post
from litestar.params import Body
from litestar.response import File, Response

from app.domain.carbon_verification.queries.verification import CarbonVerificationQueryService, VerificationQuery
from app.domain.carbon_verification.usecases.export import CarbonVerificationExportUseCase
from app.domain.energy.controllers._utils import ok_data

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


EXPORT_BODY = Body()


class CarbonVerificationController(Controller):
    tags = ["Carbon Verification"]

    @get("/api/carbon/verification/summary")
    async def get_verification_summary(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope: str | None = None,
    ) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).summary(_query(year=year, status=status, scope=scope))
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/evidence")
    async def get_verification_evidence(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).evidence_manifest(
            _query(year=year, status=status, scope=scope, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/issues")
    async def get_verification_issues(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).issues(
            _query(year=year, status=status, scope=scope, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/audit-trail")
    async def get_verification_audit_trail(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).audit_trail(
            _query(year=year, status=status, scope=scope, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/material-package")
    async def get_verification_material_package(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).material_package(
            _query(year=year, status=status, scope=scope, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/report")
    async def get_verification_report_context(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).report_context(
            _query(year=year, status=status, scope=scope, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/export-jobs")
    async def list_verification_export_jobs(
        self,
        db_session: AsyncSession,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationExportUseCase(db_session).list_export_jobs(limit=limit, offset=offset)
        return Response(content=ok_data(data))

    @post("/api/carbon/verification/export-jobs")
    async def create_verification_export_job(
        self,
        db_session: AsyncSession,
        data: dict = EXPORT_BODY,
    ) -> Response[dict]:
        try:
            usecase = CarbonVerificationExportUseCase(db_session)
            job = await usecase.create_export_job(data)
            payload = await usecase.get_export_job(job.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @get("/api/carbon/verification/export-jobs/{job_id:int}")
    async def get_verification_export_job(self, db_session: AsyncSession, job_id: int) -> Response[dict]:
        try:
            payload = await CarbonVerificationExportUseCase(db_session).get_export_job(job_id)
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return Response(content=ok_data(payload))

    @get("/api/carbon/verification/export-jobs/{job_id:int}/download")
    async def download_verification_export_job(self, db_session: AsyncSession, job_id: int) -> File | Response[dict]:
        try:
            path = await CarbonVerificationExportUseCase(db_session).export_file_path(job_id)
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return File(path=path, filename=path.name, media_type="application/zip")


def _query(
    *,
    year: int | None = None,
    status: str | None = None,
    scope: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> VerificationQuery:
    return VerificationQuery(year=year, status=status, scope=scope, limit=max(1, min(limit, 500)), offset=max(0, offset))
