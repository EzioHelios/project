# ruff: noqa: S101, PLR2004
from pathlib import Path

import httpx
import pytest
from client import PlatformClient


def test_login_and_expired_session_reread_mounted_secret(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secret = tmp_path / "password"
    secret.write_text("test-secret\n")
    monkeypatch.setenv("VISION_PASSWORD_FILE", str(secret))
    monkeypatch.setenv("VISION_USERNAME", "test@example.com")
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/teams":
            return httpx.Response(200, json={"items": [{"id": "team-one", "slug": "one"}]})
        if request.url.path == "/expire" and sum(row.url.path == "/expire" for row in requests) == 1:
            return httpx.Response(401)
        return httpx.Response(200, json={"data": True})

    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    client = PlatformClient("http://platform", "one")
    try:
        secret.write_text("rotated-secret\n")
        assert client.data("GET", "/expire") is True
        logins = [row for row in requests if row.url.path == "/api/access/login"]
        assert len(logins) == 2
        assert b"test-secret" in logins[0].content
        assert b"rotated-secret" in logins[1].content
        assert requests[-1].headers["X-Team-Id"] == "team-one"
    finally:
        client.http.close()


def test_missing_secret_has_no_password_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VISION_PASSWORD_FILE", raising=False)
    monkeypatch.setenv("VISION_PASSWORD", "not-used")
    client = PlatformClient.__new__(PlatformClient)
    with pytest.raises(ValueError, match="VISION_PASSWORD_FILE"):
        client.login()
