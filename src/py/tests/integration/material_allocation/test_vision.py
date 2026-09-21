from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from litestar.exceptions import ClientException, NotFoundException
from sqlalchemy import func, select

from app.db import models as m
from app.domain.vision.schemas import CameraRecognitionConfig, RecognitionEvent, RecognitionHeartbeat
from app.domain.vision.services import VisionService, observation_status
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def configured_camera(session):
    team = m.Team(name="Vision test", slug="vision-test")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    area = m.MonitorSector(code="VISION-AREA", name="作业区")
    equipment = m.MonitorEquipment(code="VISION-FL", name="电动叉车", sector=area, is_enable=True)
    product = m.ProductionProduct(code="MAT-001", name="物资", default_unit="pcs", is_enabled=True)
    camera = m.VideoMonitor(location="测试摄像头")
    session.add_all([area, equipment, camera, product])
    await session.commit()
    service = VisionService(session)
    config = CameraRecognitionConfig(
        enabled=True,
        rtsp_url="rtsp://127.0.0.1:18115/test",
        equipment_id=equipment.id,
        area_id=area.id,
        exclusive_equipment=True,
        task_ref="TASK-001",
        material_code="MAT-001",
        batch_no="BATCH-001",
        demo_source=True,
    )
    await service.configure(camera.id, config)
    return service, camera, config


def event(**changes):
    start = datetime.now(UTC) - timedelta(seconds=15)
    return RecognitionEvent.model_validate(
        {
            "event_key": "session:1:1",
            "session_id": "session",
            "track_id": 1,
            "started_at": start,
            "ended_at": start + timedelta(seconds=10),
            "duration_seconds": 10,
            "confidence": 0.91,
            "end_reason": "idle",
            "single_subject": True,
            "model_version": "test-model",
            "config_revision": 1,
            **changes,
        }
    )


async def test_observation_idempotency_and_confirm_once(session):
    service, camera, _ = await configured_camera(session)
    data = event()
    row = await service.ingest(camera.id, data)
    assert (await service.ingest(camera.id, data)).id == row.id
    assert observation_status(row) == "pending"
    row = await service.attach(row.id)
    assert (await service.attach(row.id)).operation_id == row.operation_id
    operation = await session.get(m.MaterialHandlingOperation, row.operation_id)
    assert operation.material_code == "MAT-001"
    assert operation.data_quality == "simulated"
    assert operation.source_payload["binding"]["equipment_id"] == camera.recognition_config["equipment_id"]
    assert operation.operation_status == "draft"
    second = await service.ingest(camera.id, event(event_key="session:1:2"))
    assert (await service.attach(second.id)).operation_id == operation.id
    from app.domain.material_allocation.usecases import MaterialHandlingOperationUseCase

    await MaterialHandlingOperationUseCase(session).confirm(operation.id)
    third = await service.ingest(camera.id, event(event_key="session:1:3"))
    with pytest.raises(ClientException, match="该任务已确认"):
        await service.attach(third.id)
    assert await session.scalar(select(func.count()).select_from(m.MaterialHandlingOperation)) == 1
    dashboard = await service.dashboard(camera.id)
    assert dashboard["summary"]["pending"] == 0
    assert next(item for item in dashboard["observations"] if item["id"] == third.id)["status"] == "task_completed"


async def test_payload_conflict_config_revision_and_private_data(session):
    service, camera, config = await configured_camera(session)
    data = event()
    await service.ingest(camera.id, data)
    with pytest.raises(ClientException, match="内容不一致"):
        await service.ingest(camera.id, data.model_copy(update={"confidence": 0.8}))
    with pytest.raises(ClientException, match="配置已更新"):
        await service.configure(camera.id, config)
    dashboard = await service.dashboard(camera.id)
    assert "rtsp_url" not in dashboard["cameras"][0]["config"]
    with pytest.raises(ClientException, match="识别配置已变更"):
        await service.ingest(camera.id, event(event_key="old:1", config_revision=2))


async def test_disable_rejects_new_events_preserves_playback_and_history(session):
    service, camera, config = await configured_camera(session)
    original = event()
    row = await service.ingest(camera.id, original)
    config.enabled = False
    config.revision = 1
    config.playback_path = "warehouse/camera-1"
    updated = await service.configure(camera.id, config)
    assert updated["playback_path"] == "warehouse/camera-1"
    assert (await service.camera(camera.id)).recognition_state["status"] == "disabled"
    assert (await service.ingest(camera.id, original)).id == row.id
    with pytest.raises(ClientException, match="识别已关闭"):
        await service.ingest(camera.id, event(event_key="disabled:1", config_revision=2))
    with pytest.raises(ClientException, match="识别配置已变更"):
        await service.ingest(camera.id, event(event_key="late:1"))
    config.enabled = True
    config.revision = 2
    await service.configure(camera.id, config)
    resumed = await service.ingest(camera.id, event(event_key="resumed:1", config_revision=3))
    assert observation_status(resumed) == "pending"


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"single_subject": False}, "unassigned"),
        ({"end_reason": "left_scene"}, "incomplete"),
        ({"end_reason": "stopped"}, "incomplete"),
    ],
)
async def test_ambiguous_or_interrupted_segments_cannot_be_operations(session, changes, status):
    service, camera, _ = await configured_camera(session)
    row = await service.ingest(camera.id, event(**changes))
    assert observation_status(row) == status
    with pytest.raises(ClientException):
        await service.attach(row.id)


async def test_cross_tenant_camera_and_observation_hidden(session):
    service, camera, config = await configured_camera(session)
    row = await service.ingest(camera.id, event())
    other = m.Team(name="Other", slug="vision-other")
    session.add(other)
    await session.commit()
    session.info[TENANT_ID_SESSION_KEY] = other.id
    other_service = VisionService(session)
    with pytest.raises(NotFoundException):
        await other_service.camera(camera.id)
    with pytest.raises(NotFoundException):
        await other_service.attach(row.id)
    other_camera = m.VideoMonitor(location="Other camera", team_id=other.id)
    session.add(other_camera)
    await session.commit()
    with pytest.raises(ClientException, match="不属于当前租户"):
        await other_service.configure(other_camera.id, config)


async def test_worker_lease_and_preview(session):
    service, camera, _ = await configured_camera(session)
    data = RecognitionHeartbeat(
        session_id="worker-a",
        config_revision=1,
        status="running",
        timestamp=datetime.now(UTC),
        detected_count=1,
        working_count=1,
        frames_processed=10,
        model_version="test",
    )
    await service.heartbeat(camera.id, data)
    with pytest.raises(ClientException, match="已有运行中的识别服务"):
        await service.heartbeat(camera.id, data.model_copy(update={"session_id": "worker-b"}))
    with pytest.raises(ClientException, match="配置已变更"):
        await service.heartbeat(camera.id, data.model_copy(update={"config_revision": 2}))
