from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import msgspec
import pytest

from app.domain.ghg_inventory.domain.allocation import validate_allocation, validate_allocation_ratios
from app.domain.ghg_inventory.domain.calculation import calculate
from app.domain.ghg_inventory.domain.catalog import CATEGORIES, METHODS, category_payload
from app.domain.ghg_inventory.models import GhgCalculationResult
from app.domain.ghg_inventory.queries.analytics import GhgAnalyticsQueryService
from app.domain.ghg_inventory.queries.inventory import GhgInventoryQueryService
from app.domain.ghg_inventory.schemas import GhgAnalyticsBreakdownItemResponse, GhgCalculationRunListResponse
from app.domain.ghg_inventory.usecases.calculation import _build_summary

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


def test_scope2_summary_keeps_location_and_market_totals_separate() -> None:
    def result(scope: str, method: str, value: str, category: str) -> GhgCalculationResult:
        return GhgCalculationResult(
            run_id=1,
            activity_id=len(value),
            method_id=1,
            iso_category_code=category,
            ghg_scope=scope,
            gas_code="CO2",
            gas_mass_kg=Decimal(value),
            gwp_value=Decimal(1),
            gwp_version="AR6",
            co2e_kg=Decimal(value),
            scope2_method=method,
            result_kind="emission",
            formula_snapshot={},
            quality_status="pass",
        )

    summary = _build_summary(
        [
            result("scope1", "not_applicable", "100", "1.1"),
            result("scope2", "location", "50", "2.1"),
            result("scope2", "market", "30", "2.1"),
            result("scope3", "not_applicable", "20", "4.1"),
        ],
        default_scope2_method="location",
    )

    assert summary["defaultTotalCo2eKg"] == "170"
    assert summary["totalLocationCo2eKg"] == "170"
    assert summary["totalMarketCo2eKg"] == "150"
    assert summary["scopeTotals"] == {"scope1": "100", "scope2": "50", "scope3": "20"}
    assert summary["isoCategoryTotals"] == {"1.1": "100", "2.1": "50", "4.1": "20"}


def test_analytics_query_payload_matches_msgspec_co2e_field_aliases() -> None:
    breakdown = GhgAnalyticsQueryService._finalize_breakdown(
        {
            "scope1": {
                "code": "scope1",
                "name": "Scope 1",
                "value": Decimal("120.5"),
                "records": {"R-1"},
                "warnings": set(),
                "evidence": {"R-1"},
            }
        },
        Decimal("120.5"),
    )
    assert breakdown[0]["valueCo2EKg"] == "120.5"
    msgspec.convert(breakdown, type=list[GhgAnalyticsBreakdownItemResponse])

    run = SimpleNamespace(
        run_code="RUN-1",
        inventory_code="INV-1",
        status="completed",
        reporting_org_id=1,
        reporting_period_id=2,
        organization_boundary_id=3,
        default_scope2_method="location",
        total_co2e_kg=Decimal("120.5"),
        quality_snapshot={},
        started_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00+00:00"),
        completed_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:01:00+00:00"),
    )
    profile = SimpleNamespace(code="CORPORATE", name="组织盘查")
    organization = SimpleNamespace(name="示例组织")
    period = SimpleNamespace(name="2026年度")
    boundary = SimpleNamespace(boundary_name="运营控制边界")
    item = GhgAnalyticsQueryService._run_list_item(
        cast("Any", run),
        cast("Any", profile),
        cast("Any", organization),
        cast("Any", period),
        cast("Any", boundary),
    )
    assert item["totalCo2EKg"] == "120.5"
    msgspec.convert({"items": [item], "total": 1}, type=GhgCalculationRunListResponse)


def test_flow_source_identity_groups_monthly_records_by_business_source() -> None:
    purchased_result = cast("Any", SimpleNamespace(iso_category_code="2.2"))
    january = cast("Any", SimpleNamespace(activity_name="外购蒸汽", source_payload={}))
    february = cast("Any", SimpleNamespace(activity_name="外购蒸汽", source_payload={}))
    january_source = cast("Any", SimpleNamespace(source_name="外购蒸汽", source_code="STEAM-202601"))
    february_source = cast("Any", SimpleNamespace(source_name="外购蒸汽", source_code="STEAM-202602"))

    january_identity = GhgAnalyticsQueryService._flow_source_identity(purchased_result, january, january_source)
    february_identity = GhgAnalyticsQueryService._flow_source_identity(purchased_result, february, february_source)

    assert january_identity == february_identity
    assert january_identity[1] == "外购蒸汽"

    transport_result = cast("Any", SimpleNamespace(iso_category_code="3.1"))
    transport_payload = {
        "transport_mode": "transport_heavy_truck",
        "origin": "仓储中心",
        "destination": "客户仓",
    }
    transport_january = cast(
        "Any", SimpleNamespace(activity_name="第三方运输 TMS-202601", source_payload=transport_payload)
    )
    transport_february = cast(
        "Any", SimpleNamespace(activity_name="第三方运输 TMS-202602", source_payload=transport_payload)
    )

    assert GhgAnalyticsQueryService._flow_source_identity(transport_result, transport_january, None) == (
        GhgAnalyticsQueryService._flow_source_identity(transport_result, transport_february, None)
    )

    waste_result = cast("Any", SimpleNamespace(iso_category_code="4.4"))
    waste_activity = cast("Any", SimpleNamespace(activity_name="waste_municipal_incineration", source_payload={}))
    waste_identity = GhgAnalyticsQueryService._flow_source_identity(waste_result, waste_activity, None)
    assert waste_identity[1] == "生活垃圾焚烧"
    assert waste_identity[2] == {"keyword": "waste_municipal_incineration"}

    forklift_result = cast("Any", SimpleNamespace(iso_category_code="1.2"))
    forklift_january = cast("Any", SimpleNamespace(activity_name="仓储叉车 1", source_payload={}))
    forklift_february = cast("Any", SimpleNamespace(activity_name="仓储叉车 2", source_payload={}))
    assert GhgAnalyticsQueryService._flow_source_identity(forklift_result, forklift_january, None) == (
        GhgAnalyticsQueryService._flow_source_identity(forklift_result, forklift_february, None)
    )
