"""Exercise persisted circuit state against an isolated Redis service."""

import pytest
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError

from app.domain.metering.projection_guard import ProjectionGuard

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="session")
def projection_redis(docker_service):
    def ready(service):
        try:
            return Redis(host=service.host, port=service.port).ping()
        except RedisError:
            return False

    with docker_service.run(
        image="valkey/valkey:latest",
        check=ready,
        container_host="127.0.0.1",
        container_port=6379,
        name="projection-redis",
        timeout=30,
    ) as service:
        yield service


async def test_circuit_survives_death_and_does_not_affect_other_months(projection_redis):
    async with AsyncRedis(host=projection_redis.host, port=projection_redis.port) as redis:
        first = ProjectionGuard(redis, "team-a", "2026-10")
        assert await first.claim() == "claimed"
        assert await ProjectionGuard(redis, "team-a", "2026-10").claim() == "busy"
        # Simulate expiry after SIGKILL: there was no finish callback.
        await redis.delete(first.key + ":lease")
        assert await ProjectionGuard(redis, "team-a", "2026-10").claim() == "cooldown"
        await redis.hset(first.key, "retry_at", 0)
        second = ProjectionGuard(redis, "team-a", "2026-10")
        assert await second.claim() == "claimed"
        await second.finish("failed")
        await redis.hset(first.key, "retry_at", 0)
        third = ProjectionGuard(redis, "team-a", "2026-10")
        assert await third.claim() == "claimed"
        await third.finish("failed")
        assert await ProjectionGuard(redis, "team-a", "2026-10").claim() == "open"
        state = await third.state()
        assert state["attempts"] == "3"
        assert await third.reset() >= 1
        reset = ProjectionGuard(redis, "team-a", "2026-10")
        assert await reset.claim() == "claimed"
        await reset.finish("success")
        other = ProjectionGuard(redis, "team-b", "2026-10")
        assert await other.claim() == "claimed"
        await other.finish("success")
        assert await redis.exists(other.key) == 0
        await redis.set("metering:projection:paused", "1")
        assert await ProjectionGuard(redis, "team-c", "2026-10").claim() == "paused"
        await redis.delete("metering:projection:paused")
