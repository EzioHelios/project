from __future__ import annotations

from app.domain.iot_ingestion.infrastructure import _reason_code_is_failure
from app.lib import worker
from app.lib.settings import get_settings


def test_mqtt_ingest_queue_is_dedicated_and_serial() -> None:
    queue_configs = {config.name: config for config in get_settings().saq.get_config().queue_configs}

    queue = queue_configs["mqtt-ingest"]

    assert queue.concurrency == 1
    assert queue.separate_process is True
    assert {task.__name__ for task in queue.tasks} == {
        "ingest_mqtt_message",
        "retry_pending_mqtt_messages",
    }


def test_standalone_worker_can_select_mqtt_ingest_queue(monkeypatch) -> None:
    monkeypatch.setenv("SAQ_WORKER_QUEUE", "mqtt-ingest")
    worker.saq_worker_settings.cache_clear()

    config = worker.saq_worker_settings()

    assert config["queue"].name == "mqtt-ingest"
    assert config["concurrency"] == 1
    assert {item[0] for item in config["functions"]} == {
        "iot.ingest_mqtt_message",
        "iot.retry_pending_mqtt_messages",
    }
    worker.saq_worker_settings.cache_clear()


def test_mqtt_callback_reason_code_supports_paho_v2_objects() -> None:
    class ReasonCode:
        def __init__(self, is_failure: bool) -> None:
            self.is_failure = is_failure

    assert _reason_code_is_failure(ReasonCode(False)) is False
    assert _reason_code_is_failure(ReasonCode(True)) is True
    assert _reason_code_is_failure(0) is False
    assert _reason_code_is_failure(1) is True
