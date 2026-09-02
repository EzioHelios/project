# ruff: noqa: S608
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.domain.energy.queries.common import jsonable_mapping, period_param
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


DEFAULT_LOSS_THRESHOLD_PCT = 5.0


@dataclass(frozen=True, slots=True)
class EnergyFlowQuery:
    """Read-model query parameters for energy flow analysis."""

    period_start: str | None = None
    period_end: str | None = None
    granularity: str = "day"
    energy_type_code: str | None = None
    area_id: str | None = None
    area_keyword: str | None = None
    equipment_id: str | None = None
    use_system_code: str | None = None
    loss_threshold_pct: float = DEFAULT_LOSS_THRESHOLD_PCT
    limit: int = 50


class EnergyFlowQueryService:
    """Query service for energy-flow graph, balance table and loss diagnostics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def graph(self, query: EnergyFlowQuery) -> dict[str, Any]:
        rows = await self._flow_rows(query)
        model = _build_flow_model(rows, _threshold(query.loss_threshold_pct))
        return {
            "title": "园区能流图",
            "unit": "kWh",
            "nodes": model["nodes"],
            "links": model["links"],
            "summary": model["summary"],
            "filters": _filters(query),
        }

    async def balance(self, query: EnergyFlowQuery) -> dict[str, Any]:
        rows = await self._flow_rows(query)
        model = _build_flow_model(rows, _threshold(query.loss_threshold_pct))
        summary = model["summary"]
        total_input = float(summary["total_input"])
        utilized = float(summary["utilized_energy"])
        return {
            "table": [
                {"label": "输入", "value": round(total_input, 4), "unit": "kWh"},
                {"label": "转换损耗", "value": None, "unit": "kWh"},
                {"label": "分配损耗", "value": None, "unit": "kWh"},
                {"label": "有效利用", "value": round(utilized, 4), "unit": "kWh"},
                {"label": "平衡差异", "value": None, "unit": "kWh"},
            ],
            "diagnostics": [
                {"label": "平衡误差率", "value": "-"},
                {"label": "高损耗链路", "value": "-"},
                {"label": "损耗阈值", "value": f"{_threshold(query.loss_threshold_pct)}%"},
                {"label": "数据对象", "value": int(summary["row_count"])},
            ],
            "summary": summary,
            "filters": _filters(query),
        }

    async def losses(self, query: EnergyFlowQuery) -> dict[str, Any]:
        rows = await self._flow_rows(query)
        model = _build_flow_model(rows, _threshold(query.loss_threshold_pct))
        items = model["losses"][: max(1, min(query.limit, 200))]
        return {
            "items": items,
            "total": len(model["losses"]),
            "summary": model["summary"],
            "filters": _filters(query),
        }

    async def report(self, query: EnergyFlowQuery) -> dict[str, Any]:
        rows = await self._flow_rows(query)
        model = _build_flow_model(rows, _threshold(query.loss_threshold_pct))
        return {
            "summary": model["summary"],
            "items": _build_report_items(model["summary"], model["links"]),
            "filters": _filters(query),
        }

    async def _flow_rows(self, query: EnergyFlowQuery) -> list[dict[str, Any]]:
        team_id = self._session.info.get(TENANT_ID_SESSION_KEY)
        if team_id is None:
            return []
        where_sql, params = _build_filters(query, team_id=str(team_id))
        sql = text(
            f"""
            select
                energy_type_code,
                case energy_type_code
                    when 'purchased_electricity' then '外购电力'
                    when 'natural_gas' then '天然气'
                    when 'diesel' then '柴油'
                    when 'gasoline' then '汽油'
                    when 'fuel_oil' then '燃料油'
                    when 'coal' then '原煤'
                    when 'purchased_heat' then '外购热力'
                    when 'purchased_steam' then '外购蒸汽'
                    when 'purchased_cooling' then '外购冷量'
                    when 'refrigerant' then '制冷剂'
                    else coalesce(energy_type_code, '其他能源')
                end as energy_type_name,
                coalesce(use_system_code, 'unclassified') as use_system_code,
                coalesce(use_system_name, '未归类系统') as use_system_name,
                coalesce(area_id, '') as area_id,
                coalesce(area_name, '未分区') as area_name,
                count(*)::int as record_count,
                count(distinct equipment_id)::int as equipment_count,
                coalesce(sum(amount), 0) as energy_amount
            from dataapp_energyintervalfact
            {where_sql}
            group by
                energy_type_code,
                coalesce(use_system_code, 'unclassified'),
                coalesce(use_system_name, '未归类系统'),
                coalesce(area_id, ''),
                coalesce(area_name, '未分区')
            having coalesce(sum(amount), 0) > 0
            order by sum(amount) desc nulls last
            limit 200
            """
        )
        return [jsonable_mapping(dict(row)) for row in (await self._session.execute(sql, params)).mappings().all()]


def _build_filters(query: EnergyFlowQuery, *, team_id: str) -> tuple[str, dict[str, Any]]:
    conditions = ["team_id = :team_id", "is_current = true", "granularity = :source_granularity"]
    params: dict[str, Any] = {
        "team_id": team_id,
        "source_granularity": "hour" if query.granularity == "hour" else "day",
    }
    if query.period_start:
        conditions.append("period_end >= (:period_start)::timestamp")
        params["period_start"] = period_param(query.period_start)
    if query.period_end:
        conditions.append("period_start <= (:period_end)::timestamp")
        params["period_end"] = period_param(query.period_end)
    if query.energy_type_code and query.energy_type_code != "all":
        conditions.append("energy_type_code = :energy_type_code")
        params["energy_type_code"] = query.energy_type_code
    if query.area_id and query.area_id != "all":
        conditions.append("area_id = :area_id")
        params["area_id"] = query.area_id
    if query.equipment_id and query.equipment_id != "all":
        conditions.append("equipment_id = :equipment_id")
        params["equipment_id"] = int(query.equipment_id)
    if query.use_system_code and query.use_system_code != "all":
        conditions.append("use_system_code = :use_system_code")
        params["use_system_code"] = query.use_system_code
    if query.area_keyword:
        conditions.append(
            "(area_name ilike :area_keyword or area_id ilike :area_keyword or equipment_name ilike :area_keyword)"
        )
        params["area_keyword"] = f"%{query.area_keyword.strip()}%"
    return f"where {' and '.join(conditions)}", params


def _build_flow_model(rows: list[dict[str, Any]], threshold_pct: float) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []
    totals = _collect_totals(rows)
    total_input = sum(totals["energy"].values())
    total_utilized = total_input

    nodes["input"] = {"id": "input", "name": "能源输入", "category": "source", "value": round(total_input, 4)}
    nodes["conversion"] = {
        "id": "conversion",
        "name": "转换/计量",
        "category": "conversion",
        "value": round(total_input, 4),
    }
    nodes["distribution"] = {
        "id": "distribution",
        "name": "分配网络",
        "category": "distribution",
        "value": round(total_utilized, 4),
    }
    links.append({"source": "input", "target": "conversion", "value": round(total_input, 4)})
    links.append({"source": "conversion", "target": "distribution", "value": round(total_utilized, 4)})

    for energy_code, amount in sorted(totals["energy"].items(), key=lambda item: item[1], reverse=True):
        source_id = f"source:{energy_code}"
        nodes[source_id] = {
            "id": source_id,
            "name": totals["energy_names"].get(energy_code, energy_code),
            "category": "source",
            "value": round(amount, 4),
        }
        links.append({"source": source_id, "target": "input", "value": round(amount, 4)})

    system_scale = _scale(total_utilized, sum(totals["system"].values()))
    for system_code, amount in sorted(totals["system"].items(), key=lambda item: item[1], reverse=True)[:20]:
        system_id = f"system:{system_code}"
        value = amount * system_scale
        nodes[system_id] = {
            "id": system_id,
            "name": totals["system_names"].get(system_code, system_code),
            "category": "use_system",
            "value": round(value, 4),
        }
        links.append({"source": "distribution", "target": system_id, "value": round(value, 4)})

    area_scale = _scale(total_utilized, sum(totals["area"].values()))
    for (system_code, area_key), amount in sorted(
        totals["system_area"].items(), key=lambda item: item[1], reverse=True
    )[:80]:
        system_id = f"system:{system_code}"
        area_id = f"area:{area_key}"
        value = amount * area_scale
        if system_id in nodes:
            links.append({"source": system_id, "target": area_id, "value": round(value, 4)})

    for area_key, amount in sorted(totals["area"].items(), key=lambda item: item[1], reverse=True)[:30]:
        area_id = f"area:{area_key}"
        use_id = f"use:{area_key}"
        value = amount * area_scale
        nodes[area_id] = {
            "id": area_id,
            "name": totals["area_names"].get(area_key, area_key),
            "category": "area",
            "value": round(value, 4),
        }
        nodes[use_id] = {
            "id": use_id,
            "name": f"{totals['area_names'].get(area_key, area_key)}有效利用",
            "category": "result",
            "value": round(value, 4),
        }
        links.append({"source": area_id, "target": use_id, "value": round(value, 4)})

    losses = _build_loss_items(links, total_input=total_input, threshold_pct=threshold_pct)

    return {
        "nodes": list(nodes.values()),
        "links": [link for link in links if link["value"] > 0],
        "losses": losses,
        "summary": {
            "total_input": round(total_input, 4),
            "transform_loss": None,
            "distribution_loss": None,
            "total_loss": None,
            "loss_rate_pct": None,
            "utilized_energy": round(total_utilized, 4),
            "high_loss_count": len([item for item in losses if item["status"] == "high_loss"]),
            "row_count": len(rows),
            "loss_threshold_pct": threshold_pct,
            "data_quality": "metered_allocation_without_loss_measurement",
        },
    }


def _collect_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Any] = {
        "energy": {},
        "energy_names": {},
        "system": {},
        "system_names": {},
        "area": {},
        "area_names": {},
        "system_area": {},
    }
    for row in rows:
        amount = float(row.get("energy_amount") or 0)
        energy_code = str(row.get("energy_type_code") or "unknown")
        system_code = str(row.get("use_system_code") or "unclassified")
        area_key = str(row.get("area_id") or row.get("area_name") or "unclassified")
        system_area_key = (system_code, area_key)
        totals["energy"][energy_code] = totals["energy"].get(energy_code, 0.0) + amount
        totals["system"][system_code] = totals["system"].get(system_code, 0.0) + amount
        totals["area"][area_key] = totals["area"].get(area_key, 0.0) + amount
        totals["system_area"][system_area_key] = totals["system_area"].get(system_area_key, 0.0) + amount
        totals["energy_names"][energy_code] = row.get("energy_type_name") or energy_code
        totals["system_names"][system_code] = row.get("use_system_name") or system_code
        totals["area_names"][area_key] = row.get("area_name") or area_key
    return totals


def _scale(target_total: float, source_total: float) -> float:
    if source_total <= 0:
        return 0
    return target_total / source_total


def _build_loss_items(links: list[dict[str, Any]], *, total_input: float, threshold_pct: float) -> list[dict[str, Any]]:
    if total_input <= 0:
        return []
    key_links = sorted([link for link in links if float(link.get("value") or 0) > 0], key=lambda item: float(item["value"]), reverse=True)[:5]
    if not key_links:
        return []
    return [
        {
            "stage": "计量覆盖诊断",
            "source": str(item["source"]),
            "target": str(item["target"]),
            "input_amount": round(float(item["value"]), 4),
            "loss_amount": 0,
            "loss_rate_pct": 0,
            "threshold_pct": threshold_pct,
            "status": "normal",
            "suggestion": "当前链路按计量分配模型形成用能流向。后续可结合分级计量补充分段损耗测量。",
        }
        for item in key_links
    ]


def _build_report_items(summary: dict[str, Any], links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total_input = float(summary.get("total_input") or 0)
    if total_input <= 0:
        return []
    top_links = sorted([link for link in links if float(link.get("value") or 0) > 0], key=lambda item: float(item["value"]), reverse=True)[:3]
    top_link_text = "、".join(f"{item['source']} -> {item['target']}" for item in top_links) or "-"
    return [
        {
            "title": "能流结构复盘",
            "priority": "medium",
            "target": "主要能流链路",
            "evidence": {
                "计量用电(kWh)": round(total_input, 4),
                "分项用电(kWh)": round(float(summary.get("utilized_energy") or 0), 4),
                "链路数量": len([link for link in links if float(link.get("value") or 0) > 0]),
                "数据对象": int(summary.get("row_count") or 0),
                "重点链路": top_link_text,
            },
            "steps": [
                "按账期、区域、设备或用能系统筛选能流图。",
                "核对能源输入、分配网络和区域有效利用之间的链路关系。",
                "结合损耗诊断结果完善分级计量点位和关键设备采集配置。",
            ],
            "expected_effect": "形成可用于月度能源运营复盘的能流结构说明。",
        }
    ]


def _threshold(value: float | None) -> float:
    if value is None:
        return DEFAULT_LOSS_THRESHOLD_PCT
    return max(0.1, min(float(value), 100.0))


def _filters(query: EnergyFlowQuery) -> dict[str, Any]:
    return {
        "period_start": query.period_start,
        "period_end": query.period_end,
        "granularity": query.granularity if query.granularity in {"hour", "day", "month"} else "day",
        "energy_type_code": query.energy_type_code,
        "area_id": query.area_id,
        "area_keyword": query.area_keyword,
        "equipment_id": query.equipment_id,
        "use_system_code": query.use_system_code,
        "loss_threshold_pct": _threshold(query.loss_threshold_pct),
    }
