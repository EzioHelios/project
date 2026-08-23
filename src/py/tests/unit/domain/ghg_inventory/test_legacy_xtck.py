from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.domain.ghg_inventory.usecases.legacy_xtck import map_legacy_activity


@pytest.mark.parametrize(
    ("table_name", "row", "category", "amount", "unit"),
    [
        (
            "dataapp_scope1mobilecombustion",
            {"id": 1, "record_date": date(2024, 1, 2), "amount": Decimal("12.5"), "unit": "L"},
            "1.2",
            Decimal("12.5"),
            "L",
        ),
        (
            "dataapp_scope2electricitybill",
            {"id": 2, "billing_month": "2024-02", "total_kwh": Decimal(300)},
            "2.1",
            Decimal(300),
            "kWh",
        ),
        (
            "dataapp_scope3thirdpartytransport",
            {
                "id": 3,
                "created_at": datetime(2024, 3, 1, 8, tzinfo=UTC),
                "distance_km": Decimal(100),
                "load_ton": Decimal("2.5"),
            },
            "3.1",
            Decimal(250),
            "t·km",
        ),
    ],
)
def test_map_legacy_activity_to_canonical_category(
    table_name: str,
    row: dict[str, object],
    category: str,
    amount: Decimal,
    unit: str,
) -> None:
    spec = map_legacy_activity(table_name, row)

    assert spec is not None
    assert spec.iso_category_code == category
    assert spec.activity_amount == amount
    assert spec.activity_unit == unit


def test_map_legacy_electricity_uses_calendar_month_and_location_method() -> None:
    spec = map_legacy_activity(
        "dataapp_scope2electricitybill",
        {"id": 9, "billing_month": "2024-02", "total_kwh": Decimal(1)},
    )

    assert spec is not None
    assert spec.period_start == date(2024, 2, 1)
    assert spec.period_end == date(2024, 2, 29)
    assert spec.payload["scope2_method"] == "location"


def test_map_legacy_transport_requires_traceable_date() -> None:
    spec = map_legacy_activity(
        "dataapp_scope3thirdpartytransport",
        {"id": 3, "distance_km": Decimal(100), "load_ton": Decimal("2.5")},
    )

    assert spec is None
