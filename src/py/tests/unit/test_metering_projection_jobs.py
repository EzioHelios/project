from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.metering.jobs import pending_projection_months
from app.domain.metering.projection import ElectricityProjectionUseCase, ReadingSample
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.unit]


async def test_only_new_or_late_readings_are_pending():
    session = AsyncMock()
    readings = MagicMock()
    readings.all.return_value = [("2026-10", 20), ("2026-09", 16), ("2026-08", 8)]
    session.execute.return_value = readings
    runs = MagicMock()
    runs.all.return_value = [
        SimpleNamespace(period_start=datetime(2026, 10, 1, tzinfo=UTC), source_high_watermark="20", run_config={}),
        SimpleNamespace(
            period_start=datetime(2026, 9, 1, tzinfo=UTC), source_high_watermark="16", run_config={"area_id": "A"}
        ),
        SimpleNamespace(period_start=datetime(2026, 9, 1, tzinfo=UTC), source_high_watermark="15", run_config={}),
    ]
    session.scalars.return_value = runs
    assert await pending_projection_months(session) == ["2026-09", "2026-08"]


@pytest.mark.parametrize(
    ("sources", "expected"),
    [(("mqtt", "mqtt"), "measured"), (("demo_seed", "mqtt"), "simulated"), (("mqtt", "demo_seed"), "simulated")],
)
async def test_projection_retains_simulated_provenance(sources, expected):
    session = AsyncMock()
    session.info = {TENANT_ID_SESSION_KEY: uuid4()}
    equipment = SimpleNamespace(id=1, code="METER", sector_id=1)
    area = SimpleNamespace(code="AREA", name="Area")
    samples = [
        ReadingSample(
            fact=SimpleNamespace(
                id=index + 1,
                reading_time=datetime(2026, 10, 1, 0, index * 15, tzinfo=UTC),
                normalized_value=Decimal(index + 1),
                source_system=source,
                quality_status="valid",
            ),
            equipment=equipment,
            area=area,
        )
        for index, source in enumerate(sources)
    ]
    rows, issues, _ = await ElectricityProjectionUseCase(session)._calculate_intervals(samples, {}, {}, {}, {})
    assert not issues
    assert len(rows) == 1
    assert next(iter(rows.values()))["data_quality"] == expected
    assert next(iter(rows.values()))["amount"] == 1
