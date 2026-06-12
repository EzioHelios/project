from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

from litestar import Controller, get
from litestar.params import Parameter
from litestar.response import Response

from app.domain.energy.queries.consumption import (
    ENERGY_CONSUMPTION_EXPORT_HEADERS,
    EnergyConsumptionQuery,
    EnergyConsumptionQueryService,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EnergyConsumptionController(Controller):
    tags = ["Energy"]

    @get("/api/energy/consumption/facts")
    async def list_energy_consumption_facts(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        energy_type_code: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        status: str | None = "approved",
        area_id: str | None = None,
        area_keyword: str | None = None,
        source_record_type: str | None = None,
        keyword: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "period_start",
        sort_order: str = "desc",
    ) -> Response[dict]:
        data = await EnergyConsumptionQueryService(db_session).facts(
            EnergyConsumptionQuery(
                period_start=period_start,
                period_end=period_end,
                energy_type_code=energy_type_code,
                scope=scope_filter,
                status=status,
                area_id=area_id,
                area_keyword=area_keyword,
                source_record_type=source_record_type,
                keyword=keyword,
                limit=limit,
                offset=offset,
                sort_field=sort_field,
                sort_order=sort_order,
            )
        )
        return Response(content=data)

    @get("/api/energy/consumption/summary")
    async def get_energy_consumption_summary(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        energy_type_code: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        status: str | None = "approved",
        area_id: str | None = None,
        area_keyword: str | None = None,
        source_record_type: str | None = None,
        keyword: str | None = None,
        group_by: str = "energy_type",
    ) -> Response[dict]:
        payload = await EnergyConsumptionQueryService(db_session).summary(
            EnergyConsumptionQuery(
                period_start=period_start,
                period_end=period_end,
                energy_type_code=energy_type_code,
                scope=scope_filter,
                status=status,
                area_id=area_id,
                area_keyword=area_keyword,
                source_record_type=source_record_type,
                keyword=keyword,
                group_by=group_by,
            )
        )
        return Response(content=payload)

    @get("/api/energy/consumption/export")
    async def export_energy_consumption(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        energy_type_code: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        status: str | None = "approved",
        area_id: str | None = None,
        area_keyword: str | None = None,
        source_record_type: str | None = None,
        keyword: str | None = None,
    ) -> Response[str]:
        rows = await EnergyConsumptionQueryService(db_session).export_rows(
            EnergyConsumptionQuery(
                period_start=period_start,
                period_end=period_end,
                energy_type_code=energy_type_code,
                scope=scope_filter,
                status=status,
                area_id=area_id,
                area_keyword=area_keyword,
                source_record_type=source_record_type,
                keyword=keyword,
            )
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(ENERGY_CONSUMPTION_EXPORT_HEADERS)
        for item in rows:
            writer.writerow([item.get(header) for header in ENERGY_CONSUMPTION_EXPORT_HEADERS])
        return Response(
            content="\ufeff" + output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"content-disposition": 'attachment; filename="energy_consumption.csv"'},
        )
