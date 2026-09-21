"""Time-based movement segmentation for stable, camera-local track IDs."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import hypot


@dataclass
class Track:
    history: deque = field(default_factory=deque)
    last_seen: float = 0
    started: float | None = None
    last_moving: float = 0
    confidence: float = 1
    single_subject: bool = True
    sequence: int = 0
    last_finished: float = 0


class MovementSegments:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.tracks: dict[int, Track] = {}
        self.sequence = 0

    def update(self, detections: list[dict], timestamp: float) -> tuple[list[dict], set[int]]:
        events = []
        working = set()
        for detection in detections:
            track_id = detection["track_id"]
            if track_id < 0:
                continue
            track = self.tracks.setdefault(track_id, Track())
            track.last_seen = timestamp
            track.history.append((timestamp, detection["center"]))
            while len(track.history) > 1 and track.history[1][0] <= timestamp - self.config["history_seconds"]:
                track.history.popleft()
            first_time, first = track.history[0]
            current = detection["center"]
            moving = (
                timestamp - first_time >= self.config["history_seconds"] * 0.75
                and hypot(current[0] - first[0], current[1] - first[1]) >= self.config["movement_threshold"]
            )
            if moving:
                if track.started is None:
                    self.sequence += 1
                    track.sequence = self.sequence
                    track.started = max(first_time, track.last_finished)
                    track.confidence = detection["confidence"]
                    track.single_subject = len(detections) == 1
                track.last_moving = timestamp
                working.add(track_id)
            if track.started is not None:
                track.confidence = min(track.confidence, detection["confidence"])
                track.single_subject = track.single_subject and len(detections) == 1
                if not moving and timestamp - track.last_moving >= self.config["idle_seconds"]:
                    event = self.finish(track_id, "idle")
                    if event:
                        events.append(event)
        for track_id, track in list(self.tracks.items()):
            if timestamp - track.last_seen >= self.config["lost_seconds"]:
                event = self.finish(track_id, "left_scene")
                if event:
                    events.append(event)
                del self.tracks[track_id]
        return events, working

    def finish(self, track_id: int, reason: str) -> dict | None:
        track = self.tracks[track_id]
        if track.started is None:
            return None
        started = track.started
        track.started = None
        duration = track.last_moving - started
        track.last_finished = track.last_moving
        if duration < self.config["min_duration_seconds"]:
            return None
        return {
            "track_id": track_id,
            "sequence": track.sequence,
            "started": started,
            "ended": track.last_moving,
            "duration_seconds": duration,
            "confidence": track.confidence,
            "single_subject": track.single_subject,
            "end_reason": reason,
        }

    def close(self, reason: str) -> list[dict]:
        return [event for track_id in self.tracks if (event := self.finish(track_id, reason))]
