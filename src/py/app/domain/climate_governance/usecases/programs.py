"""Application workflows for organization climate programs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.domain.climate_governance import models as m
from app.domain.climate_governance.domain import (
    CDP_RULESET,
    RE100_RULESET,
    SBTI_RULESET,
    ClimateGovernanceError,
    evaluate_renewable_claim,
)
from app.domain.climate_governance.queries import ClimateGovernanceQueryService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.climate_governance.schemas import (
        ClimateDisclosureCycleRequest,
        ClimateProgramRequest,
        ClimateTargetRequest,
        RenewableElectricityClaimRequest,
    )


RULESETS = {"sbti": SBTI_RULESET, "cdp": CDP_RULESET, "re100": RE100_RULESET}
MAX_PERCENT = 100


class ClimateGovernanceUseCases:
    """Coordinate configuration, claim qualification, and frozen assessments."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_program(self, data: ClimateProgramRequest) -> m.ClimateProgram:
        framework = data.framework.lower()
        if framework not in RULESETS:
            message = "仅支持SBTi、CDP和RE100计划"
            raise ClimateGovernanceError(message)
        existing = await self.session.scalar(
            select(m.ClimateProgram).where(
                m.ClimateProgram.framework == framework,
                m.ClimateProgram.reporting_year == data.reporting_year,
            )
        )
        if existing:
            existing.name = data.name
            existing.owner_name = data.owner_name
            existing.organization_boundary_id = data.organization_boundary_id
            existing.configuration = data.configuration
            existing.source_name = data.source_name
            existing.standard_version = RULESETS[framework].version
            await self.session.commit()
            return existing
        program = m.ClimateProgram(
            code=data.code,
            name=data.name,
            framework=framework,
            reporting_year=data.reporting_year,
            standard_version=RULESETS[framework].version,
            status="active",
            organization_boundary_id=data.organization_boundary_id,
            owner_name=data.owner_name,
            configuration=data.configuration,
            source_name=data.source_name,
            published_at=datetime.now().astimezone(),
        )
        self.session.add(program)
        await self.session.commit()
        return program

    async def publish_target(self, program_id: int, data: ClimateTargetRequest) -> m.ClimateTarget:
        program = await self._program(program_id)
        if data.baseline_year >= data.target_year:
            message = "目标年度必须晚于基准年度"
            raise ClimateGovernanceError(message)
        if data.baseline_value < 0 or (data.reduction_pct is not None and not 0 <= data.reduction_pct <= MAX_PERCENT):
            message = "目标数值超出允许范围"
            raise ClimateGovernanceError(message)
        current = await self.session.scalar(
            select(m.ClimateTarget)
            .where(m.ClimateTarget.program_id == program_id, m.ClimateTarget.status == "published")
            .order_by(m.ClimateTarget.version.desc())
        )
        if current:
            current.status = "archived"
        version = (
            int(
                await self.session.scalar(
                    select(func.coalesce(func.max(m.ClimateTarget.version), 0)).where(
                        m.ClimateTarget.program_id == program_id
                    )
                )
                or 0
            )
            + 1
        )
        target = m.ClimateTarget(
            program_id=program.id,
            version=version,
            target_kind=data.target_kind,
            baseline_year=data.baseline_year,
            baseline_value=Decimal(str(data.baseline_value)),
            target_year=data.target_year,
            target_value=Decimal(str(data.target_value)) if data.target_value is not None else None,
            reduction_pct=Decimal(str(data.reduction_pct)) if data.reduction_pct is not None else None,
            scope2_method=data.scope2_method,
            scope_coverage=data.scope_coverage,
            trajectory_kind="internal_linear_tracking",
            status="published",
            source_name=data.source_name,
            effective_from=data.effective_from,
        )
        self.session.add(target)
        await self.session.commit()
        return target

    async def save_disclosure_cycle(
        self, program_id: int, data: ClimateDisclosureCycleRequest
    ) -> m.ClimateDisclosureCycle:
        program = await self._program(program_id, expected_framework="cdp")
        cycle = await self.session.scalar(
            select(m.ClimateDisclosureCycle).where(
                m.ClimateDisclosureCycle.program_id == program.id,
                m.ClimateDisclosureCycle.reporting_year == data.reporting_year,
            )
        )
        if cycle is None:
            cycle = m.ClimateDisclosureCycle(
                program_id=program.id, reporting_year=data.reporting_year, questionnaire_version="2026"
            )
            self.session.add(cycle)
        cycle.status = data.status
        cycle.owner_name = data.owner_name
        cycle.due_date = data.due_date
        cycle.domain_statuses = data.domain_statuses
        cycle.response_snapshot = data.response_snapshot
        cycle.evidence_snapshot = data.evidence_snapshot
        await self.session.commit()
        return cycle

    async def create_claim(
        self, program_id: int, data: RenewableElectricityClaimRequest
    ) -> m.RenewableElectricityClaim:
        program = await self._program(program_id, expected_framework="re100")
        if data.certificate_no:
            existing_certificate = await self.session.scalar(
                select(m.RenewableElectricityClaim.id).where(
                    m.RenewableElectricityClaim.reporting_year == data.reporting_year,
                    m.RenewableElectricityClaim.certificate_no == data.certificate_no,
                )
            )
            if existing_certificate is not None:
                message = "该可再生电力凭证已在本报告年度使用"
                raise ClimateGovernanceError(message)
        status, reasons = evaluate_renewable_claim(
            quantity_mwh=Decimal(str(data.quantity_mwh)),
            reporting_year=data.reporting_year,
            generation_country=data.generation_country,
            consumption_country=data.consumption_country,
            vintage_year=data.vintage_year,
            ownership_status=data.ownership_status,
            evidence_reference=data.evidence_reference,
        )
        claim = m.RenewableElectricityClaim(
            program_id=program.id,
            claim_no=data.claim_no,
            source_type=data.source_type,
            reporting_year=data.reporting_year,
            period_start=data.period_start,
            period_end=data.period_end,
            quantity_mwh=Decimal(str(data.quantity_mwh)),
            technology=data.technology,
            generation_country=data.generation_country,
            consumption_country=data.consumption_country,
            registry=data.registry,
            certificate_no=data.certificate_no,
            vintage_year=data.vintage_year,
            ownership_status=data.ownership_status,
            retired_at=data.retired_at,
            eligibility_status=status,
            eligibility_reasons=reasons,
            evidence_reference=data.evidence_reference,
            source_name=data.source_name,
            remark=data.remark,
        )
        self.session.add(claim)
        await self.session.commit()
        return claim

    async def run_assessment(self, program_id: int, idempotency_key: str | None = None) -> m.ClimateAssessmentRun:
        program = await self._program(program_id)
        overview = await ClimateGovernanceQueryService(self.session).overview(reporting_year=program.reporting_year)
        result = dict(overview[program.framework])
        input_snapshot = {
            "sourceStatus": overview["sourceStatus"],
            "program": next(item for item in overview["programs"] if item["id"] == program.id),
            "target": result.get("target"),
            "frameworkResult": result,
        }
        digest = hashlib.sha256(json.dumps(input_snapshot, sort_keys=True, default=str).encode()).hexdigest()[:24]
        key = idempotency_key or f"{program.id}:{program.reporting_year}:{digest}"
        existing = await self.session.scalar(
            select(m.ClimateAssessmentRun).where(m.ClimateAssessmentRun.idempotency_key == key)
        )
        if existing:
            return existing
        ruleset = RULESETS[program.framework]
        run = m.ClimateAssessmentRun(
            program_id=program.id,
            framework=program.framework,
            reporting_year=program.reporting_year,
            status=str(result["status"]),
            idempotency_key=key,
            input_snapshot=input_snapshot,
            rule_snapshot=ruleset.snapshot(),
            metrics_snapshot={
                key: value for key, value in result.items() if key not in {"checks", "claims", "sourceMix", "target"}
            },
            checks=list(result["checks"]),
            completed_at=datetime.now().astimezone(),
        )
        self.session.add(run)
        if program.framework == "cdp":
            cycle = await self.session.scalar(
                select(m.ClimateDisclosureCycle).where(m.ClimateDisclosureCycle.program_id == program.id)
            )
            if cycle:
                cycle.readiness_pct = Decimal(str(result["readinessPct"]))
                cycle.last_assessed_at = run.completed_at
        await self.session.commit()
        return run

    async def _program(self, program_id: int, expected_framework: str | None = None) -> m.ClimateProgram:
        program = await self.session.get(m.ClimateProgram, program_id)
        if program is None:
            message = "气候计划不存在"
            raise ClimateGovernanceError(message)
        if expected_framework and program.framework != expected_framework:
            message = "当前计划不支持此业务操作"
            raise ClimateGovernanceError(message)
        return program
