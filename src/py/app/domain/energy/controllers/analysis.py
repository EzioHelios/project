from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get
from litestar.response import Response

from app.domain.energy.controllers._utils import ok_data
from app.domain.energy.queries.analysis import EnergyAnalysisQuery, EnergyAnalysisQueryService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EnergyAnalysisController(Controller):
    tags = ["Energy"]

    @get("/api/energy/analysis/summary")
    async def get_energy_analysis_summary(
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
        tariff_segment_type: str | None = None,
    ) -> Response[dict]:
        data = await EnergyAnalysisQueryService(db_session).summary(
            EnergyAnalysisQuery(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                energy_type_code=energy_type_code,
                area_id=area_id,
                area_keyword=area_keyword,
                equipment_id=equipment_id,
                use_system_code=use_system_code,
                tariff_segment_type=tariff_segment_type,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/analysis/anomalies")
    async def get_energy_analysis_anomalies(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "day",
        energy_type_code: str | None = None,
        area_id: str | None = None,
        use_system_code: str | None = None,
        area_keyword: str | None = None,
        equipment_id: str | None = None,
        tariff_segment_type: str | None = None,
        limit: int = 30,
    ) -> Response[dict]:
        data = await EnergyAnalysisQueryService(db_session).anomalies(
            EnergyAnalysisQuery(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                energy_type_code=energy_type_code,
                area_id=area_id,
                use_system_code=use_system_code,
                area_keyword=area_keyword,
                equipment_id=equipment_id,
                tariff_segment_type=tariff_segment_type,
                limit=limit,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/analysis/strategies")
    async def get_energy_analysis_strategies(
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
        tariff_segment_type: str | None = None,
    ) -> Response[dict]:
        data = await EnergyAnalysisQueryService(db_session).strategies(
            EnergyAnalysisQuery(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                energy_type_code=energy_type_code,
                area_id=area_id,
                area_keyword=area_keyword,
                equipment_id=equipment_id,
                use_system_code=use_system_code,
                tariff_segment_type=tariff_segment_type,
            )
        )
        return Response(content=ok_data(data))
