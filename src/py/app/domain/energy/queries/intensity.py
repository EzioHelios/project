# ruff: noqa: S608
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text

from app.db import models as m
from app.domain.energy.queries.common import jsonable_mapping, positive_float, ratio_or_none
from app.domain.energy.queries.consumption import EnergyConsumptionQuery, build_energy_fact_filters
from app.domain.production_denominator.policies import normalize_price_type
from app.domain.production_denominator.queries import (
    ProductionDenominatorQueryService,
    ProductionOutputQuery,
    period_sql_expr,
    production_totals,
    selected_output_value,
    selected_price,
    selected_price_missing,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class EnergyIntensityQuery:
    period_start: str | None = None
    period_end: str | None = None
    granularity: str = "month"
    months: int = 12
    status: str | None = "all"
    scope: str | None = None
    energy_type_code: str | None = None
    source_record_type: str | None = None
    product_code: str | None = None
    category: str | None = None
    output_kind: str | None = None
    line_code: str | None = None
    area_id: str | None = None
    equipment_code: str | None = None
    record_status: str | None = "confirmed"
    price_type: str = "standard_price"


class EnergyIntensityQueryService:
    """Read service for energy, area, product, and value intensity metrics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def summary(self, query: EnergyIntensityQuery) -> dict[str, Any]:
        where_sql, params = build_energy_fact_filters(_energy_consumption_query(query))
        totals = await _energy_kgce_totals(self._session, query)
        by_energy_type = await _rows(
            self._session,
            f"""
            select
                energy_type_code,
                energy_type_name,
                count(*)::int as record_count,
                coalesce(sum(original_amount), 0) as original_amount,
                max(original_unit) as original_unit,
                coalesce(sum(tce_amount), 0) as total_tce,
                coalesce(sum(standard_amount), 0) as total_kgce,
                coalesce(sum(co2e_amount), 0) as total_co2e
            from energy_consumption_fact_v
            {where_sql}
            group by energy_type_code, energy_type_name
            order by sum(tce_amount) desc nulls last, sum(original_amount) desc nulls last
            """,
            params,
        )
        by_scope = await _rows(
            self._session,
            f"""
            select
                scope,
                count(*)::int as record_count,
                coalesce(sum(tce_amount), 0) as total_tce,
                coalesce(sum(standard_amount), 0) as total_kgce,
                coalesce(sum(co2e_amount), 0) as total_co2e
            from energy_consumption_fact_v
            {where_sql}
            group by scope
            order by scope
            """,
            params,
        )
        by_area = await _rows(
            self._session,
            f"""
            select
                coalesce(area_id, '') as area_id,
                coalesce(area_name, '未分区') as area_name,
                count(*)::int as record_count,
                coalesce(sum(tce_amount), 0) as total_tce,
                coalesce(sum(standard_amount), 0) as total_kgce,
                coalesce(sum(co2e_amount), 0) as total_co2e,
                coalesce(sum(case when energy_type_code = 'purchased_electricity' then original_amount else 0 end), 0) as electricity_kwh
            from energy_consumption_fact_v
            {where_sql}
            group by coalesce(area_id, ''), coalesce(area_name, '未分区')
            order by sum(tce_amount) desc nulls last, sum(original_amount) desc nulls last
            limit 100
            """,
            params,
        )
        by_device = await _rows(
            self._session,
            f"""
            select
                coalesce(facility_or_device_name, '未命名') as facility_or_device_name,
                coalesce(area_name, '未分区') as area_name,
                count(*)::int as record_count,
                coalesce(sum(tce_amount), 0) as total_tce,
                coalesce(sum(standard_amount), 0) as total_kgce,
                coalesce(sum(co2e_amount), 0) as total_co2e,
                coalesce(sum(case when energy_type_code = 'purchased_electricity' then original_amount else 0 end), 0) as electricity_kwh
            from energy_consumption_fact_v
            {where_sql}
            group by coalesce(facility_or_device_name, '未命名'), coalesce(area_name, '未分区')
            order by sum(tce_amount) desc nulls last, sum(original_amount) desc nulls last
            limit 100
            """,
            params,
        )
        denominators = await energy_area_denominators(self._session)
        total_tce = totals.get("total_tce") or 0
        electricity_kwh = totals.get("electricity_kwh") or 0
        return {
            "totals": totals,
            "denominators": denominators,
            "intensities": {
                "store_area_tce_per_m2": ratio_or_none(total_tce, denominators["store_area"]),
                "park_area_tce_per_m2": ratio_or_none(total_tce, denominators["park_area"]),
                "store_area_kwh_per_m2": ratio_or_none(electricity_kwh, denominators["store_area"]),
                "park_area_kwh_per_m2": ratio_or_none(electricity_kwh, denominators["park_area"]),
            },
            "by_energy_type": by_energy_type,
            "by_scope": by_scope,
            "by_area": by_area,
            "by_device": by_device,
            "filters": _energy_filters(query),
        }

    async def trend(self, query: EnergyIntensityQuery) -> dict[str, Any]:
        months_clamped = max(1, min(query.months, 366))
        date_part, period_format = period_sql_expr(query.granularity)
        where_sql, params = build_energy_fact_filters(_energy_consumption_query(query))
        rows = await _rows(
            self._session,
            f"""
            select
                to_char(date_trunc(:date_part, period_start), :period_format) as period,
                count(*)::int as record_count,
                coalesce(sum(tce_amount), 0) as total_tce,
                coalesce(sum(standard_amount), 0) as total_kgce,
                coalesce(sum(co2e_amount), 0) as total_co2e,
                coalesce(sum(case when energy_type_code = 'purchased_electricity' then original_amount else 0 end), 0) as electricity_kwh
            from energy_consumption_fact_v
            {where_sql}
            group by date_trunc(:date_part, period_start)
            order by period desc
            limit :months
            """,
            {**params, "months": months_clamped, "date_part": date_part, "period_format": period_format},
        )
        denominators = await energy_area_denominators(self._session)
        series: list[dict[str, Any]] = []
        for row in reversed(rows):
            total_tce = row.get("total_tce") or 0
            electricity_kwh = row.get("electricity_kwh") or 0
            series.append(
                {
                    **row,
                    "store_area_tce_per_m2": ratio_or_none(total_tce, denominators["store_area"]),
                    "park_area_tce_per_m2": ratio_or_none(total_tce, denominators["park_area"]),
                    "store_area_kwh_per_m2": ratio_or_none(electricity_kwh, denominators["store_area"]),
                    "park_area_kwh_per_m2": ratio_or_none(electricity_kwh, denominators["park_area"]),
                }
            )
        return {
            "series": series,
            "denominators": denominators,
            "filters": {
                "months": months_clamped,
                "granularity": date_part,
                "period_start": query.period_start,
                "period_end": query.period_end,
                "energy_type_code": query.energy_type_code,
                "scope": query.scope,
                "status": query.status,
            },
        }

    async def basis(self) -> dict[str, Any]:
        denominators = await energy_area_denominators(self._session)
        denominator_sources = [
            {
                "key": "store_area",
                "label": "仓储面积",
                "source_table": "dataapp_enterpriseinfo",
                "source_field": "store_area",
                "value": denominators["store_area"],
                "unit": "㎡",
                "missing": denominators["store_area"] is None,
            },
            {
                "key": "park_area",
                "label": "园区面积",
                "source_table": "dataapp_enterpriseinfo",
                "source_field": "park_area",
                "value": denominators["park_area"],
                "unit": "㎡",
                "missing": denominators["park_area"] is None,
            },
        ]
        return {
            "numerator_sources": [
                {
                    "key": "total_tce",
                    "label": "综合能耗",
                    "source_view": "energy_consumption_fact_v",
                    "source_field": "tce_amount",
                    "unit": "tce",
                    "standard": "GB/T 2589-2020",
                },
                {
                    "key": "electricity_kwh",
                    "label": "外购电力专项消费量",
                    "source_view": "energy_consumption_fact_v",
                    "source_field": "original_amount",
                    "filter": "energy_type_code = purchased_electricity",
                    "unit": "kWh",
                },
            ],
            "denominator_sources": denominator_sources,
            "missing_items": [f"{item['key']}_missing" for item in denominator_sources if item["missing"]],
            "assumptions": [
                "P0 只计算面积强度, 不计算单位产值或单位产品产量强度。",
                "综合能耗来自 energy_consumption_fact_v.tce_amount, 折标口径按能源品种字典和 GB/T 2589-2020 管理。",
                "月度趋势按 period_start 所在月份归属, 跨月消费首版不拆分。",
                "默认状态为 all; 正式报表可手动切换 approved。",
            ],
        }

    async def product_summary(self, query: EnergyIntensityQuery) -> dict[str, Any]:
        energy_totals = await _energy_kgce_totals(self._session, query)
        product_rows = await ProductionDenominatorQueryService(self._session).product_rows(_production_query(query))
        production_totals_payload = production_totals(product_rows)
        can_calculate_unit_intensity = bool(query.product_code and query.product_code != "all") or len(product_rows) == 1
        total_kgce = float(energy_totals.get("total_kgce") or 0)
        rows = []
        for row in product_rows:
            standard_qty = float(row.get("total_standard_qty") or 0)
            row_kgce = total_kgce if can_calculate_unit_intensity else None
            rows.append(
                {
                    **row,
                    "total_kgce": row_kgce,
                    "kgce_per_unit": ratio_or_none(row_kgce, standard_qty) if row_kgce is not None else None,
                    "calculation_status": "ready" if row_kgce is not None else "requires_single_product_filter",
                }
            )
        return {
            "energy_totals": energy_totals,
            "production_totals": production_totals_payload,
            "items": rows,
            "unit_intensity": (
                ratio_or_none(total_kgce, production_totals_payload["total_standard_qty"]) if can_calculate_unit_intensity else None
            ),
            "mixed_unit_product_intensity": None,
            "granularity": query.granularity,
            "filters": _product_filters(query),
        }

    async def value_summary(self, query: EnergyIntensityQuery) -> dict[str, Any]:
        selected_price_type = normalize_price_type(query.price_type)
        energy_totals = await _energy_kgce_totals(self._session, query)
        product_rows = await ProductionDenominatorQueryService(self._session).product_rows(_production_query(query))
        total_kgce = float(energy_totals.get("total_kgce") or 0)
        missing_price_products = [
            {"product_code": row.get("product_code"), "product_name": row.get("product_name"), "price_type": selected_price_type}
            for row in product_rows
            if selected_price_missing(row, selected_price_type)
        ]
        output_value = sum(selected_output_value(row, selected_price_type) for row in product_rows)
        output_value_10k = output_value / 10000 if output_value else 0
        can_calculate_product_row = bool(query.product_code and query.product_code != "all") or len(product_rows) == 1
        rows = []
        for row in product_rows:
            row_output_value = selected_output_value(row, selected_price_type)
            row_output_value_10k = row_output_value / 10000 if row_output_value else 0
            row_kgce = total_kgce if can_calculate_product_row and not selected_price_missing(row, selected_price_type) else None
            rows.append(
                {
                    **row,
                    "selected_price_type": selected_price_type,
                    "selected_price": selected_price(row, selected_price_type),
                    "selected_output_value": row_output_value,
                    "selected_output_value_10k": row_output_value_10k,
                    "total_kgce": row_kgce,
                    "kgce_per_10k_value": ratio_or_none(row_kgce, row_output_value_10k) if row_kgce is not None else None,
                    "price_missing": selected_price_missing(row, selected_price_type),
                }
            )
        return {
            "energy_totals": energy_totals,
            "production_totals": production_totals(product_rows),
            "price_type": selected_price_type,
            "output_value": output_value,
            "output_value_10k": output_value_10k,
            "kgce_per_10k_value": ratio_or_none(total_kgce, output_value_10k),
            "missing_price_products": missing_price_products,
            "items": rows,
            "granularity": query.granularity,
            "filters": {**_product_filters(query), "price_type": selected_price_type},
        }

    async def product_trend(self, query: EnergyIntensityQuery) -> dict[str, Any]:
        energy_by_period = await _energy_by_period(self._session, query)
        production_rows = await ProductionDenominatorQueryService(self._session).period_rows(_production_query(query))
        series = []
        for row in production_rows:
            energy = energy_by_period.get(row["period"], {"total_kgce": 0, "total_tce": 0})
            can_calculate = bool(query.product_code and query.product_code != "all") or int(row.get("product_count") or 0) <= 1
            total_kgce = float(energy.get("total_kgce") or 0)
            standard_qty = float(row.get("total_standard_qty") or 0)
            series.append(
                {
                    **row,
                    "total_kgce": total_kgce,
                    "total_tce": energy.get("total_tce") or 0,
                    "kgce_per_unit": ratio_or_none(total_kgce, standard_qty) if can_calculate else None,
                }
            )
        return {"series": series, "granularity": query.granularity}

    async def value_trend(self, query: EnergyIntensityQuery) -> dict[str, Any]:
        selected_price_type = normalize_price_type(query.price_type)
        energy_by_period = await _energy_by_period(self._session, query)
        production_rows = await ProductionDenominatorQueryService(self._session).period_rows(_production_query(query))
        value_field = {
            "actual_average_price": "output_value_current_price",
            "standard_price": "output_value_standard_price",
            "base_period_price": "output_value_base_price",
        }[selected_price_type]
        series = []
        for row in production_rows:
            energy = energy_by_period.get(row["period"], {"total_kgce": 0, "total_tce": 0})
            total_kgce = float(energy.get("total_kgce") or 0)
            output_value = float(row.get(value_field) or 0)
            output_value_10k = output_value / 10000 if output_value else 0
            series.append(
                {
                    **row,
                    "price_type": selected_price_type,
                    "output_value": output_value,
                    "output_value_10k": output_value_10k,
                    "total_kgce": total_kgce,
                    "total_tce": energy.get("total_tce") or 0,
                    "kgce_per_10k_value": ratio_or_none(total_kgce, output_value_10k),
                }
            )
        return {"series": series, "granularity": query.granularity, "price_type": selected_price_type}


async def energy_area_denominators(session: AsyncSession) -> dict[str, Any]:
    enterprise = await session.scalar(select(m.EnterpriseInfo).limit(1))
    store_area = positive_float(enterprise.store_area) if enterprise else None
    park_area = positive_float(enterprise.park_area) if enterprise else None
    return {
        "enterprise": {
            "id": enterprise.id if enterprise else None,
            "name": enterprise.name if enterprise else None,
            "belong_unit": enterprise.belong_unit if enterprise else None,
            "unify_code": enterprise.unify_code if enterprise else None,
            "industry": enterprise.industry if enterprise else None,
            "location": enterprise.location if enterprise else None,
        },
        "store_area": store_area,
        "park_area": park_area,
        "source_record_type": "EnterpriseInfo",
        "source_table": "dataapp_enterpriseinfo",
        "source_fields": {"store_area": "store_area", "park_area": "park_area"},
    }


async def _energy_kgce_totals(session: AsyncSession, query: EnergyIntensityQuery) -> dict[str, Any]:
    where_sql, params = build_energy_fact_filters(_energy_consumption_query(query))
    row = (
        await session.execute(
            text(
                f"""
                select
                    count(*)::int as record_count,
                    coalesce(sum(tce_amount), 0) as total_tce,
                    coalesce(sum(standard_amount), 0) as total_kgce,
                    coalesce(sum(co2e_amount), 0) as total_co2e,
                    coalesce(sum(case when energy_type_code = 'purchased_electricity' then original_amount else 0 end), 0) as electricity_kwh
                from energy_consumption_fact_v
                {where_sql}
                """
            ),
            params,
        )
    ).mappings().one()
    return jsonable_mapping(dict(row))


async def _energy_by_period(session: AsyncSession, query: EnergyIntensityQuery) -> dict[str, dict[str, Any]]:
    where_sql, params = build_energy_fact_filters(_energy_consumption_query(query))
    date_part, period_format = period_sql_expr(query.granularity)
    rows = await _rows(
        session,
        f"""
        select
            to_char(date_trunc(:date_part, period_start), :period_format) as period,
            coalesce(sum(standard_amount), 0) as total_kgce,
            coalesce(sum(tce_amount), 0) as total_tce
        from energy_consumption_fact_v
        {where_sql}
        group by date_trunc(:date_part, period_start)
        """,
        {**params, "date_part": date_part, "period_format": period_format},
    )
    return {row["period"]: row for row in rows}


async def _rows(session: AsyncSession, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (await session.execute(text(sql), params)).mappings().all()
    return [jsonable_mapping(dict(row)) for row in rows]


def _energy_consumption_query(query: EnergyIntensityQuery) -> EnergyConsumptionQuery:
    return EnergyConsumptionQuery(
        period_start=query.period_start,
        period_end=query.period_end,
        energy_type_code=query.energy_type_code,
        scope=query.scope,
        status=query.status,
        source_record_type=query.source_record_type,
    )


def _production_query(query: EnergyIntensityQuery) -> ProductionOutputQuery:
    return ProductionOutputQuery(
        period_start=query.period_start,
        period_end=query.period_end,
        granularity=query.granularity,
        product_code=query.product_code,
        category=query.category,
        output_kind=query.output_kind,
        line_code=query.line_code,
        area_id=query.area_id,
        equipment_code=query.equipment_code,
        record_status=query.record_status,
    )


def _energy_filters(query: EnergyIntensityQuery) -> dict[str, Any]:
    return {
        "period_start": query.period_start,
        "period_end": query.period_end,
        "energy_type_code": query.energy_type_code,
        "scope": query.scope,
        "status": query.status,
        "source_record_type": query.source_record_type,
    }


def _product_filters(query: EnergyIntensityQuery) -> dict[str, Any]:
    return {
        **_energy_filters(query),
        "product_code": query.product_code,
        "category": query.category,
        "output_kind": query.output_kind,
        "line_code": query.line_code,
        "area_id": query.area_id,
        "equipment_code": query.equipment_code,
        "record_status": query.record_status,
    }
