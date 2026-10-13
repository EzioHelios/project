from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.db import models as m
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = [pytest.mark.anyio, pytest.mark.integration, pytest.mark.endpoints]


BIGSCREEN_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "/api/bigscreen/meta": ("title", "short_name", "default_path", "nav_items"),
    "/api/bigscreen/intro": ("hero_title", "company_gallery", "company_facts"),
    "/api/bigscreen/overview": (
        "energy_kpis",
        "trend",
        "area_ranking",
        "devices",
        "alarms",
        "energy_flow",
        "presentation",
    ),
    "/api/bigscreen/power": ("energy_kpis", "trend", "equipment_ranking", "power_alarms"),
    "/api/bigscreen/carbon": ("scope_distribution", "area_ranking", "period_facts", "hero_metrics"),
    "/api/bigscreen/events": ("total", "page", "page_size", "distribution", "recent"),
}


@pytest.mark.parametrize("query", ["category=bad", "page=0", "status=bad", "start=2026-10-02&end=2026-10-01"])
async def test_event_query_rejects_invalid_filters(authenticated_client, query):
    response = await authenticated_client.get(f"/api/bigscreen/events?{query}")
    assert response.status_code == 400


@pytest.mark.parametrize("path", list(BIGSCREEN_ENDPOINTS))
async def test_bigscreen_endpoints_require_auth(
    client: AsyncClient,
    path: str,
) -> None:
    response = await client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize(("path", "required_keys"), list(BIGSCREEN_ENDPOINTS.items()))
async def test_bigscreen_endpoints_return_stable_payload(
    authenticated_client: AsyncClient,
    path: str,
    required_keys: tuple[str, ...],
) -> None:
    response = await authenticated_client.get(path)

    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["code"] == 200
    assert isinstance(payload["data"], dict)

    data = payload["data"]
    for key in required_keys:
        assert key in data

    for value in data.values():
        if isinstance(value, list):
            assert value is not None


async def test_photos_are_private_and_tenant_scoped(
    client, authenticated_client, test_user, session, tmp_path, monkeypatch
):
    teams = [m.Team(name="Photo A", slug="photo-a"), m.Team(name="Photo B", slug="photo-b")]
    session.add_all(teams)
    await session.flush()
    for team in teams:
        session.add(m.TeamMember(team_id=team.id, user_id=test_user.id))
    session.info[TENANT_ID_SESSION_KEY] = teams[0].id
    photos = [m.MonitorSectorPhoto(path=value) for value in ["images/photo.png", "../../outside.png", None]]
    session.add_all(photos)
    await session.commit()
    root = tmp_path / str(teams[0].id)
    (root / "images").mkdir(parents=True)
    content = b"\x89PNG\r\n\x1a\n"
    (root / "images/photo.png").write_bytes(content)
    (tmp_path.parent / "outside.png").write_bytes(content)
    monkeypatch.setenv("SECTOR_PHOTO_ROOT", str(tmp_path))
    url = f"/api/bigscreen/photos/{photos[0].id}"
    result = await authenticated_client.get(url, headers={"X-Team-Id": str(teams[0].id)})
    assert result.status_code == 200
    assert result.content == content
    assert result.headers["cache-control"] == "private, no-store"
    wrong_team = await authenticated_client.get(url, headers={"X-Team-Id": str(teams[1].id)})
    assert wrong_team.status_code == 404
    for photo in photos[1:]:
        result = await authenticated_client.get(
            f"/api/bigscreen/photos/{photo.id}", headers={"X-Team-Id": str(teams[0].id)}
        )
        assert result.status_code == 404


async def test_photos_require_auth(client):
    assert (await client.get("/api/bigscreen/photos/1")).status_code == 401
