"""Cross-domain orchestration for reusable tenant demo packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, extract, func, select

from app.db import models as dbm
from app.demo.adapters import XiangtaiVerificationDemoAdapter
from app.demo.catalog import (
    DemoPackageManifest,
    DemoProfile,
    load_demo_manifest,
    load_demo_profile,
    load_demo_verification,
)
from app.domain.climate_governance import models as climate_m
from app.domain.climate_governance.queries import ClimateGovernanceQueryService
from app.domain.climate_governance.schemas import (
    ClimateDisclosureCycleRequest,
    ClimateProgramRequest,
    ClimateTargetRequest,
    RenewableElectricityClaimRequest,
)
from app.domain.climate_governance.usecases import ClimateGovernanceUseCases
from app.domain.decarbonization import models as reduction_m
from app.domain.ghg_inventory.models import GhgActivityRecord
from app.domain.ghg_inventory.usecases.tenant_dataset import CompleteWarehouseTenantInventory
from app.domain.microgrid.infrastructure.weather import demo_weather
from app.domain.microgrid.usecases.bindings import ApplyXiangtaiBindingTemplate
from app.domain.microgrid.usecases.operations import BootstrapXiangtaiDemo, RunForecast, RunOptimization
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


DEMO_CODE_PREFIX = "DEMO-XT-"


class DeterministicDemoWeatherAdapter:
    """Keep reusable package runs independent from network and proxy configuration."""

    async def forecast(
        self,
        *,
        latitude: float,
        longitude: float,
        start: datetime,
        periods: int = 96,
    ) -> Any:
        return demo_weather(start=start, periods=periods)


class DemoPackageError(ValueError):
    """Raised when a package cannot be safely applied to the active tenant."""


@dataclass(frozen=True, slots=True)
class DemoApplyResult:
    """Summary returned after all package adapters finish."""

    package_code: str
    profile_code: str
    team_id: UUID
    reporting_year: int
    inventory_activities: int
    inventory_runs: int
    verification_report_id: int
    verification_project_id: int
    verification_evidence_files: int
    verification_evidence_links: int
    verification_findings: int
    microgrid_site_id: int
    microgrid_meter_bindings: int
    forecast_run_id: int
    optimization_run_id: int
    reduction_target_id: int
    reduction_project_ids: tuple[int, ...]
    climate_program_ids: tuple[int, ...]
    renewable_electricity_mwh: float


class ApplyDemoPackage:
    """Apply one immutable demo manifest without replacing tenant source ledgers."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, *, package_code: str = "xiangtai", profile_code: str = "transition") -> DemoApplyResult:
        manifest = load_demo_manifest(package_code)
        profile = load_demo_profile(package_code, profile_code)
        team_id = require_session_tenant_id(self.session)
        await self._validate_tenant_and_sources(team_id=team_id, manifest=manifest)

        inventory = await CompleteWarehouseTenantInventory(self.session).execute()
        verification = await XiangtaiVerificationDemoAdapter(self.session).execute(
            manifest=manifest,
            spec=load_demo_verification(package_code),
        )
        microgrid_site = await BootstrapXiangtaiDemo(self.session).execute()
        binding_count = await self._ensure_microgrid_bindings(site_id=microgrid_site.id)
        forecast = await RunForecast(self.session, weather=DeterministicDemoWeatherAdapter()).execute(
            site_id=microgrid_site.id,
            start=self._next_quarter(),
        )
        optimization = await RunOptimization(self.session).execute(
            forecast_run_id=forecast.id,
            purpose="operational" if forecast.quality_status == "pass" else "trial",
            acknowledge_quality_warning=forecast.quality_status == "warning",
        )
        inventory_snapshot = await ClimateGovernanceQueryService(self.session).inventory_snapshot(
            reporting_year=manifest.reporting_year,
            scope2_method="location",
        )
        actual_tco2e = Decimal(str(inventory_snapshot["totalTco2e"]))
        if actual_tco2e <= 0:
            msg = "The tenant has no completed organization-inventory result for the demo reporting period."
            raise DemoPackageError(msg)

        target, project_ids = await self._upsert_reduction_portfolio(
            manifest=manifest,
            actual_tco2e=actual_tco2e,
        )
        program_ids, renewable_mwh = await self._replace_climate_profile(
            manifest=manifest,
            profile=profile,
            organization_boundary_id=target.organization_boundary_id,
            actual_tco2e=actual_tco2e,
        )
        return DemoApplyResult(
            package_code=manifest.code,
            profile_code=profile.code,
            team_id=team_id,
            reporting_year=manifest.reporting_year,
            inventory_activities=inventory.activities,
            inventory_runs=inventory.calculation_runs,
            verification_report_id=verification.report_id,
            verification_project_id=verification.project_id,
            verification_evidence_files=verification.evidence_files,
            verification_evidence_links=verification.evidence_links,
            verification_findings=verification.findings,
            microgrid_site_id=microgrid_site.id,
            microgrid_meter_bindings=binding_count,
            forecast_run_id=forecast.id,
            optimization_run_id=optimization.id,
            reduction_target_id=target.id,
            reduction_project_ids=tuple(project_ids),
            climate_program_ids=tuple(program_ids),
            renewable_electricity_mwh=float(renewable_mwh),
        )

    async def _ensure_microgrid_bindings(self, *, site_id: int) -> int:
        bindings = list(
            (
                await self.session.scalars(
                    select(dbm.MicrogridAssetMeterBinding).where(dbm.MicrogridAssetMeterBinding.site_id == site_id)
                )
            ).all()
        )
        if bindings:
            return len(bindings)
        rows = await ApplyXiangtaiBindingTemplate(self.session).execute(site_id, confirm=True)
        return len(rows)

    async def _validate_tenant_and_sources(self, *, team_id: UUID, manifest: DemoPackageManifest) -> None:
        team = await self.session.get(dbm.Team, team_id)
        if team is None or team.slug != manifest.tenant_slug:
            actual = team.slug if team else str(team_id)
            msg = f"Demo package {manifest.code!r} requires tenant {manifest.tenant_slug!r}; active tenant is {actual!r}."
            raise DemoPackageError(msg)

        root_area = await self.session.scalar(select(dbm.MonitorSector.id).where(dbm.MonitorSector.code == "ROOT"))
        activity_count = int(await self.session.scalar(select(func.count(GhgActivityRecord.id))) or 0)
        energy_count = int(
            await self.session.scalar(
                select(func.count(dbm.EnergyIntervalFact.id)).where(
                    dbm.EnergyIntervalFact.is_current.is_(True),
                    extract("year", dbm.EnergyIntervalFact.period_start) == manifest.source_data_year,
                )
            )
            or 0
        )
        if root_area is None or activity_count == 0 or energy_count == 0:
            msg = (
                "The Xiangtai base package is incomplete: ROOT area, GHG activities, and source-year energy facts "
                "must exist before applying the reusable demo package."
            )
            raise DemoPackageError(msg)

    async def _upsert_reduction_portfolio(  # noqa: PLR0915 - explicit fields keep demo ownership auditable
        self,
        *,
        manifest: DemoPackageManifest,
        actual_tco2e: Decimal,
    ) -> tuple[reduction_m.ReductionTarget, list[int]]:
        boundary = await self.session.scalar(
            select(dbm.OrganizationBoundary)
            .where(dbm.OrganizationBoundary.status == "published")
            .order_by(dbm.OrganizationBoundary.published_at.desc(), dbm.OrganizationBoundary.id.desc())
        )
        area_rows = list((await self.session.scalars(select(dbm.MonitorSector))).all())
        areas = {area.code: area for area in area_rows}
        target_spec = manifest.reduction_target
        target = await self.session.scalar(
            select(reduction_m.ReductionTarget).where(
                reduction_m.ReductionTarget.code == target_spec.code,
                reduction_m.ReductionTarget.version == 1,
            )
        )
        if target is not None and target.source_name != manifest.source_name:
            msg = f"Reduction target code {target_spec.code!r} is already owned by non-demo data."
            raise DemoPackageError(msg)
        reduction_tco2e = actual_tco2e * Decimal(str(target_spec.reduction_pct)) / Decimal(100)
        trajectory = self._linear_trajectory(
            baseline_year=target_spec.baseline_year,
            target_year=target_spec.target_year,
            baseline_tco2e=actual_tco2e,
            reduction_tco2e=reduction_tco2e,
        )
        if target is None:
            target = reduction_m.ReductionTarget(code=target_spec.code, version=1)
            self.session.add(target)
        target.name = target_spec.name
        target.target_year = target_spec.target_year
        target.baseline_year = target_spec.baseline_year
        target.target_type = "absolute"
        target.baseline_tco2e = actual_tco2e
        target.target_reduction_tco2e = reduction_tco2e
        target.target_reduction_pct = Decimal(str(target_spec.reduction_pct))
        target.organization_boundary_id = boundary.id if boundary else None
        target.area_id = areas["ROOT"].id
        target.business_unit = "仓储运营"
        target.trajectory = trajectory
        target.status = "published"
        target.source_name = manifest.source_name
        target.published_at = datetime.now(UTC)
        await self.session.flush()

        project_ids: list[int] = []
        for spec in manifest.reduction_projects:
            area = areas.get(spec.area_code)
            if area is None:
                msg = f"Demo reduction project {spec.code!r} references missing area {spec.area_code!r}."
                raise DemoPackageError(msg)
            project = await self.session.scalar(
                select(reduction_m.ReductionProject).where(reduction_m.ReductionProject.code == spec.code)
            )
            if project is not None and project.source_name != manifest.source_name:
                msg = f"Reduction project code {spec.code!r} is already owned by non-demo data."
                raise DemoPackageError(msg)
            if project is None:
                project = reduction_m.ReductionProject(code=spec.code)
                self.session.add(project)
            project.name = spec.name
            project.track = "internal_action"
            project.category = spec.category
            project.status = spec.status
            project.reduction_status = spec.reduction_status
            project.risk_level = spec.risk_level
            project.owner_name = spec.owner_name
            project.department_name = spec.department_name
            project.organization_boundary_id = boundary.id if boundary else None
            project.target_id = target.id
            project.planned_start = date.fromisoformat(spec.planned_start)
            project.planned_end = date.fromisoformat(spec.planned_end)
            project.actual_start = date.fromisoformat(spec.planned_start)
            project.progress_pct = Decimal(str(spec.progress_pct))
            project.investment_cny = Decimal(str(spec.investment_cny))
            project.expected_reduction_tco2e = Decimal(str(spec.expected_reduction_tco2e))
            project.monitored_reduction_tco2e = Decimal(str(spec.monitored_reduction_tco2e))
            project.verified_reduction_tco2e = Decimal(0)
            project.objective = spec.objective
            project.implementation_plan = spec.implementation_plan
            project.evaluation_summary = "项目效果按组织碳台账与微电网运行数据持续跟踪。"
            project.inventory_impact_kind = spec.inventory_impact_kind
            project.source_name = manifest.source_name
            await self.session.flush()
            await self.session.execute(
                delete(reduction_m.ReductionProjectResourceLink).where(
                    reduction_m.ReductionProjectResourceLink.project_id == project.id
                )
            )
            self.session.add(
                reduction_m.ReductionProjectResourceLink(
                    project_id=project.id,
                    resource_type="area",
                    resource_key=area.code,
                    area_id=area.id,
                    role="affected",
                    allocation_ratio=Decimal(1),
                    resource_snapshot={
                        "areaCode": area.code,
                        "areaName": area.name,
                        "demoPackage": manifest.code,
                    },
                )
            )
            project_ids.append(project.id)
        await self.session.commit()
        return target, project_ids

    async def _replace_climate_profile(
        self,
        *,
        manifest: DemoPackageManifest,
        profile: DemoProfile,
        organization_boundary_id: int | None,
        actual_tco2e: Decimal,
    ) -> tuple[list[int], Decimal]:
        existing = list(
            (
                await self.session.scalars(
                    select(climate_m.ClimateProgram).where(
                        climate_m.ClimateProgram.reporting_year == manifest.reporting_year
                    )
                )
            ).all()
        )
        foreign = [program for program in existing if program.source_name != manifest.source_name]
        if foreign:
            frameworks = ", ".join(sorted(program.framework for program in foreign))
            msg = f"Reporting year {manifest.reporting_year} already has non-demo climate programs: {frameworks}."
            raise DemoPackageError(msg)
        await self.session.execute(
            delete(climate_m.ClimateProgram).where(
                climate_m.ClimateProgram.reporting_year == manifest.reporting_year,
                climate_m.ClimateProgram.source_name == manifest.source_name,
            )
        )
        await self.session.commit()

        use_cases = ClimateGovernanceUseCases(self.session)
        shared_configuration: dict[str, Any] = {
            "demoPackageCode": manifest.code,
            "demoProfileCode": profile.code,
            "profileName": profile.name,
        }
        sbti = await use_cases.create_program(
            ClimateProgramRequest(
                code=f"{DEMO_CODE_PREFIX}SBTI-{manifest.reporting_year}",
                name="科学碳目标跟踪",
                framework="sbti",
                reporting_year=manifest.reporting_year,
                organization_boundary_id=organization_boundary_id,
                owner_name="可持续发展负责人",
                configuration={**shared_configuration, "scope2Method": profile.sbti.scope2_method},
                source_name=manifest.source_name,
            )
        )
        await use_cases.publish_target(
            sbti.id,
            ClimateTargetRequest(
                target_kind="absolute_reduction",
                baseline_year=profile.sbti.baseline_year,
                baseline_value=float(actual_tco2e * Decimal(str(profile.sbti.baseline_multiplier))),
                target_year=profile.sbti.target_year,
                reduction_pct=profile.sbti.reduction_pct,
                scope2_method=profile.sbti.scope2_method,
                scope_coverage={
                    "scope12Pct": profile.sbti.scope12_coverage_pct,
                    "scope3Pct": profile.sbti.scope3_coverage_pct,
                },
                source_name=manifest.source_name,
                effective_from=date(manifest.reporting_year, 1, 1),
            ),
        )

        cdp = await use_cases.create_program(
            ClimateProgramRequest(
                code=f"{DEMO_CODE_PREFIX}CDP-{manifest.reporting_year}",
                name="年度气候披露",
                framework="cdp",
                reporting_year=manifest.reporting_year,
                organization_boundary_id=organization_boundary_id,
                owner_name=profile.cdp.owner_name,
                configuration={**shared_configuration, "domainStatuses": profile.cdp.domain_statuses},
                source_name=manifest.source_name,
            )
        )
        await use_cases.save_disclosure_cycle(
            cdp.id,
            ClimateDisclosureCycleRequest(
                reporting_year=manifest.reporting_year,
                status=profile.cdp.status,
                owner_name=profile.cdp.owner_name,
                due_date=date(manifest.reporting_year, 9, 30),
                domain_statuses=profile.cdp.domain_statuses,
                response_snapshot={"profile": profile.code, "inventorySourceYear": manifest.source_data_year},
                evidence_snapshot=[],
            ),
        )

        re100 = await use_cases.create_program(
            ClimateProgramRequest(
                code=f"{DEMO_CODE_PREFIX}RE100-{manifest.reporting_year}",
                name="可再生电力目标跟踪",
                framework="re100",
                reporting_year=manifest.reporting_year,
                organization_boundary_id=organization_boundary_id,
                owner_name="能源采购负责人",
                configuration={
                    **shared_configuration,
                    "electricityDataYear": profile.re100.electricity_data_year,
                },
                source_name=manifest.source_name,
            )
        )
        await use_cases.publish_target(
            re100.id,
            ClimateTargetRequest(
                target_kind="renewable_electricity_share",
                baseline_year=profile.re100.electricity_data_year,
                baseline_value=0,
                target_year=profile.re100.target_year,
                target_value=profile.re100.target_pct,
                reduction_pct=None,
                scope2_method="market",
                scope_coverage={"electricityPct": 100.0},
                source_name=manifest.source_name,
                effective_from=date(manifest.reporting_year, 1, 1),
            ),
        )
        electricity_mwh = await self._electricity_mwh(profile.re100.electricity_data_year)
        if electricity_mwh <= 0:
            msg = f"No electricity denominator exists for {profile.re100.electricity_data_year}."
            raise DemoPackageError(msg)
        for index, claim in enumerate(profile.re100.claims, start=1):
            quantity = electricity_mwh * Decimal(str(claim.share_pct)) / Decimal(100)
            await use_cases.create_claim(
                re100.id,
                RenewableElectricityClaimRequest(
                    claim_no=f"{DEMO_CODE_PREFIX}{profile.code.upper()}-RE-{index:02d}",
                    source_type=claim.source_type,
                    reporting_year=profile.re100.electricity_data_year,
                    period_start=date(profile.re100.electricity_data_year, 1, 1),
                    period_end=date(profile.re100.electricity_data_year, 12, 31),
                    quantity_mwh=float(quantity),
                    technology=claim.technology,
                    generation_country="CN",
                    consumption_country="CN",
                    registry="企业可再生电力属性台账",
                    certificate_no=f"{DEMO_CODE_PREFIX}{profile.code.upper()}-{index:02d}",
                    vintage_year=profile.re100.electricity_data_year,
                    ownership_status=claim.ownership_status,
                    retired_at=datetime(manifest.reporting_year, 1, 15, tzinfo=UTC)
                    if claim.ownership_status in {"retired", "allocated"}
                    else None,
                    evidence_reference=claim.evidence_reference,
                    source_name=manifest.source_name,
                    remark=profile.description,
                ),
            )

        program_ids = [sbti.id, cdp.id, re100.id]
        for program_id in program_ids:
            await use_cases.run_assessment(
                program_id,
                idempotency_key=(
                    f"demo:{manifest.code}:{profile.code}:{manifest.reporting_year}:program:{program_id}"
                ),
            )
        return program_ids, electricity_mwh

    async def _electricity_mwh(self, reporting_year: int) -> Decimal:
        value = await self.session.scalar(
            select(func.coalesce(func.sum(dbm.EnergyIntervalFact.amount), 0)).where(
                dbm.EnergyIntervalFact.is_current.is_(True),
                func.lower(dbm.EnergyIntervalFact.energy_type_code).in_(
                    ("electricity", "grid_electricity", "purchased_electricity", "power")
                ),
                extract("year", dbm.EnergyIntervalFact.period_start) == reporting_year,
            )
        )
        return Decimal(value or 0) / Decimal(1000)

    @staticmethod
    def _next_quarter() -> datetime:
        now = datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(minutes=15)
        return now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)

    @staticmethod
    def _linear_trajectory(
        *,
        baseline_year: int,
        target_year: int,
        baseline_tco2e: Decimal,
        reduction_tco2e: Decimal,
    ) -> list[dict[str, Any]]:
        years = max(target_year - baseline_year, 1)
        return [
            {
                "year": year,
                "targetTco2e": float(
                    baseline_tco2e - reduction_tco2e * Decimal(year - baseline_year) / Decimal(years)
                ),
            }
            for year in range(baseline_year, target_year + 1)
        ]
