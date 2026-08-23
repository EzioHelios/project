from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.db import models as m
from app.domain.ghg_inventory.queries.analytics import GhgAnalyticsQueryService
from app.domain.ghg_inventory.queries.result_slice import GhgAnalyticsFilter, GhgResultSliceQuery
from app.domain.organization_boundary.schemas import (
    BoundaryAreaSelection,
    BoundaryEquipmentSelection,
    OperationalBoundarySelection,
    SaveBoundarySelectionRequest,
)
from app.domain.organization_boundary.usecases.boundary import OrganizationBoundaryUseCase
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def test_result_slice_keeps_scope2_methods_separate_and_applies_attribution(session) -> None:
    team = m.Team(name="GHG Analytics Tenant", slug="ghg-analytics-tenant")
    profile = m.GhgReportingProfile(
        code="ANALYTICS-PROFILE",
        name="组织碳分析配置",
        version="1",
        standard_code="ISO 14064-1",
        standard_version="2018",
        effective_from=date(2026, 1, 1),
    )
    method = m.GhgCalculationMethodDefinition(
        code="ANALYTICS-F08",
        version="1",
        name="购入电力核算",
        formula_family="F08",
        formula_expression={"expression": "activity * factor"},
        human_formula="活动数据乘以排放因子",
        standard_code="ISO 14064-1",
        applicable_categories=["2.1"],
        effective_from=date(2026, 1, 1),
    )
    session.add_all([team, profile, method])
    await session.flush()
    session.info[TENANT_BYPASS_SESSION_KEY] = True
    area = m.MonitorSector(team_id=team.id, code="AREA-1", name="生产区", path="/AREA-1", level=0)
    organization = m.ReportingOrganization(team_id=team.id, code="ORG-1", name="测试组织")
    session.add_all([area, organization])
    await session.flush()
    period = m.ReportingPeriod(
        team_id=team.id,
        reporting_org_id=organization.id,
        code="2026",
        name="2026年度",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
    )
    session.add(period)
    await session.flush()
    boundary = m.OrganizationBoundary(
        team_id=team.id,
        reporting_org_id=organization.id,
        period_id=period.id,
        boundary_no="BOUNDARY-1",
        boundary_name="测试边界",
        operational_boundary={"scopes": ["scope2"], "scope2Methods": ["location", "market"]},
        status="published",
    )
    session.add(boundary)
    await session.flush()
    source = m.GhgEmissionSource(
        team_id=team.id,
        inventory_code="INV-2026",
        organization_boundary_id=boundary.id,
        reporting_period_id=period.id,
        organization_code=organization.code,
        facility_code=area.code,
        source_code="GRID-POWER",
        source_name="购入电力",
        iso_category_code="2.1",
        source_mechanism="energy",
        default_area_id=area.id,
    )
    session.add(source)
    await session.flush()
    activity = m.GhgActivityRecord(
        team_id=team.id,
        record_code="ACT-1",
        inventory_code="INV-2026",
        reporting_period_id=period.id,
        organization_boundary_id=boundary.id,
        emission_source_id=source.id,
        organization_code=organization.code,
        facility_code=area.code,
        source_code=source.source_code,
        activity_code="PURCHASED-ELECTRICITY",
        activity_name="购入电力",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        iso_category_code="2.1",
        ghg_scope="scope2",
        source_mechanism="energy",
        value_chain_position="upstream",
        activity_amount=Decimal(1000),
        activity_unit="kWh",
        data_source_type="measured",
        measurement_method="关口电表",
        status="approved",
    )
    session.add(activity)
    await session.flush()
    run = m.GhgCalculationRun(
        team_id=team.id,
        run_code="RUN-ANALYTICS",
        inventory_code="INV-2026",
        reporting_profile_id=profile.id,
        reporting_org_id=organization.id,
        reporting_period_id=period.id,
        organization_boundary_id=boundary.id,
        status="completed",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    session.add_all(
        [
            m.GhgCalculationResult(
                team_id=team.id,
                run_id=run.id,
                activity_id=activity.id,
                method_id=method.id,
                iso_category_code="2.1",
                ghg_scope="scope2",
                gas_code="CO2",
                gas_mass_kg=Decimal(100),
                gwp_value=Decimal(1),
                gwp_version="AR6",
                co2e_kg=Decimal(100),
                scope2_method="location",
                formula_snapshot={},
            ),
            m.GhgCalculationResult(
                team_id=team.id,
                run_id=run.id,
                activity_id=activity.id,
                method_id=method.id,
                iso_category_code="2.1",
                ghg_scope="scope2",
                gas_code="CO2",
                gas_mass_kg=Decimal(80),
                gwp_value=Decimal(1),
                gwp_version="AR6",
                co2e_kg=Decimal(80),
                scope2_method="market",
                formula_snapshot={},
            ),
            m.GhgActivityAllocation(
                team_id=team.id,
                activity_id=activity.id,
                emission_source_id=source.id,
                allocation_code="ALLOC-1",
                area_id=area.id,
                allocation_role="responsibility",
                allocation_ratio=Decimal("0.5"),
                area_code_snapshot=area.code,
                area_name_snapshot=area.name or area.code,
            ),
        ]
    )
    await session.commit()
    session.info.clear()
    session.info[TENANT_ID_SESSION_KEY] = team.id

    location = await GhgResultSliceQuery(session).execute(
        GhgAnalyticsFilter(run_code=run.run_code, scope2_method="location", area_id=area.id)
    )
    market = await GhgResultSliceQuery(session).execute(
        GhgAnalyticsFilter(run_code=run.run_code, scope2_method="market", area_id=area.id)
    )
    unfiltered = await GhgResultSliceQuery(session).execute(
        GhgAnalyticsFilter(run_code=run.run_code, scope2_method="location")
    )
    iso_group = await GhgResultSliceQuery(session).execute(
        GhgAnalyticsFilter(run_code=run.run_code, scope2_method="location", iso_category_code="2")
    )

    assert [row.result.scope2_method for row in location.rows] == ["location"]
    assert location.rows[0].attributed_co2e_kg == Decimal(50)
    assert market.rows[0].attributed_co2e_kg == Decimal(40)
    assert unfiltered.rows[0].attributed_co2e_kg == Decimal(100)
    assert iso_group.total == 1

    flow = await GhgAnalyticsQueryService(session).flow(
        run_code=run.run_code,
        classification="scope",
        scope2_method="location",
        analytics_filter=GhgAnalyticsFilter(run_code=run.run_code, scope2_method="location"),
    )
    root = next(node for node in flow["nodes"] if node["category"] == "boundary")
    root_outgoing = sum(
        (Decimal(link["value"]) for link in flow["links"] if link["source"] == root["id"]),
        Decimal(0),
    )
    assert root_outgoing == Decimal(flow["totalCo2EKg"])
    assert any(node["name"] == "未归集" and Decimal(node["value"]) == Decimal(50) for node in flow["nodes"])


async def test_boundary_working_copy_is_idempotent_and_selection_is_validated(session) -> None:
    team = m.Team(name="Boundary Tenant", slug="boundary-tenant")
    session.add(team)
    await session.flush()
    session.info[TENANT_BYPASS_SESSION_KEY] = True
    organization = m.ReportingOrganization(team_id=team.id, code="BOUNDARY-ORG", name="边界组织")
    area = m.MonitorSector(team_id=team.id, code="ROOT", name="园区", path="/ROOT", level=0)
    session.add_all([organization, area])
    await session.flush()
    equipment = m.MonitorEquipment(team_id=team.id, code="METER-1", name="总电表", sector_id=area.id)
    period = m.ReportingPeriod(
        team_id=team.id,
        reporting_org_id=organization.id,
        code="2026",
        name="2026年度",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
    )
    session.add_all([equipment, period])
    await session.flush()
    boundary = m.OrganizationBoundary(
        team_id=team.id,
        reporting_org_id=organization.id,
        period_id=period.id,
        boundary_no="BOUNDARY-V1",
        boundary_name="组织核算边界",
        operational_boundary={
            "schemaVersion": "organization-boundary-v1",
            "scopes": ["scope1", "scope2", "scope3"],
            "scope2Methods": ["location"],
            "isoCategories": ["1", "2", "3", "4", "5", "6"],
            "scope3Categories": [1],
        },
        version=1,
        status="published",
    )
    session.add(boundary)
    await session.flush()
    session.add(
        m.BoundaryFacility(
            team_id=team.id,
            boundary_id=boundary.id,
            facility_type="area",
            area_id=area.id,
            facility_code=area.code,
            facility_name=area.name,
            included=True,
        )
    )
    await session.commit()
    session.info.clear()
    session.info[TENANT_ID_SESSION_KEY] = team.id

    use_case = OrganizationBoundaryUseCase(session)
    first = await use_case.create_working_copy(boundary.id)
    second = await use_case.create_working_copy(boundary.id)
    assert first.id == second.id
    assert first.version == 2

    saved = await use_case.save_selection(
        first.id,
        SaveBoundarySelectionRequest(
            operational_boundary=OperationalBoundarySelection(
                scopes=["scope1", "scope2", "scope3"],
                scope2_methods=["location", "market"],
                iso_categories=["1", "2", "3", "4", "5", "6"],
                scope3_categories=[1, 2],
            ),
            areas=[BoundaryAreaSelection(area_id=area.id, included=True)],
            equipment=[BoundaryEquipmentSelection(equipment_id=equipment.id, area_id=area.id, included=True)],
        ),
    )
    assert saved.status == "draft"
    assert saved.operational_boundary is not None
    assert saved.operational_boundary["scope2Methods"] == ["location", "market"]
