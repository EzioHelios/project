from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get
from litestar.response import Response

from app.domain.carbon.services._bigscreen import (
    BigscreenCarbonService,
    BigscreenIntroService,
    BigscreenMetaService,
    BigscreenOverviewService,
    BigscreenPowerService,
)
from app.domain.carbon.services._huayi_bigscreen import HuayiBigscreenMetaService, HuayiBigscreenOverviewService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.lib.settings import AppSettings


class BigscreenController(Controller):
    path = "/api/bigscreen"
    tags = ["Bigscreen"]

    @get("/meta")
    async def get_meta(self, settings: AppSettings) -> Response[dict]:
        payload = BigscreenMetaService(
            title=settings.DISPLAY_NAME,
            short_name=settings.SHORT_NAME,
            description=settings.DESCRIPTION,
        ).build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})

    @get("/intro")
    async def get_intro(self, db_session: AsyncSession, settings: AppSettings) -> Response[dict]:
        meta = BigscreenMetaService(
            title=settings.DISPLAY_NAME,
            short_name=settings.SHORT_NAME,
            description=settings.DESCRIPTION,
        )
        payload = await BigscreenIntroService(session=db_session, meta=meta).build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})

    @get("/overview")
    async def get_overview(self, db_session: AsyncSession) -> Response[dict]:
        payload = await BigscreenOverviewService(session=db_session).build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})

    @get("/power")
    async def get_power(self, db_session: AsyncSession) -> Response[dict]:
        payload = await BigscreenPowerService(session=db_session).build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})

    @get("/carbon")
    async def get_carbon(self, db_session: AsyncSession) -> Response[dict]:
        payload = await BigscreenCarbonService(session=db_session).build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})


class HuayiBigscreenController(Controller):
    path = "/api/bigscreen/huayi"
    tags = ["Bigscreen"]

    @get("/meta")
    async def get_meta(self) -> Response[dict]:
        payload = HuayiBigscreenMetaService().build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})

    @get("/overview")
    async def get_overview(self) -> Response[dict]:
        payload = HuayiBigscreenOverviewService().build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})
