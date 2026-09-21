"""Read HLS assets from the configured internal media gateway, never arbitrary URLs."""

import re
from http import HTTPStatus

import httpx
from litestar.exceptions import ClientException

from app.lib.settings import get_settings

ASSET = re.compile(r"[A-Za-z0-9_-]+\.(?:m3u8|ts)")
STREAM = re.compile(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*")
MAX_ASSET_BYTES = 16 * 1024 * 1024


async def read_asset(stream_path: str, asset: str) -> tuple[bytes, str]:
    if not ASSET.fullmatch(asset) or not STREAM.fullmatch(stream_path):
        raise ClientException(status_code=404, detail="视频流未配置或资源不存在")
    origin = get_settings().carbon.VISION_HLS_ORIGIN.rstrip("/")
    if not origin:
        raise ClientException(status_code=503, detail="视频播放服务未配置")
    content = bytearray()
    try:
        async with (
            httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client,
            client.stream("GET", f"{origin}/{stream_path}/{asset}") as response,
        ):
            if response.status_code != HTTPStatus.OK:
                raise ClientException(status_code=503, detail="视频源暂不可用")
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > MAX_ASSET_BYTES:
                    raise ClientException(status_code=502, detail="视频资源超过大小限制")
    except httpx.HTTPError as exc:
        raise ClientException(status_code=503, detail="视频源连接失败") from exc
    if asset.endswith(".m3u8"):
        # Only sibling assets may be fetched through this camera's authorized route.
        try:
            lines = content.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise ClientException(status_code=502, detail="视频播放列表无效") from exc
        if (
            not lines
            or lines[0] != "#EXTM3U"
            or any(
                (line and not line.startswith("#") and not ASSET.fullmatch(line)) or "URI=" in line for line in lines
            )
        ):
            raise ClientException(status_code=502, detail="视频播放列表无效")
    return bytes(content), "application/vnd.apple.mpegurl" if asset.endswith(".m3u8") else "video/mp2t"
