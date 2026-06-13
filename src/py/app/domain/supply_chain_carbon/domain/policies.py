from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import date

SUPPLIER_STATUSES = {"active", "suspended", "archived"}
RISK_LEVELS = {"low", "medium", "high"}
TASK_STATUSES = {"draft", "issued", "submitted", "needs_revision", "approved", "rejected", "expired"}
TASK_TYPES = {"scope3_activity", "product_pcf", "mixed"}
DATA_TYPES = {"activity", "pcf"}
DATA_STATUSES = {"draft", "submitted", "approved", "rejected", "expired"}
EVIDENCE_STATUSES = {"pending", "accepted", "rejected"}
DECISIONS = {"submit", "approve", "reject", "request_revision"}


def validate_supplier(payload: dict[str, Any]) -> None:
    for key in ("supplier_code", "name"):
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)
    status = str(payload.get("status") or "active")
    if status not in SUPPLIER_STATUSES:
        msg = f"unsupported supplier status: {status}"
        raise ValueError(msg)
    risk = str(payload.get("risk_level") or "medium")
    if risk not in RISK_LEVELS:
        msg = f"unsupported risk level: {risk}"
        raise ValueError(msg)


def validate_site(payload: dict[str, Any]) -> None:
    for key in ("supplier_id", "site_code", "site_name"):
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)


def validate_task(payload: dict[str, Any]) -> None:
    for key in ("task_no", "task_name", "supplier_id", "period_start", "period_end"):
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)
    validate_period(payload["period_start"], payload["period_end"])
    task_type = str(payload.get("task_type") or "mixed")
    if task_type not in TASK_TYPES:
        msg = f"unsupported task type: {task_type}"
        raise ValueError(msg)
    status = str(payload.get("status") or "draft")
    if status not in TASK_STATUSES:
        msg = f"unsupported task status: {status}"
        raise ValueError(msg)


def validate_carbon_data(payload: dict[str, Any]) -> None:
    for key in ("task_id", "data_no", "data_type"):
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)
    data_type = str(payload.get("data_type") or "activity")
    if data_type not in DATA_TYPES:
        msg = f"unsupported data type: {data_type}"
        raise ValueError(msg)
    if data_type == "activity" and payload.get("activity_amount") in (None, "") and payload.get("co2e_amount") in (None, ""):
        msg = "activity data requires activity_amount or co2e_amount"
        raise ValueError(msg)
    if data_type == "pcf" and payload.get("pcf_value") in (None, ""):
        msg = "pcf data requires pcf_value"
        raise ValueError(msg)
    if payload.get("validity_start") and payload.get("validity_end"):
        validate_period(payload["validity_start"], payload["validity_end"])


def validate_evidence(payload: dict[str, Any]) -> None:
    for key in ("task_id", "evidence_no", "evidence_type", "file_name"):
        if payload.get(key) in (None, ""):
            msg = f"{key} is required"
            raise ValueError(msg)
    status = str(payload.get("review_status") or "pending")
    if status not in EVIDENCE_STATUSES:
        msg = f"unsupported evidence status: {status}"
        raise ValueError(msg)


def ensure_task_transition(current: str, decision: str, *, reason: str | None = None) -> str:
    if decision not in DECISIONS:
        msg = f"unsupported decision: {decision}"
        raise ValueError(msg)
    if decision == "submit":
        if current not in {"draft", "issued", "needs_revision", "rejected"}:
            msg = "task cannot be submitted from current status"
            raise ValueError(msg)
        return "submitted"
    if current != "submitted":
        msg = "task must be submitted before review"
        raise ValueError(msg)
    if decision == "approve":
        return "approved"
    if decision == "reject":
        if not reason:
            msg = "reject reason is required"
            raise ValueError(msg)
        return "rejected"
    if decision == "request_revision":
        if not reason:
            msg = "revision reason is required"
            raise ValueError(msg)
        return "needs_revision"
    return current


def data_status_for_task(task_status: str) -> str:
    if task_status == "approved":
        return "approved"
    if task_status in {"rejected", "needs_revision"}:
        return "rejected"
    if task_status == "expired":
        return "expired"
    if task_status == "submitted":
        return "submitted"
    return "draft"


def risk_level_from_ratio(value: Decimal | None, benchmark: Decimal | None) -> str:
    if value is None or benchmark in (None, Decimal(0)):
        return "medium"
    ratio = value / benchmark
    if ratio >= Decimal("1.3"):
        return "high"
    if ratio >= Decimal("1.1"):
        return "medium"
    return "low"


def validate_period(period_start: date, period_end: date) -> None:
    if period_end < period_start:
        msg = "period_end must be later than period_start"
        raise ValueError(msg)
