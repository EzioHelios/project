"""Idempotent tenant data completion for the first warehouse inventory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Integer, func, select

from app.domain.carbon import models as m
from app.domain.ghg_inventory.models import (
    GhgActivityAllocation,
    GhgActivityRecord,
    GhgCalculationRun,
    GhgEmissionSource,
    GhgInventoryReport,
    GhgInventoryReportReview,
    GhgParameterValue,
)
from app.domain.ghg_inventory.usecases.allocations import ReplaceActivityAllocations
from app.domain.ghg_inventory.usecases.calculation import RunInventoryCalculation
from app.domain.metering.models import MeasurementBoundary, MeasurementBoundaryMember
from app.lib.demo_tenancy import require_demo_tenant

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class TenantInventoryCompletionResult:
    reporting_periods: int
    boundaries: int
    devices: int
    measurement_boundaries: int
    emission_sources: int
    activities: int
    allocations: int
    parameter_values: int
    calculation_runs: int
    inventory_reports: int


class CompleteWarehouseTenantInventory:
    """Complete organization-boundary and resource attribution for existing warehouse activities."""

    SOURCE_NAME = "组织温室气体区域设备归集与计算初始化V2"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self) -> TenantInventoryCompletionResult:
        await require_demo_tenant(self.session)
        root = await self._get_required_area("ROOT")
        areas = {row.code: row for row in (await self.session.scalars(select(m.MonitorSector))).all()}
        organization = await self._get_or_create_organization()
        periods = {
            year: await self._get_or_create_period(organization, year)
            for year in sorted(
                set(
                    (
                        await self.session.scalars(
                            select(func.extract("year", GhgActivityRecord.period_start).cast(Integer)).distinct()
                        )
                    ).all()
                )
            )
        }
        boundaries = {
            year: await self._get_or_create_boundary(organization, period, root) for year, period in periods.items()
        }
        devices = await self._ensure_carbon_source_devices(areas)
        measurement_boundary = await self._ensure_electricity_boundary(root)
        activities = list((await self.session.scalars(select(GhgActivityRecord).order_by(GhgActivityRecord.id))).all())
        allocation_use_case = ReplaceActivityAllocations(self.session)
        for activity in activities:
            year = activity.period_start.year
            period = periods[year]
            boundary = boundaries[year]
            activity.reporting_period_id = period.id
            activity.organization_boundary_id = boundary.id
            activity.organization_code = organization.code
            activity.facility_code = root.code
            await self.session.flush()
            await allocation_use_case.execute(
                inventory_code=activity.inventory_code,
                record_code=activity.record_code,
                allocations=self._allocation_payload(
                    activity,
                    areas=areas,
                    devices=devices,
                    measurement_boundary=measurement_boundary,
                ),
                commit=False,
            )
        await self._ensure_calculation_parameters(activities)
        await self.session.commit()
        calculation_runs = await self._ensure_calculation_runs(activities, periods)
        inventory_reports = await self._ensure_inventory_reports()
        return TenantInventoryCompletionResult(
            reporting_periods=len(periods),
            boundaries=len(boundaries),
            devices=len(devices),
            measurement_boundaries=1,
            emission_sources=int(await self.session.scalar(select(func.count()).select_from(GhgEmissionSource)) or 0),
            activities=len(activities),
            allocations=int(await self.session.scalar(select(func.count()).select_from(GhgActivityAllocation)) or 0),
            parameter_values=int(await self.session.scalar(select(func.count()).select_from(GhgParameterValue)) or 0),
            calculation_runs=calculation_runs,
            inventory_reports=inventory_reports,
        )

    async def _ensure_inventory_reports(self) -> int:
        runs = list(
            (
                await self.session.scalars(
                    select(GhgCalculationRun)
                    .where(GhgCalculationRun.status == "completed")
                    .order_by(GhgCalculationRun.completed_at, GhgCalculationRun.id)
                )
            ).all()
        )
        for run in runs:
            if not run.reporting_org_id or not run.reporting_period_id or not run.organization_boundary_id:
                continue
            period = await self.session.get(m.ReportingPeriod, run.reporting_period_id)
            if period is None:
                continue
            report_code = f"WAREHOUSE-GHG-{period.period_end.year}"
            report = await self.session.scalar(
                select(GhgInventoryReport).where(
                    GhgInventoryReport.report_code == report_code,
                    GhgInventoryReport.status == "published",
                )
            )
            if report is not None:
                continue
            report = GhgInventoryReport(
                report_code=report_code,
                version=1,
                title=f"{period.period_end.year}年度组织温室气体盘查报告",
                inventory_code=run.inventory_code,
                run_id=run.id,
                reporting_org_id=run.reporting_org_id,
                reporting_period_id=run.reporting_period_id,
                organization_boundary_id=run.organization_boundary_id,
                reporting_profile_id=run.reporting_profile_id,
                status="published",
                content_snapshot={"tenantDatasetSource": self.SOURCE_NAME},
                metrics_snapshot=dict(run.summary_snapshot or {}),
                evidence_snapshot=dict(run.quality_snapshot or {}),
                change_summary="租户完整组织温室气体盘查数据集",
                submitted_by="system_dataset",
                submitted_at=datetime.now().astimezone(),
                approved_by="system_dataset",
                approved_at=datetime.now().astimezone(),
                published_at=datetime.now().astimezone(),
            )
            self.session.add(report)
            await self.session.flush()
            self.session.add(
                GhgInventoryReportReview(
                    report_id=report.id,
                    action="published",
                    from_status="approved",
                    to_status="published",
                    actor="system_dataset",
                    comment=self.SOURCE_NAME,
                    acted_at=datetime.now().astimezone(),
                )
            )
        await self.session.commit()
        return int(await self.session.scalar(select(func.count()).select_from(GhgInventoryReport)) or 0)

    async def _ensure_calculation_parameters(self, activities: list[GhgActivityRecord]) -> None:
        factors = {
            row.sub_category: row
            for row in (
                await self.session.scalars(
                    select(m.EmissionFactor).where(m.EmissionFactor.is_active.is_(True)).order_by(m.EmissionFactor.year)
                )
            ).all()
        }
        for activity in activities:
            parameter = self._parameter_spec(activity, factors)
            method_code, parameter_code, parameter_name, factor, source_payload = parameter
            parameter_set_code = f"{activity.record_code}-PS1"
            value_code = f"{activity.inventory_code}:{parameter_set_code}:{parameter_code}"
            activity.parameter_set_code = parameter_set_code
            activity.source_payload = {
                **dict(activity.source_payload or {}),
                **source_payload,
                "method_code": method_code,
                "gas_code": "CO2e",
            }
            value = await self.session.scalar(
                select(GhgParameterValue).where(
                    GhgParameterValue.value_code == value_code, GhgParameterValue.version == 1
                )
            )
            if value is None:
                value = GhgParameterValue(value_code=value_code, version=1)
                self.session.add(value)
            value.parameter_code = parameter_code
            value.parameter_name = parameter_name
            value.parameter_role = "emission_factor"
            value.value = factor["value"]
            value.unit = factor["unit"]
            value.source_mode = factor["source_mode"]
            value.source_name = factor["source_name"]
            value.source_version = factor.get("source_version")
            value.standard_code = factor.get("standard_code")
            value.clause_reference = factor.get("clause_reference")
            value.reference_year = factor.get("reference_year")
            value.geography = factor.get("geography")
            value.fuel_or_material = factor.get("material")
            value.quality_grade = factor.get("quality_grade", "B")
            value.approval_status = "approved"
            value.status = "active"
        await self.session.flush()

    def _parameter_spec(  # noqa: PLR0911 - each supported category has an explicit parameter mapping
        self,
        activity: GhgActivityRecord,
        factors: dict[str, m.EmissionFactor],
    ) -> tuple[str, str, str, dict[str, Any], dict[str, Any]]:
        category = activity.iso_category_code
        if category == "1.1":
            material = str(
                activity.source_payload.get("fuel_type")
                or ("natural_gas" if activity.activity_unit == "m³" else "diesel")
            )
            return self._published_factor_spec(activity, factors, material, "F02_EF", "EMISSION_FACTOR", "排放因子")
        if category == "1.2":
            material = str(activity.source_payload.get("fuel_type") or "diesel")
            return self._published_factor_spec(activity, factors, material, "F02_EF", "EMISSION_FACTOR", "排放因子")
        if category == "1.4":
            material = str(activity.source_payload.get("refrigerant_type") or "r410a")
            assumption = material not in factors
            factor_spec = self._factor_payload(factors["r410a"], material_override=material)
            if assumption:
                factor_spec.update(
                    source_mode="custom_approved",
                    source_name="企业制冷剂替代参数(未知工质按R410A)",
                    quality_grade="C",
                )
            return "F02_EF", "EMISSION_FACTOR", "制冷剂排放因子", factor_spec, {"refrigerant_type": material}
        if category == "2.1":
            return self._published_factor_spec(
                activity,
                factors,
                "grid_electricity_jiangsu",
                "F08_PURCHASED_ENERGY",
                "ENERGY_FACTOR",
                "购入电力排放因子",
                payload={"scope2_method": "location"},
            )
        if category == "2.2":
            factor_value = Decimal(str(activity.source_payload.get("factor_value") or 120))
            return (
                "F08_PURCHASED_ENERGY",
                "ENERGY_FACTOR",
                "购入蒸汽排放因子",
                {
                    "value": factor_value,
                    "unit": str(activity.source_payload.get("factor_unit") or "kgCO2e/t"),
                    "source_mode": "custom_approved",
                    "source_name": str(activity.source_payload.get("factor_source") or "企业批准蒸汽排放因子"),
                    "source_version": str(activity.source_payload.get("factor_year") or "2026"),
                    "standard_code": activity.source_payload.get("standard_code"),
                    "reference_year": int(activity.source_payload.get("factor_year") or 2026),
                    "geography": "企业供应商",
                    "material": "purchased_steam",
                    "quality_grade": "C",
                },
                {"scope2_method": "location", "energy_type": "purchased_steam"},
            )
        if category == "3.1":
            material = str(activity.source_payload.get("vehicle_type") or "transport_heavy_truck")
            payload = {
                "origin": activity.source_payload.get("origin"),
                "destination": activity.source_payload.get("destination"),
                "vehicle_type": material,
            }
            return self._published_factor_spec(
                activity,
                factors,
                material,
                "F09_TRANSPORT_ACTIVITY",
                "TRANSPORT_FACTOR",
                "运输活动排放因子",
                payload=payload,
            )
        if category == "4.4":
            material = str(activity.source_payload.get("waste_type") or "waste_municipal_incineration")
            assumption = material not in factors
            factor_spec = self._factor_payload(factors["waste_municipal_incineration"], material_override=material)
            if assumption:
                factor_spec.update(
                    source_mode="custom_approved",
                    source_name="企业废弃物替代参数(未分类废弃物按生活垃圾焚烧)",
                    quality_grade="C",
                )
            return "F02_EF", "EMISSION_FACTOR", "废弃物处理排放因子", factor_spec, {"waste_type": material}
        msg = f"活动 {activity.record_code} 的分类 {category} 尚未配置租户参数迁移规则"
        raise ValueError(msg)

    def _published_factor_spec(
        self,
        activity: GhgActivityRecord,
        factors: dict[str, m.EmissionFactor],
        material: str,
        method_code: str,
        parameter_code: str,
        parameter_name: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> tuple[str, str, str, dict[str, Any], dict[str, Any]]:
        factor = factors.get(material)
        if factor is None:
            msg = f"活动 {activity.record_code} 缺少 {material} 的有效排放因子"
            raise ValueError(msg)
        return method_code, parameter_code, parameter_name, self._factor_payload(factor), payload or {}

    @staticmethod
    def _factor_payload(factor: m.EmissionFactor, *, material_override: str | None = None) -> dict[str, Any]:
        return {
            "value": factor.factor_value,
            "unit": factor.factor_unit,
            "source_mode": "authority_published" if "NCSC" in factor.source or "IPCC" in factor.source else "library",
            "source_name": factor.source,
            "source_version": str(factor.year),
            "standard_code": factor.source,
            "reference_year": factor.year,
            "geography": "江苏" if "jiangsu" in factor.sub_category else "中国",
            "material": material_override or factor.sub_category,
            "quality_grade": "A" if factor.review_status == "approved" else "B",
        }

    async def _ensure_calculation_runs(
        self,
        activities: list[GhgActivityRecord],
        periods: dict[int, m.ReportingPeriod],
    ) -> int:
        inventory_years = {activity.inventory_code: activity.period_start.year for activity in activities}
        for inventory_code, year in inventory_years.items():
            completed = await self.session.scalar(
                select(GhgCalculationRun)
                .where(
                    GhgCalculationRun.inventory_code == inventory_code,
                    GhgCalculationRun.status == "completed",
                )
                .order_by(GhgCalculationRun.completed_at.desc(), GhgCalculationRun.id.desc())
            )
            if completed is not None and completed.input_snapshot.get("tenantDatasetSource") == self.SOURCE_NAME:
                continue
            run = await RunInventoryCalculation(self.session).execute(
                inventory_code=inventory_code,
                reporting_profile_code="CORPORATE_ISO14064_GHGP",
                reporting_period_id=periods[year].id,
            )
            run.input_snapshot = {**run.input_snapshot, "tenantDatasetSource": self.SOURCE_NAME}
            await self.session.commit()
        return int(
            await self.session.scalar(
                select(func.count()).select_from(GhgCalculationRun).where(GhgCalculationRun.status == "completed")
            )
            or 0
        )

    async def _get_required_area(self, code: str) -> m.MonitorSector:
        area = await self.session.scalar(select(m.MonitorSector).where(m.MonitorSector.code == code))
        if area is None:
            msg = f"租户缺少必需区域 {code}"
            raise ValueError(msg)
        return area

    async def _get_or_create_organization(self) -> m.ReportingOrganization:
        organization = await self.session.scalar(select(m.ReportingOrganization).order_by(m.ReportingOrganization.id))
        if organization is not None:
            return organization
        organization = m.ReportingOrganization(
            code="WAREHOUSE-ORG",
            name="仓储运营温室气体盘查主体",
            organization_type="enterprise",
            control_method="operational_control",
            status="active",
            source_name=self.SOURCE_NAME,
            standard_code="ISO 14064-1:2018; GHG Protocol Corporate Standard",
        )
        self.session.add(organization)
        await self.session.flush()
        return organization

    async def _get_or_create_period(self, organization: m.ReportingOrganization, year: int) -> m.ReportingPeriod:
        period = await self.session.scalar(
            select(m.ReportingPeriod).where(
                m.ReportingPeriod.reporting_org_id == organization.id,
                m.ReportingPeriod.period_start == date(year, 1, 1),
                m.ReportingPeriod.period_end == date(year, 12, 31),
            )
        )
        if period is not None:
            return period
        period = m.ReportingPeriod(
            reporting_org_id=organization.id,
            code=f"WAREHOUSE-RP-{year}",
            name=f"{year}年度组织温室气体盘查",
            period_type="annual",
            period_start=date(year, 1, 1),
            period_end=date(year, 12, 31),
            status="draft",
            source_name=self.SOURCE_NAME,
            standard_code="ISO 14064-1:2018",
        )
        self.session.add(period)
        await self.session.flush()
        return period

    async def _get_or_create_boundary(
        self,
        organization: m.ReportingOrganization,
        period: m.ReportingPeriod,
        root: m.MonitorSector,
    ) -> m.OrganizationBoundary:
        existing = await self.session.scalar(
            select(m.OrganizationBoundary)
            .join(m.BoundaryFacility, m.BoundaryFacility.boundary_id == m.OrganizationBoundary.id)
            .where(
                m.OrganizationBoundary.reporting_org_id == organization.id,
                m.OrganizationBoundary.period_id == period.id,
                m.OrganizationBoundary.status == "published",
                m.BoundaryFacility.area_id == root.id,
                m.BoundaryFacility.included.is_(True),
            )
            .order_by(m.OrganizationBoundary.version.desc())
        )
        if existing is not None:
            return existing
        previous = list(
            (
                await self.session.scalars(
                    select(m.OrganizationBoundary).where(
                        m.OrganizationBoundary.reporting_org_id == organization.id,
                        m.OrganizationBoundary.period_id == period.id,
                    )
                )
            ).all()
        )
        version = max((item.version for item in previous), default=0) + 1
        for item in previous:
            if item.status == "published":
                item.status = "superseded"
        boundary = m.OrganizationBoundary(
            reporting_org_id=organization.id,
            period_id=period.id,
            boundary_no=f"WAREHOUSE-BND-{period.period_start.year}-V{version}",
            boundary_name=f"{period.period_start.year}年度仓储运营组织边界",
            boundary_type="organization",
            boundary_method="operational_control",
            operational_boundary={
                "schemaVersion": "organization-boundary-v1",
                "scopes": ["scope1", "scope2", "scope3"],
                "scope2Methods": ["location", "market"],
                "isoCategories": ["1", "2", "3", "4", "5", "6"],
                "scope3Categories": [],
                "resourceBinding": "area_equipment_allocation",
            },
            version=version,
            status="published",
            published_at=datetime.now().astimezone().replace(tzinfo=None),
            source_name=self.SOURCE_NAME,
            standard_code="ISO 14064-1:2018; GHG Protocol Corporate Standard",
            confidence_level="high",
        )
        self.session.add(boundary)
        await self.session.flush()
        self.session.add(
            m.BoundaryFacility(
                boundary_id=boundary.id,
                facility_type="area",
                area_id=root.id,
                facility_code=root.code,
                facility_name=root.name or root.code,
                facility_role="reporting_site_root",
                included=True,
                valid_from=period.period_start,
                valid_to=period.period_end,
                source_name=self.SOURCE_NAME,
            )
        )
        await self.session.flush()
        return boundary

    async def _ensure_carbon_source_devices(self, areas: dict[str, m.MonitorSector]) -> dict[str, m.MonitorEquipment]:
        types = {row.code: row for row in (await self.session.scalars(select(m.DeviceType))).all()}
        existing = {row.code: row for row in (await self.session.scalars(select(m.MonitorEquipment))).all()}
        specs: list[tuple[str, str, str, m.DeviceType | None]] = [
            ("XT-CANTEEN-GAS-METER", "食堂天然气表", "OFFICE", types.get("meter")),
            ("XT-BACKUP-GENSET-01", "备用发电机组", "ROOT", types.get("automation_equipment")),
        ]
        specs.extend(
            (f"XT-FORKLIFT-{index:02d}", f"仓储燃油叉车{index}号", "P6", types.get("forklift")) for index in range(1, 7)
        )
        specs.extend(
            (
                f"XT-REFRIGERATION-{index:02d}",
                f"仓储制冷机组{index}号",
                "WH1_A01",
                types.get("automation_equipment"),
            )
            for index in range(1, 7)
        )
        for code, name, area_code, device_type in specs:
            if code in existing:
                continue
            area = areas.get(area_code)
            if area is None:
                msg = f"租户缺少设备归属区域 {area_code}"
                raise ValueError(msg)
            device = m.MonitorEquipment(
                code=code,
                name=name,
                device_type_id=device_type.id if device_type else None,
                sector_id=area.id,
                asset_code=code,
                owner_unit="仓储运营主体",
                data_acquisition_method="台账",
                commissioning_status="active",
                location=area.name,
                remark=self.SOURCE_NAME,
                is_enable=True,
                protocol="manual",
            )
            self.session.add(device)
            existing[code] = device
        await self.session.flush()
        return existing

    async def _ensure_electricity_boundary(self, root: m.MonitorSector) -> MeasurementBoundary:
        boundary = await self.session.scalar(
            select(MeasurementBoundary).where(MeasurementBoundary.code == "XT-SITE-ELECTRICITY")
        )
        if boundary is None:
            boundary = MeasurementBoundary(
                code="XT-SITE-ELECTRICITY",
                name="仓储园区购入电力计量边界",
                boundary_type="area_aggregate",
                sector_id=root.id,
                energy_direction="import",
                include_in_scope2=True,
                valid_from=date(2025, 1, 1),
                status="active",
                mapping_version="v1",
                source_name=self.SOURCE_NAME,
                confidence_level="medium",
                remark="无单一PCC总表时按已确认电表边界汇总",
            )
            self.session.add(boundary)
            await self.session.flush()
        electricity_devices = list(
            (
                await self.session.scalars(
                    select(m.MonitorEquipment).where(
                        m.MonitorEquipment.code.op("~")(r"^[0-9]+$"),
                        m.MonitorEquipment.category == 0,
                    )
                )
            ).all()
        )
        existing_members = {
            row.member_code
            for row in (
                await self.session.scalars(
                    select(MeasurementBoundaryMember).where(MeasurementBoundaryMember.boundary_id == boundary.id)
                )
            ).all()
        }
        for device in electricity_devices:
            member_code = f"METER-{device.code}"
            if member_code in existing_members:
                continue
            self.session.add(
                MeasurementBoundaryMember(
                    boundary_id=boundary.id,
                    member_code=member_code,
                    member_type="equipment",
                    sector_id=device.sector_id,
                    equipment_id=device.id,
                    member_role="covered",
                    confirmation_status="confirmed",
                    valid_from=date(2025, 1, 1),
                    source_name=self.SOURCE_NAME,
                )
            )
        await self.session.flush()
        return boundary

    def _allocation_payload(  # noqa: PLR0911 - category routing is explicit business policy
        self,
        activity: GhgActivityRecord,
        *,
        areas: dict[str, m.MonitorSector],
        devices: dict[str, m.MonitorEquipment],
        measurement_boundary: MeasurementBoundary,
    ) -> list[dict[str, Any]]:
        category = activity.iso_category_code
        suffix = _source_suffix(activity.source_code)
        if category == "1.1":
            if "食堂" in activity.activity_name:
                return [self._allocation(activity, areas["OFFICE"], devices["XT-CANTEEN-GAS-METER"], "physical_origin")]
            return [self._allocation(activity, areas["ROOT"], devices["XT-BACKUP-GENSET-01"], "physical_origin")]
        if category == "1.2":
            device = devices[f"XT-FORKLIFT-{((suffix - 1) % 6) + 1:02d}"]
            return [self._allocation(activity, areas["P6"], device, "asset_location")]
        if category == "1.4":
            device = devices[f"XT-REFRIGERATION-{((suffix - 1) % 6) + 1:02d}"]
            return [self._allocation(activity, areas["WH1_A01"], device, "physical_origin")]
        if category == "2.1":
            return [
                self._allocation(
                    activity,
                    areas["ROOT"],
                    None,
                    "energy_consumption",
                    measurement_boundary_id=measurement_boundary.id,
                )
            ]
        if category == "2.2":
            return [self._allocation(activity, areas["WH1"], None, "energy_consumption")]
        if category == "3.1":
            payload = dict(activity.source_payload or {})
            return [
                self._allocation(
                    activity,
                    areas["WH2"],
                    None,
                    "responsibility",
                    external_facility_code=str(payload.get("destination") or activity.source_code),
                    external_facility_name=str(payload.get("carrier") or payload.get("destination") or "外部物流节点"),
                )
            ]
        if category == "4.4":
            return [
                self._allocation(activity, areas["WH1"], None, "waste_generation", ratio=Decimal("0.5"), index=1),
                self._allocation(activity, areas["WH2"], None, "waste_generation", ratio=Decimal("0.5"), index=2),
            ]
        return [self._allocation(activity, areas["ROOT"], None, "organization_root")]

    @staticmethod
    def _allocation(
        activity: GhgActivityRecord,
        area: m.MonitorSector,
        equipment: m.MonitorEquipment | None,
        role: str,
        *,
        ratio: Decimal = Decimal(1),
        index: int = 1,
        measurement_boundary_id: int | None = None,
        external_facility_code: str | None = None,
        external_facility_name: str | None = None,
    ) -> dict[str, Any]:
        return {
            "allocation_code": f"{activity.record_code}-A{index:02d}",
            "area_id": area.id,
            "equipment_id": equipment.id if equipment else None,
            "measurement_boundary_id": measurement_boundary_id,
            "allocation_role": role,
            "allocation_ratio": ratio,
            "external_facility_code": external_facility_code,
            "external_facility_name": external_facility_name,
            "source_kind": "migration",
            "valid_from": activity.period_start,
            "valid_to": activity.period_end,
        }


def _source_suffix(code: str) -> int:
    try:
        return int(code.rsplit("-", 1)[-1])
    except ValueError:
        return 1
