from __future__ import annotations

from uuid import uuid4

import pytest

pytestmark = pytest.mark.anyio


async def test_create_role_is_visible_on_roles_list(client, superuser_token_headers: dict[str, str]) -> None:
    role_name = f"echo-role-{uuid4().hex[:8]}"

    create_response = await client.post(
        "/api/roles",
        json={"name": role_name},
        headers=superuser_token_headers,
    )
    assert create_response.status_code == 201
    assert create_response.json()["name"] == role_name
    assert create_response.json()["slug"]

    list_response = await client.get("/api/roles", headers=superuser_token_headers)
    assert list_response.status_code == 200

    body = list_response.json()
    assert body["total"] >= 1
    assert body["items"][0]["name"] == role_name
