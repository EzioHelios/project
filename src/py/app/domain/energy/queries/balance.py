# ruff: noqa: S608
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.domain.energy.domain.policies import (
    data_quality_label,
    data_quality_status,
    scenario_options,
)
from app.domain.energy.queries.common import jsonable_mapping, ratio_or_none

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


DEFAULT_TRANSFORM_LOSS_RATE = 0.02
DEFAULT_DISTRIBUTION_LOSS_RATE = 0.03


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
    """Query service for balance tables and data quality read models."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def overview(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        summary = await self.summary(query)
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
        summary = await self.summary(query)
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
        summary = await self.summary(query)
        quality = summary["quality"]
        items = [
            {"label": "能耗记录数", "value": summary["record_count"], "status": "ok" if summary["record_count"] else "missing"},
            {"label": "设备覆盖数", "value": summary["equipment_count"], "status": "ok" if summary["equipment_count"] else "missing"},
            {"label": "计量覆盖率", "value": f"{summary['metering_coverage_pct']}%", "status": quality},
            {"label": "估算记录数", "value": summary["estimated_count"], "status": "warning" if summary["estimated_count"] else "ok"},
            {"label": "负荷记录数", "value": summary["workload_record_count"], "status": "ok" if summary["workload_record_count"] else "warning"},
            {"label": "数据质量", "value": data_quality_label(quality), "status": quality},
        ]
        return {
            "items": items,
            "source_distribution": summary["source_distribution"],
            "summary": summary,
            "filters": _filters(query),
        }

    async def scenarios(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        summary = await self.summary(query)
        items = scenario_options(summary)
        return {"items": items, "summary": summary, "filters": _filters(query)}

    async def summary(self, query: EnergyBalanceQuery) -> dict[str, Any]:
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
            "quality": data_quality_status(record_count, metering_coverage_pct, estimated_count),
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
