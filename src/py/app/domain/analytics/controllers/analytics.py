# ruff: noqa: B007, B008, DTZ003, DTZ011, PERF401, PLR0915, PLR2004, RUF001, SLF001
from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from dateutil.relativedelta import relativedelta
from litestar import Controller, Request, delete, get, post
from litestar.params import Body
from litestar.response import Response
from sqlalchemy import case, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.db import models as m
from app.domain.accounts.guards import requires_superuser
from app.domain.admin.deps import provide_audit_log_service
from app.domain.admin.services import AuditLogService  # noqa: TC001
from app.domain.carbon import services  # noqa: TC001
from app.domain.carbon.controllers import (
    AUDIT_ACTION_APPROVE,
    AUDIT_ACTION_REJECT,
    AUDIT_ACTION_SUBMIT,
    DEMO_SEED_MARKER,
    SOURCE_KIND_DEMO_SEED,
    SOURCE_KIND_DERIVED,
    SOURCE_KIND_ESTIMATE,
    SOURCE_KIND_FALLBACK,
    SOURCE_KIND_MANUAL_BILL,
    SOURCE_KIND_REAL,
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_PENDING,
    STATUS_REJECTED,
    _compute_year_from_date,
    _data_origin_for_source_kind,
    _format_decimal,
    _handle_db_view_error,
    _historical_fit_kwh,
    _log_security_audit,
    _month_span,
    _month_start_date,
    _month_string,
    _month_window,
    _months_back,
    _paged_payload,
    _record_attachment,
    _record_source_kind,
    _scope_display_name,
    _scope_group_label,
    _scope_record_label,
    _scope_record_period,
    _scope_trend_key,
    _seed_months,
    _serialize_scope_record,
    _sort_month_key,
    _source_kind_label,
    model_to_dict,
)
from app.domain.carbon.deps import (
    provide_scope2_meter_aggregate_service,
)
from app.domain.carbon.emission_calculator import compute_emission_result
from app.domain.carbon.validation import CarbonValidationError
from app.domain.carbon_accounting.controllers.accounting import CarbonAccountingController

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CarbonAnalyticsController(Controller):
    """统一能碳分析与追溯接口。"""

    tags = ["CarbonAnalytics"]
    signature_types = [Response]
    exception_handlers = {SQLAlchemyError: _handle_db_view_error}  # type: ignore[dict-item]

    @staticmethod
    async def _latest_energy_month(db_session: AsyncSession) -> str | None:
        meter_month = await db_session.scalar(select(func.max(m.Scope2MeterAggregate.billing_month)))
        if meter_month:
            return str(meter_month)
        bill_month = await db_session.scalar(select(func.max(m.Scope2ElectricityBill.billing_month)))
        if bill_month:
            return str(bill_month)
        raw_last = await db_session.scalar(select(func.max(m.AmmeterIndexValue.reading_time)).where(m.AmmeterIndexValue.reading_time.is_not(None)))
        return _month_string(raw_last)

    @staticmethod
    async def _recent_scope2_backfill_months(db_session: AsyncSession, months: int = 12) -> list[str]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session)
        if not latest_month:
            return []
        month_keys = _months_back(latest_month, max(1, min(months, 24)))
        raw_start = _month_window(month_keys[0])[0]
        raw_end = _month_window(month_keys[-1])[1]
        rows = await CarbonAnalyticsController._raw_meter_rollups(db_session, month_start=raw_start, month_end=raw_end)
        valid_months = {str(row["billing_month"]) for row in rows if float(row.get("total_kwh") or 0.0) > 0}
        return [month for month in month_keys if month in valid_months]

    @staticmethod
    async def _raw_history_month_range(db_session: AsyncSession) -> tuple[str | None, str | None]:
        first_time = await db_session.scalar(select(func.min(m.AmmeterIndexValue.reading_time)).where(m.AmmeterIndexValue.reading_time.is_not(None)))
        last_time = await db_session.scalar(select(func.max(m.AmmeterIndexValue.reading_time)).where(m.AmmeterIndexValue.reading_time.is_not(None)))
        return (_month_string(first_time), _month_string(last_time))

    @staticmethod
    async def _scope2_factor_for_month(db_session: AsyncSession, billing_month: str) -> dict[str, Any] | None:
        try:
            result = await compute_emission_result(
                db_session,
                "scope2",
                "electricity",
                "grid_electricity",
                1,
                "kWh",
                _compute_year_from_date(billing_month),
            )
        except CarbonValidationError:
            return None
        if result is None:
            return None
        return {
            "factor_source": result.factor_source,
            "factor_year": result.factor_year,
            "factor_unit": result.factor_unit,
            "factor_value": _format_decimal(result.co2e),
        }

    @staticmethod
    async def _historical_scope2_estimates_for_month(
        db_session: AsyncSession,
        billing_month: str,
        current_rows: list[m.Scope2MeterAggregate] | None = None,
    ) -> list[dict[str, Any]]:
        if current_rows is None:
            current_rows = (
                await db_session.execute(select(m.Scope2MeterAggregate).where(m.Scope2MeterAggregate.billing_month == billing_month))
            ).scalars().all()

        candidates = [
            row
            for row in current_rows
            if row.ammeter_id and (row.calc_status != "ready" or float(row.total_kwh or 0.0) <= 0.0)
        ]
        if not candidates:
            return []

        candidate_ids = sorted({str(row.ammeter_id) for row in candidates if row.ammeter_id})
        history_rows = (
            await db_session.execute(
                select(m.Scope2MeterAggregate)
                .where(
                    m.Scope2MeterAggregate.ammeter_id.in_(candidate_ids),
                    m.Scope2MeterAggregate.billing_month < billing_month,
                    m.Scope2MeterAggregate.calc_status == "ready",
                    m.Scope2MeterAggregate.total_kwh.is_not(None),
                    m.Scope2MeterAggregate.total_kwh > 0,
                )
                .order_by(m.Scope2MeterAggregate.ammeter_id.asc(), m.Scope2MeterAggregate.billing_month.asc())
            )
        ).scalars().all()

        history_by_meter: dict[str, list[m.Scope2MeterAggregate]] = defaultdict(list)
        for row in history_rows:
            if row.ammeter_id:
                history_by_meter[str(row.ammeter_id)].append(row)

        factor = await CarbonAnalyticsController._scope2_factor_for_month(db_session, billing_month)
        factor_value = float(factor["factor_value"]) if factor and factor.get("factor_value") is not None else None
        target_month_token = billing_month[-2:]

        estimates: list[dict[str, Any]] = []
        for candidate in candidates:
            meter_key = str(candidate.ammeter_id)
            history = history_by_meter.get(meter_key, [])
            baseline_values = [float(row.total_kwh or 0.0) for row in history if float(row.total_kwh or 0.0) > 0.0]
            if len(baseline_values) < 2:
                continue

            seasonal_values = [
                float(row.total_kwh or 0.0)
                for row in history
                if row.billing_month and str(row.billing_month).endswith(target_month_token) and float(row.total_kwh or 0.0) > 0.0
            ]
            recent_values = baseline_values[-6:]
            estimate_kwh = _historical_fit_kwh(seasonal_values, recent_values, baseline_values)
            if estimate_kwh is None or estimate_kwh <= 0:
                continue

            if len(seasonal_values) >= 2 or len(recent_values) >= 4:
                confidence = "high"
            elif len(baseline_values) >= 3:
                confidence = "medium"
            else:
                confidence = "low"

            estimate_co2e = round(estimate_kwh * factor_value, 6) if factor_value is not None else None
            estimates.append(
                {
                    "record_type": "Scope2HistoricalEstimate",
                    "record_id": None,
                    "display_name": candidate.ammeter_name or candidate.ammeter_id,
                    "ammeter_id": candidate.ammeter_id,
                    "ammeter_name": candidate.ammeter_name,
                    "area_id": candidate.area_id,
                    "area_name": candidate.area_name,
                    "period": billing_month,
                    "billing_month": billing_month,
                    "source_kind": SOURCE_KIND_ESTIMATE,
                    "data_origin": _data_origin_for_source_kind(SOURCE_KIND_ESTIMATE),
                    "total_kwh": estimate_kwh,
                    "computed_co2e": estimate_co2e,
                    "calc_status": "estimated",
                    "status": STATUS_DRAFT,
                    "factor_source": factor["factor_source"] if factor else None,
                    "factor_year": factor["factor_year"] if factor else None,
                    "confidence": confidence,
                    "history_months": len(baseline_values),
                    "computation_note": f"基于{len(baseline_values)}个历史有效月进行季节/近期中位数拟合。",
                }
            )
        return estimates

    @staticmethod
    async def _raw_meter_rollups(
        db_session: AsyncSession,
        *,
        month_start: datetime.datetime,
        month_end: datetime.datetime,
    ) -> list[dict[str, Any]]:
        sql = text(
            """
            select
                to_char(date_trunc('month', reading_time), 'YYYY-MM') as billing_month,
                ammeter_id,
                max(ammeter_name) as ammeter_name,
                coalesce(max(area_id), '') as area_id,
                coalesce(max(area_name), '未分区') as area_name,
                min(reading_time) as first_reading_time,
                max(reading_time) as last_reading_time,
                min(zygdn) as start_total_energy,
                max(zygdn) as end_total_energy,
                greatest(max(zygdn) - min(zygdn), 0) as total_kwh,
                count(*) as sample_count
            from dataapp_ammeterindexvalue
            where
                reading_time >= :month_start
                and reading_time < :month_end
                and reading_time is not null
                and ammeter_id is not null
                and zygdn is not null
            group by 1, ammeter_id
            order by total_kwh desc nulls last, ammeter_id asc
            """
        )
        rows = (await db_session.execute(sql, {"month_start": month_start, "month_end": month_end})).mappings().all()
        return [dict(row) for row in rows]

    @staticmethod
    async def _load_scope_records(db_session: AsyncSession) -> list[dict[str, Any]]:
        model_specs: list[tuple[str, Any, str | None]] = [
            ("Scope1MobileCombustion", m.Scope1MobileCombustion, SOURCE_KIND_REAL),
            ("Scope1StationaryCombustion", m.Scope1StationaryCombustion, SOURCE_KIND_REAL),
            ("Scope1RefrigerantLeak", m.Scope1RefrigerantLeak, SOURCE_KIND_REAL),
            ("Scope2ElectricityBill", m.Scope2ElectricityBill, SOURCE_KIND_MANUAL_BILL),
            ("Scope2MeterAggregate", m.Scope2MeterAggregate, SOURCE_KIND_DERIVED),
            ("Scope2PurchasedEnergy", m.Scope2PurchasedEnergy, "purchased_energy"),
            ("Scope3WasteDisposal", m.Scope3WasteDisposal, SOURCE_KIND_REAL),
            ("Scope3ThirdPartyTransport", m.Scope3ThirdPartyTransport, SOURCE_KIND_REAL),
        ]
        records: list[dict[str, Any]] = []
        for record_type, model, source_kind in model_specs:
            rows = (await db_session.execute(select(model).where(model.status != STATUS_REJECTED))).scalars().all()
            for row in rows:
                serialized = await _serialize_scope_record(row, db_session, source_kind=_record_source_kind(row, source_kind))
                records.append(
                    {
                        "record_type": record_type,
                        "scope": _scope_group_label(record_type),
                        "record_label": _scope_record_label(record_type),
                        "display_name": _scope_display_name(row),
                        "period": _scope_record_period(row),
                        "row": row,
                        "data": serialized,
                    }
                )
        return records

    @staticmethod
    async def _build_energy_series(db_session: AsyncSession, months: list[str]) -> list[dict[str, Any]]:
        if not months:
            return []
        ready_meter_stmt = (
            select(
                m.Scope2MeterAggregate.billing_month,
                func.sum(m.Scope2MeterAggregate.total_kwh),
                func.sum(m.Scope2MeterAggregate.computed_co2e),
                func.count(m.Scope2MeterAggregate.id),
            )
            .where(
                m.Scope2MeterAggregate.billing_month.in_(months),
                m.Scope2MeterAggregate.calc_status == "ready",
            )
            .group_by(m.Scope2MeterAggregate.billing_month)
        )
        ready_bill_stmt = (
            select(
                m.Scope2ElectricityBill.billing_month,
                func.sum(m.Scope2ElectricityBill.total_kwh),
                func.sum(m.Scope2ElectricityBill.computed_co2e),
                func.count(m.Scope2ElectricityBill.id),
            )
            .where(
                m.Scope2ElectricityBill.billing_month.in_(months),
                m.Scope2ElectricityBill.calc_status == "ready",
            )
            .group_by(m.Scope2ElectricityBill.billing_month)
        )
        meter_rows = {
            str(month): {
                "energy_kwh": _format_decimal(energy) or 0.0,
                "carbon_co2e": _format_decimal(carbon) or 0.0,
                "record_count": int(count or 0),
            }
            for month, energy, carbon, count in (await db_session.execute(ready_meter_stmt)).all()
        }
        bill_rows = {
            str(month): {
                "energy_kwh": _format_decimal(energy) or 0.0,
                "carbon_co2e": _format_decimal(carbon) or 0.0,
                "record_count": int(count or 0),
            }
            for month, energy, carbon, count in (await db_session.execute(ready_bill_stmt)).all()
        }

        raw_start = _month_window(months[0])[0]
        raw_end = _month_window(months[-1])[1]
        raw_rows = await CarbonAnalyticsController._raw_meter_rollups(
            db_session,
            month_start=raw_start,
            month_end=raw_end,
        )
        raw_by_month: dict[str, dict[str, Any]] = defaultdict(lambda: {"energy_kwh": 0.0, "record_count": 0})
        for row in raw_rows:
            month = str(row["billing_month"])
            raw_by_month[month]["energy_kwh"] += float(row["total_kwh"] or 0.0)
            raw_by_month[month]["record_count"] += 1

        series: list[dict[str, Any]] = []
        for month in months:
            if month in meter_rows:
                series.append({"period": month, "source_kind": "meter_aggregate", **meter_rows[month]})
                continue
            if month in bill_rows:
                series.append({"period": month, "source_kind": "manual_bill", **bill_rows[month]})
                continue
            raw_data = raw_by_month.get(month)
            carbon_co2e = None
            if raw_data and raw_data["energy_kwh"] > 0:
                factor = await CarbonAnalyticsController._scope2_factor_for_month(db_session, month)
                carbon_co2e = round(raw_data["energy_kwh"] * (factor["factor_value"] or 0.0), 6) if factor else None
            series.append(
                {
                    "period": month,
                    "source_kind": "raw_meter_fallback" if raw_data and raw_data["energy_kwh"] > 0 else "empty",
                    "energy_kwh": raw_data["energy_kwh"] if raw_data else 0.0,
                    "carbon_co2e": carbon_co2e,
                    "record_count": raw_data["record_count"] if raw_data else 0,
                }
            )
        return series

    @get("/api/carbon/analytics/overview")
    async def get_analytics_overview(self, db_session: AsyncSession) -> Response[dict]:
        latest_month = await self._latest_energy_month(db_session)
        energy_series = await self._build_energy_series(db_session, _months_back(latest_month, 1) if latest_month else [])
        current_energy = energy_series[-1] if energy_series else {"energy_kwh": 0.0, "carbon_co2e": 0.0, "source_kind": "empty"}
        previous_month = _month_string((datetime.date.fromisoformat(f"{latest_month}-01") - relativedelta(months=1)) if latest_month else None)
        previous_energy_series = await self._build_energy_series(db_session, [previous_month] if previous_month else [])
        previous_energy = previous_energy_series[0] if previous_energy_series else {"energy_kwh": 0.0, "carbon_co2e": 0.0}

        enterprise = await db_session.scalar(select(m.EnterpriseInfo).limit(1))
        equipment_rows = (
            await db_session.execute(
                select(
                    m.MonitorEquipment.category,
                    func.count(m.MonitorEquipment.id),
                    func.sum(case((m.MonitorEquipment.status == 0, 1), else_=0)),
                )
                .group_by(m.MonitorEquipment.category)
            )
        ).all()
        category_names = {0: "用电终端", 1: "发电终端", 2: "视频终端"}
        monitor_stats = [
            {
                "category": category_names.get(category, f"分类{category}"),
                "total": int(total or 0),
                "online": int(online or 0),
                "fault": max(int(total or 0) - int(online or 0), 0),
            }
            for category, total, online in equipment_rows
        ]

        scope_records = await self._load_scope_records(db_session)
        pending_count = sum(1 for item in scope_records if item["data"].get("status") == STATUS_PENDING)
        approved_count = sum(1 for item in scope_records if item["data"].get("status") == STATUS_APPROVED)
        carbon_total = sum(float(item["data"].get("computed_co2e") or 0.0) for item in scope_records)
        scope_totals: dict[str, float] = defaultdict(float)
        for item in scope_records:
            scope_totals[item["scope"]] += float(item["data"].get("computed_co2e") or 0.0)

        alarm_total = await db_session.scalar(select(func.count(m.AlarmEvent.id))) or 0
        alarm_unhandled = await db_session.scalar(select(func.count(m.AlarmEvent.id)).where(m.AlarmEvent.is_handle.is_(False))) or 0
        video_alarm_total = await db_session.scalar(select(func.count(m.VedioAlarmEvent.id))) or 0
        video_alarm_unhandled = await db_session.scalar(select(func.count(m.VedioAlarmEvent.id)).where(m.VedioAlarmEvent.is_handle.is_(False))) or 0

        current_energy_value = float(current_energy.get("energy_kwh") or 0.0)
        previous_energy_value = float(previous_energy.get("energy_kwh") or 0.0)
        current_carbon_value = carbon_total
        previous_carbon_value = None
        energy_delta_ratio = ((current_energy_value - previous_energy_value) / previous_energy_value * 100) if previous_energy_value else None
        carbon_delta_ratio = None if previous_carbon_value in (None, 0) else ((current_carbon_value - previous_carbon_value) / previous_carbon_value * 100)

        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": latest_month,
                    "enterprise": enterprise.to_dict() if enterprise else {},
                    "kpis": [
                        {"id": "energy", "label": "当期用电量", "value": round(current_energy_value, 2), "unit": "kWh", "ratio": round(energy_delta_ratio, 2) if energy_delta_ratio is not None else None},
                        {"id": "carbon", "label": "已纳入碳排", "value": round(current_carbon_value, 2), "unit": "kgCO2e", "ratio": round(carbon_delta_ratio, 2) if carbon_delta_ratio is not None else None},
                        {"id": "pending", "label": "待审核记录", "value": pending_count, "unit": "条"},
                        {"id": "alerts", "label": "未处理预警", "value": int(alarm_unhandled) + int(video_alarm_unhandled), "unit": "条"},
                    ],
                    "monitor_stats": monitor_stats,
                    "workflow": {
                        "pending_count": pending_count,
                        "approved_count": approved_count,
                        "total_records": len(scope_records),
                    },
                    "alerts": {
                        "alarm_total": int(alarm_total),
                        "alarm_unhandled": int(alarm_unhandled),
                        "video_alarm_total": int(video_alarm_total),
                        "video_alarm_unhandled": int(video_alarm_unhandled),
                    },
                    "scope_totals": [{"name": scope, "value": round(value, 2)} for scope, value in scope_totals.items()],
                    "source_mix": {
                        "source_kind": current_energy.get("source_kind"),
                        "energy_kwh": round(current_energy_value, 2),
                        "carbon_co2e": round(float(current_energy.get("carbon_co2e") or 0.0), 2),
                    },
                },
            }
        )

    @get("/api/carbon/analytics/trend")
    async def get_analytics_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict]:
        latest_month = await self._latest_energy_month(db_session)
        if not latest_month:
            return Response(content={"code": 200, "msg": "暂无数据", "data": {"series": [], "months": []}})
        month_keys = _months_back(latest_month, max(3, min(months, 24)))
        energy_series = await self._build_energy_series(db_session, month_keys)
        carbon_records = await self._load_scope_records(db_session)
        scope_month_totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for item in carbon_records:
            month = item["period"]
            if not month:
                continue
            scope_month_totals[month][item["scope"]] += float(item["data"].get("computed_co2e") or 0.0)

        series = []
        for item in energy_series:
            month = item["period"]
            scope1 = scope_month_totals[month].get("范围1", 0.0)
            scope2 = float(item.get("carbon_co2e") or 0.0)
            scope3 = scope_month_totals[month].get("范围3", 0.0)
            series.append(
                {
                    "period": month,
                    "energy_kwh": round(float(item.get("energy_kwh") or 0.0), 2),
                    "scope1_co2e": round(scope1, 2),
                    "scope2_co2e": round(scope2, 2),
                    "scope3_co2e": round(scope3, 2),
                    "carbon_co2e": round(scope1 + scope2 + scope3, 2),
                    "source_kind": item.get("source_kind"),
                }
            )
        return Response(content={"code": 200, "msg": "获取成功", "data": {"months": month_keys, "series": series}})

    @get("/api/carbon/analytics/ranking")
    async def get_analytics_ranking(self, db_session: AsyncSession) -> Response[dict]:
        latest_month = await self._latest_energy_month(db_session)
        energy_rows: list[dict[str, Any]] = []
        diagnostics = {"source_kind": "empty"}
        if latest_month:
            ready_rows = (
                await db_session.execute(
                    select(m.Scope2MeterAggregate)
                    .where(
                        m.Scope2MeterAggregate.billing_month == latest_month,
                        m.Scope2MeterAggregate.calc_status == "ready",
                    )
                    .order_by(m.Scope2MeterAggregate.total_kwh.desc().nullslast())
                )
            ).scalars().all()
            if ready_rows:
                energy_rows = [await _serialize_scope_record(row, db_session, source_kind="meter_aggregate") for row in ready_rows]
                diagnostics["source_kind"] = "meter_aggregate"
            else:
                month_start, month_end = _month_window(latest_month)
                energy_rows = await self._raw_meter_rollups(db_session, month_start=month_start, month_end=month_end)
                diagnostics["source_kind"] = "raw_meter_fallback"

        energy_by_area: dict[str, float] = defaultdict(float)
        for row in energy_rows:
            area_name = str(row.get("area_name") or "未分区")
            energy_by_area[area_name] += float(row.get("total_kwh") or 0.0)

        carbon_records = await self._load_scope_records(db_session)
        carbon_by_type: dict[str, float] = defaultdict(float)
        for item in carbon_records:
            carbon_by_type[item["record_label"]] += float(item["data"].get("computed_co2e") or 0.0)

        area_events = (
            await db_session.execute(
                select(m.MonitorSector.name, func.count(m.AlarmEvent.id))
                .join(m.AlarmEvent, m.AlarmEvent.sector_id == m.MonitorSector.id)
                .group_by(m.MonitorSector.name)
                .order_by(func.count(m.AlarmEvent.id).desc())
                .limit(10)
            )
        ).all()

        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": latest_month,
                    "diagnostics": diagnostics,
                    "energy_by_area": [{"name": name, "value": round(value, 2)} for name, value in sorted(energy_by_area.items(), key=lambda item: item[1], reverse=True)[:10]],
                    "carbon_by_type": [{"name": name, "value": round(value, 2)} for name, value in sorted(carbon_by_type.items(), key=lambda item: item[1], reverse=True)[:10]],
                    "alerts_by_area": [{"name": name or "未命名区域", "value": int(total)} for name, total in area_events],
                },
            }
        )

    @get("/api/carbon/analytics/efficiency")
    async def get_analytics_efficiency(self, db_session: AsyncSession) -> Response[dict]:
        latest_month = await self._latest_energy_month(db_session)
        energy_series = await self._build_energy_series(db_session, [latest_month] if latest_month else [])
        current_energy = energy_series[0] if energy_series else {"energy_kwh": 0.0, "carbon_co2e": 0.0, "record_count": 0, "source_kind": "empty"}
        scope_records = await self._load_scope_records(db_session)
        status_totals: dict[str, int] = defaultdict(int)
        source_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"energy_kwh": 0.0, "carbon_co2e": 0.0, "records": 0.0})
        for item in scope_records:
            status_totals[str(item["data"].get("status") or STATUS_DRAFT)] += 1
            source = str(item["data"].get("source_kind") or item["scope"])
            source_totals[source]["carbon_co2e"] += float(item["data"].get("computed_co2e") or 0.0)
            source_totals[source]["records"] += 1
            if item["record_type"] in {"Scope2ElectricityBill", "Scope2MeterAggregate"}:
                source_totals[source]["energy_kwh"] += float(item["data"].get("total_kwh") or 0.0)

        storage = await db_session.scalar(select(m.EnergyStorageValue).order_by(m.EnergyStorageValue.id.desc()).limit(1))
        source_mix = [
            {
                "name": name,
                "energy_kwh": round(values["energy_kwh"], 2),
                "carbon_co2e": round(values["carbon_co2e"], 2),
                "record_count": int(values["records"]),
            }
            for name, values in sorted(source_totals.items(), key=lambda item: item[1]["carbon_co2e"], reverse=True)
        ]
        if not source_mix and float(current_energy.get("energy_kwh") or 0.0) > 0:
            source_mix = [
                {
                    "name": str(current_energy.get("source_kind") or "raw_meter_fallback"),
                    "energy_kwh": round(float(current_energy.get("energy_kwh") or 0.0), 2),
                    "carbon_co2e": round(float(current_energy.get("carbon_co2e") or 0.0), 2),
                    "record_count": int(current_energy.get("record_count") or 0),
                }
            ]
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": latest_month,
                    "source_mix": source_mix,
                    "workflow": [{"name": name, "value": total} for name, total in status_totals.items()],
                    "energy_efficiency": {
                        "source_kind": current_energy.get("source_kind"),
                        "energy_kwh": round(float(current_energy.get("energy_kwh") or 0.0), 2),
                        "carbon_co2e": round(float(current_energy.get("carbon_co2e") or 0.0), 2),
                        "record_count": int(current_energy.get("record_count") or 0),
                    },
                    "storage": model_to_dict(storage) if storage else {},
                },
            }
        )

    @get("/api/carbon/energy-flow")
    async def get_energy_flow(self, db_session: AsyncSession, billing_month: str | None = None) -> Response[dict]:
        month = billing_month or await self._latest_energy_month(db_session)
        if not month:
            return Response(content={"code": 200, "msg": "暂无数据", "data": {"billing_month": None, "nodes": [], "links": [], "diagnostics": {"source_kind": "empty"}}})
        meter_rows = (
            await db_session.execute(
                select(m.Scope2MeterAggregate)
                .where(m.Scope2MeterAggregate.billing_month == month)
                .order_by(m.Scope2MeterAggregate.total_kwh.desc().nullslast())
            )
        ).scalars().all()
        diagnostics = {
            "source_kind": "meter_aggregate",
            "ready_count": sum(1 for row in meter_rows if row.calc_status == "ready"),
            "invalid_count": sum(1 for row in meter_rows if row.calc_status != "ready"),
            "used_fallback": False,
            "zero_ready_count": sum(1 for row in meter_rows if row.calc_status == "ready" and float(row.total_kwh or 0.0) <= 0),
        }
        flow_rows: list[dict[str, Any]]
        if meter_rows:
            flow_rows = [await _serialize_scope_record(row, db_session, source_kind="meter_aggregate") for row in meter_rows if row.total_kwh]
        else:
            month_start, month_end = _month_window(month)
            flow_rows = await self._raw_meter_rollups(db_session, month_start=month_start, month_end=month_end)
            diagnostics["source_kind"] = "raw_meter_fallback"
            diagnostics["used_fallback"] = True
        nodes: dict[str, dict[str, Any]] = {
            "grid": {"id": "grid", "name": "外部购电", "category": "source"},
        }
        links: list[dict[str, Any]] = []
        total_energy_kwh = 0.0
        for row in flow_rows:
            area_name = str(row.get("area_name") or "未分区")
            area_id = f"area:{area_name}"
            meter_name = str(row.get("ammeter_name") or row.get("display_name") or row.get("ammeter_id") or "未知电表")
            meter_id = f"meter:{row.get('ammeter_id') or meter_name}"
            result_id = f"result:{meter_id}:{month}"
            value = float(row.get("total_kwh") or 0.0)
            if value <= 0:
                continue
            total_energy_kwh += value
            nodes.setdefault(area_id, {"id": area_id, "name": area_name, "category": "area"})
            nodes.setdefault(meter_id, {"id": meter_id, "name": meter_name, "category": "meter"})
            nodes.setdefault(result_id, {"id": result_id, "name": f"{meter_name} 核算结果", "category": "result", "value": round(value, 2)})
            links.append({"source": "grid", "target": area_id, "value": round(value, 2)})
            links.append({"source": area_id, "target": meter_id, "value": round(value, 2)})
            links.append({"source": meter_id, "target": result_id, "value": round(value, 2)})
        diagnostics["total_energy_kwh"] = round(total_energy_kwh, 2)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "billing_month": month,
                    "title": "仓库级能流图",
                    "unit": "kWh",
                    "nodes": list(nodes.values()),
                    "links": links,
                    "diagnostics": diagnostics,
                },
            }
        )

    @get("/api/carbon/carbon-flow")
    async def get_carbon_flow(self, db_session: AsyncSession) -> Response[dict]:
        records = await self._load_scope_records(db_session)
        nodes: dict[str, dict[str, Any]] = {}
        links: list[dict[str, Any]] = []
        total_co2e = 0.0
        for item in records:
            co2e = float(item["data"].get("computed_co2e") or 0.0)
            if co2e <= 0:
                continue
            total_co2e += co2e
            scope_id = f"scope:{item['scope']}"
            activity_id = f"activity:{item['record_type']}:{item['display_name']}"
            factor_name = str(item["data"].get("factor_source") or "未命名因子")
            factor_year = item["data"].get("factor_year")
            factor_id = f"factor:{factor_name}:{factor_year or 'na'}"
            result_id = f"result:{item['record_type']}"
            nodes.setdefault(scope_id, {"id": scope_id, "name": item["scope"], "category": "scope"})
            nodes.setdefault(activity_id, {"id": activity_id, "name": item["display_name"], "category": "activity"})
            nodes.setdefault(factor_id, {"id": factor_id, "name": f"{factor_name}{f' / {factor_year}' if factor_year else ''}", "category": "factor"})
            nodes.setdefault(result_id, {"id": result_id, "name": item["record_label"], "category": "result"})
            links.append({"source": scope_id, "target": activity_id, "value": round(co2e, 2)})
            links.append({"source": activity_id, "target": factor_id, "value": round(co2e, 2)})
            links.append({"source": factor_id, "target": result_id, "value": round(co2e, 2)})
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "title": "范围级碳流图",
                    "unit": "kgCO2e",
                    "nodes": list(nodes.values()),
                    "links": links,
                    "diagnostics": {
                        "record_count": len(records),
                        "total_co2e": round(total_co2e, 2),
                        "empty_record_types": sorted({_scope_record_label(item["record_type"]) for item in records if item["data"].get("computed_co2e") is None}),
                    },
                },
            }
        )

    @get("/api/carbon/ledger/energy")
    async def get_energy_ledger(
        self,
        db_session: AsyncSession,
        billing_month: str | None = None,
        source_kind: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        items: list[dict[str, Any]] = []
        bill_rows = (await db_session.execute(select(m.Scope2ElectricityBill).where(m.Scope2ElectricityBill.status != STATUS_REJECTED))).scalars().all()
        for row in bill_rows:
            data = await _serialize_scope_record(row, db_session, source_kind="manual_bill")
            items.append(
                {
                    "record_type": "Scope2ElectricityBill",
                    "record_id": row.id,
                    "display_name": row.account_number,
                    "area_name": None,
                    "period": row.billing_month,
                    "source_kind": SOURCE_KIND_MANUAL_BILL,
                    "data_origin": data.get("data_origin"),
                    "total_kwh": _format_decimal(row.total_kwh),
                    "computed_co2e": data.get("computed_co2e"),
                    "calc_status": data.get("calc_status"),
                    "status": row.status,
                    "factor_source": data.get("factor_source"),
                }
            )
        meter_rows = (await db_session.execute(select(m.Scope2MeterAggregate).where(m.Scope2MeterAggregate.status != STATUS_REJECTED))).scalars().all()
        for row in meter_rows:
            data = await _serialize_scope_record(row, db_session, source_kind="meter_aggregate")
            items.append(
                {
                    "record_type": "Scope2MeterAggregate",
                    "record_id": row.id,
                    "display_name": row.ammeter_name or row.ammeter_id,
                    "area_name": row.area_name,
                    "period": row.billing_month,
                    "source_kind": SOURCE_KIND_DERIVED,
                    "data_origin": data.get("data_origin"),
                    "total_kwh": _format_decimal(row.total_kwh),
                    "computed_co2e": data.get("computed_co2e"),
                    "calc_status": data.get("calc_status"),
                    "status": row.status,
                    "factor_source": data.get("factor_source"),
                }
            )
        if billing_month and (source_kind in (None, SOURCE_KIND_ESTIMATE)):
            current_month_rows = [row for row in meter_rows if row.billing_month == billing_month]
            estimate_rows = await CarbonAnalyticsController._historical_scope2_estimates_for_month(db_session, billing_month, current_month_rows)
            for index, row in enumerate(estimate_rows):
                items.append(
                    {
                        "record_type": "Scope2HistoricalEstimate",
                        "record_id": -(index + 1),
                        "display_name": row.get("display_name"),
                        "area_name": row.get("area_name"),
                        "period": row.get("billing_month"),
                        "source_kind": SOURCE_KIND_ESTIMATE,
                        "total_kwh": row.get("total_kwh"),
                        "computed_co2e": row.get("computed_co2e"),
                        "calc_status": row.get("calc_status"),
                        "status": row.get("status"),
                        "factor_source": row.get("factor_source"),
                    }
                )
        if billing_month:
            items = [item for item in items if item["period"] == billing_month]
        if source_kind:
            items = [item for item in items if item["source_kind"] == source_kind]
        items.sort(key=lambda item: (_sort_month_key(item.get("period")), item["record_id"]), reverse=True)
        page = _paged_payload(items[offset : offset + limit], len(items), limit, offset)
        return Response(content=page)

    @get("/api/carbon/ledger/carbon")
    async def get_carbon_ledger(
        self,
        db_session: AsyncSession,
        scope: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        records = await self._load_scope_records(db_session)
        items = [
            {
                "record_type": item["record_type"],
                "record_label": item["record_label"],
                "record_id": item["row"].id,
                "scope": item["scope"],
                "display_name": item["display_name"],
                "period": item["period"],
                "status": item["data"].get("status"),
                "source_kind": item["data"].get("source_kind"),
                "data_origin": item["data"].get("data_origin"),
                "activity_amount": item["data"].get("activity_amount"),
                "activity_unit": item["data"].get("activity_unit"),
                "computed_co2e": item["data"].get("computed_co2e"),
                "factor_source": item["data"].get("factor_source"),
                "factor_year": item["data"].get("factor_year"),
            }
            for item in records
        ]
        if scope:
            items = [item for item in items if item["scope"] == scope]
        if status:
            items = [item for item in items if item["status"] == status]
        items.sort(key=lambda item: (_sort_month_key(item.get("period")), item["record_id"]), reverse=True)
        page = _paged_payload(items[offset : offset + limit], len(items), limit, offset)
        return Response(content=page)

    @get("/api/carbon/ledger/record/{record_type:str}/{record_id:int}")
    async def get_carbon_ledger_record_detail(
        self,
        db_session: AsyncSession,
        record_type: str,
        record_id: int,
    ) -> Response[dict]:
        model_map = {
            "Scope1MobileCombustion": m.Scope1MobileCombustion,
            "Scope1StationaryCombustion": m.Scope1StationaryCombustion,
            "Scope1RefrigerantLeak": m.Scope1RefrigerantLeak,
            "Scope2ElectricityBill": m.Scope2ElectricityBill,
            "Scope2MeterAggregate": m.Scope2MeterAggregate,
            "Scope3WasteDisposal": m.Scope3WasteDisposal,
            "Scope3ThirdPartyTransport": m.Scope3ThirdPartyTransport,
        }
        model = model_map.get(record_type)
        if model is None:
            return Response(content={"code": 404, "msg": "未知的记录类型"}, status_code=404)
        row = await db_session.get(model, record_id)
        if row is None:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        data = await _serialize_scope_record(
            row,
            db_session,
            source_kind="manual_bill" if record_type == "Scope2ElectricityBill" else "meter_aggregate" if record_type == "Scope2MeterAggregate" else None,
        )
        audit_logs = (
            await db_session.execute(
                select(m.CarbonAuditLog)
                .where(m.CarbonAuditLog.record_type == record_type, m.CarbonAuditLog.record_id == record_id)
                .order_by(m.CarbonAuditLog.created_at.desc())
            )
        ).scalars().all()
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "record_type": record_type,
                    "record_label": _scope_record_label(record_type),
                    "record_id": record_id,
                    "source": model_to_dict(row),
                    "computation": data,
                    "audit_logs": [model_to_dict(log) for log in audit_logs],
                },
            }
        )


class EnergyCarbonCenterController(Controller):
    """能碳中心聚合接口。"""

    tags = ["EnergyCarbonCenter"]
    signature_types = [Response]
    dependencies = {
        "scope2_meter_aggregate_service": provide_scope2_meter_aggregate_service,
        "security_audit_service": provide_audit_log_service,
    }

    @staticmethod
    def _record_model_map() -> dict[str, type]:
        return {
            "Scope1MobileCombustion": m.Scope1MobileCombustion,
            "Scope1StationaryCombustion": m.Scope1StationaryCombustion,
            "Scope1RefrigerantLeak": m.Scope1RefrigerantLeak,
            "Scope2ElectricityBill": m.Scope2ElectricityBill,
            "Scope2MeterAggregate": m.Scope2MeterAggregate,
            "Scope3WasteDisposal": m.Scope3WasteDisposal,
            "Scope3ThirdPartyTransport": m.Scope3ThirdPartyTransport,
        }

    async def _get_record_detail(self, db_session: AsyncSession, record_type: str, record_id: int) -> dict[str, Any] | None:
        model = self._record_model_map().get(record_type)
        if model is None:
            return None
        row = await db_session.get(model, record_id)
        if row is None:
            return None
        source_kind = "manual_bill" if record_type == "Scope2ElectricityBill" else "meter_aggregate" if record_type == "Scope2MeterAggregate" else None
        computation = await _serialize_scope_record(row, db_session, source_kind=source_kind)
        audit_logs = (
            await db_session.execute(
                select(m.CarbonAuditLog)
                .where(m.CarbonAuditLog.record_type == record_type, m.CarbonAuditLog.record_id == record_id)
                .order_by(m.CarbonAuditLog.created_at.desc())
            )
        ).scalars().all()
        return {
            "record_type": record_type,
            "record_label": _scope_record_label(record_type),
            "record_id": record_id,
            "source": model_to_dict(row),
            "computation": computation,
            "audit_logs": [model_to_dict(log) for log in audit_logs],
        }

    async def _demo_seed_operator_id(self, db_session: AsyncSession) -> Any:
        return await db_session.scalar(select(m.User.id).where(m.User.email == "ec-admin@example.com"))

    async def _clear_demo_seed_records(self, db_session: AsyncSession) -> dict[str, int]:
        deleted: dict[str, int] = {}
        for record_type, model in self._record_model_map().items():
            if not hasattr(model, "remark"):
                continue
            ids = [
                item[0]
                for item in (
                    await db_session.execute(
                        select(model.id).where(model.remark.is_not(None), model.remark.contains(DEMO_SEED_MARKER))
                    )
                ).all()
            ]
            if not ids:
                continue
            await db_session.execute(
                m.CarbonAuditLog.__table__.delete().where(
                    m.CarbonAuditLog.record_type == record_type,
                    m.CarbonAuditLog.record_id.in_(ids),
                )
            )
            await db_session.execute(model.__table__.delete().where(model.id.in_(ids)))
            deleted[record_type] = len(ids)
        await db_session.commit()
        return deleted

    async def _clear_imputed_meter_rows(self, db_session: AsyncSession, month_keys: list[str]) -> int:
        if not month_keys:
            return 0
        month_start, _ = _month_window(month_keys[0])
        _, month_end = _month_window(month_keys[-1])
        stmt = m.AmmeterIndexValue.__table__.delete().where(
            m.AmmeterIndexValue.data_source == 99,
            m.AmmeterIndexValue.reading_time >= month_start,
            m.AmmeterIndexValue.reading_time < month_end,
        )
        result = await db_session.execute(stmt)
        return int(result.rowcount or 0)

    async def _sync_ammeter_index_sequence(self, db_session: AsyncSession) -> None:
        sequence_name = await db_session.scalar(
            text("SELECT pg_get_serial_sequence('dataapp_ammeterindexvalue', 'id')")
        )
        if not sequence_name:
            return
        max_id = int(await db_session.scalar(text("SELECT COALESCE(MAX(id), 0) FROM dataapp_ammeterindexvalue")) or 0)
        quoted_sequence = str(sequence_name).replace("'", "''")
        await db_session.execute(text(f"SELECT setval('{quoted_sequence}', :max_id, true)"), {"max_id": max_id})

    async def _impute_raw_scope2_history(
        self,
        db_session: AsyncSession,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        month_keys: list[str],
    ) -> dict[str, Any]:
        if not month_keys:
            return {
                "months": [],
                "deleted_imputed_rows": 0,
                "inserted_imputed_rows": 0,
                "estimated_months": 0,
                "estimate_details": [],
                "rebuilt_count": 0,
                "ready_count": 0,
                "invalid_count": 0,
                "rebuild_details": [],
            }

        deleted_imputed_rows = await self._clear_imputed_meter_rows(db_session, month_keys)
        await self._sync_ammeter_index_sequence(db_session)

        # First rebuild against current raw data so estimation is based on a fresh monthly baseline.
        for billing_month in month_keys:
            await CarbonAccountingController._rebuild_scope2_meter_aggregates(self, db_session, scope2_meter_aggregate_service, billing_month)

        inserted_imputed_rows = 0
        estimate_details: list[dict[str, Any]] = []
        for billing_month in month_keys:
            current_rows = (
                await db_session.execute(select(m.Scope2MeterAggregate).where(m.Scope2MeterAggregate.billing_month == billing_month))
            ).scalars().all()
            estimate_rows = await CarbonAnalyticsController._historical_scope2_estimates_for_month(db_session, billing_month, current_rows)
            if not estimate_rows:
                continue

            month_start, month_end = _month_window(billing_month)
            raw_rows = (
                await db_session.execute(
                    select(m.AmmeterIndexValue)
                    .where(
                        m.AmmeterIndexValue.reading_time >= month_start,
                        m.AmmeterIndexValue.reading_time < month_end,
                        m.AmmeterIndexValue.ammeter_id.is_not(None),
                    )
                    .order_by(m.AmmeterIndexValue.ammeter_id.asc(), m.AmmeterIndexValue.reading_time.asc(), m.AmmeterIndexValue.id.asc())
                )
            ).scalars().all()
            samples_by_meter: dict[str, list[m.AmmeterIndexValue]] = defaultdict(list)
            for row in raw_rows:
                if row.ammeter_id:
                    samples_by_meter[str(row.ammeter_id)].append(row)

            created_for_month = 0
            for row in estimate_rows:
                ammeter_id = str(row.get("ammeter_id") or "")
                if not ammeter_id:
                    continue
                samples = samples_by_meter.get(ammeter_id, [])
                usable = [sample for sample in samples if sample.zygdn is not None]
                if not usable:
                    continue
                first = usable[0]
                last_sample = samples[-1]
                target_time = min(
                    (last_sample.reading_time or month_start) + datetime.timedelta(minutes=1),
                    month_end - datetime.timedelta(seconds=1),
                )
                if last_sample.reading_time and target_time <= last_sample.reading_time:
                    target_time = last_sample.reading_time + datetime.timedelta(seconds=1)
                if target_time >= month_end:
                    continue

                first_value = float(first.zygdn or 0.0)
                last_value = float(usable[-1].zygdn or 0.0)
                estimate_kwh = float(row.get("total_kwh") or 0.0)
                synthetic_total = max(last_value, first_value + estimate_kwh)

                imputed = m.AmmeterIndexValue(
                    equipment_id=last_sample.equipment_id or first.equipment_id,
                    zygdn=synthetic_total,
                    fygdn=last_sample.fygdn,
                    zwgdn=last_sample.zwgdn,
                    fwgdn=last_sample.fwgdn,
                    zygdnsz=last_sample.zygdnsz,
                    fygdnsz=last_sample.fygdnsz,
                    zwgdnsz=last_sample.zwgdnsz,
                    fwgdnsz=last_sample.fwgdnsz,
                    reading_time=target_time,
                    ammeter_id=last_sample.ammeter_id or first.ammeter_id,
                    ammeter_name=last_sample.ammeter_name or first.ammeter_name,
                    address=last_sample.address or first.address,
                    area_id=last_sample.area_id or first.area_id,
                    area_name=last_sample.area_name or first.area_name,
                    radio=last_sample.radio,
                    start_time=last_sample.start_time,
                    end_time=last_sample.end_time,
                    data_source=99,
                    add_time=datetime.datetime.utcnow(),
                )
                db_session.add(imputed)
                created_for_month += 1
                inserted_imputed_rows += 1

            if created_for_month:
                estimate_details.append(
                    {
                        "billing_month": billing_month,
                        "estimated_rows": created_for_month,
                    }
                )
                await self._sync_ammeter_index_sequence(db_session)

        await db_session.flush()

        rebuilt_count = 0
        ready_count = 0
        invalid_count = 0
        rebuild_details: list[dict[str, Any]] = []
        for billing_month in month_keys:
            rows = await CarbonAccountingController._rebuild_scope2_meter_aggregates(self, db_session, scope2_meter_aggregate_service, billing_month)
            rebuilt_count += len(rows)
            ready_month = sum(1 for row in rows if row.calc_status == "ready")
            invalid_month = len(rows) - ready_month
            ready_count += ready_month
            invalid_count += invalid_month
            rebuild_details.append(
                {
                    "billing_month": billing_month,
                    "rebuilt_count": len(rows),
                    "ready_count": ready_month,
                    "invalid_count": invalid_month,
                }
            )

        await db_session.commit()
        return {
            "months": month_keys,
            "deleted_imputed_rows": deleted_imputed_rows,
            "inserted_imputed_rows": inserted_imputed_rows,
            "estimated_months": len(estimate_details),
            "estimate_details": estimate_details,
            "rebuilt_count": rebuilt_count,
            "ready_count": ready_count,
            "invalid_count": invalid_count,
            "rebuild_details": rebuild_details,
        }

    async def _seed_demo_scope_records(self, db_session: AsyncSession, months: int = 6) -> dict[str, int]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session) or datetime.date.today().strftime("%Y-%m")
        month_keys = _seed_months(latest_month, max(3, min(months, 6)))
        operator_id = await self._demo_seed_operator_id(db_session)
        created: dict[str, int] = defaultdict(int)
        pending_logs: list[dict[str, Any]] = []

        def month_date(month: str, day: int = 1) -> datetime.date:
            return _month_start_date(month).replace(day=min(day, 28))

        common_feature_fields = {
            "data_source": "demo_seed",
            "collection_method": "manual_demo",
            "confidence_level": "medium",
            "data_year_type": "calendar_year",
        }

        seeded_rows: list[tuple[str, Any, str]] = []
        for index, month in enumerate(month_keys):
            seeded_rows.extend(
                [
                    (
                        "Scope1MobileCombustion",
                        m.Scope1MobileCombustion(
                            record_date=month_date(month, 5),
                            asset_id=f"FK-{index + 1:02d}",
                            asset_name=f"园区叉车 {index + 1}",
                            fuel_type="diesel" if index % 2 == 0 else "gasoline",
                            amount=Decimal("118.5") + Decimal(index * 9),
                            unit="L",
                            mileage_km=Decimal(1280) + Decimal(index * 90),
                            work_hours=Decimal(72) + Decimal(index * 4),
                            attachment=None if index == 0 else f"/demo/evidence/scope1-mobile-{month}.pdf",
                            remark=f"{DEMO_SEED_MARKER} 范围1移动源演示记录",
                            status=STATUS_PENDING if index == 0 else STATUS_APPROVED,
                            approved_at=None if index == 0 else datetime.datetime.combine(month_date(month, 24), datetime.time.min),
                            data_year=month_date(month, 5).year,
                            **common_feature_fields,
                        ),
                        "提交待审" if index == 0 else "审核通过",
                    ),
                    (
                        "Scope1StationaryCombustion",
                        m.Scope1StationaryCombustion(
                            facility_name=f"备用发电机房 {index + 1}",
                            period_start=month_date(month, 1),
                            period_end=month_date(month, 28),
                            fuel_type="natural_gas" if index % 2 == 0 else "diesel",
                            amount=Decimal(420) + Decimal(index * 35),
                            unit="m³" if index % 2 == 0 else "L",
                            meter_reading_start=Decimal(1000) + Decimal(index * 120),
                            meter_reading_end=Decimal(1100) + Decimal(index * 140),
                            attachment=f"/demo/evidence/scope1-stationary-{month}.pdf",
                            remark=f"{DEMO_SEED_MARKER} 范围1固定源演示记录",
                            status=STATUS_APPROVED,
                            approved_at=datetime.datetime.combine(month_date(month, 23), datetime.time.min),
                            data_year=month_date(month, 1).year,
                            **common_feature_fields,
                        ),
                        "审核通过",
                    ),
                    (
                        "Scope1RefrigerantLeak",
                        m.Scope1RefrigerantLeak(
                            device_id=f"AC-{index + 1:02d}",
                            device_name=f"冷机组 {index + 1}",
                            fill_date=month_date(month, 12),
                            refrigerant_type="r410a" if index != 1 else "unknown_refrigerant",
                            amount_kg=Decimal("2.6") + Decimal(index) / Decimal(10),
                            leak_type="maintenance" if index % 2 == 0 else "leak",
                            attachment=None,
                            remark=f"{DEMO_SEED_MARKER} 范围1制冷剂演示记录",
                            status=STATUS_REJECTED if index == 1 else STATUS_PENDING,
                            reject_reason="因子未匹配，需确认制冷剂类型" if index == 1 else None,
                            data_year=month_date(month, 12).year,
                            **common_feature_fields,
                        ),
                        "驳回" if index == 1 else "提交待审",
                    ),
                    (
                        "Scope3WasteDisposal",
                        m.Scope3WasteDisposal(
                            date=month_date(month, 18),
                            category="waste_municipal_incineration" if index % 2 == 0 else "waste_unknown",
                            weight_ton=Decimal("4.2") + Decimal(index) / Decimal(2),
                            treatment_method="incineration" if index % 2 == 0 else "outsourced",
                            vendor_name=f"再生资源服务商 {index + 1}",
                            attachment=None if index == 2 else f"/demo/evidence/scope3-waste-{month}.pdf",
                            remark=f"{DEMO_SEED_MARKER} 范围3废弃物演示记录",
                            status=STATUS_PENDING if index in {0, 2} else STATUS_APPROVED,
                            approved_at=None if index in {0, 2} else datetime.datetime.combine(month_date(month, 26), datetime.time.min),
                            data_year=month_date(month, 18).year,
                            **common_feature_fields,
                        ),
                        "提交待审" if index in {0, 2} else "审核通过",
                    ),
                    (
                        "Scope3ThirdPartyTransport",
                        m.Scope3ThirdPartyTransport(
                            waybill_no=f"WB-{month.replace('-', '')}-{index + 1:02d}",
                            origin="苏州工业园区仓",
                            destination=f"华东客户点位 {index + 1}",
                            vehicle_type="transport_heavy_truck" if index % 2 == 0 else "transport_light_truck",
                            distance_km=Decimal(286) + Decimal(index * 12),
                            load_ton=Decimal("14.5") + Decimal(index) / Decimal(2),
                            fuel_amount=None,
                            attachment=f"/demo/evidence/scope3-transport-{month}.pdf" if index != 3 else None,
                            remark=f"{DEMO_SEED_MARKER} 范围3运输演示记录",
                            status=STATUS_APPROVED if index % 2 == 0 else STATUS_PENDING,
                            approved_at=datetime.datetime.combine(month_date(month, 25), datetime.time.min) if index % 2 == 0 else None,
                            created_at=datetime.datetime.combine(month_date(month, 20), datetime.time.min),
                            data_year=month_date(month, 20).year,
                            **common_feature_fields,
                        ),
                        "审核通过" if index % 2 == 0 else "提交待审",
                    ),
                ]
            )

        rows_by_type: dict[str, list[Any]] = defaultdict(list)
        for record_type, row, _log_comment in seeded_rows:
            db_session.add(row)
            rows_by_type[record_type].append(row)
            created[record_type] += 1

        await db_session.flush()

        for record_type, row, log_comment in seeded_rows:
            pending_logs.append(
                {
                    "record_type": record_type,
                    "record_id": row.id,
                    "action": AUDIT_ACTION_APPROVE if row.status == STATUS_APPROVED else AUDIT_ACTION_REJECT if row.status == STATUS_REJECTED else AUDIT_ACTION_SUBMIT,
                    "operator_id": operator_id,
                    "comment": log_comment,
                    "created_at": getattr(row, "approved_at", None) or datetime.datetime.utcnow(),
                }
            )

        if pending_logs:
            await db_session.execute(m.CarbonAuditLog.__table__.insert(), pending_logs)
        await db_session.commit()
        return dict(created)

    async def _build_monitor_area_summary(self, db_session: AsyncSession) -> list[dict[str, Any]]:
        sectors = (
            await db_session.execute(select(m.MonitorSector).options(selectinload(m.MonitorSector.photos)).order_by(m.MonitorSector.id.asc()))
        ).scalars().all()
        equipment_counts = {
            sector_id: {"total": 0, "online": 0, "fault": 0}
            for sector_id in [sector.id for sector in sectors]
        }
        equipment_rows = (
            await db_session.execute(select(m.MonitorEquipment.id, m.MonitorEquipment.sector_id, m.MonitorEquipment.status, m.MonitorEquipment.category))
        ).all()
        for equipment_id, sector_id, status, _category in equipment_rows:
            if sector_id not in equipment_counts:
                continue
            equipment_counts[sector_id]["total"] += 1
            if status == 0:
                equipment_counts[sector_id]["online"] += 1
            else:
                equipment_counts[sector_id]["fault"] += 1

        alert_rows = (
            await db_session.execute(
                select(m.AlarmEvent.sector_id, func.count(m.AlarmEvent.id), func.sum(case((m.AlarmEvent.is_handle.is_(False), 1), else_=0)))
                .group_by(m.AlarmEvent.sector_id)
            )
        ).all()
        alert_map = {sector_id: {"total": int(total or 0), "unhandled": int(unhandled or 0)} for sector_id, total, unhandled in alert_rows}

        video_rows = (
            await db_session.execute(select(m.VideoMonitor.f_area, func.count(m.VideoMonitor.id), func.sum(case((m.VideoMonitor.status == 0, 1), else_=0))).group_by(m.VideoMonitor.f_area))
        ).all()
        video_map = {str(area or ""): {"total": int(total or 0), "online": int(online or 0)} for area, total, online in video_rows}

        items: list[dict[str, Any]] = []
        for sector in sectors:
            equipment = equipment_counts.get(sector.id, {"total": 0, "online": 0, "fault": 0})
            alerts = alert_map.get(sector.id, {"total": 0, "unhandled": 0})
            videos = video_map.get(str(sector.name or ""), {"total": 0, "online": 0})
            total_objects = max(equipment["total"] + videos["total"], 1)
            online_objects = equipment["online"] + videos["online"]
            status = "高风险" if alerts["unhandled"] > 3 or equipment["fault"] > 0 else "稳定"
            items.append(
                {
                    "id": sector.id,
                    "name": sector.name or f"区域{sector.id}",
                    "area_id": sector.area_id,
                    "description": sector.description,
                    "equipment_total": equipment["total"],
                    "equipment_online": equipment["online"],
                    "equipment_fault": equipment["fault"],
                    "video_total": videos["total"],
                    "video_online": videos["online"],
                    "alert_total": alerts["total"],
                    "alert_unhandled": alerts["unhandled"],
                    "health_ratio": round((online_objects / total_objects) * 100, 1),
                    "status": status,
                    "photo_count": len(sector.photos or []),
                }
            )
        return items

    async def _build_unified_alerts(self, db_session: AsyncSession) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        area_names = {
            sector_id: sector_name or f"区域{sector_id}"
            for sector_id, sector_name in (await db_session.execute(select(m.MonitorSector.id, m.MonitorSector.name))).all()
        }
        equipment_names = {
            equipment_id: equipment_name or equipment_code
            for equipment_id, equipment_name, equipment_code in (await db_session.execute(select(m.MonitorEquipment.id, m.MonitorEquipment.name, m.MonitorEquipment.code))).all()
        }
        video_names = {
            video_id: location or f"视频点位{video_id}"
            for video_id, location in (await db_session.execute(select(m.VideoMonitor.id, m.VideoMonitor.location))).all()
        }

        alarm_rows = (await db_session.execute(select(m.AlarmEvent).order_by(m.AlarmEvent.event_time.desc().nullslast(), m.AlarmEvent.id.desc()))).scalars().all()
        severity_map = {1: "high", 2: "medium", 3: "medium", 4: "high"}
        type_map = {1: "设备告警", 2: "用能告警", 3: "发电告警", 4: "碳告警"}
        for row in alarm_rows:
            alerts.append(
                {
                    "id": f"alarm:{row.id}",
                    "source": "alarm",
                    "record_id": row.id,
                    "alert_type": type_map.get(row.event_type, "业务告警"),
                    "severity": severity_map.get(row.event_type, "medium"),
                    "title": row.event_desc or type_map.get(row.event_type, "业务告警"),
                    "area_name": area_names.get(row.sector_id, "未分区"),
                    "object_name": equipment_names.get(row.equipment_id, f"设备{row.equipment_id}" if row.equipment_id else "未关联对象"),
                    "status": "已处理" if row.is_handle else "待处理",
                    "occurred_at": row.event_time.isoformat() if row.event_time else None,
                    "description": row.event_desc,
                }
            )

        video_alert_rows = (
            await db_session.execute(select(m.VedioAlarmEvent).order_by(m.VedioAlarmEvent.event_time.desc().nullslast(), m.VedioAlarmEvent.id.desc()))
        ).scalars().all()
        video_type_map = {1: "未佩戴安全帽", 2: "烟火", 3: "火点", 4: "区域入侵"}
        video_severity_map = {1: "medium", 2: "high", 3: "high", 4: "medium"}
        for row in video_alert_rows:
            alerts.append(
                {
                    "id": f"video:{row.id}",
                    "source": "video",
                    "record_id": row.id,
                    "alert_type": "视频告警",
                    "severity": video_severity_map.get(row.event_type, "medium"),
                    "title": video_type_map.get(row.event_type, "视频告警"),
                    "area_name": "视频监控",
                    "object_name": video_names.get(row.equipment_id, f"视频{row.equipment_id}" if row.equipment_id else "未关联视频"),
                    "status": "已处理" if row.is_handle else "待处理",
                    "occurred_at": row.event_time.isoformat() if row.event_time else None,
                    "description": row.event_desc,
                }
            )

        invalid_aggregates = (
            await db_session.execute(
                select(m.Scope2MeterAggregate)
                .where(m.Scope2MeterAggregate.calc_status != "ready")
                .order_by(m.Scope2MeterAggregate.billing_month.desc(), m.Scope2MeterAggregate.id.desc())
            )
        ).scalars().all()
        for row in invalid_aggregates:
            alerts.append(
                {
                    "id": f"carbon:{row.id}",
                    "source": "carbon",
                    "record_id": row.id,
                    "record_type": "Scope2MeterAggregate",
                    "alert_type": "碳告警",
                    "severity": "high",
                    "title": "范围2聚合不可核算",
                    "area_name": row.area_name or "未分区",
                    "object_name": row.ammeter_name or row.ammeter_id,
                    "status": "待处理" if row.status != STATUS_APPROVED else "已处理",
                    "occurred_at": row.updated_at.isoformat() if row.updated_at else row.created_at.isoformat() if row.created_at else None,
                    "description": row.aggregation_note or row.computation_note or "聚合快照未形成有效核算结果",
                }
            )

        alerts.sort(key=lambda item: item.get("occurred_at") or "", reverse=True)
        return alerts

    async def _build_quality_issues(self, db_session: AsyncSession) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        recent_months = await CarbonAnalyticsController._recent_scope2_backfill_months(db_session, 12)
        if recent_months:
            energy_series = await CarbonAnalyticsController._build_energy_series(db_session, recent_months)
            for item in energy_series:
                if item.get("source_kind") != SOURCE_KIND_FALLBACK:
                    continue
                period = str(item.get("period") or "")
                energy_value = round(float(item.get("energy_kwh") or 0.0), 2)
                issues.append(
                    {
                        "id": f"fallback:{period}",
                        "issue_code": "raw_meter_fallback_in_use",
                        "issue_type": "回退来源",
                        "severity": "medium",
                        "module": "范围2聚合",
                        "object_name": "月度用电核算",
                        "period": period,
                        "message": f"当前账期仍在使用电表明细回退，正式聚合快照缺失。回退电量 {energy_value} kWh。",
                    }
                )
                issues.append(
                    {
                        "id": f"missing-aggregate:{period}",
                        "issue_code": "missing_scope2_aggregate",
                        "issue_type": "缺失聚合",
                        "severity": "high",
                        "module": "范围2聚合",
                        "object_name": "月度用电核算",
                        "period": period,
                        "message": "存在原始电表数据，但未形成正式 Scope2 聚合记录。",
                    }
                )

        invalid_aggregates = (
            await db_session.execute(
                select(m.Scope2MeterAggregate)
                .where(m.Scope2MeterAggregate.calc_status != "ready")
                .order_by(m.Scope2MeterAggregate.billing_month.desc(), m.Scope2MeterAggregate.id.desc())
            )
        ).scalars().all()
        for row in invalid_aggregates:
            issue_code = "invalid_scope2_delta" if row.calc_status == "invalid_delta" else "insufficient_scope2_samples"
            issue_type = "异常增量" if row.calc_status == "invalid_delta" else "采样不足"
            issues.append(
                {
                    "id": f"aggregate:{row.id}",
                    "issue_code": issue_code,
                    "issue_type": issue_type,
                    "severity": "high",
                    "module": "范围2聚合",
                    "object_name": row.ammeter_name or row.ammeter_id,
                    "period": row.billing_month,
                    "message": row.aggregation_note or row.computation_note or "聚合记录未形成有效核算结果",
                    "record_type": "Scope2MeterAggregate",
                    "record_id": row.id,
                }
            )

        scope_records = await CarbonAnalyticsController._load_scope_records(db_session)
        for item in scope_records:
            data = item["data"]
            if data.get("computed_co2e") is None:
                issues.append(
                    {
                        "id": f"record:{item['record_type']}:{item['row'].id}",
                        "issue_code": "missing_computed_co2e",
                        "issue_type": "缺失核算结果",
                        "severity": "medium",
                        "module": item["scope"],
                        "object_name": item["display_name"],
                        "period": item["period"],
                        "message": data.get("computation_note") or "记录尚未形成有效 CO2e 结果",
                        "record_type": item["record_type"],
                        "record_id": item["row"].id,
                    }
                )
            if not data.get("factor_source"):
                issues.append(
                    {
                        "id": f"factor:{item['record_type']}:{item['row'].id}",
                        "issue_code": "missing_factor_binding",
                        "issue_type": "缺失因子",
                        "severity": "high",
                        "module": item["scope"],
                        "object_name": item["display_name"],
                        "period": item["period"],
                        "message": "当前记录缺少有效因子来源信息。",
                        "record_type": item["record_type"],
                        "record_id": item["row"].id,
                    }
                )
            if data.get("status") == STATUS_PENDING and not _record_attachment(item["row"]):
                issues.append(
                    {
                        "id": f"evidence:{item['record_type']}:{item['row'].id}",
                        "issue_code": "missing_evidence",
                        "issue_type": "缺失凭证",
                        "severity": "medium",
                        "module": item["scope"],
                        "object_name": item["display_name"],
                        "period": item["period"],
                        "message": "当前记录待审核，但未附带业务凭证。",
                        "record_type": item["record_type"],
                        "record_id": item["row"].id,
                    }
                )
            if data.get("status") == STATUS_PENDING and (not data.get("factor_source") or data.get("computed_co2e") is None):
                issues.append(
                    {
                        "id": f"audit:{item['record_type']}:{item['row'].id}",
                        "issue_code": "audit_blocked",
                        "issue_type": "审核阻塞",
                        "severity": "high",
                        "module": item["scope"],
                        "object_name": item["display_name"],
                        "period": item["period"],
                        "message": "待审核记录存在因子或结果缺口，当前无法形成稳定审核结论。",
                        "record_type": item["record_type"],
                        "record_id": item["row"].id,
                    }
                )
            if data.get("source_kind") == SOURCE_KIND_DEMO_SEED:
                issues.append(
                    {
                        "id": f"demo:{item['record_type']}:{item['row'].id}",
                        "issue_code": "demo_seed_present",
                        "issue_type": "初始化数据",
                        "severity": "low",
                        "module": item["scope"],
                        "object_name": item["display_name"],
                        "period": item["period"],
                        "message": "该记录需要补充业务来源或审核凭证。",
                        "record_type": item["record_type"],
                        "record_id": item["row"].id,
                    }
                )
        issues.sort(key=lambda item: (str(item.get("period") or ""), item["id"]), reverse=True)
        return issues

    async def _trend_data(self, db_session: AsyncSession, months: int) -> dict[str, Any]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session)
        if not latest_month:
            return {"series": [], "months": []}
        month_keys = _months_back(latest_month, max(3, min(months, 24)))
        energy_series = await CarbonAnalyticsController._build_energy_series(db_session, month_keys)
        carbon_records = await CarbonAnalyticsController._load_scope_records(db_session)
        scope_month_totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for item in carbon_records:
            month = item["period"]
            if not month:
                continue
            scope_month_totals[month][item["scope"]] += float(item["data"].get("computed_co2e") or 0.0)

        series = []
        for item in energy_series:
            month = item["period"]
            scope1 = scope_month_totals[month].get("范围1", 0.0)
            scope2 = float(item.get("carbon_co2e") or 0.0)
            scope3 = scope_month_totals[month].get("范围3", 0.0)
            series.append(
                {
                    "period": month,
                    "energy_kwh": round(float(item.get("energy_kwh") or 0.0), 2),
                    "scope1_co2e": round(scope1, 2),
                    "scope2_co2e": round(scope2, 2),
                    "scope3_co2e": round(scope3, 2),
                    "carbon_co2e": round(scope1 + scope2 + scope3, 2),
                    "source_kind": item.get("source_kind"),
                }
            )
        return {"months": month_keys, "series": series}

    async def _ranking_data(self, db_session: AsyncSession) -> dict[str, Any]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session)
        energy_rows: list[dict[str, Any]] = []
        diagnostics = {"source_kind": "empty"}
        if latest_month:
            ready_rows = (
                await db_session.execute(
                    select(m.Scope2MeterAggregate)
                    .where(
                        m.Scope2MeterAggregate.billing_month == latest_month,
                        m.Scope2MeterAggregate.calc_status == "ready",
                    )
                    .order_by(m.Scope2MeterAggregate.total_kwh.desc().nullslast())
                )
            ).scalars().all()
            if ready_rows:
                energy_rows = [await _serialize_scope_record(row, db_session, source_kind="meter_aggregate") for row in ready_rows]
                diagnostics["source_kind"] = "meter_aggregate"
            else:
                month_start, month_end = _month_window(latest_month)
                energy_rows = await CarbonAnalyticsController._raw_meter_rollups(db_session, month_start=month_start, month_end=month_end)
                diagnostics["source_kind"] = "raw_meter_fallback"

        energy_by_area: dict[str, float] = defaultdict(float)
        for row in energy_rows:
            area_name = str(row.get("area_name") or "未分区")
            energy_by_area[area_name] += float(row.get("total_kwh") or 0.0)

        carbon_records = await CarbonAnalyticsController._load_scope_records(db_session)
        carbon_by_type: dict[str, float] = defaultdict(float)
        for item in carbon_records:
            carbon_by_type[item["record_label"]] += float(item["data"].get("computed_co2e") or 0.0)

        area_events = (
            await db_session.execute(
                select(m.MonitorSector.name, func.count(m.AlarmEvent.id))
                .join(m.AlarmEvent, m.AlarmEvent.sector_id == m.MonitorSector.id)
                .group_by(m.MonitorSector.name)
                .order_by(func.count(m.AlarmEvent.id).desc())
                .limit(10)
            )
        ).all()
        return {
            "latest_month": latest_month,
            "diagnostics": diagnostics,
            "energy_by_area": [{"name": name, "value": round(value, 2)} for name, value in sorted(energy_by_area.items(), key=lambda item: item[1], reverse=True)[:10]],
            "carbon_by_type": [{"name": name, "value": round(value, 2)} for name, value in sorted(carbon_by_type.items(), key=lambda item: item[1], reverse=True)[:10]],
            "alerts_by_area": [{"name": name or "未命名区域", "value": int(total)} for name, total in area_events],
        }

    async def _efficiency_data(self, db_session: AsyncSession) -> dict[str, Any]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session)
        energy_series = await CarbonAnalyticsController._build_energy_series(db_session, [latest_month] if latest_month else [])
        current_energy = energy_series[0] if energy_series else {"energy_kwh": 0.0, "carbon_co2e": 0.0, "record_count": 0, "source_kind": "empty"}
        scope_records = await CarbonAnalyticsController._load_scope_records(db_session)
        status_totals: dict[str, int] = defaultdict(int)
        source_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"energy_kwh": 0.0, "carbon_co2e": 0.0, "records": 0.0})
        for item in scope_records:
            status_totals[str(item["data"].get("status") or STATUS_DRAFT)] += 1
            source = str(item["data"].get("source_kind") or item["scope"])
            source_totals[source]["carbon_co2e"] += float(item["data"].get("computed_co2e") or 0.0)
            source_totals[source]["records"] += 1
            if item["record_type"] in {"Scope2ElectricityBill", "Scope2MeterAggregate"}:
                source_totals[source]["energy_kwh"] += float(item["data"].get("total_kwh") or 0.0)

        storage = await db_session.scalar(select(m.EnergyStorageValue).order_by(m.EnergyStorageValue.id.desc()).limit(1))
        source_mix = [
            {
                "name": name,
                "energy_kwh": round(values["energy_kwh"], 2),
                "carbon_co2e": round(values["carbon_co2e"], 2),
                "record_count": int(values["records"]),
            }
            for name, values in sorted(source_totals.items(), key=lambda item: item[1]["carbon_co2e"], reverse=True)
        ]
        if not source_mix and float(current_energy.get("energy_kwh") or 0.0) > 0:
            source_mix = [
                {
                    "name": str(current_energy.get("source_kind") or "raw_meter_fallback"),
                    "energy_kwh": round(float(current_energy.get("energy_kwh") or 0.0), 2),
                    "carbon_co2e": round(float(current_energy.get("carbon_co2e") or 0.0), 2),
                    "record_count": int(current_energy.get("record_count") or 0),
                }
            ]
        return {
            "latest_month": latest_month,
            "source_mix": source_mix,
            "workflow": [{"name": name, "value": total} for name, total in status_totals.items()],
            "energy_efficiency": {
                "source_kind": current_energy.get("source_kind"),
                "energy_kwh": round(float(current_energy.get("energy_kwh") or 0.0), 2),
                "carbon_co2e": round(float(current_energy.get("carbon_co2e") or 0.0), 2),
                "record_count": int(current_energy.get("record_count") or 0),
            },
            "storage": model_to_dict(storage) if storage else {},
        }

    async def _energy_flow_data(self, db_session: AsyncSession, billing_month: str | None = None) -> dict[str, Any]:
        month = billing_month or await CarbonAnalyticsController._latest_energy_month(db_session)
        if not month:
            return {"billing_month": None, "title": "仓库级能流图", "unit": "kWh", "nodes": [], "links": [], "diagnostics": {"source_kind": "empty"}}
        meter_rows = (
            await db_session.execute(
                select(m.Scope2MeterAggregate)
                .where(m.Scope2MeterAggregate.billing_month == month)
                .order_by(m.Scope2MeterAggregate.total_kwh.desc().nullslast())
            )
        ).scalars().all()
        diagnostics = {
            "source_kind": "meter_aggregate",
            "ready_count": sum(1 for row in meter_rows if row.calc_status == "ready"),
            "invalid_count": sum(1 for row in meter_rows if row.calc_status != "ready"),
            "zero_ready_count": sum(1 for row in meter_rows if row.calc_status == "ready" and float(row.total_kwh or 0.0) <= 0),
            "used_fallback": False,
        }
        flow_rows: list[dict[str, Any]]
        estimate_rows: list[dict[str, Any]] = []
        if meter_rows:
            flow_rows = [await _serialize_scope_record(row, db_session, source_kind="meter_aggregate") for row in meter_rows if row.total_kwh]
            estimate_rows = await CarbonAnalyticsController._historical_scope2_estimates_for_month(db_session, month, meter_rows)
        else:
            month_start, month_end = _month_window(month)
            flow_rows = await CarbonAnalyticsController._raw_meter_rollups(db_session, month_start=month_start, month_end=month_end)
            diagnostics["source_kind"] = "raw_meter_fallback"
            diagnostics["used_fallback"] = True
        if estimate_rows:
            flow_rows = [*flow_rows, *estimate_rows]
        nodes: dict[str, dict[str, Any]] = {"grid": {"id": "grid", "name": "外部购电", "category": "source"}}
        links: list[dict[str, Any]] = []
        area_totals: dict[str, float] = {}
        total_energy_kwh = 0.0
        for row in flow_rows:
            area_name = str(row.get("area_name") or "未分区")
            value = float(row.get("total_kwh") or 0.0)
            if value <= 0:
                continue
            total_energy_kwh += value
            area_totals[area_name] = area_totals.get(area_name, 0.0) + value
        for area_name, value in sorted(area_totals.items(), key=lambda item: item[1], reverse=True):
            area_id = f"area:{area_name}"
            result_id = f"result:{area_name}:{month}"
            nodes.setdefault(area_id, {"id": area_id, "name": area_name, "category": "area", "value": round(value, 2)})
            nodes.setdefault(
                result_id,
                {
                    "id": result_id,
                    "name": f"{area_name} 核算结果",
                    "category": "result",
                    "value": round(value, 2),
                },
            )
            links.append({"source": "grid", "target": area_id, "value": round(value, 2)})
            links.append({"source": area_id, "target": result_id, "value": round(value, 2)})
        diagnostics["total_energy_kwh"] = round(total_energy_kwh, 2)
        diagnostics["positive_area_count"] = len(area_totals)
        diagnostics["estimated_count"] = len(estimate_rows)
        diagnostics["estimated_energy_kwh"] = round(sum(float(row.get("total_kwh") or 0.0) for row in estimate_rows), 4)
        return {"billing_month": month, "title": "仓库级能流图", "unit": "kWh", "nodes": list(nodes.values()), "links": links, "diagnostics": diagnostics}

    async def _energy_ledger_page(
        self,
        db_session: AsyncSession,
        billing_month: str | None = None,
        source_kind: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        bill_rows = (await db_session.execute(select(m.Scope2ElectricityBill).where(m.Scope2ElectricityBill.status != STATUS_REJECTED))).scalars().all()
        for row in bill_rows:
            data = await _serialize_scope_record(row, db_session, source_kind="manual_bill")
            items.append(
                {
                    "record_type": "Scope2ElectricityBill",
                    "record_id": row.id,
                    "display_name": row.account_number,
                    "area_name": None,
                    "period": row.billing_month,
                    "source_kind": "manual_bill",
                    "total_kwh": _format_decimal(row.total_kwh),
                    "computed_co2e": data.get("computed_co2e"),
                    "calc_status": data.get("calc_status"),
                    "status": row.status,
                    "factor_source": data.get("factor_source"),
                }
            )
        meter_rows = (await db_session.execute(select(m.Scope2MeterAggregate).where(m.Scope2MeterAggregate.status != STATUS_REJECTED))).scalars().all()
        for row in meter_rows:
            data = await _serialize_scope_record(row, db_session, source_kind="meter_aggregate")
            items.append(
                {
                    "record_type": "Scope2MeterAggregate",
                    "record_id": row.id,
                    "display_name": row.ammeter_name or row.ammeter_id,
                    "area_name": row.area_name,
                    "period": row.billing_month,
                    "source_kind": "meter_aggregate",
                    "total_kwh": _format_decimal(row.total_kwh),
                    "computed_co2e": data.get("computed_co2e"),
                    "calc_status": data.get("calc_status"),
                    "status": row.status,
                    "factor_source": data.get("factor_source"),
                }
            )
        if billing_month and (source_kind in (None, SOURCE_KIND_ESTIMATE)):
            current_month_rows = [row for row in meter_rows if row.billing_month == billing_month]
            estimate_rows = await CarbonAnalyticsController._historical_scope2_estimates_for_month(db_session, billing_month, current_month_rows)
            for index, row in enumerate(estimate_rows):
                items.append(
                    {
                        "record_type": "Scope2HistoricalEstimate",
                        "record_id": -(index + 1),
                        "display_name": row.get("display_name"),
                        "area_name": row.get("area_name"),
                        "period": row.get("billing_month"),
                        "source_kind": SOURCE_KIND_ESTIMATE,
                        "total_kwh": row.get("total_kwh"),
                        "computed_co2e": row.get("computed_co2e"),
                        "calc_status": row.get("calc_status"),
                        "status": row.get("status"),
                        "factor_source": row.get("factor_source"),
                    }
                )
        if billing_month:
            items = [item for item in items if item["period"] == billing_month]
        if source_kind:
            items = [item for item in items if item["source_kind"] == source_kind]
        items.sort(key=lambda item: (_sort_month_key(item.get("period")), item["record_id"]), reverse=True)
        page = _paged_payload(items[offset : offset + limit], len(items), limit, offset)
        return {"items": page["items"], "total": page["total"], "limit": page["limit"], "offset": page["offset"]}

    async def _carbon_ledger_page(
        self,
        db_session: AsyncSession,
        scope_filter: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        items = [
            {
                "record_type": item["record_type"],
                "record_label": item["record_label"],
                "record_id": item["row"].id,
                "scope": item["scope"],
                "display_name": item["display_name"],
                "period": item["period"],
                "status": item["data"].get("status"),
                "source_kind": item["data"].get("source_kind"),
                "activity_amount": item["data"].get("activity_amount"),
                "activity_unit": item["data"].get("activity_unit"),
                "computed_co2e": item["data"].get("computed_co2e"),
                "factor_source": item["data"].get("factor_source"),
                "factor_year": item["data"].get("factor_year"),
            }
            for item in records
        ]
        if scope_filter:
            items = [item for item in items if item["scope"] == scope_filter]
        if status:
            items = [item for item in items if item["status"] == status]
        items.sort(key=lambda item: (_sort_month_key(item.get("period")), item["record_id"]), reverse=True)
        page = _paged_payload(items[offset : offset + limit], len(items), limit, offset)
        return {"items": page["items"], "total": page["total"], "limit": page["limit"], "offset": page["offset"]}

    def _build_alert_facets(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        by_source: dict[str, int] = defaultdict(int)
        by_severity: dict[str, int] = defaultdict(int)
        by_status: dict[str, int] = defaultdict(int)
        by_area: dict[str, int] = defaultdict(int)
        for item in items:
            by_source[str(item["source"])] += 1
            by_severity[str(item["severity"])] += 1
            by_status[str(item["status"])] += 1
            by_area[str(item.get("area_name") or "未分区")] += 1
        return {
            "by_source": [{"name": name, "value": value} for name, value in sorted(by_source.items(), key=lambda pair: pair[1], reverse=True)],
            "by_severity": [{"name": name, "value": value} for name, value in sorted(by_severity.items(), key=lambda pair: pair[1], reverse=True)],
            "by_status": [{"name": name, "value": value} for name, value in sorted(by_status.items(), key=lambda pair: pair[1], reverse=True)],
            "by_area": [{"name": name, "value": value} for name, value in sorted(by_area.items(), key=lambda pair: pair[1], reverse=True)[:10]],
        }

    def _build_alert_trend(self, items: list[dict[str, Any]], months: int = 12) -> list[dict[str, Any]]:
        current_month = datetime.date.today().replace(day=1)
        month_labels = []
        for offset in range(months - 1, -1, -1):
            month = current_month - relativedelta(months=offset)
            month_labels.append(month.strftime("%Y-%m"))
        counts = {label: {"period": label, "alerts_count": 0, "handled_count": 0} for label in month_labels}
        for item in items:
            occurred_at = item.get("occurred_at")
            month_key = str(occurred_at or "")[:7]
            if month_key in counts:
                counts[month_key]["alerts_count"] += 1
                if item.get("status") == "已处理":
                    counts[month_key]["handled_count"] += 1
        return list(counts.values())

    async def _build_dashboard_completion(self, db_session: AsyncSession) -> dict[str, Any]:
        scope_records = await CarbonAnalyticsController._load_scope_records(db_session)
        issues = await self._build_quality_issues(db_session)
        alerts = await self._build_unified_alerts(db_session)
        total_records = max(len(scope_records), 1)
        issue_impacts = {
            (
                str(item.get("record_type") or item.get("module") or "unknown"),
                str(item.get("record_id") or item.get("period") or item["id"]),
            )
            for item in issues
            if item.get("severity") != "low"
        }
        return {
            "carbon_completion_rate": round(sum(1 for item in scope_records if item["data"].get("computed_co2e")) / total_records * 100, 1),
            "approval_completion_rate": round(sum(1 for item in scope_records if item["data"].get("status") == STATUS_APPROVED) / total_records * 100, 1),
            "quality_completion_rate": round(max(0.0, 100 - (len(issue_impacts) / total_records * 100)), 1),
            "alert_closure_rate": round(sum(1 for item in alerts if item["status"] == "已处理") / max(len(alerts), 1) * 100, 1),
        }

    async def _build_recent_activities(self, db_session: AsyncSession) -> list[dict[str, Any]]:
        alerts = await self._build_unified_alerts(db_session)
        scope_records = await CarbonAnalyticsController._load_scope_records(db_session)
        activities: list[dict[str, Any]] = []
        for item in alerts[:6]:
            activities.append(
                {
                    "type": "alert",
                    "title": item["title"],
                    "subtitle": item.get("area_name") or item.get("object_name") or "监测对象",
                    "time": item.get("occurred_at"),
                    "status": item.get("status"),
                }
            )
        for item in scope_records[:6]:
            activities.append(
                {
                    "type": "carbon",
                    "title": item["display_name"],
                    "subtitle": f"{item['record_label']} · {item['period']}",
                    "time": item["period"],
                    "status": item["data"].get("status"),
                }
            )
        activities.sort(key=lambda row: str(row.get("time") or ""), reverse=True)
        return activities[:10]

    def _build_carbon_scope_trend(self, records: list[dict[str, Any]], months: int = 12) -> list[dict[str, Any]]:
        latest_month = None
        month_keys = [item.get("period") for item in records if item.get("period")]
        if month_keys:
            latest_month = max(month_keys)
        if not latest_month:
            latest_month = datetime.date.today().strftime("%Y-%m")
        labels = _months_back(latest_month, months)
        series = {
            label: {
                "period": label,
                "scope1_co2e": 0.0,
                "scope2_co2e": 0.0,
                "scope3_co2e": 0.0,
                "carbon_co2e": 0.0,
            }
            for label in labels
        }
        for item in records:
            period = item.get("period")
            if period not in series:
                continue
            value = float(item["data"].get("computed_co2e") or 0.0)
            key = _scope_trend_key(str(item.get("scope") or ""))
            if key in series[period]:
                series[period][key] += value
                series[period]["carbon_co2e"] += value
        return list(series.values())

    def _build_carbon_flow(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        nodes: dict[str, dict[str, Any]] = {
            "scope1": {"id": "scope1", "name": "范围1", "category": "scope"},
            "scope2": {"id": "scope2", "name": "范围2", "category": "scope"},
            "scope3": {"id": "scope3", "name": "范围3", "category": "scope"},
        }
        links: list[dict[str, Any]] = []
        grouped: dict[tuple[str, str], float] = defaultdict(float)
        for item in records:
            scope = item["scope"]
            scope_node = "scope1" if scope == "范围1" else "scope2" if scope == "范围2" else "scope3"
            source_kind = str(item["data"].get("source_kind") or item["record_label"])
            result_name = f"{item['record_label']}结果"
            source_node = f"src:{scope}:{source_kind}"
            result_node = f"res:{scope}:{item['record_type']}"
            value = float(item["data"].get("computed_co2e") or 0.0)
            nodes.setdefault(source_node, {"id": source_node, "name": _source_kind_label(source_kind), "category": "source"})
            nodes.setdefault(result_node, {"id": result_node, "name": result_name, "category": "result"})
            grouped[(scope_node, source_node)] += value
            grouped[(source_node, result_node)] += value
        for (source, target), value in grouped.items():
            if value <= 0:
                continue
            links.append({"source": source, "target": target, "value": round(value, 2)})
        return {"title": "碳流图", "unit": "kgCO2e", "nodes": list(nodes.values()), "links": links}

    def _build_quality_trend(self, issues: list[dict[str, Any]], months: int = 12) -> list[dict[str, Any]]:
        current_month = datetime.date.today().replace(day=1)
        labels = [(current_month - relativedelta(months=offset)).strftime("%Y-%m") for offset in range(months - 1, -1, -1)]
        buckets = {label: {"period": label, "alerts_count": 0, "handled_count": 0, "energy_kwh": 0.0, "carbon_co2e": 0.0} for label in labels}
        for item in issues:
            month_key = str(item.get("period") or "")[:7]
            if month_key in buckets:
                buckets[month_key]["alerts_count"] += 1
                if item.get("severity") != "high":
                    buckets[month_key]["handled_count"] += 1
        return list(buckets.values())

    def _build_factor_usage(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        by_scope: dict[str, int] = defaultdict(int)
        missing_by_scope: dict[str, int] = defaultdict(int)
        by_source: dict[str, int] = defaultdict(int)
        for item in records:
            by_scope[item["scope"]] += 1
            factor_source = str(item["data"].get("factor_source") or "缺失因子")
            by_source[factor_source] += 1
            if not item["data"].get("factor_source"):
                missing_by_scope[item["scope"]] += 1
        return {
            "scope_distribution": [{"name": name, "value": value} for name, value in sorted(by_scope.items())],
            "missing_by_scope": [{"name": name, "value": value} for name, value in sorted(missing_by_scope.items())],
            "factor_source_distribution": [{"name": name, "value": value} for name, value in sorted(by_source.items(), key=lambda pair: pair[1], reverse=True)[:10]],
        }

    @get("/api/energy-carbon/dashboard/overview")
    async def get_dashboard_overview(self, db_session: AsyncSession) -> Response[dict]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session)
        energy_series = await CarbonAnalyticsController._build_energy_series(db_session, _months_back(latest_month, 1) if latest_month else [])
        current_energy = energy_series[-1] if energy_series else {"energy_kwh": 0.0, "carbon_co2e": 0.0, "source_kind": "empty", "record_count": 0}
        enterprise = await db_session.scalar(select(m.EnterpriseInfo).limit(1))
        scope_records = await CarbonAnalyticsController._load_scope_records(db_session)
        alerts = await self._build_unified_alerts(db_session)
        issues = await self._build_quality_issues(db_session)
        health = await self._build_monitor_area_summary(db_session)
        risk_items = [item for item in alerts if item["severity"] == "high" and item["status"] == "待处理"][:5]
        issue_impacts = {
            (
                str(item.get("record_type") or item.get("module") or "unknown"),
                str(item.get("record_id") or item.get("period") or item["id"]),
            )
            for item in issues
            if item.get("severity") != "low"
        }
        quality_rate = round(max(0.0, 100 - (len(issue_impacts) / max(len(scope_records), 1) * 100)), 1)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": latest_month,
                    "enterprise": enterprise.to_dict() if enterprise else {},
                    "kpis": [
                        {"id": "energy", "label": "总能耗", "value": round(float(current_energy.get("energy_kwh") or 0.0), 2), "unit": "kWh"},
                        {"id": "carbon", "label": "总碳排", "value": round(sum(float(item["data"].get("computed_co2e") or 0.0) for item in scope_records), 2), "unit": "kgCO2e"},
                        {"id": "alerts", "label": "异常数", "value": len(alerts), "unit": "条"},
                        {"id": "unhandled", "label": "未处理告警", "value": sum(1 for item in alerts if item["status"] == "待处理"), "unit": "条"},
                        {"id": "pending", "label": "待审核", "value": sum(1 for item in scope_records if item["data"].get("status") == STATUS_PENDING), "unit": "条"},
                        {"id": "quality", "label": "数据完整率", "value": quality_rate, "unit": "%"},
                    ],
                    "trend_summary": {
                        "source_kind": current_energy.get("source_kind"),
                        "data_origin": _data_origin_for_source_kind(current_energy.get("source_kind")),
                        "energy_kwh": round(float(current_energy.get("energy_kwh") or 0.0), 2),
                        "carbon_co2e": round(float(current_energy.get("carbon_co2e") or 0.0), 2),
                    },
                    "risk_items": risk_items,
                    "todo_items": [
                        {"label": "待处理告警", "value": sum(1 for item in alerts if item["status"] == "待处理")},
                        {"label": "待审核记录", "value": sum(1 for item in scope_records if item["data"].get("status") == STATUS_PENDING)},
                        {"label": "质量问题", "value": len(issues)},
                    ],
                    "health_matrix": health[:6],
                    "completion": await self._build_dashboard_completion(db_session),
                    "recent_activities": await self._build_recent_activities(db_session),
                    "quick_links": [
                        {"label": "监测中心", "to": "/energy-carbon/monitor"},
                        {"label": "告警中心", "to": "/energy-carbon/alerts"},
                        {"label": "碳盘查", "to": "/energy-carbon/carbon"},
                        {"label": "能流分析", "to": "/energy-carbon/flows"},
                        {"label": "数据质量", "to": "/energy-carbon/quality"},
                        {"label": "因子数据库", "to": "/energy-carbon/factors"},
                    ],
                },
            }
        )

    @get("/api/energy-carbon/dashboard/completion")
    async def get_dashboard_completion(self, db_session: AsyncSession) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": await self._build_dashboard_completion(db_session)})

    @get("/api/energy-carbon/dashboard/recent-activities")
    async def get_dashboard_recent_activities(self, db_session: AsyncSession) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": await self._build_recent_activities(db_session)}})

    @get("/api/energy-carbon/dashboard/trend")
    async def get_dashboard_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": await self._trend_data(db_session, months)})

    @get("/api/energy-carbon/dashboard/health")
    async def get_dashboard_health(self, db_session: AsyncSession) -> Response[dict]:
        health = await self._build_monitor_area_summary(db_session)
        alerts = await self._build_unified_alerts(db_session)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "areas": health,
                    "summary": {
                        "area_count": len(health),
                        "stable_count": sum(1 for item in health if item["status"] == "稳定"),
                        "risk_count": sum(1 for item in health if item["status"] != "稳定"),
                        "high_alert_count": sum(1 for item in alerts if item["severity"] == "high" and item["status"] == "待处理"),
                    },
                },
            }
        )

    @get("/api/energy-carbon/energy/summary")
    async def get_energy_summary(self, db_session: AsyncSession) -> Response[dict]:
        ranking = await self._ranking_data(db_session)
        efficiency = await self._efficiency_data(db_session)
        latest_month = ranking.get("latest_month")
        ledger = await self._energy_ledger_page(db_session, latest_month, None, 12, 0)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": latest_month,
                    "energy_by_area": ranking.get("energy_by_area", []),
                    "alerts_by_area": ranking.get("alerts_by_area", []),
                    "carbon_by_type": ranking.get("carbon_by_type", []),
                    "source_mix": efficiency.get("source_mix", []),
                    "energy_efficiency": efficiency.get("energy_efficiency", {}),
                    "workflow": efficiency.get("workflow", []),
                    "diagnostics": ranking.get("diagnostics", []),
                    "ledger": ledger.get("items", []),
                },
            }
        )

    @get("/api/energy-carbon/energy/trend")
    async def get_energy_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": await self._trend_data(db_session, months)})

    @get("/api/energy-carbon/energy/structure")
    async def get_energy_structure(self, db_session: AsyncSession) -> Response[dict]:
        ranking = await self._ranking_data(db_session)
        efficiency = await self._efficiency_data(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"source_mix": efficiency.get("source_mix", []), "energy_by_area": ranking.get("energy_by_area", []), "alerts_by_area": ranking.get("alerts_by_area", [])}})

    @get("/api/energy-carbon/energy/intensity")
    async def get_energy_intensity(self, db_session: AsyncSession) -> Response[dict]:
        latest_month = await CarbonAnalyticsController._latest_energy_month(db_session)
        energy_series = await CarbonAnalyticsController._build_energy_series(db_session, [latest_month] if latest_month else [])
        current_energy = energy_series[0] if energy_series else {"energy_kwh": 0.0}
        enterprise = await db_session.scalar(select(m.EnterpriseInfo).limit(1))
        total_kwh = float(current_energy.get("energy_kwh") or 0.0)
        store_area = float(enterprise.store_area or 0.0) if enterprise else 0.0
        park_area = float(enterprise.park_area or 0.0) if enterprise else 0.0
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": latest_month,
                    "metrics": [
                        {"label": "总用电量", "value": round(total_kwh, 2), "unit": "kWh"},
                        {"label": "单位仓储面积能耗", "value": round(total_kwh / store_area, 4) if store_area else None, "unit": "kWh/㎡"},
                        {"label": "单位园区面积能耗", "value": round(total_kwh / park_area, 4) if park_area else None, "unit": "kWh/㎡"},
                    ],
                },
            }
        )

    @get("/api/energy-carbon/energy/ranking")
    async def get_energy_ranking(self, db_session: AsyncSession) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": await self._ranking_data(db_session)})

    @get("/api/energy-carbon/energy/ledger-preview")
    async def get_energy_ledger_preview(
        self,
        db_session: AsyncSession,
        billing_month: str | None = None,
        source_kind: str | None = None,
        limit: int = 12,
        offset: int = 0,
    ) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": await self._energy_ledger_page(db_session, billing_month, source_kind, limit, offset)})

    @get("/api/energy-carbon/energy/diagnostics")
    async def get_energy_diagnostics(self, db_session: AsyncSession) -> Response[dict]:
        ranking = await self._ranking_data(db_session)
        efficiency = await self._efficiency_data(db_session)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "latest_month": ranking.get("latest_month"),
                    "diagnostics": ranking.get("diagnostics", []),
                    "workflow": efficiency.get("workflow", []),
                    "storage": efficiency.get("storage", {}),
                },
            }
        )

    @get("/api/energy-carbon/monitor/areas")
    async def list_monitor_areas(self, db_session: AsyncSession) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": await self._build_monitor_area_summary(db_session)}})

    @get("/api/energy-carbon/monitor/devices")
    async def list_monitor_devices(
        self,
        db_session: AsyncSession,
        sector_id: int | None = None,
        status: int | None = None,
        category: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Response[dict]:
        stmt = select(m.MonitorEquipment).options(selectinload(m.MonitorEquipment.sector)).order_by(m.MonitorEquipment.sort_index.asc().nullslast(), m.MonitorEquipment.id.desc())
        if sector_id:
            stmt = stmt.where(m.MonitorEquipment.sector_id == sector_id)
        if status is not None:
            stmt = stmt.where(m.MonitorEquipment.status == status)
        if category is not None:
            stmt = stmt.where(m.MonitorEquipment.category == category)
        rows = (await db_session.execute(stmt.offset(offset).limit(limit))).scalars().all()
        items = []
        for row in rows:
            alert_count = int(
                (
                    await db_session.execute(select(func.count(m.AlarmEvent.id)).where(m.AlarmEvent.equipment_id == row.id, m.AlarmEvent.is_handle.is_(False)))
                ).scalar_one()
            )
            items.append(
                {
                    "id": row.id,
                    "name": row.name or row.code,
                    "code": row.code,
                    "category": row.category,
                    "sector_id": row.sector_id,
                    "sector_name": row.sector.name if row.sector else None,
                    "status": row.status,
                    "trip_state": row.trip_state,
                    "location": row.location,
                    "protocol": row.protocol,
                    "alert_unhandled": alert_count,
                }
            )
        total_stmt = select(func.count()).select_from(m.MonitorEquipment)
        if sector_id:
            total_stmt = total_stmt.where(m.MonitorEquipment.sector_id == sector_id)
        if status is not None:
            total_stmt = total_stmt.where(m.MonitorEquipment.status == status)
        if category is not None:
            total_stmt = total_stmt.where(m.MonitorEquipment.category == category)
        total = int((await db_session.execute(total_stmt)).scalar_one())
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": items, "total": total, "limit": limit, "offset": offset}})

    @get("/api/energy-carbon/monitor/devices/{device_id:int}")
    async def get_monitor_device_detail(self, db_session: AsyncSession, device_id: int) -> Response[dict]:
        device = (
            await db_session.execute(select(m.MonitorEquipment).options(selectinload(m.MonitorEquipment.sector)).where(m.MonitorEquipment.id == device_id))
        ).scalars().first()
        if not device:
            return Response(content={"code": 404, "msg": "设备不存在"}, status_code=404)
        meter_samples = (
            await db_session.execute(select(m.AmmeterIndexValue).where(m.AmmeterIndexValue.equipment_id == device_id).order_by(m.AmmeterIndexValue.reading_time.desc().nullslast()).limit(12))
        ).scalars().all()
        alarms = (
            await db_session.execute(select(m.AlarmEvent).where(m.AlarmEvent.equipment_id == device_id).order_by(m.AlarmEvent.event_time.desc().nullslast()).limit(10))
        ).scalars().all()
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "device": {
                        "id": device.id,
                        "name": device.name or device.code,
                        "code": device.code,
                        "category": device.category,
                        "status": device.status,
                        "trip_state": device.trip_state,
                        "sector_name": device.sector.name if device.sector else None,
                        "location": device.location,
                        "protocol": device.protocol,
                        "install_time": device.install_time.isoformat() if device.install_time else None,
                    },
                    "meter_samples": [model_to_dict(item) for item in meter_samples],
                    "alerts": [model_to_dict(item) for item in alarms],
                },
            }
        )

    @get("/api/energy-carbon/monitor/devices/{device_id:int}/timeseries")
    async def get_monitor_device_timeseries(self, db_session: AsyncSession, device_id: int) -> Response[dict]:
        samples = (
            await db_session.execute(
                select(m.AmmeterIndexValue).where(m.AmmeterIndexValue.equipment_id == device_id).order_by(m.AmmeterIndexValue.reading_time.asc().nullslast()).limit(48)
            )
        ).scalars().all()
        points = [
            {
                "period": item.reading_time.strftime("%m-%d %H:%M") if item.reading_time else f"样本{index + 1}",
                "energy_kwh": float(item.zygdn or item.zygdnsz or 0.0),
                "carbon_co2e": 0.0,
            }
            for index, item in enumerate(samples)
        ]
        return Response(content={"code": 200, "msg": "获取成功", "data": {"series": points}})

    @get("/api/energy-carbon/monitor/devices/{device_id:int}/alerts")
    async def get_monitor_device_alerts(self, db_session: AsyncSession, device_id: int) -> Response[dict]:
        alarms = (
            await db_session.execute(select(m.AlarmEvent).where(m.AlarmEvent.equipment_id == device_id).order_by(m.AlarmEvent.event_time.desc().nullslast()).limit(20))
        ).scalars().all()
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": [model_to_dict(item) for item in alarms]}})

    @get("/api/energy-carbon/monitor/devices/{device_id:int}/videos")
    async def get_monitor_device_videos(self, db_session: AsyncSession, device_id: int) -> Response[dict]:
        device = await db_session.scalar(select(m.MonitorEquipment).where(m.MonitorEquipment.id == device_id))
        if not device or not device.sector_id:
            return Response(content={"code": 200, "msg": "获取成功", "data": {"items": []}})
        sector_name = await db_session.scalar(select(m.MonitorSector.name).where(m.MonitorSector.id == device.sector_id))
        if not sector_name:
            return Response(content={"code": 200, "msg": "获取成功", "data": {"items": []}})
        videos = (
            await db_session.execute(select(m.VideoMonitor).where(m.VideoMonitor.f_area == sector_name).limit(8))
        ).scalars().all()
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": [model_to_dict(item) for item in videos]}})

    @get("/api/energy-carbon/alerts")
    async def list_energy_center_alerts(
        self,
        db_session: AsyncSession,
        source: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        items = await self._build_unified_alerts(db_session)
        if source and source != "all":
            items = [item for item in items if item["source"] == source]
        if status and status != "all":
            items = [item for item in items if item["status"] == status]
        if severity and severity != "all":
            items = [item for item in items if item["severity"] == severity]
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": items[offset : offset + limit], "total": len(items), "limit": limit, "offset": offset}})

    @get("/api/energy-carbon/alerts/summary")
    async def get_energy_center_alert_summary(self, db_session: AsyncSession) -> Response[dict]:
        items = await self._build_unified_alerts(db_session)
        facets = self._build_alert_facets(items)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "total": len(items),
                    "unhandled": sum(1 for item in items if item["status"] == "待处理"),
                    "high_risk": sum(1 for item in items if item["severity"] == "high"),
                    "today_added": sum(1 for item in items if str(item.get("occurred_at") or "").startswith(datetime.date.today().isoformat())),
                    "avg_handle_hours": None,
                    **facets,
                },
            }
        )

    @get("/api/energy-carbon/alerts/facets")
    async def get_energy_center_alert_facets(self, db_session: AsyncSession) -> Response[dict]:
        items = await self._build_unified_alerts(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": self._build_alert_facets(items)})

    @get("/api/energy-carbon/alerts/trend")
    async def get_energy_center_alert_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict]:
        items = await self._build_unified_alerts(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"series": self._build_alert_trend(items, months)}})

    @get("/api/energy-carbon/alerts/{alert_id:str}")
    async def get_energy_center_alert_detail(self, db_session: AsyncSession, alert_id: str) -> Response[dict]:
        items = await self._build_unified_alerts(db_session)
        match = next((item for item in items if item["id"] == alert_id), None)
        if not match:
            return Response(content={"code": 404, "msg": "告警不存在"}, status_code=404)
        history = [
            {"label": "发生", "value": match.get("occurred_at")},
            {"label": "当前状态", "value": match.get("status")},
            {"label": "风险等级", "value": match.get("severity")},
        ]
        return Response(content={"code": 200, "msg": "获取成功", "data": {**match, "history": history}})

    @get("/api/energy-carbon/alerts/{alert_id:str}/history")
    async def get_energy_center_alert_history(self, db_session: AsyncSession, alert_id: str) -> Response[dict]:
        items = await self._build_unified_alerts(db_session)
        match = next((item for item in items if item["id"] == alert_id), None)
        if not match:
            return Response(content={"code": 404, "msg": "告警不存在"}, status_code=404)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": [{"stage": "发现", "time": match.get("occurred_at"), "status": match.get("status")}]}})

    @get("/api/energy-carbon/flows/energy")
    async def get_energy_center_flow(self, db_session: AsyncSession, billing_month: str | None = None) -> Response[dict]:
        return Response(content={"code": 200, "msg": "获取成功", "data": await self._energy_flow_data(db_session, billing_month)})

    @get("/api/energy-carbon/flows/energy-balance")
    async def get_energy_balance(self, db_session: AsyncSession, billing_month: str | None = None) -> Response[dict]:
        month = billing_month or await CarbonAnalyticsController._latest_energy_month(db_session)
        if not month:
            return Response(content={"code": 200, "msg": "暂无数据", "data": {"billing_month": None, "table": [], "diagnostics": []}})
        flow = await self._energy_flow_data(db_session, month)
        total_input = float(flow.get("diagnostics", {}).get("total_energy_kwh") or 0.0)
        ready_rows = (
            await db_session.execute(
                select(m.Scope2MeterAggregate).where(m.Scope2MeterAggregate.billing_month == month, m.Scope2MeterAggregate.calc_status == "ready")
            )
        ).scalars().all()
        invalid_rows = (
            await db_session.execute(
                select(m.Scope2MeterAggregate).where(m.Scope2MeterAggregate.billing_month == month, m.Scope2MeterAggregate.calc_status != "ready")
            )
        ).scalars().all()
        distributed = round(sum(float(row.total_kwh or 0.0) for row in ready_rows), 2)
        losses = round(max(total_input - distributed, 0.0), 2)
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "billing_month": month,
                    "table": [
                        {"label": "输入", "value": round(total_input, 2), "unit": "kWh"},
                        {"label": "已聚合利用", "value": distributed, "unit": "kWh"},
                        {"label": "损耗/缺失", "value": losses, "unit": "kWh"},
                    ],
                    "diagnostics": [
                        {"label": "可核算电表数", "value": len(ready_rows)},
                        {"label": "不可核算电表数", "value": len(invalid_rows)},
                        {"label": "正向能耗区域", "value": flow.get("diagnostics", {}).get("positive_area_count", 0)},
                        {"label": "零增量区域", "value": flow.get("diagnostics", {}).get("zero_ready_count", 0)},
                        {"label": "历史估算点位", "value": flow.get("diagnostics", {}).get("estimated_count", 0)},
                        {"label": "历史估算电量", "value": f"{flow.get('diagnostics', {}).get('estimated_energy_kwh', 0)} kWh"},
                        {"label": "回退来源", "value": "是" if flow.get("diagnostics", {}).get("used_fallback") else "否"},
                    ],
                },
            }
        )

    @get("/api/energy-carbon/flows/energy-diagnostics")
    async def get_energy_flow_diagnostics(self, db_session: AsyncSession, billing_month: str | None = None) -> Response[dict]:
        flow = await self._energy_flow_data(db_session, billing_month)
        return Response(content={"code": 200, "msg": "获取成功", "data": flow.get("diagnostics", {})})

    @get("/api/energy-carbon/flows/energy-top-links")
    async def get_energy_flow_top_links(self, db_session: AsyncSession, billing_month: str | None = None) -> Response[dict]:
        flow = await self._energy_flow_data(db_session, billing_month)
        node_map = {item["id"]: item["name"] for item in flow.get("nodes", [])}
        top_links = [
            {**item, "source": node_map.get(item["source"], item["source"]), "target": node_map.get(item["target"], item["target"])}
            for item in sorted(flow.get("links", []), key=lambda item: item["value"], reverse=True)[:10]
        ]
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": top_links}})

    @get("/api/energy-carbon/carbon/records")
    async def list_energy_center_carbon_records(
        self,
        db_session: AsyncSession,
        scope_filter: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Response[dict]:
        ledger = await self._carbon_ledger_page(db_session, scope_filter, status, limit, offset)
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        summary = {
            "total": len(records),
            "pending": sum(1 for item in records if item["data"].get("status") == STATUS_PENDING),
            "approved": sum(1 for item in records if item["data"].get("status") == STATUS_APPROVED),
            "missing_factor": sum(1 for item in records if not item["data"].get("factor_source")),
            "missing_result": sum(1 for item in records if item["data"].get("computed_co2e") is None),
            "rejected": sum(1 for item in records if item["data"].get("status") == STATUS_REJECTED),
        }
        return Response(content={"code": 200, "msg": "获取成功", "data": {**ledger, "summary": summary}})

    @get("/api/energy-carbon/carbon/summary")
    async def get_energy_center_carbon_summary(self, db_session: AsyncSession) -> Response[dict]:
        ledger = await self._carbon_ledger_page(db_session, None, None, 500, 0)
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        usage = self._build_factor_usage(records)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"summary": ledger.get("items", []), "usage": usage, "totals": ledger.get("total", 0)}})

    @get("/api/energy-carbon/carbon/records/{record_type:str}/{record_id:int}")
    async def get_energy_center_carbon_record(self, db_session: AsyncSession, record_type: str, record_id: int) -> Response[dict]:
        detail = await self._get_record_detail(db_session, record_type, record_id)
        if not detail:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        return Response(content={"code": 200, "msg": "获取成功", "data": detail})

    @get("/api/energy-carbon/carbon/pending")
    async def list_energy_center_pending(self, db_session: AsyncSession, limit: int = 20, offset: int = 0) -> Response[dict]:
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        pending_items = [
            {
                "record_type": item["record_type"],
                "record_label": item["record_label"],
                "record_id": item["row"].id,
                "scope": item["scope"],
                "display_name": item["display_name"],
                "period": item["period"],
                "status": item["data"].get("status"),
                "factor_source": item["data"].get("factor_source"),
                "computed_co2e": item["data"].get("computed_co2e"),
            }
            for item in records
            if item["data"].get("status") == STATUS_PENDING
        ]
        pending_items.sort(key=lambda item: (_sort_month_key(item.get("period")), item["record_id"]), reverse=True)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": pending_items[offset : offset + limit], "total": len(pending_items), "limit": limit, "offset": offset}})

    @get("/api/energy-carbon/carbon/trend")
    async def get_energy_center_carbon_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict]:
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"series": self._build_carbon_scope_trend(records, months)}})

    @get("/api/energy-carbon/carbon/flow")
    async def get_energy_center_carbon_flow(self, db_session: AsyncSession) -> Response[dict]:
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": self._build_carbon_flow(records)})

    @get("/api/energy-carbon/carbon/evidence/{record_type:str}/{record_id:int}")
    async def get_energy_center_carbon_evidence(self, db_session: AsyncSession, record_type: str, record_id: int) -> Response[dict]:
        detail = await self._get_record_detail(db_session, record_type, record_id)
        if not detail:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        source = detail.get("source", {})
        attachments = []
        if isinstance(source, dict) and source.get("attachment"):
            attachments.append({"label": "业务附件", "path": source.get("attachment")})
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": attachments}})

    @get("/api/energy-carbon/quality/issues")
    async def list_quality_issues(
        self,
        db_session: AsyncSession,
        issue_type: str | None = None,
        severity: str | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> Response[dict]:
        items = await self._build_quality_issues(db_session)
        if issue_type and issue_type != "all":
            items = [item for item in items if item["issue_type"] == issue_type]
        if severity and severity != "all":
            items = [item for item in items if item["severity"] == severity]
        summary: dict[str, int] = defaultdict(int)
        for item in items:
            summary[item["issue_type"]] += 1
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": items[offset : offset + limit], "total": len(items), "limit": limit, "offset": offset, "summary": summary}})

    @get("/api/energy-carbon/quality/summary")
    async def get_quality_summary(self, db_session: AsyncSession) -> Response[dict]:
        issues = await self._build_quality_issues(db_session)
        summary: dict[str, int] = defaultdict(int)
        by_module: dict[str, int] = defaultdict(int)
        for item in issues:
            summary[item["issue_type"]] += 1
            by_module[item["module"]] += 1
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "summary": summary,
                    "by_module": [{"name": name, "value": value} for name, value in sorted(by_module.items(), key=lambda pair: pair[1], reverse=True)],
                },
            }
        )

    @get("/api/energy-carbon/quality/trend")
    async def get_quality_trend(self, db_session: AsyncSession, months: int = 12) -> Response[dict]:
        issues = await self._build_quality_issues(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": {"series": self._build_quality_trend(issues, months)}})

    @get("/api/energy-carbon/quality/impact-ranking")
    async def get_quality_impact_ranking(self, db_session: AsyncSession) -> Response[dict]:
        issues = await self._build_quality_issues(db_session)
        by_module: dict[str, int] = defaultdict(int)
        for item in issues:
            by_module[item["module"]] += 1
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": [{"name": name, "value": value} for name, value in sorted(by_module.items(), key=lambda pair: pair[1], reverse=True)]}})

    @get("/api/energy-carbon/trace/{record_type:str}/{record_id:int}")
    async def get_trace(self, db_session: AsyncSession, record_type: str, record_id: int) -> Response[dict]:
        detail = await self._get_record_detail(db_session, record_type, record_id)
        if not detail:
            return Response(content={"code": 404, "msg": "记录不存在"}, status_code=404)
        trace = [
            {"step": "采集/录入", "summary": detail["record_label"], "detail": detail["source"]},
            {"step": "核算", "summary": "活动量、因子与结果", "detail": detail["computation"]},
            {"step": "审核", "summary": f"{len(detail['audit_logs'])} 条审核日志", "detail": detail["audit_logs"]},
        ]
        return Response(content={"code": 200, "msg": "获取成功", "data": {"trace": trace, **detail}})

    @get("/api/energy-carbon/factors")
    async def list_energy_center_factors(
        self,
        db_session: AsyncSession,
        limit: int = 20,
        offset: int = 0,
        scope_filter: str | None = None,
    ) -> Response[dict]:
        stmt = select(m.EmissionFactor).order_by(m.EmissionFactor.year.desc(), m.EmissionFactor.id.desc())
        count_stmt = select(func.count()).select_from(m.EmissionFactor)
        if scope_filter:
            stmt = stmt.where(m.EmissionFactor.scope == scope_filter)
            count_stmt = count_stmt.where(m.EmissionFactor.scope == scope_filter)
        items = (await db_session.execute(stmt.offset(offset).limit(limit))).scalars().all()
        total = int((await db_session.execute(count_stmt)).scalar_one())
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": [model_to_dict(item) for item in items], "total": total, "limit": limit, "offset": offset}})

    @get("/api/energy-carbon/factors/stats")
    async def get_energy_center_factor_stats(self, db_session: AsyncSession) -> Response[dict]:
        emission_total = int((await db_session.execute(select(func.count()).select_from(m.EmissionFactor))).scalar_one())
        active_total = int((await db_session.execute(select(func.count()).select_from(m.EmissionFactor).where(m.EmissionFactor.is_active.is_(True)))).scalar_one())
        library_total = int((await db_session.execute(select(func.count()).select_from(m.CarbonFactorLibrary))).scalar_one())
        raw_total = int((await db_session.execute(select(func.count()).select_from(m.CarbonFactorRawRecord))).scalar_one())
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        missing_factor_total = sum(1 for item in records if not item["data"].get("factor_source"))
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "emission_total": emission_total,
                    "active_total": active_total,
                    "library_total": library_total,
                    "raw_total": raw_total,
                    "used_total": len(records) - missing_factor_total,
                    "missing_factor_total": missing_factor_total,
                },
            }
        )

    @get("/api/energy-carbon/factors/usage")
    async def get_energy_center_factor_usage(self, db_session: AsyncSession) -> Response[dict]:
        records = await CarbonAnalyticsController._load_scope_records(db_session)
        return Response(content={"code": 200, "msg": "获取成功", "data": self._build_factor_usage(records)})

    @get("/api/energy-carbon/factors/categories")
    async def get_energy_center_factor_categories(self, db_session: AsyncSession) -> Response[dict]:
        rows = (
            await db_session.execute(select(m.EmissionFactor.scope, m.EmissionFactor.category, func.count(m.EmissionFactor.id)).group_by(m.EmissionFactor.scope, m.EmissionFactor.category))
        ).all()
        return Response(
            content={
                "code": 200,
                "msg": "获取成功",
                "data": {
                    "items": [{"scope": scope, "category": category, "value": int(total)} for scope, category, total in rows],
                },
            }
        )

    @post("/api/energy-carbon/admin/backfill/raw-meter-history", guards=[requires_superuser])
    async def admin_backfill_raw_meter_history(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        start_month = str(data.get("start_month")).strip() if data.get("start_month") not in (None, "") else None
        end_month = str(data.get("end_month")).strip() if data.get("end_month") not in (None, "") else None
        raw_start_month, raw_end_month = await CarbonAnalyticsController._raw_history_month_range(db_session)
        effective_start = start_month or raw_start_month
        effective_end = end_month or raw_end_month
        if not effective_start or not effective_end:
            return Response(content={"code": 200, "msg": "暂无原始电表历史数据", "data": {"months": []}})
        month_keys = _month_span(effective_start, effective_end)
        result = await self._impute_raw_scope2_history(db_session, scope2_meter_aggregate_service, month_keys)
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.scope2.backfill-raw-history",
            target_type="scope2_meter_aggregate",
            details={"query_scope": {"start_month": effective_start, "end_month": effective_end}, "batch_size": len(month_keys)},
        )
        return Response(content={"code": 200, "msg": "原始电表历史补全完成", "data": result})

    @post("/api/energy-carbon/admin/backfill/scope2", guards=[requires_superuser])
    async def admin_backfill_scope2(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        scope2_meter_aggregate_service: services.Scope2MeterAggregateService,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        months = int(data.get("months") or 12)
        area_id = str(data.get("area_id")).strip() if data.get("area_id") not in (None, "") else None
        month_keys = await CarbonAnalyticsController._recent_scope2_backfill_months(db_session, months)
        rebuilt_count = 0
        ready_count = 0
        invalid_count = 0
        details: list[dict[str, Any]] = []
        for billing_month in month_keys:
            rows = await CarbonAccountingController._rebuild_scope2_meter_aggregates(self, db_session, scope2_meter_aggregate_service, billing_month, area_id)
            rebuilt_count += len(rows)
            ready_month = sum(1 for row in rows if row.calc_status == "ready")
            invalid_month = len(rows) - ready_month
            ready_count += ready_month
            invalid_count += invalid_month
            details.append(
                {
                    "billing_month": billing_month,
                    "rebuilt_count": len(rows),
                    "ready_count": ready_month,
                    "invalid_count": invalid_month,
                }
            )
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.scope2.backfill",
            target_type="scope2_meter_aggregate",
            details={"batch_size": len(month_keys), "query_scope": {"months": months, "area_id": area_id}},
        )
        return Response(
            content={
                "code": 200,
                "msg": "范围2回填完成",
                "data": {
                    "months": month_keys,
                    "rebuilt_count": rebuilt_count,
                    "ready_count": ready_count,
                    "invalid_count": invalid_count,
                    "details": details,
                },
            }
        )

    @post("/api/energy-carbon/admin/seed/demo-carbon", guards=[requires_superuser])
    async def admin_seed_demo_carbon(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
        data: dict[str, Any] = Body(default={}),
    ) -> Response[dict]:
        months = int(data.get("months") or 6)
        deleted = await self._clear_demo_seed_records(db_session)
        created = await self._seed_demo_scope_records(db_session, months)
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.demo.seed",
            target_type="demo_seed",
            details={"query_scope": {"months": months}, "deleted": deleted, "created": created},
        )
        return Response(content={"code": 200, "msg": "初始化数据已重建", "data": {"deleted": deleted, "created": created}})

    @delete("/api/energy-carbon/admin/seed/demo-carbon", guards=[requires_superuser], status_code=200)
    async def admin_delete_demo_carbon(
        self,
        request: Request[Any, Any, Any],
        db_session: AsyncSession,
        security_audit_service: AuditLogService,
    ) -> Response[dict]:
        deleted = await self._clear_demo_seed_records(db_session)
        await _log_security_audit(
            security_audit_service,
            request,
            action="carbon.demo.delete",
            target_type="demo_seed",
            details={"deleted": deleted},
        )
        return Response(content={"code": 200, "msg": "初始化数据已清理", "data": {"deleted": deleted}})
