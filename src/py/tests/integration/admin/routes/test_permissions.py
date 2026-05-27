"""Integration tests for admin permission management endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from app.db import models as m
from tests.factories import PermissionFactory

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.anyio, pytest.mark.integration, pytest.mark.auth, pytest.mark.endpoints]


async def _ensure_permissions(session: AsyncSession, codes: list[str]) -> None:
    existing_codes = {
        row[0]
        for row in await session.execute(select(m.Permission.code).where(m.Permission.code.in_(codes)))
    }
    missing_codes = [code for code in codes if code not in existing_codes]
    if not missing_codes:
        return

    for code in missing_codes:
        permission = PermissionFactory.build(
            code=code,
            name=code.replace(".", " ").title(),
            module=code.split(".")[0],
            description=f"Test seed for {code}",
        )
        session.add(permission)
    await session.commit()


async def test_permissions_list_requires_permission(
    client: AsyncClient,
    user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    session: AsyncSession,
) -> None:
    await _ensure_permissions(session, ["auth.role.manage", "carbon.record.create"])

    response = await client.get("/api/admin/permissions", headers=user_token_headers)
    assert response.status_code == 403

    response = await client.get("/api/admin/permissions", headers=superuser_token_headers)
    assert response.status_code == 200
    codes = {permission["code"] for permission in response.json()}
    assert "auth.role.manage" in codes
    assert "carbon.record.create" in codes


async def test_update_role_permissions(
    client: AsyncClient,
    superuser_token_headers: dict[str, str],
    session: AsyncSession,
) -> None:
    await _ensure_permissions(session, ["carbon.record.create", "carbon.record.submit"])
    role = (await session.execute(select(m.Role).where(m.Role.name == "Application Access"))).scalar_one()

    response = await client.put(
        f"/api/admin/roles/{role.id}/permissions",
        json={"permissionCodes": ["carbon.record.create", "carbon.record.submit"]},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == role.slug
    assert {permission["code"] for permission in payload["permissions"]} == {
        "carbon.record.create",
        "carbon.record.submit",
    }
