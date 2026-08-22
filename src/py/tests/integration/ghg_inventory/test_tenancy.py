from datetime import date
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
