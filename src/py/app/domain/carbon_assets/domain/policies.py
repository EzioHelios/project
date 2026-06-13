from __future__ import annotations

from decimal import Decimal
from typing import Any

ASSET_TYPES = {"quota", "ccer", "green_certificate", "carbon_credit"}
ACCOUNT_STATUSES = {"active", "suspended", "closed"}
PERIOD_STATUSES = {"open", "locked", "closed"}
CREDIT_STATUSES = {"active", "expired", "used", "frozen"}
TRANSACTION_TYPES = {"buy", "sell", "transfer", "offset"}
SURRENDER_STATUSES = {"draft", "completed", "cancelled"}
FORECAST_SCENARIO_STATUSES = {"draft", "active", "archived"}
LOCKED_INVENTORY_STATUS = "locked"


def validate_period_payload(payload: dict[str, Any]) -> None:
    for key in ("period_code", "period_name", "period_start", "period_end"):
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)
    if payload["period_end"] < payload["period_start"]:
        msg = "履约周期结束日期不能早于开始日期"
        raise ValueError(msg)
    status = str(payload.get("status") or "open")
    if status not in PERIOD_STATUSES:
        msg = f"unsupported period status: {status}"
        raise ValueError(msg)


def validate_account_payload(payload: dict[str, Any]) -> None:
    for key in ("account_code", "account_name", "asset_type"):
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)
    asset_type = str(payload.get("asset_type"))
    if asset_type not in ASSET_TYPES:
        msg = f"unsupported asset type: {asset_type}"
        raise ValueError(msg)
    status = str(payload.get("status") or "active")
    if status not in ACCOUNT_STATUSES:
        msg = f"unsupported account status: {status}"
        raise ValueError(msg)


def validate_positive_amount(value: Decimal | None, field: str = "amount") -> None:
    if value is None or value <= 0:
        msg = f"{field} must be greater than 0"
        raise ValueError(msg)


def validate_non_negative_amount(value: Decimal | None, field: str = "amount") -> None:
    if value is None or value < 0:
        msg = f"{field} cannot be negative"
        raise ValueError(msg)


def validate_forecast_payload(payload: dict[str, Any]) -> None:
    for key in ("period_id", "scenario_code", "scenario_name"):
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)
    status = str(payload.get("status") or "draft")
    if status not in FORECAST_SCENARIO_STATUSES:
        msg = f"unsupported forecast scenario status: {status}"
        raise ValueError(msg)
    if payload.get("forecast_start") and payload.get("forecast_end") and payload["forecast_end"] < payload["forecast_start"]:
        msg = "预测结束日期不能早于开始日期"
        raise ValueError(msg)
    for field in (
        "planned_reduction",
        "planned_allowance_purchase",
        "planned_credit_purchase",
        "planned_surrender",
        "allowance_price",
        "credit_price",
    ):
        validate_non_negative_amount(_decimal(payload.get(field)), field)


def forecast_position(
    *,
    verified_emission: Decimal,
    allowance_available_value: Decimal,
    credit_available_value: Decimal,
    surrendered_amount: Decimal,
    emission_growth_rate: Decimal | None,
    planned_reduction: Decimal | None,
    planned_allowance_purchase: Decimal | None,
    planned_credit_purchase: Decimal | None,
    planned_surrender: Decimal | None,
    allowance_price: Decimal | None,
    credit_price: Decimal | None,
    yellow: Decimal | None,
    orange: Decimal | None,
    red: Decimal | None,
) -> dict[str, Decimal | str]:
    growth_rate = _decimal(emission_growth_rate)
    forecast_emission = (verified_emission * (Decimal(1) + growth_rate)) - _decimal(planned_reduction)
    if forecast_emission < 0:
        forecast_emission = Decimal(0)
    forecast_available_assets = allowance_available_value + credit_available_value + _decimal(planned_allowance_purchase) + _decimal(planned_credit_purchase)
    forecast_surrendered = surrendered_amount + _decimal(planned_surrender)
    net_position = forecast_available_assets + forecast_surrendered - forecast_emission
    gap_amount = abs(net_position) if net_position < 0 else Decimal(0)
    funding_need = (_decimal(planned_allowance_purchase) * _decimal(allowance_price)) + (_decimal(planned_credit_purchase) * _decimal(credit_price))
    return {
        "forecast_emission": forecast_emission.quantize(Decimal("0.000001")),
        "forecast_available_assets": forecast_available_assets.quantize(Decimal("0.000001")),
        "forecast_surrendered": forecast_surrendered.quantize(Decimal("0.000001")),
        "forecast_net_position": net_position.quantize(Decimal("0.000001")),
        "forecast_gap_amount": gap_amount.quantize(Decimal("0.000001")),
        "forecast_gap_rate": (gap_amount / forecast_emission).quantize(Decimal("0.000001")) if forecast_emission > 0 else Decimal(0),
        "funding_need": funding_need.quantize(Decimal("0.000001")),
        "risk_level": compliance_risk_level(gap_amount, forecast_emission, yellow, orange, red),
    }


def ensure_period_open(status: str) -> None:
    if status == "closed":
        msg = "已关闭履约周期不可新增资产或清缴记录"
        raise ValueError(msg)


def allowance_available(allocated: Decimal | None, adjustment: Decimal | None, used: Decimal | None, frozen: Decimal | None) -> Decimal:
    return _decimal(allocated) + _decimal(adjustment) - _decimal(used) - _decimal(frozen)


def credit_available(quantity: Decimal | None, used: Decimal | None, frozen: Decimal | None) -> Decimal:
    return _decimal(quantity) - _decimal(used) - _decimal(frozen)


def compliance_risk_level(
    gap_amount: Decimal,
    verified_emission: Decimal,
    yellow: Decimal | None,
    orange: Decimal | None,
    red: Decimal | None,
) -> str:
    if gap_amount <= 0:
        return "low"
    if verified_emission <= 0:
        return "medium"
    ratio = gap_amount / verified_emission
    if ratio >= _decimal(red, Decimal("0.15")):
        return "red"
    if ratio >= _decimal(orange, Decimal("0.08")):
        return "orange"
    if ratio >= _decimal(yellow, Decimal("0.03")):
        return "yellow"
    return "low"


def inventory_position_status(*, has_batch: bool, is_locked: bool, has_total: bool) -> str:
    """Return the carbon-assets data status for the bound accounting inventory."""
    if not has_batch:
        return "missing_batch"
    if not is_locked:
        return "unlocked_inventory"
    if not has_total:
        return "missing_inventory_total"
    return LOCKED_INVENTORY_STATUS


def simulate_transaction(
    amount: Decimal,
    unit_price: Decimal,
    fee_rate: Decimal | None = None,
    tax_rate: Decimal | None = None,
) -> dict[str, Decimal]:
    validate_positive_amount(amount)
    validate_non_negative_amount(unit_price, "unit_price")
    fee_rate = _decimal(fee_rate)
    tax_rate = _decimal(tax_rate)
    validate_non_negative_amount(fee_rate, "fee_rate")
    validate_non_negative_amount(tax_rate, "tax_rate")
    gross_amount = amount * unit_price
    fee_amount = gross_amount * fee_rate
    tax_amount = gross_amount * tax_rate
    total_amount = gross_amount + fee_amount + tax_amount
    unit_total_price = total_amount / amount if amount > 0 else Decimal(0)
    return {
        "gross_amount": gross_amount.quantize(Decimal("0.000001")),
        "fee_amount": fee_amount.quantize(Decimal("0.000001")),
        "tax_amount": tax_amount.quantize(Decimal("0.000001")),
        "total_amount": total_amount.quantize(Decimal("0.000001")),
        "unit_total_price": unit_total_price.quantize(Decimal("0.000001")),
    }


def _decimal(value: Decimal | None, default: Decimal | None = None) -> Decimal:
    if value is None:
        return default or Decimal(0)
    return value
