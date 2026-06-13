from __future__ import annotations

from datetime import date
from typing import Any

ACTIVE_STATUSES = {"active", "draft", "published", "locked"}
BOUNDARY_METHODS = {"operational_control", "financial_control", "equity_share"}
BOUNDARY_STATUSES = {"draft", "published", "superseded", "archived"}
FACILITY_TYPES = {"enterprise", "area", "equipment", "other"}
PERIOD_STATUSES = {"draft", "locked", "archived"}


def validate_period_range(period_start: date, period_end: date) -> None:
    if period_end < period_start:
        msg = "报告期结束日期不能早于开始日期"
        raise ValueError(msg)


def validate_boundary_method(value: str) -> None:
    if value not in BOUNDARY_METHODS:
        msg = "组织边界方法不支持"
        raise ValueError(msg)


def validate_boundary_status(value: str) -> None:
    if value not in BOUNDARY_STATUSES:
        msg = "边界状态不支持"
        raise ValueError(msg)


def validate_period_status(value: str) -> None:
    if value not in PERIOD_STATUSES:
        msg = "报告期状态不支持"
        raise ValueError(msg)


def validate_facility(data: dict[str, Any]) -> None:
    facility_type = str(data.get("facility_type") or "area")
    if facility_type not in FACILITY_TYPES:
        msg = "边界设施类型不支持"
        raise ValueError(msg)
    included = bool(data.get("included", True))
    if not included and not str(data.get("exclusion_reason") or "").strip():
        msg = "排除边界设施必须填写排除原因"
        raise ValueError(msg)
    valid_from = data.get("valid_from")
    valid_to = data.get("valid_to")
    if isinstance(valid_from, date) and isinstance(valid_to, date) and valid_to < valid_from:
        msg = "边界设施有效期结束日期不能早于开始日期"
        raise ValueError(msg)

