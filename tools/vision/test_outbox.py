# ruff: noqa: S101
"""Exercise committed delivery state across process restarts and request failures."""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from outbox import ObservationOutbox


def test_pending_survives_reopen_and_success_keeps_event_identity(tmp_path: Path) -> None:
    path = tmp_path / "camera.sqlite"
    payload = {"event_key": "session:track:1", "config_revision": 7}
    first = ObservationOutbox(path)
    first.put(payload)
    first.close()
    reopened = ObservationOutbox(path)
    calls = []

    def accept(method: str, url: str, **kwargs: object) -> dict:
        calls.append((method, url, kwargs["json"]))
        return {"id": 3, "status": "pending", "duration_seconds": 2}

    reopened.deliver(SimpleNamespace(data=accept), 42)
    reopened.deliver(SimpleNamespace(data=accept), 42)
    assert calls == [("POST", "/api/vision/cameras/42/observations", payload)]
    assert reopened.db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
    reopened.close()


@pytest.mark.parametrize("status", [None, 401, 403, 500, 503])
def test_network_or_server_failure_keeps_committed_payload(tmp_path: Path, status: int | None) -> None:
    path = tmp_path / "camera.sqlite"
    payload = {"event_key": "stable:1", "config_revision": 2}
    outbox = ObservationOutbox(path)
    outbox.put(payload)

    def fail(*_args: object, **_kwargs: object) -> None:
        if status is None:
            raise httpx.ConnectError("offline")
        response = httpx.Response(status, request=httpx.Request("POST", "http://platform/observations"))
        response.raise_for_status()

    outbox.deliver(SimpleNamespace(data=fail), 42)
    outbox.close()
    restarted = ObservationOutbox(path)
    assert json.loads(restarted.db.execute("SELECT payload FROM events").fetchone()[0]) == payload
    restarted.close()


def test_rejected_payload_is_retained_but_not_retried(tmp_path: Path) -> None:
    path = tmp_path / "camera.sqlite"
    payload = {"event_key": "disabled:1", "config_revision": 1}
    outbox = ObservationOutbox(path)
    outbox.put(payload)

    def reject(*_args: object, **_kwargs: object) -> None:
        httpx.Response(409, request=httpx.Request("POST", "http://platform/observations")).raise_for_status()

    outbox.deliver(SimpleNamespace(data=reject), 42)
    outbox.close()
    restarted = ObservationOutbox(path)
    assert restarted.db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
    assert json.loads(restarted.db.execute("SELECT payload FROM rejected_events").fetchone()[0]) == payload
    restarted.close()
