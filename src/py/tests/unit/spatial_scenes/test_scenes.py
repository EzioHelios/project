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

from app.domain.spatial_scenes.controllers import TenantSceneController
from app.domain.spatial_scenes.store import SceneAssetStore

if TYPE_CHECKING:
    from pathlib import Path

A = UUID("00000000-0000-7000-8000-000000000010")
B = UUID("00000000-0000-7000-8000-000000000020")
C = UUID("00000000-0000-7000-8000-000000000030")
pytestmark = pytest.mark.unit


class TestIdentity(AbstractAuthenticationMiddleware):
    __test__ = False

    async def authenticate_request(self, connection):
        identity = connection.headers.get("x-test-identity")
        if identity not in {"a", "b", "c", "admin", "inactive"}:
            raise NotAuthorizedException
        team = {"a": A, "b": B, "c": C, "inactive": A}.get(identity)
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
    (tmp_path / "bindings.json").write_text(json.dumps({str(A): "a", str(B): "b"}))
    for key in ["a", "b"]:
        pack = tmp_path / "packs" / key
        pack.mkdir(parents=True)
        (pack / "model.glb").write_bytes(key.encode())
        (pack / "hidden.txt").write_text("not an exposed asset")
        (pack / "scene.json").write_text(json.dumps({"sceneId": key, "revision": "1", "assets": ["model.glb"]}))
    store = SceneAssetStore(tmp_path)

    class Controller(TenantSceneController):
        dependencies = {"scene_store": Provide(lambda: store, sync_to_thread=False)}

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
