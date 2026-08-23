from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db import models as m
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


def _activity(team_id: UUID | None, record_code: str) -> m.GhgActivityRecord:
    return m.GhgActivityRecord(
        team_id=team_id,
        record_code=record_code,
        inventory_code="INV-2026",
        organization_code="ORG",
        facility_code="FAC",
        source_code=f"SOURCE-{record_code}",
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
        source_payload={"method_code": "F08_PURCHASED_ENERGY", "scope2_method": "location"},
        status="approved",
    )


async def test_ghg_activity_is_tenant_isolated_and_auto_assigned(session) -> None:
    team_a = m.Team(name="GHG Tenant A", slug="ghg-tenant-a")
    team_b = m.Team(name="GHG Tenant B", slug="ghg-tenant-b")
    session.add_all([team_a, team_b])
    await session.flush()

    session.info[TENANT_BYPASS_SESSION_KEY] = True
    session.add_all([_activity(team_a.id, "A-1"), _activity(team_b.id, "B-1")])
    await session.commit()
    session.info.clear()

    session.info[TENANT_ID_SESSION_KEY] = team_a.id
    rows = (await session.scalars(select(m.GhgActivityRecord))).all()
    assert [row.record_code for row in rows] == ["A-1"]

    auto_assigned = _activity(None, "A-2")
    session.add(auto_assigned)
    await session.commit()
    assert str(auto_assigned.team_id) == str(team_a.id)


async def test_ghg_source_and_allocation_are_tenant_isolated(session) -> None:
    team_a = m.Team(name="GHG Resource Tenant A", slug="ghg-resource-a")
    team_b = m.Team(name="GHG Resource Tenant B", slug="ghg-resource-b")
    session.add_all([team_a, team_b])
    await session.flush()

    session.info[TENANT_BYPASS_SESSION_KEY] = True
    area_a = m.MonitorSector(team_id=team_a.id, code="A-ROOT", name="A园区", path="/A-ROOT", level=0)
    area_b = m.MonitorSector(team_id=team_b.id, code="B-ROOT", name="B园区", path="/B-ROOT", level=0)
    activity_a = _activity(team_a.id, "A-RESOURCE")
    activity_b = _activity(team_b.id, "B-RESOURCE")
    session.add_all([area_a, area_b, activity_a, activity_b])
    await session.flush()
    source_a = m.GhgEmissionSource(
        team_id=team_a.id,
        inventory_code="INV-2026",
        organization_code="ORG",
        facility_code="A-ROOT",
        source_code="SOURCE-A",
        source_name="A园区购入电力",
        iso_category_code="2.1",
        source_mechanism="energy",
        default_area_id=area_a.id,
    )
    source_b = m.GhgEmissionSource(
        team_id=team_b.id,
        inventory_code="INV-2026",
        organization_code="ORG",
        facility_code="B-ROOT",
        source_code="SOURCE-B",
        source_name="B园区购入电力",
        iso_category_code="2.1",
        source_mechanism="energy",
        default_area_id=area_b.id,
    )
    session.add_all([source_a, source_b])
    await session.flush()
    session.add_all(
        [
            m.GhgActivityAllocation(
                team_id=team_a.id,
                activity_id=activity_a.id,
                emission_source_id=source_a.id,
                allocation_code="A-RESOURCE-001",
                area_id=area_a.id,
                allocation_role="energy_consumption",
                allocation_ratio=Decimal(1),
                area_code_snapshot=area_a.code,
                area_name_snapshot=area_a.name or area_a.code,
            ),
            m.GhgActivityAllocation(
                team_id=team_b.id,
                activity_id=activity_b.id,
                emission_source_id=source_b.id,
                allocation_code="B-RESOURCE-001",
                area_id=area_b.id,
                allocation_role="energy_consumption",
                allocation_ratio=Decimal(1),
                area_code_snapshot=area_b.code,
                area_name_snapshot=area_b.name or area_b.code,
            ),
        ]
    )
    await session.commit()
    session.info.clear()

    session.info[TENANT_ID_SESSION_KEY] = team_a.id
    sources = (await session.scalars(select(m.GhgEmissionSource))).all()
    allocations = (await session.scalars(select(m.GhgActivityAllocation))).all()
    assert [row.source_code for row in sources] == ["SOURCE-A"]
    assert [row.allocation_code for row in allocations] == ["A-RESOURCE-001"]


async def test_inventory_reports_are_tenant_isolated(session) -> None:
    team_a = m.Team(name="GHG Report Tenant A", slug="ghg-report-a")
    team_b = m.Team(name="GHG Report Tenant B", slug="ghg-report-b")
    profile = m.GhgReportingProfile(
        code="REPORT-PROFILE",
        name="组织盘查报告配置",
        version="1",
        standard_code="ISO 14064-1",
        standard_version="2018",
        effective_from=date(2026, 1, 1),
    )
    session.add_all([team_a, team_b, profile])
    await session.flush()
    session.info[TENANT_BYPASS_SESSION_KEY] = True

    async def add_report(team: m.Team, suffix: str) -> None:
        organization = m.ReportingOrganization(team_id=team.id, code=f"ORG-{suffix}", name=f"报告组织{suffix}")
        session.add(organization)
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
            boundary_no=f"BOUNDARY-{suffix}",
            boundary_name=f"组织边界{suffix}",
            status="published",
        )
        session.add(boundary)
        await session.flush()
        run = m.GhgCalculationRun(
            team_id=team.id,
            run_code=f"RUN-{suffix}",
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
        session.add(
            m.GhgInventoryReport(
                team_id=team.id,
                report_code="ORG-GHG-REPORT",
                version=1,
                title=f"组织盘查报告{suffix}",
                inventory_code="INV-2026",
                run_id=run.id,
                reporting_org_id=organization.id,
                reporting_period_id=period.id,
                organization_boundary_id=boundary.id,
                reporting_profile_id=profile.id,
            )
        )

    await add_report(team_a, "A")
    await add_report(team_b, "B")
    await session.commit()
    session.info.clear()
    session.info[TENANT_ID_SESSION_KEY] = team_a.id

    reports = (await session.scalars(select(m.GhgInventoryReport))).all()
    assert [row.title for row in reports] == ["组织盘查报告A"]
