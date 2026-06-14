from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get, patch, post
from litestar.params import Body, Parameter
from litestar.response import File, Response

from app.domain.carbon_verification.queries.attachments import AttachmentQuery, CarbonVerificationAttachmentQueryService
from app.domain.carbon_verification.queries.findings import CarbonVerificationFindingQueryService, FindingQuery
from app.domain.carbon_verification.queries.projects import CarbonVerificationProjectQueryService, ProjectQuery
from app.domain.carbon_verification.queries.templates import CarbonVerificationTemplateQueryService, TemplateQuery
from app.domain.carbon_verification.queries.verification import CarbonVerificationQueryService, VerificationQuery
from app.domain.carbon_verification.usecases.attachments import CarbonVerificationAttachmentUseCase
from app.domain.carbon_verification.usecases.export import CarbonVerificationExportUseCase
from app.domain.carbon_verification.usecases.findings import CarbonVerificationFindingUseCase
from app.domain.carbon_verification.usecases.projects import CarbonVerificationProjectUseCase
from app.domain.carbon_verification.usecases.templates import CarbonVerificationTemplateUseCase
from app.domain.energy.controllers._utils import ok_data

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


EXPORT_BODY = Body()


class CarbonVerificationController(Controller):
    tags = ["Carbon Verification"]

    @get("/api/carbon/verification/source-readiness")
    async def get_verification_source_readiness(self, db_session: AsyncSession) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).source_readiness()
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/summary")
    async def get_verification_summary(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        project_id: int | None = None,
        accounting_batch_id: int | None = None,
    ) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).summary(
            _query(year=year, status=status, scope=scope_filter, project_id=project_id, accounting_batch_id=accounting_batch_id)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/evidence")
    async def get_verification_evidence(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        project_id: int | None = None,
        accounting_batch_id: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).evidence_manifest(
            _query(year=year, status=status, scope=scope_filter, project_id=project_id, accounting_batch_id=accounting_batch_id, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/attachments")
    async def list_verification_attachments(
        self,
        db_session: AsyncSession,
        project_id: int | None = None,
        source_object_type: str | None = None,
        source_object_id: int | None = None,
        status: str | None = None,
        material_group: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationAttachmentQueryService(db_session).list_attachments(
            AttachmentQuery(
                project_id=project_id,
                source_object_type=source_object_type,
                source_object_id=source_object_id,
                status=status,
                material_group=material_group,
                limit=max(1, min(limit, 500)),
                offset=max(0, offset),
            )
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/verification/attachments")
    async def create_verification_attachment(
        self,
        db_session: AsyncSession,
        data: dict = EXPORT_BODY,
    ) -> Response[dict]:
        try:
            attachment = await CarbonVerificationAttachmentUseCase(db_session).create_attachment(data)
            payload = await CarbonVerificationAttachmentQueryService(db_session).get_attachment(attachment.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @patch("/api/carbon/verification/attachments/{attachment_id:int}")
    async def update_verification_attachment(
        self,
        db_session: AsyncSession,
        attachment_id: int,
        data: dict = EXPORT_BODY,
    ) -> Response[dict]:
        try:
            attachment = await CarbonVerificationAttachmentUseCase(db_session).update_attachment(attachment_id, data)
            payload = await CarbonVerificationAttachmentQueryService(db_session).get_attachment(attachment.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @get("/api/carbon/verification/issues")
    async def get_verification_issues(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        project_id: int | None = None,
        accounting_batch_id: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).issues(
            _query(year=year, status=status, scope=scope_filter, project_id=project_id, accounting_batch_id=accounting_batch_id, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/findings")
    async def list_verification_findings(
        self,
        db_session: AsyncSession,
        project_id: int | None = None,
        status: str | None = None,
        severity: str | None = None,
        record_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationFindingQueryService(db_session).list_findings(
            FindingQuery(
                project_id=project_id,
                status=status,
                severity=severity,
                record_type=record_type,
                limit=max(1, min(limit, 500)),
                offset=max(0, offset),
            )
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/projects")
    async def list_verification_projects(
        self,
        db_session: AsyncSession,
        status: str | None = None,
        reporting_org_id: int | None = None,
        period_id: int | None = None,
        accounting_batch_id: int | None = None,
        verification_year: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationProjectQueryService(db_session).list_projects(
            ProjectQuery(
                status=status,
                reporting_org_id=reporting_org_id,
                period_id=period_id,
                accounting_batch_id=accounting_batch_id,
                verification_year=verification_year,
                limit=max(1, min(limit, 500)),
                offset=max(0, offset),
            )
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/projects/{project_id:int}")
    async def get_verification_project(self, db_session: AsyncSession, project_id: int) -> Response[dict]:
        try:
            payload = await CarbonVerificationProjectQueryService(db_session).get_project(project_id)
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return Response(content=ok_data(payload))

    @post("/api/carbon/verification/projects")
    async def create_verification_project(
        self,
        db_session: AsyncSession,
        data: dict = EXPORT_BODY,
    ) -> Response[dict]:
        try:
            project = await CarbonVerificationProjectUseCase(db_session).create_project(data)
            payload = await CarbonVerificationProjectQueryService(db_session).get_project(project.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @patch("/api/carbon/verification/projects/{project_id:int}")
    async def update_verification_project(
        self,
        db_session: AsyncSession,
        project_id: int,
        data: dict = EXPORT_BODY,
    ) -> Response[dict]:
        try:
            project = await CarbonVerificationProjectUseCase(db_session).update_project(project_id, data)
            payload = await CarbonVerificationProjectQueryService(db_session).get_project(project.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @post("/api/carbon/verification/projects/{project_id:int}/refresh")
    async def refresh_verification_project(self, db_session: AsyncSession, project_id: int) -> Response[dict]:
        try:
            project = await CarbonVerificationProjectUseCase(db_session).refresh_project_status(project_id)
            payload = await CarbonVerificationProjectQueryService(db_session).get_project(project.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @post("/api/carbon/verification/findings")
    async def create_verification_finding(
        self,
        db_session: AsyncSession,
        data: dict = EXPORT_BODY,
    ) -> Response[dict]:
        try:
            finding = await CarbonVerificationFindingUseCase(db_session).create_finding(data)
            payload = await CarbonVerificationFindingQueryService(db_session).get_finding(finding.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @patch("/api/carbon/verification/findings/{finding_id:int}")
    async def update_verification_finding(
        self,
        db_session: AsyncSession,
        finding_id: int,
        data: dict = EXPORT_BODY,
    ) -> Response[dict]:
        try:
            finding = await CarbonVerificationFindingUseCase(db_session).update_finding(finding_id, data)
            payload = await CarbonVerificationFindingQueryService(db_session).get_finding(finding.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @get("/api/carbon/verification/audit-trail")
    async def get_verification_audit_trail(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        project_id: int | None = None,
        accounting_batch_id: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).audit_trail(
            _query(year=year, status=status, scope=scope_filter, project_id=project_id, accounting_batch_id=accounting_batch_id, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/material-package")
    async def get_verification_material_package(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        project_id: int | None = None,
        accounting_batch_id: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).material_package(
            _query(year=year, status=status, scope=scope_filter, project_id=project_id, accounting_batch_id=accounting_batch_id, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/templates")
    async def list_verification_templates(
        self,
        db_session: AsyncSession,
        status: str | None = None,
        applicable_industry: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationTemplateQueryService(db_session).list_templates(
            TemplateQuery(status=status, applicable_industry=applicable_industry, limit=max(1, min(limit, 500)), offset=max(0, offset))
        )
        return Response(content=ok_data(data))

    @post("/api/carbon/verification/templates")
    async def create_verification_template(
        self,
        db_session: AsyncSession,
        data: dict = EXPORT_BODY,
    ) -> Response[dict]:
        try:
            template = await CarbonVerificationTemplateUseCase(db_session).create_template(data)
            payload = await CarbonVerificationTemplateQueryService(db_session).get_template(template.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @post("/api/carbon/verification/templates/ensure-default")
    async def ensure_default_verification_template(self, db_session: AsyncSession) -> Response[dict]:
        template = await CarbonVerificationTemplateUseCase(db_session).ensure_default_template()
        payload = await CarbonVerificationTemplateQueryService(db_session).get_template(template.id)
        return Response(content=ok_data(payload))

    @patch("/api/carbon/verification/templates/{template_id:int}")
    async def update_verification_template(
        self,
        db_session: AsyncSession,
        template_id: int,
        data: dict = EXPORT_BODY,
    ) -> Response[dict]:
        try:
            template = await CarbonVerificationTemplateUseCase(db_session).update_template(template_id, data)
            payload = await CarbonVerificationTemplateQueryService(db_session).get_template(template.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @get("/api/carbon/verification/report")
    async def get_verification_report_context(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        project_id: int | None = None,
        accounting_batch_id: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationQueryService(db_session).report_context(
            _query(year=year, status=status, scope=scope_filter, project_id=project_id, accounting_batch_id=accounting_batch_id, limit=limit, offset=offset)
        )
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/export-jobs")
    async def list_verification_export_jobs(
        self,
        db_session: AsyncSession,
        project_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        data = await CarbonVerificationExportUseCase(db_session).list_export_jobs(project_id=project_id, limit=limit, offset=offset)
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
    project_id: int | None = None,
    accounting_batch_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> VerificationQuery:
    return VerificationQuery(
        year=year,
        status=status,
        scope=scope,
        project_id=project_id,
        accounting_batch_id=accounting_batch_id,
        limit=max(1, min(limit, 500)),
        offset=max(0, offset),
    )
