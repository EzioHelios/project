# ruff: noqa: S608
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict
from app.domain.energy.queries.common import jsonable_mapping
from app.domain.energy_budget.domain.policies import (
    execution_rate_pct,
    execution_status,
    forecast_status,
    forecast_value,
    intensity,
    recommendation_for,
)

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class EnergyBudgetQuery:
    plan_id: int | None = None
    budget_year: int | None = None
    status: str | None = None
    target_scope: str | None = None
    target_code: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    limit: int = 50
    offset: int = 0


class EnergyBudgetQueryService:
    """Read model service for energy and carbon budgets."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def selected_plan(self, query: EnergyBudgetQuery) -> m.EnergyCarbonBudgetPlan | None:
        if query.plan_id is not None:
            return await self._session.get(m.EnergyCarbonBudgetPlan, query.plan_id)
        conditions = []
        if query.budget_year is not None:
            conditions.append(m.EnergyCarbonBudgetPlan.budget_year == query.budget_year)
        if query.status and query.status != "all":
            conditions.append(m.EnergyCarbonBudgetPlan.status == query.status)
        else:
            conditions.append(m.EnergyCarbonBudgetPlan.status.in_(("active", "approved")))
        if query.target_scope and query.target_scope != "all":
            conditions.append(m.EnergyCarbonBudgetPlan.target_scope == query.target_scope)
        if query.target_code:
            conditions.append(m.EnergyCarbonBudgetPlan.target_code == query.target_code)
        return await self._session.scalar(
            select(m.EnergyCarbonBudgetPlan).where(*conditions).order_by(m.EnergyCarbonBudgetPlan.id.desc()).limit(1)
        )

    async def progress(self, query: EnergyBudgetQuery) -> dict[str, Any]:
        plan = await self.selected_plan(query)
        if plan is None:
            return _empty_plan_payload(query)
        allocations = (
            (
                await self._session.execute(
                    select(m.EnergyCarbonBudgetAllocation)
                    .where(m.EnergyCarbonBudgetAllocation.plan_id == plan.id)
                    .order_by(m.EnergyCarbonBudgetAllocation.period_month.asc())
                )
            )
            .scalars()
            .all()
        )
        actual_by_month = await self._monthly_actuals(plan)
        rows = [_progress_row(allocation, actual_by_month.get(allocation.period_month)) for allocation in allocations]
        totals = _totals(plan, rows)
        return {
            "plan": model_to_dict(plan),
            "rows": rows,
            "totals": totals,
            "filters": _filters(query),
        }

    async def alerts(self, query: EnergyBudgetQuery) -> dict[str, Any]:
        progress = await self.progress(query)
        items = [
            row
            for row in progress["rows"]
            if row["energy_status"] in {"warning", "exceeded"} or row["carbon_status"] in {"warning", "exceeded"}
        ]
        return {"items": items, "total": len(items), "plan": progress["plan"], "filters": progress["filters"]}

    async def forecast(self, query: EnergyBudgetQuery) -> dict[str, Any]:
        progress = await self.progress(query)
        plan = progress["plan"]
        rows = progress["rows"]
        if not plan:
            return {"plan": None, "items": [], "summary": _empty_totals(), "filters": progress["filters"]}
        elapsed_rows = [row for row in rows if (row.get("actual_tce") or 0) > 0 or (row.get("actual_co2e") or 0) > 0]
        elapsed_months = len(elapsed_rows)
        total_months = len(rows)
        actual_tce = sum(float(row.get("actual_tce") or 0) for row in rows)
        actual_co2e = sum(float(row.get("actual_co2e") or 0) for row in rows)
        forecast_tce = forecast_value(actual_tce, elapsed_months, total_months)
        forecast_co2e = forecast_value(actual_co2e, elapsed_months, total_months)
        energy_rate = execution_rate_pct(forecast_tce, plan.get("energy_budget_tce"))
        carbon_rate = execution_rate_pct(forecast_co2e, plan.get("carbon_budget_co2e"))
        summary = {
            "elapsed_months": elapsed_months,
            "total_months": total_months,
            "forecast_tce": forecast_tce,
            "forecast_co2e": forecast_co2e,
            "energy_forecast_rate_pct": energy_rate,
            "carbon_forecast_rate_pct": carbon_rate,
            "energy_status": forecast_status(energy_rate, bool(plan.get("energy_budget_tce"))),
            "carbon_status": forecast_status(carbon_rate, bool(plan.get("carbon_budget_co2e"))),
        }
        return {"plan": plan, "items": rows, "summary": summary, "filters": progress["filters"]}

    async def recommendations(self, query: EnergyBudgetQuery) -> dict[str, Any]:
        progress = await self.progress(query)
        seen: set[str] = set()
        items = []
        for row in progress["rows"]:
            recommendation = recommendation_for(row)
            if recommendation is None:
                continue
            key = f"{recommendation['code']}:{recommendation['target']}"
            if key in seen:
                continue
            seen.add(key)
            items.append(recommendation)
        if not items and progress["plan"]:
            items.append(
                {
                    "code": "budget-on-track",
                    "priority": "low",
                    "title": "维持预算跟踪",
                    "target": progress["plan"].get("name"),
                    "evidence": progress["totals"],
                    "action": "按月复核实际值和预算分解, 保留调整记录。",
                }
            )
        return {"items": items, "plan": progress["plan"], "filters": progress["filters"]}

    async def report(self, query: EnergyBudgetQuery) -> dict[str, Any]:
        progress = await self.progress(query)
        alerts = [
            row
            for row in progress["rows"]
            if row["energy_status"] in {"warning", "exceeded"} or row["carbon_status"] in {"warning", "exceeded"}
        ]
        forecast = await self.forecast(query)
        recommendations = await self.recommendations(query)
        return {
            "plan": progress["plan"],
            "summary": progress["totals"],
            "alerts": alerts,
            "forecast": forecast["summary"],
            "recommendations": recommendations["items"],
            "filters": progress["filters"],
        }

    async def _monthly_actuals(self, plan: m.EnergyCarbonBudgetPlan) -> dict[date, dict[str, Any]]:
        where = [
            "period_end >= :period_start",
            "period_start <= :period_end",
            "(status = 'approved' or status = 'confirmed')",
        ]
        params: dict[str, Any] = {"period_start": plan.period_start, "period_end": plan.period_end}
        if plan.target_scope == "area" and plan.target_code:
            where.append("area_id = :target_code")
            params["target_code"] = plan.target_code
        elif plan.target_scope == "device" and (plan.target_name or plan.target_code):
            where.append("facility_or_device_name = :target_name")
            params["target_name"] = plan.target_name or plan.target_code
        rows = (
            await self._session.execute(
                text(
                    f"""
                    select
                        date_trunc('month', period_start)::date as period_month,
                        coalesce(sum(tce_amount), 0) as actual_tce,
                        coalesce(sum(co2e_amount), 0) as actual_co2e,
                        count(*)::int as record_count
                    from energy_consumption_fact_v
                    where {" and ".join(where)}
                    group by date_trunc('month', period_start)::date
                    """
                ),
                params,
            )
        ).mappings().all()
        return {row["period_month"]: jsonable_mapping(dict(row)) for row in rows}


def _progress_row(allocation: m.EnergyCarbonBudgetAllocation, actual: dict[str, Any] | None) -> dict[str, Any]:
    row = model_to_dict(allocation)
    actual_tce = float((actual or {}).get("actual_tce") or 0)
    actual_co2e = float((actual or {}).get("actual_co2e") or 0)
    denominator_actual = None
    energy_rate = execution_rate_pct(actual_tce, allocation.energy_budget_tce)
    carbon_rate = execution_rate_pct(actual_co2e, allocation.carbon_budget_co2e)
    row.update(
        {
            "period": allocation.period_month.strftime("%Y-%m"),
            "actual_tce": round(actual_tce, 6),
            "actual_co2e": round(actual_co2e, 6),
            "denominator_actual": denominator_actual,
            "actual_energy_intensity": intensity(actual_tce, denominator_actual),
            "actual_carbon_intensity": intensity(actual_co2e, denominator_actual),
            "energy_execution_rate_pct": energy_rate,
            "carbon_execution_rate_pct": carbon_rate,
            "energy_variance_tce": _variance(actual_tce, allocation.energy_budget_tce),
            "carbon_variance_co2e": _variance(actual_co2e, allocation.carbon_budget_co2e),
            "energy_status": execution_status(energy_rate, allocation.energy_budget_tce is not None, (actual or {}).get("record_count", 0) > 0),
            "carbon_status": execution_status(carbon_rate, allocation.carbon_budget_co2e is not None, (actual or {}).get("record_count", 0) > 0),
            "record_count": (actual or {}).get("record_count", 0),
        }
    )
    return row


def _totals(plan: m.EnergyCarbonBudgetPlan, rows: list[dict[str, Any]]) -> dict[str, Any]:
    budget_tce = float(plan.energy_budget_tce or 0)
    budget_co2e = float(plan.carbon_budget_co2e or 0)
    actual_tce = sum(float(row.get("actual_tce") or 0) for row in rows)
    actual_co2e = sum(float(row.get("actual_co2e") or 0) for row in rows)
    energy_rate = execution_rate_pct(actual_tce, budget_tce)
    carbon_rate = execution_rate_pct(actual_co2e, budget_co2e)
    return {
        "budget_tce": round(budget_tce, 6),
        "budget_co2e": round(budget_co2e, 6),
        "actual_tce": round(actual_tce, 6),
        "actual_co2e": round(actual_co2e, 6),
        "energy_execution_rate_pct": energy_rate,
        "carbon_execution_rate_pct": carbon_rate,
        "energy_variance_tce": _variance(actual_tce, budget_tce),
        "carbon_variance_co2e": _variance(actual_co2e, budget_co2e),
        "energy_status": execution_status(energy_rate, budget_tce > 0, actual_tce > 0),
        "carbon_status": execution_status(carbon_rate, budget_co2e > 0, actual_co2e > 0),
    }


def _empty_plan_payload(query: EnergyBudgetQuery) -> dict[str, Any]:
    return {"plan": None, "rows": [], "totals": _empty_totals(), "filters": _filters(query)}


def _empty_totals() -> dict[str, Any]:
    return {
        "budget_tce": 0,
        "budget_co2e": 0,
        "actual_tce": 0,
        "actual_co2e": 0,
        "energy_execution_rate_pct": None,
        "carbon_execution_rate_pct": None,
        "energy_status": "missing_budget",
        "carbon_status": "missing_budget",
    }


def _variance(actual: Any, budget: Any) -> float | None:
    if budget is None:
        return None
    return round(float(actual or 0) - float(budget or 0), 6)


def _filters(query: EnergyBudgetQuery) -> dict[str, Any]:
    return {
        "plan_id": query.plan_id,
        "budget_year": query.budget_year,
        "status": query.status,
        "target_scope": query.target_scope,
        "target_code": query.target_code,
        "period_start": query.period_start,
        "period_end": query.period_end,
    }
