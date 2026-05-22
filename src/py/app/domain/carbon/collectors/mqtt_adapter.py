"""
MQTT 适配器：监听 IoT 设备主动上报数据（参考 xtck_deploy dataapp/collectors/mqtt_adapter.py）。

Topic 格式: carbon/site/{site_id}/device/{device_id}/telemetry
Payload 格式 (JSON):
  { "ts": 1707812345000, "values": { "active_power", "reactive_power", "voltage_a", "current_a", "total_energy" } }

数据写入 IotTelemetry 表。topic 内的 device_id 应与 MonitorEquipment.external_device_id 对齐；
兼容历史数据时，仍允许与 MonitorEquipment.code 对齐。paho-mqtt 为同步库，在后台线程运行；
收到消息后放入队列，由异步任务从队列取数据写入 DB。
"""
from __future__ import annotations

import json
import logging
import queue
import threading
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# 供异步消费者取数（单例队列）
_mqtt_message_queue: queue.Queue[tuple[str, str, dict]] | None = None


def get_mqtt_queue() -> queue.Queue[tuple[str, str, dict]]:
    """获取或创建全局 MQTT 消息队列。"""
    global _mqtt_message_queue
    if _mqtt_message_queue is None:
        _mqtt_message_queue = queue.Queue()
    return _mqtt_message_queue


try:
    import paho.mqtt.client as mqtt_client
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False
    mqtt_client = None  # type: ignore[assignment]


def _parse_topic(topic: str) -> tuple[str, str] | None:
    """解析 topic：carbon/site/{site_id}/device/{device_id}/telemetry -> (site_id, device_id)。"""
    parts = topic.split("/")
    if len(parts) == 6 and parts[0] == "carbon" and parts[5] == "telemetry":
        return parts[2], parts[4]
    return None


class MqttAdapter:
    """
    MQTT 监听适配器（常驻后台线程，不阻塞主进程）。
    消息放入队列，由 app 侧异步任务写入 IotTelemetry。
    """

    def __init__(self) -> None:
        from app.lib.settings import get_settings
        s = get_settings()
        self.broker_host = getattr(s, "MQTT_BROKER_HOST", "localhost")
        self.broker_port = getattr(s, "MQTT_BROKER_PORT", 1883)
        self.client_id = getattr(s, "MQTT_CLIENT_ID", "carbon_litestar_consumer")
        self.topic_root = getattr(s, "MQTT_TOPIC_ROOT", "carbon/#")
        self._client: Any = None
        self._thread: threading.Thread | None = None

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        if rc == 0:
            logger.info("MQTT 已连接至 %s:%s", self.broker_host, self.broker_port)
            client.subscribe(self.topic_root)
            logger.info("MQTT 已订阅 topic: %s", self.topic_root)
        else:
            logger.error("MQTT 连接失败，返回码：%s", rc)

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        topic = msg.topic
        parsed = _parse_topic(topic)
        if parsed is None:
            logger.warning("MQTT: 无法解析 topic %s，已跳过", topic)
            return
        site_id, device_id = parsed
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            get_mqtt_queue().put((site_id, device_id, payload))
        except (json.JSONDecodeError, Exception) as e:
            logger.error("MQTT 消息处理失败 [%s]: %s", topic, e)

    def _on_disconnect(self, client: Any, userdata: Any, rc: int) -> None:
        if rc != 0:
            logger.warning("MQTT 意外断开 (rc=%s)，将自动重连...", rc)

    def start_background(self) -> None:
        """在后台守护线程中启动 MQTT loop。"""
        if not PAHO_AVAILABLE:
            logger.warning("paho-mqtt 未安装，跳过 MQTT 监听。请安装 paho-mqtt。")
            return

        def _run() -> None:
            self._client = mqtt_client.Client(client_id=self.client_id)
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.on_disconnect = self._on_disconnect
            self._client.reconnect_delay_set(min_delay=5, max_delay=60)
            try:
                self._client.connect(self.broker_host, self.broker_port, keepalive=60)
                self._client.loop_forever()
            except Exception as e:
                logger.error("MQTT 启动失败：%s", e)

        self._thread = threading.Thread(target=_run, name="mqtt-listener", daemon=True)
        self._thread.start()
        logger.info("MQTT 后台监听线程已启动")

    def stop(self) -> None:
        """停止监听。"""
        if self._client:
            self._client.disconnect()
            logger.info("MQTT 已断开")


async def save_telemetry_from_payload(
    session_factory: Any,
    site_id: str,
    device_id: str,
    payload: dict,
) -> None:
    """将单条 MQTT 遥测写入 IotTelemetry（异步，由消费者调用）。"""
    from app.domain.carbon.models import IotTelemetry
    ts = payload.get("ts", 0)
    values = payload.get("values") or {}
    reading_time = datetime.fromtimestamp(ts / 1000.0) if ts else datetime.utcnow()
    async with session_factory() as session:
        row = IotTelemetry(
            site_id=site_id,
            device_id=device_id,
            ts=int(ts),
            reading_time=reading_time,
            active_power=values.get("active_power"),
            reactive_power=values.get("reactive_power"),
            voltage_a=values.get("voltage_a"),
            current_a=values.get("current_a"),
            total_energy=values.get("total_energy"),
            interval="raw",
            raw_payload=payload,
        )
        session.add(row)
        await session.commit()
    logger.debug("MQTT 数据已写入: %s/%s total_energy=%s", site_id, device_id, values.get("total_energy"))
