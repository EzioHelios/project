"""Create and validate the exact monthly boundary used by the enterprise demo."""

from __future__ import annotations

# ruff: noqa: RUF001 - Chinese business validation messages.
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.db import models as m
from app.domain.ghg_inventory.queries.analytics import GhgAnalyticsQueryService
from app.domain.organization_boundary.schemas import (
    BoundaryAreaSelection,
    BoundaryEquipmentSelection,
    OperationalBoundarySelection,
    SaveBoundarySelectionRequest,
)
from app.domain.organization_boundary.usecases.boundary import OrganizationBoundaryUseCase
from app.lib.demo_tenancy import require_demo_tenant

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.demo.ops.enterprise_entry import EntryCase


async def ensure_entry_boundary(
    session: AsyncSession,
    *,
    city: str,
    period: m.ReportingPeriod,
    cases: list[EntryCase],
) -> m.OrganizationBoundary:
    """Publish a same-period boundary using the business workbench commands."""
    from app.demo.ops.enterprise_entry import CITY_NAMES, SOURCE_NAME

    await require_demo_tenant(session)
    if period.code != f"WOHENG-{city}-ENTRY-202610" or (period.period_start, period.period_end) != (
        date(2026, 10, 1),
        date(2026, 10, 31),
    ):
        msg = "企业案例必须使用2026年10月对应报告期，不能替换为年度边界"
        raise ValueError(msg)
    published = list(
        (
            await session.scalars(
                select(m.OrganizationBoundary).where(
                    m.OrganizationBoundary.period_id == period.id,
                    m.OrganizationBoundary.reporting_org_id == period.reporting_org_id,
                    m.OrganizationBoundary.status == "published",
                    m.OrganizationBoundary.boundary_type == "organization",
                )
            )
        ).all()
    )
    if len(published) > 1:
        msg = "10月报告期存在多个已发布组织边界，请先明确版本"
        raise ValueError(msg)
    if published:
        return published[0]
    code = f"{period.code}-BOUNDARY"
    boundary = await session.scalar(select(m.OrganizationBoundary).where(m.OrganizationBoundary.boundary_no == code))
    service = OrganizationBoundaryUseCase(session)
    if boundary is None:
        boundary = await service.create_boundary(
            {
                "reporting_org_id": period.reporting_org_id,
                "period_id": period.id,
                "boundary_no": code,
                "boundary_name": f"{CITY_NAMES[city]}基地2026年10月月结核算边界",
                "boundary_type": "organization",
                "boundary_method": "operational_control",
                "status": "draft",
                "source_name": SOURCE_NAME,
                "standard_code": "DEMO-ASSUMPTION-20261115",
                "confidence_level": "demo",
                "remark": "10月合成案例采用运营控制法，纳入能源、冷媒维修、员工通勤和入厂运输对象。",
            }
        )
    if (
        boundary.status != "draft"
        or boundary.period_id != period.id
        or boundary.reporting_org_id != period.reporting_org_id
    ):
        msg = "案例边界已有不同期间、主体或版本状态，保留原配置"
        raise ValueError(msg)
    areas = {row.code: row for row in (await session.scalars(select(m.MonitorSector))).all()}
    equipment = {row.code: row for row in (await session.scalars(select(m.MonitorEquipment))).all()}
    await service.save_selection(
        boundary.id,
        SaveBoundarySelectionRequest(
            operational_boundary=OperationalBoundarySelection(
                scopes=["scope1", "scope2", "scope3"],
                scope2_methods=["location"],
                iso_categories=["1", "2", "3"],
                scope3_categories=[4, 7],
            ),
            areas=[
                BoundaryAreaSelection(area_id=areas[code].id) for code in sorted({case.area_code for case in cases})
            ],
            equipment=[
                BoundaryEquipmentSelection(
                    equipment_id=equipment[code].id,
                    area_id=equipment[code].sector_id,
                )
                for code in sorted({case.equipment_code for case in cases if case.equipment_code})
            ],
        ),
    )
    return await service.publish_boundary(boundary.id)


async def entry_boundary_readiness(
    session: AsyncSession,
    *,
    city: str,
    cases: list[EntryCase],
    activities: list[m.GhgActivityRecord],
) -> dict[str, Any]:
    """Use the UI readiness query and also verify exact period and resource coverage."""
    errors: list[str] = []
    inventory = f"WOHENG-{city}-ENTRY-202610"
    period = await session.scalar(select(m.ReportingPeriod).where(m.ReportingPeriod.code == inventory))
    if period is None or (period.period_start, period.period_end) != (date(2026, 10, 1), date(2026, 10, 31)):
        return {"ready": False, "errors": ["缺少对应2026年10月报告期"], "boundary_id": None}
    boundaries = list(
        (
            await session.scalars(
                select(m.OrganizationBoundary).where(
                    m.OrganizationBoundary.period_id == period.id,
                    m.OrganizationBoundary.reporting_org_id == period.reporting_org_id,
                    m.OrganizationBoundary.boundary_type == "organization",
                    m.OrganizationBoundary.status == "published",
                )
            )
        ).all()
    )
    if len(boundaries) != 1:
        return {"ready": False, "errors": ["10月报告期必须有唯一对应主体的已发布组织边界"], "boundary_id": None}
    boundary = boundaries[0]
    organization = await session.get(m.ReportingOrganization, period.reporting_org_id)
    if organization is None or any(row.organization_code != organization.code for row in activities):
        errors.append("案例活动与10月报告主体不一致")
    if any(row.organization_boundary_id != boundary.id or row.reporting_period_id != period.id for row in activities):
        errors.append("案例活动尚未全部绑定同一10月已发布边界及报告期")
    operational = boundary.operational_boundary or {}
    required = {
        "scopes": {"scope1", "scope2", "scope3"},
        "scope2Methods": {"location"},
        "isoCategories": {"1", "2", "3"},
        "scope3Categories": {4, 7},
    }
    if any(not values <= set(operational.get(key) or []) for key, values in required.items()):
        errors.append("10月边界未覆盖案例范围、ISO类别或地点法")
    facilities = list(
        (
            await session.scalars(
                select(m.BoundaryFacility).where(
                    m.BoundaryFacility.boundary_id == boundary.id,
                    m.BoundaryFacility.included.is_(True),
                )
            )
        ).all()
    )
    included_codes = {
        row.facility_code
        for row in facilities
        if (row.valid_from is None or row.valid_from <= period.period_start)
        and (row.valid_to is None or row.valid_to >= period.period_end)
    }
    required_codes = {case.area_code for case in cases} | {case.equipment_code for case in cases if case.equipment_code}
    if not required_codes <= included_codes:
        errors.append("10月边界缺少有效的案例区域或设备")
    readiness = await GhgAnalyticsQueryService(session).readiness(
        inventory_code=inventory,
        reporting_period_id=period.id,
        organization_boundary_id=boundary.id,
    )
    if not readiness["readyForCalculation"] or readiness["activityCount"] != len(cases):
        errors.append("页面核算就绪检查未通过或活动条数与案例不一致")
    return {"ready": not errors, "errors": errors, "boundary_id": boundary.id, "ui_readiness": readiness}


async def repair_entry_boundary_links(session: AsyncSession, *, city: str) -> dict[str, Any]:
    """Explicit upgrade: add the monthly boundary and link current activities, retaining old runs."""
    from app.demo.ops.enterprise_entry import SOURCE_SYSTEM, compare_cases, load_cases
    from app.domain.ghg_inventory.usecases.maintenance import GhgInventoryMaintenance

    await require_demo_tenant(session)
    inventory = f"WOHENG-{city}-ENTRY-202610"
    cases = load_cases(city)
    period = await session.scalar(select(m.ReportingPeriod).where(m.ReportingPeriod.code == inventory))
    if period is None:
        msg = "案例尚无10月报告期，请先安装企业案例"
        raise ValueError(msg)
    activities = list(
        (
            await session.scalars(
                select(m.GhgActivityRecord).where(
                    m.GhgActivityRecord.inventory_code == inventory,
                )
            )
        ).all()
    )
    facts = list(
        (
            await session.scalars(
                select(m.EnergyIntervalFact).where(
                    m.EnergyIntervalFact.source_system == SOURCE_SYSTEM,
                    m.EnergyIntervalFact.is_current.is_(True),
                )
            )
        ).all()
    )
    errors = compare_cases(cases, facts, activities)
    organization = await session.get(m.ReportingOrganization, period.reporting_org_id)
    if organization is None or any(
        row.reporting_period_id != period.id or row.organization_code != organization.code for row in activities
    ):
        errors.append("案例活动与10月报告主体或报告期不一致")
    if errors or any(row.status != "approved" for row in activities) or period.status in {"locked", "archived"}:
        msg = f"案例已有编辑或锁定状态，不执行边界关联修复：{errors}"
        raise ValueError(msg)
    existing_boundary_ids = {row.organization_boundary_id for row in activities if row.organization_boundary_id}
    for boundary_id in existing_boundary_ids:
        current = await session.get(m.OrganizationBoundary, boundary_id)
        if current is None or current.period_id != period.id or current.reporting_org_id != period.reporting_org_id:
            msg = "案例活动已关联其他期间或主体的边界，不自动改选"
            raise ValueError(msg)
    boundary = await ensure_entry_boundary(session, city=city, period=period, cases=cases)
    if existing_boundary_ids - {boundary.id}:
        msg = "案例活动已关联其他边界版本，不自动改选"
        raise ValueError(msg)
    fields = (
        "inventory_code",
        "reporting_period_id",
        "organization_code",
        "facility_code",
        "source_code",
        "record_code",
        "activity_code",
        "activity_name",
        "iso_category_code",
        "period_start",
        "period_end",
        "activity_amount",
        "activity_unit",
        "data_source_type",
        "measurement_method",
        "quality_status",
        "parameter_set_code",
        "source_payload",
        "remarks",
        "status",
        "source_system",
        "source_record_type",
        "source_record_id",
    )
    service = GhgInventoryMaintenance(session)
    updated = 0
    for activity in activities:
        if activity.organization_boundary_id == boundary.id:
            continue
        payload = {key: getattr(activity, key) for key in fields}
        payload["organization_boundary_id"] = boundary.id
        for key in ("period_start", "period_end", "activity_amount"):
            payload[key] = str(payload[key])
        await service.update_activity(activity.record_code, payload)
        updated += 1
    validation = await entry_boundary_readiness(session, city=city, cases=cases, activities=activities)
    if not validation["ready"]:
        msg = f"边界关联后页面仍不可核算：{validation['errors']}"
        raise ValueError(msg)
    return {**validation, "activity_links_updated": updated, "historical_runs_changed": False}
