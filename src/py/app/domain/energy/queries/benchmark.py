# ruff: noqa: S608
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select, text

from app.db import models as m
from app.domain.energy.queries.common import jsonable_mapping, period_param, ratio_or_none
from app.domain.energy.queries.intensity import energy_area_denominators
from app.lib.tenancy import require_session_tenant_id

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
    "energy_efficiency_level": {"name": "设备能效等级", "unit": "级"},
}
DEFAULT_WARNING_THRESHOLD = 10.0
DEFAULT_SEVERE_THRESHOLD = 25.0
MAX_TREND_MONTHS = 24
DECEMBER = 12


@dataclass(frozen=True, slots=True)
class EnergyBenchmarkQuery:
    period_start: str | None = None
    period_end: str | None = None
    profile_id: int | None = None
    target_type: str | None = "device"
    target_code: str | None = None
    metric_code: str | None = "kwh_per_run_hour"
    area_id: str | None = None
    library_type: str | None = None
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
        profile_id = query.profile_id or await self._default_profile_id(target_type, metric_code, query.library_type)
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

    async def summary(self, query: EnergyBenchmarkQuery) -> dict[str, Any]:
        comparison = await self.comparisons(query)
        items = comparison["items"]
        compared = [
            item
            for item in items
            if item.get("actual_value") is not None and item.get("benchmark_value") is not None and item.get("status") != "unit_mismatch"
        ]
        warning_items = [item for item in compared if item.get("status") in {"warning", "severe"}]
        deviations = [float(item["deviation_pct"]) for item in compared if item.get("deviation_pct") is not None]
        potential = sum(float(item.get("saving_potential") or 0) for item in compared)
        coverage_rate = round(len(compared) / len(items) * 100, 2) if items else 0.0
        return {
            "summary": {
                "total": len(items),
                "compared": len(compared),
                "warning_total": len(warning_items),
                "severe_total": len([item for item in warning_items if item.get("status") == "severe"]),
                "coverage_rate": coverage_rate,
                "average_deviation_pct": round(sum(deviations) / len(deviations), 2) if deviations else None,
                "saving_potential": round(potential, 4),
                "unit": comparison["metric"]["unit"].split("/")[0],
            },
            "filters": comparison["filters"],
            "metric": comparison["metric"],
        }

    async def coverage(self, query: EnergyBenchmarkQuery) -> dict[str, Any]:
        comparison = await self.comparisons(query)
        items = comparison["items"]
        status_counts: dict[str, int] = {}
        for item in items:
            status = str(item.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "items": [
                {"status": status, "count": count}
                for status, count in sorted(status_counts.items(), key=lambda value: value[0])
            ],
            "total": len(items),
            "filters": comparison["filters"],
        }

    async def distribution(self, query: EnergyBenchmarkQuery) -> dict[str, Any]:
        comparison = await self.comparisons(query)
        labels = {
            "ok": "达标",
            "warning": "接近预警",
            "severe": "明显偏高",
            "missing_benchmark": "缺少标杆",
            "invalid_denominator": "缺少分母",
            "unit_mismatch": "单位不一致",
        }
        counts: dict[str, int] = {}
        for item in comparison["items"]:
            status = str(item.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
        return {
            "items": [{"name": labels.get(status, status), "status": status, "value": count} for status, count in counts.items()],
            "filters": comparison["filters"],
        }

    async def trend(self, query: EnergyBenchmarkQuery) -> dict[str, Any]:
        periods = _month_windows(query.period_start, query.period_end)
        rows = []
        for start, end in periods:
            period_query = EnergyBenchmarkQuery(
                period_start=start.isoformat(),
                period_end=end.isoformat(),
                profile_id=query.profile_id,
                target_type=query.target_type,
                target_code=query.target_code,
                metric_code=query.metric_code,
                area_id=query.area_id,
                library_type=query.library_type,
                limit=query.limit,
            )
            comparison = await self.comparisons(period_query)
            comparable = [
                item
                for item in comparison["items"]
                if item.get("actual_value") is not None and item.get("benchmark_value") is not None
            ]
            actual_values = [float(item["actual_value"]) for item in comparable]
            benchmark_values = [float(item["benchmark_value"]) for item in comparable]
            rows.append(
                {
                    "period": start.strftime("%Y-%m"),
                    "actual": round(sum(actual_values) / len(actual_values), 6) if actual_values else None,
                    "benchmark": round(sum(benchmark_values) / len(benchmark_values), 6) if benchmark_values else None,
                    "severe_count": len([item for item in comparable if item.get("status") == "severe"]),
                    "warning_count": len([item for item in comparable if item.get("status") == "warning"]),
                }
            )
        return {"items": rows, "filters": _filters(query), "metric": {"code": _metric_code(query.metric_code), **METRICS[_metric_code(query.metric_code)]}}

    async def detail(self, query: EnergyBenchmarkQuery) -> dict[str, Any]:
        comparison = await self.comparisons(EnergyBenchmarkQuery(**{**_filters(query), "limit": 200}))
        target_code = query.target_code
        selected = next((item for item in comparison["items"] if str(item.get("target_code") or "") == str(target_code or "")), None)
        if selected is None and comparison["items"]:
            selected = comparison["items"][0]
        return {
            "item": selected,
            "data_sources": _data_sources_for(selected or {}, _metric_code(query.metric_code)),
            "filters": comparison["filters"],
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
        profile_name = command.profile_name.strip() or "历史基准方案"
        profiles = list(
            (
                await self._session.scalars(
                    select(m.EnergyBenchmarkProfile)
                    .where(
                        m.EnergyBenchmarkProfile.name == profile_name,
                        m.EnergyBenchmarkProfile.source_name == "历史基线",
                        m.EnergyBenchmarkProfile.library_type == "enterprise_internal",
                    )
                    .order_by(m.EnergyBenchmarkProfile.id.asc())
                )
            ).all()
        )
        profile = profiles[0] if profiles else None
        for duplicate in profiles[1:]:
            await self._session.execute(delete(m.EnergyBenchmarkItem).where(m.EnergyBenchmarkItem.profile_id == duplicate.id))
            await self._session.delete(duplicate)
        if profile is None:
            profile = await self._session.scalar(
                select(m.EnergyBenchmarkProfile).where(
                    m.EnergyBenchmarkProfile.name == profile_name,
                    m.EnergyBenchmarkProfile.source_name == "历史基线",
                    m.EnergyBenchmarkProfile.library_type == "enterprise_internal",
                )
            )
        if profile is None:
            profile = m.EnergyBenchmarkProfile(name=profile_name)
            self._session.add(profile)
        profile.scenario = "历史基线生成"
        profile.source_name = "历史基线"
        profile.library_type = "enterprise_internal"
        profile.version_status = "active"
        profile.is_enabled = True
        await self._session.flush()

        value_key = {"best_period": "best_value", "p25": "p25_value", "average": "average_value"}[method]
        upserted_count = 0
        for candidate in candidates:
            value = candidate.get(value_key)
            if value in (None, ""):
                continue
            target_code = candidate.get("target_code")
            stmt = (
                select(m.EnergyBenchmarkItem)
                .where(m.EnergyBenchmarkItem.profile_id == profile.id)
                .where(m.EnergyBenchmarkItem.target_type == command.target_type)
                .where(m.EnergyBenchmarkItem.metric_code == command.metric_code)
            )
            if target_code in (None, ""):
                stmt = stmt.where(m.EnergyBenchmarkItem.target_code.is_(None))
            else:
                stmt = stmt.where(m.EnergyBenchmarkItem.target_code == str(target_code))
            item = await self._session.scalar(stmt)
            if item is None:
                item = m.EnergyBenchmarkItem(
                    profile_id=profile.id,
                    target_type=command.target_type,
                    target_code=str(target_code) if target_code not in (None, "") else None,
                    metric_code=command.metric_code,
                )
                self._session.add(item)
            item.target_name = candidate.get("target_name")
            item.metric_name = METRICS[command.metric_code]["name"]
            item.benchmark_value = value
            item.unit = METRICS[command.metric_code]["unit"]
            item.source_name = "历史基线"
            item.metric_direction = _metric_direction(command.metric_code)
            item.standard_level = "internal_baseline"
            item.version_status = "active"
            item.confidence_level = "medium"
            item.is_enabled = True
            upserted_count += 1
        await self._session.commit()
        await self._session.refresh(profile)
        return {
            "profile": jsonable_mapping(_model_dict(profile)),
            "created_count": upserted_count,
            "method": method,
        }

    async def _default_profile_id(self, target_type: str, metric_code: str, library_type: str | None) -> int | None:
        stmt = (
            select(m.EnergyBenchmarkProfile.id)
            .join(m.EnergyBenchmarkItem, m.EnergyBenchmarkItem.profile_id == m.EnergyBenchmarkProfile.id)
            .where(m.EnergyBenchmarkProfile.is_enabled.is_(True))
            .where(m.EnergyBenchmarkItem.is_enabled.is_(True))
            .where(m.EnergyBenchmarkItem.target_type == target_type)
            .where(m.EnergyBenchmarkItem.metric_code == metric_code)
            .order_by(
                text(
                    "case "
                    "when dataapp_energybenchmarkprofile.library_type in ('policy_industry', 'equipment_efficiency') then 0 "
                    "when dataapp_energybenchmarkprofile.library_type = 'enterprise_standard' then 1 "
                    "else 2 end"
                ),
                m.EnergyBenchmarkProfile.id.desc(),
            )
            .limit(1)
        )
        if library_type:
            stmt = stmt.where(m.EnergyBenchmarkProfile.library_type == library_type)
        return await self._session.scalar(stmt)

    async def _benchmark_rows(
        self,
        profile_id: int | None,
        target_type: str,
        metric_code: str,
        target_code: str | None,
    ) -> list[dict[str, Any]]:
        team_id = require_session_tenant_id(self._session)
        conditions = [
            "i.team_id = :team_id",
            "p.team_id = :team_id",
            "i.is_enabled is true",
            "p.is_enabled is true",
            "i.target_type = :target_type",
            "i.metric_code = :metric_code",
        ]
        params: dict[str, Any] = {
            "team_id": str(team_id),
            "target_type": target_type,
            "metric_code": metric_code,
        }
        if profile_id is not None:
            conditions.append("i.profile_id = :profile_id")
            params["profile_id"] = profile_id
        if target_code:
            conditions.append("(i.target_code = :target_code or i.target_code is null or i.target_code = '')")
            params["target_code"] = target_code
        rows = (
            (
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
                        i.standard_code,
                        i.source_url,
                        i.source_hash,
                        i.applicable_industry,
                        i.applicable_category,
                        i.applicable_condition,
                        i.metric_direction,
                        i.advanced_value,
                        i.saving_value,
                        i.access_value,
                        i.baseline_value,
                        i.advanced_level,
                        i.saving_level,
                        i.access_level,
                        i.standard_level,
                        i.version_status,
                        i.reference_standard,
                        i.excellent_value,
                        i.warning_threshold_pct,
                        i.severe_threshold_pct,
                        i.source_name,
                        i.confidence_level
                    from dataapp_energybenchmarkitem i
                    join dataapp_energybenchmarkprofile p
                      on p.id = i.profile_id and p.team_id = i.team_id
                    where {" and ".join(conditions)}
                    order by i.target_code nulls last, i.id desc
                    """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        return [jsonable_mapping(dict(row)) for row in rows]

    async def _actual_rows(
        self, query: EnergyBenchmarkQuery, target_type: str, metric_code: str
    ) -> list[dict[str, Any]]:
        if metric_code in {"kwh_per_run_hour", "kwh_per_workload"}:
            return await self._workload_actuals(query, target_type, metric_code)
        if metric_code in {"tce_per_m2", "kwh_per_m2"}:
            return await self._area_actuals(query, metric_code)
        if metric_code in {"kgce_per_unit", "kgce_per_10k_value"}:
            return await self._product_actuals(query, metric_code)
        if metric_code == "energy_efficiency_level":
            return await self._equipment_efficiency_actuals(query, target_type)
        return []

    async def _equipment_efficiency_actuals(self, query: EnergyBenchmarkQuery, target_type: str) -> list[dict[str, Any]]:
        if target_type not in {"device_type", "device"}:
            return []
        team_id = require_session_tenant_id(self._session)
        benchmark_category_expr = _equipment_efficiency_category_expr()
        if target_type == "device":
            target_code_expr = "e.code"
            target_name_expr = "coalesce(e.name, e.code)"
            group_expr = "e.code, coalesce(e.name, e.code)"
        else:
            target_code_expr = benchmark_category_expr
            target_name_expr = _equipment_efficiency_category_name_expr(benchmark_category_expr)
            group_expr = f"{benchmark_category_expr}, {_equipment_efficiency_category_name_expr(benchmark_category_expr)}"
        conditions = [
            "e.team_id = :team_id",
            "e.energy_efficiency_level is not null",
            "coalesce(e.is_enable, true) is true",
        ]
        params: dict[str, Any] = {"team_id": str(team_id)}
        if target_type == "device_type":
            conditions.append(f"{benchmark_category_expr} is not null")
        if query.target_code:
            conditions.append(f"{target_code_expr} = :target_code")
            params["target_code"] = query.target_code
        rows = (
            (
                await self._session.execute(
                    text(
                        f"""
                    select
                        :target_type as target_type,
                        {target_code_expr} as target_code,
                        {target_name_expr} as target_name,
                        :metric_code as metric_code,
                        avg(e.energy_efficiency_level)::numeric as actual_value,
                        count(*)::numeric as denominator,
                        :unit as unit,
                        'equipment_master_data' as data_quality
                    from dataapp_monitorequipment e
                    left join dataapp_devicetype dt on dt.id = e.device_type_id
                    where {" and ".join(conditions)}
                    group by {group_expr}
                    order by actual_value asc nulls last
                    limit :limit
                    """
                    ),
                    {
                        **params,
                        "target_type": target_type,
                        "metric_code": "energy_efficiency_level",
                        "unit": METRICS["energy_efficiency_level"]["unit"],
                        "limit": max(1, min(query.limit, 200)),
                    },
                )
            )
            .mappings()
            .all()
        )
        return [jsonable_mapping(dict(row)) for row in rows]

    async def _workload_actuals(
        self, query: EnergyBenchmarkQuery, target_type: str, metric_code: str
    ) -> list[dict[str, Any]]:
        target_expr = _workload_target_expr(target_type)
        if target_expr is None:
            return []
        target_code_expr, target_name_expr, target_filter = target_expr
        workload_field = "run_hours" if metric_code == "kwh_per_run_hour" else "workload_amount"
        team_id = require_session_tenant_id(self._session)
        where, params = _period_conditions(query, "e", team_id=str(team_id))
        where.append("e.is_current = true")
        workload_where, workload_params = _period_conditions(query, "w", team_id=str(team_id))
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
            (
                await self._session.execute(
                    text(
                        f"""
                    with energy as (
                        select
                            {target_code_expr.replace("x.", "e.")} as target_code,
                            {target_name_expr.replace("x.", "e.")} as target_name,
                            coalesce(sum(e.amount), 0) as energy_kwh
                        from dataapp_energyintervalfact e
                        where {" and ".join(where)}
                        group by {target_code_expr.replace("x.", "e.")}, {target_name_expr.replace("x.", "e.")}
                    ),
                    workload as (
                        select
                            {target_code_expr.replace("x.", "w.")} as target_code,
                            coalesce(sum(w.{workload_field}), 0) as denominator
                        from dataapp_equipmentworkloadfact w
                        where {" and ".join(workload_where)} and w.record_status = 'confirmed'
                        group by {target_code_expr.replace("x.", "w.")}
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
            )
            .mappings()
            .all()
        )
        return [jsonable_mapping(dict(row)) for row in rows]

    async def _area_actuals(self, query: EnergyBenchmarkQuery, metric_code: str) -> list[dict[str, Any]]:
        denominators = await energy_area_denominators(self._session)
        area = denominators.get("store_area") or denominators.get("park_area")
        where, params = _fact_period_conditions(query, team_id=str(require_session_tenant_id(self._session)))
        row = (
            (
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
            )
            .mappings()
            .one()
        )
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
        team_id = require_session_tenant_id(self._session)
        where, params = _fact_period_conditions(query, team_id=str(team_id))
        energy = (
            (
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
            )
            .mappings()
            .one()
        )
        production_where, production_params = _production_period_conditions(query, team_id=str(team_id))
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
            (
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
            )
            .mappings()
            .all()
        )
        result = []
        for row in rows:
            item = jsonable_mapping(dict(row))
            denominator = (
                item["standard_qty"] if metric_code == "kgce_per_unit" else float(item["output_value"] or 0) / 10000
            )
            energy_denominator = max(1, len(rows))
            allocated_kgce = float(energy["total_kgce"] or 0) / energy_denominator if rows else 0
            result.append(
                {
                    "target_type": "product",
                    "target_code": item["target_code"],
                    "target_name": item["target_name"],
                    "metric_code": metric_code,
                    "actual_value": ratio_or_none(allocated_kgce, denominator),
                    "denominator": denominator,
                    "unit": METRICS[metric_code]["unit"],
                    "data_quality": "allocated" if denominator else "invalid_denominator",
                }
            )
        return result

    async def _workload_baseline(
        self, query: EnergyBenchmarkQuery, target_type: str, metric_code: str
    ) -> list[dict[str, Any]]:
        target_expr = _workload_target_expr(target_type)
        if target_expr is None:
            return []
        target_code_expr, target_name_expr, target_filter = target_expr
        workload_field = "run_hours" if metric_code == "kwh_per_run_hour" else "workload_amount"
        team_id = require_session_tenant_id(self._session)
        where, params = _period_conditions(query, "e", team_id=str(team_id))
        where.append("e.is_current = true")
        workload_where, workload_params = _period_conditions(query, "w", team_id=str(team_id))
        where.append(target_filter.replace("x.", "e."))
        workload_where.append(target_filter.replace("x.", "w."))
        rows = (
            (
                await self._session.execute(
                    text(
                        f"""
                    with energy as (
                        select
                            {target_code_expr.replace("x.", "e.")} as target_code,
                            {target_name_expr.replace("x.", "e.")} as target_name,
                            date_trunc('month', e.period_start) as period,
                            coalesce(sum(e.amount), 0) as energy_kwh
                        from dataapp_energyintervalfact e
                        where {" and ".join(where)}
                        group by {target_code_expr.replace("x.", "e.")}, {target_name_expr.replace("x.", "e.")}, date_trunc('month', e.period_start)
                    ),
                    workload as (
                        select
                            {target_code_expr.replace("x.", "w.")} as target_code,
                            date_trunc('month', w.period_start) as period,
                            coalesce(sum(w.{workload_field}), 0) as denominator
                        from dataapp_equipmentworkloadfact w
                        where {" and ".join(workload_where)} and w.record_status = 'confirmed'
                        group by {target_code_expr.replace("x.", "w.")}, date_trunc('month', w.period_start)
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
            )
            .mappings()
            .all()
        )
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
        return (
            "x.equipment_id::text",
            "coalesce(x.equipment_name, x.equipment_code, '未命名设备')",
            "x.equipment_id is not null",
        )
    if target_type == "use_system":
        return ("x.use_system_code", "coalesce(x.use_system_code, '未归类')", "x.use_system_code is not null")
    if target_type == "area":
        return ("x.area_id", "coalesce(x.area_name, '未分区')", "x.area_id is not null")
    return None


def _period_conditions(query: EnergyBenchmarkQuery, alias: str, *, team_id: str) -> tuple[list[str], dict[str, Any]]:
    conditions = [f"{alias}.team_id = :team_id"]
    params: dict[str, Any] = {"team_id": team_id}
    if query.period_start:
        conditions.append(f"{alias}.period_end >= (:period_start)::timestamp")
        params["period_start"] = period_param(query.period_start)
    if query.period_end:
        conditions.append(f"{alias}.period_start <= (:period_end)::timestamp")
        params["period_end"] = period_param(query.period_end)
    return conditions, params


def _fact_period_conditions(query: EnergyBenchmarkQuery, *, team_id: str) -> tuple[list[str], dict[str, Any]]:
    conditions: list[str] = ["team_id = :team_id"]
    params: dict[str, Any] = {"team_id": team_id}
    if query.period_start:
        conditions.append("period_end >= (:period_start)::timestamp")
        params["period_start"] = period_param(query.period_start)
    if query.period_end:
        conditions.append("period_start <= (:period_end)::timestamp")
        params["period_end"] = period_param(query.period_end)
    return conditions, params


def _production_period_conditions(query: EnergyBenchmarkQuery, *, team_id: str) -> tuple[list[str], dict[str, Any]]:
    conditions = ["o.team_id = :team_id", "o.record_status = 'confirmed'"]
    params: dict[str, Any] = {"team_id": team_id}
    if query.period_start:
        conditions.append("o.period_end >= (:period_start)::date")
        params["period_start"] = period_param(query.period_start)
    if query.period_end:
        conditions.append("o.period_start <= (:period_end)::date")
        params["period_end"] = period_param(query.period_end)
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
        direction = str(benchmark.get("metric_direction") or _metric_direction(str(base.get("metric_code") or "")))
        deviation_pct = round(_is_worse(float(actual_value), float(benchmark_value), direction), 2)
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
        "metric_name": (benchmark or {}).get("metric_name")
        or METRICS.get(str(base.get("metric_code")), {}).get("name"),
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
        "standard_code": (benchmark or {}).get("standard_code"),
        "applicable_condition": (benchmark or {}).get("applicable_condition"),
        "metric_direction": (benchmark or {}).get("metric_direction"),
        "advanced_value": (benchmark or {}).get("advanced_value"),
        "saving_value": (benchmark or {}).get("saving_value"),
        "access_value": (benchmark or {}).get("access_value"),
        "baseline_value": (benchmark or {}).get("baseline_value"),
        "standard_level": (benchmark or {}).get("standard_level"),
        "reference_standard": (benchmark or {}).get("reference_standard"),
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
    elif metric_code == "energy_efficiency_level":
        title = "评估重点用能设备更新"
        steps = ["核对设备类型和能效等级", "补充设备标准来源", "形成更新改造优先级"]
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
        "library_type": query.library_type,
    }


def _model_dict(obj: Any) -> dict[str, Any]:
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}


def _metric_direction(metric_code: str | None) -> str:
    if metric_code == "energy_efficiency_level":
        return "level_rank"
    return "lower_is_better"


def _equipment_efficiency_category_expr() -> str:
    haystack = (
        "lower(coalesce(dt.code, '') || ' ' || coalesce(dt.name, '') || ' ' || "
        "coalesce(e.name, '') || ' ' || coalesce(e.code, ''))"
    )
    cn_haystack = "coalesce(dt.name, '') || coalesce(e.name, '')"
    return f"""
        case
            when {haystack} like '%transformer%' or {cn_haystack} like '%变压%' then 'transformer'
            when {haystack} like '%chiller%' or {cn_haystack} like '%冷水%' then 'chiller'
            when {haystack} like '%ev_charger%' or {haystack} like '%evse%' or {cn_haystack} like '%充电%' then 'ev_charger'
            when {haystack} like '%pv_inverter%' or {cn_haystack} like '%逆变%' or {cn_haystack} like '%光伏%' then 'pv_inverter'
            when {haystack} like '%air_compressor%' or {cn_haystack} like '%空压%' then 'air_compressor'
            when {haystack} like '%boiler%' or {cn_haystack} like '%锅炉%' then 'industrial_boiler'
            when {haystack} like '%motor%' or {haystack} like '%conveyor%' or {cn_haystack} like '%电机%' or {cn_haystack} like '%输送%' then 'motor'
            when {haystack} like '%ventilator%' or {cn_haystack} like '%风机%' or {cn_haystack} like '%通风%' then 'ventilator'
            when {haystack} like '%multi_split%' or {haystack} like '%hvac%' or {cn_haystack} like '%空调%' or {cn_haystack} like '%暖通%' then 'multi_split_ac'
            else null
        end
    """


def _equipment_efficiency_category_name_expr(category_expr: str) -> str:
    return f"""
        case {category_expr}
            when 'transformer' then '电力变压器'
            when 'chiller' then '冷水机组'
            when 'ev_charger' then '充电桩'
            when 'pv_inverter' then '光伏并网逆变器'
            when 'industrial_boiler' then '工业锅炉'
            when 'air_compressor' then '空气压缩机'
            when 'motor' then '电机'
            when 'ventilator' then '通风机'
            when 'multi_split_ac' then '多联式空调机组'
            else coalesce(dt.name, e.name, e.code)
        end
    """


def _is_worse(actual_value: float, benchmark_value: float, direction: str) -> float:
    if direction == "higher_is_better":
        return (benchmark_value - actual_value) / benchmark_value * 100
    return (actual_value - benchmark_value) / benchmark_value * 100


def _month_windows(period_start: str | None, period_end: str | None) -> list[tuple[date, date]]:
    today = datetime.now(UTC).date()
    start = date.fromisoformat(period_start) if period_start else date(today.year, 1, 1)
    end = date.fromisoformat(period_end) if period_end else date(today.year, DECEMBER, 31)
    cursor = date(start.year, start.month, 1)
    windows = []
    while cursor <= end and len(windows) < MAX_TREND_MONTHS:
        last = date(cursor.year, cursor.month, monthrange(cursor.year, cursor.month)[1])
        windows.append((max(start, cursor), min(end, last)))
        cursor = date(
            cursor.year + (1 if cursor.month == DECEMBER else 0),
            1 if cursor.month == DECEMBER else cursor.month + 1,
            1,
        )
    return windows


def _data_sources_for(item: dict[str, Any], metric_code: str) -> dict[str, Any]:
    metric_sources = {
        "kwh_per_run_hour": ("能源分子来自能源时段事实表", "分母来自设备运行小时事实"),
        "kwh_per_workload": ("能源分子来自能源时段事实表", "分母来自设备作业量事实"),
        "kgce_per_unit": ("能源分子来自综合能耗折标结果", "分母来自生产/作业产量事实"),
        "kgce_per_10k_value": ("能源分子来自综合能耗折标结果", "分母来自产品产量和价格台账"),
        "tce_per_m2": ("能源分子来自综合能耗折标结果", "分母来自企业/区域面积配置"),
        "kwh_per_m2": ("能源分子来自外购电力事实", "分母来自企业/区域面积配置"),
        "energy_efficiency_level": ("实际值来自设备能效等级或检测记录", "标杆来自重点用能产品设备政策库"),
    }
    numerator, denominator = metric_sources.get(metric_code, ("能源数据", "业务分母"))
    return {
        "numerator": numerator,
        "denominator": denominator,
        "benchmark_source": item.get("source_name") or item.get("profile_name"),
        "standard_code": item.get("standard_code"),
        "reference_standard": item.get("reference_standard"),
        "data_quality": item.get("data_quality"),
    }
