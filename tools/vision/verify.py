# ruff: noqa: T201
"""Verify actual live preview, stored observations and tenant isolation over HTTP."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from http import HTTPStatus
from pathlib import Path

from client import PlatformClient


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:18101")
    parser.add_argument("--tenant", default="woheng-taizhou-production-base")
    parser.add_argument("--camera", type=int, required=True)
    parser.add_argument("--observation", type=int, required=True)
    parser.add_argument("--output", type=Path, default=Path(".storage/vision/verification.json"))
    args = parser.parse_args()
    client = PlatformClient(args.api, args.tenant)
    dashboard_path = f"/api/vision/dashboard?camera_id={args.camera}"
    preview_path = f"/api/vision/cameras/{args.camera}/preview"
    first = client.data("GET", dashboard_path)
    camera = next(row for row in first["cameras"] if row["id"] == args.camera)
    require(camera["state"]["status"] == "running", "Recognition worker is not running")
    image = client.http.get(preview_path)
    image.raise_for_status()
    require(image.headers["content-type"].startswith("image/jpeg"), "Preview must be a real JPEG")
    before_hash = hashlib.sha256(image.content).hexdigest()
    time.sleep(4)
    second = client.data("GET", dashboard_path)
    next_camera = next(row for row in second["cameras"] if row["id"] == args.camera)
    image2 = client.http.get(preview_path)
    image2.raise_for_status()
    after_hash = hashlib.sha256(image2.content).hexdigest()
    require(before_hash != after_hash, "Live preview has not changed")
    require(
        next_camera["state"]["frames_processed"] > camera["state"]["frames_processed"],
        "Inference frame counter has not advanced",
    )
    require(bool(second["observations"]), "No recognized observations")
    # Attaching the same observation must return its existing draft operation.
    linked = client.data("POST", f"/api/vision/observations/{args.observation}/attach")
    require(linked["status"] == "linked", "Observation did not produce an operation")
    again = client.data("POST", f"/api/vision/observations/{args.observation}/attach")
    require(again["operation_id"] == linked["operation_id"], "Confirmation was not idempotent")
    operations = client.data("GET", "/api/material-allocation/operations?material_code=VISION-WHEEL-RIM")
    operation = next(row for row in operations["items"] if row["id"] == linked["operation_id"])
    require(operation["source_system"] == "vision", "Operation provenance is missing")
    require(operation["material_code"] == linked["material_code"], "Material binding differs from observation")
    cameras = client.request("GET", "/api/data/video-monitors")["items"]
    require(
        all("recognition_preview" not in row and "recognition_config" not in row for row in cameras),
        "Camera list leaks private recognition fields",
    )
    teams = client.request("GET", "/api/teams?limit=200")["items"]
    other = next(row for row in teams if row["id"] != client.tenant_id)
    response = client.http.get(preview_path, headers={"X-Team-Id": other["id"]})
    require(response.status_code == HTTPStatus.NOT_FOUND, "Cross-tenant camera access was not rejected")
    client.http.cookies.clear()
    require(bool(client.data("GET", dashboard_path)), "Automatic session renewal failed")
    result = {
        "tenant": args.tenant,
        "camera_id": args.camera,
        "live_preview_changed": True,
        "inference_frames": [camera["state"]["frames_processed"], next_camera["state"]["frames_processed"]],
        "observations": second["summary"],
        "attached_observation": linked,
        "operation": operation,
        "idempotent_attachment": True,
        "cross_tenant_status": response.status_code,
        "session_renewal": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(json.dumps({"result": "passed", "output": str(args.output), "operation_id": linked["operation_id"]}))
    client.http.close()


if __name__ == "__main__":
    main()
