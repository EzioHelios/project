# ruff: noqa: S101, PLR2004
from tracking import MovementSegments

CONFIG = {
    "history_seconds": 1,
    "movement_threshold": 5,
    "idle_seconds": 1,
    "lost_seconds": 2,
    "min_duration_seconds": 1,
}


def detection(x: float, track_id: int = 1) -> dict:
    return {"track_id": track_id, "center": [x, 100], "confidence": 0.9}


def test_movement_then_idle_produces_one_segment() -> None:
    tracker = MovementSegments(CONFIG)
    events = []
    for t, x in enumerate([0, 10, 20, 20, 20, 20]):
        emitted, _ = tracker.update([detection(x)], t)
        events.extend(emitted)
    assert len(events) == 1
    assert events[0]["duration_seconds"] == 2
    assert events[0]["end_reason"] == "idle"
    assert events[0]["single_subject"]
    assert tracker.close("stopped") == []


def test_multiple_targets_or_lost_tracks_are_not_complete_single_subjects() -> None:
    tracker = MovementSegments(CONFIG)
    tracker.update([detection(0), detection(100, 2)], 0)
    tracker.update([detection(10), detection(110, 2)], 1)
    tracker.update([detection(20), detection(120, 2)], 2)
    events, _ = tracker.update([], 4)
    assert len(events) == 2
    assert all(not event["single_subject"] and event["end_reason"] == "left_scene" for event in events)


def test_missing_track_ids_and_short_movement_are_ignored() -> None:
    tracker = MovementSegments(CONFIG)
    assert tracker.update([detection(0, -1)], 0) == ([], set())
    assert tracker.tracks == {}
    tracker.update([detection(0)], 0)
    tracker.update([detection(10)], 0.8)
    assert tracker.close("stream_end") == []
