"""Authenticated platform client for recognition and verification."""

from __future__ import annotations

import os
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx


class PlatformClient:
    def __init__(self, base_url: str, tenant_slug: str) -> None:
        self.http = httpx.Client(base_url=base_url, timeout=20, trust_env=False)
        self.login()
        payload = self.request("GET", "/api/teams?limit=200")
        teams = payload["items"]
        team = next((item for item in teams if item["slug"] == tenant_slug), None)
        if team is None:
            raise ValueError(f"Tenant not found: {tenant_slug}")
        self.http.headers["X-Team-Id"] = team["id"]
        self.tenant_id = team["id"]

    def login(self) -> None:
        password_file = os.environ.get("VISION_PASSWORD_FILE")
        if not password_file:
            raise ValueError("Set VISION_PASSWORD_FILE to the platform password secret")
        password = Path(password_file).read_text().rstrip("\r\n")
        if not password:
            raise ValueError("Platform password secret is empty")
        response = self.http.post(
            "/api/access/login",
            json={"username": os.environ.get("VISION_USERNAME", "admin@example.com"), "password": password},
        )
        response.raise_for_status()
        self.http.get("/api/me").raise_for_status()

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self.http.request(method, path, **kwargs)
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            self.login()
            response = self.http.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def data(self, method: str, path: str, **kwargs: Any) -> Any:
        return self.request(method, path, **kwargs)["data"]
