from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get
from litestar.response import Response
from sqlalchemy import func, or_, select

from app.db import models as m
from app.domain.energy.controllers._utils import model_to_dict
from app.domain.production_denominator.controllers._utils import paged_payload

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MeteringReadingController(Controller):
    tags = ["Metering"]

    @get("/api/data/ammeter-values")
    async def list_ammeter_values(
        self,
        db_session: AsyncSession,
        keyword: str | None = None,
        search: str | None = None,
        area_id: str | None = None,
        ammeter_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_field: str = "reading_time",
        sort_order: str = "desc",
        include_null_reading_time: bool = False,
    ) -> Response[dict]:
        conditions = []
        if area_id:
            conditions.append(m.AmmeterIndexValue.area_id == area_id)
        if ammeter_id:
            conditions.append(m.AmmeterIndexValue.ammeter_id == ammeter_id)
        if not include_null_reading_time:
            conditions.append(m.AmmeterIndexValue.reading_time.is_not(None))

        search_value = (search or keyword or "").strip()
        if search_value:
            pattern = f"%{search_value}%"
            conditions.append(
                or_(
                    m.AmmeterIndexValue.ammeter_id.ilike(pattern),
                    m.AmmeterIndexValue.ammeter_name.ilike(pattern),
                    m.AmmeterIndexValue.address.ilike(pattern),
                    m.AmmeterIndexValue.area_name.ilike(pattern),
                )
            )

        limit_clamped = max(1, min(limit, 100))
        offset_clamped = max(0, offset)
        order = "asc" if sort_order == "asc" else "desc"
        sort_column = getattr(m.AmmeterIndexValue, sort_field, m.AmmeterIndexValue.reading_time)
        order_expr = sort_column.asc() if order == "asc" else sort_column.desc()
        if sort_field == "reading_time" and not include_null_reading_time:
            order_expr = m.AmmeterIndexValue.reading_time.asc() if order == "asc" else m.AmmeterIndexValue.reading_time.desc()

        count_stmt = select(func.count()).select_from(m.AmmeterIndexValue)
        rows_stmt = select(m.AmmeterIndexValue).order_by(order_expr, m.AmmeterIndexValue.id.desc()).limit(limit_clamped).offset(offset_clamped)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            rows_stmt = rows_stmt.where(condition)

        total = await db_session.scalar(count_stmt)
        rows = (await db_session.execute(rows_stmt)).scalars().all()
        return Response(content=paged_payload([model_to_dict(row) for row in rows], total or 0, limit_clamped, offset_clamped))

