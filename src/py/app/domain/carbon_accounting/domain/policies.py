from __future__ import annotations

from typing import Any

BATCH_STATUSES = {"draft", "rebuilt", "pending_revision", "rejected", "locked", "archived"}
INVENTORY_STATUSES = {"empty", "ready", "issues", "locked"}
READY_CALC_STATUS = "ready"


def validate_batch_status(value: str) -> None:
    if value not in BATCH_STATUSES:
        msg = "核算批次状态不支持"
        raise ValueError(msg)


def inventory_quality(computation: dict[str, Any], *, included: bool) -> str:
    if not included:
        return "excluded"
    if computation.get("computed_co2e") is None:
        return "missing_result"
    if computation.get("calc_status") != READY_CALC_STATUS:
        return "calculation_issue"
    return "ready"


def inventory_status(*, missing_result_count: int) -> str:
    return "issues" if missing_result_count > 0 else "ready"
