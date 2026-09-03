# ruff: noqa: S608
from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.domain.energy.queries.common import period_param, ratio_or_none
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


HIGH_SHARE_THRESHOLD = 0.5
MIN_STRATEGY_COUNT = 3
PEAK_COST_SHARE_THRESHOLD = 0.25
SYSTEM_SHARE_THRESHOLD = 0.35


@dataclass(frozen=True, slots=True)
class EnergyAnalysisQuery:
    """Read-model query parameters for energy analysis."""

    period_start: str | None = None
    period_end: str | None = None
    granularity: str = "day"
    energy_type_code: str | None = None
    area_id: str | None = None
    area_keyword: str | None = None
    equipment_id: str | None = None
    use_system_code: str | None = None
    tariff_segment_type: str | None = None
    limit: int = 30


class EnergyAnalysisQueryService:
    """Query service for energy structure, anomaly and strategy read models."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def summary(self, query: EnergyAnalysisQuery) -> dict[str, Any]:
        team_id = require_session_tenant_id(self._session)
        where_sql, params = _build_energy_interval_filters(query, team_id=str(team_id))
        totals_sql = text(
            f"""
            select
                count(*)::int as record_count,
                coalesce(sum(amount), 0) as total_energy,
                coalesce(sum(cost_cny), 0) as total_cost,
                count(distinct equipment_id)::int as equipment_count,
                count(distinct area_id)::int as area_count,
                count(distinct use_system_code)::int as system_count,
                min(period_start) as min_period,
                max(period_end) as max_period
            from dataapp_energyintervalfact
            {where_sql}
            """
        )
        totals = _jsonable_mapping(dict((await self._session.execute(totals_sql, params)).mappings().one()))

        by_system_sql = text(
            f"""
            select
                coalesce(use_system_code, 'unclassified') as use_system_code,
                coalesce(use_system_name, '未归类') as use_system_name,
                count(*)::int as record_count,
                count(distinct equipment_id)::int as equipment_count,
                coalesce(sum(amount), 0) as total_energy,
                coalesce(sum(cost_cny), 0) as total_cost
            from dataapp_energyintervalfact
            {where_sql}
            group by coalesce(use_system_code, 'unclassified'), coalesce(use_system_name, '未归类')
            order by sum(amount) desc nulls last
            limit 20
            """
        )
        by_area_sql = text(
            f"""
            select
                coalesce(area_id, '') as area_id,
                coalesce(area_name, '未分区') as area_name,
                count(*)::int as record_count,
                count(distinct equipment_id)::int as equipment_count,
                coalesce(sum(amount), 0) as total_energy,
                coalesce(sum(cost_cny), 0) as total_cost
            from dataapp_energyintervalfact
            {where_sql}
            group by coalesce(area_id, ''), coalesce(area_name, '未分区')
            order by sum(amount) desc nulls last
            limit 20
            """
        )
        by_equipment_sql = text(
            f"""
            select
                equipment_id,
                coalesce(equipment_name, equipment_code, '未命名设备') as equipment_name,
                coalesce(area_name, '未分区') as area_name,
                coalesce(use_system_name, '未归类') as use_system_name,
                count(*)::int as record_count,
                coalesce(sum(amount), 0) as total_energy,
                coalesce(sum(cost_cny), 0) as total_cost
            from dataapp_energyintervalfact
            {where_sql}
            group by equipment_id, coalesce(equipment_name, equipment_code, '未命名设备'), coalesce(area_name, '未分区'), coalesce(use_system_name, '未归类')
            order by sum(amount) desc nulls last
            limit 30
            """
        )
        by_tariff_sql = text(
            f"""
            select
                coalesce(tariff_segment_type, 'none') as tariff_segment_type,
                count(*)::int as record_count,
                coalesce(sum(amount), 0) as total_energy,
                coalesce(sum(cost_cny), 0) as total_cost
            from dataapp_energyintervalfact
            {where_sql}
            group by coalesce(tariff_segment_type, 'none')
            order by sum(cost_cny) desc nulls last
            """
        )
        trend_sql = text(
            f"""
            with bucketed as (
                select
                    date_trunc(:bucket, period_start) as bucket_start,
                    coalesce(sum(amount), 0) as total_energy,
                    coalesce(sum(cost_cny), 0) as total_cost,
                    count(distinct equipment_id)::int as equipment_count
                from dataapp_energyintervalfact
                {where_sql}
                group by date_trunc(:bucket, period_start)
            )
            select
                to_char(
                    bucket_start,
                    case
                        when :analysis_granularity = 'hour' then 'YYYY-MM-DD HH24:00'
                        when :analysis_granularity = 'month' then 'YYYY-MM'
                        else 'YYYY-MM-DD'
                    end
                ) as period,
                total_energy,
                total_cost,
                equipment_count
            from bucketed
            order by bucket_start asc
            limit 500
            """
        )
        workload_sql = text(
            """
            select
                count(*)::int as record_count,
                coalesce(sum(workload_amount), 0) as workload_amount,
                coalesce(sum(run_hours), 0) as run_hours,
                count(distinct equipment_id)::int as equipment_count
            from dataapp_equipmentworkloadfact
            where team_id = :team_id
              and ((:period_start)::timestamp is null or period_end >= (:period_start)::timestamp)
              and ((:period_end)::timestamp is null or period_start <= (:period_end)::timestamp)
              and ((:area_id)::text is null or area_id = (:area_id)::text)
              and ((:equipment_id)::bigint is null or equipment_id = (:equipment_id)::bigint)
              and ((:use_system_code)::text is null or use_system_code = (:use_system_code)::text)
              and record_status = 'confirmed'
            """
        )

        by_system = [
            _jsonable_mapping(dict(row))
            for row in (await self._session.execute(by_system_sql, params)).mappings().all()
        ]
        by_area = [
            _jsonable_mapping(dict(row)) for row in (await self._session.execute(by_area_sql, params)).mappings().all()
        ]
        by_equipment = [
            _jsonable_mapping(dict(row))
            for row in (await self._session.execute(by_equipment_sql, params)).mappings().all()
        ]
        by_tariff = [
            _jsonable_mapping(dict(row))
            for row in (await self._session.execute(by_tariff_sql, params)).mappings().all()
        ]
        trend = [
            _jsonable_mapping(dict(row))
            for row in (
                await self._session.execute(
                    trend_sql,
                    {
                        **params,
                        "bucket": _analysis_bucket(query.granularity),
                        "analysis_granularity": _analysis_granularity(query.granularity),
                    },
                )
            )
            .mappings()
            .all()
        ]
        workload = _jsonable_mapping(
            dict(
                (
                    await self._session.execute(
                        workload_sql,
                        {
                            "team_id": str(team_id),
                            "period_start": period_param(query.period_start),
                            "period_end": period_param(query.period_end),
                            "area_id": query.area_id if query.area_id and query.area_id != "all" else None,
                            "equipment_id": query.equipment_id
                            if query.equipment_id and query.equipment_id != "all"
                            else None,
                            "use_system_code": query.use_system_code
                            if query.use_system_code and query.use_system_code != "all"
                            else None,
                        },
                    )
                )
                .mappings()
                .one()
            )
        )
        total_energy = float(totals.get("total_energy") or 0)
        workload_amount = float(workload.get("workload_amount") or 0)
        return {
            "totals": totals,
            "workload": workload,
            "performance": {
                "kwh_per_run_hour": _ratio_or_none(total_energy, workload_amount),
                "cost_per_kwh": _ratio_or_none(totals.get("total_cost"), total_energy),
            },
            "by_system": by_system,
            "by_area": by_area,
            "by_equipment": by_equipment,
            "by_tariff": by_tariff,
            "trend": trend,
            "filters": {
                "period_start": query.period_start,
                "period_end": query.period_end,
                "granularity": _analysis_granularity(query.granularity),
                "energy_type_code": query.energy_type_code,
                "area_id": query.area_id,
                "area_keyword": query.area_keyword,
                "equipment_id": query.equipment_id,
                "use_system_code": query.use_system_code,
                "tariff_segment_type": query.tariff_segment_type,
            },
        }

    async def anomalies(self, query: EnergyAnalysisQuery) -> dict[str, Any]:
        team_id = require_session_tenant_id(self._session)
        where_sql, params = _build_energy_interval_filters(
            EnergyAnalysisQuery(
                period_start=query.period_start,
                period_end=query.period_end,
                granularity=query.granularity,
                energy_type_code=query.energy_type_code,
                area_id=query.area_id,
                use_system_code=query.use_system_code,
                area_keyword=query.area_keyword,
                equipment_id=query.equipment_id,
                tariff_segment_type=query.tariff_segment_type,
            ),
            team_id=str(team_id),
        )
        limit_clamped = max(1, min(query.limit, 100))
        anomaly_sql = text(
            f"""
            with base as (
                select
                    equipment_id,
                    coalesce(equipment_name, equipment_code, '未命名设备') as equipment_name,
                    coalesce(area_name, '未分区') as area_name,
                    coalesce(use_system_name, '未归类') as use_system_name,
                    period_start,
                    amount,
                    cost_cny,
                    avg(amount) over (partition by equipment_id) as avg_amount,
                    stddev_pop(amount) over (partition by equipment_id) as std_amount
                from dataapp_energyintervalfact
                {where_sql}
            )
            select
                equipment_id,
                equipment_name,
                area_name,
                use_system_name,
                period_start,
                amount,
                cost_cny,
                avg_amount,
                std_amount,
                case
                    when std_amount > 0 then (amount - avg_amount) / std_amount
                    else null
                end as deviation_score,
                case
                    when std_amount > 0 and amount > avg_amount + 2 * std_amount then 'statistical_spike'
                    when avg_amount > 0 and amount > avg_amount * 1.5 then 'high_vs_baseline'
                    else 'normal'
                end as anomaly_type
            from base
            where (std_amount > 0 and amount > avg_amount + 2 * std_amount)
               or (avg_amount > 0 and amount > avg_amount * 1.5)
            order by period_start desc, amount desc
            limit :limit
            """
        )
        rows = (
            (
                await self._session.execute(
                    anomaly_sql,
                    {
                        **params,
                        "limit": limit_clamped,
                    },
                )
            )
            .mappings()
            .all()
        )
        energy_alarm_sql = text(
            """
            select
                id,
                alarm_name,
                alarm_level,
                alarm_category,
                event_desc,
                event_time,
                current_value,
                threshold_value,
                status
            from dataapp_alarmevent
            where team_id = :team_id
              and (event_type = 2 or alarm_category in ('energy', 'carbon'))
              and ((:period_start)::timestamp is null or event_time >= (:period_start)::timestamp)
              and ((:period_end)::timestamp is null or event_time <= (:period_end)::timestamp)
            order by event_time desc nulls last
            limit :limit
            """
        )
        alarms = (
            (
                await self._session.execute(
                    energy_alarm_sql,
                    {
                        "team_id": str(team_id),
                        "period_start": period_param(query.period_start),
                        "period_end": period_param(query.period_end),
                        "limit": limit_clamped,
                    },
                )
            )
            .mappings()
            .all()
        )
        return {
            "items": [_jsonable_mapping(dict(row)) for row in rows],
            "alarms": [_jsonable_mapping(dict(row)) for row in alarms],
            "filters": {
                "period_start": query.period_start,
                "period_end": query.period_end,
                "granularity": _analysis_granularity(query.granularity),
                "energy_type_code": query.energy_type_code,
                "area_id": query.area_id,
                "use_system_code": query.use_system_code,
                "area_keyword": query.area_keyword,
                "equipment_id": query.equipment_id,
                "tariff_segment_type": query.tariff_segment_type,
            },
        }

    async def strategies(self, query: EnergyAnalysisQuery) -> dict[str, Any]:
        summary = await self.summary(query)
        anomalies = await self.anomalies(
            EnergyAnalysisQuery(
                period_start=query.period_start,
                period_end=query.period_end,
                granularity=query.granularity,
                energy_type_code=query.energy_type_code,
                area_id=query.area_id,
                area_keyword=query.area_keyword,
                equipment_id=query.equipment_id,
                use_system_code=query.use_system_code,
                tariff_segment_type=query.tariff_segment_type,
                limit=20,
            )
        )
        totals = summary["totals"]
        total_energy = float(totals.get("total_energy") or 0)
        total_cost = float(totals.get("total_cost") or 0)
        by_system = summary["by_system"]
        by_tariff = summary["by_tariff"]
        strategies: list[dict[str, Any]] = []
        if by_system and total_energy > 0:
            top_system = by_system[0]
            share = float(top_system.get("total_energy") or 0) / total_energy
            if share >= SYSTEM_SHARE_THRESHOLD:
                strategies.append(
                    _analysis_strategy_item(
                        code="focus_top_energy_system",
                        title=f"优先治理{top_system.get('use_system_name')}",
                        priority="high" if share >= HIGH_SHARE_THRESHOLD else "medium",
                        strategy_type="system_focus",
                        target=top_system.get("use_system_name") or "-",
                        evidence={
                            "energy_share": round(share, 4),
                            "total_energy": top_system.get("total_energy"),
                            "equipment_count": top_system.get("equipment_count"),
                        },
                        steps=[
                            "锁定该系统下排名前 3 的设备和区域。",
                            "核对设备运行小时、班次和作业量是否同步增长。",
                            "对异常高耗设备建立整改任务并在下一周期复核单位作业量能耗。",
                        ],
                        expected_effect="降低高占比系统的无效运行和异常用能。",
                    )
                )
        if by_tariff and total_cost > 0:
            peak = next((item for item in by_tariff if item.get("tariff_segment_type") == "peak"), None)
            peak_share = float(peak.get("total_cost") or 0) / total_cost if peak else 0
            if peak_share >= PEAK_COST_SHARE_THRESHOLD:
                strategies.append(
                    _analysis_strategy_item(
                        code="shift_peak_load",
                        title="削减峰段用电成本",
                        priority="medium",
                        strategy_type="cost_optimization",
                        target="峰段用电",
                        evidence={
                            "peak_cost_share": round(peak_share, 4),
                            "peak_cost": peak.get("total_cost") if peak else 0,
                        },
                        steps=[
                            "识别峰段运行的非连续生产设备和可平移作业。",
                            "优先将充电、备货、非紧急搬运调整到平段或谷段。",
                            "调整后对比峰段电量占比和总电费变化。",
                        ],
                        expected_effect="减少尖峰时段电费支出。",
                    )
                )
        if anomalies["items"]:
            top_anomaly = anomalies["items"][0]
            strategies.append(
                _analysis_strategy_item(
                    code="investigate_anomaly_periods",
                    title="核查异常高耗时段",
                    priority="high",
                    strategy_type="anomaly_diagnosis",
                    target=top_anomaly.get("equipment_name") or "-",
                    evidence={
                        "anomaly_count": len(anomalies["items"]),
                        "latest_period": top_anomaly.get("period_start"),
                        "latest_amount": top_anomaly.get("amount"),
                    },
                    steps=[
                        "打开异常设备的小时/日负荷曲线确认突增时间。",
                        "核对对应时段告警、检修、补录和生产/作业量记录。",
                        "确认原因后记录为设备异常、业务增长或数据质量问题。",
                    ],
                    expected_effect="减少异常用能和误判统计。",
                )
            )
        if summary["workload"].get("record_count"):
            kwh_per_run_hour = summary["performance"].get("kwh_per_run_hour")
            strategies.append(
                _analysis_strategy_item(
                    code="normalize_by_workload",
                    title="用运行小时校正设备能效",
                    priority="medium",
                    strategy_type="performance_tracking",
                    target="设备作业量",
                    evidence={
                        "run_hours": summary["workload"].get("run_hours"),
                        "kwh_per_run_hour": kwh_per_run_hour,
                    },
                    steps=[
                        "将运行小时作为设备级 EnPI 分母纳入月度复盘。",
                        "对比同类设备的 kWh/h, 筛出明显偏高设备。",
                        "补充搬运次数、充电次数、托盘数等更贴近业务的作业量字段。",
                    ],
                    expected_effect="把能耗变化拆分为业务量变化和设备效率变化。",
                )
            )
        if len(strategies) < MIN_STRATEGY_COUNT:
            strategies.append(
                _analysis_strategy_item(
                    code="improve_energy_data_coverage",
                    title="补齐能源分析数据覆盖",
                    priority="medium",
                    strategy_type="data_governance",
                    target="能源计量和作业量",
                    evidence={
                        "equipment_count": totals.get("equipment_count"),
                        "system_count": totals.get("system_count"),
                        "workload_records": summary["workload"].get("record_count"),
                    },
                    steps=[
                        "检查未归类设备并维护用能系统。",
                        "维护真实尖峰平谷电价和账单金额。",
                        "为关键仓储设备补运行时间、作业次数或处理量。",
                    ],
                    expected_effect="提升异常诊断和策略推荐的可信度。",
                )
            )
        return {
            "items": strategies[:8],
            "evidence_summary": {
                "total_energy": total_energy,
                "total_cost": total_cost,
                "anomaly_count": len(anomalies["items"]),
                "alarm_count": len(anomalies["alarms"]),
            },
        }


def _analysis_granularity(value: str | None) -> str:
    return value if value in {"hour", "day", "month"} else "day"


def _analysis_source_granularity(value: str | None) -> str:
    return _analysis_granularity(value)


def _analysis_bucket(value: str | None) -> str:
    return "month" if _analysis_granularity(value) == "month" else _analysis_granularity(value)


def _build_energy_interval_filters(query: EnergyAnalysisQuery, *, team_id: str) -> tuple[str, dict[str, Any]]:
    conditions: list[str] = ["team_id = :team_id", "is_current = true"]
    params: dict[str, Any] = {"team_id": team_id}
    conditions.append("granularity = :source_granularity")
    params["source_granularity"] = _analysis_source_granularity(query.granularity)
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
    if query.tariff_segment_type and query.tariff_segment_type != "all":
        conditions.append("tariff_segment_type = :tariff_segment_type")
        params["tariff_segment_type"] = query.tariff_segment_type
    if query.area_keyword:
        conditions.append(
            "(area_name ilike :area_keyword or area_id ilike :area_keyword or equipment_name ilike :area_keyword)"
        )
        params["area_keyword"] = f"%{query.area_keyword.strip()}%"
    where_sql = f"where {' and '.join(conditions)}" if conditions else ""
    return where_sql, params


def _analysis_strategy_item(
    *,
    code: str,
    title: str,
    priority: str,
    strategy_type: str,
    target: str,
    evidence: dict[str, Any],
    steps: list[str],
    expected_effect: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "priority": priority,
        "strategy_type": strategy_type,
        "target": target,
        "evidence": evidence,
        "steps": steps,
        "expected_effect": expected_effect,
    }


def _jsonable_mapping(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (datetime.date, datetime.datetime)):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


def _ratio_or_none(numerator: Any, denominator: float | None, digits: int = 6) -> float | None:
    return ratio_or_none(numerator, denominator, digits)
