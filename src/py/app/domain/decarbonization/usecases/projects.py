"""Transactional workflows for targets, projects, calculations, reviews, and CCER assets."""

from __future__ import annotations

# ruff: noqa: EM101, TRY003 - domain guard messages are intentionally local and concise.
import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import msgspec
from litestar.exceptions import NotFoundException
from sqlalchemy import delete, func, select, update

from app.domain.carbon.models import MonitorEquipment, MonitorSector
from app.domain.carbon_assets.models import CarbonAssetAccount, CarbonAssetInstrument, CarbonAssetLot
from app.domain.decarbonization import models as m
from app.domain.decarbonization.domain import (
    CcerIssuancePolicy,
    ProjectLifecyclePolicy,
    ReductionDomainError,
    calculate_reduction,
    screen_applicability,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.decarbonization.schemas import (
        ApplicabilityAssessmentRequest,
        BaselineScenarioRequest,
        CalculationRunRequest,
        CcerDossierRequest,
        FinancialScenarioRequest,
        MonitoringPlanRequest,
        ProjectBoundaryRequest,
        ProjectReviewRequest,
        ReductionProjectRequest,
        ReductionProjectUpdateRequest,
        ReductionTargetRequest,
    )


def _now() -> datetime:
    return datetime.now(UTC)


def _decimal(value: float | Decimal | None) -> Decimal:
    return Decimal(str(value or 0))


def _snapshot(obj: object, fields: tuple[str, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in fields:
        value = getattr(obj, field, None)
        if isinstance(value, Decimal):
            result[field] = float(value)
        elif isinstance(value, (date, datetime)):
            result[field] = value.isoformat()
        else:
            result[field] = value
    return result


def _level_irr(capex: Decimal, annual_net: Decimal, years: int) -> Decimal | None:
    """Solve the level annual-cash-flow IRR deterministically by bisection."""
    if capex <= 0 or annual_net <= 0 or years <= 0:
        return None

    def npv(rate: Decimal) -> Decimal:
        return -capex + sum(annual_net / ((Decimal(1) + rate) ** year) for year in range(1, years + 1))

    low = Decimal("-0.999")
    high = Decimal(10)
    if npv(low) * npv(high) > 0:
        return None
    for _ in range(100):
        middle = (low + high) / Decimal(2)
        if npv(middle) > 0:
            low = middle
        else:
            high = middle
    return (low + high) / Decimal(2)


class DecarbonizationUseCases:
    """Application boundary for all mutation workflows in the bounded context."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_target(self, data: ReductionTargetRequest) -> m.ReductionTarget:
        if data.target_year <= data.baseline_year:
            raise ReductionDomainError("Target year must be later than baseline year.")
        if data.baseline_tco2e <= 0 or data.target_reduction_tco2e <= 0:
            raise ReductionDomainError("Baseline and target reduction must be greater than zero.")
        latest = await self.session.scalar(
            select(func.max(m.ReductionTarget.version)).where(m.ReductionTarget.code == data.code)
        )
        target = m.ReductionTarget(
            code=data.code,
            name=data.name,
            version=int(latest or 0) + 1,
            target_year=data.target_year,
            baseline_year=data.baseline_year,
            baseline_tco2e=_decimal(data.baseline_tco2e),
            target_reduction_tco2e=_decimal(data.target_reduction_tco2e),
            target_reduction_pct=_decimal(data.target_reduction_pct) if data.target_reduction_pct is not None else None,
            organization_boundary_id=data.organization_boundary_id,
            area_id=data.area_id,
            business_unit=data.business_unit,
            trajectory=data.trajectory,
            source_name=data.source_name,
        )
        self.session.add(target)
        await self.session.flush()
        await self._audit("target", target.id, "target.created", None, _snapshot(target, ("code", "version", "status")))
        await self.session.commit()
        return target

    async def publish_target(self, target_id: int) -> m.ReductionTarget:
        target = await self._get(m.ReductionTarget, target_id, "Reduction target not found.")
        if target.status != "draft":
            raise ReductionDomainError("Only a draft reduction target can be published.")
        await self.session.execute(
            update(m.ReductionTarget)
            .where(m.ReductionTarget.code == target.code, m.ReductionTarget.status == "published")
            .values(status="archived")
        )
        target.status = "published"
        target.published_at = _now()
        await self._audit("target", target.id, "target.published", {"status": "draft"}, {"status": "published"})
        await self.session.commit()
        return target

    async def create_project(self, data: ReductionProjectRequest) -> m.ReductionProject:
        ProjectLifecyclePolicy.ensure_track(data.track)
        ProjectLifecyclePolicy.ensure_category(data.category)
        if data.inventory_impact_kind not in {"none", "scope1_actual", "scope2_location", "scope2_market", "scope3_actual"}:
            raise ReductionDomainError("Unsupported organization-inventory impact kind.")
        if data.track == "ccer_project" and data.inventory_impact_kind == "scope2_market" and data.category == "green_power":
            raise ReductionDomainError("Green-electricity procurement cannot be presented as a CCER project.")
        project = m.ReductionProject(
            code=data.code,
            name=data.name,
            track=data.track,
            category=data.category,
            owner_name=data.owner_name,
            department_name=data.department_name,
            organization_boundary_id=data.organization_boundary_id,
            methodology_id=data.methodology_id,
            target_id=data.target_id,
            planned_start=data.planned_start,
            planned_end=data.planned_end,
            investment_cny=_decimal(data.investment_cny),
            expected_reduction_tco2e=_decimal(data.expected_reduction_tco2e),
            objective=data.objective,
            implementation_plan=data.implementation_plan,
            inventory_impact_kind=data.inventory_impact_kind,
        )
        self.session.add(project)
        await self.session.flush()
        await self._audit("project", project.id, "project.created", None, self._project_snapshot(project))
        await self.session.commit()
        return project

    async def update_project(self, project_id: int, data: ReductionProjectUpdateRequest) -> m.ReductionProject:
        project = await self._get(m.ReductionProject, project_id, "Reduction project not found.")
        if project.status in {"issued", "closed", "archived"}:
            raise ReductionDomainError("Issued, closed, or archived projects are read-only.")
        before = self._project_snapshot(project)
        for field, value in data.to_dict().items():
            if field in {"investment_cny", "expected_reduction_tco2e", "progress_pct"}:
                value = _decimal(value)
            setattr(project, field, value)
        if not Decimal(0) <= project.progress_pct <= Decimal(100):
            raise ReductionDomainError("Project progress must be between 0 and 100.")
        await self._audit("project", project.id, "project.updated", before, self._project_snapshot(project))
        await self.session.commit()
        return project

    async def transition_project(
        self, project_id: int, target_status: str, *, actor_name: str | None = None, reason: str | None = None
    ) -> m.ReductionProject:
        project = await self._get(m.ReductionProject, project_id, "Reduction project not found.")
        ProjectLifecyclePolicy.ensure_transition(project.status, target_status)
        if target_status == "approved" and project.track != "internal_action":
            assessment = await self.session.scalar(
                select(m.ReductionApplicabilityAssessment)
                .where(m.ReductionApplicabilityAssessment.project_id == project.id)
                .order_by(m.ReductionApplicabilityAssessment.created_at.desc())
            )
            if assessment is None or assessment.status != "applicable":
                raise ReductionDomainError("A passing methodology applicability assessment is required before approval.")
        before = project.status
        project.status = target_status
        await self._audit(
            "project",
            project.id,
            f"project.{target_status}",
            {"status": before},
            {"status": target_status},
            actor_name=actor_name,
            reason=reason,
        )
        await self.session.commit()
        return project

    async def save_boundary(self, project_id: int, data: ProjectBoundaryRequest) -> m.ReductionProjectBoundary:
        project = await self._get(m.ReductionProject, project_id, "Reduction project not found.")
        if project.status not in {"draft", "screening", "approved"}:
            raise ReductionDomainError("Project boundary is read-only after the baseline is locked.")
        latest = await self.session.scalar(
            select(func.max(m.ReductionProjectBoundary.version)).where(m.ReductionProjectBoundary.project_id == project_id)
        )
        boundary = m.ReductionProjectBoundary(
            project_id=project_id,
            version=int(latest or 0) + 1,
            physical_boundary=data.physical_boundary,
            ghg_sources_sinks=data.ghg_sources_sinks,
            included_gases=data.included_gases,
            exclusions=data.exclusions,
            organization_snapshot={"organizationBoundaryId": project.organization_boundary_id},
        )
        self.session.add(boundary)
        await self.session.flush()
        await self.session.execute(delete(m.ReductionProjectResourceLink).where(m.ReductionProjectResourceLink.project_id == project_id))
        for row in data.resources:
            resource_type = str(row.get("resourceType") or row.get("resource_type") or "area")
            resource_key = str(row.get("resourceKey") or row.get("resource_key") or "")
            if not resource_key:
                raise ReductionDomainError("Every project resource link requires a resource key.")
            area_id = row.get("areaId") or row.get("area_id")
            equipment_id = row.get("equipmentId") or row.get("equipment_id")
            if area_id is not None and await self.session.get(MonitorSector, area_id) is None:
                raise ReductionDomainError("The selected area is outside the current tenant or does not exist.")
            if equipment_id is not None and await self.session.get(MonitorEquipment, equipment_id) is None:
                raise ReductionDomainError("The selected equipment is outside the current tenant or does not exist.")
            self.session.add(
                m.ReductionProjectResourceLink(
                    project_id=project_id,
                    resource_type=resource_type,
                    resource_key=resource_key,
                    area_id=area_id,
                    equipment_id=equipment_id,
                    measurement_boundary_id=row.get("measurementBoundaryId") or row.get("measurement_boundary_id"),
                    role=str(row.get("role") or "affected"),
                    allocation_ratio=_decimal(row.get("allocationRatio") or row.get("allocation_ratio") or 1),
                    resource_snapshot=dict(row.get("resourceSnapshot") or row.get("resource_snapshot") or {}),
                )
            )
        await self._audit("boundary", boundary.id, "boundary.version_created", None, {"version": boundary.version}, project_id=project_id)
        await self.session.commit()
        return boundary

    async def create_baseline(self, project_id: int, data: BaselineScenarioRequest) -> m.ReductionBaselineScenario:
        await self._get(m.ReductionProject, project_id, "Reduction project not found.")
        if data.period_end < data.period_start:
            raise ReductionDomainError("Baseline period end cannot be earlier than its start.")
        latest = await self.session.scalar(
            select(func.max(m.ReductionBaselineScenario.version)).where(m.ReductionBaselineScenario.project_id == project_id)
        )
        baseline = m.ReductionBaselineScenario(
            project_id=project_id,
            version=int(latest or 0) + 1,
            name=data.name,
            period_start=data.period_start,
            period_end=data.period_end,
            model_kind=data.model_kind,
            model_parameters=data.model_parameters,
            normalization_variables=data.normalization_variables,
            factor_snapshot=data.factor_snapshot,
            inventory_reference=data.inventory_reference,
            baseline_tco2e=_decimal(data.baseline_tco2e) if data.baseline_tco2e is not None else None,
        )
        self.session.add(baseline)
        await self.session.flush()
        await self._audit("baseline", baseline.id, "baseline.created", None, {"version": baseline.version}, project_id=project_id)
        await self.session.commit()
        return baseline

    async def lock_baseline(self, project_id: int, baseline_id: int) -> m.ReductionBaselineScenario:
        project = await self._get(m.ReductionProject, project_id, "Reduction project not found.")
        baseline = await self._get(m.ReductionBaselineScenario, baseline_id, "Baseline scenario not found.")
        if baseline.project_id != project_id:
            raise ReductionDomainError("Baseline scenario does not belong to this project.")
        if project.status != "approved":
            raise ReductionDomainError("The project must be approved before locking its baseline.")
        if baseline.status != "draft":
            raise ReductionDomainError("Only a draft baseline can be locked.")
        baseline.status = "locked"
        baseline.locked_at = _now()
        project.status = "baseline_locked"
        await self._audit("baseline", baseline.id, "baseline.locked", {"status": "draft"}, {"status": "locked"}, project_id=project_id)
        await self.session.commit()
        return baseline

    async def assess_applicability(
        self, project_id: int, data: ApplicabilityAssessmentRequest
    ) -> m.ReductionApplicabilityAssessment:
        project = await self._get(m.ReductionProject, project_id, "Reduction project not found.")
        methodology = await self._get(m.ReductionMethodologyVersion, data.methodology_id, "Methodology not found.")
        outcome = screen_applicability(methodology.code, data.answers)
        assessment = m.ReductionApplicabilityAssessment(
            project_id=project_id,
            methodology_id=methodology.id,
            status=outcome["status"],
            answers=data.answers,
            checks=outcome["checks"],
            blocking_reasons=outcome["blockingReasons"],
            methodology_snapshot=self._methodology_snapshot(methodology),
            assessed_by=data.assessed_by,
        )
        project.methodology_id = methodology.id
        if project.status == "draft":
            project.status = "screening"
        self.session.add(assessment)
        await self.session.flush()
        await self._audit("assessment", assessment.id, "methodology.screened", None, outcome, project_id=project_id)
        await self.session.commit()
        return assessment

    async def save_monitoring_plan(self, project_id: int, data: MonitoringPlanRequest) -> m.ReductionMonitoringPlan:
        project = await self._get(m.ReductionProject, project_id, "Reduction project not found.")
        if project.status in {"issued", "closed", "archived"}:
            raise ReductionDomainError("The monitoring plan is read-only for this project status.")
        latest = await self.session.scalar(
            select(func.max(m.ReductionMonitoringPlan.version)).where(m.ReductionMonitoringPlan.project_id == project_id)
        )
        incomplete = [item for item in data.parameters if not item.get("source") or not item.get("frequency")]
        readiness = "ready" if data.parameters and not incomplete and data.evidence_requirements else "incomplete"
        if data.publish and readiness != "ready":
            raise ReductionDomainError("A monitoring plan cannot be published while required data controls are incomplete.")
        plan = m.ReductionMonitoringPlan(
            project_id=project_id,
            version=int(latest or 0) + 1,
            status="published" if data.publish else "draft",
            parameters=data.parameters,
            quality_controls=data.quality_controls,
            evidence_requirements=data.evidence_requirements,
            data_retention_years=max(10, data.data_retention_years),
            readiness_status=readiness,
            published_at=_now() if data.publish else None,
        )
        self.session.add(plan)
        await self.session.flush()
        await self._audit("monitoring_plan", plan.id, "monitoring_plan.saved", None, {"status": plan.status, "readiness": readiness}, project_id=project_id)
        await self.session.commit()
        return plan

    async def run_calculation(self, project_id: int, data: CalculationRunRequest) -> m.ReductionCalculationRun:
        project = await self._get(m.ReductionProject, project_id, "Reduction project not found.")
        methodology = await self._get(m.ReductionMethodologyVersion, data.methodology_id, "Methodology not found.")
        baseline = await self._get(m.ReductionBaselineScenario, data.baseline_id, "Baseline scenario not found.")
        if baseline.project_id != project_id or baseline.status != "locked":
            raise ReductionDomainError("A locked baseline belonging to this project is required.")
        if methodology.status != "published" or not methodology.executable:
            raise ReductionDomainError("Only a published executable methodology can run a formal calculation.")
        if project.track != "internal_action":
            assessment = await self.session.scalar(
                select(m.ReductionApplicabilityAssessment)
                .where(
                    m.ReductionApplicabilityAssessment.project_id == project_id,
                    m.ReductionApplicabilityAssessment.methodology_id == methodology.id,
                )
                .order_by(m.ReductionApplicabilityAssessment.created_at.desc())
            )
            if assessment is None or assessment.status != "applicable":
                raise ReductionDomainError("The selected methodology has not passed applicability screening.")
        if data.run_kind == "ex_post":
            monitoring = await self.session.scalar(
                select(m.ReductionMonitoringPlan)
                .where(
                    m.ReductionMonitoringPlan.project_id == project_id,
                    m.ReductionMonitoringPlan.status == "published",
                    m.ReductionMonitoringPlan.readiness_status == "ready",
                )
                .order_by(m.ReductionMonitoringPlan.version.desc())
            )
            if monitoring is None:
                raise ReductionDomainError("A published, ready monitoring plan is required for ex-post calculation.")
        key = data.idempotency_key or hashlib.sha256(
            msgspec.json.encode(
                {
                    "project": project_id,
                    "methodology": methodology.code,
                    "baseline": baseline.id,
                    "kind": data.run_kind,
                    "start": data.period_start.isoformat(),
                    "end": data.period_end.isoformat(),
                    "inputs": data.inputs,
                },
                order="sorted",
            )
        ).hexdigest()
        existing = await self.session.scalar(
            select(m.ReductionCalculationRun).where(m.ReductionCalculationRun.idempotency_key == key)
        )
        if existing is not None:
            return existing
        run = m.ReductionCalculationRun(
            project_id=project_id,
            methodology_id=methodology.id,
            baseline_id=baseline.id,
            idempotency_key=key,
            run_kind=data.run_kind,
            status="running",
            assurance_status="monitored" if data.run_kind == "ex_post" else "estimated",
            period_start=data.period_start,
            period_end=data.period_end,
            input_snapshot=data.inputs,
            factor_snapshot=data.factor_snapshot,
            methodology_snapshot=self._methodology_snapshot(methodology),
            baseline_snapshot=self._baseline_snapshot(baseline),
        )
        self.session.add(run)
        await self.session.flush()
        try:
            result = calculate_reduction(methodology.code, data.inputs)
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            await self.session.commit()
            raise
        run.status = "completed"
        run.baseline_tco2e = result.baseline_tco2e
        run.project_tco2e = result.project_tco2e
        run.leakage_tco2e = result.leakage_tco2e
        run.deduction_tco2e = result.deduction_tco2e
        run.reduction_tco2e = result.reduction_tco2e
        run.components = result.components
        run.diagnostics = list(result.diagnostics)
        run.completed_at = _now()
        if data.run_kind == "ex_post":
            project.monitored_reduction_tco2e = result.reduction_tco2e
            project.reduction_status = "monitored"
            if project.status == "monitoring":
                project.status = "calculated"
        else:
            project.expected_reduction_tco2e = result.reduction_tco2e
        await self._audit("calculation", run.id, "calculation.completed", None, {"reductionTco2e": float(result.reduction_tco2e)}, project_id=project_id)
        await self.session.commit()
        return run

    async def create_financial_scenario(
        self, project_id: int, data: FinancialScenarioRequest
    ) -> m.ReductionFinancialScenario:
        await self._get(m.ReductionProject, project_id, "Reduction project not found.")
        if data.project_life_years <= 0 or not 0 <= data.discount_rate < 1:
            raise ReductionDomainError("Project life and discount rate are outside allowed ranges.")
        capex = _decimal(data.capex_cny)
        annual_net = _decimal(data.annual_energy_savings_cny) + _decimal(data.carbon_price_cny_per_t) * _decimal(
            data.annual_reduction_tco2e
        ) - _decimal(data.annual_opex_cny)
        discount = _decimal(data.discount_rate)
        npv = -capex + sum(annual_net / ((Decimal(1) + discount) ** year) for year in range(1, data.project_life_years + 1))
        payback = capex / annual_net if annual_net > 0 else None
        irr = _level_irr(capex, annual_net, data.project_life_years)
        macc = (capex / Decimal(data.project_life_years) + _decimal(data.annual_opex_cny) - _decimal(data.annual_energy_savings_cny)) / _decimal(
            data.annual_reduction_tco2e
        ) if data.annual_reduction_tco2e > 0 else None
        latest = await self.session.scalar(
            select(func.max(m.ReductionFinancialScenario.version)).where(m.ReductionFinancialScenario.project_id == project_id)
        )
        scenario = m.ReductionFinancialScenario(
            project_id=project_id,
            version=int(latest or 0) + 1,
            name=data.name,
            capex_cny=capex,
            annual_opex_cny=_decimal(data.annual_opex_cny),
            annual_energy_savings_cny=_decimal(data.annual_energy_savings_cny),
            carbon_price_cny_per_t=_decimal(data.carbon_price_cny_per_t),
            annual_reduction_tco2e=_decimal(data.annual_reduction_tco2e),
            project_life_years=data.project_life_years,
            discount_rate=discount,
            npv_cny=npv,
            irr=irr,
            payback_years=payback,
            macc_cny_per_t=macc,
            status="calculated",
        )
        self.session.add(scenario)
        await self.session.flush()
        await self._audit("financial_scenario", scenario.id, "financial.calculated", None, {"npvCny": float(npv)}, project_id=project_id)
        await self.session.commit()
        return scenario

    async def create_review(self, project_id: int, data: ProjectReviewRequest) -> m.ReductionProjectReview:
        project = await self._get(m.ReductionProject, project_id, "Reduction project not found.")
        if data.review_type not in {"internal", "validation", "verification"}:
            raise ReductionDomainError("Unsupported review type.")
        dossier = await self.session.scalar(select(m.CcerDossier).where(m.CcerDossier.project_id == project_id))
        validation_body = data.organization_name if data.review_type == "validation" else dossier.validation_body if dossier else None
        verification_body = data.organization_name if data.review_type == "verification" else dossier.verification_body if dossier else None
        CcerIssuancePolicy.ensure_independent_validation(validation_body, verification_body)
        review = m.ReductionProjectReview(
            project_id=project_id,
            calculation_run_id=data.calculation_run_id,
            review_type=data.review_type,
            decision=data.decision,
            reviewer_name=data.reviewer_name,
            organization_name=data.organization_name,
            reviewed_at=data.reviewed_at,
            findings=data.findings,
            conclusion=data.conclusion,
        )
        if data.calculation_run_id is not None:
            calculation = await self._get(
                m.ReductionCalculationRun,
                data.calculation_run_id,
                "Calculation run not found.",
            )
            if calculation.project_id != project_id:
                raise ReductionDomainError("The calculation run does not belong to this project.")
        self.session.add(review)
        if data.decision == "approved":
            if data.review_type == "internal":
                project.reduction_status = "internally_reviewed"
                if project.status == "calculated":
                    project.status = "internally_reviewed"
            elif data.review_type == "verification":
                project.reduction_status = "verified"
                if project.status == "internally_reviewed":
                    project.status = "verified"
                if data.calculation_run_id:
                    run = await self._get(m.ReductionCalculationRun, data.calculation_run_id, "Calculation run not found.")
                    run.assurance_status = "verified"
                    project.verified_reduction_tco2e = run.reduction_tco2e or Decimal(0)
        await self.session.flush()
        await self._audit("review", review.id, "review.recorded", None, {"type": data.review_type, "decision": data.decision}, project_id=project_id)
        await self.session.commit()
        return review

    async def save_ccer_dossier(self, project_id: int, data: CcerDossierRequest) -> m.CcerDossier:
        project = await self._get(m.ReductionProject, project_id, "Reduction project not found.")
        if project.track != "ccer_project":
            raise ReductionDomainError("A CCER dossier is available only for CCER projects.")
        CcerIssuancePolicy.ensure_independent_validation(data.validation_body, data.verification_body)
        dossier = await self.session.scalar(select(m.CcerDossier).where(m.CcerDossier.project_id == project_id))
        previous_status = dossier.status if dossier is not None else "preparation"
        status_sequence = ("preparation", "validated", "verified", "registered", "issued")
        if data.status not in status_sequence:
            raise ReductionDomainError("Unsupported CCER dossier status.")
        if status_sequence.index(data.status) < status_sequence.index(previous_status):
            raise ReductionDomainError("CCER dossier status cannot move backwards.")
        if status_sequence.index(data.status) > status_sequence.index(previous_status) + 1:
            raise ReductionDomainError("CCER dossier stages must be recorded in sequence.")
        if data.status in {"validated", "verified"}:
            required_review = "validation" if data.status == "validated" else "verification"
            approved_review = await self.session.scalar(
                select(m.ReductionProjectReview.id).where(
                    m.ReductionProjectReview.project_id == project_id,
                    m.ReductionProjectReview.review_type == required_review,
                    m.ReductionProjectReview.decision == "approved",
                )
            )
            if approved_review is None:
                message = f"An approved {required_review} review is required for this CCER stage."
                raise ReductionDomainError(message)
        if dossier is None:
            dossier = m.CcerDossier(project_id=project_id)
            self.session.add(dossier)
        for field, value in data.to_dict().items():
            if field == "issued_quantity_tco2e" and value is not None:
                value = _decimal(value)
            setattr(dossier, field, value)
        if dossier.status == "issued":
            if previous_status not in {"registered", "issued"}:
                raise ReductionDomainError("Only a registered CCER dossier can be recorded as issued.")
            if not dossier.issuance_no or not dossier.issuance_date or not dossier.issued_quantity_tco2e:
                raise ReductionDomainError("Issuance number, date, and quantity are required for issued CCER.")
            project.status = "issued"
            project.reduction_status = "issued"
        elif dossier.status == "registered" and project.status == "verified":
            project.status = "registered"
            project.reduction_status = "registered"
        await self.session.flush()
        await self._audit("ccer_dossier", dossier.id, "ccer.dossier_saved", None, {"status": dossier.status}, project_id=project_id)
        await self.session.commit()
        return dossier

    async def link_issuance(self, project_id: int, account_id: int, market_price: float | None) -> CarbonAssetLot:
        project = await self._get(m.ReductionProject, project_id, "Reduction project not found.")
        dossier = await self.session.scalar(select(m.CcerDossier).where(m.CcerDossier.project_id == project_id))
        if dossier is None:
            raise ReductionDomainError("CCER dossier not found.")
        CcerIssuancePolicy.ensure_asset_eligible(
            project_track=project.track,
            dossier_status=dossier.status,
            verified_tco2e=dossier.issued_quantity_tco2e,
        )
        if dossier.carbon_asset_lot_id:
            return await self._get(CarbonAssetLot, dossier.carbon_asset_lot_id, "Carbon asset lot not found.")
        account = await self._get(CarbonAssetAccount, account_id, "Carbon asset account not found.")
        instrument = await self._get(CarbonAssetInstrument, account.instrument_id, "Carbon asset instrument not found.")
        if instrument.instrument_class != "CCER" or instrument.native_unit != "tCO2e":
            raise ReductionDomainError("CCER issuance must be linked to a CCER account denominated in tCO2e.")
        lot_no = dossier.issuance_no or f"CCER-{project.code}"
        existing = await self.session.scalar(select(CarbonAssetLot).where(CarbonAssetLot.lot_no == lot_no))
        if existing is not None:
            dossier.carbon_asset_lot_id = existing.id
            await self.session.commit()
            return existing
        lot = CarbonAssetLot(
            account_id=account_id,
            instrument_id=instrument.id,
            lot_no=lot_no,
            registry_serial_no=dossier.issuance_no,
            project_code=project.code,
            project_name=project.name,
            vintage_year=dossier.issuance_date.year if dossier.issuance_date else None,
            issued_quantity=dossier.issued_quantity_tco2e or Decimal(0),
            acquisition_unit_cost=_decimal(market_price) if market_price is not None else None,
            currency="CNY",
            valid_from=dossier.issuance_date,
            status="active",
            source_name="CCER签发台账",
            standard_code=(project.methodology_id and "CCER") or None,
            remark="由减碳项目签发记录生成。",
        )
        self.session.add(lot)
        await self.session.flush()
        dossier.carbon_asset_lot_id = lot.id
        await self._audit("ccer_dossier", dossier.id, "ccer.asset_linked", None, {"lotId": lot.id}, project_id=project_id)
        await self.session.commit()
        return lot

    async def _get(self, model: type[Any], object_id: int, message: str) -> Any:
        obj = await self.session.get(model, object_id)
        if obj is None:
            raise NotFoundException(detail=message)
        return obj

    async def _audit(
        self,
        entity_type: str,
        entity_id: int | None,
        event_type: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        *,
        project_id: int | None = None,
        actor_name: str | None = None,
        reason: str | None = None,
    ) -> None:
        self.session.add(
            m.ReductionAuditEvent(
                project_id=project_id or (entity_id if entity_type == "project" else None),
                entity_type=entity_type,
                entity_id=entity_id,
                event_type=event_type,
                actor_name=actor_name,
                before_snapshot=before or {},
                after_snapshot=after or {},
                reason=reason,
            )
        )

    @staticmethod
    def _project_snapshot(project: m.ReductionProject) -> dict[str, Any]:
        return _snapshot(
            project,
            (
                "code",
                "name",
                "track",
                "category",
                "status",
                "reduction_status",
                "progress_pct",
                "investment_cny",
                "expected_reduction_tco2e",
                "monitored_reduction_tco2e",
                "verified_reduction_tco2e",
            ),
        )

    @staticmethod
    def _methodology_snapshot(methodology: m.ReductionMethodologyVersion) -> dict[str, Any]:
        return _snapshot(
            methodology,
            ("code", "version", "name", "status", "source_url", "source_sha256", "adapter_code", "parameter_schema"),
        )

    @staticmethod
    def _baseline_snapshot(baseline: m.ReductionBaselineScenario) -> dict[str, Any]:
        return _snapshot(
            baseline,
            ("id", "version", "period_start", "period_end", "model_kind", "model_parameters", "factor_snapshot", "baseline_tco2e", "locked_at"),
        )
