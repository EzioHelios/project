# ruff: noqa: T201
"""Read a configured RTSP source, run YOLO/ByteTrack and durably deliver observations."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import signal
import threading
import time
from contextlib import suppress
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from uuid import uuid4

import cv2
import httpx
from client import PlatformClient
from outbox import ObservationOutbox
from tracking import MovementSegments

CONFIG_POLL_SECONDS = 3


class LatestFrame:
    def __init__(self, url: str) -> None:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        self.capture = cv2.VideoCapture(
            url, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000]
        )
        if not self.capture.isOpened():
            raise RuntimeError("Configured RTSP source could not be opened")
        self.latest = None
        self.sequence = 0
        self.running = True
        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()

    def read(self) -> None:
        while self.running:
            ok, frame = self.capture.read()
            if not ok:
                self.running = False
                return
            self.sequence += 1
            self.latest = (self.sequence, time.time(), frame)

    def close(self) -> None:
        self.running = False
        self.thread.join(timeout=6)
        if not self.thread.is_alive():
            self.capture.release()


def run_session(args: argparse.Namespace, client: PlatformClient, config: dict, stopped: threading.Event) -> None:  # noqa: C901
    from ultralytics import YOLO

    base = f"/api/vision/cameras/{args.camera}"
    model = YOLO(str(args.model))
    if model.names != {0: "forklift"} or config["equipment_type"] != "forklift":
        raise ValueError("This worker requires the forklift detector and a forklift camera configuration")
    model_version = f"forklift-{hashlib.sha256(args.model.read_bytes()).hexdigest()[:16]}"
    args.spool.mkdir(parents=True, exist_ok=True)
    spool = ObservationOutbox(args.spool / f"{client.tenant_id}-{args.camera}.sqlite")
    session_id = uuid4().hex
    segmenter = MovementSegments(config)
    frames = 0
    preview = None
    evidence_by_track = {}

    def deliver() -> None:
        spool.deliver(client, args.camera)

    def save(events: list[dict]) -> None:
        for event in events:
            track_id = event["track_id"]
            sequence = event.pop("sequence")
            payload = {
                **event,
                "event_key": f"{session_id}:{track_id}:{sequence}",
                "session_id": session_id,
                "started_at": datetime.fromtimestamp(event.pop("started"), UTC).isoformat(),
                "ended_at": datetime.fromtimestamp(event.pop("ended"), UTC).isoformat(),
                "config_revision": config["revision"],
                "model_version": model_version,
                "evidence_jpeg": evidence_by_track.get(track_id, preview),
            }
            payload.pop("started", None)
            payload.pop("ended", None)
            spool.put(payload)

    def heartbeat(status: str, count: int = 0, working: int = 0, message: str = "") -> None:
        client.request(
            "POST",
            f"{base}/heartbeat",
            json={
                "session_id": session_id,
                "config_revision": config["revision"],
                "status": status,
                "timestamp": datetime.now(UTC).isoformat(),
                "detected_count": count,
                "working_count": working,
                "frames_processed": frames,
                "model_version": model_version,
                "message": message,
                "preview_jpeg": preview,
            },
        )

    reader = None
    end_reason = "stopped"
    try:
        heartbeat("running")
        deliver()
        reader = LatestFrame(config["rtsp_url"])
        started = time.monotonic()
        last_sequence = 0
        last_heartbeat = 0
        last_config_check = 0
        while not stopped.is_set() and (not args.duration or time.monotonic() - started < args.duration):
            item = reader.latest
            if not reader.running:
                end_reason = "stream_end"
                break
            if item is None or item[0] == last_sequence:
                time.sleep(0.02)
                continue
            last_sequence, timestamp, frame = item
            height, width = frame.shape[:2]
            frame = cv2.resize(frame, (640, max(1, round(height * 640 / width))))
            result = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=config["confidence_threshold"],
                device=args.device,
                verbose=False,
            )[0]
            detections = []
            if result.boxes is not None and result.boxes.id is not None:
                for box, track, confidence in zip(
                    result.boxes.xywh.cpu().tolist(),
                    result.boxes.id.int().cpu().tolist(),
                    result.boxes.conf.cpu().tolist(),
                    strict=True,
                ):
                    detections.append({"track_id": track, "center": box[:2], "confidence": confidence})
            events, working = segmenter.update(detections, timestamp)
            annotated = result.plot()
            cv2.putText(
                annotated,
                f"Targets {len(detections)} | Moving {len(working)}",
                (12, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )
            ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                preview = base64.b64encode(encoded).decode()
                for detection in detections:
                    evidence_by_track[detection["track_id"]] = preview
            frames += 1
            save(events)
            evidence_by_track = {key: value for key, value in evidence_by_track.items() if key in segmenter.tracks}
            now = time.monotonic()
            if now - last_heartbeat >= 1:
                try:
                    heartbeat("running", len(detections), len(working))
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == HTTPStatus.CONFLICT:
                        end_reason = "config_changed"
                        break
                    print(json.dumps({"heartbeat_error": exc.response.status_code}), flush=True)
                except httpx.TransportError:
                    print(json.dumps({"heartbeat_error": "connection_unavailable"}), flush=True)
                deliver()
                last_heartbeat = now
            if now - last_config_check >= CONFIG_POLL_SECONDS:
                with suppress(httpx.HTTPError):
                    updated = client.data("GET", f"{base}/config")
                    if args.health_file:
                        args.health_file.touch()
                    if updated["revision"] != config["revision"] or not updated["enabled"]:
                        end_reason = "config_changed"
                        break
                last_config_check = now
            time.sleep(0.04)
    except Exception as exc:
        end_reason = "stream_end"
        with suppress(httpx.HTTPError):
            heartbeat("error", message=f"识别服务异常: {type(exc).__name__}")
        raise
    finally:
        save(segmenter.close(end_reason))
        deliver()
        if reader:
            reader.close()
        with suppress(httpx.HTTPError):
            if end_reason == "stopped":
                heartbeat("stopped")
            elif end_reason == "stream_end":
                heartbeat("error", message="视频流已中断")
        spool.close()
        print(json.dumps({"frames_processed": frames, "end_reason": end_reason}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:18101")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--camera", type=int, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=0)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--spool", type=Path, default=Path(".storage/vision"))
    parser.add_argument("--health-file", type=Path)
    args = parser.parse_args()
    if not args.model.is_file():
        raise ValueError("Recognition model file does not exist")
    if config_directory := os.environ.get("YOLO_CONFIG_DIR"):
        Path(config_directory).mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(1)
    stopped = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopped.set())
    client = PlatformClient(args.api, args.tenant)
    try:
        while not stopped.is_set():
            config = client.data("GET", f"/api/vision/cameras/{args.camera}/config")
            if args.health_file:
                args.health_file.touch()
            if config.get("enabled"):
                run_session(args, client, config, stopped)
                if args.duration:
                    break
            stopped.wait(CONFIG_POLL_SECONDS)
    finally:
        client.http.close()


if __name__ == "__main__":
    main()
