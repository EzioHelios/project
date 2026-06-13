from __future__ import annotations

from dataclasses import dataclass
from typing import Any

WARNING_RATE_PCT = 90.0
EXCEEDED_RATE_PCT = 100.0


@dataclass(frozen=True, slots=True)
class BudgetProgress:
    budget: float | None
    actual: float | None
    denominator: float | None = None


def execution_rate_pct(actual: Any, budget: Any) -> float | None:
    budget_value = _float_or_none(budget)
    if budget_value is None or budget_value <= 0:
        return None
    return round(float(actual or 0) / budget_value * 100, 4)


def intensity(actual: Any, denominator: Any) -> float | None:
    denominator_value = _float_or_none(denominator)
    if denominator_value is None or denominator_value <= 0:
        return None
    return round(float(actual or 0) / denominator_value, 6)


def execution_status(rate_pct: float | None, has_budget: bool, has_actual: bool) -> str:
    if not has_budget:
        return "missing_budget"
    if not has_actual:
        return "no_actual"
    if rate_pct is None:
        return "invalid_budget"
    if rate_pct > EXCEEDED_RATE_PCT:
        return "exceeded"
    if rate_pct >= WARNING_RATE_PCT:
        return "warning"
    return "ok"


def forecast_value(actual_to_date: Any, elapsed_months: int, total_months: int) -> float | None:
    if elapsed_months <= 0 or total_months <= 0:
        return None
    return round(float(actual_to_date or 0) / elapsed_months * total_months, 6)


def forecast_status(forecast_rate_pct: float | None, has_budget: bool) -> str:
    if not has_budget:
        return "missing_budget"
    if forecast_rate_pct is None:
        return "no_actual"
    if forecast_rate_pct > EXCEEDED_RATE_PCT:
        return "forecast_exceeded"
    if forecast_rate_pct >= WARNING_RATE_PCT:
        return "forecast_warning"
    return "ok"


def recommendation_for(row: dict[str, Any]) -> dict[str, Any] | None:
    energy_status = row.get("energy_status")
    carbon_status = row.get("carbon_status")
    target = row.get("period") or row.get("plan_name") or "预算对象"
    if energy_status == "exceeded" or carbon_status == "exceeded":
        return {
            "code": "budget-exceeded-review",
            "priority": "high",
            "title": "复核超预算月份",
            "target": target,
            "evidence": {
                "energy_rate_pct": row.get("energy_execution_rate_pct"),
                "carbon_rate_pct": row.get("carbon_execution_rate_pct"),
            },
            "action": "核对实际数据、锁定高耗能对象, 并发起预算调整或节能整改。",
        }
    if energy_status == "warning" or carbon_status == "warning":
        return {
            "code": "budget-warning-control",
            "priority": "medium",
            "title": "跟踪接近预算上限月份",
            "target": target,
            "evidence": {
                "energy_rate_pct": row.get("energy_execution_rate_pct"),
                "carbon_rate_pct": row.get("carbon_execution_rate_pct"),
            },
            "action": "压实后续月份用能计划, 优先排查峰值时段和高排放能源来源。",
        }
    if energy_status == "missing_budget" or carbon_status == "missing_budget":
        return {
            "code": "complete-budget",
            "priority": "medium",
            "title": "补齐预算目标",
            "target": target,
            "evidence": {},
            "action": "维护年度目标并生成月度分解后再执行偏差分析。",
        }
    return None


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
