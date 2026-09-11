"""Read versioned scene packs from private server storage."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from litestar.exceptions import NotFoundException

if TYPE_CHECKING:
    from uuid import UUID

PACK_KEY = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
ASSET_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}\Z")
DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "assets" / "scenes"


class SceneAssetStore:
    """Resolve explicit team assignments without a cross-tenant fallback."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _pack(self, team_id: UUID) -> Path:
        bindings_path = self.root / "bindings.json"
        bindings = json.loads(bindings_path.read_text()) if bindings_path.is_file() else {}
        key = bindings.get(str(team_id))
        if not isinstance(key, str) or not PACK_KEY.fullmatch(key):
            raise NotFoundException(detail="当前租户尚未配置园区模型")
        packs = (self.root / "packs").resolve()
        pack = (packs / key).resolve()
        if not pack.is_relative_to(packs) or not pack.is_dir():
            raise NotFoundException(detail="园区模型资源不存在")
        return pack

    def manifest(self, team_id: UUID) -> dict[str, Any]:
        """Return only the assigned scene, with protected asset references."""
        pack = self._pack(team_id)
        source = json.loads((pack / "scene.json").read_text())
        revision = source["revision"]
        base = f"/api/teams/{team_id}/scene/assets"
        source["assets"] = [f"{base}/{name}?revision={revision}" for name in source["assets"]]
        if source.get("reference"):
            source["reference"] = f"{base}/{source['reference']}?revision={revision}"
        if source.get("legacyManifest"):
            source["legacyManifest"] = f"{base}/{source['legacyManifest']}?revision={revision}"
        source["teamId"] = str(team_id)
        return source

    def asset(self, team_id: UUID, name: str, revision: str | None = None) -> Path:
        """Serve only manifest-listed files inside the assigned pack."""
        pack = self._pack(team_id)
        source = json.loads((pack / "scene.json").read_text())
        allowed = {*source["assets"], source.get("reference")}
        if revision is not None and revision != source.get("revision"):
            raise NotFoundException(detail="园区模型版本已更新")
        if not ASSET_NAME.fullmatch(name) or name not in allowed:
            raise NotFoundException(detail="模型资源不存在")
        path = (pack / name).resolve()
        if not path.is_relative_to(pack) or not path.is_file():
            raise NotFoundException(detail="模型资源不存在")
        return path


def provide_scene_store() -> SceneAssetStore:
    """Use a deployment-mounted asset root when configured."""
    return SceneAssetStore(Path(os.environ.get("SCENE_ASSET_ROOT", str(DEFAULT_ROOT))))
