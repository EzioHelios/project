"""Standards-aligned reduction, methodology, and offline CCER API."""

from __future__ import annotations

# ruff: noqa: RUF001 - Chinese business copy is intentional.
import base64
from typing import TYPE_CHECKING, Any

import msgspec
from litestar import Controller, get, patch, post, put
from litestar.exceptions import ClientException, NotFoundException
from litestar.response import Response

from app.domain.accounts.guards import requires_permission
from app.domain.decarbonization import models as m
from app.domain.decarbonization.domain import ReductionDomainError
from app.domain.decarbonization.infrastructure.workbook import build_monitoring_template, preview_monitoring_workbook
from app.domain.decarbonization.queries import DecarbonizationQueryService
from app.domain.decarbonization.schemas import (
    ApplicabilityAssessmentRequest,
    BaselineScenarioRequest,
    CalculationRunRequest,
    CcerDossierRequest,
    FinancialScenarioRequest,
    IssuanceLinkRequest,
    MonitoringPlanRequest,
    MonitoringWorkbookRequest,
    ProjectBoundaryRequest,
    ProjectReviewRequest,
    ProjectTransitionRequest,
    ReductionAuditListResponse,
    ReductionCalculationResponse,
    ReductionMethodologyListResponse,
    ReductionMethodologyResponse,
    ReductionOverviewResponse,
    ReductionProjectDetailResponse,
    ReductionProjectListResponse,
    ReductionProjectRequest,
    ReductionProjectUpdateRequest,
    ReductionTargetListResponse,
    ReductionTargetRequest,
    ReductionTargetResponse,
)
from app.domain.decarbonization.usecases import DecarbonizationUseCases

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class DecarbonizationController(Controller):
    """Expose read models and explicit lifecycle commands for reduction projects."""

    path = "/api/carbon/reduction"
    tags = ["Carbon Reduction"]
    guards = [requires_permission("carbon.reduction.view")]

    @get("/overview", operation_id="CarbonReductionGetOverview")
    async def overview(
        self,
        db_session: AsyncSession,
        target_year: int | None = None,
        category: str | None = None,
        status: str | None = None,
        area_id: int | None = None,
    ) -> ReductionOverviewResponse:
        return msgspec.convert(
            await DecarbonizationQueryService(db_session).overview(
                target_year=target_year, category=category, status=status, area_id=area_id
            ),
            type=ReductionOverviewResponse,
        )

    @get("/targets", operation_id="CarbonReductionListTargets")
    async def targets(self, db_session: AsyncSession, status: str | None = None) -> ReductionTargetListResponse:
        return msgspec.convert(
            {"items": await DecarbonizationQueryService(db_session).targets(status=status)},
            type=ReductionTargetListResponse,
        )

    @post(
        "/targets",
        operation_id="CarbonReductionCreateTarget",
        guards=[requires_permission("carbon.reduction.target.manage")],
    )
    async def create_target(self, db_session: AsyncSession, data: ReductionTargetRequest) -> ReductionTargetResponse:
        try:
            target = await DecarbonizationUseCases(db_session).create_target(data)
            return msgspec.convert(
                next(row for row in await DecarbonizationQueryService(db_session).targets() if row["id"] == target.id),
                type=ReductionTargetResponse,
            )
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @post(
        "/targets/{target_id:int}/publish",
        operation_id="CarbonReductionPublishTarget",
        guards=[requires_permission("carbon.reduction.target.manage")],
    )
    async def publish_target(self, db_session: AsyncSession, target_id: int) -> ReductionTargetResponse:
        try:
            target = await DecarbonizationUseCases(db_session).publish_target(target_id)
            return msgspec.convert(
                next(row for row in await DecarbonizationQueryService(db_session).targets() if row["id"] == target.id),
                type=ReductionTargetResponse,
            )
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @get("/projects", operation_id="CarbonReductionListProjects")
    async def projects(
        self,
        db_session: AsyncSession,
        keyword: str | None = None,
        track: str | None = None,
        category: str | None = None,
        status: str | None = None,
        risk_level: str | None = None,
        methodology_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ReductionProjectListResponse:
        return msgspec.convert(
            await DecarbonizationQueryService(db_session).projects(
                keyword=keyword,
                track=track,
                category=category,
                status=status,
                risk_level=risk_level,
                methodology_id=methodology_id,
                limit=limit,
                offset=offset,
            ),
            type=ReductionProjectListResponse,
        )

    @post(
        "/projects",
        operation_id="CarbonReductionCreateProject",
        guards=[requires_permission("carbon.reduction.project.manage")],
    )
    async def create_project(
        self, db_session: AsyncSession, data: ReductionProjectRequest
    ) -> ReductionProjectDetailResponse:
        try:
            project = await DecarbonizationUseCases(db_session).create_project(data)
            return await self._project_or_404(db_session, project.id)
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @get("/projects/{project_id:int}", operation_id="CarbonReductionGetProject")
    async def project(self, db_session: AsyncSession, project_id: int) -> ReductionProjectDetailResponse:
        return await self._project_or_404(db_session, project_id)

    @patch(
        "/projects/{project_id:int}",
        operation_id="CarbonReductionUpdateProject",
        guards=[requires_permission("carbon.reduction.project.manage")],
    )
    async def update_project(
        self, db_session: AsyncSession, project_id: int, data: ReductionProjectUpdateRequest
    ) -> ReductionProjectDetailResponse:
        try:
            await DecarbonizationUseCases(db_session).update_project(project_id, data)
            return await self._project_or_404(db_session, project_id)
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @post(
        "/projects/{project_id:int}/transition",
        operation_id="CarbonReductionTransitionProject",
        guards=[requires_permission("carbon.reduction.project.manage")],
    )
    async def transition_project(
        self, db_session: AsyncSession, project_id: int, data: ProjectTransitionRequest
    ) -> ReductionProjectDetailResponse:
        try:
            await DecarbonizationUseCases(db_session).transition_project(
                project_id, data.target_status, actor_name=data.actor_name, reason=data.reason
            )
            return await self._project_or_404(db_session, project_id)
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @post(
        "/projects/{project_id:int}/approve",
        operation_id="CarbonReductionApproveProject",
        guards=[requires_permission("carbon.reduction.project.manage")],
    )
    async def approve_project(self, db_session: AsyncSession, project_id: int) -> ReductionProjectDetailResponse:
        try:
            await DecarbonizationUseCases(db_session).transition_project(project_id, "approved")
            return await self._project_or_404(db_session, project_id)
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @put(
        "/projects/{project_id:int}/boundary",
        operation_id="CarbonReductionSaveProjectBoundary",
        guards=[requires_permission("carbon.reduction.project.manage")],
    )
    async def save_boundary(
        self, db_session: AsyncSession, project_id: int, data: ProjectBoundaryRequest
    ) -> ReductionProjectDetailResponse:
        try:
            await DecarbonizationUseCases(db_session).save_boundary(project_id, data)
            return await self._project_or_404(db_session, project_id)
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @post(
        "/projects/{project_id:int}/baselines",
        operation_id="CarbonReductionCreateBaseline",
        guards=[requires_permission("carbon.reduction.project.manage")],
    )
    async def create_baseline(
        self, db_session: AsyncSession, project_id: int, data: BaselineScenarioRequest
    ) -> dict[str, Any]:
        try:
            baseline = await DecarbonizationUseCases(db_session).create_baseline(project_id, data)
            detail = await self._project_or_404(db_session, project_id)
            return next(row for row in detail.baselines if row["id"] == baseline.id)
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @post(
        "/projects/{project_id:int}/baselines/{baseline_id:int}/lock",
        operation_id="CarbonReductionLockBaseline",
        guards=[requires_permission("carbon.reduction.project.manage")],
    )
    async def lock_baseline(
        self, db_session: AsyncSession, project_id: int, baseline_id: int
    ) -> ReductionProjectDetailResponse:
        try:
            await DecarbonizationUseCases(db_session).lock_baseline(project_id, baseline_id)
            return await self._project_or_404(db_session, project_id)
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @post(
        "/projects/{project_id:int}/applicability-assessments",
        operation_id="CarbonReductionAssessApplicability",
        guards=[requires_permission("carbon.reduction.project.manage")],
    )
    async def assess_applicability(
        self, db_session: AsyncSession, project_id: int, data: ApplicabilityAssessmentRequest
    ) -> dict[str, Any]:
        try:
            assessment = await DecarbonizationUseCases(db_session).assess_applicability(project_id, data)
            detail = await self._project_or_404(db_session, project_id)
            return next(row for row in detail.assessments if row["id"] == assessment.id)
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @put(
        "/projects/{project_id:int}/monitoring-plan",
        operation_id="CarbonReductionSaveMonitoringPlan",
        guards=[requires_permission("carbon.reduction.project.manage")],
    )
    async def save_monitoring_plan(
        self, db_session: AsyncSession, project_id: int, data: MonitoringPlanRequest
    ) -> dict[str, Any]:
        try:
            plan = await DecarbonizationUseCases(db_session).save_monitoring_plan(project_id, data)
            detail = await self._project_or_404(db_session, project_id)
            return next(row for row in detail.monitoring_plans if row["id"] == plan.id)
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @get(
        "/projects/{project_id:int}/monitoring-template",
        operation_id="CarbonReductionDownloadMonitoringTemplate",
        guards=[requires_permission("carbon.reduction.export")],
    )
    async def monitoring_template(self, db_session: AsyncSession, project_id: int) -> Response[bytes]:
        project = await db_session.get(m.ReductionProject, project_id)
        if project is None or project.methodology_id is None:
            raise NotFoundException(detail="Project methodology not found.")
        method = await db_session.get(m.ReductionMethodologyVersion, project.methodology_id)
        if method is None:
            raise NotFoundException(detail="Project methodology not found.")
        payload = self._method_payload(method)
        content = build_monitoring_template(payload)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{project.code}-{method.code}-monitoring.xlsx"'},
        )

    @post(
        "/projects/{project_id:int}/monitoring-imports",
        operation_id="CarbonReductionImportMonitoringWorkbook",
        guards=[requires_permission("carbon.reduction.project.manage")],
    )
    async def monitoring_import(
        self, db_session: AsyncSession, project_id: int, data: MonitoringWorkbookRequest
    ) -> dict[str, Any]:
        project = await db_session.get(m.ReductionProject, project_id)
        if project is None or project.methodology_id is None:
            raise NotFoundException(detail="Project methodology not found.")
        method = await db_session.get(m.ReductionMethodologyVersion, project.methodology_id)
        if method is None:
            raise NotFoundException(detail="Project methodology not found.")
        try:
            content = base64.b64decode(data.workbook_base64, validate=True)
        except ValueError as exc:
            raise ClientException(status_code=422, detail="工作簿内容不是有效的Base64数据。") from exc
        preview = preview_monitoring_workbook(content, self._method_payload(method))
        payload = preview.payload()
        if data.commit:
            if not payload["canCommit"]:
                raise ClientException(status_code=422, detail="工作簿存在错误，不能正式导入。")
            request = MonitoringPlanRequest(
                parameters=payload["rows"],
                quality_controls=[{"code": "workbook_precheck", "status": "pass", "fileName": data.file_name}],
                evidence_requirements=[{"name": item, "required": True} for item in method.evidence_schema],
                data_retention_years=10,
                publish=True,
            )
            plan = await DecarbonizationUseCases(db_session).save_monitoring_plan(project_id, request)
            payload["monitoringPlanId"] = plan.id
        return payload

    @post(
        "/projects/{project_id:int}/calculation-runs",
        operation_id="CarbonReductionRunCalculation",
        status_code=202,
        guards=[requires_permission("carbon.reduction.calculate")],
    )
    async def run_calculation(
        self, db_session: AsyncSession, project_id: int, data: CalculationRunRequest
    ) -> Response[ReductionCalculationResponse]:
        try:
            run = await DecarbonizationUseCases(db_session).run_calculation(project_id, data)
            result = await DecarbonizationQueryService(db_session).calculation(run.id)
            return Response(content=msgspec.convert(result, type=ReductionCalculationResponse), status_code=202)
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @get("/calculation-runs/{run_id:int}", operation_id="CarbonReductionGetCalculationRun")
    async def calculation(self, db_session: AsyncSession, run_id: int) -> ReductionCalculationResponse:
        result = await DecarbonizationQueryService(db_session).calculation(run_id)
        if result is None:
            raise NotFoundException(detail="Calculation run not found.")
        return msgspec.convert(result, type=ReductionCalculationResponse)

    @post(
        "/projects/{project_id:int}/financial-scenarios",
        operation_id="CarbonReductionCreateFinancialScenario",
        guards=[requires_permission("carbon.reduction.calculate")],
    )
    async def create_financial_scenario(
        self, db_session: AsyncSession, project_id: int, data: FinancialScenarioRequest
    ) -> dict[str, Any]:
        try:
            scenario = await DecarbonizationUseCases(db_session).create_financial_scenario(project_id, data)
            detail = await self._project_or_404(db_session, project_id)
            return next(row for row in detail.financial_scenarios if row["id"] == scenario.id)
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @post(
        "/projects/{project_id:int}/reviews",
        operation_id="CarbonReductionCreateReview",
        guards=[requires_permission("carbon.reduction.review")],
    )
    async def create_review(
        self, db_session: AsyncSession, project_id: int, data: ProjectReviewRequest
    ) -> dict[str, Any]:
        try:
            review = await DecarbonizationUseCases(db_session).create_review(project_id, data)
            detail = await self._project_or_404(db_session, project_id)
            return next(row for row in detail.reviews if row["id"] == review.id)
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @get("/projects/{project_id:int}/ccer-dossier", operation_id="CarbonReductionGetCcerDossier")
    async def ccer_dossier(self, db_session: AsyncSession, project_id: int) -> dict[str, Any] | None:
        return (await self._project_or_404(db_session, project_id)).ccer_dossier

    @put(
        "/projects/{project_id:int}/ccer-dossier",
        operation_id="CarbonReductionSaveCcerDossier",
        guards=[requires_permission("carbon.reduction.ccer.manage")],
    )
    async def save_ccer_dossier(
        self, db_session: AsyncSession, project_id: int, data: CcerDossierRequest
    ) -> dict[str, Any]:
        try:
            await DecarbonizationUseCases(db_session).save_ccer_dossier(project_id, data)
            dossier = (await self._project_or_404(db_session, project_id)).ccer_dossier
            if dossier is None:
                raise NotFoundException(detail="CCER dossier not found.")
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        else:
            return dossier

    @post(
        "/projects/{project_id:int}/issuance-link",
        operation_id="CarbonReductionLinkIssuedCcer",
        guards=[requires_permission("carbon.reduction.ccer.manage")],
    )
    async def link_issuance(
        self, db_session: AsyncSession, project_id: int, data: IssuanceLinkRequest
    ) -> dict[str, Any]:
        try:
            holding = await DecarbonizationUseCases(db_session).link_issuance(
                project_id, data.account_id, data.market_price
            )
            return {
                "id": holding.id,
                "lotNo": holding.lot_no,
                "projectCode": holding.project_code,
                "quantity": float(holding.issued_quantity),
                "unit": "tCO2e",
                "status": holding.status,
            }
        except (ReductionDomainError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @get("/projects/{project_id:int}/audit-events", operation_id="CarbonReductionListAuditEvents")
    async def audit_events(self, db_session: AsyncSession, project_id: int) -> ReductionAuditListResponse:
        return msgspec.convert(
            {"items": await DecarbonizationQueryService(db_session).audit_events(project_id)},
            type=ReductionAuditListResponse,
        )

    @get("/methodologies", operation_id="CarbonReductionListMethodologies")
    async def methodologies(
        self,
        db_session: AsyncSession,
        keyword: str | None = None,
        sector: str | None = None,
        executable: bool | None = None,
    ) -> ReductionMethodologyListResponse:
        return msgspec.convert(
            {
                "items": await DecarbonizationQueryService(db_session).methodologies(
                    keyword=keyword, sector=sector, executable=executable
                )
            },
            type=ReductionMethodologyListResponse,
        )

    @get("/methodologies/{methodology_id:int}", operation_id="CarbonReductionGetMethodology")
    async def methodology(self, db_session: AsyncSession, methodology_id: int) -> ReductionMethodologyResponse:
        result = await DecarbonizationQueryService(db_session).methodology(methodology_id)
        if result is None:
            raise NotFoundException(detail="Methodology not found.")
        return msgspec.convert(result, type=ReductionMethodologyResponse)

    async def _project_or_404(self, db_session: AsyncSession, project_id: int) -> ReductionProjectDetailResponse:
        result = await DecarbonizationQueryService(db_session).project(project_id)
        if result is None:
            raise NotFoundException(detail="Reduction project not found.")
        return msgspec.convert(result, type=ReductionProjectDetailResponse)

    @staticmethod
    def _method_payload(method: m.ReductionMethodologyVersion) -> dict[str, Any]:
        return {
            "code": method.code,
            "name": method.name,
            "version": method.version,
            "source_url": method.source_url,
            "parameter_schema": method.parameter_schema,
            "evidence_schema": method.evidence_schema,
        }
