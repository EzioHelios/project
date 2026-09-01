"""Read models for reduction overview, project workbench, and methodology reference pages."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from advanced_alchemy.utils.text import camelize
from sqlalchemy import desc, func, select

from app.domain.carbon.models import MonitorSector
from app.domain.decarbonization import models as m
from app.domain.ghg_inventory.models import GhgCalculationRun

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _model_payload(obj: object, fields: tuple[str, ...]) -> dict[str, Any]:
    return {camelize(field).replace("Tco2e", "Tco2E"): _value(getattr(obj, field, None)) for field in fields}


PROJECT_FIELDS = (
    "id",
    "code",
    "name",
    "track",
    "category",
    "status",
    "reduction_status",
    "risk_level",
    "owner_name",
    "department_name",
    "organization_boundary_id",
    "methodology_id",
    "target_id",
    "planned_start",
    "planned_end",
    "actual_start",
    "progress_pct",
    "investment_cny",
    "expected_reduction_tco2e",
    "monitored_reduction_tco2e",
    "verified_reduction_tco2e",
    "objective",
    "implementation_plan",
    "evaluation_summary",
    "inventory_impact_kind",
    "source_name",
    "created_at",
    "updated_at",
)


class DecarbonizationQueryService:
    """Build tenant-filtered read projections without crossing mutation boundaries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def overview(
        self,
        *,
        target_year: int | None = None,
        category: str | None = None,
        status: str | None = None,
        area_id: int | None = None,
    ) -> dict[str, Any]:
        target_stmt = select(m.ReductionTarget).where(m.ReductionTarget.status == "published")
        if target_year is not None:
            target_stmt = target_stmt.where(m.ReductionTarget.target_year == target_year)
        target = await self.session.scalar(target_stmt.order_by(desc(m.ReductionTarget.target_year), desc(m.ReductionTarget.version)))

        project_stmt = select(m.ReductionProject)
        if category:
            project_stmt = project_stmt.where(m.ReductionProject.category == category)
        if status:
            project_stmt = project_stmt.where(m.ReductionProject.status == status)
        if area_id is not None:
            project_stmt = project_stmt.join(
                m.ReductionProjectResourceLink,
                m.ReductionProjectResourceLink.project_id == m.ReductionProject.id,
            ).where(m.ReductionProjectResourceLink.area_id == area_id)
        projects = list((await self.session.scalars(project_stmt.order_by(desc(m.ReductionProject.updated_at)))).unique().all())

        latest_inventory = await self.session.scalar(
            select(GhgCalculationRun)
            .where(GhgCalculationRun.status == "completed")
            .order_by(desc(GhgCalculationRun.completed_at))
        )
        actual_tco2e = float((latest_inventory.total_co2e_kg or Decimal(0)) / Decimal(1000)) if latest_inventory else 0.0
        expected = sum(float(row.expected_reduction_tco2e) for row in projects)
        monitored = sum(float(row.monitored_reduction_tco2e) for row in projects)
        verified = sum(float(row.verified_reduction_tco2e) for row in projects)
        issued = await self.session.scalar(
            select(func.coalesce(func.sum(m.CcerDossier.issued_quantity_tco2e), 0)).where(m.CcerDossier.status == "issued")
        )
        baseline = float(target.baseline_tco2e) if target else 0.0
        target_reduction = float(target.target_reduction_tco2e) if target else 0.0
        target_emissions = max(0.0, baseline - target_reduction)
        gap = actual_tco2e - target_emissions if target else 0.0

        trajectory = list(target.trajectory) if target else []
        if actual_tco2e:
            trajectory.append(
                {
                    "period": str(datetime.now(UTC).year),
                    "actualTco2e": actual_tco2e,
                    "targetTco2e": target_emissions,
                    "forecastTco2e": max(0.0, actual_tco2e - expected),
                }
            )
        contribution = await self._area_contribution(projects)
        return {
            "metrics": {
                "actualInventoryTco2E": actual_tco2e,
                "targetEmissionsTco2E": target_emissions,
                "targetGapTco2E": gap,
                "expectedReductionTco2E": expected,
                "monitoredReductionTco2E": monitored,
                "verifiedReductionTco2E": verified,
                "issuedCcerTco2E": float(issued or 0),
                "projectCount": len(projects),
                "onTrackCount": sum(row.progress_pct >= Decimal(50) and row.risk_level != "high" for row in projects),
            },
            "inventoryReference": {
                "runCode": latest_inventory.run_code if latest_inventory else None,
                "completedAt": _value(latest_inventory.completed_at) if latest_inventory else None,
                "sourceKind": "organization_inventory",
            },
            "target": self._target_payload(target) if target else None,
            "trend": trajectory,
            "waterfall": [
                {"name": "基准排放", "value": baseline, "kind": "total"},
                {"name": "盘查实际变化", "value": actual_tco2e - baseline if baseline else 0, "kind": "change"},
                {"name": "当前实际排放", "value": actual_tco2e, "kind": "total"},
            ],
            "projectReduction": {
                "expected": expected,
                "monitored": monitored,
                "verified": verified,
                "noteCode": "separate_from_inventory",
            },
            "contribution": contribution,
            "portfolio": [
                {
                    "id": row.id,
                    "name": row.name,
                    "category": row.category,
                    "investmentCny": float(row.investment_cny),
                    "reductionTco2e": float(row.verified_reduction_tco2e or row.monitored_reduction_tco2e or row.expected_reduction_tco2e),
                    "progressPct": float(row.progress_pct),
                    "riskLevel": row.risk_level,
                    "status": row.status,
                }
                for row in projects
            ],
            "keyMeasures": [self._project_payload(row) for row in projects[:8]],
        }

    async def targets(self, *, status: str | None = None) -> list[dict[str, Any]]:
        stmt = select(m.ReductionTarget)
        if status:
            stmt = stmt.where(m.ReductionTarget.status == status)
        rows = (await self.session.scalars(stmt.order_by(desc(m.ReductionTarget.target_year), desc(m.ReductionTarget.version)))).all()
        return [self._target_payload(row) for row in rows]

    async def projects(
        self,
        *,
        keyword: str | None = None,
        track: str | None = None,
        category: str | None = None,
        status: str | None = None,
        risk_level: str | None = None,
        methodology_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        conditions = []
        if keyword:
            pattern = f"%{keyword}%"
            conditions.append((m.ReductionProject.code.ilike(pattern)) | (m.ReductionProject.name.ilike(pattern)))
        if track:
            conditions.append(m.ReductionProject.track == track)
        if category:
            conditions.append(m.ReductionProject.category == category)
        if status:
            conditions.append(m.ReductionProject.status == status)
        if risk_level:
            conditions.append(m.ReductionProject.risk_level == risk_level)
        if methodology_id is not None:
            conditions.append(m.ReductionProject.methodology_id == methodology_id)
        total = await self.session.scalar(select(func.count(m.ReductionProject.id)).where(*conditions))
        rows = (
            await self.session.scalars(
                select(m.ReductionProject)
                .where(*conditions)
                .order_by(desc(m.ReductionProject.updated_at))
                .limit(min(max(limit, 1), 500))
                .offset(max(offset, 0))
            )
        ).all()
        methodology_ids = {row.methodology_id for row in rows if row.methodology_id}
        methods = {
            row.id: row
            for row in (
                await self.session.scalars(
                    select(m.ReductionMethodologyVersion).where(m.ReductionMethodologyVersion.id.in_(methodology_ids))
                )
            ).all()
        } if methodology_ids else {}
        project_ids = [row.id for row in rows]
        latest_baselines = await self._latest_locked_baselines(project_ids)
        latest_calculations = await self._latest_calculations(project_ids)
        return {
            "items": [
                self._project_payload(
                    row,
                    methods.get(row.methodology_id) if row.methodology_id else None,
                    latest_baselines.get(row.id),
                    latest_calculations.get(row.id),
                )
                for row in rows
            ],
            "total": int(total or 0),
            "limit": limit,
            "offset": offset,
        }

    async def project(self, project_id: int) -> dict[str, Any] | None:
        project = await self.session.get(m.ReductionProject, project_id)
        if project is None:
            return None
        methodology = await self.session.get(m.ReductionMethodologyVersion, project.methodology_id) if project.methodology_id else None
        resources = (
            await self.session.scalars(
                select(m.ReductionProjectResourceLink)
                .where(m.ReductionProjectResourceLink.project_id == project_id)
                .order_by(m.ReductionProjectResourceLink.id)
            )
        ).all()
        boundaries = (
            await self.session.scalars(
                select(m.ReductionProjectBoundary)
                .where(m.ReductionProjectBoundary.project_id == project_id)
                .order_by(desc(m.ReductionProjectBoundary.version))
            )
        ).all()
        baselines = (
            await self.session.scalars(
                select(m.ReductionBaselineScenario)
                .where(m.ReductionBaselineScenario.project_id == project_id)
                .order_by(desc(m.ReductionBaselineScenario.version))
            )
        ).all()
        assessments = (
            await self.session.scalars(
                select(m.ReductionApplicabilityAssessment)
                .where(m.ReductionApplicabilityAssessment.project_id == project_id)
                .order_by(desc(m.ReductionApplicabilityAssessment.created_at))
            )
        ).all()
        monitoring = (
            await self.session.scalars(
                select(m.ReductionMonitoringPlan)
                .where(m.ReductionMonitoringPlan.project_id == project_id)
                .order_by(desc(m.ReductionMonitoringPlan.version))
            )
        ).all()
        calculations = (
            await self.session.scalars(
                select(m.ReductionCalculationRun)
                .where(m.ReductionCalculationRun.project_id == project_id)
                .order_by(desc(m.ReductionCalculationRun.created_at))
            )
        ).all()
        financial = (
            await self.session.scalars(
                select(m.ReductionFinancialScenario)
                .where(m.ReductionFinancialScenario.project_id == project_id)
                .order_by(desc(m.ReductionFinancialScenario.version))
            )
        ).all()
        reviews = (
            await self.session.scalars(
                select(m.ReductionProjectReview)
                .where(m.ReductionProjectReview.project_id == project_id)
                .order_by(desc(m.ReductionProjectReview.reviewed_at))
            )
        ).all()
        dossier = await self.session.scalar(select(m.CcerDossier).where(m.CcerDossier.project_id == project_id))
        evidence_count = await self._evidence_count(project.code)
        latest_baseline = next((row for row in baselines if row.status == "locked"), baselines[0] if baselines else None)
        latest_calculation = calculations[0] if calculations else None
        return {
            **self._project_payload(project, methodology, latest_baseline, latest_calculation),
            "resources": [
                _model_payload(
                    row,
                    (
                        "id",
                        "resource_type",
                        "resource_key",
                        "area_id",
                        "equipment_id",
                        "measurement_boundary_id",
                        "role",
                        "allocation_ratio",
                        "resource_snapshot",
                    ),
                )
                for row in resources
            ],
            "boundaries": [
                _model_payload(
                    row,
                    (
                        "id",
                        "version",
                        "status",
                        "physical_boundary",
                        "ghg_sources_sinks",
                        "included_gases",
                        "exclusions",
                        "organization_snapshot",
                        "locked_at",
                    ),
                )
                for row in boundaries
            ],
            "baselines": [self._baseline_payload(row) for row in baselines],
            "assessments": [
                _model_payload(
                    row,
                    (
                        "id",
                        "methodology_id",
                        "status",
                        "answers",
                        "checks",
                        "blocking_reasons",
                        "methodology_snapshot",
                        "assessed_by",
                        "created_at",
                    ),
                )
                for row in assessments
            ],
            "monitoringPlans": [
                _model_payload(
                    row,
                    (
                        "id",
                        "version",
                        "status",
                        "parameters",
                        "quality_controls",
                        "evidence_requirements",
                        "data_retention_years",
                        "readiness_status",
                        "published_at",
                    ),
                )
                for row in monitoring
            ],
            "calculations": [self._calculation_payload(row) for row in calculations],
            "financialScenarios": [
                _model_payload(
                    row,
                    (
                        "id",
                        "version",
                        "name",
                        "capex_cny",
                        "annual_opex_cny",
                        "annual_energy_savings_cny",
                        "carbon_price_cny_per_t",
                        "annual_reduction_tco2e",
                        "project_life_years",
                        "discount_rate",
                        "npv_cny",
                        "irr",
                        "payback_years",
                        "macc_cny_per_t",
                        "status",
                    ),
                )
                for row in financial
            ],
            "reviews": [
                _model_payload(
                    row,
                    (
                        "id",
                        "calculation_run_id",
                        "review_type",
                        "decision",
                        "reviewer_name",
                        "organization_name",
                        "reviewed_at",
                        "findings",
                        "conclusion",
                    ),
                )
                for row in reviews
            ],
            "ccerDossier": self._dossier_payload(dossier) if dossier else None,
            "evidenceCount": evidence_count,
        }

    async def methodologies(
        self, *, keyword: str | None = None, sector: str | None = None, executable: bool | None = None
    ) -> list[dict[str, Any]]:
        conditions = [m.ReductionMethodologyVersion.status == "published"]
        if keyword:
            pattern = f"%{keyword}%"
            conditions.append(
                (m.ReductionMethodologyVersion.code.ilike(pattern))
                | (m.ReductionMethodologyVersion.name.ilike(pattern))
            )
        if sector:
            conditions.append(m.ReductionMethodologyVersion.sector == sector)
        if executable is not None:
            conditions.append(m.ReductionMethodologyVersion.executable.is_(executable))
        rows = (
            await self.session.scalars(
                select(m.ReductionMethodologyVersion)
                .where(*conditions)
                .order_by(m.ReductionMethodologyVersion.code)
            )
        ).all()
        return [self._methodology_payload(row) for row in rows]

    async def methodology(self, methodology_id: int) -> dict[str, Any] | None:
        row = await self.session.get(m.ReductionMethodologyVersion, methodology_id)
        return self._methodology_payload(row) if row else None

    async def calculation(self, run_id: int) -> dict[str, Any] | None:
        row = await self.session.get(m.ReductionCalculationRun, run_id)
        return self._calculation_payload(row) if row else None

    async def audit_events(self, project_id: int) -> list[dict[str, Any]]:
        rows = (
            await self.session.scalars(
                select(m.ReductionAuditEvent)
                .where(m.ReductionAuditEvent.project_id == project_id)
                .order_by(desc(m.ReductionAuditEvent.created_at))
            )
        ).all()
        return [
            _model_payload(
                row,
                (
                    "id",
                    "entity_type",
                    "entity_id",
                    "event_type",
                    "actor_name",
                    "before_snapshot",
                    "after_snapshot",
                    "reason",
                    "created_at",
                ),
            )
            for row in rows
        ]

    async def _area_contribution(self, projects: list[m.ReductionProject]) -> list[dict[str, Any]]:
        project_ids = [row.id for row in projects]
        if not project_ids:
            return []
        rows = (
            await self.session.execute(
                select(m.ReductionProjectResourceLink.area_id, MonitorSector.name, m.ReductionProject.id)
                .join(MonitorSector, MonitorSector.id == m.ReductionProjectResourceLink.area_id, isouter=True)
                .join(m.ReductionProject, m.ReductionProject.id == m.ReductionProjectResourceLink.project_id)
                .where(m.ReductionProjectResourceLink.project_id.in_(project_ids))
            )
        ).all()
        project_by_id = {row.id: row for row in projects}
        totals: dict[str, float] = {}
        for area_id, area_name, project_id in rows:
            name = area_name or (f"区域 {area_id}" if area_id else "未分配区域")
            project = project_by_id[project_id]
            totals[name] = totals.get(name, 0) + float(
                project.verified_reduction_tco2e or project.monitored_reduction_tco2e or project.expected_reduction_tco2e
            )
        return [{"name": name, "value": value} for name, value in sorted(totals.items(), key=lambda item: item[1], reverse=True)]

    async def _evidence_count(self, project_code: str) -> int:
        from app.domain.ghg_inventory.models import GhgEvidenceLink

        count = await self.session.scalar(
            select(func.count(func.distinct(GhgEvidenceLink.evidence_id))).where(
                GhgEvidenceLink.record_type == "reduction_project",
                GhgEvidenceLink.record_code == project_code,
            )
        )
        return int(count or 0)

    async def _latest_locked_baselines(self, project_ids: list[int]) -> dict[int, m.ReductionBaselineScenario]:
        if not project_ids:
            return {}
        rows = (
            await self.session.scalars(
                select(m.ReductionBaselineScenario)
                .where(
                    m.ReductionBaselineScenario.project_id.in_(project_ids),
                    m.ReductionBaselineScenario.status == "locked",
                )
                .order_by(m.ReductionBaselineScenario.project_id, desc(m.ReductionBaselineScenario.version))
            )
        ).all()
        latest: dict[int, m.ReductionBaselineScenario] = {}
        for row in rows:
            latest.setdefault(row.project_id, row)
        return latest

    async def _latest_calculations(self, project_ids: list[int]) -> dict[int, m.ReductionCalculationRun]:
        if not project_ids:
            return {}
        rows = (
            await self.session.scalars(
                select(m.ReductionCalculationRun)
                .where(m.ReductionCalculationRun.project_id.in_(project_ids))
                .order_by(m.ReductionCalculationRun.project_id, desc(m.ReductionCalculationRun.created_at))
            )
        ).all()
        latest: dict[int, m.ReductionCalculationRun] = {}
        for row in rows:
            latest.setdefault(row.project_id, row)
        return latest

    @staticmethod
    def _project_payload(
        row: m.ReductionProject,
        methodology: m.ReductionMethodologyVersion | None = None,
        latest_baseline: m.ReductionBaselineScenario | None = None,
        latest_calculation: m.ReductionCalculationRun | None = None,
    ) -> dict[str, Any]:
        payload = _model_payload(row, PROJECT_FIELDS)
        payload.update(
            {
                "latestLockedBaselineTco2E": _value(latest_baseline.baseline_tco2e) if latest_baseline else None,
                "latestCalculationBaselineTco2E": _value(latest_calculation.baseline_tco2e)
                if latest_calculation
                else None,
                "latestCalculationProjectTco2E": _value(latest_calculation.project_tco2e)
                if latest_calculation
                else None,
                "latestCalculationReductionTco2E": _value(latest_calculation.reduction_tco2e)
                if latest_calculation
                else None,
                "latestCalculationStatus": latest_calculation.status if latest_calculation else None,
            }
        )
        payload["methodology"] = (
            {"id": methodology.id, "code": methodology.code, "name": methodology.name, "version": methodology.version}
            if methodology
            else None
        )
        return payload

    @staticmethod
    def _target_payload(row: m.ReductionTarget) -> dict[str, Any]:
        return _model_payload(
            row,
            (
                "id",
                "code",
                "name",
                "version",
                "target_year",
                "baseline_year",
                "target_type",
                "baseline_tco2e",
                "target_reduction_tco2e",
                "target_reduction_pct",
                "organization_boundary_id",
                "area_id",
                "business_unit",
                "trajectory",
                "status",
                "source_name",
                "published_at",
            ),
        )

    @staticmethod
    def _methodology_payload(row: m.ReductionMethodologyVersion) -> dict[str, Any]:
        return _model_payload(
            row,
            (
                "id",
                "code",
                "version",
                "name",
                "sector",
                "method_kind",
                "status",
                "published_on",
                "effective_from",
                "effective_to",
                "source_url",
                "source_sha256",
                "executable",
                "adapter_code",
                "parameter_schema",
                "applicability_schema",
                "monitoring_schema",
                "evidence_schema",
            ),
        )

    @staticmethod
    def _baseline_payload(row: m.ReductionBaselineScenario) -> dict[str, Any]:
        return _model_payload(
            row,
            (
                "id",
                "version",
                "name",
                "status",
                "period_start",
                "period_end",
                "model_kind",
                "model_parameters",
                "normalization_variables",
                "factor_snapshot",
                "inventory_reference",
                "baseline_tco2e",
                "locked_at",
            ),
        )

    @staticmethod
    def _calculation_payload(row: m.ReductionCalculationRun) -> dict[str, Any]:
        return _model_payload(
            row,
            (
                "id",
                "project_id",
                "methodology_id",
                "baseline_id",
                "run_kind",
                "status",
                "assurance_status",
                "period_start",
                "period_end",
                "input_snapshot",
                "methodology_snapshot",
                "baseline_snapshot",
                "factor_snapshot",
                "baseline_tco2e",
                "project_tco2e",
                "leakage_tco2e",
                "deduction_tco2e",
                "reduction_tco2e",
                "components",
                "diagnostics",
                "completed_at",
                "error_message",
                "created_at",
            ),
        )

    @staticmethod
    def _dossier_payload(row: m.CcerDossier) -> dict[str, Any]:
        return _model_payload(
            row,
            (
                "id",
                "project_id",
                "status",
                "project_design_document_no",
                "validation_body",
                "verification_body",
                "registration_no",
                "registration_date",
                "issuance_no",
                "issuance_date",
                "issued_quantity_tco2e",
                "material_checklist",
                "milestones",
                "carbon_asset_lot_id",
                "updated_at",
            ),
        )
