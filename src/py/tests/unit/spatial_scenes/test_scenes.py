"""Exercise tenant authorization on both scene manifests and copied binary URLs."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from litestar import Litestar
from litestar.di import Provide
from litestar.exceptions import NotAuthorizedException
from litestar.middleware.authentication import AbstractAuthenticationMiddleware, AuthenticationResult
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.spatial_scenes.controllers import TenantSceneController
from app.domain.spatial_scenes.store import DEFAULT_ROOT, SceneAssetStore

if TYPE_CHECKING:
    from pathlib import Path

A = UUID("00000000-0000-7000-8000-000000000010")
B = UUID("00000000-0000-7000-8000-000000000020")
C = UUID("00000000-0000-7000-8000-000000000030")
D = UUID("00000000-0000-7000-8000-000000000040")
WAREHOUSE_SCENES = {
    UUID("00000000-0000-7000-8000-000000000001"): ("xiangtai-warehouse", "cesium-campus"),
    UUID("00000000-0000-7000-8000-000000000002"): ("anfang-central", "cesium-campus"),
    UUID("00000000-0000-7000-8000-000000000003"): ("jiangyan-tianmu-road", "cesium-campus"),
    UUID("00000000-0000-7000-8000-000000000004"): ("taixing-keneng-road", "cesium-campus"),
}
pytestmark = pytest.mark.unit


class TestIdentity(AbstractAuthenticationMiddleware):
    __test__ = False

    async def authenticate_request(self, connection):
        identity = connection.headers.get("x-test-identity")
        if identity not in {"a", "b", "c", "d", "admin", "inactive"}:
            raise NotAuthorizedException
        team = {"a": A, "b": B, "c": C, "d": D, "inactive": A}.get(identity)
        user = SimpleNamespace(
            id=A,
            is_active=identity != "inactive",
            is_superuser=identity == "admin",
            roles=[],
            teams=[SimpleNamespace(team_id=team)] if team else [],
        )
        return AuthenticationResult(user=user, auth=None)


@pytest.fixture
def scene_client(tmp_path: Path):
    (tmp_path / "bindings.json").write_text(
        json.dumps({str(A): "a", str(B): "b", "slug:woheng-taizhou-production-base": "woheng"})
    )
    for key in ["a", "b", "woheng"]:
        pack = tmp_path / "packs" / key
        pack.mkdir(parents=True)
        (pack / "model.glb").write_bytes(key.encode())
        (pack / "hidden.txt").write_text("not an exposed asset")
        (pack / "scene.json").write_text(json.dumps({"sceneId": key, "revision": "1", "assets": ["model.glb"]}))
    store = SceneAssetStore(tmp_path)

    class SceneSession(AsyncSession):
        async def scalar(self, statement):
            team_id = next(iter(statement.compile().params.values()))
            return "woheng-taizhou-production-base" if team_id == D else None

    session = SceneSession()

    class Controller(TenantSceneController):
        dependencies = {
            "scene_store": Provide(lambda: store, sync_to_thread=False),
            "db_session": Provide(lambda: session, sync_to_thread=False),
        }

    app = Litestar(route_handlers=[Controller], middleware=[TestIdentity])
    with TestClient(app) as client:
        yield client


def test_members_get_only_their_scene_and_private_assets(scene_client):
    manifest = scene_client.get(f"/api/teams/{A}/scene/", headers={"x-test-identity": "a"})
    assert manifest.status_code == 200
    assert manifest.json()["sceneId"] == "a"
    assert manifest.json()["teamId"] == str(A)
    asset_url = manifest.json()["assets"][0]
    response = scene_client.get(asset_url, headers={"x-test-identity": "a"})
    assert response.status_code == 200
    assert response.content == b"a"
    assert response.headers["cache-control"] == "private, no-store"
    assert "Cookie" in response.headers["vary"]


@pytest.mark.parametrize("suffix", ["", "assets/model.glb", "assets/model.glb?revision=1"])
def test_copied_other_tenant_urls_are_denied_even_with_own_header(scene_client, suffix):
    response = scene_client.get(f"/api/teams/{B}/scene/{suffix}", headers={"x-test-identity": "a", "X-Team-Id": str(A)})
    assert response.status_code == 403


@pytest.mark.parametrize("identity,status", [(None, 401), ("inactive", 403)])
def test_anonymous_and_inactive_asset_reads_denied(scene_client, identity, status):
    headers = {"x-test-identity": identity} if identity else {}
    assert scene_client.get(f"/api/teams/{A}/scene/assets/model.glb", headers=headers).status_code == status


def test_missing_assignment_never_falls_back(scene_client):
    assert scene_client.get(f"/api/teams/{C}/scene/", headers={"x-test-identity": "c"}).status_code == 404


def test_unlisted_files_never_served(scene_client):
    assert (
        scene_client.get(f"/api/teams/{A}/scene/assets/hidden.txt", headers={"x-test-identity": "a"}).status_code == 404
    )


def test_admin_can_explicitly_select_an_assigned_team(scene_client):
    response = scene_client.get(f"/api/teams/{B}/scene/", headers={"x-test-identity": "admin"})
    assert response.status_code == 200
    assert response.json()["sceneId"] == "b"


def test_demo_slug_binding_uses_database_identity_and_keeps_asset_authorization(scene_client):
    manifest = scene_client.get(f"/api/teams/{D}/scene/", headers={"x-test-identity": "d"})
    assert manifest.status_code == 200
    assert manifest.json()["sceneId"] == "woheng"
    asset = scene_client.get(manifest.json()["assets"][0], headers={"x-test-identity": "d"})
    assert asset.status_code == 200
    assert asset.content == b"woheng"
    assert scene_client.get(f"/api/teams/{D}/scene/", headers={"x-test-identity": "a"}).status_code == 403


def test_file_symlink_cannot_escape_pack(tmp_path):
    pack = tmp_path / "packs" / "a"
    pack.mkdir(parents=True)
    (tmp_path / "bindings.json").write_text(json.dumps({str(A): "a"}))
    (pack / "scene.json").write_text(json.dumps({"assets": ["model.glb"]}))
    outside = tmp_path / "outside.glb"
    outside.write_bytes(b"private")
    (pack / "model.glb").symlink_to(outside)
    from litestar.exceptions import NotFoundException

    with pytest.raises(NotFoundException):
        SceneAssetStore(tmp_path).asset(A, "model.glb")


def test_stale_asset_revision_cannot_mix_scene_versions(scene_client):
    response = scene_client.get(f"/api/teams/{A}/scene/assets/model.glb?revision=old", headers={"x-test-identity": "a"})
    assert response.status_code == 404


@pytest.mark.parametrize(("team_id", "expected"), WAREHOUSE_SCENES.items())
def test_warehouse_tenants_have_dedicated_scene_packs(team_id, expected):
    scene_id, engine = expected
    store = SceneAssetStore(DEFAULT_ROOT)

    manifest = store.manifest(team_id)

    assert manifest["sceneId"] == scene_id
    assert manifest["engine"] == engine
    assert manifest["teamId"] == str(team_id)
    assert manifest["assets"]
    for asset_url in manifest["assets"]:
        asset_name = asset_url.rsplit("/", maxsplit=1)[-1].split("?", maxsplit=1)[0]
        assert store.asset(team_id, asset_name, manifest["revision"]).is_file()


@pytest.mark.parametrize(
    ("slug", "scene_id", "expected_origin", "expected_heading"),
    [
        ("woheng-taizhou-production-base", "woheng-taizhou", [119.92300272, 32.36004393], 0),
        ("woheng-huzhou-production-base", "woheng-huzhou", [119.98303056, 30.91592199], -25),
    ],
)
def test_woheng_demo_tenants_have_distinct_virtual_campus_packs(slug, scene_id, expected_origin, expected_heading):
    store = SceneAssetStore(DEFAULT_ROOT)
    manifest = store.manifest(D, slug)

    assert manifest["sceneId"] == scene_id
    assert manifest["engine"] == "cesium-campus"
    assert manifest["georegistration"]["origin"] == expected_origin
    assert manifest["georegistration"]["headingDegrees"] == expected_heading
    assert manifest["georegistration"]["placement"]["kind"] == "fictional-demonstration"
    assert manifest["georegistration"]["placement"]["parcelOwnership"] == "unverified"
    assert len(manifest["world"]["buildings"]) >= 5
    for asset_url in manifest["assets"]:
        asset_name = asset_url.rsplit("/", maxsplit=1)[-1].split("?", maxsplit=1)[0]
        assert store.asset(D, asset_name, manifest["revision"], slug).is_file()
