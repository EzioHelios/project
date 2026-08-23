"""Pure rules for carbon asset accounting and compliance."""

from __future__ import annotations

# ruff: noqa: EM101, EM102, TRY003
from dataclasses import dataclass
from decimal import Decimal

INSTRUMENT_CLASSES = {"CEA", "CCER", "GREEN_CERTIFICATE"}
NATIVE_UNITS = {"CEA": "tCO2e", "CCER": "tCO2e", "GREEN_CERTIFICATE": "certificate"}
COMPLIANCE_CLASSES = {"CEA", "CCER"}
MOVEMENT_TYPES = {
    "opening", "allocation", "issuance", "purchase", "sale", "transfer_in", "transfer_out",
    "freeze", "unfreeze", "surrender", "offset", "consume", "expire", "reversal",
}
POSITIVE_MOVEMENTS = {"opening", "allocation", "issuance", "purchase", "transfer_in", "unfreeze"}
NEGATIVE_MOVEMENTS = {"sale", "transfer_out", "freeze", "surrender", "offset", "consume", "expire"}


@dataclass(frozen=True, slots=True)
class CompliancePosition:
    obligation_tco2e: Decimal
    cea_available_tco2e: Decimal
    ccer_available_tco2e: Decimal
    ccer_limit_tco2e: Decimal
    usable_ccer_tco2e: Decimal
    covered_tco2e: Decimal
    gap_tco2e: Decimal


def ensure_positive(value: Decimal, field: str) -> None:
    if value <= 0:
        raise ValueError(f"{field} must be greater than zero")


def ensure_nonnegative(value: Decimal, field: str) -> None:
    if value < 0:
        raise ValueError(f"{field} cannot be negative")


def validate_instrument(instrument_class: str, native_unit: str, compliance_eligible: bool) -> None:
    if instrument_class not in INSTRUMENT_CLASSES:
        raise ValueError("unsupported instrument class")
    if native_unit != NATIVE_UNITS[instrument_class]:
        raise ValueError(f"{instrument_class} must use {NATIVE_UNITS[instrument_class]}")
    if compliance_eligible and instrument_class not in COMPLIANCE_CLASSES:
        raise ValueError("green certificates cannot be compliance instruments")


def validate_movement(movement_type: str, quantity_delta: Decimal, *, reversed_delta: Decimal | None = None) -> None:
    if movement_type not in MOVEMENT_TYPES:
        raise ValueError("unsupported movement type")
    if quantity_delta == 0:
        raise ValueError("quantity delta cannot be zero")
    if movement_type in POSITIVE_MOVEMENTS and quantity_delta < 0:
        raise ValueError("positive movement requires a positive quantity delta")
    if movement_type in NEGATIVE_MOVEMENTS and quantity_delta > 0:
        raise ValueError("outgoing movement requires a negative quantity delta")
    if movement_type == "reversal":
        if reversed_delta is None:
            raise ValueError("reversal requires the original movement")
        if quantity_delta != -reversed_delta:
            raise ValueError("reversal quantity must exactly negate the original movement")


def available_balance(issued_quantity: Decimal, movement_total: Decimal) -> Decimal:
    balance = issued_quantity + movement_total
    if balance < 0:
        raise ValueError("movement would make the lot balance negative")
    return balance


def validate_environmental_usage(instrument_class: str, purpose: str) -> None:
    if purpose == "compliance":
        raise ValueError("environmental attribute usage cannot be used for compliance surrender")
    if instrument_class != "GREEN_CERTIFICATE":
        raise ValueError("environmental attribute usage only accepts green certificate lots")


def validate_settlement_line(instrument_class: str, purpose: str) -> None:
    expected = {"CEA": "surrender", "CCER": "offset"}.get(instrument_class)
    if expected is None:
        raise ValueError("green certificates cannot enter compliance settlement")
    if purpose != expected:
        raise ValueError(f"{instrument_class} settlement purpose must be {expected}")


def calculate_compliance_position(
    *, obligation_tco2e: Decimal, cea_available_tco2e: Decimal, ccer_available_tco2e: Decimal,
    max_offset_ratio: Decimal,
) -> CompliancePosition:
    if not Decimal(0) <= max_offset_ratio <= Decimal(1):
        raise ValueError("max offset ratio must be between zero and one")
    ccer_limit = obligation_tco2e * max_offset_ratio
    usable_ccer = min(ccer_available_tco2e, ccer_limit)
    covered = min(obligation_tco2e, cea_available_tco2e + usable_ccer)
    return CompliancePosition(
        obligation_tco2e=obligation_tco2e, cea_available_tco2e=cea_available_tco2e,
        ccer_available_tco2e=ccer_available_tco2e, ccer_limit_tco2e=ccer_limit,
        usable_ccer_tco2e=usable_ccer, covered_tco2e=covered,
        gap_tco2e=max(Decimal(0), obligation_tco2e - covered),
    )


def calculate_cost_result(
    *, obligation_tco2e: Decimal, cea_balance_tco2e: Decimal, ccer_balance_tco2e: Decimal,
    max_offset_ratio: Decimal, cea_price: Decimal, ccer_price: Decimal, safety_margin_ratio: Decimal,
) -> dict[str, Decimal]:
    target = obligation_tco2e * (Decimal(1) + safety_margin_ratio)
    ccer_limit = obligation_tco2e * max_offset_ratio
    ccer_used = min(ccer_balance_tco2e, ccer_limit, target)
    cea_used = min(cea_balance_tco2e, max(Decimal(0), target - ccer_used))
    shortage = max(Decimal(0), target - ccer_used - cea_used)
    ccer_purchase = max(Decimal(0), min(ccer_limit - ccer_used, shortage))
    cea_purchase = max(Decimal(0), shortage - ccer_purchase)
    return {
        "targetTco2e": target, "ceaUsedTco2e": cea_used, "ccerUsedTco2e": ccer_used,
        "ceaPurchaseTco2e": cea_purchase, "ccerPurchaseTco2e": ccer_purchase,
        "totalCostCny": cea_purchase * cea_price + ccer_purchase * ccer_price,
    }
