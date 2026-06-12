# ruff: noqa: S608
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.domain.energy.queries.common import jsonable_mapping, ratio_or_none

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


DEFAULT_TRANSFORM_LOSS_RATE = 0.02
DEFAULT_DISTRIBUTION_LOSS_RATE = 0.03
GOOD_METERING_COVERAGE_PCT = 90
WARNING_METERING_COVERAGE_PCT = 70

SCENARIOS = {
    "warehouse_lighting": {
        "name": "仓库照明分区降载",
        "parameter_schema": {
            "controlled_load_pct": 25,
            "reduction_pct": 30,
        },
        "method": "measure_based_rule",
        "source_name": "企业运行假设",
    },
    "warehouse_idle_reduction": {
        "name": "仓储设备空转压降",
        "parameter_schema": {
            "idle_energy_pct": 18,
            "idle_reduction_pct": 35,
        },
        "method": "measure_based_rule",
        "source_name": "企业运行假设",
    },
    "off_peak_charging": {
        "name": "充电负荷错峰",
        "parameter_schema": {
            "shifted_energy_pct": 40,
            "price_delta_cny_per_kwh": 0.35,
        },
        "method": "tariff_shift",
        "source_name": "企业分时电价假设",
    },
    "compressed_air_pressure": {
        "name": "空压站参数优化",
        "parameter_schema": {
            "current_pressure_mpa": 0.8,
            "target_pressure_mpa": 0.75,
            "expected_saving_pct": 5,
        },
        "method": "engineering_assumption",
        "source_name": "企业运行假设",
    },
}


@dataclass(frozen=True, slots=True)
class EnergyBalanceQuery:
    """Read-model query parameters for energy balance and optimization."""

    period_start: str | None = None
    period_end: str | None = None
    granularity: str = "day"
    balance_object_type: str = "enterprise"
    balance_object_code: str | None = None
    energy_type_code: str | None = None
    area_keyword: str | None = None
    use_system_code: str | None = None


class EnergyBalanceQueryService:
    """Query service for balance tables, data quality and simulation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def overview(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        summary = await self._summary(query)
        return {
            "summary": summary,
            "cards": [
                {"label": "能源输入", "value": summary["total_input"], "unit": "kWh"},
                {"label": "有效利用", "value": summary["effective_energy"], "unit": "kWh"},
                {"label": "损耗/缺失", "value": summary["total_loss"], "unit": "kWh"},
                {"label": "平衡误差率", "value": summary["balance_error_pct"], "unit": "%"},
                {"label": "计量覆盖率", "value": summary["metering_coverage_pct"], "unit": "%"},
            ],
            "filters": _filters(query),
        }

    async def table(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        summary = await self._summary(query)
        rows = [
            _row("input", "能源输入", summary["total_input"], "metered", "能源消费事实"),
            _row("effective", "有效利用", summary["effective_energy"], "calculated", "输入扣减估算损耗"),
            _row("transform_loss", "转换损失", summary["transform_loss"], "estimated", "企业运行假设"),
            _row("distribution_loss", "输配损失", summary["distribution_loss"], "estimated", "企业运行假设"),
            _row("terminal_loss", "终端损失/缺失", summary["terminal_loss"], "estimated", "未归类与数据缺口"),
            _row("inventory_change", "库存变化", summary["inventory_change"], "missing", "暂未接入库存计量"),
            _row("balance_difference", "平衡差异", summary["balance_difference"], "calculated", "平衡关系计算"),
        ]
        return {
            "rows": rows,
            "summary": summary,
            "filters": _filters(query),
        }

    async def data_quality(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        summary = await self._summary(query)
        quality = summary["quality"]
        items = [
            {"label": "能耗记录数", "value": summary["record_count"], "status": "ok" if summary["record_count"] else "missing"},
            {"label": "设备覆盖数", "value": summary["equipment_count"], "status": "ok" if summary["equipment_count"] else "missing"},
            {"label": "计量覆盖率", "value": f"{summary['metering_coverage_pct']}%", "status": quality},
            {"label": "估算记录数", "value": summary["estimated_count"], "status": "warning" if summary["estimated_count"] else "ok"},
            {"label": "负荷记录数", "value": summary["workload_record_count"], "status": "ok" if summary["workload_record_count"] else "warning"},
            {"label": "数据质量", "value": _quality_label(quality), "status": quality},
        ]
        return {
            "items": items,
            "source_distribution": summary["source_distribution"],
            "summary": summary,
            "filters": _filters(query),
        }

    async def scenarios(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        summary = await self._summary(query)
        items = []
        for scenario_type, config in SCENARIOS.items():
            items.append(
                {
                    "scenario_type": scenario_type,
                    "scenario_name": config["name"],
                    "method": config["method"],
                    "source_name": config["source_name"],
                    "default_parameters": config["parameter_schema"],
                    "baseline_energy": summary["total_input"],
                    "baseline_cost": summary["total_cost"],
                    "confidence_level": _confidence(summary),
                }
            )
        return {"items": items, "summary": summary, "filters": _filters(query)}

    async def simulate(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = EnergyBalanceQuery(
            period_start=_str_or_none(payload.get("period_start")),
            period_end=_str_or_none(payload.get("period_end")),
            granularity=_str_or_none(payload.get("granularity")) or "day",
            balance_object_type=_str_or_none(payload.get("balance_object_type")) or "enterprise",
            balance_object_code=_str_or_none(payload.get("balance_object_code")),
            energy_type_code=_str_or_none(payload.get("energy_type_code")),
            area_keyword=_str_or_none(payload.get("area_keyword")),
            use_system_code=_str_or_none(payload.get("use_system_code")),
        )
        scenario_type = _str_or_none(payload.get("scenario_type")) or "warehouse_lighting"
        scenario = SCENARIOS.get(scenario_type, SCENARIOS["warehouse_lighting"])
        summary = await self._summary(query)
        parameters = {**scenario["parameter_schema"], **_dict_or_empty(payload.get("parameters"))}
        baseline_energy = _num(payload.get("baseline_energy"), summary["total_input"])
        baseline_cost = _num(payload.get("baseline_cost"), summary["total_cost"])
        result = _simulate_scenario(scenario_type, baseline_energy, baseline_cost, parameters)
        result.update(
            {
                "scenario_type": scenario_type,
                "scenario_name": scenario["name"],
                "method": scenario["method"],
                "source_name": scenario["source_name"],
                "source_type": "enterprise_assumption",
                "confidence_level": _confidence(summary),
                "before_parameters": _before_parameters(scenario_type, parameters, baseline_energy),
                "after_parameters": parameters,
                "assumptions": _assumptions(scenario_type, parameters),
                "summary": summary,
                "filters": _filters(query),
            }
        )
        return result

    async def _summary(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        energy = await self._energy_totals(query)
        workload = await self._workload_totals(query)
        total_input = float(energy.get("total_input") or 0)
        transform_loss = total_input * DEFAULT_TRANSFORM_LOSS_RATE
        after_transform = max(total_input - transform_loss, 0)
        distribution_loss = after_transform * DEFAULT_DISTRIBUTION_LOSS_RATE
        terminal_loss = _terminal_gap(energy)
        total_loss = transform_loss + distribution_loss + terminal_loss
        effective_energy = max(total_input - total_loss, 0)
        inventory_change = 0.0
        balance_difference = total_input - effective_energy - total_loss - inventory_change
        balance_error_pct = ratio_or_none(abs(balance_difference) * 100, total_input, 4) or 0
        record_count = int(energy.get("record_count") or 0)
        measured_count = int(energy.get("measured_count") or 0)
        estimated_count = int(energy.get("estimated_count") or 0)
        metering_coverage_pct = ratio_or_none(measured_count * 100, record_count, 2) or 0
        return {
            "total_input": round(total_input, 4),
            "effective_energy": round(effective_energy, 4),
            "transform_loss": round(transform_loss, 4),
            "distribution_loss": round(distribution_loss, 4),
            "terminal_loss": round(terminal_loss, 4),
            "total_loss": round(total_loss, 4),
            "inventory_change": round(inventory_change, 4),
            "balance_difference": round(balance_difference, 6),
            "balance_error_pct": balance_error_pct,
            "metering_coverage_pct": metering_coverage_pct,
            "record_count": record_count,
            "equipment_count": int(energy.get("equipment_count") or 0),
            "area_count": int(energy.get("area_count") or 0),
            "total_cost": round(float(energy.get("total_cost") or 0), 4),
            "estimated_count": estimated_count,
            "workload_record_count": int(workload.get("workload_record_count") or 0),
            "run_hours": round(float(workload.get("run_hours") or 0), 4),
            "workload_amount": round(float(workload.get("workload_amount") or 0), 4),
            "source_distribution": await self._source_distribution(query),
            "quality": _quality(record_count, metering_coverage_pct, estimated_count),
            "balance_status": "estimated_closed" if total_input else "no_data",
        }

    async def _energy_totals(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        where_sql, params = _energy_filters(query)
        sql = text(
            f"""
            select
                coalesce(sum(amount), 0) as total_input,
                coalesce(sum(cost_cny), 0) as total_cost,
                count(*)::int as record_count,
                count(distinct equipment_id)::int as equipment_count,
                count(distinct area_id)::int as area_count,
                count(*) filter (where data_quality = 'measured')::int as measured_count,
                count(*) filter (where data_quality <> 'measured')::int as estimated_count,
                coalesce(sum(amount) filter (where use_system_code is null or use_system_code = ''), 0) as unclassified_energy
            from dataapp_energyintervalfact
            {where_sql}
            """
        )
        row = (await self._session.execute(sql, params)).mappings().one()
        return jsonable_mapping(dict(row))

    async def _workload_totals(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        where_sql, params = _workload_filters(query)
        sql = text(
            f"""
            select
                count(*)::int as workload_record_count,
                coalesce(sum(run_hours), 0) as run_hours,
                coalesce(sum(workload_amount), 0) as workload_amount
            from dataapp_equipmentworkloadfact
            {where_sql}
            """
        )
        row = (await self._session.execute(sql, params)).mappings().one()
        return jsonable_mapping(dict(row))

    async def _source_distribution(self, query: EnergyBalanceQuery) -> list[dict[str, Any]]:
        where_sql, params = _energy_filters(query)
        sql = text(
            f"""
            select
                coalesce(data_quality, 'unknown') as source_type,
                count(*)::int as record_count,
                coalesce(sum(amount), 0) as energy_amount
            from dataapp_energyintervalfact
            {where_sql}
            group by coalesce(data_quality, 'unknown')
            order by sum(amount) desc nulls last
            """
        )
        return [jsonable_mapping(dict(row)) for row in (await self._session.execute(sql, params)).mappings().all()]


def _energy_filters(query: EnergyBalanceQuery) -> tuple[str, dict[str, Any]]:
    conditions = ["granularity = :source_granularity"]
    params: dict[str, Any] = {"source_granularity": "hour" if query.granularity == "hour" else "day"}
    _append_common_filters(conditions, params, query, include_energy_type=True)
    return f"where {' and '.join(conditions)}", params


def _workload_filters(query: EnergyBalanceQuery) -> tuple[str, dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}
    if query.period_start:
        conditions.append("period_end >= (:period_start)::timestamp")
        params["period_start"] = query.period_start
    if query.period_end:
        conditions.append("period_start <= (:period_end)::timestamp")
        params["period_end"] = query.period_end
    if query.use_system_code and query.use_system_code != "all":
        conditions.append("use_system_code = :use_system_code")
        params["use_system_code"] = query.use_system_code
    if query.area_keyword:
        conditions.append("(area_name ilike :area_keyword or area_id ilike :area_keyword or equipment_name ilike :area_keyword)")
        params["area_keyword"] = f"%{query.area_keyword.strip()}%"
    if query.balance_object_type == "area" and query.balance_object_code:
        conditions.append("area_id = :balance_object_code")
        params["balance_object_code"] = query.balance_object_code
    if query.balance_object_type == "use_system" and query.balance_object_code:
        conditions.append("use_system_code = :balance_object_code")
        params["balance_object_code"] = query.balance_object_code
    return f"where {' and '.join(conditions)}" if conditions else "", params


def _append_common_filters(conditions: list[str], params: dict[str, Any], query: EnergyBalanceQuery, *, include_energy_type: bool) -> None:
    if query.period_start:
        conditions.append("period_end >= (:period_start)::timestamp")
        params["period_start"] = query.period_start
    if query.period_end:
        conditions.append("period_start <= (:period_end)::timestamp")
        params["period_end"] = query.period_end
    if include_energy_type and query.energy_type_code and query.energy_type_code != "all":
        conditions.append("energy_type_code = :energy_type_code")
        params["energy_type_code"] = query.energy_type_code
    if query.use_system_code and query.use_system_code != "all":
        conditions.append("use_system_code = :use_system_code")
        params["use_system_code"] = query.use_system_code
    if query.area_keyword:
        conditions.append("(area_name ilike :area_keyword or area_id ilike :area_keyword or equipment_name ilike :area_keyword)")
        params["area_keyword"] = f"%{query.area_keyword.strip()}%"
    if query.balance_object_type == "area" and query.balance_object_code:
        conditions.append("area_id = :balance_object_code")
        params["balance_object_code"] = query.balance_object_code
    if query.balance_object_type == "use_system" and query.balance_object_code:
        conditions.append("use_system_code = :balance_object_code")
        params["balance_object_code"] = query.balance_object_code
    if query.balance_object_type == "device" and query.balance_object_code:
        conditions.append("equipment_code = :balance_object_code")
        params["balance_object_code"] = query.balance_object_code


def _simulate_scenario(scenario_type: str, baseline_energy: float, baseline_cost: float, parameters: dict[str, Any]) -> dict[str, Any]:
    status = "ok" if baseline_energy > 0 else "invalid_baseline"
    saving_energy = 0.0
    cost_delta = 0.0
    if scenario_type == "warehouse_lighting":
        saving_energy = baseline_energy * _pct(parameters, "controlled_load_pct") * _pct(parameters, "reduction_pct")
    elif scenario_type == "warehouse_idle_reduction":
        saving_energy = baseline_energy * _pct(parameters, "idle_energy_pct") * _pct(parameters, "idle_reduction_pct")
    elif scenario_type == "off_peak_charging":
        shifted_energy = baseline_energy * _pct(parameters, "shifted_energy_pct")
        cost_delta = -shifted_energy * _float(parameters.get("price_delta_cny_per_kwh"), 0.0)
    elif scenario_type == "compressed_air_pressure":
        saving_energy = baseline_energy * _pct(parameters, "expected_saving_pct")
    saving_energy = max(0.0, saving_energy)
    expected_energy = max(0.0, baseline_energy - saving_energy)
    saving_rate_pct = ratio_or_none(saving_energy * 100, baseline_energy, 4) or 0
    if scenario_type != "off_peak_charging" and baseline_energy > 0 and baseline_cost > 0:
        cost_delta = -(baseline_cost * saving_rate_pct / 100)
    return {
        "status": status,
        "baseline_energy": round(baseline_energy, 4),
        "expected_energy": round(expected_energy, 4),
        "saving_energy": round(saving_energy, 4),
        "saving_rate_pct": saving_rate_pct,
        "cost_delta_cny": round(cost_delta, 4),
        "unit": "kWh",
    }


def _terminal_gap(energy: dict[str, Any]) -> float:
    total_input = float(energy.get("total_input") or 0)
    unclassified = float(energy.get("unclassified_energy") or 0)
    return min(total_input * 0.01, unclassified * 0.2) if total_input else 0.0


def _row(code: str, label: str, value: float, source_type: str, source_name: str) -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "value": round(value, 4),
        "unit": "kWh",
        "source_type": source_type,
        "source_name": source_name,
    }


def _quality(record_count: int, metering_coverage_pct: float, estimated_count: int) -> str:
    if record_count <= 0:
        return "missing"
    if metering_coverage_pct >= GOOD_METERING_COVERAGE_PCT and estimated_count == 0:
        return "good"
    if metering_coverage_pct >= WARNING_METERING_COVERAGE_PCT:
        return "warning"
    return "low"


def _quality_label(value: str) -> str:
    return {
        "good": "良好",
        "warning": "需复核",
        "low": "覆盖不足",
        "missing": "暂无数据",
    }.get(value, value)


def _confidence(summary: dict[str, Any]) -> str:
    if summary["quality"] == "good" and summary["workload_record_count"]:
        return "medium"
    if summary["quality"] in {"good", "warning"}:
        return "low"
    return "reference"


def _filters(query: EnergyBalanceQuery) -> dict[str, Any]:
    return {
        "period_start": query.period_start,
        "period_end": query.period_end,
        "granularity": query.granularity,
        "balance_object_type": query.balance_object_type,
        "balance_object_code": query.balance_object_code,
        "energy_type_code": query.energy_type_code,
        "area_keyword": query.area_keyword,
        "use_system_code": query.use_system_code,
    }


def _before_parameters(scenario_type: str, parameters: dict[str, Any], baseline_energy: float) -> dict[str, Any]:
    result = {"baseline_energy": round(baseline_energy, 4)}
    if scenario_type == "compressed_air_pressure":
        result["current_pressure_mpa"] = parameters.get("current_pressure_mpa")
    return result


def _assumptions(scenario_type: str, parameters: dict[str, Any]) -> dict[str, Any]:
    result = {"scenario_type": scenario_type, "parameters": parameters}
    if scenario_type == "off_peak_charging":
        result["energy_saving_note"] = "错峰仅测算费用变化, 不计入节能量。"
    return result


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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


def _pct(parameters: dict[str, Any], key: str) -> float:
    return max(0.0, min(_float(parameters.get(key), 0.0), 100.0)) / 100
