"""Tenant-scoped video recognition endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get, post, put
from litestar.exceptions import NotFoundException
from litestar.response import Response

from app.domain.accounts.guards import requires_active_user, requires_superuser
from app.domain.vision.playback import read_asset
from app.domain.vision.schemas import CameraRecognitionConfig, RecognitionEvent, RecognitionHeartbeat
from app.domain.vision.services import VisionService, observation_data

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class VisionController(Controller):
    path = "/api/vision"
    tags = ["Vision Operations"]
    guards = [requires_active_user]

    @get("/dashboard")
    async def dashboard(self, db_session: AsyncSession, camera_id: int | None = None) -> dict:
        return {"data": await VisionService(db_session).dashboard(camera_id)}

    @get("/cameras/{camera_id:int}/config", guards=[requires_superuser])
    async def config(self, db_session: AsyncSession, camera_id: int) -> dict:
        camera = await VisionService(db_session).camera(camera_id)
        return {"data": camera.recognition_config or CameraRecognitionConfig().model_dump()}

    @put("/cameras/{camera_id:int}/config", guards=[requires_superuser])
    async def configure(self, db_session: AsyncSession, camera_id: int, data: CameraRecognitionConfig) -> dict:
        return {"data": await VisionService(db_session).configure(camera_id, data)}

    @post("/cameras/{camera_id:int}/heartbeat", guards=[requires_superuser])
    async def heartbeat(self, db_session: AsyncSession, camera_id: int, data: RecognitionHeartbeat) -> dict:
        await VisionService(db_session).heartbeat(camera_id, data)
        return {"data": {"accepted": True}}

    @post("/cameras/{camera_id:int}/observations", guards=[requires_superuser])
    async def ingest(self, db_session: AsyncSession, camera_id: int, data: RecognitionEvent) -> dict:
        row = await VisionService(db_session).ingest(camera_id, data)
        return {"data": observation_data(row)}

    @post("/observations/{observation_id:int}/attach", guards=[requires_superuser])
    async def attach(self, db_session: AsyncSession, observation_id: int) -> dict:
        row = await VisionService(db_session).attach(observation_id)
        return {"data": observation_data(row)}

    @get("/cameras/{camera_id:int}/preview")
    async def preview(self, db_session: AsyncSession, camera_id: int) -> Response:
        camera = await VisionService(db_session).camera(camera_id)
        if not camera.recognition_preview:
            raise NotFoundException(detail="尚未收到识别画面")
        return Response(camera.recognition_preview, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @get("/cameras/{camera_id:int}/stream/{asset:str}")
    async def stream(self, db_session: AsyncSession, camera_id: int, asset: str) -> Response:
        camera = await VisionService(db_session).camera(camera_id)
        content, media_type = await read_asset((camera.recognition_config or {}).get("playback_path", ""), asset)
        return Response(content, media_type=media_type, headers={"Cache-Control": "no-store"})

    @get("/observations/{observation_id:int}/evidence")
    async def evidence(self, db_session: AsyncSession, observation_id: int) -> Response:
        row = await VisionService(db_session).observation(observation_id)
        if not row.evidence_jpeg:
            raise NotFoundException(detail="该记录没有图像证据")
        return Response(row.evidence_jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
