"""Metered-scope calculation must not admit synthetic data or changed bindings."""

import importlib.util
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

_path = Path(__file__).resolve().parents[4] / "tools/maintenance/calculate_xiangtai_meter_inventory.py"
_spec = importlib.util.spec_from_file_location("xiangtai_meter_calculation", _path)
assert _spec is not None and _spec.loader is not None
maintenance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(maintenance)
pytestmark = pytest.mark.unit


def inputs():
    activity = SimpleNamespace(
        id=1,
        inventory_code="XIANGTAI-METER-2025",
        source_system="energy_fact",
        data_source_type="measured",
        iso_category_code="2.1",
        activity_unit="kWh",
        status="draft",
        activity_amount=Decimal("23.5"),
        facility_code="P1",
        record_code="XT-1",
        reporting_period_id=12,
        period_start="2025-07-01",
        period_end="2025-07-31",
        source_payload={
            "prepared_by": maintenance.PREPARED_BY,
            "method_code": "F08_PURCHASED_ENERGY",
            "meter_point": "m1",
            "fact_ids": [1, 2],
            "fact_count": 2,
            "fact_hash": "hash",
            "missing_hours": 742,
        },
    )
    device = SimpleNamespace(id=1, code="m1", sector_id=2, is_enable=True, category=0, name="Meter")
    area = SimpleNamespace(id=2, code="P1", name="Area")
    allocation = SimpleNamespace(allocation_ratio=Decimal(1), equipment_id=1, area_id=2)
    return activity, allocation, device, area


def test_plan_does_not_approve_or_rewrite_data():
    activity, allocation, device, area = inputs()
    result = maintenance.validate_activity(activity, allocation, device, area)
    assert result["kwh"] == "23.5"
    assert result["missing_hours"] == 742
    assert activity.status == "draft"
    assert "calculated_by" not in activity.source_payload
    assert maintenance.digest(result) == maintenance.digest(dict(reversed(list(result.items()))))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_system", "demo_seed"),
        ("data_source_type", "estimated"),
        ("activity_unit", "MWh"),
        ("iso_category_code", "1.1"),
        ("activity_amount", Decimal(-1)),
        ("activity_amount", Decimal("NaN")),
        ("facility_code", "P99"),
        ("status", "archived"),
        ("inventory_code", "OTHER"),
    ],
)
def test_invalid_activity_rejected(field, value):
    activity, allocation, device, area = inputs()
    setattr(activity, field, value)
    with pytest.raises(ValueError):
        maintenance.validate_activity(activity, allocation, device, area)


@pytest.mark.parametrize("change", ["allocation", "area", "pv", "storage", "disabled", "duplicated_facts"])
def test_bindings_and_meter_selection(change):
    activity, allocation, device, area = inputs()
    if change == "allocation":
        allocation.allocation_ratio = Decimal("0.5")
    elif change == "area":
        device.sector_id = 9
    elif change == "pv":
        device.category = 1
    elif change == "storage":
        device.code = "432301227008"
    elif change == "disabled":
        device.is_enable = False
    else:
        activity.source_payload["fact_ids"] = [1, 1]
    with pytest.raises(ValueError):
        maintenance.validate_activity(activity, allocation, device, area)
