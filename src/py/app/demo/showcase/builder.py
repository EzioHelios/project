"""Build the independent industrial energy-carbon showcase tenant.

The package is deterministic and owns records with the ``DEMO-PARK`` prefix. It
does not read customer tenants; warehouse-project scale only informed the
published demo specification.
"""

from __future__ import annotations

# ruff: noqa: DTZ001, PLR0915, PLR2004, RUF001 - explicit dated scenarios and Chinese audit text are intentional.
import hashlib
from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import pi, sin
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, text

from app.db import models as m
from app.db.models import Team, TeamMember, TeamRoles, User
from app.demo.showcase.market_data import PUBLIC_MARKET_QUOTES
from app.domain.carbon.energy_analysis_importer import seed_energy_analysis_data
from app.domain.carbon_assets.domain.policies import calculate_cost_result
from app.domain.carbon_assets.usecases.reference import ensure_carbon_asset_reference_data
from app.domain.carbon_verification.usecases.projects import CarbonVerificationProjectUseCase
from app.domain.carbon_verification.usecases.templates import CarbonVerificationTemplateUseCase
from app.domain.climate_governance.schemas import (
    ClimateDisclosureCycleRequest,
    ClimateProgramRequest,
    ClimateTargetRequest,
    RenewableElectricityClaimRequest,
)
from app.domain.climate_governance.usecases import ClimateGovernanceUseCases
from app.domain.decarbonization import models as reduction_m
from app.domain.ghg_inventory.models import (
    GhgActivityAllocation,
    GhgActivityRecord,
    GhgCalculationRun,
    GhgEmissionSource,
    GhgEvidenceFile,
    GhgEvidenceLink,
    GhgInventoryReport,
    GhgParameterValue,
)
from app.domain.ghg_inventory.usecases.calculation import RunInventoryCalculation
from app.domain.ghg_inventory.usecases.reports import CreateInventoryReport, TransitionInventoryReport
from app.domain.microgrid.domain.scada import warehouse_microgrid_scada_scene
from app.domain.microgrid.infrastructure.weather import demo_weather
from app.domain.microgrid.usecases.operations import (
    CreateDispatchBatch,
    RunForecast,
    RunOptimization,
)
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


SHOWCASE_PACKAGE_CODE = "industrial-park"
SHOWCASE_TENANT_SLUG = "demo-industrial-park"
SHOWCASE_TENANT_NAME = "华东综合能源示范园区"
SOURCE_NAME = "综合能碳标准演示数据包V1"
CODE_PREFIX = "DEMO-PARK"
EVIDENCE_ROOT = Path(".storage/ghg-evidence")


@dataclass(frozen=True, slots=True)
class AreaSpec:
    code: str
    name: str
    parent_code: str | None
    area_type: str
    manager: str
    department: str


@dataclass(frozen=True, slots=True)
class EquipmentSpec:
    code: str
    name: str
    area_code: str
    energy_type: str | None
    category: int | None
    rated_power_kw: float | None
    protocol: str


@dataclass(frozen=True, slots=True)
class ActivitySeriesSpec:
    code: str
    name: str
    iso_category: str
    scope: str
    scope3_category: int | None
    mechanism: str
    unit: str
    base_amount: Decimal
    factor: Decimal
    factor_unit: str
    area_code: str
    equipment_code: str | None
    method_code: str = "F02_EF"
    parameter_code: str = "EMISSION_FACTOR"
    value_chain_position: str = "within_boundary"
    origin_kind: str = "internal"


@dataclass(frozen=True, slots=True)
class CarbonAssetLotSpec:
    instrument_code: str
    lot_no: str
    vintage_year: int
    issued_quantity: Decimal
    acquisition_unit_cost: Decimal
    project_name: str
    valid_from: date
    attributes: dict[str, Any]
    standard_code: str
    evidence_ref: str


AREAS = (
    AreaSpec("ROOT", "综合能源示范园区", None, "park", "园区总经理", "园区管理中心"),
    AreaSpec("LOGISTICS", "智慧仓储物流中心", "ROOT", "facility", "运营经理", "仓储运营部"),
    AreaSpec("ENERGY", "综合能源站", "ROOT", "facility", "能源经理", "能源动力部"),
    AreaSpec("AUTO_WH", "自动化立体仓库", "LOGISTICS", "operation", "仓储主管", "仓储运营部"),
    AreaSpec("COLD_WH", "冷链仓库", "LOGISTICS", "operation", "冷链主管", "冷链运营部"),
    AreaSpec("SORTING", "分拣包装中心", "LOGISTICS", "operation", "分拣主管", "物流运营部"),
    AreaSpec("OFFICE", "办公研发中心", "ROOT", "building", "行政经理", "行政管理部"),
    AreaSpec("UTILITY", "动力与制冷站房", "ENERGY", "utility", "设备经理", "能源动力部"),
    AreaSpec("CHARGING", "充电与停车区", "ENERGY", "operation", "车队经理", "物流运营部"),
    AreaSpec("WASTE", "环保与固废站", "ROOT", "utility", "环保经理", "安全环保部"),
)

EQUIPMENT = (
    EquipmentSpec("PCC-METER-01", "园区PCC关口电表", "ENERGY", "electricity", 0, None, "modbus"),
    EquipmentSpec("PV-INVERTER-01", "屋顶光伏逆变器一号", "ENERGY", "electricity", 1, 300, "modbus"),
    EquipmentSpec("PV-INVERTER-02", "屋顶光伏逆变器二号", "ENERGY", "electricity", 1, 300, "modbus"),
    EquipmentSpec("BESS-PCS-01", "储能变流器", "ENERGY", "electricity", None, 500, "modbus"),
    EquipmentSpec("TRANSFORMER-01", "10/0.4kV主变压器", "ENERGY", "electricity", None, 1250, "modbus"),
    EquipmentSpec("GAS-METER-01", "天然气计量表", "UTILITY", "natural_gas", None, None, "modbus"),
    EquipmentSpec("BOILER-01", "燃气热水锅炉", "UTILITY", "natural_gas", None, 420, "modbus"),
    EquipmentSpec("GENSET-01", "柴油备用发电机", "UTILITY", "diesel", None, 500, "manual"),
    EquipmentSpec("CHILLER-01", "冷链制冷机组一号", "COLD_WH", "electricity", None, 280, "modbus"),
    EquipmentSpec("CHILLER-02", "冷链制冷机组二号", "COLD_WH", "electricity", None, 280, "modbus"),
    EquipmentSpec("REFRIGERANT-01", "制冷剂维护台账设备", "COLD_WH", None, None, None, "manual"),
    EquipmentSpec("CONVEYOR-01", "自动输送分拣线", "SORTING", "electricity", None, 320, "modbus"),
    EquipmentSpec("ASRS-01", "堆垛机与立库系统", "AUTO_WH", "electricity", None, 360, "modbus"),
    EquipmentSpec("LIGHTING-01", "仓储智能照明配电柜", "AUTO_WH", "electricity", 0, 120, "modbus"),
    EquipmentSpec("HVAC-01", "办公暖通系统", "OFFICE", "electricity", None, 180, "bacnet"),
    EquipmentSpec("AIR-COMPRESSOR-01", "空气压缩机", "UTILITY", "electricity", None, 160, "modbus"),
    EquipmentSpec("EVSE-GROUP-01", "新能源车辆充电桩群", "CHARGING", "electricity", None, 360, "ocpp"),
    EquipmentSpec("FORKLIFT-FLEET-01", "叉车车队燃料台账", "CHARGING", "diesel", None, None, "manual"),
    EquipmentSpec("WASTE-SCALE-01", "固废称重终端", "WASTE", None, None, None, "http"),
)

ACTIVITY_SERIES = (
    ActivitySeriesSpec(
        "C11-GAS",
        "固定源天然气燃烧",
        "1.1",
        "scope1",
        None,
        "stationary_combustion",
        "m³",
        Decimal(15800),
        Decimal("2.162"),
        "kgCO2e/m³",
        "UTILITY",
        "BOILER-01",
    ),
    ActivitySeriesSpec(
        "C12-DIESEL",
        "移动源柴油消耗",
        "1.2",
        "scope1",
        None,
        "mobile_combustion",
        "L",
        Decimal(3900),
        Decimal("2.676"),
        "kgCO2e/L",
        "CHARGING",
        "FORKLIFT-FLEET-01",
    ),
    ActivitySeriesSpec(
        "C14-REFRIGERANT",
        "制冷剂补充与逸散",
        "1.4",
        "scope1",
        None,
        "fugitive_emission",
        "kg",
        Decimal("8.2"),
        Decimal(2088),
        "kgCO2e/kg",
        "COLD_WH",
        "REFRIGERANT-01",
    ),
    ActivitySeriesSpec(
        "C21-ELECTRICITY",
        "外购电力",
        "2.1",
        "scope2",
        None,
        "purchased_electricity",
        "kWh",
        Decimal(842000),
        Decimal("0.5827"),
        "kgCO2e/kWh",
        "ROOT",
        "PCC-METER-01",
        method_code="F08_PURCHASED_ENERGY",
        parameter_code="ENERGY_FACTOR",
    ),
    ActivitySeriesSpec(
        "C22-STEAM",
        "外购蒸汽",
        "2.2",
        "scope2",
        None,
        "purchased_steam",
        "t",
        Decimal(1160),
        Decimal(120),
        "kgCO2e/t",
        "UTILITY",
        None,
        method_code="F08_PURCHASED_ENERGY",
        parameter_code="ENERGY_FACTOR",
    ),
    ActivitySeriesSpec(
        "C31-INBOUND",
        "上游干线运输",
        "3.1",
        "scope3",
        4,
        "upstream_transport",
        "t·km",
        Decimal(920000),
        Decimal("0.082"),
        "kgCO2e/t·km",
        "LOGISTICS",
        None,
        value_chain_position="upstream",
        origin_kind="external",
    ),
    ActivitySeriesSpec(
        "C32-OUTBOUND",
        "下游配送运输",
        "3.2",
        "scope3",
        9,
        "downstream_transport",
        "t·km",
        Decimal(760000),
        Decimal("0.076"),
        "kgCO2e/t·km",
        "SORTING",
        None,
        value_chain_position="downstream",
        origin_kind="external",
    ),
    ActivitySeriesSpec(
        "C33-COMMUTE",
        "员工通勤",
        "3.3",
        "scope3",
        7,
        "employee_commuting",
        "人·km",
        Decimal(185000),
        Decimal("0.135"),
        "kgCO2e/人·km",
        "OFFICE",
        None,
        value_chain_position="upstream",
        origin_kind="external",
    ),
    ActivitySeriesSpec(
        "C41-PACKAGING",
        "采购包装材料",
        "4.1",
        "scope3",
        1,
        "purchased_goods",
        "t",
        Decimal(96),
        Decimal(820),
        "kgCO2e/t",
        "SORTING",
        None,
        value_chain_position="upstream",
        origin_kind="external",
    ),
    ActivitySeriesSpec(
        "C43-ENERGY-UPSTREAM",
        "购入能源上游排放",
        "4.3",
        "scope3",
        3,
        "fuel_energy_related",
        "kWh",
        Decimal(842000),
        Decimal("0.041"),
        "kgCO2e/kWh",
        "ENERGY",
        "PCC-METER-01",
        value_chain_position="upstream",
    ),
    ActivitySeriesSpec(
        "C44-WASTE",
        "运营废弃物处置",
        "4.4",
        "scope3",
        5,
        "waste_treatment",
        "t",
        Decimal(42),
        Decimal(510),
        "kgCO2e/t",
        "WASTE",
        "WASTE-SCALE-01",
        value_chain_position="upstream",
        origin_kind="external",
    ),
    ActivitySeriesSpec(
        "C54-LEASED",
        "下游租赁冷藏设备用电",
        "5.4",
        "scope3",
        13,
        "downstream_leased_assets",
        "kWh",
        Decimal(118000),
        Decimal("0.5827"),
        "kgCO2e/kWh",
        "COLD_WH",
        None,
        value_chain_position="downstream",
        origin_kind="external",
    ),
    ActivitySeriesSpec(
        "C61-CLOUD",
        "云服务与数据托管用电",
        "6.1",
        "scope3",
        None,
        "other_indirect",
        "kWh",
        Decimal(26000),
        Decimal("0.5827"),
        "kgCO2e/kWh",
        "OFFICE",
        None,
        value_chain_position="upstream",
        origin_kind="external",
    ),
)


@dataclass(frozen=True, slots=True)
class ShowcaseCoverage:
    passed: bool
    checks: dict[str, bool]
    counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class ShowcaseDemoResult:
    team_id: UUID
    team_slug: str
    areas: int
    equipment: int
    activities: int
    calculation_runs: int
    reports: int
    verification_projects: int
    reduction_projects: int
    climate_programs: int
    carbon_asset_instruments: int
    carbon_asset_lots: int
    carbon_asset_cost_runs: int
    microgrid_site_id: int
    microgrid_assets: int
    microgrid_meter_bindings: int
    forecast_run_id: int
    optimization_run_id: int
    dispatch_batch_id: int | None
    coverage: ShowcaseCoverage


class _ShowcaseWeatherAdapter:
    """Provide a deterministic weather horizon without a network dependency."""

    async def forecast(
        self,
        *,
        latitude: float,
        longitude: float,
        start: datetime,
        periods: int = 96,
    ) -> Any:
        del latitude, longitude
        return demo_weather(start=start, periods=periods)


async def ensure_showcase_team(session: AsyncSession) -> Team:
    """Create the dedicated tenant and grant all superusers access, idempotently."""

    await session.execute(text("SELECT set_config('app.tenant_bypass', 'true', true)"))
    await session.execute(
        text(
            """
            DO $repair_sequences$
            DECLARE
                item record;
                last_id bigint;
            BEGIN
                FOR item IN
                    SELECT
                        columns.table_schema,
                        columns.table_name,
                        columns.column_name,
                        format('%I.%I_id_seq', columns.table_schema, columns.table_name) AS sequence_name
                    FROM information_schema.columns AS columns
                    WHERE columns.table_schema = 'public'
                      AND columns.column_name = 'id'
                      AND (
                          columns.table_name LIKE 'dataapp_%'
                          OR columns.table_name LIKE 'carbon_%'
                          OR columns.table_name LIKE 'ghg_%'
                          OR columns.table_name LIKE 'decarbonization_%'
                          OR columns.table_name LIKE 'climate_governance_%'
                          OR columns.table_name LIKE 'microgrid_%'
                      )
                LOOP
                    IF to_regclass(item.sequence_name) IS NOT NULL THEN
                        EXECUTE format(
                            'SELECT max(%I) FROM %I.%I',
                            item.column_name,
                            item.table_schema,
                            item.table_name
                        ) INTO last_id;
                        PERFORM setval(item.sequence_name::regclass, COALESCE(last_id, 0) + 1000, true);
                    END IF;
                END LOOP;
            END
            $repair_sequences$;
            """
        )
    )
    team = await session.scalar(select(Team).where(Team.slug == SHOWCASE_TENANT_SLUG))
    if team is None:
        team = Team(
            slug=SHOWCASE_TENANT_SLUG,
            name=SHOWCASE_TENANT_NAME,
            description=f"{SOURCE_NAME}；可重复安装，数据覆盖2024年至2026年8月。",
            is_active=True,
        )
        session.add(team)
        await session.flush()
    superusers = list((await session.scalars(select(User).where(User.is_superuser.is_(True)))).all())
    for user in superusers:
        membership = await session.scalar(
            select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == user.id)
        )
        if membership is None:
            session.add(TeamMember(team_id=team.id, user_id=user.id, role=TeamRoles.ADMIN, is_owner=True))
    await session.commit()
    return team


class ShowcaseDemoBuilder:
    """Populate all organization-carbon demonstration surfaces for one dedicated tenant."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, *, climate_profile: str = "transition") -> ShowcaseDemoResult:
        require_session_tenant_id(self.session)
        enterprise, areas, equipment = await self._master_data()
        _organization, periods, boundaries = await self._inventory_context(enterprise=enterprise, areas=areas)
        activities = await self._activities(periods=periods, boundaries=boundaries, areas=areas, equipment=equipment)
        await self._energy_facts(activities=activities, areas=areas, equipment=equipment)
        microgrid = await self._microgrid(areas=areas, equipment=equipment)
        runs = await self._calculation_runs(periods=periods, boundaries=boundaries)
        await self._evidence(activities)
        reports = await self._reports(runs)
        verification_projects = await self._verification(reports=reports, runs=runs, activities=activities)
        reduction_projects = await self._reduction(
            boundary=boundaries[2025], areas=areas, equipment=equipment, runs=runs
        )
        climate_programs = await self._climate(
            boundary=boundaries[2026], runs=runs, profile=climate_profile, activities=activities
        )
        carbon_assets = await self._carbon_assets(boundary=boundaries[2026])
        await self._budgets(runs)
        coverage = await self.verify()
        return ShowcaseDemoResult(
            team_id=require_session_tenant_id(self.session),
            team_slug=SHOWCASE_TENANT_SLUG,
            areas=len(areas),
            equipment=len(equipment),
            activities=len(activities),
            calculation_runs=len(runs),
            reports=len(reports),
            verification_projects=verification_projects,
            reduction_projects=reduction_projects,
            climate_programs=climate_programs,
            carbon_asset_instruments=carbon_assets[0],
            carbon_asset_lots=carbon_assets[1],
            carbon_asset_cost_runs=carbon_assets[2],
            microgrid_site_id=microgrid[0],
            microgrid_assets=microgrid[1],
            microgrid_meter_bindings=microgrid[2],
            forecast_run_id=microgrid[3],
            optimization_run_id=microgrid[4],
            dispatch_batch_id=microgrid[5],
            coverage=coverage,
        )

    async def _master_data(self) -> tuple[m.EnterpriseInfo, dict[str, m.MonitorSector], dict[str, m.MonitorEquipment]]:
        enterprise = await self.session.scalar(
            select(m.EnterpriseInfo).where(m.EnterpriseInfo.unify_code == "DEMO91320000PARK2026X")
        )
        if enterprise is None:
            enterprise = m.EnterpriseInfo(
                name="华东综合能源示范园区有限公司",
                belong_unit="示范园区运营集团",
                people_count=860,
                park_area=168000,
                store_area=124000,
                green_area=21000,
                unify_code="DEMO91320000PARK2026X",
                industry="综合仓储物流",
                location="华东地区",
                other_info={
                    "demoPackage": SHOWCASE_PACKAGE_CODE,
                    "baselineYears": [2024, 2025],
                    "currentThrough": "2026-08-31",
                },
            )
            self.session.add(enterprise)
            await self.session.flush()
        areas: dict[str, m.MonitorSector] = {}
        for index, spec in enumerate(AREAS):
            area = await self.session.scalar(select(m.MonitorSector).where(m.MonitorSector.code == spec.code))
            parent = areas.get(spec.parent_code or "")
            if area is None:
                area = m.MonitorSector(code=spec.code)
                self.session.add(area)
            area.name = spec.name
            area.parent_id = parent.id if parent else None
            area.area_type = spec.area_type
            area.level = 0 if parent is None else int(parent.level or 0) + 1
            area.path = f"{parent.path}/{spec.code}" if parent and parent.path else f"/{spec.code}"
            area.sort_index = index
            area.manager_name = spec.manager
            area.owner_department = spec.department
            area.location_desc = "华东综合能源示范园区"
            area.description = "区域级能耗、排放、设备和项目归集单元"
            area.remark = SOURCE_NAME
            area.is_enable = True
            await self.session.flush()
            areas[spec.code] = area
        equipment: dict[str, m.MonitorEquipment] = {}
        for index, spec in enumerate(EQUIPMENT):
            item = await self.session.scalar(select(m.MonitorEquipment).where(m.MonitorEquipment.code == spec.code))
            if item is None:
                item = m.MonitorEquipment(code=spec.code)
                self.session.add(item)
            item.name = spec.name
            item.sector_id = areas[spec.area_code].id
            item.category = spec.category
            item.asset_code = spec.code
            item.energy_type = spec.energy_type
            item.rated_power_kw = spec.rated_power_kw
            item.owner_unit = enterprise.name
            item.warehouse_name = areas[spec.area_code].name
            item.warehouse_code = spec.area_code
            item.data_acquisition_method = "自动采集" if spec.protocol != "manual" else "台账填报"
            item.running_status = "online"
            item.commissioning_status = "active"
            item.status = 0
            item.location = areas[spec.area_code].name
            item.protocol = spec.protocol
            item.sort_index = index
            item.remark = SOURCE_NAME
            item.is_enable = True
            await self.session.flush()
            equipment[spec.code] = item
        await self.session.commit()
        return enterprise, areas, equipment

    async def _inventory_context(
        self, *, enterprise: m.EnterpriseInfo, areas: dict[str, m.MonitorSector]
    ) -> tuple[m.ReportingOrganization, dict[int, m.ReportingPeriod], dict[int, m.OrganizationBoundary]]:
        organization = await self.session.scalar(
            select(m.ReportingOrganization).where(m.ReportingOrganization.code == "DEMO-PARK-ORG")
        )
        if organization is None:
            organization = m.ReportingOrganization(
                code="DEMO-PARK-ORG",
                name="华东综合能源示范园区运营主体",
                enterprise_id=enterprise.id,
                organization_type="enterprise",
                legal_entity_code="DEMO91320000PARK2026X",
                control_method="operational_control",
                status="active",
                source_name=SOURCE_NAME,
                standard_code="ISO 14064-1:2018; GHG Protocol Corporate Standard",
                remark="采用运营控制法建立组织边界",
            )
            self.session.add(organization)
            await self.session.flush()
        periods: dict[int, m.ReportingPeriod] = {}
        boundaries: dict[int, m.OrganizationBoundary] = {}
        for year, end, status in (
            (2024, date(2024, 12, 31), "locked"),
            (2025, date(2025, 12, 31), "locked"),
            (2026, date(2026, 8, 31), "open"),
        ):
            period = await self.session.scalar(
                select(m.ReportingPeriod).where(m.ReportingPeriod.code == f"DEMO-PARK-RP-{year}")
            )
            if period is None:
                period = m.ReportingPeriod(
                    reporting_org_id=organization.id,
                    code=f"DEMO-PARK-RP-{year}",
                    name=f"{year}年度组织温室气体盘查" if year < 2026 else "2026年1—8月组织温室气体盘查",
                    period_type="annual" if year < 2026 else "ytd",
                    period_start=date(year, 1, 1),
                    period_end=end,
                    base_year=2024,
                    status=status,
                    locked_at=datetime(year + 1, 3, 15) if year < 2026 else None,
                    source_name=SOURCE_NAME,
                    standard_code="ISO 14064-1:2018",
                    remark="完整年度" if year < 2026 else "截至2026年8月31日的年内累计期间",
                )
                self.session.add(period)
                await self.session.flush()
            periods[year] = period
            boundary = await self.session.scalar(
                select(m.OrganizationBoundary).where(m.OrganizationBoundary.boundary_no == f"DEMO-PARK-BND-{year}-V1")
            )
            if boundary is None:
                boundary = m.OrganizationBoundary(
                    reporting_org_id=organization.id,
                    period_id=period.id,
                    boundary_no=f"DEMO-PARK-BND-{year}-V1",
                    boundary_name=f"{year}年度园区组织与运营边界",
                    boundary_type="organization",
                    boundary_method="operational_control",
                    operational_boundary={
                        "schemaVersion": "organization-boundary-v1",
                        "scopes": ["scope1", "scope2", "scope3"],
                        "scope2Methods": ["location", "market"],
                        "isoCategories": ["1", "2", "3", "4", "5", "6"],
                        "resourceBinding": "area_equipment_allocation",
                    },
                    version=1,
                    status="published",
                    published_at=datetime(year, 1, 15),
                    source_name=SOURCE_NAME,
                    standard_code="ISO 14064-1:2018; GHG Protocol Corporate Standard",
                    confidence_level="high",
                    remark="覆盖园区运营控制下的全部业务区域；外部承运商作为价值链活动纳入。",
                )
                self.session.add(boundary)
                await self.session.flush()
                for area in areas.values():
                    self.session.add(
                        m.BoundaryFacility(
                            boundary_id=boundary.id,
                            facility_type="area",
                            area_id=area.id,
                            facility_code=area.code,
                            facility_name=area.name,
                            facility_role="reporting_site_root" if area.code == "ROOT" else "operated_area",
                            included=True,
                            valid_from=period.period_start,
                            valid_to=period.period_end,
                            source_name=SOURCE_NAME,
                        )
                    )
                self.session.add(
                    m.BoundaryFacility(
                        boundary_id=boundary.id,
                        facility_type="external_facility",
                        facility_code="LEASED-OFFSITE-01",
                        facility_name="外部承租中转仓",
                        facility_role="excluded_leased_site",
                        included=False,
                        exclusion_reason="园区不具有运营控制权，相关能源活动按价值链分类评估。",
                        valid_from=period.period_start,
                        valid_to=period.period_end,
                        source_name=SOURCE_NAME,
                    )
                )
            boundaries[year] = boundary
        await self.session.commit()
        return organization, periods, boundaries

    async def _activities(
        self,
        *,
        periods: dict[int, m.ReportingPeriod],
        boundaries: dict[int, m.OrganizationBoundary],
        areas: dict[str, m.MonitorSector],
        equipment: dict[str, m.MonitorEquipment],
    ) -> list[GhgActivityRecord]:
        activities: list[GhgActivityRecord] = []
        for year, months in ((2024, 12), (2025, 12), (2026, 8)):
            inventory_code = f"DEMO-PARK-INV-{year}"
            for spec in ACTIVITY_SERIES:
                source = await self.session.scalar(
                    select(GhgEmissionSource).where(
                        GhgEmissionSource.inventory_code == inventory_code,
                        GhgEmissionSource.source_code == spec.code,
                    )
                )
                if source is None:
                    source = GhgEmissionSource(
                        inventory_code=inventory_code,
                        organization_boundary_id=boundaries[year].id,
                        reporting_period_id=periods[year].id,
                        organization_code="DEMO-PARK-ORG",
                        facility_code=spec.area_code,
                        source_code=spec.code,
                        source_name=spec.name,
                        iso_category_code=spec.iso_category,
                        source_mechanism=spec.mechanism,
                        origin_kind=spec.origin_kind,
                        default_area_id=areas[spec.area_code].id,
                        default_equipment_id=equipment[spec.equipment_code].id if spec.equipment_code else None,
                        default_allocation_role="physical_origin"
                        if spec.origin_kind == "internal"
                        else "responsibility",
                        external_facility_code=f"EXT-{spec.code}" if spec.origin_kind == "external" else None,
                        external_facility_name="价值链合作方" if spec.origin_kind == "external" else None,
                        valid_from=date(year, 1, 1),
                        valid_to=periods[year].period_end,
                        source_system="demo_generator",
                        source_payload={"demoPackage": SHOWCASE_PACKAGE_CODE, "sourceName": SOURCE_NAME},
                        status="active",
                    )
                    self.session.add(source)
                    await self.session.flush()
                for month in range(1, months + 1):
                    record_code = f"DEMO-PARK-{year}{month:02d}-{spec.code}"
                    activity = await self.session.scalar(
                        select(GhgActivityRecord).where(
                            GhgActivityRecord.inventory_code == inventory_code,
                            GhgActivityRecord.record_code == record_code,
                        )
                    )
                    amount = self._monthly_amount(spec, year=year, month=month)
                    if activity is None:
                        activity = GhgActivityRecord(
                            record_code=record_code,
                            inventory_code=inventory_code,
                            reporting_period_id=periods[year].id,
                            organization_boundary_id=boundaries[year].id,
                            emission_source_id=source.id,
                            organization_code="DEMO-PARK-ORG",
                            facility_code=spec.area_code,
                            source_code=spec.code,
                            activity_code=spec.code,
                            activity_name=spec.name,
                            period_start=date(year, month, 1),
                            period_end=date(year, month, monthrange(year, month)[1]),
                            iso_category_code=spec.iso_category,
                            ghg_scope=spec.scope,
                            scope3_category=spec.scope3_category,
                            source_mechanism=spec.mechanism,
                            value_chain_position=spec.value_chain_position,
                            boundary_status="included",
                            national_source_category=self._national_category(spec),
                            activity_amount=amount,
                            activity_unit=spec.unit,
                            data_source_type="metered" if spec.origin_kind == "internal" else "supplier_ledger",
                            measurement_method="计量系统月结" if spec.origin_kind == "internal" else "经复核的业务台账",
                            quality_status="warning"
                            if year == 2026 and month == 8 and spec.code in {"C33-COMMUTE", "C61-CLOUD"}
                            else "pass",
                            parameter_set_code=f"{record_code}-PS1",
                            source_payload={
                                "method_code": spec.method_code,
                                "gas_code": "CO2e",
                                "scope2_method": "location" if spec.scope == "scope2" else "not_applicable",
                                "demoPackage": SHOWCASE_PACKAGE_CODE,
                                "isYtd": year == 2026,
                            },
                            remarks="2026年8月数据处于月结复核期" if year == 2026 and month == 8 else None,
                            status="approved",
                            source_system="demo_generator",
                        )
                        self.session.add(activity)
                        await self.session.flush()
                    await self._parameter(activity=activity, spec=spec, year=year)
                    await self._allocation(activity=activity, spec=spec, areas=areas, equipment=equipment)
                    activities.append(activity)
        await self.session.commit()
        return activities

    async def _parameter(self, *, activity: GhgActivityRecord, spec: ActivitySeriesSpec, year: int) -> None:
        value_code = f"{activity.inventory_code}:{activity.parameter_set_code}:{spec.parameter_code}"
        value = await self.session.scalar(
            select(GhgParameterValue).where(GhgParameterValue.value_code == value_code, GhgParameterValue.version == 1)
        )
        if value is None:
            value = GhgParameterValue(value_code=value_code, version=1)
            self.session.add(value)
        value.parameter_code = spec.parameter_code
        value.parameter_name = "购入能源排放因子" if spec.parameter_code == "ENERGY_FACTOR" else "活动排放因子"
        value.parameter_role = "emission_factor"
        value.value = spec.factor
        value.unit = spec.factor_unit
        value.source_mode = (
            "authority_published"
            if spec.code in {"C11-GAS", "C12-DIESEL", "C14-REFRIGERANT", "C21-ELECTRICITY"}
            else "custom_approved"
        )
        value.source_name = self._factor_source(spec)
        value.source_version = str(year)
        value.standard_code = self._factor_standard(spec)
        value.reference_year = min(year, 2025)
        value.geography = "中国华东"
        value.fuel_or_material = spec.code
        value.uncertainty = Decimal("0.03") if value.source_mode == "authority_published" else Decimal("0.08")
        value.quality_grade = "A" if value.source_mode == "authority_published" else "B"
        value.approval_status = "approved"
        value.status = "active"

    async def _allocation(
        self,
        *,
        activity: GhgActivityRecord,
        spec: ActivitySeriesSpec,
        areas: dict[str, m.MonitorSector],
        equipment: dict[str, m.MonitorEquipment],
    ) -> None:
        existing = list(
            (
                await self.session.scalars(
                    select(GhgActivityAllocation).where(GhgActivityAllocation.activity_id == activity.id)
                )
            ).all()
        )
        if existing:
            return
        if spec.code == "C21-ELECTRICITY":
            splits = (
                ("AUTO_WH", "ASRS-01", Decimal("0.24")),
                ("COLD_WH", "CHILLER-01", Decimal("0.27")),
                ("SORTING", "CONVEYOR-01", Decimal("0.17")),
                ("OFFICE", "HVAC-01", Decimal("0.10")),
                ("UTILITY", "AIR-COMPRESSOR-01", Decimal("0.12")),
                ("CHARGING", "EVSE-GROUP-01", Decimal("0.10")),
            )
        else:
            splits = ((spec.area_code, spec.equipment_code, Decimal(1)),)
        for index, (area_code, equipment_code, ratio) in enumerate(splits, start=1):
            area = areas[area_code]
            item = equipment.get(equipment_code or "")
            self.session.add(
                GhgActivityAllocation(
                    activity_id=activity.id,
                    emission_source_id=activity.emission_source_id,
                    allocation_code=f"{activity.record_code}-A{index:02d}",
                    area_id=area.id,
                    equipment_id=item.id if item else None,
                    allocation_role="energy_consumption"
                    if spec.scope == "scope2"
                    else ("physical_origin" if spec.origin_kind == "internal" else "responsibility"),
                    allocation_ratio=ratio,
                    external_facility_code=f"EXT-{spec.code}" if spec.origin_kind == "external" else None,
                    external_facility_name="价值链合作方" if spec.origin_kind == "external" else None,
                    area_code_snapshot=area.code,
                    area_name_snapshot=area.name or area.code,
                    area_path_snapshot=area.path,
                    equipment_code_snapshot=item.code if item else None,
                    equipment_name_snapshot=item.name if item else None,
                    source_kind="demo_generator",
                    valid_from=activity.period_start,
                    valid_to=activity.period_end,
                    status="active",
                )
            )

    async def _energy_facts(
        self,
        *,
        activities: list[GhgActivityRecord],
        areas: dict[str, m.MonitorSector],
        equipment: dict[str, m.MonitorEquipment],
    ) -> None:
        electricity = [item for item in activities if item.activity_code == "C21-ELECTRICITY"]
        splits = (
            ("AUTO_WH", "ASRS-01", Decimal("0.24")),
            ("COLD_WH", "CHILLER-01", Decimal("0.27")),
            ("SORTING", "CONVEYOR-01", Decimal("0.17")),
            ("OFFICE", "HVAC-01", Decimal("0.10")),
            ("UTILITY", "AIR-COMPRESSOR-01", Decimal("0.12")),
            ("CHARGING", "EVSE-GROUP-01", Decimal("0.10")),
        )
        for activity in electricity:
            for area_code, equipment_code, ratio in splits:
                source_record_id = f"{activity.record_code}:{equipment_code}"
                fact = await self.session.scalar(
                    select(m.EnergyIntervalFact).where(
                        m.EnergyIntervalFact.source_system == "demo_showcase",
                        m.EnergyIntervalFact.source_record_id == source_record_id,
                        m.EnergyIntervalFact.revision_no == 1,
                    )
                )
                if fact is None:
                    area = areas[area_code]
                    item = equipment[equipment_code]
                    amount = (activity.activity_amount * ratio).quantize(Decimal("0.001"))
                    fact = m.EnergyIntervalFact(
                        source_system="demo_showcase",
                        source_record_id=source_record_id,
                        energy_type_code="electricity",
                        equipment_id=item.id,
                        equipment_code=item.code,
                        equipment_name=item.name,
                        area_id=area.code,
                        area_name=area.name,
                        use_system_code="warehouse_operations",
                        use_system_name="仓储物流用能系统",
                        granularity="month",
                        period_start=datetime.combine(activity.period_start, datetime.min.time()),
                        period_end=datetime.combine(activity.period_end, datetime.max.time()).replace(microsecond=0),
                        amount=amount,
                        unit="kWh",
                        cost_cny=(amount * Decimal("0.79")).quantize(Decimal("0.01")),
                        reading_count=monthrange(activity.period_start.year, activity.period_start.month)[1] * 96,
                        data_quality="measured" if activity.period_start < date(2026, 8, 1) else "provisional",
                        revision_no=1,
                        is_current=True,
                        source_snapshot={"activityRecord": activity.record_code, "sourceName": SOURCE_NAME},
                        remark=SOURCE_NAME,
                    )
                    self.session.add(fact)
        await self.session.commit()

    async def _create_microgrid_site(
        self,
        *,
        area: m.MonitorSector,
        tariff: m.EnergyTariffPlan | None,
        factor: m.EmissionFactor,
        observed_at: datetime,
    ) -> m.MicrogridSite:
        """Create the standalone site without reading or copying a customer tenant."""

        site = m.MicrogridSite(
            code=SHOWCASE_TENANT_SLUG,
            name="综合能源示范园区微电网",
            timezone="Asia/Shanghai",
            latitude=Decimal("31.9800000"),
            longitude=Decimal("120.8900000"),
            pcc_capacity_kw=Decimal(1250),
            monitor_sector_id=area.id,
            topology_version=3,
            topology=warehouse_microgrid_scada_scene(),
            status="shadow",
            source_name=SOURCE_NAME,
        )
        self.session.add(site)
        await self.session.flush()
        asset_specs = (
            ("PCC", "园区公共连接点", "grid", 1250, None, False, {"voltage_kv": 10}),
            (
                "PV-01",
                "屋顶分布式光伏",
                "pv",
                500,
                None,
                False,
                {"dc_capacity_kw": 600, "tilt_deg": 18, "azimuth_deg": 180},
            ),
            (
                "BESS-01",
                "磷酸铁锂储能系统",
                "storage",
                500,
                1000,
                True,
                {"minimum_soc_pct": 15, "maximum_soc_pct": 90},
            ),
            ("EVSE-GROUP", "新能源车辆充电桩群", "charger", 240, None, True, {"charger_count": 8}),
            (
                "LIGHTING",
                "仓储智能照明",
                "lighting",
                80,
                None,
                True,
                {"critical_minimum_ratio": 0.55},
            ),
            (
                "WAREHOUSE",
                "仓储与制冷作业负荷",
                "load",
                900,
                None,
                False,
                {"load_class": "warehouse_operations"},
            ),
        )
        assets: dict[str, m.MicrogridAsset] = {}
        for code, name, asset_type, power, energy, controllable, parameters in asset_specs:
            asset = m.MicrogridAsset(
                site_id=site.id,
                code=code,
                name=name,
                asset_type=asset_type,
                rated_power_kw=Decimal(power),
                rated_energy_kwh=Decimal(energy) if energy is not None else None,
                controllable=controllable,
                parameters=parameters,
                source_kind="demo_package",
                source_name=SOURCE_NAME,
                confidence_level=Decimal("0.90"),
            )
            self.session.add(asset)
            assets[code] = asset
        await self.session.flush()
        parameters: dict[str, Any] = {
            "interval_minutes": 15,
            "reserve_margin_pct": 8,
            "objective_weights": {"energy": 1, "peak": 1.5, "carbon": 1.5},
            "grid": {"pcc_capacity_kw": 1250, "export_capacity_kw": 300},
            "pv": {"dc_capacity_kw": 600, "ac_capacity_kw": 500, "tilt_deg": 18, "azimuth_deg": 180},
            "storage": {
                "capacity_kwh": 1000,
                "power_kw": 500,
                "initial_soc_pct": 52,
                "terminal_soc_pct": 52,
                "minimum_soc_pct": 15,
                "maximum_soc_pct": 90,
                "charging_efficiency": 0.95,
                "discharging_efficiency": 0.95,
            },
            "charger": {
                "minimum_power_kw": 0,
                "maximum_power_kw": 240,
                "target_energy_kwh": 720,
                "start_interval": 28,
                "end_interval": 88,
            },
            "lighting": {"baseline_power_kw": 80, "minimum_power_kw": 44},
            "generator": {
                "minimum_power_kw": 0,
                "maximum_power_kw": 0,
                "ramp_kw_per_interval": 0,
                "fuel_cny_per_kwh": 1.8,
                "start_cost_cny": 0,
            },
            "tariff": {"valley": 0.42, "flat": 0.76, "peak": 1.26, "export": 0.25},
            "economics": {
                "battery_degradation_cny_per_kwh": 0.08,
                "export_cny_per_kwh": 0.25,
                "demand_cny_per_kw_day": 0.35,
                "grid_carbon_kg_per_kwh": 0.5827,
                "carbon_cny_per_kg": 0.08,
                "curtailment_cny_per_kwh": 0.02,
            },
        }
        scenario = m.MicrogridScenario(
            site_id=site.id,
            code="demo-park-operational",
            name="园区源网荷储协同策略V1",
            version=1,
            status="published",
            parameters=parameters,
            asset_snapshot=[
                {"code": asset.code, "type": asset.asset_type, "ratedPowerKw": float(asset.rated_power_kw or 0)}
                for asset in assets.values()
            ],
            source_kind="demo_package",
            source_name=SOURCE_NAME,
            confidence_level=Decimal("0.90"),
            published_at=datetime(2026, 8, 20, tzinfo=UTC),
            tariff_plan_id=tariff.id if tariff is not None else None,
            grid_emission_factor_id=factor.id,
            change_summary="基于园区设备台账、分时电价和柔性负荷契约建立演示运行策略。",
        )
        self.session.add(scenario)
        await self.session.flush()
        self.session.add_all(
            [
                m.FlexibilityContract(
                    scenario_id=scenario.id,
                    asset_id=assets["EVSE-GROUP"].id,
                    contract_type="energy_deadline",
                    start_minute=7 * 60,
                    end_minute=22 * 60,
                    minimum_power_kw=Decimal(0),
                    maximum_power_kw=Decimal(240),
                    target_energy_kwh=Decimal(720),
                    priority=80,
                    penalty_cny_per_kwh=Decimal(8),
                    recovery_constraints={"hard_constraint": True},
                ),
                m.FlexibilityContract(
                    scenario_id=scenario.id,
                    asset_id=assets["LIGHTING"].id,
                    contract_type="minimum_service",
                    start_minute=0,
                    end_minute=1440,
                    minimum_power_kw=Decimal(44),
                    maximum_power_kw=Decimal(80),
                    priority=95,
                    penalty_cny_per_kwh=Decimal(12),
                ),
            ]
        )
        state_values = {
            "PCC": (438, None),
            "PV-01": (286, None),
            "BESS-01": (-72, 52),
            "EVSE-GROUP": (96, None),
            "LIGHTING": (64, None),
            "WAREHOUSE": (536, None),
        }
        self.session.add_all(
            [
                m.MicrogridAssetState(
                    asset_id=assets[code].id,
                    observed_at=observed_at,
                    online=True,
                    operating_mode="shadow",
                    active_power_kw=Decimal(power),
                    soc_pct=Decimal(soc) if soc is not None else None,
                    temperature_c=Decimal("31.4") if code == "BESS-01" else None,
                    alarm_level="normal",
                    source_kind="demo_package",
                )
                for code, (power, soc) in state_values.items()
            ]
        )
        telemetry: list[m.MicrogridTelemetryFact] = []
        for index in range(96):
            point_at = observed_at - timedelta(minutes=15 * (95 - index))
            local = point_at.astimezone(ZoneInfo("Asia/Shanghai"))
            hour = local.hour + local.minute / 60
            daylight = max(0.0, sin(pi * (hour - 6) / 12)) if 6 <= hour <= 18 else 0.0
            warehouse = 430 + (95 if 7 <= hour < 21 else 18) + 24 * sin(2 * pi * (hour - 7) / 24)
            pv = min(500.0, 470 * daylight**1.35)
            charger = max(18.0, 92 + 34 * sin(2 * pi * (hour - 8) / 12)) if 7 <= hour < 22 else 18.0
            lighting = 64.0 if 6 <= hour < 22 else 44.0
            storage = -72.0 if 10 <= hour < 16 else (110.0 if 18 <= hour < 21 else 0.0)
            values = {
                "PV-01": pv,
                "BESS-01": storage,
                "EVSE-GROUP": charger,
                "LIGHTING": lighting,
                "WAREHOUSE": warehouse,
                "PCC": warehouse + charger + lighting - pv - storage,
            }
            for code, value in values.items():
                telemetry.append(
                    m.MicrogridTelemetryFact(
                        site_id=site.id,
                        asset_id=assets[code].id,
                        metric_code="active_power_kw",
                        value=Decimal(str(round(value, 3))),
                        unit="kW",
                        observed_at=point_at,
                        source_kind="simulated",
                        source_ref="demo-industrial-park/scada-telemetry",
                        quality="D",
                    )
                )
        self.session.add_all(telemetry)
        await self.session.commit()
        return site

    async def _microgrid(
        self,
        *,
        areas: dict[str, m.MonitorSector],
        equipment: dict[str, m.MonitorEquipment],
    ) -> tuple[int, int, int, int, int, int | None]:
        """Build a generic microgrid workbench over the showcase equipment ledger."""

        local_now = datetime.now(ZoneInfo("Asia/Shanghai"))
        forecast_start = local_now.replace(minute=(local_now.minute // 15) * 15, second=0, microsecond=0)
        await seed_energy_analysis_data(self.session)
        factor = await self.session.scalar(
            select(m.EmissionFactor).where(
                m.EmissionFactor.sub_category == "grid_electricity_jiangsu",
                m.EmissionFactor.year == 2023,
                m.EmissionFactor.is_active.is_(True),
            )
        )
        if factor is None:
            factor = m.EmissionFactor(
                scope="scope2",
                category="purchased_energy",
                sub_category="grid_electricity_jiangsu",
                unit="kWh",
                factor_value=Decimal("0.5827"),
                factor_unit="kgCO2e/kWh",
                year=2023,
                source="生态环境部2023年全国电力平均二氧化碳排放因子",
                is_active=True,
                note="综合能碳标准演示数据包冻结值",
                source_system="showcase_demo",
                source_snapshot_id="DEMO-PARK-GRID-EF-2023",
                projection_status="projected",
                review_status="approved",
            )
            self.session.add(factor)
            await self.session.commit()

        tariff = await self.session.scalar(
            select(m.EnergyTariffPlan).where(
                m.EnergyTariffPlan.code == "default_electricity_tou",
                m.EnergyTariffPlan.is_enabled.is_(True),
            )
        )
        site = await self.session.scalar(select(m.MicrogridSite).where(m.MicrogridSite.code == SHOWCASE_TENANT_SLUG))
        if site is None:
            site = await self._create_microgrid_site(
                area=areas["ENERGY"],
                tariff=tariff,
                factor=factor,
                observed_at=forecast_start.astimezone(UTC),
            )

        site.name = "综合能源示范园区微电网"
        site.monitor_sector_id = areas["ENERGY"].id
        site.latitude = Decimal("31.9800000")
        site.longitude = Decimal("120.8900000")
        site.pcc_capacity_kw = Decimal(1250)
        site.source_name = SOURCE_NAME

        assets = {
            row.code: row
            for row in (
                await self.session.scalars(select(m.MicrogridAsset).where(m.MicrogridAsset.site_id == site.id))
            ).all()
        }
        equipment_by_asset = {
            "PCC": "PCC-METER-01",
            "PV-01": "PV-INVERTER-01",
            "BESS-01": "BESS-PCS-01",
            "EVSE-GROUP": "EVSE-GROUP-01",
            "LIGHTING": "LIGHTING-01",
            "WAREHOUSE": "ASRS-01",
        }
        asset_names = {
            "PCC": "园区公共连接点",
            "PV-01": "屋顶分布式光伏",
            "BESS-01": "磷酸铁锂储能系统",
            "EVSE-GROUP": "新能源车辆充电桩群",
            "LIGHTING": "仓储智能照明",
            "WAREHOUSE": "仓储与制冷作业负荷",
        }
        for code, asset in assets.items():
            asset.name = asset_names.get(code, asset.name)
            asset.equipment_id = equipment[equipment_by_asset[code]].id
            asset.source_name = SOURCE_NAME
            asset.confidence_level = Decimal("0.90")
        states = list(
            (
                await self.session.scalars(
                    select(m.MicrogridAssetState).where(
                        m.MicrogridAssetState.asset_id.in_([asset.id for asset in assets.values()])
                    )
                )
            ).all()
        )
        for state in states:
            state.observed_at = forecast_start.astimezone(UTC)

        scenario = await self.session.scalar(
            select(m.MicrogridScenario)
            .where(m.MicrogridScenario.site_id == site.id, m.MicrogridScenario.status == "published")
            .order_by(m.MicrogridScenario.version.desc())
        )
        if scenario is None:
            msg = "The showcase microgrid bootstrap did not create a published scenario."
            raise ValueError(msg)
        scenario.code = "demo-park-operational"
        scenario.name = "园区源网荷储协同策略V1"
        scenario.source_name = SOURCE_NAME
        scenario.confidence_level = Decimal("0.90")
        scenario.tariff_plan_id = tariff.id if tariff is not None else None
        scenario.grid_emission_factor_id = factor.id
        scenario.change_summary = "基于园区设备台账、分时电价和柔性负荷契约建立演示运行策略。"

        binding_specs = {
            "PCC": (("PCC-METER-01", "pcc"),),
            "PV-01": (("PV-INVERTER-01", "pv"), ("PV-INVERTER-02", "pv")),
            "BESS-01": (("BESS-PCS-01", "storage"),),
            "EVSE-GROUP": (("EVSE-GROUP-01", "charger"),),
            "LIGHTING": (("LIGHTING-01", "lighting"),),
            "WAREHOUSE": (
                ("ASRS-01", "fixed_load"),
                ("CONVEYOR-01", "fixed_load"),
                ("CHILLER-01", "fixed_load"),
                ("HVAC-01", "fixed_load"),
                ("AIR-COMPRESSOR-01", "fixed_load"),
            ),
        }
        for asset_code, rows in binding_specs.items():
            asset = assets[asset_code]
            for equipment_code, role in rows:
                meter = equipment[equipment_code]
                binding = await self.session.scalar(
                    select(m.MicrogridAssetMeterBinding).where(
                        m.MicrogridAssetMeterBinding.site_id == site.id,
                        m.MicrogridAssetMeterBinding.asset_id == asset.id,
                        m.MicrogridAssetMeterBinding.equipment_id == meter.id,
                        m.MicrogridAssetMeterBinding.point_code == "forward_active_total",
                        m.MicrogridAssetMeterBinding.direction == "import",
                    )
                )
                if binding is None:
                    self.session.add(
                        m.MicrogridAssetMeterBinding(
                            site_id=site.id,
                            asset_id=asset.id,
                            equipment_id=meter.id,
                            role=role,
                            point_code="forward_active_total",
                            direction="import",
                            sign=Decimal(1),
                            valid_from=datetime(2024, 1, 1, tzinfo=UTC),
                            source_kind="demo_package",
                            source_name=SOURCE_NAME,
                        )
                    )

        generic_source_ref = "demo-industrial-park/measured-load-projection"
        await self.session.execute(
            delete(m.MicrogridTelemetryFact).where(
                m.MicrogridTelemetryFact.site_id == site.id,
                m.MicrogridTelemetryFact.source_ref == generic_source_ref,
            )
        )
        fixed_load_asset = assets["WAREHOUSE"]
        measured_points: list[m.MicrogridTelemetryFact] = []
        for index in range(21 * 96):
            observed_at = forecast_start.astimezone(UTC) - timedelta(minutes=15 * (21 * 96 - index))
            local = observed_at.astimezone(ZoneInfo("Asia/Shanghai"))
            hour = local.hour + local.minute / 60
            workday = local.weekday() < 5
            operation_load = 510 if 7 <= hour < 22 else 335
            weekday_load = 52 if workday else -35
            cooling_load = 86 * max(0.0, sin(pi * (hour - 7) / 15))
            interval_variation = 20 * (((local.day * 17 + index * 13) % 23) - 11) / 11
            value = Decimal(str(round(operation_load + weekday_load + cooling_load + interval_variation, 3)))
            measured_points.append(
                m.MicrogridTelemetryFact(
                    site_id=site.id,
                    asset_id=fixed_load_asset.id,
                    metric_code="active_power_kw",
                    value=value,
                    unit="kW",
                    observed_at=observed_at,
                    source_kind="measured_projection",
                    source_ref=generic_source_ref,
                    quality="A",
                )
            )
        self.session.add_all(measured_points)

        await self.session.commit()

        stale_forecast = await self.session.scalar(
            select(m.ForecastRun).where(
                m.ForecastRun.site_id == site.id,
                m.ForecastRun.scenario_id == scenario.id,
                m.ForecastRun.horizon_start == forecast_start,
                m.ForecastRun.quality_status != "pass",
            )
        )
        if stale_forecast is not None:
            await self.session.execute(
                delete(m.OptimizationRun).where(m.OptimizationRun.forecast_run_id == stale_forecast.id)
            )
            await self.session.delete(stale_forecast)
            await self.session.commit()

        forecast = await RunForecast(self.session, weather=_ShowcaseWeatherAdapter()).execute(
            site_id=site.id,
            scenario_id=scenario.id,
            start=forecast_start,
        )
        purpose = "operational" if forecast.quality_status == "pass" else "trial"
        optimization = await RunOptimization(self.session).execute(
            forecast_run_id=forecast.id,
            scenario_id=scenario.id,
            purpose=purpose,
            acknowledge_quality_warning=forecast.quality_status == "warning",
        )
        dispatch_id: int | None = None
        if purpose == "operational" and optimization.status in {"optimal", "feasible"}:
            dispatch = await CreateDispatchBatch(self.session).execute(optimization_run_id=optimization.id)
            dispatch_id = dispatch.id
        binding_count = int(
            await self.session.scalar(
                select(func.count(m.MicrogridAssetMeterBinding.id)).where(
                    m.MicrogridAssetMeterBinding.site_id == site.id,
                    m.MicrogridAssetMeterBinding.enabled.is_(True),
                )
            )
            or 0
        )
        return site.id, len(assets), binding_count, forecast.id, optimization.id, dispatch_id

    async def _calculation_runs(
        self,
        *,
        periods: dict[int, m.ReportingPeriod],
        boundaries: dict[int, m.OrganizationBoundary],
    ) -> dict[int, GhgCalculationRun]:
        runs: dict[int, GhgCalculationRun] = {}
        for year in (2024, 2025, 2026):
            inventory_code = f"DEMO-PARK-INV-{year}"
            run = await self.session.scalar(
                select(GhgCalculationRun)
                .where(GhgCalculationRun.inventory_code == inventory_code, GhgCalculationRun.status == "completed")
                .order_by(GhgCalculationRun.id.desc())
            )
            if run is None:
                run = await RunInventoryCalculation(self.session).execute(
                    inventory_code=inventory_code,
                    reporting_profile_code="CORPORATE_ISO14064_GHGP",
                    reporting_period_id=periods[year].id,
                    organization_boundary_id=boundaries[year].id,
                    default_scope2_method="location",
                )
                run.input_snapshot = {
                    **run.input_snapshot,
                    "demoPackage": SHOWCASE_PACKAGE_CODE,
                    "sourceName": SOURCE_NAME,
                }
                await self.session.commit()
            runs[year] = run
        return runs

    async def _evidence(self, activities: list[GhgActivityRecord]) -> None:
        team_id = require_session_tenant_id(self.session)
        grouped: dict[tuple[int, str], list[GhgActivityRecord]] = {}
        for activity in activities:
            grouped.setdefault((activity.period_start.year, activity.iso_category_code), []).append(activity)
        for (year, category), rows in grouped.items():
            evidence_code = f"DEMO-PARK-EVD-{year}-C{category.replace('.', '')}"
            content = self._evidence_content(rows=rows)
            digest = hashlib.sha256(content).hexdigest()
            path = EVIDENCE_ROOT / str(team_id) / evidence_code / f"{year}年度类别{category}活动数据台账.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            evidence = await self.session.scalar(
                select(GhgEvidenceFile).where(GhgEvidenceFile.evidence_code == evidence_code)
            )
            if evidence is None:
                evidence = GhgEvidenceFile(
                    evidence_code=evidence_code,
                    file_name=path.name,
                    document_type="activity_ledger",
                    document_no=evidence_code,
                    issuer="园区能碳管理中心",
                    period_start=date(year, 1, 1),
                    period_end=date(year, 12, 31) if year < 2026 else date(2026, 8, 31),
                    storage_key=str(path),
                    sha256=digest,
                    confidentiality="internal",
                    verification_status="approved" if year < 2026 or category not in {"3.3", "6.1"} else "pending",
                    valid_from=date(year, 1, 1),
                    valid_to=date(year + 2, 12, 31),
                )
                self.session.add(evidence)
                await self.session.flush()
            for activity in rows:
                link_code = f"{evidence_code}-{activity.record_code}"
                link = await self.session.scalar(select(GhgEvidenceLink).where(GhgEvidenceLink.link_code == link_code))
                if link is None:
                    approved = evidence.verification_status == "approved"
                    self.session.add(
                        GhgEvidenceLink(
                            link_code=link_code,
                            record_type="activity",
                            record_code=activity.record_code,
                            evidence_id=evidence.id,
                            evidence_role="activity_evidence",
                            page_or_cell_reference=activity.period_start.strftime("%Y-%m"),
                            coverage_ratio=Decimal(1),
                            review_status="approved" if approved else "pending",
                            reviewer="组织碳复核专员" if approved else None,
                            reviewed_at=datetime(year + 1, 2, 20, tzinfo=UTC) if approved else None,
                        )
                    )
        await self.session.commit()

    async def _reports(self, runs: dict[int, GhgCalculationRun]) -> dict[int, GhgInventoryReport]:
        reports: dict[int, GhgInventoryReport] = {}
        transitions = TransitionInventoryReport(self.session)
        for year, run in runs.items():
            existing = await self.session.scalar(
                select(GhgInventoryReport)
                .where(GhgInventoryReport.inventory_code == run.inventory_code)
                .order_by(GhgInventoryReport.version.desc())
            )
            if existing is not None:
                published_existing = await self.session.scalar(
                    select(GhgInventoryReport)
                    .where(
                        GhgInventoryReport.inventory_code == run.inventory_code,
                        GhgInventoryReport.status == "published",
                    )
                    .order_by(GhgInventoryReport.version.desc())
                )
                if year == 2026 and published_existing is not None and existing.status == "submitted":
                    reports[year] = published_existing
                    continue
                if year < 2026 or existing.status == "published":
                    reports[year] = existing
                    continue
                if existing.status == "submitted":
                    existing = await transitions.execute(
                        report_code=existing.report_code,
                        version=existing.version,
                        action="approve",
                        actor="可持续发展负责人",
                        comment="年内累计盘查边界、数据和证据复核通过",
                    )
                    existing = await transitions.execute(
                        report_code=existing.report_code,
                        version=existing.version,
                        action="publish",
                        actor="园区管理委员会",
                        comment="发布年内累计核查基准版本",
                    )
                    await self._create_current_ytd_revision(run)
                    reports[year] = existing
                    continue
            if year == 2025:
                rejected = await CreateInventoryReport(self.session).execute(
                    run_code=run.run_code,
                    title="2025年度组织温室气体盘查报告",
                    change_summary="首次编制并进入内部复核",
                )
                rejected = await transitions.execute(
                    report_code=rejected.report_code,
                    version=1,
                    action="submit",
                    actor="盘查编制负责人",
                    comment="提交内部审核",
                )
                await transitions.execute(
                    report_code=rejected.report_code,
                    version=1,
                    action="reject",
                    actor="可持续发展负责人",
                    comment="补充分区域用电归集与价值链运输抽样依据",
                )
                report = await CreateInventoryReport(self.session).execute(
                    run_code=run.run_code,
                    title="2025年度组织温室气体盘查报告",
                    change_summary="补充分区域用电归集、证据索引和运输抽样工作底稿",
                )
            else:
                title = f"{year}年度组织温室气体盘查报告" if year < 2026 else "2026年1—8月组织温室气体盘查报告"
                report = await CreateInventoryReport(self.session).execute(
                    run_code=run.run_code,
                    title=title,
                    change_summary="形成完整盘查与证据快照" if year < 2026 else "形成截至8月31日的年内累计盘查快照",
                )
            report = await transitions.execute(
                report_code=report.report_code,
                version=report.version,
                action="submit",
                actor="盘查编制负责人",
                comment="提交内部审核",
            )
            if year < 2026:
                report = await transitions.execute(
                    report_code=report.report_code,
                    version=report.version,
                    action="approve",
                    actor="可持续发展负责人",
                    comment="边界、活动数据、因子和证据复核通过",
                )
                report = await transitions.execute(
                    report_code=report.report_code,
                    version=report.version,
                    action="publish",
                    actor="园区管理委员会",
                    comment="批准发布",
                )
            else:
                report = await transitions.execute(
                    report_code=report.report_code,
                    version=report.version,
                    action="approve",
                    actor="可持续发展负责人",
                    comment="年内累计盘查边界、数据和证据复核通过",
                )
                report = await transitions.execute(
                    report_code=report.report_code,
                    version=report.version,
                    action="publish",
                    actor="园区管理委员会",
                    comment="发布年内累计核查基准版本",
                )
                await self._create_current_ytd_revision(run)
            reports[year] = report
        return reports

    async def _create_current_ytd_revision(self, run: GhgCalculationRun) -> GhgInventoryReport:
        report = await CreateInventoryReport(self.session).execute(
            run_code=run.run_code,
            title="2026年1—8月组织温室气体盘查报告",
            change_summary="更新8月月结复核状态并提交内部审核",
        )
        return await TransitionInventoryReport(self.session).execute(
            report_code=report.report_code,
            version=report.version,
            action="submit",
            actor="盘查编制负责人",
            comment="提交8月月结修订版审核",
        )

    async def _verification(
        self,
        *,
        reports: dict[int, GhgInventoryReport],
        runs: dict[int, GhgCalculationRun],
        activities: list[GhgActivityRecord],
    ) -> int:
        template = await CarbonVerificationTemplateUseCase(self.session).ensure_default_template()
        by_year: dict[int, list[GhgActivityRecord]] = {}
        for activity in activities:
            by_year.setdefault(activity.period_start.year, []).append(activity)
        usecase = CarbonVerificationProjectUseCase(self.session)
        for year in (2024, 2025, 2026):
            project_no = f"DEMO-PARK-VER-{year}-01"
            project = await self.session.scalar(
                select(m.CarbonVerificationProject).where(m.CarbonVerificationProject.project_no == project_no)
            )
            if project is None:
                project = await usecase.create_project(
                    {
                        "project_no": project_no,
                        "project_name": f"{year}年度组织温室气体盘查核查"
                        if year < 2026
                        else "2026年1—8月组织温室气体盘查复核",
                        "project_type": "organization_inventory",
                        "reporting_org_id": reports[year].reporting_org_id,
                        "period_id": reports[year].reporting_period_id,
                        "boundary_id": reports[year].organization_boundary_id,
                        "inventory_report_id": reports[year].id,
                        "calculation_run_id": runs[year].id,
                        "template_version_id": template.id,
                        "verification_year": year,
                        "planned_start": date(year + 1, 2, 1) if year < 2026 else date(2026, 8, 15),
                        "planned_end": date(year + 1, 3, 31) if year < 2026 else date(2026, 9, 30),
                        "lead_reviewer": "组织碳核查组长",
                        "responsible_person": "可持续发展负责人",
                        "verifier_org": "园区内部独立核查组",
                        "assurance_level": "limited",
                        "materiality_threshold_pct": Decimal(5),
                        "verification_basis": "ISO 14064-3:2019",
                        "sampling_strategy": "按类别和贡献度分层抽样；Scope 1、Scope 2及高贡献价值链类别全量复核。",
                        "site_visit_required": True,
                        "site_visit_status": "completed" if year < 2026 else "planned",
                        "conclusion_status": "approved" if year < 2026 else "draft",
                        "scope_description": "覆盖组织边界内Scope 1、Scope 2与纳入盘查的Scope 3活动、因子、计算和证据链。",
                        "source_name": SOURCE_NAME,
                        "standard_code": "ISO 14064-3:2019",
                        "confidence_level": "high" if year < 2026 else "medium",
                    }
                )
            if year in {2025, 2026}:
                finding_no = f"DEMO-PARK-VF-{year}-001"
                finding = await self.session.scalar(
                    select(m.CarbonVerificationFinding).where(m.CarbonVerificationFinding.finding_no == finding_no)
                )
                if finding is None:
                    target = next(
                        item for item in by_year[year] if item.iso_category_code == ("3.1" if year == 2025 else "3.3")
                    )
                    closed = year == 2025
                    self.session.add(
                        m.CarbonVerificationFinding(
                            finding_no=finding_no,
                            project_id=project.id,
                            issue_type="evidence_traceability",
                            finding_type="data_quality",
                            severity="low" if closed else "medium",
                            title="运输抽样依据已补充" if closed else "补充8月通勤抽样复核记录",
                            description="核查抽样所需的业务台账、计算工作底稿与证据索引。",
                            action_required="归档抽样工作底稿" if closed else "完成样本复核并更新证据状态",
                            record_type="activity",
                            record_id=target.id,
                            record_code=target.record_code,
                            scope=target.ghg_scope,
                            display_name=target.activity_name,
                            period=target.period_start.strftime("%Y-%m"),
                            status="closed" if closed else "open",
                            owner="数据治理专员",
                            due_date=date(2026, 9, 15),
                            correction_comment="已完成补充复核" if closed else None,
                            reviewer="组织碳核查组长" if closed else None,
                            reviewed_at=datetime(2026, 3, 12) if closed else None,
                            closed_at=datetime(2026, 3, 12) if closed else None,
                            source_name=SOURCE_NAME,
                            standard_code="ISO 14064-3:2019",
                            source_payload={"demoPackage": SHOWCASE_PACKAGE_CODE},
                        )
                    )
                    await self.session.commit()
            await usecase.refresh_project_status(project.id)
        return int(await self.session.scalar(select(func.count(m.CarbonVerificationProject.id))) or 0)

    async def _reduction(
        self,
        *,
        boundary: m.OrganizationBoundary,
        areas: dict[str, m.MonitorSector],
        equipment: dict[str, m.MonitorEquipment],
        runs: dict[int, GhgCalculationRun],
    ) -> int:
        baseline_tco2e = Decimal(runs[2024].total_co2e_kg or 0) / Decimal(1000)
        target = await self.session.scalar(
            select(reduction_m.ReductionTarget).where(reduction_m.ReductionTarget.code == "DEMO-PARK-NETZERO-2030")
        )
        if target is None:
            target = reduction_m.ReductionTarget(
                code="DEMO-PARK-NETZERO-2030",
                name="园区2030运营减排目标",
                version=1,
                target_year=2030,
                baseline_year=2024,
                target_type="absolute",
                baseline_tco2e=baseline_tco2e,
                target_reduction_tco2e=baseline_tco2e * Decimal("0.42"),
                target_reduction_pct=Decimal(42),
                organization_boundary_id=boundary.id,
                area_id=areas["ROOT"].id,
                business_unit="园区运营",
                trajectory=[
                    {
                        "year": year,
                        "targetTco2e": float(
                            baseline_tco2e * (Decimal(1) - Decimal("0.42") * Decimal(year - 2024) / Decimal(6))
                        ),
                    }
                    for year in range(2024, 2031)
                ],
                status="published",
                source_name=SOURCE_NAME,
                published_at=datetime(2025, 3, 28, tzinfo=UTC),
            )
            self.session.add(target)
            await self.session.flush()
        methodology = await self.session.scalar(
            select(reduction_m.ReductionMethodologyVersion)
            .where(reduction_m.ReductionMethodologyVersion.executable.is_(True))
            .order_by(reduction_m.ReductionMethodologyVersion.id)
        )
        if methodology is None:
            message = "The published reduction methodology catalog must be seeded before installing showcase data."
            raise ValueError(message)
        ccer_methodology = await self.session.scalar(
            select(reduction_m.ReductionMethodologyVersion).where(
                reduction_m.ReductionMethodologyVersion.code == "CCER-06-001-V01",
                reduction_m.ReductionMethodologyVersion.status == "published",
                reduction_m.ReductionMethodologyVersion.executable.is_(True),
            )
        )
        if ccer_methodology is None:
            message = "The published CCER public-building methodology must be seeded before installing showcase data."
            raise ValueError(message)
        project_specs = (
            (
                "PV-SELFUSE",
                "屋顶光伏自发自用提升",
                "internal_action",
                "renewable_energy",
                "monitoring",
                "monitored",
                "ENERGY",
                "PV-INVERTER-01",
                Decimal(2860000),
                Decimal(318),
                Decimal(244),
                Decimal(88),
            ),
            (
                "BESS-PEAK",
                "储能削峰与需量控制",
                "internal_action",
                "energy_efficiency",
                "implementing",
                "estimated",
                "ENERGY",
                "BESS-PCS-01",
                Decimal(1680000),
                Decimal(86),
                Decimal(34),
                Decimal(66),
            ),
            (
                "HVAC-RETROFIT",
                "办公暖通与围护结构节能改造",
                "ccer",
                "energy_efficiency",
                "monitoring",
                "monitored",
                "OFFICE",
                "HVAC-01",
                Decimal(2380000),
                Decimal(126),
                Decimal(92),
                Decimal(82),
            ),
            (
                "FLEX-LOAD",
                "照明与充电负荷柔性调度",
                "internal_action",
                "operational_optimization",
                "monitoring",
                "monitored",
                "CHARGING",
                "EVSE-GROUP-01",
                Decimal(460000),
                Decimal(38),
                Decimal(31),
                Decimal(94),
            ),
            (
                "REFRIGERANT",
                "低GWP制冷剂替代与泄漏控制",
                "iso14064_2",
                "refrigerant_control",
                "implementing",
                "estimated",
                "COLD_WH",
                "REFRIGERANT-01",
                Decimal(920000),
                Decimal(168),
                Decimal(46),
                Decimal(54),
            ),
        )
        now = datetime(2026, 8, 23, tzinfo=UTC)
        for index, (
            suffix,
            name,
            track,
            category,
            status,
            reduction_status,
            area_code,
            equipment_code,
            investment,
            expected,
            monitored,
            progress,
        ) in enumerate(project_specs, start=1):
            code = f"DEMO-PARK-{suffix}"
            project = await self.session.scalar(
                select(reduction_m.ReductionProject).where(reduction_m.ReductionProject.code == code)
            )
            if project is not None:
                continue
            project = reduction_m.ReductionProject(
                code=code,
                name=name,
                track=track,
                category=category,
                status=status,
                reduction_status=reduction_status,
                risk_level="medium" if track != "internal_action" else "low",
                owner_name=("能源平台主管", "设备平台主管", "工程平台主管", "运营平台主管", "冷链设备主管")[index - 1],
                department_name=("能源动力部", "设备管理部", "工程管理部", "物流运营部", "冷链运营部")[index - 1],
                organization_boundary_id=boundary.id,
                methodology_id=ccer_methodology.id if track == "ccer" else None,
                target_id=target.id,
                planned_start=date(2025, index, 1),
                planned_end=date(2027, min(index + 4, 12), 28),
                actual_start=date(2025, index, 15),
                progress_pct=progress,
                investment_cny=investment,
                expected_reduction_tco2e=expected,
                monitored_reduction_tco2e=monitored,
                verified_reduction_tco2e=monitored
                if reduction_status == "monitored" and index in {1, 4}
                else Decimal(0),
                objective="降低园区能源成本和温室气体排放，并形成可监测、可复核的项目效果。",
                implementation_plan="完成资源绑定、基准线锁定、监测计划、效果计算和内部复核。",
                evaluation_summary="项目按月跟踪进度、物理减排效果与财务收益。",
                inventory_impact_kind="scope2_location" if category != "refrigerant_control" else "scope1",
                source_name=SOURCE_NAME,
            )
            self.session.add(project)
            await self.session.flush()
            area = areas[area_code]
            item = equipment[equipment_code]
            self.session.add(
                reduction_m.ReductionProjectResourceLink(
                    project_id=project.id,
                    resource_type="equipment",
                    resource_key=item.code,
                    area_id=area.id,
                    equipment_id=item.id,
                    role="affected",
                    allocation_ratio=Decimal(1),
                    resource_snapshot={
                        "areaCode": area.code,
                        "areaName": area.name,
                        "equipmentCode": item.code,
                        "equipmentName": item.name,
                    },
                )
            )
            self.session.add(
                reduction_m.ReductionProjectBoundary(
                    project_id=project.id,
                    version=1,
                    status="locked",
                    physical_boundary={"areas": [area.code], "equipment": [item.code]},
                    ghg_sources_sinks=[{"kind": "source", "scope": project.inventory_impact_kind}],
                    included_gases=["CO2", "CH4", "N2O"] if category != "refrigerant_control" else ["HFCs"],
                    exclusions=[],
                    organization_snapshot={"boundaryNo": boundary.boundary_no},
                    locked_at=now,
                )
            )
            baseline = reduction_m.ReductionBaselineScenario(
                project_id=project.id,
                version=1,
                name="2024基准情景",
                status="locked",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                model_kind="adjusted_historical",
                model_parameters={"baselineYear": 2024, "adjustment": "throughput_weather"},
                normalization_variables=[{"code": "throughput", "unit": "t"}, {"code": "CDD", "unit": "K·d"}],
                factor_snapshot={"sourceName": SOURCE_NAME},
                inventory_reference={"runCode": runs[2024].run_code},
                baseline_tco2e=expected * Decimal("1.18"),
                locked_at=now,
            )
            self.session.add(baseline)
            await self.session.flush()
            self.session.add(
                reduction_m.ReductionMonitoringPlan(
                    project_id=project.id,
                    version=1,
                    status="published",
                    parameters=[
                        {
                            "code": "energy",
                            "name": "项目边界能源消耗",
                            "unit": "kWh",
                            "frequency": "monthly",
                            "equipmentCode": item.code,
                        },
                        {"code": "throughput", "name": "业务活动水平", "unit": "t", "frequency": "monthly"},
                    ],
                    quality_controls=[
                        {"rule": "completeness", "thresholdPct": 95},
                        {"rule": "meterCalibration", "frequency": "annual"},
                    ],
                    evidence_requirements=[
                        {"documentType": "meter_ledger", "required": True},
                        {"documentType": "project_acceptance", "required": True},
                    ],
                    data_retention_years=10,
                    readiness_status="ready",
                    published_at=now,
                )
            )
            calc = reduction_m.ReductionCalculationRun(
                project_id=project.id,
                methodology_id=ccer_methodology.id if track == "ccer" else methodology.id,
                baseline_id=baseline.id,
                idempotency_key=f"demo-park:{code}:2026-08",
                run_kind="ex_post" if monitored > 0 else "ex_ante",
                status="completed",
                assurance_status="internally_reviewed" if index in {1, 4} else "monitored",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 8, 31),
                input_snapshot={"sourceName": SOURCE_NAME, "equipmentCode": item.code},
                methodology_snapshot={
                    "methodologyCode": ccer_methodology.code if track == "ccer" else methodology.code
                },
                baseline_snapshot={"baselineId": baseline.id, "baselineTco2e": str(baseline.baseline_tco2e)},
                factor_snapshot={"sourceName": SOURCE_NAME},
                baseline_tco2e=baseline.baseline_tco2e,
                project_tco2e=(baseline.baseline_tco2e or Decimal(0)) - monitored,
                leakage_tco2e=Decimal(0),
                deduction_tco2e=Decimal(0),
                reduction_tco2e=monitored,
                components={"monitored": str(monitored)},
                diagnostics=[],
                completed_at=now,
            )
            self.session.add(calc)
            await self.session.flush()
            annual_savings = (investment / Decimal("5.4")).quantize(Decimal("0.01"))
            self.session.add(
                reduction_m.ReductionFinancialScenario(
                    project_id=project.id,
                    version=1,
                    name="综合收益情景",
                    capex_cny=investment,
                    annual_opex_cny=investment * Decimal("0.015"),
                    annual_energy_savings_cny=annual_savings,
                    carbon_price_cny_per_t=Decimal(85),
                    annual_reduction_tco2e=expected,
                    project_life_years=10,
                    discount_rate=Decimal("0.08"),
                    npv_cny=annual_savings * Decimal("6.71") - investment,
                    irr=Decimal("0.142"),
                    payback_years=investment / annual_savings,
                    macc_cny_per_t=(investment - annual_savings * Decimal(10)) / (expected * Decimal(10)),
                    status="published",
                )
            )
            self.session.add(
                reduction_m.ReductionProjectReview(
                    project_id=project.id,
                    calculation_run_id=calc.id,
                    review_type="internal_review",
                    decision="approved" if index in {1, 4} else "conditional",
                    reviewer_name="减排项目评审组",
                    organization_name="园区能碳管理中心",
                    reviewed_at=now,
                    findings=[]
                    if index in {1, 4}
                    else [{"severity": "low", "status": "open", "title": "持续补充监测期数据"}],
                    conclusion="项目计算边界、基准线和监测数据已完成内部复核。",
                )
            )
            if track == "ccer":
                self.session.add(
                    reduction_m.ReductionApplicabilityAssessment(
                        project_id=project.id,
                        methodology_id=ccer_methodology.id,
                        status="needs_material",
                        answers={"buildingType": "existing_public_building", "measure": "envelope_hvac"},
                        checks=[
                            {"code": "applicability", "passed": True},
                            {"code": "additionality_material", "passed": False},
                        ],
                        blocking_reasons=["补充额外性论证材料"],
                        methodology_snapshot={"code": ccer_methodology.code, "version": ccer_methodology.version},
                        assessed_by="方法学专员",
                    )
                )
                self.session.add(
                    reduction_m.CcerDossier(
                        project_id=project.id,
                        status="preparing",
                        project_design_document_no="PDD-DEMO-PARK-2026-01",
                        material_checklist=[
                            {"name": "项目设计文件", "status": "completed"},
                            {"name": "额外性论证", "status": "pending"},
                        ],
                        milestones=[
                            {"name": "适用性筛选", "date": "2026-05-12", "status": "completed"},
                            {"name": "材料准备", "date": "2026-08-23", "status": "in_progress"},
                        ],
                    )
                )
            self.session.add(
                reduction_m.ReductionAuditEvent(
                    project_id=project.id,
                    entity_type="project",
                    entity_id=project.id,
                    event_type="demo_initialized",
                    actor_name="演示数据安装器",
                    after_snapshot={"status": status, "progressPct": str(progress)},
                    reason=SOURCE_NAME,
                )
            )
        await self.session.commit()
        return int(await self.session.scalar(select(func.count(reduction_m.ReductionProject.id))) or 0)

    async def _climate(
        self,
        *,
        boundary: m.OrganizationBoundary,
        runs: dict[int, GhgCalculationRun],
        profile: str,
        activities: list[GhgActivityRecord],
    ) -> int:
        if profile not in {"foundation", "transition", "leadership"}:
            msg = "Climate profile must be foundation, transition, or leadership."
            raise ValueError(msg)
        usecases = ClimateGovernanceUseCases(self.session)
        baseline_tco2e = float(Decimal(runs[2024].total_co2e_kg or 0) / Decimal(1000))
        shared = {"demoPackageCode": SHOWCASE_PACKAGE_CODE, "profileCode": profile, "baselineYear": 2024}
        sbti = await usecases.create_program(
            ClimateProgramRequest(
                code="DEMO-PARK-SBTI-2026",
                name="科学碳目标跟踪",
                framework="sbti",
                reporting_year=2026,
                organization_boundary_id=boundary.id,
                owner_name="可持续发展负责人",
                configuration={
                    **shared,
                    "scope2Method": "location",
                    "coveragePolicy": "scope1_scope2_and_material_scope3",
                },
                source_name=SOURCE_NAME,
            )
        )
        if not await self.session.scalar(
            select(func.count()).select_from(m.ClimateTarget).where(m.ClimateTarget.program_id == sbti.id)
        ):
            await usecases.publish_target(
                sbti.id,
                ClimateTargetRequest(
                    target_kind="absolute_reduction",
                    baseline_year=2024,
                    baseline_value=baseline_tco2e,
                    target_year=2030,
                    reduction_pct=42.0 if profile != "foundation" else 30.0,
                    scope2_method="location",
                    scope_coverage={"scope12Pct": 100.0, "scope3Pct": 72.0 if profile == "leadership" else 55.0},
                    source_name=SOURCE_NAME,
                    effective_from=date(2025, 1, 1),
                ),
            )
        cdp = await usecases.create_program(
            ClimateProgramRequest(
                code="DEMO-PARK-CDP-2026",
                name="年度气候披露",
                framework="cdp",
                reporting_year=2026,
                organization_boundary_id=boundary.id,
                owner_name="ESG披露经理",
                configuration={**shared, "managementReview": True},
                source_name=SOURCE_NAME,
            )
        )
        await usecases.save_disclosure_cycle(
            cdp.id,
            ClimateDisclosureCycleRequest(
                reporting_year=2026,
                status="internal_review" if profile != "foundation" else "preparing",
                owner_name="ESG披露经理",
                due_date=date(2026, 9, 30),
                domain_statuses={
                    "governance": True,
                    "risks": True,
                    "strategy": profile != "foundation",
                    "metrics": True,
                    "targets": True,
                    "verification": profile == "leadership",
                },
                response_snapshot={"inventoryRunCode": runs[2026].run_code, "periodEnd": "2026-08-31"},
                evidence_snapshot=[{"code": "DEMO-PARK-EVD-2026-C21", "status": "approved"}],
            ),
        )
        re100 = await usecases.create_program(
            ClimateProgramRequest(
                code="DEMO-PARK-RE100-2026",
                name="可再生电力目标跟踪",
                framework="re100",
                reporting_year=2026,
                organization_boundary_id=boundary.id,
                owner_name="能源采购负责人",
                configuration={**shared, "electricityDataYear": 2025},
                source_name=SOURCE_NAME,
            )
        )
        if not await self.session.scalar(
            select(func.count()).select_from(m.ClimateTarget).where(m.ClimateTarget.program_id == re100.id)
        ):
            await usecases.publish_target(
                re100.id,
                ClimateTargetRequest(
                    target_kind="renewable_electricity_share",
                    baseline_year=2025,
                    baseline_value=18.0,
                    target_year=2030,
                    target_value=100.0,
                    scope2_method="market",
                    scope_coverage={"electricityPct": 100.0},
                    source_name=SOURCE_NAME,
                    effective_from=date(2025, 1, 1),
                ),
            )
        annual_electricity_kwh = sum(
            (
                item.activity_amount
                for item in activities
                if item.period_start.year == 2025 and item.activity_code == "C21-ELECTRICITY"
            ),
            Decimal(0),
        )
        claims = (
            ("SELFUSE", "self_generation", Decimal("0.16"), "solar", "allocated"),
            ("GEC", "certificate", Decimal("0.12" if profile != "foundation" else "0.06"), "wind", "retired"),
            ("PPA", "ppa", Decimal("0.08" if profile == "leadership" else "0.04"), "solar", "allocated"),
        )
        for suffix, source_type, share, technology, ownership in claims:
            claim_no = f"DEMO-PARK-RE-{suffix}-2025"
            exists = await self.session.scalar(
                select(m.RenewableElectricityClaim.id).where(m.RenewableElectricityClaim.claim_no == claim_no)
            )
            if exists:
                continue
            await usecases.create_claim(
                re100.id,
                RenewableElectricityClaimRequest(
                    claim_no=claim_no,
                    source_type=source_type,
                    reporting_year=2025,
                    period_start=date(2025, 1, 1),
                    period_end=date(2025, 12, 31),
                    quantity_mwh=float(annual_electricity_kwh * share / Decimal(1000)),
                    technology=technology,
                    generation_country="CN",
                    consumption_country="CN",
                    registry="企业可再生电力属性台账",
                    certificate_no=f"DEMO-PARK-CERT-{suffix}-2025",
                    vintage_year=2025,
                    ownership_status=ownership,
                    retired_at=datetime(2026, 2, 28, tzinfo=UTC),
                    evidence_reference=f"DEMO-PARK-EVD-2025-C21#{suffix}",
                    source_name=SOURCE_NAME,
                    remark="已完成唯一性分配的演示凭证",
                ),
            )
        for program in (sbti, cdp, re100):
            await usecases.run_assessment(program.id, idempotency_key=f"demo-park:{profile}:2026:{program.framework}")
        return 3

    async def _carbon_assets(self, *, boundary: m.OrganizationBoundary) -> tuple[int, int, int]:  # noqa: C901
        """Build a traceable asset ledger without treating local rooftop PV as CCER."""
        instruments, _national_rule = await ensure_carbon_asset_reference_data(self.session)
        account_specs = (
            ("CEA-NATIONAL", "DEMO-PARK-CEA-REFERENCE", "全国碳市场参考账户", "reference_only"),
            ("CCER-NATIONAL", "DEMO-PARK-CCER-HOLDING", "自愿减排量持有账户", "external_procurement"),
            (
                "GREEN-CERTIFICATE-CN",
                "DEMO-PARK-GEC-ATTRIBUTE",
                "可再生电力环境属性账户",
                "renewable_electricity_claim",
            ),
        )
        accounts: dict[str, m.CarbonAssetAccount] = {}
        for instrument_code, account_code, account_name, account_role in account_specs:
            account = await self.session.scalar(
                select(m.CarbonAssetAccount).where(m.CarbonAssetAccount.account_code == account_code)
            )
            if account is None:
                account = m.CarbonAssetAccount(account_code=account_code)
                self.session.add(account)
            account.instrument_id = instruments[instrument_code].id
            account.account_name = account_name
            account.registry_account_no = None
            account.owner_name = SHOWCASE_TENANT_NAME
            account.status = "active"
            account.source_name = SOURCE_NAME
            account.remark = f"账户用途：{account_role}"
            await self.session.flush()
            accounts[instrument_code] = account

        lot_specs = (
            CarbonAssetLotSpec(
                instrument_code="CCER-NATIONAL",
                lot_no="DEMO-PARK-CCER-2024-PROCUREMENT",
                vintage_year=2024,
                issued_quantity=Decimal(2600),
                acquisition_unit_cost=Decimal("72.50"),
                project_name="外购国家核证自愿减排量组合",
                valid_from=date(2025, 1, 1),
                attributes={
                    "origin": "external_procurement",
                    "localReductionProject": False,
                    "assetPurpose": "voluntary_offset",
                },
                standard_code="生态环境部令第31号",
                evidence_ref="DEMO-PARK-EVD-CCER-PROCUREMENT-2025",
            ),
            CarbonAssetLotSpec(
                instrument_code="GREEN-CERTIFICATE-CN",
                lot_no="DEMO-PARK-GEC-2025-PROCUREMENT",
                vintage_year=2025,
                issued_quantity=Decimal(10000),
                acquisition_unit_cost=Decimal("4.80"),
                project_name="2025年度可再生电力环境属性采购",
                valid_from=date(2025, 1, 1),
                attributes={"energyMwhPerCertificate": 1, "claimUse": "scope2_market"},
                standard_code="国能发新能规〔2024〕67号",
                evidence_ref="DEMO-PARK-EVD-GEC-PROCUREMENT-2025",
            ),
            CarbonAssetLotSpec(
                instrument_code="GREEN-CERTIFICATE-CN",
                lot_no="DEMO-PARK-GEC-2026-PROCUREMENT",
                vintage_year=2026,
                issued_quantity=Decimal(9000),
                acquisition_unit_cost=Decimal("5.20"),
                project_name="2026年度可再生电力环境属性采购",
                valid_from=date(2026, 1, 1),
                attributes={"energyMwhPerCertificate": 1, "claimUse": "scope2_market"},
                standard_code="国能发新能规〔2024〕67号",
                evidence_ref="DEMO-PARK-EVD-GEC-PROCUREMENT-2026",
            ),
        )
        lots: dict[str, m.CarbonAssetLot] = {}
        for spec in lot_specs:
            lot = await self.session.scalar(select(m.CarbonAssetLot).where(m.CarbonAssetLot.lot_no == spec.lot_no))
            if lot is None:
                lot = m.CarbonAssetLot(lot_no=spec.lot_no)
                self.session.add(lot)
            instrument_code = spec.instrument_code
            lot.account_id = accounts[instrument_code].id
            lot.instrument_id = instruments[instrument_code].id
            lot.registry_serial_no = None
            lot.project_code = None
            lot.project_name = spec.project_name
            lot.vintage_year = spec.vintage_year
            lot.issued_quantity = spec.issued_quantity
            lot.acquisition_unit_cost = spec.acquisition_unit_cost
            lot.currency = "CNY"
            lot.valid_from = spec.valid_from
            lot.valid_to = None
            lot.status = "active"
            lot.attributes = dict(spec.attributes)
            lot.source_name = SOURCE_NAME
            lot.standard_code = spec.standard_code
            lot.evidence_ref = spec.evidence_ref
            lot.remark = "来源、用途和唯一使用关系均纳入资产审计台账。"
            await self.session.flush()
            lots[lot.lot_no] = lot

        voluntary_rule = await self.session.scalar(
            select(m.CarbonComplianceRuleVersion).where(
                m.CarbonComplianceRuleVersion.rule_code == "DEMO-PARK-VOLUNTARY-OFFSET",
                m.CarbonComplianceRuleVersion.version == 1,
            )
        )
        if voluntary_rule is None:
            voluntary_rule = m.CarbonComplianceRuleVersion(
                rule_code="DEMO-PARK-VOLUNTARY-OFFSET",
                version=1,
            )
            self.session.add(voluntary_rule)
        voluntary_rule.rule_name = "企业自愿抵消计划管理规则"
        voluntary_rule.market = "voluntary"
        voluntary_rule.eligible_instrument_classes = ["CCER"]
        voluntary_rule.max_offset_ratio = Decimal(1)
        voluntary_rule.parameters = {
            "purpose": "voluntary_offset",
            "prohibitDoubleClaim": True,
            "requiresRetirementEvidence": True,
        }
        voluntary_rule.effective_from = date(2025, 1, 1)
        voluntary_rule.effective_to = None
        voluntary_rule.status = "published"
        voluntary_rule.source_name = "企业气候行动与自愿抵消管理制度"
        voluntary_rule.standard_code = "ISO 14068-1:2023"
        voluntary_rule.source_url = None
        await self.session.flush()

        cycle_specs = (
            (
                "DEMO-PARK-OFFSET-2025",
                "2025年度企业自愿抵消计划",
                date(2025, 1, 1),
                date(2025, 12, 31),
                date(2026, 3, 31),
                Decimal(600),
                "completed",
            ),
            (
                "DEMO-PARK-OFFSET-2026",
                "2026年度企业自愿抵消计划",
                date(2026, 1, 1),
                date(2026, 12, 31),
                date(2027, 3, 31),
                Decimal(2400),
                "open",
            ),
        )
        cycles: dict[str, m.CarbonComplianceCycle] = {}
        for cycle_code, cycle_name, period_start, period_end, due_date, obligation, status in cycle_specs:
            cycle = await self.session.scalar(
                select(m.CarbonComplianceCycle).where(m.CarbonComplianceCycle.cycle_code == cycle_code)
            )
            if cycle is None:
                cycle = m.CarbonComplianceCycle(cycle_code=cycle_code)
                self.session.add(cycle)
            cycle.cycle_name = cycle_name
            cycle.market = "voluntary"
            cycle.period_start = period_start
            cycle.period_end = period_end
            cycle.surrender_due_date = due_date
            cycle.rule_version_id = voluntary_rule.id
            cycle.boundary_id = boundary.id
            cycle.covered_emissions_tco2e = obligation
            cycle.required_surrender_tco2e = obligation
            cycle.obligation_source = "management_plan"
            cycle.obligation_snapshot = {
                "purpose": "voluntary_offset",
                "organizationInventoryIsReadOnly": True,
                "ordinaryRooftopPvIsNotCcer": True,
            }
            cycle.status = status
            cycle.source_name = SOURCE_NAME
            cycle.evidence_ref = f"DEMO-PARK-EVD-OFFSET-PLAN-{period_start.year}"
            cycle.remark = "企业自愿计划，不代表全国碳市场法定履约义务。"
            await self.session.flush()
            cycles[cycle_code] = cycle

        ccer_lot = lots["DEMO-PARK-CCER-2024-PROCUREMENT"]
        offset_movement = await self.session.scalar(
            select(m.CarbonAssetMovement).where(m.CarbonAssetMovement.movement_no == "DEMO-PARK-CAMV-CCER-OFFSET-2025")
        )
        if offset_movement is None:
            offset_movement = m.CarbonAssetMovement(
                movement_no="DEMO-PARK-CAMV-CCER-OFFSET-2025",
                account_id=ccer_lot.account_id,
                instrument_id=ccer_lot.instrument_id,
                lot_id=ccer_lot.id,
                movement_type="offset",
                quantity_delta=Decimal(-600),
                unit_price=Decimal("76.00"),
                fee_amount=Decimal(0),
                currency="CNY",
                occurred_on=date(2026, 3, 20),
                posted_at=datetime(2026, 3, 20, 9, tzinfo=UTC),
                counterparty="企业自愿抵消注销台账",
                reference_type="compliance_settlement",
                source_name=SOURCE_NAME,
                evidence_ref="DEMO-PARK-EVD-CCER-RETIREMENT-2025",
                remark="用于2025年度企业自愿抵消计划。",
            )
            self.session.add(offset_movement)
            await self.session.flush()

        settlement = await self.session.scalar(
            select(m.CarbonComplianceSettlement).where(
                m.CarbonComplianceSettlement.settlement_no == "DEMO-PARK-CASET-2025"
            )
        )
        if settlement is None:
            settlement = m.CarbonComplianceSettlement(
                settlement_no="DEMO-PARK-CASET-2025",
                cycle_id=cycles["DEMO-PARK-OFFSET-2025"].id,
            )
            self.session.add(settlement)
        settlement.status = "completed"
        settlement.submitted_at = datetime(2026, 3, 18, 9, tzinfo=UTC)
        settlement.completed_at = datetime(2026, 3, 20, 9, tzinfo=UTC)
        settlement.total_cea_tco2e = Decimal(0)
        settlement.total_ccer_tco2e = Decimal(600)
        settlement.rule_snapshot = {
            "ruleCode": voluntary_rule.rule_code,
            "version": voluntary_rule.version,
            "purpose": "voluntary_offset",
        }
        settlement.source_name = SOURCE_NAME
        settlement.evidence_ref = "DEMO-PARK-EVD-CCER-RETIREMENT-2025"
        settlement.remark = "已完成注销凭证与批次核对。"
        await self.session.flush()
        offset_movement.reference_id = settlement.id
        settlement_line = await self.session.scalar(
            select(m.CarbonComplianceSettlementLine).where(
                m.CarbonComplianceSettlementLine.settlement_id == settlement.id,
                m.CarbonComplianceSettlementLine.lot_id == ccer_lot.id,
            )
        )
        if settlement_line is None:
            settlement_line = m.CarbonComplianceSettlementLine(
                settlement_id=settlement.id,
                lot_id=ccer_lot.id,
                instrument_class="CCER",
                quantity=Decimal(600),
                purpose="offset",
                movement_id=offset_movement.id,
            )
            self.session.add(settlement_line)

        certificate_claim = await self.session.scalar(
            select(m.RenewableElectricityClaim).where(m.RenewableElectricityClaim.claim_no == "DEMO-PARK-RE-GEC-2025")
        )
        if certificate_claim is None:
            msg = "renewable electricity certificate claim must exist before carbon assets are built"
            raise RuntimeError(msg)
        certificate_quantity = Decimal(certificate_claim.quantity_mwh)
        green_lot = lots["DEMO-PARK-GEC-2025-PROCUREMENT"]
        usage_movement = await self.session.scalar(
            select(m.CarbonAssetMovement).where(m.CarbonAssetMovement.movement_no == "DEMO-PARK-CAMV-GEC-CONSUME-2025")
        )
        if usage_movement is None:
            usage_movement = m.CarbonAssetMovement(
                movement_no="DEMO-PARK-CAMV-GEC-CONSUME-2025",
                account_id=green_lot.account_id,
                instrument_id=green_lot.instrument_id,
                lot_id=green_lot.id,
                movement_type="consume",
                quantity_delta=-certificate_quantity,
                unit_price=green_lot.acquisition_unit_cost,
                fee_amount=Decimal(0),
                currency="CNY",
                occurred_on=date(2026, 2, 28),
                posted_at=datetime(2026, 2, 28, 9, tzinfo=UTC),
                reference_type="environmental_asset_usage",
                source_name=SOURCE_NAME,
                evidence_ref="DEMO-PARK-EVD-2025-C21#GEC",
                remark="与2025年度可再生电力声明一一对应。",
            )
            self.session.add(usage_movement)
            await self.session.flush()
        usage = await self.session.scalar(
            select(m.EnvironmentalAssetUsage).where(m.EnvironmentalAssetUsage.usage_no == "DEMO-PARK-CAUS-GEC-2025")
        )
        if usage is None:
            usage = m.EnvironmentalAssetUsage(
                usage_no="DEMO-PARK-CAUS-GEC-2025",
                lot_id=green_lot.id,
                quantity=certificate_quantity,
                purpose="scope2_market",
                target_type="renewable_electricity_claim",
                target_id=certificate_claim.id,
                reporting_period="2025",
                used_at=datetime(2026, 2, 28, 9, tzinfo=UTC),
                movement_id=usage_movement.id,
                evidence_ref="DEMO-PARK-EVD-2025-C21#GEC",
                remark="用于市场法可再生电力属性声明，不进入碳市场履约。",
            )
            self.session.add(usage)
            await self.session.flush()
        usage_movement.reference_id = usage.id

        await self.session.execute(
            delete(m.CarbonMarketQuote).where(
                m.CarbonMarketQuote.source_name == "企业预算价格曲线",
                m.CarbonMarketQuote.source_version == "2026.08-v1",
            )
        )
        for spec in PUBLIC_MARKET_QUOTES:
            instrument = instruments[spec.instrument_code]
            quote = await self.session.scalar(
                select(m.CarbonMarketQuote).where(
                    m.CarbonMarketQuote.instrument_id == instrument.id,
                    m.CarbonMarketQuote.trade_date == spec.trade_date,
                    m.CarbonMarketQuote.source_name == spec.source_name,
                    m.CarbonMarketQuote.source_version == spec.source_version,
                )
            )
            if quote is None:
                quote = m.CarbonMarketQuote(
                    instrument_id=instrument.id,
                    trade_date=spec.trade_date,
                    source_name=spec.source_name,
                    source_version=spec.source_version,
                )
                self.session.add(quote)
            quote.open_price = spec.open_price
            quote.high_price = spec.high_price
            quote.low_price = spec.low_price
            quote.close_price = spec.close_price
            quote.volume = spec.volume
            quote.turnover = spec.turnover
            quote.currency = "CNY"
            quote.quote_unit = instrument.native_unit
            quote.source_kind = "observed"
            quote.source_url = spec.source_url
            quote.published_at = spec.published_at

        scenario_specs = (
            ("BASE", "基准价格情景", Decimal(84), Decimal(78), Decimal("0.05")),
            ("HIGH", "高价格压力情景", Decimal(110), Decimal(96), Decimal("0.10")),
            ("RESERVE", "审慎储备情景", Decimal(92), Decimal(84), Decimal("0.15")),
        )
        balance_snapshot = {
            "CEA": Decimal(0),
            "CCER": Decimal(2000),
            "GREEN_CERTIFICATE": Decimal(19000) - certificate_quantity,
        }
        active_cycle = cycles["DEMO-PARK-OFFSET-2026"]
        for suffix, scenario_name, cea_price, ccer_price, safety_margin in scenario_specs:
            scenario_code = f"DEMO-PARK-COST-{suffix}-2026"
            scenario = await self.session.scalar(
                select(m.CarbonCostScenario).where(m.CarbonCostScenario.scenario_code == scenario_code)
            )
            parameters = {
                "ceaPrice": float(cea_price),
                "ccerPrice": float(ccer_price),
                "safetyMarginRatio": float(safety_margin),
            }
            if scenario is None:
                scenario = m.CarbonCostScenario(scenario_code=scenario_code)
                self.session.add(scenario)
            scenario.scenario_name = scenario_name
            scenario.cycle_id = active_cycle.id
            scenario.status = "active"
            scenario.parameters = parameters
            scenario.source_name = "企业年度预算价格与风险偏好"
            scenario.remark = "用于预算和采购决策，不作为已成交市场价格。"
            await self.session.flush()
            result = calculate_cost_result(
                obligation_tco2e=Decimal(active_cycle.required_surrender_tco2e),
                cea_balance_tco2e=balance_snapshot["CEA"],
                ccer_balance_tco2e=balance_snapshot["CCER"],
                max_offset_ratio=Decimal(voluntary_rule.max_offset_ratio),
                cea_price=cea_price,
                ccer_price=ccer_price,
                safety_margin_ratio=safety_margin,
            )
            run_no = f"DEMO-PARK-COST-RUN-{suffix}-202608"
            cost_run = await self.session.scalar(select(m.CarbonCostRun).where(m.CarbonCostRun.run_no == run_no))
            if cost_run is None:
                cost_run = m.CarbonCostRun(run_no=run_no, scenario_id=scenario.id)
                self.session.add(cost_run)
            cost_run.status = "completed"
            cost_run.input_snapshot = {
                "scenario": parameters,
                "cycleId": active_cycle.id,
                "cycleCode": active_cycle.cycle_code,
                "requiredSurrenderTco2e": float(active_cycle.required_surrender_tco2e),
                "ruleVersionId": voluntary_rule.id,
            }
            cost_run.quote_snapshot = {
                "ceaPrice": float(cea_price),
                "ccerPrice": float(ccer_price),
                "currency": "CNY",
                "sourceName": "企业年度预算价格与风险偏好",
            }
            cost_run.balance_snapshot = {key: float(value) for key, value in balance_snapshot.items()}
            cost_run.result_summary = {key: float(value) for key, value in result.items()}
            cost_run.period_results = [
                {
                    "period": "2026",
                    "requiredTco2e": float(active_cycle.required_surrender_tco2e),
                    **{key: float(value) for key, value in result.items()},
                }
            ]
            cost_run.completed_at = datetime(2026, 8, 23, 12, tzinfo=UTC)
        await self.session.commit()
        return len(instruments), len(lots), len(scenario_specs)

    async def _budgets(self, runs: dict[int, GhgCalculationRun]) -> None:
        for year in (2024, 2025, 2026):
            code = f"DEMO-PARK-BUDGET-{year}"
            plan = await self.session.scalar(
                select(m.EnergyCarbonBudgetPlan).where(m.EnergyCarbonBudgetPlan.code == code)
            )
            if plan is not None:
                continue
            actual_tco2e = Decimal(runs[year].total_co2e_kg or 0) / Decimal(1000)
            months = 12 if year < 2026 else 8
            annualized = actual_tco2e if year < 2026 else actual_tco2e / Decimal(8) * Decimal(12)
            carbon_budget = (annualized * (Decimal("1.03") if year == 2024 else Decimal("0.96"))).quantize(
                Decimal("0.001")
            )
            plan = m.EnergyCarbonBudgetPlan(
                code=code,
                name=f"{year}年度园区能碳预算",
                budget_year=year,
                period_type="annual",
                period_start=date(year, 1, 1),
                period_end=date(year, 12, 31),
                target_scope="enterprise",
                target_code="DEMO-PARK-ORG",
                target_name="华东综合能源示范园区运营主体",
                energy_budget_tce=Decimal(2950) * Decimal(str(1 - (year - 2024) * 0.025)),
                carbon_budget_co2e=carbon_budget,
                denominator_plan=Decimal(1280000) * Decimal(str(1 + (year - 2024) * 0.045)),
                denominator_unit="t",
                carbon_intensity_budget=carbon_budget / (Decimal(1280000) * Decimal(str(1 + (year - 2024) * 0.045))),
                status="active",
                source_name=SOURCE_NAME,
                standard_code="企业年度经营计划",
                confidence_level="high" if year < 2026 else "medium",
                remark="2026预算为全年预算，实际数据截至8月。",
            )
            self.session.add(plan)
            await self.session.flush()
            for month in range(1, 13):
                weight = self._seasonal_weight(month)
                self.session.add(
                    m.EnergyCarbonBudgetAllocation(
                        plan_id=plan.id,
                        period_month=date(year, month, 1),
                        target_scope="enterprise",
                        target_code="DEMO-PARK-ORG",
                        target_name="华东综合能源示范园区运营主体",
                        energy_budget_tce=(Decimal(plan.energy_budget_tce or 0) * weight).quantize(Decimal("0.001")),
                        carbon_budget_co2e=(carbon_budget * weight).quantize(Decimal("0.001")),
                        denominator_budget=(Decimal(plan.denominator_plan or 0) / Decimal(12)).quantize(
                            Decimal("0.001")
                        ),
                        denominator_unit="t",
                        status="active" if month <= months else "planned",
                        source_name=SOURCE_NAME,
                        standard_code="企业年度经营计划",
                        confidence_level="high" if year < 2026 or month <= 8 else "medium",
                    )
                )
        await self.session.commit()

    async def verify(self) -> ShowcaseCoverage:
        activities = list(
            (
                await self.session.scalars(
                    select(GhgActivityRecord).where(GhgActivityRecord.inventory_code.startswith("DEMO-PARK-INV-"))
                )
            ).all()
        )
        month_counts = {
            year: len({item.period_start.month for item in activities if item.period_start.year == year})
            for year in (2024, 2025, 2026)
        }
        activity_ids = [item.id for item in activities]
        allocation_sums: dict[int, Decimal] = {}
        if activity_ids:
            allocation_rows = (
                await self.session.execute(
                    select(GhgActivityAllocation.activity_id, func.sum(GhgActivityAllocation.allocation_ratio))
                    .where(GhgActivityAllocation.activity_id.in_(activity_ids))
                    .group_by(GhgActivityAllocation.activity_id)
                )
            ).all()
            allocation_sums = {int(activity_id): Decimal(str(total)) for activity_id, total in allocation_rows}
        linked_records = set(
            (
                await self.session.scalars(
                    select(GhgEvidenceLink.record_code).where(
                        GhgEvidenceLink.record_type == "activity",
                        GhgEvidenceLink.record_code.startswith("DEMO-PARK-"),
                    )
                )
            ).all()
        )
        categories = {item.iso_category_code.split(".", 1)[0] for item in activities}
        scopes = {item.ghg_scope for item in activities}
        microgrid_site = await self.session.scalar(
            select(m.MicrogridSite).where(m.MicrogridSite.code == SHOWCASE_TENANT_SLUG)
        )
        microgrid_site_id = microgrid_site.id if microgrid_site is not None else -1
        counts = {
            "activities": len(activities),
            "areas": int(await self.session.scalar(select(func.count(m.MonitorSector.id))) or 0),
            "equipment": int(await self.session.scalar(select(func.count(m.MonitorEquipment.id))) or 0),
            "runs": int(
                await self.session.scalar(
                    select(func.count(GhgCalculationRun.id)).where(
                        GhgCalculationRun.inventory_code.startswith("DEMO-PARK-INV-")
                    )
                )
                or 0
            ),
            "reports": int(
                await self.session.scalar(
                    select(func.count(GhgInventoryReport.id)).where(
                        GhgInventoryReport.inventory_code.startswith("DEMO-PARK-INV-")
                    )
                )
                or 0
            ),
            "evidenceLinks": len(linked_records),
            "reductionProjects": int(
                await self.session.scalar(
                    select(func.count(reduction_m.ReductionProject.id)).where(
                        reduction_m.ReductionProject.code.startswith("DEMO-PARK-")
                    )
                )
                or 0
            ),
            "climatePrograms": int(
                await self.session.scalar(
                    select(func.count(m.ClimateProgram.id)).where(m.ClimateProgram.code.startswith("DEMO-PARK-"))
                )
                or 0
            ),
            "carbonAssetInstruments": int(
                await self.session.scalar(select(func.count(m.CarbonAssetInstrument.id))) or 0
            ),
            "carbonAssetAccounts": int(await self.session.scalar(select(func.count(m.CarbonAssetAccount.id))) or 0),
            "carbonAssetLots": int(await self.session.scalar(select(func.count(m.CarbonAssetLot.id))) or 0),
            "carbonAssetMovements": int(await self.session.scalar(select(func.count(m.CarbonAssetMovement.id))) or 0),
            "carbonAssetRules": int(
                await self.session.scalar(select(func.count(m.CarbonComplianceRuleVersion.id))) or 0
            ),
            "carbonAssetCycles": int(await self.session.scalar(select(func.count(m.CarbonComplianceCycle.id))) or 0),
            "carbonAssetSettlements": int(
                await self.session.scalar(select(func.count(m.CarbonComplianceSettlement.id))) or 0
            ),
            "carbonAssetUsages": int(await self.session.scalar(select(func.count(m.EnvironmentalAssetUsage.id))) or 0),
            "carbonAssetQuotes": int(await self.session.scalar(select(func.count(m.CarbonMarketQuote.id))) or 0),
            "publicMarketQuotes": int(
                await self.session.scalar(
                    select(func.count(m.CarbonMarketQuote.id)).where(
                        m.CarbonMarketQuote.source_kind == "observed",
                        m.CarbonMarketQuote.source_name.in_({spec.source_name for spec in PUBLIC_MARKET_QUOTES}),
                        m.CarbonMarketQuote.source_url.is_not(None),
                    )
                )
                or 0
            ),
            "generatedMarketQuotes": int(
                await self.session.scalar(
                    select(func.count(m.CarbonMarketQuote.id)).where(
                        m.CarbonMarketQuote.source_name == "企业预算价格曲线"
                    )
                )
                or 0
            ),
            "carbonCostScenarios": int(await self.session.scalar(select(func.count(m.CarbonCostScenario.id))) or 0),
            "carbonCostRuns": int(await self.session.scalar(select(func.count(m.CarbonCostRun.id))) or 0),
            "microgridSites": int(microgrid_site is not None),
            "microgridAssets": int(
                await self.session.scalar(
                    select(func.count(m.MicrogridAsset.id)).where(m.MicrogridAsset.site_id == microgrid_site_id)
                )
                or 0
            ),
            "microgridBindings": int(
                await self.session.scalar(
                    select(func.count(m.MicrogridAssetMeterBinding.id)).where(
                        m.MicrogridAssetMeterBinding.site_id == microgrid_site_id,
                        m.MicrogridAssetMeterBinding.enabled.is_(True),
                    )
                )
                or 0
            ),
            "forecastRuns": int(
                await self.session.scalar(
                    select(func.count(m.ForecastRun.id)).where(
                        m.ForecastRun.site_id == microgrid_site_id,
                        m.ForecastRun.status == "completed",
                    )
                )
                or 0
            ),
            "optimizationRuns": int(
                await self.session.scalar(
                    select(func.count(m.OptimizationRun.id)).where(
                        m.OptimizationRun.site_id == microgrid_site_id,
                        m.OptimizationRun.status.in_(("optimal", "feasible")),
                    )
                )
                or 0
            ),
            "dispatchBatches": int(
                await self.session.scalar(
                    select(func.count(m.DispatchBatch.id))
                    .join(m.OptimizationRun, m.OptimizationRun.id == m.DispatchBatch.optimization_run_id)
                    .where(
                        m.OptimizationRun.site_id == microgrid_site_id,
                        m.DispatchBatch.status == "completed",
                    )
                )
                or 0
            ),
        }
        checks = {
            "complete_2024": month_counts[2024] == 12,
            "complete_2025": month_counts[2025] == 12,
            "ytd_2026_through_august": month_counts[2026] == 8,
            "all_scopes": scopes == {"scope1", "scope2", "scope3"},
            "all_iso_major_categories": categories == {"1", "2", "3", "4", "5", "6"},
            "all_activities_allocated": len(allocation_sums) == len(activities)
            and all(abs(value - Decimal(1)) <= Decimal("0.000001") for value in allocation_sums.values()),
            "all_activities_have_evidence": len(linked_records) == len(activities),
            "annual_calculation_runs": counts["runs"] >= 3,
            "report_lifecycle": counts["reports"] >= 4,
            "reduction_workbench": counts["reductionProjects"] >= 5,
            "climate_governance": counts["climatePrograms"] == 3,
            "carbon_asset_reference": counts["carbonAssetInstruments"] == 3
            and counts["carbonAssetAccounts"] == 3
            and counts["carbonAssetRules"] >= 2,
            "carbon_asset_ledger": counts["carbonAssetLots"] >= 3
            and counts["carbonAssetMovements"] >= 2
            and counts["carbonAssetUsages"] >= 1,
            "carbon_asset_compliance": counts["carbonAssetCycles"] >= 2 and counts["carbonAssetSettlements"] >= 1,
            "carbon_asset_market_and_cost": counts["publicMarketQuotes"] >= len(PUBLIC_MARKET_QUOTES)
            and counts["generatedMarketQuotes"] == 0
            and counts["carbonCostScenarios"] >= 3
            and counts["carbonCostRuns"] >= 3,
            "resource_granularity": counts["areas"] >= 10 and counts["equipment"] >= 19,
            "microgrid_operations": counts["microgridSites"] == 1
            and counts["microgridAssets"] >= 6
            and counts["microgridBindings"] >= 10,
            "microgrid_forecast_optimization": counts["forecastRuns"] >= 1 and counts["optimizationRuns"] >= 1,
            "microgrid_simulated_dispatch": counts["dispatchBatches"] >= 1,
        }
        return ShowcaseCoverage(passed=all(checks.values()), checks=checks, counts=counts)

    @staticmethod
    def _monthly_amount(spec: ActivitySeriesSpec, *, year: int, month: int) -> Decimal:
        trend = {2024: Decimal("1.00"), 2025: Decimal("1.045"), 2026: Decimal("1.075")}[year]
        seasonal = Decimal(str(1 + 0.12 * sin(2 * pi * (month - 1) / 12)))
        if spec.code in {"C14-REFRIGERANT", "C21-ELECTRICITY", "C22-STEAM", "C54-LEASED"}:
            seasonal *= Decimal(str(1 + 0.16 * abs(sin(2 * pi * (month - 2) / 12))))
        deterministic = Decimal(1) + Decimal(((year + month + sum(map(ord, spec.code))) % 7) - 3) / Decimal(100)
        return (spec.base_amount * trend * seasonal * deterministic).quantize(Decimal("0.001"))

    @staticmethod
    def _seasonal_weight(month: int) -> Decimal:
        raw = [
            Decimal("0.078"),
            Decimal("0.073"),
            Decimal("0.079"),
            Decimal("0.080"),
            Decimal("0.082"),
            Decimal("0.088"),
            Decimal("0.096"),
            Decimal("0.098"),
            Decimal("0.087"),
            Decimal("0.083"),
            Decimal("0.079"),
            Decimal("0.077"),
        ]
        return raw[month - 1]

    @staticmethod
    def _national_category(spec: ActivitySeriesSpec) -> str:
        return {
            "1": "直接温室气体排放",
            "2": "能源间接温室气体排放",
            "3": "运输产生的间接温室气体排放",
            "4": "组织使用产品产生的间接温室气体排放",
            "5": "与组织产品使用相关的间接温室气体排放",
            "6": "其他来源的间接温室气体排放",
        }[spec.iso_category.split(".", 1)[0]]

    @staticmethod
    def _factor_source(spec: ActivitySeriesSpec) -> str:
        if spec.code == "C21-ELECTRICITY":
            return "生态环境部2023年全国电力平均二氧化碳排放因子（演示冻结值）"
        if spec.code == "C14-REFRIGERANT":
            return "IPCC AR5 GWP100（演示冻结值）"
        if spec.code in {"C11-GAS", "C12-DIESEL"}:
            return "国家温室气体核算指南与企业燃料台账（演示冻结值）"
        return f"企业批准的{spec.name}排放因子（演示假设）"

    @staticmethod
    def _factor_standard(spec: ActivitySeriesSpec) -> str:
        if spec.code == "C21-ELECTRICITY":
            return "生态环境部电力排放因子公告"
        if spec.code == "C14-REFRIGERANT":
            return "IPCC AR5"
        return "ISO 14064-1:2018; GHG Protocol"

    @staticmethod
    def _evidence_content(*, rows: list[GhgActivityRecord]) -> bytes:
        lines = ["record_code,period_start,period_end,activity_name,amount,unit,quality_status"]
        lines.extend(
            f"{row.record_code},{row.period_start},{row.period_end},{row.activity_name},{row.activity_amount},{row.activity_unit},{row.quality_status}"
            for row in rows
        )
        return ("\n".join(lines) + "\n").encode("utf-8")
