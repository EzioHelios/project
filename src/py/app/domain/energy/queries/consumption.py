# ruff: noqa: S608
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.domain.energy.queries.common import jsonable_mapping, paged_payload

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


ENERGY_FACT_SORT_FIELDS = {
    "period_start",
    "period_end",
    "scope",
    "energy_type_code",
    "energy_type_name",
    "original_amount",
    "factor_amount",
    "tce_amount",
    "co2e_amount",
    "status",
    "source_record_id",
}

ENERGY_CONSUMPTION_EXPORT_HEADERS = [
    "source_record_type",
    "source_record_id",
    "scope",
    "emission_category",
    "energy_type_code",
    "energy_type_name",
    "original_amount",
    "original_unit",
    "factor_amount",
    "factor_unit",
    "unit_conversion_factor",
    "unit_conversion_source",
    "standard_amount",
    "standard_unit",
    "tce_amount",
    "co2e_amount",
    "period_start",
    "period_end",
    "area_id",
    "area_name",
    "facility_or_device_name",
    "status",
    "standard_code",
    "conversion_factor_source",
    "emission_factor_source",
]


@dataclass(frozen=True, slots=True)
class EnergyConsumptionQuery:
    period_start: str | None = None
    period_end: str | None = None
    energy_type_code: str | None = None
    scope: str | None = None
    status: str | None = "approved"
    area_id: str | None = None
    area_keyword: str | None = None
    source_record_type: str | None = None
    keyword: str | None = None
    limit: int = 20
    offset: int = 0
    sort_field: str = "period_start"
    sort_order: str = "desc"
    group_by: str = "energy_type"


class EnergyConsumptionQueryService:
    """Read service for the guide-facing energy consumption fact view."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def facts(self, query: EnergyConsumptionQuery) -> dict[str, Any]:
        limit_clamped = max(1, min(query.limit, 200))
        offset_clamped = max(0, query.offset)
        where_sql, params = build_energy_fact_filters(query)
        order_field = query.sort_field if query.sort_field in ENERGY_FACT_SORT_FIELDS else "period_start"
        order_direction = "asc" if query.sort_order == "asc" else "desc"
        total = int(
            (await self._session.execute(text(f"select count(*) from energy_consumption_fact_v {where_sql}"), params)).scalar_one()
            or 0
        )
        rows = (
            await self._session.execute(
                text(
                    f"""
                    select
                        {", ".join(ENERGY_CONSUMPTION_EXPORT_HEADERS)}
                    from energy_consumption_fact_v
                    {where_sql}
                    order by {order_field} {order_direction}, source_record_id desc
                    limit :limit offset :offset
                    """
                ),
                {**params, "limit": limit_clamped, "offset": offset_clamped},
            )
        ).mappings().all()
        return paged_payload([jsonable_mapping(dict(row)) for row in rows], total, limit_clamped, offset_clamped)

    async def summary(self, query: EnergyConsumptionQuery) -> dict[str, Any]:
        group_options = {
            "energy_type": ("energy_type_code", "energy_type_name"),
            "scope": ("scope", "scope"),
            "area": ("coalesce(area_id, '')", "coalesce(area_name, '未分区')"),
            "source": ("source_record_type", "source_record_type"),
            "facility": ("coalesce(facility_or_device_name, '')", "coalesce(facility_or_device_name, '未命名')"),
        }
        requested_groups = [item.strip() for item in query.group_by.split(",") if item.strip() in group_options]
        if not requested_groups:
            requested_groups = ["energy_type"]

        select_parts: list[str] = []
        group_parts: list[str] = []
        for index, group_name in enumerate(requested_groups, start=1):
            key_expr, label_expr = group_options[group_name]
            select_parts.append(f"{key_expr} as group_key_{index}")
            select_parts.append(f"{label_expr} as group_label_{index}")
            group_parts.extend([key_expr, label_expr])

        where_sql, params = build_energy_fact_filters(query)
        rows = (
            await self._session.execute(
                text(
                    f"""
                    select
                        {", ".join(select_parts)},
                        count(*)::int as record_count,
                        sum(original_amount) as original_amount,
                        max(original_unit) as original_unit,
                        sum(factor_amount) as factor_amount,
                        max(factor_unit) as factor_unit,
                        sum(standard_amount) as standard_amount,
                        max(standard_unit) as standard_unit,
                        sum(tce_amount) as tce_amount,
                        sum(co2e_amount) as co2e_amount
                    from energy_consumption_fact_v
                    {where_sql}
                    group by {", ".join(group_parts)}
                    order by sum(tce_amount) desc nulls last, sum(original_amount) desc nulls last
                    """
                ),
                params,
            )
        ).mappings().all()

        items: list[dict[str, Any]] = []
        for row in rows:
            item = jsonable_mapping(dict(row))
            groups = [
                {
                    "dimension": requested_groups[index - 1],
                    "key": item.pop(f"group_key_{index}", None),
                    "label": item.pop(f"group_label_{index}", None),
                }
                for index in range(1, len(requested_groups) + 1)
            ]
            item["groups"] = groups
            item["group_key"] = " / ".join(str(group["key"] or "") for group in groups)
            item["group_label"] = " / ".join(str(group["label"] or "-") for group in groups)
            items.append(item)

        totals = jsonable_mapping(
            dict(
                (
                    await self._session.execute(
                        text(
                            f"""
                            select
                                count(*)::int as record_count,
                                sum(original_amount) as original_amount,
                                sum(factor_amount) as factor_amount,
                                sum(standard_amount) as standard_amount,
                                sum(tce_amount) as tce_amount,
                                sum(co2e_amount) as co2e_amount
                            from energy_consumption_fact_v
                            {where_sql}
                            """
                        ),
                        params,
                    )
                )
                .mappings()
                .one()
            )
        )
        return {
            "code": 200,
            "msg": "获取成功",
            "data": {
                "items": items,
                "totals": totals,
                "group_by": requested_groups,
                "filters": filters_payload(query),
            },
        }

    async def export_rows(self, query: EnergyConsumptionQuery) -> list[dict[str, Any]]:
        where_sql, params = build_energy_fact_filters(query)
        rows = (
            await self._session.execute(
                text(
                    f"""
                    select
                        {", ".join(ENERGY_CONSUMPTION_EXPORT_HEADERS)}
                    from energy_consumption_fact_v
                    {where_sql}
                    order by period_start desc, source_record_id desc
                    limit 5000
                    """
                ),
                params,
            )
        ).mappings().all()
        return [jsonable_mapping(dict(row)) for row in rows]


def build_energy_fact_filters(query: EnergyConsumptionQuery) -> tuple[str, dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}
    if query.period_start:
        conditions.append("period_end >= :period_start")
        params["period_start"] = query.period_start
    if query.period_end:
        conditions.append("period_start <= :period_end")
        params["period_end"] = query.period_end
    if query.energy_type_code and query.energy_type_code != "all":
        conditions.append("energy_type_code = :energy_type_code")
        params["energy_type_code"] = query.energy_type_code
    if query.scope and query.scope != "all":
        conditions.append("scope = :scope")
        params["scope"] = query.scope
    if query.status and query.status != "all":
        conditions.append("status = :status")
        params["status"] = query.status
    if query.area_id and query.area_id != "all":
        conditions.append("area_id = :area_id")
        params["area_id"] = query.area_id
    if query.source_record_type and query.source_record_type != "all":
        conditions.append("source_record_type = :source_record_type")
        params["source_record_type"] = query.source_record_type
    if query.area_keyword:
        conditions.append("(area_name ilike :area_keyword or area_id ilike :area_keyword)")
        params["area_keyword"] = f"%{query.area_keyword.strip()}%"
    if query.keyword:
        conditions.append(
            """
            (
                energy_type_code ilike :keyword
                or energy_type_name ilike :keyword
                or facility_or_device_name ilike :keyword
                or area_name ilike :keyword
                or source_record_type ilike :keyword
            )
            """
        )
        params["keyword"] = f"%{query.keyword.strip()}%"
    return (f"where {' and '.join(conditions)}" if conditions else ""), params


def filters_payload(query: EnergyConsumptionQuery) -> dict[str, Any]:
    return {
        "period_start": query.period_start,
        "period_end": query.period_end,
        "energy_type_code": query.energy_type_code,
        "scope": query.scope,
        "status": query.status,
        "area_id": query.area_id,
        "area_keyword": query.area_keyword,
        "source_record_type": query.source_record_type,
        "keyword": query.keyword,
    }
