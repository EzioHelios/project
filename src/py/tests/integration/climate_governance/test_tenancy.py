"""Tenant isolation for climate-governance programs and claims."""

import pytest
from sqlalchemy import select

from app.db import models as m
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


def _program(team_id, code: str) -> m.ClimateProgram:
    return m.ClimateProgram(
        team_id=team_id,
        code=code,
        name=f"气候计划 {code}",
        framework="sbti",
        reporting_year=2026,
        standard_version="NZS-1.3.1+NTC-5.3.1",
        source_name="企业气候计划",
    )


async def test_climate_programs_are_tenant_isolated_and_auto_assigned(session) -> None:
    team_a = m.Team(name="Climate Tenant A", slug="climate-tenant-a")
    team_b = m.Team(name="Climate Tenant B", slug="climate-tenant-b")
    session.add_all([team_a, team_b])
    await session.flush()

    session.info[TENANT_BYPASS_SESSION_KEY] = True
    session.add_all([_program(team_a.id, "CLIMATE-A"), _program(team_b.id, "CLIMATE-B")])
    await session.commit()
    session.info.clear()

    session.info[TENANT_ID_SESSION_KEY] = team_a.id
    rows = (await session.scalars(select(m.ClimateProgram))).all()
    assert [row.code for row in rows] == ["CLIMATE-A"]

    automatic = _program(None, "CLIMATE-AUTO")
    automatic.framework = "cdp"
    session.add(automatic)
    await session.commit()
    assert automatic.team_id == team_a.id
