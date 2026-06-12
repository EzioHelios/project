from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get
from litestar.params import Parameter
from litestar.response import Response
from sqlalchemy import select, text

from app.db import models as m
from app.domain.carbon.deps import provide_energy_type_service
from app.domain.energy.controllers._utils import model_to_dict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EnergyDictionaryController(Controller):
    tags = ["Energy"]
    dependencies = {"energy_type_service": provide_energy_type_service}

    @get("/api/energy/types")
    async def list_energy_types(
        self,
        db_session: AsyncSession,
        category: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        include_disabled: bool = False,
    ) -> Response[dict]:
        conditions = []
        if category:
            conditions.append(m.EnergyType.category == category)
        if scope_filter:
            conditions.append(m.EnergyType.default_scope == scope_filter)
        if not include_disabled:
            conditions.append(m.EnergyType.is_enabled.is_(True))
        rows = (
            await db_session.execute(
                select(m.EnergyType)
                .where(*(conditions or [text("1=1")]))
                .order_by(m.EnergyType.default_scope.asc(), m.EnergyType.category.asc(), m.EnergyType.id.asc())
            )
        ).scalars().all()
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": [model_to_dict(row) for row in rows]}})

    @get("/api/energy/unit-conversions")
    async def list_energy_unit_conversions(
        self,
        db_session: AsyncSession,
        energy_type_code: str | None = None,
        include_disabled: bool = False,
    ) -> Response[dict]:
        conditions = []
        if energy_type_code:
            conditions.append(m.EnergyUnitConversion.energy_type_code == energy_type_code)
        if not include_disabled:
            conditions.append(m.EnergyUnitConversion.is_enabled.is_(True))
        rows = (
            await db_session.execute(
                select(m.EnergyUnitConversion)
                .where(*(conditions or [text("1=1")]))
                .order_by(
                    m.EnergyUnitConversion.energy_type_code.asc(),
                    m.EnergyUnitConversion.from_unit.asc(),
                    m.EnergyUnitConversion.to_unit.asc(),
                )
            )
        ).scalars().all()
        return Response(content={"code": 200, "msg": "获取成功", "data": {"items": [model_to_dict(row) for row in rows]}})
