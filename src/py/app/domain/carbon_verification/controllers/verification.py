from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, get, patch, post
from litestar.datastructures import UploadFile  # noqa: TC002
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.params import Body, Parameter
from litestar.response import File, Response
from saq import Queue  # noqa: TC002

from app.domain.accounts.guards import requires_permission
from app.domain.carbon_verification.queries.canonical import (
    CanonicalVerificationQueryService as CarbonVerificationQueryService,
)
from app.domain.carbon_verification.queries.canonical import (
    VerificationQuery,
)
from app.domain.carbon_verification.queries.findings import CarbonVerificationFindingQueryService, FindingQuery
from app.domain.carbon_verification.queries.projects import CarbonVerificationProjectQueryService, ProjectQuery
from app.domain.carbon_verification.queries.templates import CarbonVerificationTemplateQueryService, TemplateQuery
from app.domain.carbon_verification.usecases.evidence import CanonicalEvidenceUseCase
from app.domain.carbon_verification.usecases.export import CarbonVerificationExportUseCase
from app.domain.carbon_verification.usecases.findings import CarbonVerificationFindingUseCase
from app.domain.carbon_verification.usecases.projects import CarbonVerificationProjectUseCase
from app.domain.carbon_verification.usecases.templates import CarbonVerificationTemplateUseCase
from app.domain.energy.controllers._utils import ok_data
from app.lib.deps import get_task_queue

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import models as m


EXPORT_BODY = Body()
UPLOAD_BODY = Body(media_type=RequestEncodingType.MULTI_PART)
JsonObject = dict[str, Any]


class CarbonVerificationController(Controller):
    tags = ["Carbon Verification"]
    guards = [requires_permission("carbon.verification.view")]
    dependencies = {"task_queue": Provide(get_task_queue)}

    @get("/api/carbon/verification/source-readiness", operation_id="CarbonVerificationGetSourceReadiness")
    async def get_verification_source_readiness(self, db_session: AsyncSession) -> Response[JsonObject]:
        data = await CarbonVerificationQueryService(db_session).source_readiness()
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/summary", operation_id="CarbonVerificationGetSummary")
    async def get_verification_summary(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        project_id: int | None = None,
    ) -> Response[JsonObject]:
        try:
            data = await CarbonVerificationQueryService(db_session).summary(
                _query(year=year, status=status, scope=scope_filter, project_id=project_id)
            )
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/evidence", operation_id="CarbonVerificationListEvidence")
    async def get_verification_evidence(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        project_id: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[JsonObject]:
        try:
            data = await CarbonVerificationQueryService(db_session).evidence_manifest(
                _query(
                    year=year,
                    status=status,
                    scope=scope_filter,
                    project_id=project_id,
                    limit=limit,
                    offset=offset,
                )
            )
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/issues", operation_id="CarbonVerificationListIssues")
    async def get_verification_issues(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        project_id: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[JsonObject]:
        try:
            data = await CarbonVerificationQueryService(db_session).issues(
                _query(
                    year=year,
                    status=status,
                    scope=scope_filter,
                    project_id=project_id,
                    limit=limit,
                    offset=offset,
                )
            )
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/findings", operation_id="CarbonVerificationListFindings")
    async def list_verification_findings(
        self,
        db_session: AsyncSession,
        project_id: int | None = None,
        status: str | None = None,
        severity: str | None = None,
        record_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Response[JsonObject]:
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

    @get("/api/carbon/verification/projects", operation_id="CarbonVerificationListProjects")
    async def list_verification_projects(
        self,
        db_session: AsyncSession,
        status: str | None = None,
        reporting_org_id: int | None = None,
        period_id: int | None = None,
        verification_year: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Response[JsonObject]:
        data = await CarbonVerificationProjectQueryService(db_session).list_projects(
            ProjectQuery(
                status=status,
                reporting_org_id=reporting_org_id,
                period_id=period_id,
                verification_year=verification_year,
                limit=max(1, min(limit, 500)),
                offset=max(0, offset),
            )
        )
        return Response(content=ok_data(data))

    @get(
        "/api/carbon/verification/projects/{project_id:int}",
        operation_id="CarbonVerificationGetProject",
    )
    async def get_verification_project(self, db_session: AsyncSession, project_id: int) -> Response[JsonObject]:
        try:
            payload = await CarbonVerificationProjectQueryService(db_session).get_project(project_id)
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return Response(content=ok_data(payload))

    @post(
        "/api/carbon/verification/projects",
        operation_id="CarbonVerificationCreateProject",
        guards=[requires_permission("carbon.verification.manage")],
    )
    async def create_verification_project(
        self,
        db_session: AsyncSession,
        data: JsonObject = EXPORT_BODY,
    ) -> Response[JsonObject]:
        try:
            project = await CarbonVerificationProjectUseCase(db_session).create_project(data)
            payload = await CarbonVerificationProjectQueryService(db_session).get_project(project.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @patch(
        "/api/carbon/verification/projects/{project_id:int}",
        operation_id="CarbonVerificationUpdateProject",
        guards=[requires_permission("carbon.verification.manage")],
    )
    async def update_verification_project(
        self,
        db_session: AsyncSession,
        project_id: int,
        data: JsonObject = EXPORT_BODY,
    ) -> Response[JsonObject]:
        try:
            project = await CarbonVerificationProjectUseCase(db_session).update_project(project_id, data)
            payload = await CarbonVerificationProjectQueryService(db_session).get_project(project.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @post(
        "/api/carbon/verification/projects/{project_id:int}/refresh",
        operation_id="CarbonVerificationRefreshProject",
        guards=[requires_permission("carbon.verification.manage")],
    )
    async def refresh_verification_project(self, db_session: AsyncSession, project_id: int) -> Response[JsonObject]:
        try:
            project = await CarbonVerificationProjectUseCase(db_session).refresh_project_status(project_id)
            payload = await CarbonVerificationProjectQueryService(db_session).get_project(project.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @post(
        "/api/carbon/verification/findings",
        operation_id="CarbonVerificationCreateFinding",
        guards=[requires_permission("carbon.verification.manage")],
    )
    async def create_verification_finding(
        self,
        db_session: AsyncSession,
        data: JsonObject = EXPORT_BODY,
    ) -> Response[JsonObject]:
        try:
            finding = await CarbonVerificationFindingUseCase(db_session).create_finding(data)
            payload = await CarbonVerificationFindingQueryService(db_session).get_finding(finding.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @patch(
        "/api/carbon/verification/findings/{finding_id:int}",
        operation_id="CarbonVerificationUpdateFinding",
        guards=[requires_permission("carbon.verification.review")],
    )
    async def update_verification_finding(
        self,
        db_session: AsyncSession,
        finding_id: int,
        data: JsonObject = EXPORT_BODY,
    ) -> Response[JsonObject]:
        try:
            finding = await CarbonVerificationFindingUseCase(db_session).update_finding(finding_id, data)
            payload = await CarbonVerificationFindingQueryService(db_session).get_finding(finding.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @get("/api/carbon/verification/audit-trail", operation_id="CarbonVerificationGetAuditTrail")
    async def get_verification_audit_trail(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        project_id: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[JsonObject]:
        try:
            data = await CarbonVerificationQueryService(db_session).audit_trail(
                _query(
                    year=year,
                    status=status,
                    scope=scope_filter,
                    project_id=project_id,
                    limit=limit,
                    offset=offset,
                )
            )
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return Response(content=ok_data(data))

    @get(
        "/api/carbon/verification/material-package",
        operation_id="CarbonVerificationGetMaterialPackage",
    )
    async def get_verification_material_package(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        project_id: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[JsonObject]:
        try:
            data = await CarbonVerificationQueryService(db_session).material_package(
                _query(
                    year=year,
                    status=status,
                    scope=scope_filter,
                    project_id=project_id,
                    limit=limit,
                    offset=offset,
                )
            )
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/templates", operation_id="CarbonVerificationListTemplates")
    async def list_verification_templates(
        self,
        db_session: AsyncSession,
        status: str | None = None,
        applicable_industry: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Response[JsonObject]:
        data = await CarbonVerificationTemplateQueryService(db_session).list_templates(
            TemplateQuery(
                status=status,
                applicable_industry=applicable_industry,
                limit=max(1, min(limit, 500)),
                offset=max(0, offset),
            )
        )
        return Response(content=ok_data(data))

    @post(
        "/api/carbon/verification/templates",
        operation_id="CarbonVerificationCreateTemplate",
        guards=[requires_permission("carbon.verification.manage")],
    )
    async def create_verification_template(
        self,
        db_session: AsyncSession,
        data: JsonObject = EXPORT_BODY,
    ) -> Response[JsonObject]:
        try:
            template = await CarbonVerificationTemplateUseCase(db_session).create_template(data)
            payload = await CarbonVerificationTemplateQueryService(db_session).get_template(template.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @post(
        "/api/carbon/verification/templates/ensure-default",
        operation_id="CarbonVerificationEnsureDefaultTemplate",
        guards=[requires_permission("carbon.verification.manage")],
    )
    async def ensure_default_verification_template(self, db_session: AsyncSession) -> Response[JsonObject]:
        template = await CarbonVerificationTemplateUseCase(db_session).ensure_default_template()
        payload = await CarbonVerificationTemplateQueryService(db_session).get_template(template.id)
        return Response(content=ok_data(payload))

    @patch(
        "/api/carbon/verification/templates/{template_id:int}",
        operation_id="CarbonVerificationUpdateTemplate",
        guards=[requires_permission("carbon.verification.manage")],
    )
    async def update_verification_template(
        self,
        db_session: AsyncSession,
        template_id: int,
        data: JsonObject = EXPORT_BODY,
    ) -> Response[JsonObject]:
        try:
            template = await CarbonVerificationTemplateUseCase(db_session).update_template(template_id, data)
            payload = await CarbonVerificationTemplateQueryService(db_session).get_template(template.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload))

    @get("/api/carbon/verification/report", operation_id="CarbonVerificationGetReportContext")
    async def get_verification_report_context(
        self,
        db_session: AsyncSession,
        year: int | None = None,
        status: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        project_id: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Response[JsonObject]:
        try:
            data = await CarbonVerificationQueryService(db_session).report_context(
                _query(
                    year=year,
                    status=status,
                    scope=scope_filter,
                    project_id=project_id,
                    limit=limit,
                    offset=offset,
                )
            )
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return Response(content=ok_data(data))

    @get("/api/carbon/verification/export-jobs", operation_id="CarbonVerificationListExports")
    async def list_verification_export_jobs(
        self,
        db_session: AsyncSession,
        project_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[JsonObject]:
        data = await CarbonVerificationExportUseCase(db_session).list_export_jobs(
            project_id=project_id, limit=limit, offset=offset
        )
        return Response(content=ok_data(data))

    @post(
        "/api/carbon/verification/export-jobs",
        operation_id="CarbonVerificationCreateExport",
        guards=[requires_permission("carbon.verification.export")],
        status_code=202,
    )
    async def create_verification_export_job(
        self,
        db_session: AsyncSession,
        current_user: m.User,
        task_queue: Queue,
        data: JsonObject = EXPORT_BODY,
    ) -> Response[JsonObject]:
        try:
            usecase = CarbonVerificationExportUseCase(db_session)
            job = await usecase.create_export_job({**data, "requested_by": current_user.email})
            await task_queue.enqueue(
                "run_carbon_verification_export",
                job_id=job.id,
                team_id=str(job.team_id),
                key=f"carbon-verification-export:{job.team_id}:{job.id}",
                timeout=180,
            )
            payload = await usecase.get_export_job(job.id)
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(payload), status_code=202)

    @get(
        "/api/carbon/verification/export-jobs/{job_id:int}",
        operation_id="CarbonVerificationGetExport",
    )
    async def get_verification_export_job(self, db_session: AsyncSession, job_id: int) -> Response[JsonObject]:
        try:
            payload = await CarbonVerificationExportUseCase(db_session).get_export_job(job_id)
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return Response(content=ok_data(payload))

    @get(
        "/api/carbon/verification/export-jobs/{job_id:int}/download",
        operation_id="CarbonVerificationDownloadExport",
        guards=[requires_permission("carbon.verification.export")],
    )
    async def download_verification_export_job(
        self, db_session: AsyncSession, job_id: int
    ) -> File | Response[JsonObject]:
        try:
            path = await CarbonVerificationExportUseCase(db_session).export_file_path(job_id)
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return File(path=path, filename=path.name, media_type="application/zip")

    @post(
        "/api/carbon/verification/evidence/upload",
        operation_id="CarbonVerificationUploadEvidence",
        guards=[requires_permission("carbon.verification.evidence.manage")],
    )
    async def upload_verification_evidence(
        self,
        db_session: AsyncSession,
        current_user: m.User,
        project_id: int,
        record_type: str,
        record_code: str,
        evidence_role: str,
        document_type: str,
        data: UploadFile = UPLOAD_BODY,
    ) -> Response[JsonObject]:
        try:
            content = await data.read()
            evidence = await CanonicalEvidenceUseCase(db_session).upload(
                project_id=project_id,
                record_type=record_type,
                record_code=record_code,
                evidence_role=evidence_role,
                document_type=document_type,
                file_name=data.filename or "evidence-file",
                content_type=data.content_type,
                content=content,
                uploaded_by=current_user.email,
            )
        except ValueError as exc:
            return Response(content={"code": 422, "msg": str(exc)}, status_code=422)
        return Response(
            content=ok_data(
                {
                    "evidence_code": evidence.evidence_code,
                    "file_name": evidence.file_name,
                    "document_type": evidence.document_type,
                    "sha256": evidence.sha256,
                    "verification_status": evidence.verification_status,
                }
            )
        )

    @post(
        "/api/carbon/verification/evidence/{evidence_code:str}/review",
        operation_id="CarbonVerificationReviewEvidence",
        guards=[requires_permission("carbon.verification.review")],
    )
    async def review_verification_evidence(
        self,
        db_session: AsyncSession,
        current_user: m.User,
        evidence_code: str,
        project_id: int,
        data: JsonObject = EXPORT_BODY,
    ) -> Response[JsonObject]:
        try:
            evidence = await CanonicalEvidenceUseCase(db_session).review(
                project_id=project_id,
                evidence_code=evidence_code,
                decision=str(data.get("decision") or ""),
                reviewer=current_user.email,
            )
        except ValueError as exc:
            return Response(content={"code": 422, "msg": str(exc)}, status_code=422)
        return Response(
            content=ok_data({"evidence_code": evidence.evidence_code, "status": evidence.verification_status})
        )

    @get(
        "/api/carbon/verification/evidence/{evidence_code:str}/download",
        operation_id="CarbonVerificationDownloadEvidence",
    )
    async def download_verification_evidence(
        self, db_session: AsyncSession, evidence_code: str
    ) -> File | Response[JsonObject]:
        try:
            path = await CanonicalEvidenceUseCase(db_session).file_path(evidence_code)
        except ValueError as exc:
            return Response(content={"code": 404, "msg": str(exc)}, status_code=404)
        return File(path=path, filename=path.name)


def _query(
    *,
    year: int | None = None,
    status: str | None = None,
    scope: str | None = None,
    project_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> VerificationQuery:
    return VerificationQuery(
        year=year,
        status=status,
        scope=scope,
        project_id=project_id,
        limit=max(1, min(limit, 500)),
        offset=max(0, offset),
    )
