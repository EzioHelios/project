"""Projection semantics for climate-governance charts."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.climate_governance.queries.overview import ClimateGovernanceQueryService

pytestmark = pytest.mark.unit


def test_partial_year_inventory_becomes_forecast_not_annual_actual() -> None:
    target = SimpleNamespace(
        baseline_year=2024,
        baseline_value=Decimal(1000),
        target_year=2030,
        reduction_pct=Decimal(42),
    )
    rows = [
        {"year": 2024, "totalTco2e": 1000.0, "isFullYear": True},
        {"year": 2025, "totalTco2e": 920.0, "isFullYear": True},
        {"year": 2026, "totalTco2e": 620.0, "annualizedTco2e": 930.0, "isFullYear": False},
    ]

    trajectory = ClimateGovernanceQueryService._trajectory(rows, target, 2026)
    by_year = {item["period"]: item for item in trajectory}

    assert by_year["2026"]["actual"] is None
    assert by_year["2026"]["forecast"] == 930.0
    assert by_year["2025"]["forecast"] == 920.0
    assert by_year["2030"]["reference"] == 580.0
