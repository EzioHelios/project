from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get
from litestar.params import Parameter
from litestar.response import Response

from app.domain.energy.controllers._utils import ok_data
from app.domain.energy.queries.intensity import EnergyIntensityQuery, EnergyIntensityQueryService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EnergyIntensityController(Controller):
    tags = ["Energy"]

    @get("/api/energy/intensity/summary")
    async def get_energy_intensity_summary(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        energy_type_code: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        status: str | None = "all",
        source_record_type: str | None = None,
    ) -> Response[dict]:
        data = await EnergyIntensityQueryService(db_session).summary(
            EnergyIntensityQuery(
                period_start=period_start,
                period_end=period_end,
                energy_type_code=energy_type_code,
                scope=scope_filter,
                status=status,
                source_record_type=source_record_type,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/intensity/trend")
    async def get_energy_intensity_trend(
        self,
        db_session: AsyncSession,
        months: int = 12,
        status: str | None = "all",
        energy_type_code: str | None = None,
        scope_filter: str | None = Parameter(query="scope", required=False),
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "month",
    ) -> Response[dict]:
        data = await EnergyIntensityQueryService(db_session).trend(
            EnergyIntensityQuery(
                period_start=period_start,
                period_end=period_end,
                energy_type_code=energy_type_code,
                scope=scope_filter,
                status=status,
                months=months,
                granularity=granularity,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/intensity/basis")
    async def get_energy_intensity_basis(self, db_session: AsyncSession) -> Response[dict]:
        data = await EnergyIntensityQueryService(db_session).basis()
        return Response(content=ok_data(data))

    @get("/api/energy/intensity/product-summary")
    async def get_energy_intensity_product_summary(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "month",
        status: str | None = "all",
        scope_filter: str | None = Parameter(query="scope", required=False),
        energy_type_code: str | None = None,
        source_record_type: str | None = None,
        product_code: str | None = None,
        category: str | None = None,
        output_kind: str | None = None,
        line_code: str | None = None,
        area_id: str | None = None,
        equipment_code: str | None = None,
        record_status: str | None = "confirmed",
    ) -> Response[dict]:
        data = await EnergyIntensityQueryService(db_session).product_summary(
            _query(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                status=status,
                scope=scope_filter,
                energy_type_code=energy_type_code,
                source_record_type=source_record_type,
                product_code=product_code,
                category=category,
                output_kind=output_kind,
                line_code=line_code,
                area_id=area_id,
                equipment_code=equipment_code,
                record_status=record_status,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/intensity/value-summary")
    async def get_energy_intensity_value_summary(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "month",
        status: str | None = "all",
        scope_filter: str | None = Parameter(query="scope", required=False),
        energy_type_code: str | None = None,
        source_record_type: str | None = None,
        product_code: str | None = None,
        category: str | None = None,
        output_kind: str | None = None,
        line_code: str | None = None,
        area_id: str | None = None,
        equipment_code: str | None = None,
        record_status: str | None = "confirmed",
        price_type: str = "standard_price",
    ) -> Response[dict]:
        try:
            data = await EnergyIntensityQueryService(db_session).value_summary(
                _query(
                    period_start=period_start,
                    period_end=period_end,
                    granularity=granularity,
                    status=status,
                    scope=scope_filter,
                    energy_type_code=energy_type_code,
                    source_record_type=source_record_type,
                    product_code=product_code,
                    category=category,
                    output_kind=output_kind,
                    line_code=line_code,
                    area_id=area_id,
                    equipment_code=equipment_code,
                    record_status=record_status,
                    price_type=price_type,
                )
            )
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(data))

    @get("/api/energy/intensity/product-trend")
    async def get_energy_intensity_product_trend(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "month",
        status: str | None = "all",
        scope_filter: str | None = Parameter(query="scope", required=False),
        energy_type_code: str | None = None,
        source_record_type: str | None = None,
        product_code: str | None = None,
        category: str | None = None,
        output_kind: str | None = None,
        line_code: str | None = None,
        area_id: str | None = None,
        equipment_code: str | None = None,
        record_status: str | None = "confirmed",
    ) -> Response[dict]:
        data = await EnergyIntensityQueryService(db_session).product_trend(
            _query(
                period_start=period_start,
                period_end=period_end,
                granularity=granularity,
                status=status,
                scope=scope_filter,
                energy_type_code=energy_type_code,
                source_record_type=source_record_type,
                product_code=product_code,
                category=category,
                output_kind=output_kind,
                line_code=line_code,
                area_id=area_id,
                equipment_code=equipment_code,
                record_status=record_status,
            )
        )
        return Response(content=ok_data(data))

    @get("/api/energy/intensity/value-trend")
    async def get_energy_intensity_value_trend(
        self,
        db_session: AsyncSession,
        period_start: str | None = None,
        period_end: str | None = None,
        granularity: str = "month",
        status: str | None = "all",
        scope_filter: str | None = Parameter(query="scope", required=False),
        energy_type_code: str | None = None,
        source_record_type: str | None = None,
        product_code: str | None = None,
        category: str | None = None,
        output_kind: str | None = None,
        line_code: str | None = None,
        area_id: str | None = None,
        equipment_code: str | None = None,
        record_status: str | None = "confirmed",
        price_type: str = "standard_price",
    ) -> Response[dict]:
        try:
            data = await EnergyIntensityQueryService(db_session).value_trend(
                _query(
                    period_start=period_start,
                    period_end=period_end,
                    granularity=granularity,
                    status=status,
                    scope=scope_filter,
                    energy_type_code=energy_type_code,
                    source_record_type=source_record_type,
                    product_code=product_code,
                    category=category,
                    output_kind=output_kind,
                    line_code=line_code,
                    area_id=area_id,
                    equipment_code=equipment_code,
                    record_status=record_status,
                    price_type=price_type,
                )
            )
        except ValueError as exc:
            return Response(content={"code": 400, "msg": str(exc)}, status_code=400)
        return Response(content=ok_data(data))


def _query(**kwargs: object) -> EnergyIntensityQuery:
    return EnergyIntensityQuery(**kwargs)
