"""Organization-level SBTi, CDP, and RE100 workbench API."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
from litestar import Controller, get, post, put
from litestar.exceptions import ClientException

from app.domain.accounts.guards import requires_permission
from app.domain.climate_governance.domain import ClimateGovernanceError
from app.domain.climate_governance.queries import ClimateGovernanceQueryService
from app.domain.climate_governance.schemas import (
    ClimateAssessmentRequest,
    ClimateAssessmentRunListResponse,
    ClimateAssessmentRunResponse,
    ClimateDisclosureCycleRequest,
    ClimateOverviewResponse,
    ClimateProgramListResponse,
    ClimateProgramRequest,
    ClimateProgramResponse,
    ClimateTargetRequest,
    ClimateTargetResponse,
    RenewableElectricityClaimListResponse,
    RenewableElectricityClaimRequest,
    RenewableElectricityClaimResponse,
)
from app.domain.climate_governance.usecases import ClimateGovernanceUseCases

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ClimateGovernanceController(Controller):
    """Expose the lightweight climate-target and disclosure workflow."""

    path = "/api/carbon/climate"
    tags = ["Climate Governance"]
    guards = [requires_permission("carbon.climate.view")]

    @get("/overview", operation_id="CarbonClimateGetOverview")
    async def overview(self, db_session: AsyncSession, reporting_year: int) -> ClimateOverviewResponse:
        return msgspec.convert(
            await ClimateGovernanceQueryService(db_session).overview(reporting_year=reporting_year),
            type=ClimateOverviewResponse,
        )

    @get("/programs", operation_id="CarbonClimateListPrograms")
    async def programs(self, db_session: AsyncSession, reporting_year: int | None = None) -> ClimateProgramListResponse:
        return msgspec.convert(
            {"items": await ClimateGovernanceQueryService(db_session).programs(reporting_year)},
            type=ClimateProgramListResponse,
        )

    @post("/programs", operation_id="CarbonClimateSaveProgram", guards=[requires_permission("carbon.climate.manage")])
    async def save_program(self, db_session: AsyncSession, data: ClimateProgramRequest) -> ClimateProgramResponse:
        try:
            program = await ClimateGovernanceUseCases(db_session).create_program(data)
            row = next(
                item
                for item in await ClimateGovernanceQueryService(db_session).programs(data.reporting_year)
                if item["id"] == program.id
            )
            return msgspec.convert(row, type=ClimateProgramResponse)
        except (ClimateGovernanceError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @post(
        "/programs/{program_id:int}/targets",
        operation_id="CarbonClimatePublishTarget",
        guards=[requires_permission("carbon.climate.manage")],
    )
    async def publish_target(
        self, db_session: AsyncSession, program_id: int, data: ClimateTargetRequest
    ) -> ClimateTargetResponse:
        try:
            target = await ClimateGovernanceUseCases(db_session).publish_target(program_id, data)
            return msgspec.convert(
                ClimateGovernanceQueryService.target_payload(target),
                type=ClimateTargetResponse,
            )
        except (ClimateGovernanceError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @put(
        "/programs/{program_id:int}/disclosure-cycle",
        operation_id="CarbonClimateSaveDisclosureCycle",
        guards=[requires_permission("carbon.climate.manage")],
    )
    async def save_disclosure_cycle(
        self, db_session: AsyncSession, program_id: int, data: ClimateDisclosureCycleRequest
    ) -> ClimateOverviewResponse:
        try:
            await ClimateGovernanceUseCases(db_session).save_disclosure_cycle(program_id, data)
            return msgspec.convert(
                await ClimateGovernanceQueryService(db_session).overview(reporting_year=data.reporting_year),
                type=ClimateOverviewResponse,
            )
        except (ClimateGovernanceError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @get("/renewable-claims", operation_id="CarbonClimateListRenewableClaims")
    async def renewable_claims(
        self,
        db_session: AsyncSession,
        program_id: int | None = None,
        reporting_year: int | None = None,
    ) -> RenewableElectricityClaimListResponse:
        return msgspec.convert(
            {
                "items": await ClimateGovernanceQueryService(db_session).claims(
                    program_id=program_id, reporting_year=reporting_year
                )
            },
            type=RenewableElectricityClaimListResponse,
        )

    @post(
        "/programs/{program_id:int}/renewable-claims",
        operation_id="CarbonClimateCreateRenewableClaim",
        guards=[requires_permission("carbon.climate.manage")],
    )
    async def create_renewable_claim(
        self,
        db_session: AsyncSession,
        program_id: int,
        data: RenewableElectricityClaimRequest,
    ) -> RenewableElectricityClaimResponse:
        try:
            claim = await ClimateGovernanceUseCases(db_session).create_claim(program_id, data)
            return msgspec.convert(
                ClimateGovernanceQueryService.claim_payload(claim),
                type=RenewableElectricityClaimResponse,
            )
        except (ClimateGovernanceError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @post(
        "/programs/{program_id:int}/assessments",
        operation_id="CarbonClimateRunAssessment",
        guards=[requires_permission("carbon.climate.assess")],
    )
    async def run_assessment(
        self,
        db_session: AsyncSession,
        program_id: int,
        data: ClimateAssessmentRequest,
    ) -> ClimateAssessmentRunResponse:
        try:
            run = await ClimateGovernanceUseCases(db_session).run_assessment(program_id, data.idempotency_key)
            row = next(
                item
                for item in await ClimateGovernanceQueryService(db_session).assessment_runs(program_id=program_id)
                if item["id"] == run.id
            )
            return msgspec.convert(row, type=ClimateAssessmentRunResponse)
        except (ClimateGovernanceError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc

    @get("/programs/{program_id:int}/assessments", operation_id="CarbonClimateListAssessments")
    async def assessments(
        self, db_session: AsyncSession, program_id: int, limit: int = 20
    ) -> ClimateAssessmentRunListResponse:
        return msgspec.convert(
            {
                "items": await ClimateGovernanceQueryService(db_session).assessment_runs(
                    program_id=program_id, limit=limit
                )
            },
            type=ClimateAssessmentRunListResponse,
        )
