"""Tenant isolation for the carbon asset ledger."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from app.db import models as m
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


def _instrument(team_id: UUID | None, code: str) -> m.CarbonAssetInstrument:
    return m.CarbonAssetInstrument(
        team_id=team_id,
        code=code,
        name=f"全国碳排放配额 {code}",
        instrument_class="CEA",
        native_unit="tCO2e",
        market="national",
        compliance_eligible=True,
        source_name="履约资产台账",
    )


async def test_carbon_asset_instruments_are_tenant_isolated_and_auto_assigned(session: AsyncSession) -> None:
    team_a = m.Team(name="Carbon Asset Tenant A", slug="carbon-asset-a")
    team_b = m.Team(name="Carbon Asset Tenant B", slug="carbon-asset-b")
    session.add_all([team_a, team_b])
    await session.flush()

    session.info[TENANT_BYPASS_SESSION_KEY] = True
    session.add_all([_instrument(team_a.id, "CEA-A"), _instrument(team_b.id, "CEA-B")])
    await session.commit()
    session.info.clear()

    session.info[TENANT_ID_SESSION_KEY] = team_a.id
    rows = (await session.scalars(select(m.CarbonAssetInstrument))).all()
    assert [row.code for row in rows] == ["CEA-A"]

    auto_assigned = _instrument(None, "CEA-AUTO")
    session.add(auto_assigned)
    await session.commit()
    assert str(auto_assigned.team_id) == str(team_a.id)
