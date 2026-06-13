from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.db import models as m
from app.domain.energy.domain.policies import (
    assumptions,
    before_parameters,
    confidence_level,
    merge_parameters,
    scenario_config,
    simulate_scenario,
)
from app.domain.energy.queries.balance import EnergyBalanceQuery, EnergyBalanceQueryService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EnergyBalanceOptimizationUseCase:
    """Application workflow for energy-balance optimization commands."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def simulate(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = _query_from_payload(payload)
        scenario_type = _str_or_none(payload.get("scenario_type")) or "warehouse_lighting"
        scenario = scenario_config(scenario_type)
        summary = await EnergyBalanceQueryService(self._session).summary(query)
        parameters = merge_parameters(scenario_type, _dict_or_empty(payload.get("parameters")))
        baseline_energy = _num(payload.get("baseline_energy"), summary["total_input"])
        baseline_cost = _num(payload.get("baseline_cost"), summary["total_cost"])
        result = simulate_scenario(scenario_type, baseline_energy, baseline_cost, parameters)
        result.update(
            {
                "scenario_type": scenario_type,
                "scenario_name": scenario["name"],
                "method": scenario["method"],
                "source_name": scenario["source_name"],
                "source_type": "enterprise_assumption",
                "confidence_level": confidence_level(summary),
                "before_parameters": before_parameters(scenario_type, parameters, baseline_energy),
                "after_parameters": parameters,
                "assumptions": assumptions(scenario_type, parameters),
                "summary": summary,
                "filters": {
                    "period_start": query.period_start,
                    "period_end": query.period_end,
                    "granularity": query.granularity,
                    "balance_object_type": query.balance_object_type,
                    "balance_object_code": query.balance_object_code,
                    "energy_type_code": query.energy_type_code,
                    "area_keyword": query.area_keyword,
                    "use_system_code": query.use_system_code,
                },
            }
        )
        return result

    async def create_record(self, payload: dict[str, Any]) -> m.EnergyOptimizationRecord:
        record_payload = _record_payload(payload)
        obj = m.EnergyOptimizationRecord(**record_payload)
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj


def _query_from_payload(payload: dict[str, Any]) -> EnergyBalanceQuery:
    return EnergyBalanceQuery(
        period_start=_str_or_none(payload.get("period_start")),
        period_end=_str_or_none(payload.get("period_end")),
        granularity=_str_or_none(payload.get("granularity")) or "day",
        balance_object_type=_str_or_none(payload.get("balance_object_type")) or "enterprise",
        balance_object_code=_str_or_none(payload.get("balance_object_code")),
        energy_type_code=_str_or_none(payload.get("energy_type_code")),
        area_keyword=_str_or_none(payload.get("area_keyword")),
        use_system_code=_str_or_none(payload.get("use_system_code")),
    )


def _record_payload(data: dict[str, Any]) -> dict[str, Any]:
    scenario_type = _str_or_none(data.get("scenario_type")) or ""
    scenario = scenario_config(scenario_type)
    return {
        "balance_object_type": _str_or_none(data.get("balance_object_type")) or "enterprise",
        "balance_object_code": _str_or_none(data.get("balance_object_code")),
        "balance_object_name": _str_or_none(data.get("balance_object_name")),
        "period_start": _date_or_none(data.get("period_start")),
        "period_end": _date_or_none(data.get("period_end")),
        "scenario_type": scenario_type,
        "scenario_name": _str_or_none(data.get("scenario_name")) or scenario["name"],
        "before_parameters": _dict_or_none(data.get("before_parameters")),
        "after_parameters": _dict_or_none(data.get("after_parameters")),
        "baseline_energy": _decimal_or_none(data.get("baseline_energy")),
        "expected_energy": _decimal_or_none(data.get("expected_energy")),
        "saving_energy": _decimal_or_none(data.get("saving_energy")),
        "saving_rate_pct": _decimal_or_none(data.get("saving_rate_pct")),
        "cost_delta_cny": _decimal_or_none(data.get("cost_delta_cny")),
        "method": _str_or_none(data.get("method")),
        "assumptions": _dict_or_none(data.get("assumptions")),
        "source_name": _str_or_none(data.get("source_name")),
        "source_type": _str_or_none(data.get("source_type")),
        "confidence_level": _str_or_none(data.get("confidence_level")),
        "status": _str_or_none(data.get("status")) or "simulated",
        "remark": _str_or_none(data.get("remark")),
    }


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _num(value: Any, default: float) -> float:
    if value in (None, ""):
        return float(default or 0)
    return _float(value, default)


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date_or_none(value: Any) -> date | None:
    text = _str_or_none(value)
    if not text:
        return None
    return date.fromisoformat(text[:10])


def _decimal_or_none(value: Any) -> Decimal | None:
    text = _str_or_none(value)
    if text is None:
        return None
    return Decimal(text)
