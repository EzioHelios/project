"""Independent showcase tenant specification tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.demo.showcase.builder import ACTIVITY_SERIES, AREAS, EQUIPMENT, ShowcaseDemoBuilder
from app.demo.showcase.market_data import PUBLIC_MARKET_QUOTES
from app.domain.carbon_assets.domain.policies import NATIVE_UNITS
from app.domain.carbon_assets.usecases.reference import REFERENCE_INSTRUMENTS
from app.domain.microgrid.domain.scada import validate_scada_scene, warehouse_microgrid_scada_scene


@pytest.mark.unit
def test_showcase_resource_catalog_has_expected_granularity() -> None:
    assert len(AREAS) == 10
    assert len(EQUIPMENT) == 19
    assert {item.code for item in AREAS} >= {"ROOT", "AUTO_WH", "COLD_WH", "SORTING", "ENERGY"}
    assert all(item.parent_code is None or item.parent_code in {area.code for area in AREAS} for item in AREAS)


@pytest.mark.unit
def test_showcase_activity_catalog_covers_scopes_and_iso_categories() -> None:
    assert {item.scope for item in ACTIVITY_SERIES} == {"scope1", "scope2", "scope3"}
    assert {item.iso_category.split(".", 1)[0] for item in ACTIVITY_SERIES} == {"1", "2", "3", "4", "5", "6"}
    assert all(item.factor > 0 and item.base_amount > 0 for item in ACTIVITY_SERIES)


@pytest.mark.unit
def test_showcase_monthly_values_are_deterministic_and_trending() -> None:
    electricity = next(item for item in ACTIVITY_SERIES if item.code == "C21-ELECTRICITY")
    first = ShowcaseDemoBuilder._monthly_amount(electricity, year=2024, month=1)
    repeated = ShowcaseDemoBuilder._monthly_amount(electricity, year=2024, month=1)
    later_year = ShowcaseDemoBuilder._monthly_amount(electricity, year=2026, month=1)

    assert first == repeated
    assert later_year > first * Decimal("1.03")


@pytest.mark.unit
def test_showcase_carbon_asset_catalog_has_standard_instruments() -> None:
    assert {item["instrument_class"] for item in REFERENCE_INSTRUMENTS} == {
        "CEA",
        "CCER",
        "GREEN_CERTIFICATE",
    }
    assert all(item["native_unit"] == NATIVE_UNITS[str(item["instrument_class"])] for item in REFERENCE_INSTRUMENTS)
    green_certificate = next(item for item in REFERENCE_INSTRUMENTS if item["instrument_class"] == "GREEN_CERTIFICATE")
    assert green_certificate["compliance_eligible"] is False


@pytest.mark.unit
def test_showcase_market_quotes_are_public_observations() -> None:
    assert len(PUBLIC_MARKET_QUOTES) == 22
    assert {item.instrument_code for item in PUBLIC_MARKET_QUOTES} == {
        "CEA-NATIONAL",
        "CCER-NATIONAL",
        "GREEN-CERTIFICATE-CN",
    }
    assert all(item.source_url.startswith("https://") for item in PUBLIC_MARKET_QUOTES)
    assert all(item.close_price > 0 and item.published_at.date() >= item.trade_date for item in PUBLIC_MARKET_QUOTES)
    green_quotes = [item for item in PUBLIC_MARKET_QUOTES if item.instrument_code == "GREEN-CERTIFICATE-CN"]
    assert all(item.source_version == "monthly-average-vintage-2025-v1" for item in green_quotes)
    assert all(item.open_price is None and item.high_price is None and item.low_price is None for item in green_quotes)


@pytest.mark.unit
def test_showcase_microgrid_scene_is_generic_and_electrically_valid() -> None:
    scene = warehouse_microgrid_scada_scene()
    labels = " ".join(str(node.get("label", "")) for node in scene["nodes"])
    asset_codes = {str(node["assetCode"]) for node in scene["nodes"] if node.get("assetCode")}

    assert validate_scada_scene(scene) == []
    assert asset_codes == {"PCC", "PV-01", "BESS-01", "EVSE-GROUP", "LIGHTING", "WAREHOUSE"}
    assert "祥泰" not in labels
