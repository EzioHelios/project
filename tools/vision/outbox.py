# ruff: noqa: T201
"""Durable observation delivery, independent of video inference."""

from __future__ import annotations

import json
import sqlite3
from http import HTTPStatus
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from pathlib import Path

    from client import PlatformClient


class ObservationOutbox:
    def __init__(self, path: Path) -> None:
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS events (event_key TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS rejected_events (event_key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )

    def put(self, payload: dict) -> None:
        with self.db:
            self.db.execute("INSERT INTO events VALUES (?, ?)", (payload["event_key"], json.dumps(payload)))

    def deliver(self, client: PlatformClient, camera: int) -> None:
        for key, raw in self.db.execute("SELECT event_key, payload FROM events ORDER BY rowid").fetchall():
            try:
                result = client.data("POST", f"/api/vision/cameras/{camera}/observations", json=json.loads(raw))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != HTTPStatus.CONFLICT:
                    print(json.dumps({"delivery_pending": key, "error": exc.response.status_code}), flush=True)
                    return
                with self.db:
                    self.db.execute("INSERT OR REPLACE INTO rejected_events VALUES (?, ?)", (key, raw))
                    self.db.execute("DELETE FROM events WHERE event_key = ?", (key,))
                print(json.dumps({"delivery_rejected": key, "status": 409}), flush=True)
                continue
            except httpx.HTTPError as exc:
                print(json.dumps({"delivery_pending": key, "error": type(exc).__name__}), flush=True)
                return
            with self.db:
                self.db.execute("DELETE FROM events WHERE event_key = ?", (key,))
            print(
                json.dumps(
                    {
                        "observation_id": result["id"],
                        "status": result["status"],
                        "duration_seconds": result["duration_seconds"],
                    }
                ),
                flush=True,
            )

    def close(self) -> None:
        self.db.close()
