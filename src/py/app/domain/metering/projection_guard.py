"""Persistent circuit breaker scoped only to electricity projection jobs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from redis.asyncio import Redis

# Count an attempt BEFORE work begins. A killed process therefore consumes an attempt too.
CLAIM = """
if redis.call('GET', KEYS[3]) == '1' then return 'paused' end
if redis.call('EXISTS', KEYS[2]) == 1 then return 'busy' end
local attempts = tonumber(redis.call('HGET', KEYS[1], 'attempts') or '0')
if attempts >= 3 then return 'open' end
local now = tonumber(redis.call('TIME')[1])
local retry_at = tonumber(redis.call('HGET', KEYS[1], 'retry_at') or '0')
if retry_at > now then return 'cooldown' end
attempts = attempts + 1
local delay = 3600
if attempts > 1 then delay = 21600 end
redis.call('HSET', KEYS[1], 'attempts', attempts, 'retry_at', now + delay, 'status', 'running', 'token', ARGV[1])
redis.call('SET', KEYS[2], ARGV[1], 'EX', 2100)
return 'claimed'
"""
FINISH = """
if redis.call('HGET', KEYS[1], 'token') ~= ARGV[1] then return 0 end
if ARGV[2] == 'success' or ARGV[2] == 'busy' then
  if ARGV[2] == 'success' then redis.call('DEL', KEYS[1])
  else
    redis.call('HINCRBY', KEYS[1], 'attempts', -1)
    redis.call('HSET', KEYS[1], 'retry_at', 0, 'status', 'idle')
  end
else redis.call('HSET', KEYS[1], 'status', 'failed') end
if redis.call('GET', KEYS[2]) == ARGV[1] then redis.call('DEL', KEYS[2]) end
return 1
"""


class ProjectionGuard:
    def __init__(self, redis: Redis, team: str, month: str) -> None:
        self.redis = redis
        self.key = f"metering:projection:{team}:{month}"
        self.token = uuid4().hex

    async def claim(self) -> str:
        result = await cast(
            "Awaitable[Any]",
            self.redis.eval(CLAIM, 3, self.key, f"{self.key}:lease", "metering:projection:paused", self.token),
        )
        return result.decode() if isinstance(result, bytes) else str(result)

    async def finish(self, status: str) -> None:
        await cast("Awaitable[Any]", self.redis.eval(FINISH, 2, self.key, f"{self.key}:lease", self.token, status))

    async def state(self) -> dict[str, str]:
        """Read persisted breaker metadata for operational diagnostics."""
        values = await self.redis.hgetall(self.key)
        return {
            key.decode() if isinstance(key, bytes) else str(key): value.decode()
            if isinstance(value, bytes)
            else str(value)
            for key, value in values.items()
        }

    async def reset(self) -> int:
        """Remove the scoped breaker and lease after an operator-reviewed fix."""
        return int(await self.redis.delete(self.key, f"{self.key}:lease"))
