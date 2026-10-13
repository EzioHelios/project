from __future__ import annotations

import os
from datetime import date  # noqa: TC003 - Litestar resolves handler date annotations at runtime.
from pathlib import Path
from typing import TYPE_CHECKING

from litestar import Controller, get
from litestar.exceptions import NotFoundException, ValidationException
from litestar.response import File, Response
from sqlalchemy import select

from app.domain.carbon.models import MonitorSectorPhoto
from app.domain.carbon.services._bigscreen import (
    BigscreenCarbonService,
    BigscreenIntroService,
    BigscreenMetaService,
)
from app.domain.carbon.services._bigscreen_operations import BigscreenOperationsService
from app.domain.carbon.services._huayi_bigscreen import HuayiBigscreenMetaService, HuayiBigscreenOverviewService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.lib.settings import AppSettings


class BigscreenController(Controller):
    path = "/api/bigscreen"
    tags = ["Bigscreen"]

    @get("/photos/{photo_id:int}")
    async def get_photo(self, db_session: AsyncSession, photo_id: int) -> File:
        photo = await db_session.scalar(select(MonitorSectorPhoto).where(MonitorSectorPhoto.id == photo_id))
        if photo is None or not photo.path:
            raise NotFoundException(detail="照片不存在")
        root = (Path(os.environ.get("SECTOR_PHOTO_ROOT", ".storage/sector-photos")) / str(photo.team_id)).resolve()
        path = (root / photo.path).resolve()
        if (
            not path.is_relative_to(root)
            or not path.is_file()
            or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}
        ):
            raise NotFoundException(detail="照片文件不存在")
        return File(
            path=path,
            content_disposition_type="inline",
            headers={"Cache-Control": "private, no-store", "Vary": "Cookie, Authorization, X-Team-Id"},
        )

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
    async def get_overview(
        self,
        db_session: AsyncSession,
        start: date | None = None,
        end: date | None = None,
        grain: str = "day",
        area: str | None = None,
    ) -> Response[dict]:
        try:
            payload = await BigscreenOperationsService(db_session).build(start=start, end=end, grain=grain, area=area)
        except ValueError as exc:
            raise ValidationException(detail=str(exc)) from exc
        return Response(content={"code": 200, "data": payload})

    @get("/power")
    async def get_power(
        self,
        db_session: AsyncSession,
        start: date | None = None,
        end: date | None = None,
        grain: str = "day",
        area: str | None = None,
    ) -> Response[dict]:
        try:
            payload = await BigscreenOperationsService(db_session).build(start=start, end=end, grain=grain, area=area)
        except ValueError as exc:
            raise ValidationException(detail=str(exc)) from exc
        return Response(content={"code": 200, "data": payload})

    @get("/carbon")
    async def get_carbon(self, db_session: AsyncSession) -> Response[dict]:
        payload = await BigscreenCarbonService(session=db_session).build()
        return Response(content={"code": 200, "msg": "获取成功", "data": payload.model_dump(mode="json")})

    @get("/events")
    async def get_events(
        self,
        db_session: AsyncSession,
        category: str = "all",
        start: date | None = None,
        end: date | None = None,
        status: str | None = None,
        area: str | None = None,
        page: int = 1,
    ) -> Response[dict]:
        if category not in {"all", "power", "carbon", "video"}:
            raise ValidationException(detail="预警类别无效")
        try:
            payload = await BigscreenOperationsService(db_session).alerts(
                video=category == "video",
                event_types={"power": [2, 3], "carbon": [4]}.get(category),
                start=start,
                end=end,
                status=status,
                area=area,
                page=page,
                page_size=10,
            )
        except ValueError as exc:
            raise ValidationException(detail=str(exc)) from exc
        return Response(content={"code": 200, "data": payload})


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
