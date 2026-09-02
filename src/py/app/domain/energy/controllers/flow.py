from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get
from litestar.response import Response

from app.domain.energy.controllers._utils import ok_data
from app.domain.energy.queries.flow import EnergyFlowQuery, EnergyFlowQueryService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EnergyFlowController(Controller):
    tags = ["Energy"]

    @get("/api/energy/flow/graph")
    async def get_energy_flow_graph(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "day",
        energy_type_code: str | None = None,
        area_id: str | None = None,
        area_keyword: str | None = None,
        equipment_id: str | None = None,
        use_system_code: str | None = None,
        loss_threshold_pct: float = 5.0,
    ) -> Response[dict]:
        data = await EnergyFlowQueryService(db_session).graph(
            _query(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                energy_type_code=energy_type_code,
                area_id=area_id,
                area_keyword=area_keyword,
                equipment_id=equipment_id,
                use_system_code=use_system_code,
                loss_threshold_pct=loss_threshold_pct,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/flow/balance")
    async def get_energy_flow_balance(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "day",
        energy_type_code: str | None = None,
        area_id: str | None = None,
        area_keyword: str | None = None,
        equipment_id: str | None = None,
        use_system_code: str | None = None,
        loss_threshold_pct: float = 5.0,
    ) -> Response[dict]:
        data = await EnergyFlowQueryService(db_session).balance(
            _query(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                energy_type_code=energy_type_code,
                area_id=area_id,
                area_keyword=area_keyword,
                equipment_id=equipment_id,
                use_system_code=use_system_code,
                loss_threshold_pct=loss_threshold_pct,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/flow/losses")
    async def list_energy_flow_losses(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "day",
        energy_type_code: str | None = None,
        area_id: str | None = None,
        area_keyword: str | None = None,
        equipment_id: str | None = None,
        use_system_code: str | None = None,
        loss_threshold_pct: float = 5.0,
        limit: int = 50,
    ) -> Response[dict]:
        data = await EnergyFlowQueryService(db_session).losses(
            _query(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                energy_type_code=energy_type_code,
                area_id=area_id,
                area_keyword=area_keyword,
                equipment_id=equipment_id,
                use_system_code=use_system_code,
                loss_threshold_pct=loss_threshold_pct,
                limit=limit,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/flow/report")
    async def get_energy_flow_report(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "day",
        energy_type_code: str | None = None,
        area_id: str | None = None,
        area_keyword: str | None = None,
        equipment_id: str | None = None,
        use_system_code: str | None = None,
        loss_threshold_pct: float = 5.0,
    ) -> Response[dict]:
        data = await EnergyFlowQueryService(db_session).report(
            _query(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                energy_type_code=energy_type_code,
                area_id=area_id,
                area_keyword=area_keyword,
                equipment_id=equipment_id,
                use_system_code=use_system_code,
                loss_threshold_pct=loss_threshold_pct,
            )
        )
        return Response(content=ok_data(data))


def _query(
    *,
    period_start: str | None,
    period_end: str | None,
    granularity: str,
    energy_type_code: str | None,
    area_id: str | None,
    area_keyword: str | None,
    equipment_id: str | None,
    use_system_code: str | None,
    loss_threshold_pct: float,
    limit: int = 50,
) -> EnergyFlowQuery:
    return EnergyFlowQuery(
        period_start=period_start,
        period_end=period_end,
        granularity=granularity,
        energy_type_code=energy_type_code,
        area_id=area_id,
        area_keyword=area_keyword,
        equipment_id=equipment_id,
        use_system_code=use_system_code,
        loss_threshold_pct=loss_threshold_pct,
        limit=limit,
    )
