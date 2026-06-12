# ruff: noqa: S608
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.domain.energy.queries.common import jsonable_mapping, ratio_or_none

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


DEFAULT_LOSS_THRESHOLD_PCT = 5.0
DEFAULT_TRANSFORM_LOSS_RATE = 0.02
DEFAULT_DISTRIBUTION_LOSS_RATE = 0.03


@dataclass(frozen=True, slots=True)
class EnergyFlowQuery:
    """Read-model query parameters for energy flow analysis."""

    period_start: str | None = None
    period_end: str | None = None
    granularity: str = "day"
    energy_type_code: str | None = None
    area_keyword: str | None = None
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
        transform_loss = float(summary["transform_loss"])
        distribution_loss = float(summary["distribution_loss"])
        utilized = float(summary["utilized_energy"])
        balance_error = round(total_input - transform_loss - distribution_loss - utilized, 6)
        error_pct = ratio_or_none(abs(balance_error) * 100, total_input, 4)
        return {
            "table": [
                {"label": "输入", "value": round(total_input, 4), "unit": "kWh"},
                {"label": "转换损耗", "value": round(transform_loss, 4), "unit": "kWh"},
                {"label": "分配损耗", "value": round(distribution_loss, 4), "unit": "kWh"},
                {"label": "有效利用", "value": round(utilized, 4), "unit": "kWh"},
                {"label": "平衡差异", "value": balance_error, "unit": "kWh"},
            ],
            "diagnostics": [
                {"label": "平衡误差率", "value": f"{error_pct or 0}%"},
                {"label": "高损耗链路", "value": int(summary["high_loss_count"])},
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
        high_losses = [item for item in model["losses"] if item["status"] == "high_loss"]
        focus = high_losses[:5] or model["losses"][:3]
        return {
            "summary": model["summary"],
            "items": [_report_item(item) for item in focus],
            "filters": _filters(query),
        }

    async def _flow_rows(self, query: EnergyFlowQuery) -> list[dict[str, Any]]:
        where_sql, params = _build_filters(query)
        sql = text(
            f"""
            select
                energy_type_code,
                case energy_type_code
                    when 'purchased_electricity' then '外购电力'
                    when 'purchased_heat' then '外购热力'
                    when 'purchased_steam' then '外购蒸汽'
                    when 'purchased_cooling' then '外购冷量'
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


def _build_filters(query: EnergyFlowQuery) -> tuple[str, dict[str, Any]]:
    conditions = ["granularity = :source_granularity"]
    params: dict[str, Any] = {"source_granularity": "hour" if query.granularity == "hour" else "day"}
    if query.period_start:
        conditions.append("period_end >= (:period_start)::timestamp")
        params["period_start"] = query.period_start
    if query.period_end:
        conditions.append("period_start <= (:period_end)::timestamp")
        params["period_end"] = query.period_end
    if query.energy_type_code and query.energy_type_code != "all":
        conditions.append("energy_type_code = :energy_type_code")
        params["energy_type_code"] = query.energy_type_code
    if query.use_system_code and query.use_system_code != "all":
        conditions.append("use_system_code = :use_system_code")
        params["use_system_code"] = query.use_system_code
    if query.area_keyword:
        conditions.append("(area_name ilike :area_keyword or area_id ilike :area_keyword or equipment_name ilike :area_keyword)")
        params["area_keyword"] = f"%{query.area_keyword.strip()}%"
    return f"where {' and '.join(conditions)}", params


def _build_flow_model(rows: list[dict[str, Any]], threshold_pct: float) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []
    losses: list[dict[str, Any]] = []
    totals = _collect_totals(rows)
    total_input = sum(totals["energy"].values())
    total_transform_loss = total_input * DEFAULT_TRANSFORM_LOSS_RATE
    total_after_transform = max(total_input - total_transform_loss, 0)
    total_distribution_loss = total_after_transform * DEFAULT_DISTRIBUTION_LOSS_RATE
    total_utilized = max(total_after_transform - total_distribution_loss, 0)

    nodes["input"] = {"id": "input", "name": "能源输入", "category": "source", "value": round(total_input, 4)}
    nodes["conversion"] = {
        "id": "conversion",
        "name": "转换/计量",
        "category": "conversion",
        "value": round(total_after_transform, 4),
    }
    nodes["distribution"] = {
        "id": "distribution",
        "name": "分配网络",
        "category": "distribution",
        "value": round(total_utilized, 4),
    }
    _append_loss_node(
        nodes,
        links,
        losses,
        source="input",
        target="loss:transform",
        name="转换损耗",
        input_amount=total_input,
        loss_amount=total_transform_loss,
        threshold_pct=threshold_pct,
        stage="转换",
    )
    links.append({"source": "input", "target": "conversion", "value": round(total_after_transform, 4)})
    _append_loss_node(
        nodes,
        links,
        losses,
        source="conversion",
        target="loss:distribution",
        name="分配损耗",
        input_amount=total_after_transform,
        loss_amount=total_distribution_loss,
        threshold_pct=threshold_pct,
        stage="分配",
    )
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
    for (system_code, area_key), amount in sorted(totals["system_area"].items(), key=lambda item: item[1], reverse=True)[:80]:
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

    losses.sort(key=lambda item: item["loss_rate_pct"], reverse=True)
    high_loss_count = sum(1 for item in losses if item["status"] == "high_loss")
    return {
        "nodes": list(nodes.values()),
        "links": [link for link in links if link["value"] > 0],
        "losses": losses,
        "summary": {
            "total_input": round(total_input, 4),
            "transform_loss": round(total_transform_loss, 4),
            "distribution_loss": round(total_distribution_loss, 4),
            "total_loss": round(total_transform_loss + total_distribution_loss, 4),
            "loss_rate_pct": ratio_or_none((total_transform_loss + total_distribution_loss) * 100, total_input, 4) or 0,
            "utilized_energy": round(total_utilized, 4),
            "high_loss_count": high_loss_count,
            "row_count": len(rows),
            "loss_threshold_pct": threshold_pct,
            "data_quality": "estimated_loss_model",
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


def _append_loss_node(
    nodes: dict[str, dict[str, Any]],
    links: list[dict[str, Any]],
    losses: list[dict[str, Any]],
    *,
    source: str,
    target: str,
    name: str,
    input_amount: float,
    loss_amount: float,
    threshold_pct: float,
    stage: str,
) -> None:
    loss_rate_pct = ratio_or_none(loss_amount * 100, input_amount, 4) or 0
    status = "high_loss" if loss_rate_pct >= threshold_pct else "normal"
    nodes[target] = {"id": target, "name": name, "category": "loss", "value": round(loss_amount, 4)}
    links.append({"source": source, "target": target, "value": round(loss_amount, 4)})
    losses.append(
        {
            "stage": stage,
            "source": source,
            "target": name,
            "input_amount": round(input_amount, 4),
            "loss_amount": round(loss_amount, 4),
            "loss_rate_pct": loss_rate_pct,
            "threshold_pct": threshold_pct,
            "status": status,
            "suggestion": _loss_suggestion(stage, status),
        }
    )


def _loss_suggestion(stage: str, status: str) -> str:
    if status != "high_loss":
        return "保持周期复核。"
    if stage == "转换":
        return "复核变压器、计量装置和转换设备效率。"
    return "复核分配网络、线路损耗和末端计量覆盖。"


def _report_item(loss: dict[str, Any]) -> dict[str, Any]:
    priority = "high" if loss["status"] == "high_loss" else "medium"
    return {
        "title": f"{loss['stage']}环节损耗复核",
        "priority": priority,
        "target": loss["target"],
        "evidence": {
            "input_amount": loss["input_amount"],
            "loss_amount": loss["loss_amount"],
            "loss_rate_pct": loss["loss_rate_pct"],
            "threshold_pct": loss["threshold_pct"],
        },
        "steps": [
            "核对该环节输入、输出和计量点覆盖。",
            "检查异常时段、补录记录和设备运行状态。",
            "形成整改动作并在下一统计周期复核损耗率。",
        ],
        "expected_effect": loss["suggestion"],
    }


def _scale(target_total: float, source_total: float) -> float:
    if source_total <= 0:
        return 0
    return target_total / source_total


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
        "area_keyword": query.area_keyword,
        "use_system_code": query.use_system_code,
        "loss_threshold_pct": _threshold(query.loss_threshold_pct),
    }
