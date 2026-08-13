"""System status schemas."""

from __future__ import annotations

from typing import Literal

from app.__metadata__ import __version__
from app.lib.schema import CamelizedBaseStruct


class SystemHealth(CamelizedBaseStruct, kw_only=True):
    app: str
    database_status: Literal["online", "offline"] = "offline"
    version: str = __version__


class OAuthConfig(CamelizedBaseStruct, kw_only=True):
    """OAuth provider configuration for frontend."""

    google_enabled: bool = False
    github_enabled: bool = False


class PublicAppConfig(CamelizedBaseStruct, kw_only=True):
    """Public application configuration for frontend display."""

    display_name: str
    short_name: str
    description: str
    brand_mark_url: str | None = None
    favicon_url: str | None = None
    auth_mode: str = "cookie-session"
    captcha_provider: str | None = None
    captcha_enabled: bool = False
    captcha_challenge_url: str | None = None
    captcha_site_key: str | None = None
