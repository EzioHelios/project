from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = [pytest.mark.anyio, pytest.mark.integration, pytest.mark.endpoints]


BIGSCREEN_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "/api/bigscreen/meta": ("title", "short_name", "default_path", "nav_items"),
    "/api/bigscreen/intro": ("hero_title", "hero_description", "company_gallery", "company_facts"),
    "/api/bigscreen/overview": (
        "energy_kpis",
        "carbon_kpis",
        "energy_flow",
        "production_trend",
        "filters",
    ),
    "/api/bigscreen/power": (
        "alerts",
        "energy_structure",
        "energy_ranking",
        "energy_flow",
        "energy_timeseries",
    ),
    "/api/bigscreen/carbon": (
        "carbon_compare",
        "production_share",
        "carbon_flow",
        "carbon_alerts",
        "carbon_price_trend",
        "commentary",
    ),
}


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
