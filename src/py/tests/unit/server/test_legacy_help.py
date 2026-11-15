"""Legacy help URLs must serve canonical redirects before the production SPA fallback."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from litestar import Litestar
from litestar.config.app import AppConfig
from litestar.testing import TestClient
from litestar_vite import PathConfig, RuntimeConfig, ViteConfig, VitePlugin

from app.lib.settings import get_settings
from app.server.core import ApplicationCore

if TYPE_CHECKING:
    from collections.abc import Iterator


PUBLIC_HELP = Path(__file__).resolve().parents[4] / "js/web/public/help/woheng-showcase"


@pytest.fixture
def help_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient[Litestar]]:
    """Use the registered help route with real production Vite routing, without database plugins."""
    bundle = tmp_path / "bundle"
    bundled_help = bundle / "help/woheng-showcase"
    for source in PUBLIC_HELP.rglob("*.html"):
        target = bundled_help / source.relative_to(PUBLIC_HELP)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (bundle / "index.html").write_text('<html><body><div id="root">SPA fallback</div></body></html>')
    (bundle / "manifest.json").write_text("{}")
    monkeypatch.setattr(get_settings().vite, "BUNDLE_DIR", bundle)
    monkeypatch.setattr(get_settings().vite, "DEV_MODE", False)
    configured = ApplicationCore().on_app_init(AppConfig(route_handlers=[]))
    vite = VitePlugin(
        config=ViteConfig(
            mode="spa",
            dev_mode=False,
            runtime=RuntimeConfig(dev_mode=False),
            paths=PathConfig(root=tmp_path, bundle_dir=bundle, asset_url="/static/web/"),
        )
    )
    app = Litestar(
        route_handlers=configured.route_handlers,
        plugins=[vite],
        middleware=configured.middleware,
        after_request=configured.after_request,
    )
    with TestClient(app=app) as client:
        yield client


def test_all_legacy_help_urls_serve_canonical_pages_anonymously(help_client: TestClient[Litestar]) -> None:
    """All generated aliases serve the same bytes as the bundle, with no old body or SPA shell."""
    pages = json.loads((PUBLIC_HELP / "site-map.json").read_text())["pages"]
    assert len(pages) == 34
    assert all(page["target"].startswith("https://docs.nexlca.com/energy-carbon/manual") for page in pages)
    for page in pages:
        response = help_client.get(f"/help/woheng-showcase/{page['href']}")
        assert response.status_code == 200
        assert response.content == (PUBLIC_HELP / page["href"]).read_bytes()
        assert f'content="0; url={page["target"]}"' in response.text
        assert 'id="root"' not in response.text
        assert "<img" not in response.text
        assert "content-security-policy" in response.headers


def test_help_directory_unknown_page_and_spa_routes(help_client: TestClient[Litestar]) -> None:
    """Directory URLs work; missing help stays 404 while normal client routes retain SPA fallback."""
    index = help_client.get("/help/woheng-showcase/")
    assert index.status_code == 200
    assert index.content == (PUBLIC_HELP / "index.html").read_bytes()
    assert help_client.get("/help/woheng-showcase/pages/unknown.html").status_code == 404
    spa = help_client.get("/energy/consumption")
    assert spa.status_code == 200
    assert "SPA fallback" in spa.text


def test_dev_mode_leaves_help_to_vite_without_a_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Development initialization neither needs built help nor intercepts Vite public paths."""
    bundle = tmp_path / "not-built"
    monkeypatch.setattr(get_settings().vite, "BUNDLE_DIR", bundle)
    monkeypatch.setattr(get_settings().vite, "DEV_MODE", True)
    configured = ApplicationCore().on_app_init(AppConfig(route_handlers=[]))
    assert not bundle.exists()
    assert configured.route_handlers == []
