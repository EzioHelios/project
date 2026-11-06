from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.metering import projection


def test_projection_monitor_limits_job_growth_not_worker_baseline(monkeypatch) -> None:
    readings = iter([1300.0, 1340.0, 1410.0])
    monkeypatch.setattr(projection, "_current_rss_mb", lambda: next(readings))
    monkeypatch.setattr(projection, "_peak_rss_mb", lambda: 1500.0)
    monkeypatch.setenv("METERING_PROJECTION_RSS_MB", "100")
    monitor = projection.ProjectionMonitor(uuid4(), "2026-11")

    monitor.check("read", 10)

    with pytest.raises(projection.ProjectionBudgetExceededError, match="growth budget exceeded"):
        monitor.check("write", 20)
