# ruff: noqa: S608
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text

from app.db import models as m
from app.domain.energy.queries.common import jsonable_mapping, ratio_or_none
from app.domain.energy.queries.intensity import energy_area_denominators

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


TARGET_TYPES = {"enterprise", "area", "device_type", "device", "use_system", "line", "product"}
METRICS: dict[str, dict[str, str]] = {
    "kwh_per_run_hour": {"name": "单位运行小时用电", "unit": "kWh/h"},
    "kwh_per_workload": {"name": "单位作业量用电", "unit": "kWh/unit"},
    "kgce_per_unit": {"name": "单位产品综合能耗", "unit": "kgce/unit"},
    "kgce_per_10k_value": {"name": "单位产值综合能耗", "unit": "kgce/万元"},
    "tce_per_m2": {"name": "单位面积综合能耗", "unit": "tce/m2"},
    "kwh_per_m2": {"name": "单位面积用电量", "unit": "kWh/m2"},
}
DEFAULT_WARNING_THRESHOLD = 10.0
DEFAULT_SEVERE_THRESHOLD = 25.0


@dataclass(frozen=True, slots=True)
class EnergyBenchmarkQuery:
    period_start: str | None = None
    period_end: str | None = None
    profile_id: int | None = None
    target_type: str | None = "device"
    target_code: str | None = None
    metric_code: str | None = "kwh_per_run_hour"
    area_id: str | None = None
    limit: int = 50


@dataclass(frozen=True, slots=True)
class EnergyBenchmarkGenerateCommand:
    period_start: str | None
    period_end: str | None
    target_type: str
    metric_code: str
    profile_name: str
    method: str = "best_period"


class EnergyBenchmarkQueryService:
    """Read and calculation service for energy efficiency benchmarking."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def baseline(self, query: EnergyBenchmarkQuery) -> dict[str, Any]:
        target_type = _target_type(query.target_type)
        metric_code = _metric_code(query.metric_code)
        if metric_code in {"kwh_per_run_hour", "kwh_per_workload"}:
            candidates = await self._workload_baseline(query, target_type, metric_code)
        elif metric_code in {"tce_per_m2", "kwh_per_m2"}:
            candidates = await self._area_baseline(query, metric_code)
        else:
            candidates = await self._product_baseline(query, metric_code)
        return {
            "items": candidates,
            "metric": {"code": metric_code, **METRICS[metric_code]},
            "filters": _filters(query),
        }

    async def comparisons(self, query: EnergyBenchmarkQuery) -> dict[str, Any]:
        target_type = _target_type(query.target_type)
        metric_code = _metric_code(query.metric_code)
        profile_id = query.profile_id or await self._default_profile_id(target_type, metric_code)
        actual_rows = await self._actual_rows(query, target_type, metric_code)
        benchmark_rows = await self._benchmark_rows(profile_id, target_type, metric_code, query.target_code)
        wildcard = next((row for row in benchmark_rows if not row.get("target_code")), None)
        by_code = {str(row.get("target_code")): row for row in benchmark_rows if row.get("target_code")}
        items: list[dict[str, Any]] = []
        used_benchmark_ids: set[int] = set()

        for actual in actual_rows:
            code = str(actual.get("target_code") or "")
            benchmark = by_code.get(code) or wildcard
            if benchmark and benchmark.get("id"):
                used_benchmark_ids.add(int(benchmark["id"]))
            items.append(_comparison_row(actual, benchmark))

        actual_codes = {str(row.get("target_code") or "") for row in actual_rows}
        for benchmark in benchmark_rows:
            if benchmark.get("id") in used_benchmark_ids:
                continue
            code = str(benchmark.get("target_code") or "")
            if code and code in actual_codes:
                continue
            items.append(_comparison_row(None, benchmark))

        items.sort(key=lambda row: (row.get("status") == "ok", -(float(row.get("deviation_pct") or 0))))
        limit = max(1, min(query.limit, 200))
        return {
            "items": items[:limit],
            "total": len(items),
            "profile_id": profile_id,
            "metric": {"code": metric_code, **METRICS[metric_code]},
            "filters": _filters(query),
        }

    async def conclusions(self, query: EnergyBenchmarkQuery) -> dict[str, Any]:
        comparison = await self.comparisons(query)
        items = comparison["items"]
        status_counts: dict[str, int] = {}
        total_potential = 0.0
        for item in items:
            status = str(item.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            total_potential += float(item.get("saving_potential") or 0)
        return {
            "summary": {
                "total": len(items),
                "status_counts": status_counts,
                "saving_potential": round(total_potential, 4),
                "unit": comparison["metric"]["unit"].split("/")[0],
            },
            "top_deviations": [
                item
                for item in items
                if item.get("deviation_pct") is not None and item.get("status") in {"warning", "severe"}
            ][:10],
            "missing_benchmarks": [item for item in items if item.get("status") == "missing_benchmark"][:10],
            "filters": comparison["filters"],
        }

    async def recommendations(self, query: EnergyBenchmarkQuery) -> dict[str, Any]:
        conclusions = await self.conclusions(query)
        recommendations = [_recommendation_for(item) for item in conclusions["top_deviations"][:8]]
        if not recommendations and conclusions["missing_benchmarks"]:
            recommendations.append(
                {
                    "code": "complete-benchmark-library",
                    "priority": "medium",
                    "title": "补齐关键对象行业标杆",
                    "target": "行业标杆库",
                    "evidence": {"missing_count": len(conclusions["missing_benchmarks"])},
                    "steps": ["基于历史基线生成候选值", "补充来源和适用范围", "启用后重新执行对标"],
                    "expected_effect": "提升对标覆盖率和整改优先级排序质量。",
                }
            )
        return {"items": recommendations, "summary": conclusions["summary"], "filters": conclusions["filters"]}

    async def generate_from_history(self, command: EnergyBenchmarkGenerateCommand) -> dict[str, Any]:
        method = command.method if command.method in {"best_period", "p25", "average"} else "best_period"
        query = EnergyBenchmarkQuery(
            period_start=command.period_start,
            period_end=command.period_end,
            target_type=command.target_type,
            metric_code=command.metric_code,
            limit=200,
        )
        candidates = (await self.baseline(query))["items"]
        profile = m.EnergyBenchmarkProfile(
            name=command.profile_name.strip() or "行业标杆方案",
            scenario="历史基线生成",
            source_name="历史基线",
            is_enabled=True,
        )
        self._session.add(profile)
        await self._session.flush()

        value_key = {"best_period": "best_value", "p25": "p25_value", "average": "average_value"}[method]
        created_items = []
        for candidate in candidates:
            value = candidate.get(value_key)
            if value in (None, ""):
                continue
            item = m.EnergyBenchmarkItem(
                profile_id=profile.id,
                target_type=command.target_type,
                target_code=candidate.get("target_code"),
                target_name=candidate.get("target_name"),
                metric_code=command.metric_code,
                metric_name=METRICS[command.metric_code]["name"],
                benchmark_value=value,
                unit=METRICS[command.metric_code]["unit"],
                source_name="历史基线",
                confidence_level="medium",
                is_enabled=True,
            )
            self._session.add(item)
            created_items.append(item)
        await self._session.commit()
        await self._session.refresh(profile)
        return {
            "profile": jsonable_mapping(_model_dict(profile)),
            "created_count": len(created_items),
            "method": method,
        }

    async def _default_profile_id(self, target_type: str, metric_code: str) -> int | None:
        return await self._session.scalar(
            select(m.EnergyBenchmarkProfile.id)
            .join(m.EnergyBenchmarkItem, m.EnergyBenchmarkItem.profile_id == m.EnergyBenchmarkProfile.id)
            .where(m.EnergyBenchmarkProfile.is_enabled.is_(True))
            .where(m.EnergyBenchmarkItem.is_enabled.is_(True))
            .where(m.EnergyBenchmarkItem.target_type == target_type)
            .where(m.EnergyBenchmarkItem.metric_code == metric_code)
            .order_by(m.EnergyBenchmarkProfile.id.desc())
            .limit(1)
        )

    async def _benchmark_rows(
        self,
        profile_id: int | None,
        target_type: str,
        metric_code: str,
        target_code: str | None,
    ) -> list[dict[str, Any]]:
        conditions = [
            "i.is_enabled is true",
            "p.is_enabled is true",
            "i.target_type = :target_type",
            "i.metric_code = :metric_code",
        ]
        params: dict[str, Any] = {"target_type": target_type, "metric_code": metric_code}
        if profile_id is not None:
            conditions.append("i.profile_id = :profile_id")
            params["profile_id"] = profile_id
        if target_code:
            conditions.append("(i.target_code = :target_code or i.target_code is null or i.target_code = '')")
            params["target_code"] = target_code
        rows = (
            await self._session.execute(
                text(
                    f"""
                    select
                        i.id,
                        i.profile_id,
                        p.name as profile_name,
                        i.target_type,
                        i.target_code,
                        i.target_name,
                        i.metric_code,
                        i.metric_name,
                        i.benchmark_value,
                        i.unit,
                        i.excellent_value,
                        i.warning_threshold_pct,
                        i.severe_threshold_pct,
                        i.source_name,
                        i.confidence_level
                    from dataapp_energybenchmarkitem i
                    join dataapp_energybenchmarkprofile p on p.id = i.profile_id
                    where {" and ".join(conditions)}
                    order by i.target_code nulls last, i.id desc
                    """
                ),
                params,
            )
        ).mappings().all()
        return [jsonable_mapping(dict(row)) for row in rows]

    async def _actual_rows(self, query: EnergyBenchmarkQuery, target_type: str, metric_code: str) -> list[dict[str, Any]]:
        if metric_code in {"kwh_per_run_hour", "kwh_per_workload"}:
            return await self._workload_actuals(query, target_type, metric_code)
        if metric_code in {"tce_per_m2", "kwh_per_m2"}:
            return await self._area_actuals(query, metric_code)
        if metric_code in {"kgce_per_unit", "kgce_per_10k_value"}:
            return await self._product_actuals(query, metric_code)
        return []

    async def _workload_actuals(self, query: EnergyBenchmarkQuery, target_type: str, metric_code: str) -> list[dict[str, Any]]:
        target_expr = _workload_target_expr(target_type)
        if target_expr is None:
            return []
        target_code_expr, target_name_expr, target_filter = target_expr
        workload_field = "run_hours" if metric_code == "kwh_per_run_hour" else "workload_amount"
        where, params = _period_conditions(query, "e")
        workload_where, workload_params = _period_conditions(query, "w")
        if query.area_id:
            where.append("e.area_id = :area_id")
            workload_where.append("w.area_id = :area_id")
            params["area_id"] = query.area_id
            workload_params["area_id"] = query.area_id
        if query.target_code:
            where.append(f"{target_code_expr.replace('x.', 'e.')} = :target_code")
            workload_where.append(f"{target_code_expr.replace('x.', 'w.')} = :target_code")
            params["target_code"] = query.target_code
            workload_params["target_code"] = query.target_code
        where.append(target_filter.replace("x.", "e."))
        workload_where.append(target_filter.replace("x.", "w."))
        rows = (
            await self._session.execute(
                text(
                    f"""
                    with energy as (
                        select
                            {target_code_expr.replace('x.', 'e.')} as target_code,
                            {target_name_expr.replace('x.', 'e.')} as target_name,
                            coalesce(sum(e.amount), 0) as energy_kwh
                        from dataapp_energyintervalfact e
                        where {" and ".join(where)}
                        group by {target_code_expr.replace('x.', 'e.')}, {target_name_expr.replace('x.', 'e.')}
                    ),
                    workload as (
                        select
                            {target_code_expr.replace('x.', 'w.')} as target_code,
                            coalesce(sum(w.{workload_field}), 0) as denominator
                        from dataapp_equipmentworkloadfact w
                        where {" and ".join(workload_where)} and w.record_status = 'confirmed'
                        group by {target_code_expr.replace('x.', 'w.')}
                    )
                    select
                        :target_type as target_type,
                        energy.target_code,
                        energy.target_name,
                        :metric_code as metric_code,
                        energy.energy_kwh,
                        workload.denominator,
                        case when workload.denominator > 0 then energy.energy_kwh / workload.denominator else null end as actual_value,
                        :unit as unit,
                        case when workload.denominator > 0 then 'measured' else 'invalid_denominator' end as data_quality
                    from energy
                    left join workload on workload.target_code = energy.target_code
                    order by actual_value desc nulls last
                    limit :limit
                    """
                ),
                {
                    **params,
                    **workload_params,
                    "target_type": target_type,
                    "metric_code": metric_code,
                    "unit": METRICS[metric_code]["unit"],
                    "limit": max(1, min(query.limit, 200)),
                },
            )
        ).mappings().all()
        return [jsonable_mapping(dict(row)) for row in rows]

    async def _area_actuals(self, query: EnergyBenchmarkQuery, metric_code: str) -> list[dict[str, Any]]:
        denominators = await energy_area_denominators(self._session)
        area = denominators.get("store_area") or denominators.get("park_area")
        where, params = _fact_period_conditions(query)
        row = (
            await self._session.execute(
                text(
                    f"""
                    select
                        coalesce(sum(tce_amount), 0) as total_tce,
                        coalesce(sum(case when energy_type_code = 'purchased_electricity' then original_amount else 0 end), 0) as electricity_kwh
                    from energy_consumption_fact_v
                    {"where " + " and ".join(where) if where else ""}
                    """
                ),
                params,
            )
        ).mappings().one()
        total = jsonable_mapping(dict(row))
        numerator = total["total_tce"] if metric_code == "tce_per_m2" else total["electricity_kwh"]
        return [
            {
                "target_type": "enterprise",
                "target_code": "enterprise",
                "target_name": denominators.get("enterprise", {}).get("name") or "企业整体",
                "metric_code": metric_code,
                "actual_value": ratio_or_none(numerator, area),
                "denominator": area,
                "unit": METRICS[metric_code]["unit"],
                "data_quality": "measured" if area else "invalid_denominator",
            }
        ]

    async def _product_actuals(self, query: EnergyBenchmarkQuery, metric_code: str) -> list[dict[str, Any]]:
        where, params = _fact_period_conditions(query)
        energy = (
            await self._session.execute(
                text(
                    f"""
                    select coalesce(sum(standard_amount), 0) as total_kgce
                    from energy_consumption_fact_v
                    {"where " + " and ".join(where) if where else ""}
                    """
                ),
                params,
            )
        ).mappings().one()
        production_where, production_params = _production_period_conditions(query)
        if query.target_code:
            production_where.append("o.product_code = :target_code")
            production_params["target_code"] = query.target_code
        value_expr = """
            coalesce(sum(
                o.standard_qty * coalesce((
                    select pp.price
                    from dataapp_productprice pp
                    where pp.team_id = o.team_id
                      and pp.product_code = o.product_code
                      and pp.price_type = 'standard_price'
                    order by pp.valid_from desc nulls last, pp.id desc
                    limit 1
                ), 0)
            ), 0)
        """
        rows = (
            await self._session.execute(
                text(
                    f"""
                    select
                        'product' as target_type,
                        o.product_code as target_code,
                        coalesce(max(o.product_name), o.product_code) as target_name,
                        coalesce(sum(o.standard_qty), 0) as standard_qty,
                        {value_expr} as output_value
                    from dataapp_productionoutputfact o
                    where {" and ".join(production_where)}
                    group by o.product_code
                    order by sum(o.standard_qty) desc
                    limit :limit
                    """
                ),
                {**production_params, "limit": max(1, min(query.limit, 200))},
            )
        ).mappings().all()
        total_kgce = float(energy["total_kgce"] or 0)
        result = []
        for row in rows:
            item = jsonable_mapping(dict(row))
            denominator = item["standard_qty"] if metric_code == "kgce_per_unit" else float(item["output_value"] or 0) / 10000
            result.append(
                {
                    "target_type": "product",
                    "target_code": item["target_code"],
                    "target_name": item["target_name"],
                    "metric_code": metric_code,
                    "actual_value": ratio_or_none(total_kgce, denominator),
                    "denominator": denominator,
                    "unit": METRICS[metric_code]["unit"],
                    "data_quality": "measured" if denominator else "invalid_denominator",
                }
            )
        return result

    async def _workload_baseline(self, query: EnergyBenchmarkQuery, target_type: str, metric_code: str) -> list[dict[str, Any]]:
        target_expr = _workload_target_expr(target_type)
        if target_expr is None:
            return []
        target_code_expr, target_name_expr, target_filter = target_expr
        workload_field = "run_hours" if metric_code == "kwh_per_run_hour" else "workload_amount"
        where, params = _period_conditions(query, "e")
        workload_where, workload_params = _period_conditions(query, "w")
        where.append(target_filter.replace("x.", "e."))
        workload_where.append(target_filter.replace("x.", "w."))
        rows = (
            await self._session.execute(
                text(
                    f"""
                    with energy as (
                        select
                            {target_code_expr.replace('x.', 'e.')} as target_code,
                            {target_name_expr.replace('x.', 'e.')} as target_name,
                            date_trunc('month', e.period_start) as period,
                            coalesce(sum(e.amount), 0) as energy_kwh
                        from dataapp_energyintervalfact e
                        where {" and ".join(where)}
                        group by {target_code_expr.replace('x.', 'e.')}, {target_name_expr.replace('x.', 'e.')}, date_trunc('month', e.period_start)
                    ),
                    workload as (
                        select
                            {target_code_expr.replace('x.', 'w.')} as target_code,
                            date_trunc('month', w.period_start) as period,
                            coalesce(sum(w.{workload_field}), 0) as denominator
                        from dataapp_equipmentworkloadfact w
                        where {" and ".join(workload_where)} and w.record_status = 'confirmed'
                        group by {target_code_expr.replace('x.', 'w.')}, date_trunc('month', w.period_start)
                    ),
                    ratio_rows as (
                        select
                            energy.target_code,
                            energy.target_name,
                            energy.period,
                            case when workload.denominator > 0 then energy.energy_kwh / workload.denominator else null end as ratio_value
                        from energy
                        join workload on workload.target_code = energy.target_code and workload.period = energy.period
                        where workload.denominator > 0
                    )
                    select
                        :target_type as target_type,
                        target_code,
                        target_name,
                        :metric_code as metric_code,
                        min(ratio_value) as best_value,
                        percentile_cont(0.25) within group (order by ratio_value) as p25_value,
                        avg(ratio_value) as average_value,
                        count(*)::int as period_count,
                        :unit as unit
                    from ratio_rows
                    group by target_code, target_name
                    order by best_value asc nulls last
                    limit :limit
                    """
                ),
                {
                    **params,
                    **workload_params,
                    "target_type": target_type,
                    "metric_code": metric_code,
                    "unit": METRICS[metric_code]["unit"],
                    "limit": max(1, min(query.limit, 200)),
                },
            )
        ).mappings().all()
        return [jsonable_mapping(dict(row)) for row in rows]

    async def _area_baseline(self, query: EnergyBenchmarkQuery, metric_code: str) -> list[dict[str, Any]]:
        actuals = await self._area_actuals(query, metric_code)
        return [
            {
                **actuals[0],
                "best_value": actuals[0]["actual_value"],
                "p25_value": actuals[0]["actual_value"],
                "average_value": actuals[0]["actual_value"],
                "period_count": 1 if actuals[0]["actual_value"] is not None else 0,
            }
        ]

    async def _product_baseline(self, query: EnergyBenchmarkQuery, metric_code: str) -> list[dict[str, Any]]:
        actuals = await self._product_actuals(query, metric_code)
        return [
            {
                **row,
                "best_value": row["actual_value"],
                "p25_value": row["actual_value"],
                "average_value": row["actual_value"],
                "period_count": 1 if row["actual_value"] is not None else 0,
            }
            for row in actuals
        ]


def _workload_target_expr(target_type: str) -> tuple[str, str, str] | None:
    if target_type == "device":
        return ("x.equipment_id::text", "coalesce(x.equipment_name, x.equipment_code, '未命名设备')", "x.equipment_id is not null")
    if target_type == "use_system":
        return ("x.use_system_code", "coalesce(x.use_system_code, '未归类')", "x.use_system_code is not null")
    if target_type == "area":
        return ("x.area_id", "coalesce(x.area_name, '未分区')", "x.area_id is not null")
    return None


def _period_conditions(query: EnergyBenchmarkQuery, alias: str) -> tuple[list[str], dict[str, Any]]:
    conditions = ["1=1"]
    params: dict[str, Any] = {}
    if query.period_start:
        conditions.append(f"{alias}.period_end >= (:period_start)::timestamp")
        params["period_start"] = query.period_start
    if query.period_end:
        conditions.append(f"{alias}.period_start <= (:period_end)::timestamp")
        params["period_end"] = query.period_end
    return conditions, params


def _fact_period_conditions(query: EnergyBenchmarkQuery) -> tuple[list[str], dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}
    if query.period_start:
        conditions.append("period_end >= (:period_start)::timestamp")
        params["period_start"] = query.period_start
    if query.period_end:
        conditions.append("period_start <= (:period_end)::timestamp")
        params["period_end"] = query.period_end
    return conditions, params


def _production_period_conditions(query: EnergyBenchmarkQuery) -> tuple[list[str], dict[str, Any]]:
    conditions = ["o.record_status = 'confirmed'"]
    params: dict[str, Any] = {}
    if query.period_start:
        conditions.append("o.period_end >= (:period_start)::date")
        params["period_start"] = query.period_start
    if query.period_end:
        conditions.append("o.period_start <= (:period_end)::date")
        params["period_end"] = query.period_end
    return conditions, params


def _target_type(value: str | None) -> str:
    return value if value in TARGET_TYPES else "device"


def _metric_code(value: str | None) -> str:
    return value if value in METRICS else "kwh_per_run_hour"


def _comparison_row(actual: dict[str, Any] | None, benchmark: dict[str, Any] | None) -> dict[str, Any]:
    base = actual or benchmark or {}
    actual_value = actual.get("actual_value") if actual else None
    benchmark_value = benchmark.get("benchmark_value") if benchmark else None
    denominator = actual.get("denominator") if actual else None
    unit = (actual or {}).get("unit") or (benchmark or {}).get("unit")
    status = "ok"
    deviation_pct = None
    saving_potential = None
    if benchmark is None:
        status = "missing_benchmark"
    elif actual is None or actual_value is None:
        status = "invalid_denominator"
    elif unit != benchmark.get("unit"):
        status = "unit_mismatch"
    elif not benchmark_value:
        status = "missing_benchmark"
    else:
        deviation_pct = round((float(actual_value) - float(benchmark_value)) / float(benchmark_value) * 100, 2)
        severe = float(benchmark.get("severe_threshold_pct") or DEFAULT_SEVERE_THRESHOLD)
        warning = float(benchmark.get("warning_threshold_pct") or DEFAULT_WARNING_THRESHOLD)
        if deviation_pct >= severe:
            status = "severe"
        elif deviation_pct >= warning:
            status = "warning"
        else:
            status = "ok"
        if denominator:
            saving_potential = round(max(0.0, float(actual_value) - float(benchmark_value)) * float(denominator), 4)
    return {
        "target_type": base.get("target_type"),
        "target_code": base.get("target_code"),
        "target_name": base.get("target_name"),
        "metric_code": base.get("metric_code"),
        "metric_name": (benchmark or {}).get("metric_name") or METRICS.get(str(base.get("metric_code")), {}).get("name"),
        "actual_value": actual_value,
        "benchmark_value": benchmark_value,
        "unit": unit,
        "deviation_pct": deviation_pct,
        "status": status,
        "saving_potential": saving_potential,
        "data_quality": (actual or {}).get("data_quality") or "missing_actual",
        "profile_id": (benchmark or {}).get("profile_id"),
        "profile_name": (benchmark or {}).get("profile_name"),
        "source_name": (benchmark or {}).get("source_name"),
        "confidence_level": (benchmark or {}).get("confidence_level"),
    }


def _recommendation_for(item: dict[str, Any]) -> dict[str, Any]:
    metric_code = item.get("metric_code")
    title = "优化设备运行效率"
    steps = ["核查设备运行小时与负荷匹配情况", "排查空载、待机和异常启停", "对偏差较大的设备安排巡检"]
    if metric_code == "kwh_per_workload":
        title = "降低单位作业量用电"
        steps = ["复核作业量归集口径", "检查高耗能作业时段", "优化班次和设备负荷分配"]
    elif metric_code in {"kgce_per_unit", "kgce_per_10k_value"}:
        title = "优化产品能耗强度"
        steps = ["核查产品产量和价格口径", "检查产线资源绑定", "优先分析高偏差产品批次"]
    elif metric_code in {"tce_per_m2", "kwh_per_m2"}:
        title = "优化面积能耗强度"
        steps = ["分解区域和公共系统能耗", "检查空调、照明、空压运行策略", "跟踪高强度区域整改效果"]
    return {
        "code": f"benchmark-{metric_code}-{item.get('target_code') or 'target'}",
        "priority": "high" if item.get("status") == "severe" else "medium",
        "title": title,
        "target": item.get("target_name") or item.get("target_code") or "-",
        "evidence": {
            "metric_code": metric_code,
            "actual_value": item.get("actual_value"),
            "benchmark_value": item.get("benchmark_value"),
            "deviation_pct": item.get("deviation_pct"),
            "saving_potential": item.get("saving_potential"),
        },
        "steps": steps,
        "expected_effect": "降低偏差对象的单位能耗并提升对标达标率。",
    }


def _filters(query: EnergyBenchmarkQuery) -> dict[str, Any]:
    return {
        "period_start": query.period_start,
        "period_end": query.period_end,
        "profile_id": query.profile_id,
        "target_type": query.target_type,
        "target_code": query.target_code,
        "metric_code": query.metric_code,
        "area_id": query.area_id,
    }


def _model_dict(obj: Any) -> dict[str, Any]:
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}
