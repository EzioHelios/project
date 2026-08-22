from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from app.domain.ghg_inventory.domain.allocation import validate_allocation, validate_allocation_ratios
from app.domain.ghg_inventory.domain.calculation import calculate
from app.domain.ghg_inventory.domain.catalog import CATEGORIES, METHODS, category_payload
from app.domain.ghg_inventory.queries.inventory import GhgInventoryQueryService

if TYPE_CHECKING:
    from app.domain.ghg_inventory.models import GhgActivityRecord


def test_catalog_has_complete_iso_and_ghgp_crosswalk() -> None:
    assert len(CATEGORIES) == 24
    assert {category.code for category in CATEGORIES} == {
        "1.1",
        "1.2",
        "1.3",
        "1.4",
        "1.5",
        "2.1",
        "2.2",
        "3.1",
        "3.2",
        "3.3",
        "3.4",
        "3.5",
        "4.1",
        "4.2",
        "4.3",
        "4.4",
        "4.5",
        "5.1",
        "5.2",
        "5.3",
        "5.4",
        "5.5",
        "5.6",
        "6.1",
    }
    assert {category.scope3_category for category in CATEGORIES if category.scope3_category} == set(range(1, 16))
    assert {method.family for method in METHODS} == {f"F{index:02d}" for index in range(1, 12)}


def test_category_catalog_and_activity_projection_share_business_fields() -> None:
    purchased_electricity = next(category for category in CATEGORIES if category.code == "2.1")
    field_codes = {field["code"] for field in category_payload(purchased_electricity)["activityFields"]}
    assert field_codes == {"energy_type", "supplier_name", "meter_point", "scope2_method", "market_instrument"}

    activity = SimpleNamespace(
        iso_category_code="2.1",
        source_payload={
            "energy_type": "electricity",
            "supplier_name": "电网企业",
            "meter_point": "PCC-01",
            "scope2_method": "location",
            "method_code": "F08_PURCHASED_ENERGY",
            "source_definition": {"source_code": "PCC-01"},
        },
    )
    assert GhgInventoryQueryService.activity_details(cast("GhgActivityRecord", activity)) == {
        "energy_type": "electricity",
        "supplier_name": "电网企业",
        "meter_point": "PCC-01",
        "scope2_method": "location",
    }


def test_activity_allocation_requires_complete_ratios_and_rejects_internal_equipment_for_transport() -> None:
    validate_allocation_ratios([Decimal("0.4"), Decimal("0.6")])
    with pytest.raises(ValueError, match="100%"):
        validate_allocation_ratios([Decimal("0.4"), Decimal("0.5")])
    with pytest.raises(ValueError, match="内部设备"):
        validate_allocation(
            category_code="3.1",
            role="responsibility",
            area_present=True,
            equipment_present=True,
            external_present=True,
        )


@pytest.mark.parametrize(
    ("method_code", "activity", "parameters", "payload", "expected"),
    [
        (
            "F01_NCV",
            Decimal(10),
            {"NCV": Decimal(40), "CARBON_CONTENT": Decimal("0.02"), "OXIDATION_FACTOR": Decimal(1)},
            {},
            Decimal("29333.33333333333333333333333"),
        ),
        (
            "F02_EF",
            Decimal(12),
            {"EMISSION_FACTOR": Decimal("2.5"), "UNIT_CONVERSION": Decimal("0.001"), "GWP": Decimal(28)},
            {"gas_code": "CH4"},
            Decimal("0.8400"),
        ),
        (
            "F05_INVENTORY",
            Decimal(0),
            {
                "OPENING_STOCK": Decimal(100),
                "PURCHASES": Decimal(20),
                "CHARGES": Decimal(10),
                "CLOSING_STOCK": Decimal(90),
                "TRANSFERS": Decimal(5),
                "RECOVERY": Decimal(3),
                "GWP": Decimal(1430),
            },
            {"gas_code": "HFC-134a"},
            Decimal(45760),
        ),
        (
            "F08_PURCHASED_ENERGY",
            Decimal(1000),
            {"ENERGY_FACTOR": Decimal("0.55")},
            {"scope2_method": "location"},
            Decimal("550.00"),
        ),
        ("F09_DISTANCE", Decimal(125), {"DISTANCE_FACTOR": Decimal("0.2")}, {}, Decimal("25.0")),
        (
            "F09_TRANSPORT_ACTIVITY",
            Decimal(240),
            {"TRANSPORT_FACTOR": Decimal("0.08")},
            {},
            Decimal("19.20"),
        ),
    ],
)
def test_p0_calculators_are_deterministic(
    method_code: str,
    activity: Decimal,
    parameters: dict[str, Decimal],
    payload: dict[str, str],
    expected: Decimal,
) -> None:
    assert calculate(method_code, activity, parameters, payload).co2e_kg == expected


def test_unpublished_method_cannot_execute() -> None:
    with pytest.raises(ValueError, match="尚未发布"):
        calculate("F10_VALUE_CHAIN", Decimal(1), {}, {})


def test_fugitive_inventory_rejects_negative_balance() -> None:
    with pytest.raises(ValueError, match="不能为负数"):
        calculate(
            "F05_INVENTORY",
            Decimal(0),
            {
                "OPENING_STOCK": Decimal(1),
                "PURCHASES": Decimal(0),
                "CHARGES": Decimal(0),
                "CLOSING_STOCK": Decimal(2),
                "TRANSFERS": Decimal(0),
                "RECOVERY": Decimal(0),
                "GWP": Decimal(1),
            },
            {},
        )
