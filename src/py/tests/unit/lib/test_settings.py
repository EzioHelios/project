import pytest

from app.lib.settings import AppSettings, get_settings

pytestmark = pytest.mark.anyio


def test_app_slug() -> None:
    """Test app name conversion to slug."""
    settings = get_settings()
    settings.app.NAME = "My Application!"
    assert settings.app.slug == "my-application"


def test_app_display_config_defaults() -> None:
    """Test public display config defaults."""
    settings = AppSettings()
    assert settings.DISPLAY_NAME == "碳数据收集与管理系统"
    assert settings.SHORT_NAME == "CD"
    assert settings.DESCRIPTION == "支持 Scope 1/2/3 碳排放数据的采集、审核与统计分析。"
    assert settings.BRAND_MARK_URL == ""
    assert settings.FAVICON_URL == ""


def test_app_display_config_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test public display config can be overridden by environment variables."""
    monkeypatch.setenv("APP_DISPLAY_NAME", "内网碳管理平台")
    monkeypatch.setenv("APP_SHORT_NAME", "NW")
    monkeypatch.setenv("APP_DESCRIPTION", "内网部署版本")
    monkeypatch.setenv("APP_BRAND_MARK_URL", "/brand.svg")
    monkeypatch.setenv("APP_FAVICON_URL", "/favicon-brand.ico")

    settings = AppSettings()

    assert settings.DISPLAY_NAME == "内网碳管理平台"
    assert settings.SHORT_NAME == "NW"
    assert settings.DESCRIPTION == "内网部署版本"
    assert settings.BRAND_MARK_URL == "/brand.svg"
    assert settings.FAVICON_URL == "/favicon-brand.ico"
