"""MQTT broker runner used by the dedicated SAQ worker."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.config import alchemy
from app.db import models as m
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY

if TYPE_CHECKING:
    from saq import Queue
    from saq.types import Context


logger = logging.getLogger(__name__)
ERR_PAYLOAD_ROOT = "MQTT payload root must be a JSON object"

try:
    import paho.mqtt.client as mqtt_client

    PAHO_AVAILABLE = True
except ImportError:  # pragma: no cover - package is a runtime dependency, retained for clear startup diagnostics.
    mqtt_client = None  # type: ignore[assignment]
    PAHO_AVAILABLE = False


@dataclass(frozen=True, slots=True)
class _SubscriptionRuntime:
    team_id: str
    source_id: int
    subscription_id: int
    broker_host: str
    broker_port: int
    client_id: str
    username: str | None
    password: str | None
    tls_enabled: bool
    topic_filter: str
    qos: int


class MqttSubscriptionRunner:
    """Owns Paho clients and durably hands received payloads to the SAQ MQTT queue."""

    def __init__(self, queue: Queue) -> None:
        self._queue = queue
        self._clients: list[Any] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        if not PAHO_AVAILABLE:
            logger.error("paho-mqtt 未安装, MQTT 接入 worker 不会订阅任何 Broker。")
            return
        self._loop = asyncio.get_running_loop()
        runtimes = await _load_enabled_runtimes()
        for runtime in runtimes:
            self._start_client(runtime)
        logger.info("MQTT 接入订阅运行器已启动: subscriptions=%s", len(self._clients))

    async def stop(self) -> None:
        for client in self._clients:
            client.loop_stop()
            client.disconnect()
        self._clients.clear()

    def _start_client(self, runtime: _SubscriptionRuntime) -> None:
        client = mqtt_client.Client(
            mqtt_client.CallbackAPIVersion.VERSION2,
            client_id=runtime.client_id,
            clean_session=False,
            manual_ack=True,
        )
        if runtime.username is not None:
            client.username_pw_set(runtime.username, runtime.password)
        if runtime.tls_enabled:
            client.tls_set()
        client.user_data_set(runtime)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        client.reconnect_delay_set(min_delay=5, max_delay=60)
        client.connect_async(runtime.broker_host, runtime.broker_port, keepalive=60)
        client.loop_start()
        self._clients.append(client)

    @staticmethod
    def _on_connect(
        client: Any, runtime: _SubscriptionRuntime, _flags: Any, reason_code: Any, _properties: Any = None
    ) -> None:
        if _reason_code_is_failure(reason_code):
            logger.error("MQTT 连接失败: source_id=%s code=%s", runtime.source_id, reason_code)
            return
        client.subscribe(runtime.topic_filter, qos=runtime.qos)
        logger.info("MQTT 已订阅: source_id=%s topic=%s", runtime.source_id, runtime.topic_filter)

    def _on_message(self, client: Any, runtime: _SubscriptionRuntime, message: Any) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(
            asyncio.create_task,
            self._enqueue_then_ack(client, runtime, message),
        )

    @staticmethod
    def _on_disconnect(
        _client: Any, runtime: _SubscriptionRuntime, _flags: Any, reason_code: Any, _properties: Any = None
    ) -> None:
        if _reason_code_is_failure(reason_code):
            logger.warning("MQTT 意外断开, 将重连: source_id=%s code=%s", runtime.source_id, reason_code)

    async def _enqueue_then_ack(self, client: Any, runtime: _SubscriptionRuntime, message: Any) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            payload = _require_payload_object(payload)
            await self._queue.enqueue(
                "iot.ingest_mqtt_message",
                team_id=runtime.team_id,
                source_id=runtime.source_id,
                subscription_id=runtime.subscription_id,
                topic=message.topic,
                payload=payload,
            )
        except Exception:
            logger.exception("MQTT message handoff failed: source_id=%s topic=%s", runtime.source_id, message.topic)
            return
        if message.qos:
            client.ack(message.mid, message.qos)


async def on_mqtt_ingest_startup(ctx: Context) -> None:
    """Start broker subscriptions only in the dedicated MQTT queue worker."""
    worker = ctx["worker"]
    runner = MqttSubscriptionRunner(worker.queue)
    await runner.start()
    ctx["mqtt_subscription_runner"] = runner


async def on_mqtt_ingest_shutdown(ctx: Context) -> None:
    """Stop broker subscriptions before the dedicated worker exits."""
    runner = ctx.get("mqtt_subscription_runner")
    if isinstance(runner, MqttSubscriptionRunner):
        await runner.stop()


async def _load_enabled_runtimes() -> list[_SubscriptionRuntime]:
    async with alchemy.get_session() as session:
        session.info[TENANT_BYPASS_SESSION_KEY] = True
        rows = (
            await session.execute(
                select(m.MqttDataSource, m.MqttSubscription)
                .join(m.MqttSubscription, m.MqttSubscription.source_id == m.MqttDataSource.id)
                .where(m.MqttDataSource.enabled.is_(True), m.MqttSubscription.enabled.is_(True))
            )
        ).all()
    runtimes: list[_SubscriptionRuntime] = []
    for source, subscription in rows:
        username = os.getenv(source.username_env) if source.username_env else None
        password = os.getenv(source.password_env) if source.password_env else None
        if source.username_env and username is None:
            logger.error("MQTT 数据源缺少用户名环境变量: source_id=%s env=%s", source.id, source.username_env)
            continue
        if source.password_env and password is None:
            logger.error("MQTT 数据源缺少密码环境变量: source_id=%s env=%s", source.id, source.password_env)
            continue
        runtimes.append(
            _SubscriptionRuntime(
                team_id=str(source.team_id),
                source_id=source.id,
                subscription_id=subscription.id,
                broker_host=source.broker_host,
                broker_port=source.broker_port,
                client_id=f"{source.client_id}-{subscription.id}",
                username=username,
                password=password,
                tls_enabled=source.tls_enabled,
                topic_filter=subscription.topic_filter,
                qos=subscription.qos,
            )
        )
    return runtimes


def _require_payload_object(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise TypeError(ERR_PAYLOAD_ROOT)
    return payload


def _reason_code_is_failure(reason_code: object) -> bool:
    """Support Paho callback API v2 `ReasonCode` and the numeric v1 callback value."""
    failure = getattr(reason_code, "is_failure", None)
    if failure is not None:
        return bool(failure)
    return bool(reason_code)
