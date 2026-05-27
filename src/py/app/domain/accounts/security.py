"""Authentication security helpers for login risk and human verification."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from http import HTTPStatus
from typing import Any

import httpx
import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.lib.settings import get_settings

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def get_security_redis() -> Redis:
    """Return a shared Redis client for auth security state."""
    settings = get_settings()
    return Redis.from_url(settings.saq.REDIS_URL, encoding="utf-8", decode_responses=True)


@dataclass(slots=True)
class LoginRiskService:
    """Track login failures and CAPTCHA escalation state in Redis."""

    redis: Redis
    threshold: int
    window_seconds: int
    block_seconds: int

    @staticmethod
    def _normalize_ip(ip_address: str | None) -> str:
        return ip_address or "unknown"

    @staticmethod
    def _normalize_username(username: str) -> str:
        return username.strip().lower()

    def _key(self, username: str, ip_address: str | None) -> str:
        raw = f"{self._normalize_username(username)}:{self._normalize_ip(ip_address)}"
        suffix = hashlib.sha256(raw.encode()).hexdigest()
        return f"auth:login-risk:{suffix}"

    async def get_failure_count(self, username: str, ip_address: str | None) -> int:
        """Return the current failure count for a login tuple."""
        try:
            value = await self.redis.get(self._key(username, ip_address))
        except (RedisError, RuntimeError) as exc:  # pragma: no cover - defensive fallback
            logger.warning("login risk lookup failed, falling back to no throttling", error=str(exc))
            return 0
        return int(value or 0)

    async def requires_human_verification(self, username: str, ip_address: str | None) -> bool:
        """Return whether the login tuple must pass human verification."""
        return await self.get_failure_count(username, ip_address) >= self.threshold

    async def record_failure(self, username: str, ip_address: str | None) -> int:
        """Increment failure count and extend the rolling window."""
        key = self._key(username, ip_address)
        try:
            failure_count = int(await self.redis.incr(key))
            ttl = self.block_seconds if failure_count > self.threshold else self.window_seconds
            await self.redis.expire(key, ttl)
        except (RedisError, RuntimeError) as exc:  # pragma: no cover - defensive fallback
            logger.warning("login risk update failed, falling back to no throttling", error=str(exc))
            return 0
        return failure_count

    async def clear_failures(self, username: str, ip_address: str | None) -> None:
        """Clear any recorded failures after a successful login."""
        try:
            await self.redis.delete(self._key(username, ip_address))
        except (RedisError, RuntimeError) as exc:  # pragma: no cover - defensive fallback
            logger.warning("login risk reset failed, ignoring", error=str(exc))


@dataclass(slots=True)
class HumanVerificationResult:
    """Normalized result from a human verification provider."""

    verified: bool
    verification_data: dict[str, Any] | None = None
    reason: str | None = None


@dataclass(slots=True)
class AltchaSentinelProvider:
    """Verify ALTCHA Sentinel payloads via the Sentinel HTTP API."""

    verify_url: str
    api_key: str

    async def verify(self, payload: str, request_origin: str | None = None) -> HumanVerificationResult:
        """Verify the base64 payload returned by the ALTCHA widget."""
        headers = {"Content-Type": "application/json"}
        if request_origin:
            headers["Referer"] = request_origin
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(self.verify_url, json={"payload": payload}, headers=headers)

        if response.status_code != HTTPStatus.OK:
            return HumanVerificationResult(verified=False, reason=f"verification_http_{response.status_code}")

        payload_data = response.json()
        return HumanVerificationResult(
            verified=bool(payload_data.get("verified")),
            verification_data=payload_data.get("verificationData"),
            reason=None if payload_data.get("verified") else str(payload_data.get("error") or "verification_failed"),
        )


def provide_login_risk_service() -> LoginRiskService:
    """Provide the login risk service."""
    settings = get_settings().app
    return LoginRiskService(
        redis=get_security_redis(),
        threshold=settings.LOGIN_RISK_THRESHOLD,
        window_seconds=settings.LOGIN_RISK_WINDOW_SECONDS,
        block_seconds=settings.LOGIN_RISK_BLOCK_SECONDS,
    )


def provide_human_verification_provider() -> AltchaSentinelProvider | None:
    """Provide the configured human verification provider, if enabled."""
    settings = get_settings().app
    if not settings.altcha_enabled or not settings.altcha_verify_url:
        return None
    return AltchaSentinelProvider(verify_url=settings.altcha_verify_url, api_key=settings.ALTCHA_SENTINEL_API_KEY)
