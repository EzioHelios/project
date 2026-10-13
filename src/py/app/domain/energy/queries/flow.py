# ruff: noqa: S608
from __future__ import annotations

from collections import defaultdict
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
    metered_only: bool = False
    area_codes: tuple[str, ...] | None = None


class EnergyFlowQueryService:
    """Query service for energy-flow graph, balance table and loss diagnostics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def graph(self, query: EnergyFlowQuery) -> dict[str, Any]:
        rows = await self._flow_rows(query)
        model = _build_flow_model(rows, _threshold(query.loss_threshold_pct))
        return {
            "title": "能源归集流图",
            "unit": model["unit"],
            "nodes": model["nodes"],
            "links": model["links"],
            "summary": model["summary"],
            "filters": _filters(query),
        }

    async def balance(self, query: EnergyFlowQuery) -> dict[str, Any]:
        rows = await self._flow_rows(query)
        model = _build_flow_model(rows, _threshold(query.loss_threshold_pct))
        summary = model["summary"]
        total_input = summary["total_input"]
        utilized = summary["utilized_energy"]
        return {
            "table": [
                {"label": "计量归集", "value": total_input, "unit": model["unit"] or ""},
                {"label": "转换损耗", "value": None, "unit": "kWh"},
                {"label": "分配损耗", "value": None, "unit": "kWh"},
                {"label": "区域设备归集", "value": utilized, "unit": model["unit"] or ""},
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
            "items": _build_report_items(model["summary"], model["links"], model["nodes"], model["unit"]),
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
                unit,
                case energy_type_code
                    when 'purchased_electricity' then '外购电力'
                    when 'electricity' then '电力'
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
                equipment_id,
                coalesce(equipment_name, '未关联设备') as equipment_name,
                count(*)::int as record_count,
                count(distinct equipment_id)::int as equipment_count,
                coalesce(sum(amount), 0) as energy_amount
            from dataapp_energyintervalfact
            {where_sql}
            group by
                energy_type_code,
                unit,
                coalesce(use_system_code, 'unclassified'),
                coalesce(use_system_name, '未归类系统'),
                coalesce(area_id, ''),
                coalesce(area_name, '未分区'),
                equipment_id,
                coalesce(equipment_name, '未关联设备')
            having coalesce(sum(amount), 0) > 0
            order by sum(amount) desc nulls last
            """
        )
        return [jsonable_mapping(dict(row)) for row in (await self._session.execute(sql, params)).mappings().all()]


def _build_filters(query: EnergyFlowQuery, *, team_id: str) -> tuple[str, dict[str, Any]]:
    conditions = ["team_id = :team_id", "is_current = true", "granularity = :source_granularity"]
    params: dict[str, Any] = {
        "team_id": team_id,
        "source_granularity": query.granularity if query.granularity in {"hour", "day", "month"} else "day",
    }
    if query.period_start:
        conditions.append("period_start >= (:period_start)::timestamp")
        params["period_start"] = period_param(query.period_start)
    if query.period_end:
        conditions.append("period_start < (:period_end)::date + interval '1 day'")
        params["period_end"] = period_param(query.period_end)
    if query.energy_type_code and query.energy_type_code != "all":
        conditions.append(
            "energy_type_code in ('electricity', 'purchased_electricity')"
            if query.energy_type_code in {"electricity", "purchased_electricity"}
            else "energy_type_code = :energy_type_code"
        )
        params["energy_type_code"] = query.energy_type_code
    if query.area_id and query.area_id != "all":
        conditions.append("area_id = :area_id")
        params["area_id"] = query.area_id
    if query.area_codes is not None:
        conditions.append("area_id = any(:area_codes)")
        params["area_codes"] = list(query.area_codes)
    if query.metered_only:
        conditions.extend(
            [
                "unit = 'kWh'",
                "energy_type_code in ('electricity', 'purchased_electricity')",
                "source_system in ('meter_projection', 'meter_daily', 'meter_hourly')",
                "data_quality <> 'simulated'",
                "equipment_id in (select id from dataapp_monitorequipment where team_id = :team_id and category = 0)",
            ]
        )
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
    """Show recorded attribution only; no invented conversion or loss stages."""
    units = {str(row.get("unit") or "kWh") for row in rows}
    unit = next(iter(units)) if len(units) == 1 else "kWh" if not units else None
    nodes: dict[str, dict[str, Any]] = {}
    links: dict[tuple[str, str], float] = defaultdict(float)
    for row in rows:
        amount = float(row.get("energy_amount") or 0)
        if amount <= 0:
            continue
        code = str(row["energy_type_code"])
        code = "electricity" if code in {"electricity", "purchased_electricity"} else code
        row_unit = str(row.get("unit") or "kWh")
        prefix = f"{code}:{row_unit}"
        source = f"energy:{prefix}"
        area = f"area:{prefix}:{row.get('area_id') or 'unallocated'}"
        device = f"equipment:{prefix}:{row.get('equipment_id') or 'unallocated'}"
        definitions = [
            (source, "电量" if code == "electricity" else str(row.get("energy_type_name") or code), "source"),
            (area, str(row.get("area_name") or "未归集区域"), "area"),
            (device, str(row.get("equipment_name") or "未关联设备"), "equipment"),
        ]
        for key, name, category in definitions:
            node = nodes.setdefault(key, {"id": key, "name": name, "category": category, "value": 0})
            node["value"] += amount
        links[(source, area)] += amount
        links[(area, device)] += amount
    # Different physical units cannot share a width scale or a single total.
    mixed_units = len(units) > 1
    total = sum(float(row.get("energy_amount") or 0) for row in rows) if not mixed_units else None
    return {
        "unit": unit,
        "nodes": [] if mixed_units else list(nodes.values()),
        "links": []
        if mixed_units
        else [{"source": source, "target": target, "value": value} for (source, target), value in links.items()],
        "losses": [],
        "summary": {
            "total_input": total,
            "transform_loss": None,
            "distribution_loss": None,
            "total_loss": None,
            "loss_rate_pct": None,
            "utilized_energy": total,
            "high_loss_count": 0,
            "row_count": len(rows),
            "loss_threshold_pct": threshold_pct,
            "data_quality": "incompatible_units" if mixed_units else "metered_allocation_without_loss_measurement",
        },
    }


def _build_report_items(
    summary: dict[str, Any], links: list[dict[str, Any]], nodes: list[dict[str, Any]], unit: str | None
) -> list[dict[str, Any]]:
    total_input = float(summary.get("total_input") or 0)
    if total_input <= 0:
        return []
    top_links = sorted(
        [link for link in links if float(link.get("value") or 0) > 0],
        key=lambda item: float(item["value"]),
        reverse=True,
    )[:3]
    names = {node["id"]: node["name"] for node in nodes}
    top_link_text = "、".join(f"{names[item['source']]} -> {names[item['target']]}" for item in top_links) or "-"
    return [
        {
            "title": "能流结构复盘",
            "priority": "medium",
            "target": "主要能流链路",
            "evidence": {
                f"归集总量({unit})": round(total_input, 4),
                "链路数量": len([link for link in links if float(link.get("value") or 0) > 0]),
                "数据对象": int(summary.get("row_count") or 0),
                "重点链路": top_link_text,
            },
            "steps": [
                "按账期、能源品种、区域或设备筛选归集记录。",
                "查看已有计量记录的区域与设备归属。",
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
