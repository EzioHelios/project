from decimal import Decimal

import pytest

from app.domain.carbon_assets.domain.policies import (
    available_balance,
    calculate_compliance_position,
    calculate_cost_result,
    validate_environmental_usage,
    validate_instrument,
    validate_movement,
    validate_settlement_line,
)


def test_instrument_units_and_compliance_are_not_interchangeable() -> None:
    validate_instrument("CEA", "tCO2e", True)
    validate_instrument("CCER", "tCO2e", True)
    validate_instrument("GREEN_CERTIFICATE", "certificate", False)
    with pytest.raises(ValueError, match="green certificates"):
        validate_instrument("GREEN_CERTIFICATE", "certificate", True)
    with pytest.raises(ValueError, match="must use"):
        validate_instrument("GREEN_CERTIFICATE", "tCO2e", False)


def test_posted_movement_direction_and_reversal_are_strict() -> None:
    validate_movement("purchase", Decimal(10))
    validate_movement("sale", Decimal(-3))
    validate_movement("reversal", Decimal(3), reversed_delta=Decimal(-3))
    with pytest.raises(ValueError, match="negative"):
        validate_movement("sale", Decimal(3))
    with pytest.raises(ValueError, match="exactly negate"):
        validate_movement("reversal", Decimal(2), reversed_delta=Decimal(-3))


def test_lot_balance_cannot_be_negative() -> None:
    assert available_balance(Decimal(10), Decimal(-4)) == Decimal(6)
    with pytest.raises(ValueError, match="negative"):
        available_balance(Decimal(10), Decimal(-11))


def test_green_certificate_usage_never_enters_compliance() -> None:
    validate_environmental_usage("GREEN_CERTIFICATE", "renewable_electricity_claim")
    with pytest.raises(ValueError, match="cannot be used for compliance"):
        validate_environmental_usage("GREEN_CERTIFICATE", "compliance")
    with pytest.raises(ValueError, match="only accepts"):
        validate_environmental_usage("CCER", "renewable_electricity_claim")


def test_compliance_settlement_keeps_instrument_purpose_strict() -> None:
    validate_settlement_line("CEA", "surrender")
    validate_settlement_line("CCER", "offset")
    with pytest.raises(ValueError, match="must be offset"):
        validate_settlement_line("CCER", "surrender")
    with pytest.raises(ValueError, match="green certificates"):
        validate_settlement_line("GREEN_CERTIFICATE", "surrender")


def test_ccer_offset_is_capped_by_rule_version() -> None:
    position = calculate_compliance_position(
        obligation_tco2e=Decimal(1000),
        cea_available_tco2e=Decimal(900),
        ccer_available_tco2e=Decimal(200),
        max_offset_ratio=Decimal("0.05"),
    )
    assert position.ccer_limit_tco2e == Decimal("50.00")
    assert position.usable_ccer_tco2e == Decimal("50.00")
    assert position.gap_tco2e == Decimal("50.00")


def test_cost_result_freezes_purchase_mix_without_unit_crossing() -> None:
    result = calculate_cost_result(
        obligation_tco2e=Decimal(1000),
        cea_balance_tco2e=Decimal(800),
        ccer_balance_tco2e=Decimal(20),
        max_offset_ratio=Decimal("0.05"),
        cea_price=Decimal(100),
        ccer_price=Decimal(60),
        safety_margin_ratio=Decimal(0),
    )
    assert result["ccerUsedTco2e"] == Decimal(20)
    assert result["ccerPurchaseTco2e"] == Decimal("30.00")
    assert result["ceaPurchaseTco2e"] == Decimal("150.00")
    assert result["totalCostCny"] == Decimal("16800.00")
