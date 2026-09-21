# ruff: noqa: T201
"""Verify independent playback and recognition against a running demo camera and Worker."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

import httpx
from client import PlatformClient

TS_PACKET_BYTES = 188


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:18101")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--other-tenant", required=True)
    parser.add_argument("--camera", type=int, required=True)
    parser.add_argument("--output", type=Path, default=Path(".storage/vision/playback-verification.json"))
    args = parser.parse_args()
    client = PlatformClient(args.api, args.tenant)
    base = f"/api/vision/cameras/{args.camera}"
    report = {"camera_id": args.camera, "tenant": args.tenant, "started_at": datetime.now(UTC).isoformat()}

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    def configure(enabled: bool) -> None:
        config = client.data("GET", f"{base}/config")
        for key in ("equipment_name", "equipment_code", "area_name", "area_code"):
            config.pop(key, None)
        config["enabled"] = enabled
        client.data("PUT", f"{base}/config", json=config)

    def snapshot() -> dict:
        data = client.data("GET", f"/api/vision/dashboard?camera_id={args.camera}")
        camera = next(row for row in data["cameras"] if row["id"] == args.camera)
        return {"count": data["summary"]["observations"], "state": camera["state"]}

    def media() -> dict:
        master = client.http.get(f"{base}/stream/index.m3u8")
        master.raise_for_status()
        playlist = next(line for line in master.text.splitlines() if line and not line.startswith("#"))
        response = client.http.get(f"{base}/stream/{playlist}")
        response.raise_for_status()
        lines = response.text.splitlines()
        segment = [line for line in lines if line and not line.startswith("#")][-1]
        video = client.http.get(f"{base}/stream/{segment}")
        video.raise_for_status()
        require(len(video.content) > TS_PACKET_BYTES, "Video segment is empty")
        return {"segment": segment, "sha256": hashlib.sha256(video.content).hexdigest(), "bytes": len(video.content)}

    def verify_idle(label: str) -> None:
        configure(False)
        before, stream_before = snapshot(), media()
        time.sleep(10)
        after, stream_after = snapshot(), media()
        require(after["count"] == before["count"], "Events increased while recognition was disabled")
        require(after["state"]["status"] == "disabled", "Disabled state was overwritten")
        require(stream_after["segment"] != stream_before["segment"], "Video sequence did not advance")
        require(stream_after["sha256"] != stream_before["sha256"], "Video segments did not change")
        report[label] = {"before": before, "after": after, "media_before": stream_before, "media_after": stream_after}

    def verify_enabled(label: str) -> None:
        initial = snapshot()["count"]
        configure(True)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            current = snapshot()
            if current["count"] > initial and current["state"].get("frames_processed", 0) > 0:
                report[label] = {"initial_count": initial, "result": current, "media": media()}
                return
            time.sleep(2)
        raise AssertionError("Worker did not resume inference and produce a real observation")

    try:
        verify_idle("initial_disabled")
        verify_enabled("first_enabled")
        verify_idle("disabled_after_inference")
        verify_enabled("resumed_same_worker")
        verify_idle("final_disabled")
        with httpx.Client(base_url=args.api, trust_env=False) as anonymous:
            status = anonymous.get(f"{base}/stream/index.m3u8").status_code
            require(status in (401, 403), "Anonymous video access was not rejected")
            report["anonymous_status"] = status
        other = PlatformClient(args.api, args.other_tenant)
        try:
            status = other.http.get(f"{base}/stream/index.m3u8").status_code
            require(status == HTTPStatus.NOT_FOUND, "Cross-tenant video access was not rejected")
            report["other_tenant_status"] = status
        finally:
            other.http.close()
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["failure"] = str(exc)
        raise
    finally:
        try:
            configure(False)
        finally:
            client.http.close()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
            print(json.dumps({"status": report.get("status"), "report": str(args.output)}))


if __name__ == "__main__":
    main()
