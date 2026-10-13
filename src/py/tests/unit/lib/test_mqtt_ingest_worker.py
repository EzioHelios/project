from __future__ import annotations

import builtins

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


def test_mqtt_worker_does_not_import_reporting_or_forecasting(monkeypatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith(("app.domain.carbon_verification", "app.domain.microgrid", "docx")):
            msg = f"MQTT worker must not load {name}"
            raise AssertionError(msg)
        return original_import(name, *args, **kwargs)

    monkeypatch.setenv("SAQ_WORKER_QUEUE", "mqtt-ingest")
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    worker.saq_worker_settings.cache_clear()
    try:
        config = worker.saq_worker_settings()
        assert config["queue"].name == "mqtt-ingest"
        assert len(config["functions"]) == 2
    finally:
        worker.saq_worker_settings.cache_clear()
