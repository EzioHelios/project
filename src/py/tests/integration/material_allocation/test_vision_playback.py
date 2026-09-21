from types import SimpleNamespace

import httpx
import pytest
from litestar.exceptions import ClientException

from app.domain.vision import playback

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.mark.parametrize(
    "path,asset",
    [("../secret", "index.m3u8"), ("camera", "../other.ts"), ("https://evil", "index.m3u8"), ("camera", "file.json")],
)
async def test_invalid_media_path_never_contacts_gateway(path, asset):
    with pytest.raises(ClientException) as error:
        await playback.read_asset(path, asset)
    assert error.value.status_code == 404


async def test_hls_assets_use_fixed_gateway_without_redirects(monkeypatch):
    original = httpx.AsyncClient
    requested = []

    def respond(request):
        requested.append(str(request.url))
        return httpx.Response(200, content=b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1000\nstream.m3u8\n")

    monkeypatch.setattr(
        playback,
        "get_settings",
        lambda: SimpleNamespace(carbon=SimpleNamespace(VISION_HLS_ORIGIN="http://gateway:8888")),
    )
    monkeypatch.setattr(
        playback.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(respond), **kw)
    )
    content, kind = await playback.read_asset("warehouse/camera1", "index.m3u8")
    assert requested == ["http://gateway:8888/warehouse/camera1/index.m3u8"]
    assert kind == "application/vnd.apple.mpegurl"
    assert b"stream.m3u8" in content


@pytest.mark.parametrize(
    "content",
    [
        b"#EXTM3U\nhttps://other/segment.ts",
        b'#EXTM3U\n#EXT-X-KEY:URI="https://other/key"',
        b"#EXTM3U\n../other/stream.m3u8",
    ],
)
async def test_external_playlist_rejected(monkeypatch, content):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        playback,
        "get_settings",
        lambda: SimpleNamespace(carbon=SimpleNamespace(VISION_HLS_ORIGIN="http://gateway:8888")),
    )
    monkeypatch.setattr(
        playback.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=content)), **kw),
    )
    with pytest.raises(ClientException) as error:
        await playback.read_asset("camera1", "index.m3u8")
    assert error.value.status_code == 502
