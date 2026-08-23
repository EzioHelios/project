"""Read projections for automatic SBTi, CDP, and RE100 tracking."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import extract, func, or_, select

from app.domain.carbon.models import EnergyIntervalFact, ReportingPeriod
from app.domain.climate_governance import models as m
from app.domain.climate_governance.domain import assess_cdp_readiness, assess_re100_progress, assess_sbti_progress
from app.domain.decarbonization.models import ReductionProject
from app.domain.ghg_inventory.models import GhgCalculationResult, GhgCalculationRun, GhgEvidenceLink, GhgInventoryReport

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


ELECTRICITY_CODES = ("electricity", "grid_electricity", "purchased_electricity", "power")


class ClimateGovernanceQueryService:
    """Build one tenant-filtered workbench from authoritative source domains."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def programs(self, reporting_year: int | None = None) -> list[dict[str, Any]]:
        stmt = select(m.ClimateProgram)
        if reporting_year is not None:
            stmt = stmt.where(m.ClimateProgram.reporting_year == reporting_year)
        rows = list(
            (
                await self.session.scalars(
                    stmt.order_by(m.ClimateProgram.reporting_year.desc(), m.ClimateProgram.framework)
                )
            ).all()
        )
        return [self.program_payload(row) for row in rows]

    async def inventory_snapshot(self, *, reporting_year: int, scope2_method: str = "location") -> dict[str, Any]:
        """Return the latest authoritative inventory at or before one disclosure year."""

        rows = await self._inventory_history(scope2_method=scope2_method)
        return next(
            (item for item in reversed(rows) if item["year"] <= reporting_year),
            {
                "year": reporting_year,
                "scope1Tco2e": 0.0,
                "scope2Tco2e": 0.0,
                "scope3Tco2e": 0.0,
                "totalTco2e": 0.0,
                "runCode": None,
                "completedAt": None,
            },
        )

    async def claims(self, *, program_id: int | None = None, reporting_year: int | None = None) -> list[dict[str, Any]]:
        stmt = select(m.RenewableElectricityClaim)
        if program_id is not None:
            stmt = stmt.where(m.RenewableElectricityClaim.program_id == program_id)
        if reporting_year is not None:
            stmt = stmt.where(m.RenewableElectricityClaim.reporting_year == reporting_year)
        rows = list((await self.session.scalars(stmt.order_by(m.RenewableElectricityClaim.period_end.desc()))).all())
        return [self.claim_payload(row) for row in rows]

    async def overview(self, *, reporting_year: int) -> dict[str, Any]:
        programs = await self._program_map(reporting_year)
        targets = await self._target_map(programs)
        sbti_target = targets.get("sbti")
        scope2_method = sbti_target.scope2_method if sbti_target else "location"
        inventory_rows = await self._inventory_history(scope2_method=scope2_method)
        scope = next(
            (item for item in reversed(inventory_rows) if item["year"] <= reporting_year),
            {
                "year": reporting_year,
                "scope1Tco2e": 0.0,
                "scope2Tco2e": 0.0,
                "scope3Tco2e": 0.0,
                "totalTco2e": 0.0,
                "runCode": None,
                "completedAt": None,
            },
        )

        sbti_program = programs.get("sbti")
        annualization_factor = Decimal(str(scope.get("annualizationFactor") or 1))
        sbti = assess_sbti_progress(
            reporting_year=reporting_year,
            scope1_tco2e=Decimal(str(scope["scope1Tco2e"])) * annualization_factor,
            scope2_tco2e=Decimal(str(scope["scope2Tco2e"])) * annualization_factor,
            scope3_tco2e=Decimal(str(scope["scope3Tco2e"])) * annualization_factor,
            baseline_year=sbti_target.baseline_year if sbti_target else None,
            baseline_tco2e=sbti_target.baseline_value if sbti_target else None,
            target_year=sbti_target.target_year if sbti_target else None,
            reduction_pct=sbti_target.reduction_pct if sbti_target else None,
            scope12_coverage_pct=Decimal(str((sbti_target.scope_coverage or {}).get("scope12Pct", 0)))
            if sbti_target
            else Decimal(0),
            scope3_coverage_pct=Decimal(str((sbti_target.scope_coverage or {}).get("scope3Pct", 0)))
            if sbti_target
            else Decimal(0),
        )
        sbti["trackingTco2e"] = sbti["actualTco2e"]
        sbti["actualTco2e"] = float(scope["totalTco2e"] or 0)
        sbti["actualKind"] = "full_year" if scope.get("isFullYear", True) else "partial_year"
        sbti["actualPeriodEnd"] = scope.get("periodEnd")
        sbti["programId"] = sbti_program.id if sbti_program else None
        sbti["target"] = self.target_payload(sbti_target) if sbti_target else None

        re100_program = programs.get("re100")
        re100_target = targets.get("re100")
        re100_configuration = dict(re100_program.configuration or {}) if re100_program else {}
        electricity_data_year = int(re100_configuration.get("electricityDataYear", reporting_year))
        electricity_mwh = await self._electricity_mwh(electricity_data_year)
        claims = await self.claims(
            program_id=re100_program.id if re100_program else None, reporting_year=electricity_data_year
        )
        eligible_mwh = sum(
            (Decimal(str(item["quantityMwh"])) for item in claims if item["eligibilityStatus"] == "eligible"),
            Decimal(0),
        )
        pending_mwh = sum(
            (Decimal(str(item["quantityMwh"])) for item in claims if item["eligibilityStatus"] != "eligible"),
            Decimal(0),
        )
        target_pct = Decimal(
            str(re100_target.target_value if re100_target and re100_target.target_value is not None else 100)
        )
        re100 = assess_re100_progress(
            reporting_year=electricity_data_year,
            total_electricity_mwh=electricity_mwh,
            eligible_mwh=eligible_mwh,
            pending_mwh=pending_mwh,
            target_pct=target_pct,
        )
        re100["programId"] = re100_program.id if re100_program else None
        re100["target"] = self.target_payload(re100_target) if re100_target else None
        re100["claims"] = claims
        re100["sourceMix"] = self._claim_mix(claims, electricity_mwh)
        re100["coverageSegments"] = [
            {"name": "经规则认可", "value": float(eligible_mwh), "status": "eligible"},
            {"name": "待核验", "value": float(pending_mwh), "status": "pending"},
            {
                "name": "其他电力",
                "value": float(max(Decimal(0), electricity_mwh - eligible_mwh - pending_mwh)),
                "status": "other",
            },
        ]

        cdp_program = programs.get("cdp")
        cdp_cycle = await self._disclosure_cycle(cdp_program)
        manual_domains = (
            dict(cdp_cycle.domain_statuses or {})
            if cdp_cycle
            else dict((cdp_program.configuration or {}).get("domainStatuses", {}))
            if cdp_program
            else {}
        )
        project_count = int(
            await self.session.scalar(select(func.count(ReductionProject.id)).where(ReductionProject.status != "draft"))
            or 0
        )
        evidence_count = int(await self.session.scalar(select(func.count(GhgEvidenceLink.id))) or 0)
        report_count = int(
            await self.session.scalar(
                select(func.count(GhgInventoryReport.id)).where(
                    GhgInventoryReport.status.in_(("approved", "published"))
                )
            )
            or 0
        )
        cdp_domains = {
            "governance": bool(manual_domains.get("governance")),
            "risks": bool(manual_domains.get("risks")),
            "strategy": bool(manual_domains.get("strategy")),
            "inventory": float(scope["totalTco2e"] or 0) > 0,
            "energy": electricity_mwh > 0,
            "targets": sbti_target is not None or bool(manual_domains.get("targets")),
            "actions": project_count > 0,
            "verification": report_count > 0 and evidence_count > 0,
        }
        cdp = assess_cdp_readiness(reporting_year=reporting_year, domains=cdp_domains)
        cdp["programId"] = cdp_program.id if cdp_program else None
        cdp["questionnaireVersion"] = cdp_cycle.questionnaire_version if cdp_cycle else "2026"
        cdp["cycleStatus"] = cdp_cycle.status if cdp_cycle else "not_configured"
        cdp["readinessMatrix"] = [
            {
                "domain": check["label"],
                "dimension": "内部准备状态",
                "status": "complete"
                if check["passed"]
                else "blocked"
                if check["severity"] == "blocking"
                else "missing",
                "detail": "已具备当前周期所需信息" if check["passed"] else "需补充当前周期数据或材料",
            }
            for check in cdp["checks"]
        ]

        trajectory = self._trajectory(inventory_rows, sbti_target, reporting_year)
        tasks = [
            {"framework": framework, **check}
            for framework, result in (("sbti", sbti), ("cdp", cdp), ("re100", re100))
            for check in result["checks"]
            if not check["passed"]
        ]
        return {
            "reportingYear": reporting_year,
            "programs": [self.program_payload(program) for program in programs.values()],
            "sourceStatus": {
                "inventoryRunCode": scope["runCode"],
                "inventoryCompletedAt": scope["completedAt"],
                "inventoryYear": scope["year"],
                "electricityDataYear": electricity_data_year,
                "electricityMwh": float(electricity_mwh),
                "reductionProjectCount": project_count,
                "evidenceCount": evidence_count,
            },
            "metrics": {
                "actualTco2e": float(scope["totalTco2e"] or 0),
                "sbtiReadinessPct": sbti["readinessPct"],
                "sbtiGapTco2e": sbti["gapTco2e"],
                "cdpReadinessPct": cdp["readinessPct"],
                "re100ProgressPct": re100["progressPct"],
                "renewableGapMwh": re100["gapMwh"],
                "actionCount": len(tasks),
            },
            "inventoryTrend": trajectory,
            "scopeBreakdown": [
                {"name": "Scope 1", "value": scope["scope1Tco2e"]},
                {"name": "Scope 2", "value": scope["scope2Tco2e"]},
                {"name": "Scope 3", "value": scope["scope3Tco2e"]},
            ],
            "sbti": sbti,
            "cdp": cdp,
            "re100": re100,
            "tasks": tasks[:12],
        }

    async def assessment_runs(self, *, program_id: int, limit: int = 20) -> list[dict[str, Any]]:
        rows = list(
            (
                await self.session.scalars(
                    select(m.ClimateAssessmentRun)
                    .where(m.ClimateAssessmentRun.program_id == program_id)
                    .order_by(m.ClimateAssessmentRun.completed_at.desc())
                    .limit(min(max(limit, 1), 100))
                )
            ).all()
        )
        return [
            {
                "id": row.id,
                "programId": row.program_id,
                "framework": row.framework,
                "reportingYear": row.reporting_year,
                "status": row.status,
                "metrics": row.metrics_snapshot,
                "checks": row.checks,
                "ruleSnapshot": row.rule_snapshot,
                "completedAt": row.completed_at.isoformat(),
            }
            for row in rows
        ]

    async def _program_map(self, reporting_year: int) -> dict[str, m.ClimateProgram]:
        rows = list(
            (
                await self.session.scalars(
                    select(m.ClimateProgram).where(
                        m.ClimateProgram.reporting_year == reporting_year, m.ClimateProgram.status != "archived"
                    )
                )
            ).all()
        )
        return {row.framework: row for row in rows}

    async def _target_map(self, programs: dict[str, m.ClimateProgram]) -> dict[str, m.ClimateTarget]:
        result: dict[str, m.ClimateTarget] = {}
        for framework, program in programs.items():
            target = await self.session.scalar(
                select(m.ClimateTarget)
                .where(m.ClimateTarget.program_id == program.id, m.ClimateTarget.status == "published")
                .order_by(m.ClimateTarget.version.desc())
            )
            if target:
                result[framework] = target
        return result

    async def _disclosure_cycle(self, program: m.ClimateProgram | None) -> m.ClimateDisclosureCycle | None:
        if program is None:
            return None
        return await self.session.scalar(
            select(m.ClimateDisclosureCycle).where(
                m.ClimateDisclosureCycle.program_id == program.id,
                m.ClimateDisclosureCycle.reporting_year == program.reporting_year,
            )
        )

    async def _inventory_history(self, *, scope2_method: str | None = None) -> list[dict[str, Any]]:
        rows = list(
            (
                await self.session.execute(
                    select(GhgCalculationRun, ReportingPeriod)
                    .outerjoin(ReportingPeriod, ReportingPeriod.id == GhgCalculationRun.reporting_period_id)
                    .where(GhgCalculationRun.status == "completed")
                    .order_by(ReportingPeriod.period_end.desc().nullslast(), GhgCalculationRun.completed_at.desc())
                )
            ).all()
        )
        latest: dict[int, tuple[GhgCalculationRun, ReportingPeriod | None]] = {}
        for run, period in rows:
            year = (
                period.period_end.year
                if period
                else (run.completed_at.year if run.completed_at else run.started_at.year)
            )
            latest.setdefault(year, (run, period))
        output: list[dict[str, Any]] = []
        for year, (run, period) in sorted(latest.items()):
            totals = await self._scope_totals(run, scope2_method or run.default_scope2_method)
            period_start = period.period_start if period else date(year, 1, 1)
            period_end = period.period_end if period else date(year, 12, 31)
            is_full_year = period_start <= date(year, 1, 1) and period_end >= date(year, 12, 31)
            covered_days = max((period_end - period_start).days + 1, 1)
            year_days = (date(year, 12, 31) - date(year, 1, 1)).days + 1
            annualization_factor = Decimal(1) if is_full_year else Decimal(year_days) / Decimal(covered_days)
            output.append(
                {
                    "year": year,
                    "scope1Tco2e": float(totals["scope1"] / Decimal(1000)),
                    "scope2Tco2e": float(totals["scope2"] / Decimal(1000)),
                    "scope3Tco2e": float(totals["scope3"] / Decimal(1000)),
                    "totalTco2e": float(sum(totals.values(), Decimal(0)) / Decimal(1000)),
                    "runCode": run.run_code,
                    "completedAt": run.completed_at.isoformat() if run.completed_at else None,
                    "periodStart": period_start.isoformat(),
                    "periodEnd": period_end.isoformat(),
                    "isFullYear": is_full_year,
                    "annualizationFactor": float(annualization_factor),
                    "annualizedTco2e": float(sum(totals.values(), Decimal(0)) / Decimal(1000) * annualization_factor),
                }
            )
        return output

    async def _scope_totals(self, run: GhgCalculationRun, scope2_method: str) -> dict[str, Decimal]:
        rows = list(
            (
                await self.session.execute(
                    select(GhgCalculationResult.ghg_scope, func.sum(GhgCalculationResult.co2e_kg))
                    .where(
                        GhgCalculationResult.run_id == run.id,
                        or_(
                            GhgCalculationResult.ghg_scope != "scope2",
                            GhgCalculationResult.scope2_method.in_(("not_applicable", scope2_method)),
                        ),
                    )
                    .group_by(GhgCalculationResult.ghg_scope)
                )
            ).all()
        )
        totals = {"scope1": Decimal(0), "scope2": Decimal(0), "scope3": Decimal(0)}
        for scope, value in rows:
            if scope in totals:
                totals[scope] = Decimal(value or 0)
        return totals

    async def _electricity_mwh(self, reporting_year: int) -> Decimal:
        value = await self.session.scalar(
            select(func.coalesce(func.sum(EnergyIntervalFact.amount), 0)).where(
                EnergyIntervalFact.is_current.is_(True),
                func.lower(EnergyIntervalFact.energy_type_code).in_(ELECTRICITY_CODES),
                extract("year", EnergyIntervalFact.period_start) == reporting_year,
            )
        )
        return Decimal(value or 0) / Decimal(1000)

    @staticmethod
    def _trajectory(
        inventory_rows: list[dict[str, Any]], target: m.ClimateTarget | None, reporting_year: int
    ) -> list[dict[str, Any]]:
        by_year = {int(item["year"]): item for item in inventory_rows}
        years = sorted(by_year)
        if target:
            years = sorted(set(years) | set(range(target.baseline_year, max(target.target_year, reporting_year) + 1)))
        output: list[dict[str, Any]] = []
        for year in years:
            target_value: float | None = None
            if target and target.reduction_pct is not None and target.target_year > target.baseline_year:
                elapsed = max(0, min(year - target.baseline_year, target.target_year - target.baseline_year))
                end = target.baseline_value * (Decimal(1) - target.reduction_pct / Decimal(100))
                path = target.baseline_value - (target.baseline_value - end) * Decimal(elapsed) / Decimal(
                    target.target_year - target.baseline_year
                )
                target_value = float(path)
            inventory = by_year.get(year, {})
            is_full_year = bool(inventory.get("isFullYear", True))
            output.append(
                {
                    "period": str(year),
                    "actual": inventory.get("totalTco2e") if is_full_year else None,
                    "forecast": inventory.get("annualizedTco2e") if inventory and not is_full_year else None,
                    "scope1": inventory.get("scope1Tco2e"),
                    "scope2": inventory.get("scope2Tco2e"),
                    "scope3": inventory.get("scope3Tco2e"),
                    "target": target_value,
                    "reference": target_value,
                }
            )
        for index, item in enumerate(output):
            if item.get("forecast") is not None and index > 0:
                previous = output[index - 1]
                previous["forecast"] = previous.get("actual")
        return output

    @staticmethod
    def _claim_mix(claims: list[dict[str, Any]], total_electricity_mwh: Decimal) -> list[dict[str, Any]]:
        grouped: defaultdict[str, Decimal] = defaultdict(Decimal)
        for claim in claims:
            if claim["eligibilityStatus"] == "eligible":
                grouped[str(claim["sourceType"])] += Decimal(str(claim["quantityMwh"]))
        eligible = sum(grouped.values(), Decimal(0))
        items = [{"name": code, "value": float(value)} for code, value in grouped.items()]
        items.append({"name": "grid", "value": float(max(Decimal(0), total_electricity_mwh - eligible))})
        return items

    @staticmethod
    def program_payload(row: m.ClimateProgram) -> dict[str, Any]:
        return {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "framework": row.framework,
            "reportingYear": row.reporting_year,
            "standardVersion": row.standard_version,
            "status": row.status,
            "organizationBoundaryId": row.organization_boundary_id,
            "ownerName": row.owner_name,
            "configuration": row.configuration,
            "sourceName": row.source_name,
            "publishedAt": row.published_at.isoformat() if row.published_at else None,
        }

    @staticmethod
    def target_payload(row: m.ClimateTarget | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "id": row.id,
            "programId": row.program_id,
            "version": row.version,
            "targetKind": row.target_kind,
            "baselineYear": row.baseline_year,
            "baselineValue": float(row.baseline_value),
            "targetYear": row.target_year,
            "targetValue": float(row.target_value) if row.target_value is not None else None,
            "reductionPct": float(row.reduction_pct) if row.reduction_pct is not None else None,
            "scope2Method": row.scope2_method,
            "scopeCoverage": row.scope_coverage,
            "trajectoryKind": row.trajectory_kind,
            "status": row.status,
            "sourceName": row.source_name,
        }

    @staticmethod
    def claim_payload(row: m.RenewableElectricityClaim) -> dict[str, Any]:
        return {
            "id": row.id,
            "programId": row.program_id,
            "claimNo": row.claim_no,
            "sourceType": row.source_type,
            "reportingYear": row.reporting_year,
            "periodStart": row.period_start.isoformat(),
            "periodEnd": row.period_end.isoformat(),
            "quantityMwh": float(row.quantity_mwh),
            "technology": row.technology,
            "generationCountry": row.generation_country,
            "consumptionCountry": row.consumption_country,
            "registry": row.registry,
            "certificateNo": row.certificate_no,
            "vintageYear": row.vintage_year,
            "ownershipStatus": row.ownership_status,
            "eligibilityStatus": row.eligibility_status,
            "eligibilityReasons": row.eligibility_reasons,
            "evidenceReference": row.evidence_reference,
            "sourceName": row.source_name,
        }
