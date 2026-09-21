# ruff: noqa: RUF001
"""Persist observations and explicitly associate them with material operations."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from litestar.exceptions import ClientException, NotFoundException
from sqlalchemy import select

from app.db import models as m
from app.domain.material_allocation.schemas import OperationCreate
from app.domain.material_allocation.usecases import MaterialHandlingOperationUseCase
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.vision.schemas import CameraRecognitionConfig, RecognitionEvent, RecognitionHeartbeat

MAX_JPEG_BYTES = 450000


def decode_jpeg(value: str | None) -> bytes | None:
    if not value:
        return None
    try:
        image = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise ClientException(detail="识别图像编码无效") from exc
    if len(image) > MAX_JPEG_BYTES or not image.startswith(b"\xff\xd8") or not image.endswith(b"\xff\xd9"):
        raise ClientException(detail="识别图像必须是小于 450KB 的 JPEG")
    return image


def observation_status(row: m.VisionObservation) -> str:
    if row.operation_id:
        return "linked"
    config = row.binding_snapshot
    if row.end_reason != "idle":
        return "incomplete"
    if (
        row.single_subject
        and config.get("exclusive_equipment")
        and config.get("equipment_id")
        and config.get("area_id")
        and config.get("task_ref")
        and config.get("material_code")
        and config.get("batch_no")
    ):
        return "pending"
    return "unassigned"


def observation_data(row: m.VisionObservation) -> dict[str, Any]:
    config = row.binding_snapshot
    return {
        "id": row.id,
        "camera_id": row.camera_id,
        "track_id": row.track_id,
        "started_at": row.started_at.isoformat(),
        "ended_at": row.ended_at.isoformat(),
        "duration_seconds": row.duration_seconds,
        "confidence": row.confidence,
        "end_reason": row.end_reason,
        "status": observation_status(row),
        "equipment_name": config.get("equipment_name"),
        "material_name": config.get("material_name") or config.get("material_code"),
        "material_code": config.get("material_code"),
        "batch_no": config.get("batch_no"),
        "task_ref": config.get("task_ref"),
        "demo_source": config.get("demo_source", False),
        "operation_id": row.operation_id,
        "has_evidence": bool(row.evidence_jpeg),
        "model_version": row.model_version,
    }


class VisionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tenant_id = require_session_tenant_id(session)

    async def camera(self, camera_id: int, *, lock: bool = False) -> m.VideoMonitor:
        query = select(m.VideoMonitor).where(m.VideoMonitor.id == camera_id, m.VideoMonitor.team_id == self.tenant_id)
        if lock:
            query = query.with_for_update()
        row = await self.session.scalar(query)
        if row is None:
            raise NotFoundException(detail="摄像头不存在")
        return row

    async def configure(self, camera_id: int, data: CameraRecognitionConfig) -> dict[str, Any]:
        camera = await self.camera(camera_id, lock=True)
        previous = camera.recognition_config or {}
        if data.revision != previous.get("revision", 0):
            raise ClientException(status_code=409, detail="配置已更新，请刷新后重试")
        config = data.model_dump()
        config["revision"] = previous.get("revision", 0) + 1
        if data.equipment_id:
            equipment = await self.session.scalar(
                select(m.MonitorEquipment).where(
                    m.MonitorEquipment.id == data.equipment_id, m.MonitorEquipment.team_id == self.tenant_id
                )
            )
            if equipment is None:
                raise ClientException(detail="关联设备不属于当前租户")
            if data.area_id and equipment.sector_id != data.area_id:
                raise ClientException(detail="设备不属于所选区域")
            config["equipment_name"] = equipment.name
            config["equipment_code"] = equipment.code
        if data.area_id:
            area = await self.session.scalar(
                select(m.MonitorSector).where(
                    m.MonitorSector.id == data.area_id, m.MonitorSector.team_id == self.tenant_id
                )
            )
            if area is None:
                raise ClientException(detail="所属区域不属于当前租户")
            config["area_name"] = area.name
            config["area_code"] = area.code
        if data.exclusive_equipment and not data.equipment_id:
            raise ClientException(detail="单设备监控必须关联设备")
        if data.material_code:
            material = await self.session.scalar(
                select(m.ProductionProduct).where(
                    m.ProductionProduct.team_id == self.tenant_id,
                    m.ProductionProduct.code == data.material_code,
                    m.ProductionProduct.is_enabled.is_(True),
                )
            )
            if material is None:
                raise ClientException(detail="请选择当前租户的有效物资")
            config["material_name"] = material.name
            config["unit"] = material.default_unit
        camera.recognition_config = config
        camera.recognition_state = {
            "status": "awaiting_worker" if data.enabled else "disabled",
            "config_revision": config["revision"],
        }
        camera.recognition_preview = None
        await self.session.commit()
        return config

    async def heartbeat(self, camera_id: int, data: RecognitionHeartbeat) -> None:
        camera = await self.camera(camera_id, lock=True)
        config = camera.recognition_config or {}
        if data.config_revision != config.get("revision") or not config.get("enabled"):
            raise ClientException(status_code=409, detail="摄像头配置已变更")
        state = camera.recognition_state or {}
        last_seen = datetime.fromisoformat(state["received_at"]) if state.get("received_at") else None
        if (
            state.get("session_id") not in (None, data.session_id)
            and state.get("status") == "running"
            and last_seen
            and datetime.now(UTC) - last_seen < timedelta(seconds=20)
        ):
            raise ClientException(status_code=409, detail="摄像头已有运行中的识别服务")
        camera.recognition_state = {
            **data.model_dump(mode="json", exclude={"preview_jpeg"}),
            "received_at": datetime.now(UTC).isoformat(),
        }
        if data.preview_jpeg:
            camera.recognition_preview = decode_jpeg(data.preview_jpeg)
        await self.session.commit()

    async def ingest(self, camera_id: int, data: RecognitionEvent) -> m.VisionObservation:
        camera = await self.camera(camera_id, lock=True)
        fingerprint = hashlib.sha256(
            json.dumps(data.model_dump(mode="json", exclude={"evidence_jpeg"}), sort_keys=True).encode()
        ).hexdigest()
        row = await self.session.scalar(
            select(m.VisionObservation).where(
                m.VisionObservation.team_id == self.tenant_id, m.VisionObservation.event_key == data.event_key
            )
        )
        if row:
            if row.camera_id != camera_id or row.binding_snapshot.get("payload_hash") != fingerprint:
                raise ClientException(status_code=409, detail="识别记录标识对应的内容不一致")
            return row
        config = dict(camera.recognition_config or {})
        if config.get("revision") != data.config_revision:
            raise ClientException(status_code=409, detail="识别配置已变更，该片段不再接收")
        if not config.get("enabled"):
            raise ClientException(status_code=409, detail="识别已关闭，该片段不再接收")
        config.pop("rtsp_url", None)
        config["payload_hash"] = fingerprint
        row = m.VisionObservation(
            team_id=self.tenant_id,
            camera_id=camera.id,
            **data.model_dump(exclude={"config_revision", "evidence_jpeg"}),
            binding_snapshot=config,
            evidence_jpeg=decode_jpeg(data.evidence_jpeg),
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def observation(self, observation_id: int, *, lock: bool = False) -> m.VisionObservation:
        query = select(m.VisionObservation).where(
            m.VisionObservation.id == observation_id, m.VisionObservation.team_id == self.tenant_id
        )
        if lock:
            query = query.with_for_update()
        row = await self.session.scalar(query)
        if row is None:
            raise NotFoundException(detail="识别记录不存在")
        return row

    async def attach(self, observation_id: int) -> m.VisionObservation:
        row = await self.observation(observation_id, lock=True)
        if row.operation_id:
            return row
        if observation_status(row) != "pending":
            raise ClientException(detail="仅可选取关联完整、正常结束的单目标观测")
        config = row.binding_snapshot
        product = await self.session.scalar(
            select(m.ProductionProduct).where(
                m.ProductionProduct.team_id == self.tenant_id,
                m.ProductionProduct.code == config["material_code"],
                m.ProductionProduct.is_enabled.is_(True),
            )
        )
        if product is None:
            raise ClientException(detail="请先维护该物资主数据")
        usecase = MaterialHandlingOperationUseCase(self.session)
        await usecase.references(config["equipment_id"], product.id)
        task_key = f"task:{config['task_ref']}"
        operation = await self.session.scalar(
            select(m.MaterialHandlingOperation)
            .where(
                m.MaterialHandlingOperation.team_id == self.tenant_id,
                m.MaterialHandlingOperation.source_system == "vision",
                m.MaterialHandlingOperation.source_record_id == task_key,
            )
            .with_for_update()
        )
        active = [{"start": row.started_at.isoformat(), "end": row.ended_at.isoformat()}]
        if operation:
            if operation.operation_status != "draft":
                raise ClientException(status_code=409, detail="该任务已确认，请配置下一项任务")
            binding = operation.source_payload["binding"]
            keys = (
                "equipment_id",
                "material_code",
                "batch_no",
                "operation_type",
                "quantity",
                "unit",
                "weight_kg",
                "revision",
            )
            if (
                any(binding.get(key) != config.get(key) for key in keys)
                or operation.source_payload["camera_id"] != row.camera_id
            ):
                raise ClientException(status_code=409, detail="观测配置与作业任务不一致")
            await usecase.append_observed_intervals(operation.id, active)
        else:
            command = OperationCreate(
                operation_no=f"VIS-{row.id}",
                operation_type=config["operation_type"],
                equipment_id=config["equipment_id"],
                equipment_type=config["equipment_type"],
                material_id=product.id,
                batch_no=config["batch_no"],
                quantity=config["quantity"],
                weight_kg=config.get("weight_kg"),
                active_intervals=active,
            )
            operation = await usecase.receive(
                command,
                source_system="vision",
                source_record_id=task_key,
                data_quality="simulated" if config.get("demo_source") else "vision_confirmed",
                source_payload={"binding": config, "camera_id": row.camera_id},
            )
        row.operation_id = operation.id
        await self.session.commit()
        return row

    async def dashboard(self, camera_id: int | None = None) -> dict[str, Any]:
        cameras = list(
            (
                await self.session.scalars(
                    select(m.VideoMonitor).where(m.VideoMonitor.team_id == self.tenant_id).order_by(m.VideoMonitor.id)
                )
            ).all()
        )
        now = datetime.now(UTC)
        items = []
        for camera in cameras:
            config = camera.recognition_config or {}
            state = dict(camera.recognition_state or {})
            received = datetime.fromisoformat(state["received_at"]) if state.get("received_at") else None
            if state.get("status") == "running" and (received is None or now - received > timedelta(seconds=20)):
                state["status"] = "offline"
            items.append(
                {
                    "id": camera.id,
                    "name": camera.location or f"摄像头 {camera.id}",
                    "area_name": config.get("area_name") or camera.f_area,
                    "config": {key: value for key, value in config.items() if key != "rtsp_url"},
                    "state": state,
                }
            )
        query = select(m.VisionObservation).where(
            m.VisionObservation.team_id == self.tenant_id, m.VisionObservation.started_at >= now - timedelta(hours=24)
        )
        if camera_id is not None:
            await self.camera(camera_id)
            query = query.where(m.VisionObservation.camera_id == camera_id)
        rows = list((await self.session.scalars(query.order_by(m.VisionObservation.started_at.desc()))).all())
        task_keys = {
            f"task:{row.binding_snapshot.get('task_ref')}" for row in rows if row.binding_snapshot.get("task_ref")
        }
        consumed = (
            set(
                (
                    await self.session.scalars(
                        select(m.MaterialHandlingOperation.source_record_id).where(
                            m.MaterialHandlingOperation.team_id == self.tenant_id,
                            m.MaterialHandlingOperation.source_system == "vision",
                            m.MaterialHandlingOperation.operation_status == "confirmed",
                            m.MaterialHandlingOperation.source_record_id.in_(task_keys),
                        )
                    )
                ).all()
            )
            if task_keys
            else set()
        )
        observations = []
        for row in rows:
            item = observation_data(row)
            if item["status"] == "pending" and f"task:{item['task_ref']}" in consumed:
                item["status"] = "task_completed"
            observations.append(item)
        buckets = {str(hour): 0.0 for hour in range(24)}
        # UTC hour keys keep aggregation independent of the host's timezone.
        for row in rows:
            start = max(row.started_at, now - timedelta(hours=24))
            end = row.ended_at
            while start < end:
                boundary = start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                chunk_end = min(boundary, end)
                buckets[str(start.astimezone(UTC).hour)] += (chunk_end - start).total_seconds() / 60
                start = chunk_end
        return {
            "cameras": items,
            "observations": observations[:100],
            "summary": {
                "observations": len(rows),
                "duration_minutes": round(sum(row.duration_seconds for row in rows) / 60, 2),
                "linked": sum(row.operation_id is not None for row in rows),
                "pending": sum(item["status"] == "pending" for item in observations),
            },
            "hourly": [{"hour_utc": int(hour), "minutes": round(minutes, 2)} for hour, minutes in buckets.items()],
        }
