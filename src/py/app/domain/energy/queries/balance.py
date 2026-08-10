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
from app.domain.energy.queries.common import jsonable_mapping, period_param, ratio_or_none
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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
                {"label": "计量用电", "value": summary["total_input"], "unit": "kWh"},
                {"label": "分项用电", "value": summary["effective_energy"], "unit": "kWh"},
                {"label": "平衡差异", "value": summary["balance_difference"], "unit": "kWh"},
                {"label": "平衡误差率", "value": summary["balance_error_pct"], "unit": "%"},
                {"label": "计量覆盖率", "value": summary["metering_coverage_pct"], "unit": "%"},
            ],
            "filters": _filters(query),
        }

    async def table(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        summary = await self.summary(query)
        rows = [
            _row("input", "计量用电", summary["total_input"], "measured", "能源计量事实"),
            _row("effective", "分项用电", summary["effective_energy"], "aggregated", "区域与用能系统分项汇总"),
            _row("transform_loss", "转换损失", summary["transform_loss"], "missing", "未配置转换环节输入/输出计量"),
            _row(
                "distribution_loss", "输配损失", summary["distribution_loss"], "missing", "未配置输配环节输入/输出计量"
            ),
            _row("terminal_loss", "终端损失/缺失", summary["terminal_loss"], "missing", "未形成总表与末端分项闭合关系"),
            _row("inventory_change", "库存变化", summary["inventory_change"], "missing", "未接入库存计量"),
            _row("balance_difference", "平衡差异", summary["balance_difference"], "missing", "计量边界尚未闭合"),
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
            {
                "label": "能耗记录数",
                "value": summary["record_count"],
                "status": "ok" if summary["record_count"] else "missing",
            },
            {
                "label": "设备覆盖数",
                "value": summary["equipment_count"],
                "status": "ok" if summary["equipment_count"] else "missing",
            },
            {"label": "计量覆盖率", "value": f"{summary['metering_coverage_pct']}%", "status": quality},
            {
                "label": "估算记录数",
                "value": summary["estimated_count"],
                "status": "warning" if summary["estimated_count"] else "ok",
            },
            {
                "label": "负荷记录数",
                "value": summary["workload_record_count"],
                "status": "ok" if summary["workload_record_count"] else "warning",
            },
            {
                "label": "平衡边界",
                "value": "已闭合" if summary["balance_status"] == "balanced" else "待完善",
                "status": "ok" if summary["balance_status"] == "balanced" else "warning",
            },
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
        effective_energy = total_input
        record_count = int(energy.get("record_count") or 0)
        measured_count = int(energy.get("measured_count") or 0)
        estimated_count = int(energy.get("estimated_count") or 0)
        metering_coverage_pct = ratio_or_none(measured_count * 100, record_count, 2) or 0
        return {
            "total_input": round(total_input, 4),
            "effective_energy": round(effective_energy, 4),
            "transform_loss": None,
            "distribution_loss": None,
            "terminal_loss": None,
            "total_loss": None,
            "inventory_change": None,
            "balance_difference": None,
            "balance_error_pct": None,
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
            "balance_status": "insufficient_boundary" if total_input else "no_data",
        }

    async def _energy_totals(self, query: EnergyBalanceQuery) -> dict[str, Any]:
        team_id = self._session.info.get(TENANT_ID_SESSION_KEY)
        if team_id is None:
            return {}
        where_sql, params = _energy_filters(query, team_id=str(team_id))
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
        team_id = self._session.info.get(TENANT_ID_SESSION_KEY)
        if team_id is None:
            return {}
        where_sql, params = _workload_filters(query, team_id=str(team_id))
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
        team_id = self._session.info.get(TENANT_ID_SESSION_KEY)
        if team_id is None:
            return []
        where_sql, params = _energy_filters(query, team_id=str(team_id))
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


def _energy_filters(query: EnergyBalanceQuery, *, team_id: str) -> tuple[str, dict[str, Any]]:
    conditions = ["team_id = :team_id", "is_current = true", "granularity = :source_granularity"]
    params: dict[str, Any] = {
        "team_id": team_id,
        "source_granularity": "hour" if query.granularity == "hour" else "day",
    }
    _append_common_filters(conditions, params, query, include_energy_type=True)
    return f"where {' and '.join(conditions)}", params


def _workload_filters(query: EnergyBalanceQuery, *, team_id: str) -> tuple[str, dict[str, Any]]:
    conditions = ["team_id = :team_id"]
    params: dict[str, Any] = {"team_id": team_id}
    if query.period_start:
        conditions.append("period_end >= (:period_start)::timestamp")
        params["period_start"] = period_param(query.period_start)
    if query.period_end:
        conditions.append("period_start <= (:period_end)::timestamp")
        params["period_end"] = period_param(query.period_end)
    if query.use_system_code and query.use_system_code != "all":
        conditions.append("use_system_code = :use_system_code")
        params["use_system_code"] = query.use_system_code
    if query.area_keyword:
        conditions.append(
            "(area_name ilike :area_keyword or area_id ilike :area_keyword or equipment_name ilike :area_keyword)"
        )
        params["area_keyword"] = f"%{query.area_keyword.strip()}%"
    if query.balance_object_type == "area" and query.balance_object_code:
        conditions.append("area_id = :balance_object_code")
        params["balance_object_code"] = query.balance_object_code
    if query.balance_object_type == "use_system" and query.balance_object_code:
        conditions.append("use_system_code = :balance_object_code")
        params["balance_object_code"] = query.balance_object_code
    return f"where {' and '.join(conditions)}", params


def _append_common_filters(
    conditions: list[str], params: dict[str, Any], query: EnergyBalanceQuery, *, include_energy_type: bool
) -> None:
    if query.period_start:
        conditions.append("period_end >= (:period_start)::timestamp")
        params["period_start"] = period_param(query.period_start)
    if query.period_end:
        conditions.append("period_start <= (:period_end)::timestamp")
        params["period_end"] = period_param(query.period_end)
    if include_energy_type and query.energy_type_code and query.energy_type_code != "all":
        conditions.append("energy_type_code = :energy_type_code")
        params["energy_type_code"] = query.energy_type_code
    if query.use_system_code and query.use_system_code != "all":
        conditions.append("use_system_code = :use_system_code")
        params["use_system_code"] = query.use_system_code
    if query.area_keyword:
        conditions.append(
            "(area_name ilike :area_keyword or area_id ilike :area_keyword or equipment_name ilike :area_keyword)"
        )
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


def _row(code: str, label: str, value: float | None, source_type: str, source_name: str) -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "value": round(value, 4) if value is not None else None,
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
