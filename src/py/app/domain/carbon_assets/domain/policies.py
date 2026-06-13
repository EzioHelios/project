from __future__ import annotations

from decimal import Decimal
from typing import Any

ASSET_TYPES = {"quota", "ccer", "green_certificate", "carbon_credit"}
ACCOUNT_STATUSES = {"active", "suspended", "closed"}
PERIOD_STATUSES = {"open", "locked", "closed"}
CREDIT_STATUSES = {"active", "expired", "used", "frozen"}
TRANSACTION_TYPES = {"buy", "sell", "transfer", "offset"}
SURRENDER_STATUSES = {"draft", "completed", "cancelled"}


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
