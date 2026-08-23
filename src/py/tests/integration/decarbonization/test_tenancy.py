"""Tenant-isolation coverage for the decarbonization bounded context."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import models as m
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


def _project(team_id, code: str) -> m.ReductionProject:
    return m.ReductionProject(
        team_id=team_id,
        code=code,
        name=f"减排项目 {code}",
        track="internal_action",
        category="energy_efficiency",
        owner_name="能源管理部",
        expected_reduction_tco2e=Decimal(10),
    )


async def test_reduction_projects_are_tenant_isolated_and_auto_assigned(session) -> None:
    team_a = m.Team(name="Reduction Tenant A", slug="reduction-tenant-a")
    team_b = m.Team(name="Reduction Tenant B", slug="reduction-tenant-b")
    session.add_all([team_a, team_b])
    await session.flush()

    session.info[TENANT_BYPASS_SESSION_KEY] = True
    session.add_all([_project(team_a.id, "RED-A"), _project(team_b.id, "RED-B")])
    await session.commit()
    session.info.clear()

    session.info[TENANT_ID_SESSION_KEY] = team_a.id
    rows = (await session.scalars(select(m.ReductionProject))).all()
    assert [row.code for row in rows] == ["RED-A"]

    auto_assigned = _project(None, "RED-AUTO")
    session.add(auto_assigned)
    await session.commit()
    assert auto_assigned.team_id == team_a.id
