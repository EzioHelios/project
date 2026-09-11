"""Authenticated scene and binary-resource endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID  # noqa: TC003 - Litestar resolves route annotations at runtime.

from litestar import Controller, Request, get
from litestar.di import Provide
from litestar.exceptions import PermissionDeniedException
from litestar.response import File, Response

from app.domain.accounts.guards import requires_authenticated_user
from app.domain.spatial_scenes.store import SceneAssetStore, provide_scene_store
from app.lib.tenancy import resolve_tenant_context

PRIVATE_HEADERS = {"Cache-Control": "private, no-store", "Vary": "Cookie, Authorization, X-Team-Id"}


def authorize_scene_team(request: Request, team_id: UUID) -> None:
    """Require an active user and access to the explicit URL team."""
    context = resolve_tenant_context(request.scope)
    if context is None or context.team_id != team_id:
        raise PermissionDeniedException(detail="无权访问该租户的园区模型")


class TenantSceneController(Controller):
    """Expose private scene assets under team authorization."""

    path = "/api/teams/{team_id:uuid}/scene"
    tags = ["Spatial Scenes"]
    guards = [requires_authenticated_user]
    dependencies = {"scene_store": Provide(provide_scene_store, sync_to_thread=False)}

    @get("/")
    async def get_scene(
        self,
        request: Request,
        team_id: UUID,
        scene_store: SceneAssetStore,
    ) -> Response[dict[str, Any]]:
        """Read the current team's assigned scene manifest."""
        authorize_scene_team(request, team_id)
        return Response(scene_store.manifest(team_id), headers=PRIVATE_HEADERS)

    @get("/assets/{asset_name:str}")
    async def get_asset(
        self,
        request: Request,
        team_id: UUID,
        asset_name: str,
        scene_store: SceneAssetStore,
        revision: str | None = None,
    ) -> File:
        """Authorize every asset read, including requests for copied URLs."""
        authorize_scene_team(request, team_id)
        path = scene_store.asset(team_id, asset_name, revision)
        return File(
            path=path,
            media_type={
                ".glb": "model/gltf-binary",
                ".json": "application/json",
                ".geojson": "application/geo+json",
            }.get(path.suffix, "image/jpeg"),
            content_disposition_type="inline",
            headers=PRIVATE_HEADERS,
        )
