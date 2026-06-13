from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import date

STUDY_STATUSES = {"draft", "active", "calculated", "archived"}
RESULT_STATUSES = {"not_calculated", "no_inventory", "incomplete_inventory", "calculated"}
BOUNDARY_TYPES = {"cradle_to_gate", "cradle_to_grave", "gate_to_gate"}
ALLOCATION_METHODS = {"physical", "economic", "mass", "energy", "none"}
ACTIVITY_TYPES = {"material", "energy", "transport", "process", "waste", "supplier_pcf", "other"}


def validate_study_payload(payload: dict[str, Any]) -> None:
    required = {"study_code", "study_name", "product_code", "standard_code", "period_start", "period_end"}
    for key in required:
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)
    if not payload.get("functional_unit") and not payload.get("declared_unit"):
        msg = "functional_unit or declared_unit is required"
        raise ValueError(msg)
    if payload["period_end"] < payload["period_start"]:
        msg = "period_end must be later than period_start"
        raise ValueError(msg)
    validate_study_status(str(payload.get("status") or "draft"))
    validate_boundary_type(str(payload.get("boundary_type") or "cradle_to_gate"))


def validate_study_status(status: str) -> None:
    if status not in STUDY_STATUSES:
        msg = f"unsupported study status: {status}"
        raise ValueError(msg)


def validate_boundary_type(boundary_type: str) -> None:
    if boundary_type not in BOUNDARY_TYPES:
        msg = f"unsupported boundary type: {boundary_type}"
        raise ValueError(msg)


def validate_stage_payload(payload: dict[str, Any]) -> None:
    for key in ("study_id", "stage_code", "stage_name"):
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)


def validate_inventory_payload(payload: dict[str, Any]) -> None:
    for key in ("study_id", "item_no", "activity_type", "item_name"):
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)
    activity_type = str(payload.get("activity_type") or "other")
    if activity_type not in ACTIVITY_TYPES:
        msg = f"unsupported activity type: {activity_type}"
        raise ValueError(msg)
    ratio = _decimal_or_default(payload.get("allocation_ratio"), Decimal(1))
    if ratio <= 0 or ratio > 1:
        msg = "allocation_ratio must be greater than 0 and no more than 1"
        raise ValueError(msg)


def validate_allocation_payload(payload: dict[str, Any]) -> None:
    for key in ("study_id", "process_name"):
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)
    method = str(payload.get("allocation_method") or "physical")
    if method not in ALLOCATION_METHODS:
        msg = f"unsupported allocation method: {method}"
        raise ValueError(msg)
    ratio = _decimal_or_default(payload.get("ratio"), Decimal(1))
    if ratio <= 0 or ratio > 1:
        msg = "ratio must be greater than 0 and no more than 1"
        raise ValueError(msg)


def inventory_calc_status(payload: dict[str, Any]) -> str:
    if payload.get("included") is False:
        return "excluded"
    if payload.get("supplier_pcf_value") not in (None, ""):
        return "ready"
    if payload.get("activity_amount") in (None, ""):
        return "incomplete_activity"
    if payload.get("factor_value") in (None, "") and payload.get("factor_id") in (None, ""):
        return "pending_factor"
    return "ready"


def result_status(inventory_count: int, missing_count: int) -> str:
    if inventory_count <= 0:
        return "no_inventory"
    if missing_count > 0:
        return "incomplete_inventory"
    return "calculated"


def validate_period_range(period_start: date, period_end: date) -> None:
    if period_end < period_start:
        msg = "period_end must be later than period_start"
        raise ValueError(msg)


def _decimal_or_default(value: Any, default: Decimal) -> Decimal:
    if value in (None, ""):
        return default
    return Decimal(str(value))
