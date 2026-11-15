from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db import models as m
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def test_energy_entry_permission_and_team_isolation(
    client: AsyncClient,
    user_token_headers: dict[str, str],
    session: AsyncSession,
) -> None:
    own_team = UUID("97108ac1-ffcb-411d-8b1e-d9183399f63b")
    other_team = UUID("81108ac1-ffcb-411d-8b1e-d91833999999")
    headers = {**user_token_headers, "X-Team-Id": str(own_team)}
    payload = {
        "source_record_id": "MONTH-01",
        "energy_type_code": "purchased_electricity",
        "amount": 100,
        "unit": "kWh",
        "period_start": "2026-08-01",
        "period_end": "2026-08-31",
    }
    # A team owner without the business permission still cannot maintain the ledger.
    response = await client.post("/api/energy/interval-facts", headers=headers, json=payload)
    assert response.status_code == 403
    role = (await session.scalars(select(m.Role).where(m.Role.name == "Application Access"))).one()
    permission = m.Permission(code="carbon.config.manage", name="Maintain energy business data", module="carbon")
    session.add(permission)
    await session.flush()
    session.add(m.RolePermission(role_id=role.id, permission_id=permission.id))
    user_id = UUID("5ef29f3c-3560-4d15-ba6b-a2e5c721e4d2")
    if (
        await session.scalar(select(m.UserRole.id).where(m.UserRole.user_id == user_id, m.UserRole.role_id == role.id))
        is None
    ):
        session.add(m.UserRole(user_id=user_id, role_id=role.id))
    session.add(
        m.EnergyType(
            code="purchased_electricity",
            name="外购电力",
            category="purchased_energy",
            default_scope="scope2",
            original_unit="kWh",
        )
    )
    session.info[TENANT_BYPASS_SESSION_KEY] = True
    foreign_device = m.MonitorEquipment(team_id=other_team, code="OTHER-METER", name="其他工厂电表")
    session.add(foreign_device)
    await session.commit()

    response = await client.post("/api/energy/interval-facts", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    record = response.json()["data"]
    record_id = record["id"]
    response = await client.patch(
        f"/api/energy/interval-facts/{record_id}", headers=headers, json={**payload, "amount": 125}
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["amount"] == 125

    response = await client.post(
        "/api/energy/interval-facts",
        headers=headers,
        json={**payload, "source_record_id": "FOREIGN-DEVICE", "equipment_id": foreign_device.id},
    )
    assert response.status_code == 400
    # A valid business permission cannot select an unrelated tenant.
    foreign_headers = {**user_token_headers, "X-Team-Id": str(other_team)}
    for method in ("PATCH", "DELETE"):
        response = await client.request(
            method,
            f"/api/energy/interval-facts/{record_id}",
            headers=foreign_headers,
            json=payload if method == "PATCH" else None,
        )
        assert response.status_code == 403
    response = await client.post(
        "/api/energy/imports/datasets",
        headers=foreign_headers,
        json={"dataset": "energy_interval_facts", "rows": [payload]},
    )
    assert response.status_code == 403

    # A foreign record ID is also rejected when a legitimate own-team header is used.
    other_record = m.EnergyIntervalFact(
        team_id=other_team,
        source_system="manual_entry",
        source_record_id="OTHER",
        energy_type_code="purchased_electricity",
        amount=Decimal(50),
        unit="kWh",
        period_start=record["period_start"],
        period_end=record["period_end"],
    )
    from datetime import datetime

    other_record.period_start = datetime.fromisoformat(record["period_start"])
    other_record.period_end = datetime.fromisoformat(record["period_end"])
    session.add(other_record)
    await session.commit()
    response = await client.delete(f"/api/energy/interval-facts/{other_record.id}", headers=headers)
    assert response.status_code == 404
    response = await client.post(
        "/api/energy/imports/datasets",
        headers=headers,
        json={
            "dataset": "energy_interval_facts",
            "source_name": "车间月度能源台账.csv",
            "rows": [{**payload, "source_record_id": "IMPORT-01"}],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["imported_count"] == 1
    imported_id = response.json()["data"]["imported_ids"][0]
    imported = await client.get(f"/api/energy/interval-facts?ids={imported_id}", headers=headers)
    assert imported.json()["items"][0]["source_name"] == "车间月度能源台账.csv"
    response = await client.get(f"/api/energy/interval-facts?ids={record_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["totals"][0]["amount"] == 125
    response = await client.delete(f"/api/energy/interval-facts/{record_id}", headers=headers)
    assert response.status_code == 200
