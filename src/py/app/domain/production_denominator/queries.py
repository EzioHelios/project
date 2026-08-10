# ruff: noqa: S608
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.domain.energy.queries.common import jsonable_mapping, period_param
from app.domain.production_denominator.policies import normalize_production_output_kind
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ProductionOutputQuery:
    period_start: str | None = None
    period_end: str | None = None
    granularity: str = "month"
    product_code: str | None = None
    category: str | None = None
    output_kind: str | None = None
    line_code: str | None = None
    area_id: str | int | None = None
    equipment_code: str | None = None
    record_status: str | None = "confirmed"


class ProductionDenominatorQueryService:
    """Read service for product quantity, workload, and value denominators."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def summary(self, query: ProductionOutputQuery) -> dict[str, Any]:
        product_rows = await self.product_rows(query)
        period_rows = await self.period_rows(query)
        return {
            "totals": production_totals(product_rows),
            "by_product": product_rows,
            "by_period": period_rows,
            "filters": {
                "period_start": query.period_start,
                "period_end": query.period_end,
                "granularity": query.granularity,
                "product_code": query.product_code,
                "category": query.category,
                "output_kind": query.output_kind,
                "line_code": query.line_code,
                "area_id": query.area_id,
                "equipment_code": query.equipment_code,
                "record_status": query.record_status,
            },
        }

    async def product_rows(self, query: ProductionOutputQuery) -> list[dict[str, Any]]:
        where_sql, params = production_output_where_sql(query, team_id=require_session_tenant_id(self._session))
        return await _rows(
            self._session,
            f"""
            select
                o.product_code,
                coalesce(max(nullif(o.product_name, '')), max(p.name), o.product_code) as product_name,
                coalesce(max(nullif(o.product_spec, '')), max(p.spec)) as product_spec,
                max(p.category) as category,
                coalesce(max(nullif(o.output_kind, '')), max(p.output_kind), 'product') as output_kind,
                coalesce(max(nullif(o.standard_unit, '')), max(p.standard_unit), max(o.unit)) as standard_unit,
                count(*)::int as record_count,
                coalesce(sum(o.good_qty), 0) as total_good_qty,
                coalesce(sum(coalesce(o.standard_qty, o.good_qty)), 0) as total_standard_qty,
                coalesce(sum(coalesce(o.standard_qty, o.good_qty) * coalesce(price_actual_average_price.price, 0)), 0) as output_value_current_price,
                coalesce(sum(coalesce(o.standard_qty, o.good_qty) * coalesce(price_standard_price.price, 0)), 0) as output_value_standard_price,
                coalesce(sum(coalesce(o.standard_qty, o.good_qty) * coalesce(price_base_period_price.price, 0)), 0) as output_value_base_price,
                max(price_actual_average_price.price) as actual_average_price,
                max(price_standard_price.price) as standard_price,
                max(price_base_period_price.price) as base_period_price,
                bool_or(price_actual_average_price.price is null) as actual_average_price_missing,
                bool_or(price_standard_price.price is null) as standard_price_missing,
                bool_or(price_base_period_price.price is null) as base_period_price_missing
            from dataapp_productionoutputfact o
            left join dataapp_productionproduct p on p.team_id = o.team_id and p.code = o.product_code
            {price_lateral_joins()}
            {where_sql}
            group by o.product_code
            order by sum(coalesce(o.standard_qty, o.good_qty)) desc nulls last, o.product_code asc
            """,
            params,
        )

    async def period_rows(self, query: ProductionOutputQuery) -> list[dict[str, Any]]:
        where_sql, params = production_output_where_sql(query, team_id=require_session_tenant_id(self._session))
        date_part, period_format = period_sql_expr(query.granularity)
        return await _rows(
            self._session,
            f"""
            select
                to_char(date_trunc(:date_part, o.period_start), :period_format) as period,
                count(*)::int as record_count,
                count(distinct o.product_code)::int as product_count,
                coalesce(sum(o.good_qty), 0) as total_good_qty,
                coalesce(sum(coalesce(o.standard_qty, o.good_qty)), 0) as total_standard_qty,
                coalesce(sum(coalesce(o.standard_qty, o.good_qty) * coalesce(price_actual_average_price.price, 0)), 0) as output_value_current_price,
                coalesce(sum(coalesce(o.standard_qty, o.good_qty) * coalesce(price_standard_price.price, 0)), 0) as output_value_standard_price,
                coalesce(sum(coalesce(o.standard_qty, o.good_qty) * coalesce(price_base_period_price.price, 0)), 0) as output_value_base_price
            from dataapp_productionoutputfact o
            left join dataapp_productionproduct p on p.team_id = o.team_id and p.code = o.product_code
            {price_lateral_joins()}
            {where_sql}
            group by date_trunc(:date_part, o.period_start)
            order by date_trunc(:date_part, o.period_start)
            """,
            {**params, "date_part": date_part, "period_format": period_format},
        )


def production_output_where_sql(query: ProductionOutputQuery, *, team_id: UUID | str) -> tuple[str, dict[str, Any]]:
    conditions = ["o.team_id = :team_id"]
    params: dict[str, Any] = {"team_id": str(team_id)}
    if query.period_start:
        conditions.append("o.period_end >= :period_start")
        params["period_start"] = period_param(query.period_start)
    if query.period_end:
        conditions.append("o.period_start <= :period_end")
        params["period_end"] = period_param(query.period_end)
    if query.product_code and query.product_code != "all":
        conditions.append("o.product_code = :product_code")
        params["product_code"] = query.product_code
    if query.category and query.category != "all":
        conditions.append("p.category = :category")
        params["category"] = query.category
    if query.output_kind and query.output_kind != "all":
        conditions.append("coalesce(o.output_kind, p.output_kind, 'product') = :output_kind")
        params["output_kind"] = normalize_production_output_kind(query.output_kind)
    if query.line_code and query.line_code != "all":
        conditions.append("o.line_code = :line_code")
        params["line_code"] = query.line_code
    if query.area_id and str(query.area_id) != "all":
        conditions.append("o.area_id = :area_id")
        params["area_id"] = int(query.area_id)
    if query.equipment_code and query.equipment_code != "all":
        conditions.append("o.equipment_code = :equipment_code")
        params["equipment_code"] = query.equipment_code
    if query.record_status and query.record_status != "all":
        conditions.append("o.record_status = :record_status")
        params["record_status"] = query.record_status
    return (f"where {' and '.join(conditions)}" if conditions else ""), params


def production_totals(product_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "record_count": int(sum(row.get("record_count") or 0 for row in product_rows)),
        "product_count": len(product_rows),
        "total_good_qty": sum(float(row.get("total_good_qty") or 0) for row in product_rows),
        "total_standard_qty": sum(float(row.get("total_standard_qty") or 0) for row in product_rows),
        "output_value_current_price": sum(float(row.get("output_value_current_price") or 0) for row in product_rows),
        "output_value_standard_price": sum(float(row.get("output_value_standard_price") or 0) for row in product_rows),
        "output_value_base_price": sum(float(row.get("output_value_base_price") or 0) for row in product_rows),
    }


def period_sql_expr(granularity: str) -> tuple[str, str]:
    date_part = granularity if granularity in {"day", "month", "year"} else "month"
    return date_part, {"day": "YYYY-MM-DD", "month": "YYYY-MM", "year": "YYYY"}[date_part]


def price_lateral_joins(
    price_types: tuple[str, ...] = ("actual_average_price", "standard_price", "base_period_price"),
) -> str:
    joins = []
    for price_type in price_types:
        alias = f"price_{price_type}"
        joins.append(
            f"""
            left join lateral (
                select pp.price
                from dataapp_productprice pp
                where pp.team_id = o.team_id
                  and pp.product_code = o.product_code
                  and pp.price_type = '{price_type}'
                  and pp.valid_from <= o.period_start
                  and (pp.valid_to is null or pp.valid_to >= o.period_start)
                order by pp.valid_from desc, pp.id desc
                limit 1
            ) {alias} on true
            """
        )
    return "\n".join(joins)


def selected_output_value(row: dict[str, Any], price_type: str) -> float:
    field = {
        "actual_average_price": "output_value_current_price",
        "standard_price": "output_value_standard_price",
        "base_period_price": "output_value_base_price",
    }[price_type]
    return float(row.get(field) or 0)


def selected_price(row: dict[str, Any], price_type: str) -> float | None:
    value = row.get(price_type)
    return float(value) if value is not None else None


def selected_price_missing(row: dict[str, Any], price_type: str) -> bool:
    return bool(row.get(f"{price_type}_missing"))


async def _rows(session: AsyncSession, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (await session.execute(text(sql), params)).mappings().all()
    return [jsonable_mapping(dict(row)) for row in rows]
