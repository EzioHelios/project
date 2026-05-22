from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.carbon import models as m

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.anyio

# Endpoints backed by SQLAlchemy ORM models (work with test DB schema)
CARBON_ORM_ENDPOINTS: list[str] = [
    # Scope1/2/3 列表接口
    "/api/carbon/scope1-mobile-combustion",
    "/api/carbon/scope1-stationary-combustion",
    "/api/carbon/scope1-refrigerant-leak",
    "/api/carbon/scope2-electricity-bill",
    "/api/carbon/scope3-waste-disposal",
    "/api/carbon/scope3-third-party-transport",
    # 统一待审核列表
    "/api/carbon/pending",
    # 排放因子库
    "/api/carbon/emission-factors",
    # IoT 与审核日志
    "/api/carbon/iot-telemetry",
    "/api/carbon/audit-logs",
]

# Endpoints that query raw SQL database views (require legacy views in DB)
CARBON_VIEW_ENDPOINTS: list[str] = [
    "/api/page1/ydfdzl/day",
    "/api/page1/yjzl/day",
    "/api/page2/spgl",
    "/api/page3/cnsy",
    "/api/page4/tpfltj",
]


async def test_carbon_orm_endpoints_return_json(client: AsyncClient) -> None:
    """连通性测试：ORM 端点不应返回 5xx。"""
    for path in CARBON_ORM_ENDPOINTS:
        response = await client.get(path)
        assert response.status_code < 500, f"{path} 返回 {response.status_code}"
        if response.content:
            _ = response.json()


async def test_carbon_view_endpoints_return_json(client: AsyncClient) -> None:
    """连通性测试：大屏视图端点应优雅处理视图不存在的情况。

    这些端点查询数据库视图（如 yj_day_sum_view），在测试数据库中不存在。
    当前预期行为是返回 500（因 controller 缺少错误处理），标记为 xfail。
    """
    for path in CARBON_VIEW_ENDPOINTS:
        response = await client.get(path)
        # 这些端点查询不存在的视图会 500，这是已知的 controller 层缺陷
        # 当 controller 加上错误处理后，应改为 assert < 500
        assert response.status_code < 500, f"{path} 返回 {response.status_code}"


async def test_device_types_endpoint_seeds_defaults(client: AsyncClient) -> None:
    response = await client.get("/api/data/device-types")

    assert response.status_code == 200
    payload = response.json()
    codes = {item["code"] for item in payload["items"]}
    assert {"meter", "pv_inverter", "storage_bms", "charger", "camera"}.issubset(codes)


async def test_monitor_equipment_create_backfills_category_and_default_points(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    sector = m.MonitorSector(code="A-01", name="一区")
    session.add(sector)
    await session.commit()
    await session.refresh(sector)

    await client.get("/api/data/device-types")
    response = await client.post(
        "/api/data/monitor-equipments",
        json={
            "code": "METER-001",
            "name": "一号总表",
            "device_type_id": 1,
            "sector_id": sector.id,
            "warehouse_code": "WH-01",
            "running_status": "正常使用",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["device_type_id"] == 1
    assert data["category"] == 0
    assert data["external_device_id"] == "METER-001"

    point_response = await client.get("/api/data/device-points", params={"device_id": data["id"]})
    assert point_response.status_code == 200
    point_codes = {item["point_code"] for item in point_response.json()["items"]}
    assert point_codes == {"active_power", "voltage_a", "current_a", "total_energy"}


async def test_monitor_equipment_create_preserves_asset_code(client: AsyncClient, session: AsyncSession) -> None:
    sector = m.MonitorSector(code="A-11", name="十一区")
    session.add(sector)
    await session.commit()
    await session.refresh(sector)

    response = await client.post(
        "/api/data/monitor-equipments",
        json={
            "code": "FORK-001",
            "name": "叉车一号",
            "asset_code": "厂(场)内苏M00001",
            "device_type_id": 5,
            "sector_id": sector.id,
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["asset_code"] == "厂(场)内苏M00001"
    assert data["external_device_id"] == "FORK-001"


async def test_iot_telemetry_resolves_monitor_equipment_by_external_device_id(client: AsyncClient, session: AsyncSession) -> None:
    equipment = m.MonitorEquipment(
        code="METER-010",
        name="十号总表",
        external_device_id="mqtt-meter-010",
        asset_code="ASSET-010",
    )
    telemetry = m.IotTelemetry(
        site_id="site-a",
        device_id="mqtt-meter-010",
        ts=1710000000,
        reading_time=datetime.datetime.utcnow(),
        active_power=12.5,
        total_energy=345.6,
        interval="raw",
    )
    session.add(equipment)
    session.add(telemetry)
    await session.commit()

    response = await client.get("/api/carbon/iot-telemetry", params={"device_id": "mqtt-meter-010"})

    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["equipment_code"] == "METER-010"
    assert row["equipment_name"] == "十号总表"
    assert row["external_device_id"] == "mqtt-meter-010"


async def test_device_point_duplicate_code_is_rejected(client: AsyncClient, session: AsyncSession) -> None:
    sector = m.MonitorSector(code="A-02", name="二区")
    session.add(sector)
    await session.commit()
    await session.refresh(sector)

    await client.get("/api/data/device-types")
    create_equipment = await client.post(
        "/api/data/monitor-equipments",
        json={
            "code": "METER-002",
            "name": "二号总表",
            "device_type_id": 1,
            "sector_id": sector.id,
            "warehouse_code": "WH-02",
            "running_status": "正常使用",
        },
    )
    equipment_id = create_equipment.json()["data"]["id"]

    response = await client.post(
        "/api/data/device-points",
        json={
            "device_id": equipment_id,
            "point_code": "active_power",
            "point_name": "重复有功功率",
            "value_type": "float",
        },
    )

    assert response.status_code == 400
    assert response.json()["msg"] == "同一设备下测点编码不能重复"


async def test_alarm_rule_and_event_status_flow(client: AsyncClient, session: AsyncSession) -> None:
    sector = m.MonitorSector(code="A-03", name="三区")
    session.add(sector)
    await session.commit()
    await session.refresh(sector)

    await client.get("/api/data/device-types")
    create_equipment = await client.post(
        "/api/data/monitor-equipments",
        json={
            "code": "BMS-001",
            "name": "一号储能",
            "device_type_id": 3,
            "sector_id": sector.id,
            "warehouse_code": "WH-03",
            "running_status": "正常使用",
        },
    )
    equipment_id = create_equipment.json()["data"]["id"]

    rule_response = await client.post(
        "/api/data/warning-rules",
        json={
            "name": "SOC 低告警",
            "event_type": 1,
            "equipment_id": equipment_id,
            "point_code": "soc",
            "alarm_code": "soc_low",
            "alarm_name": "SOC 低告警",
            "alarm_level": "critical",
            "is_enabled": True,
        },
    )
    assert rule_response.status_code == 201
    rule_id = rule_response.json()["data"]["id"]

    event = m.AlarmEvent(
        rule_id=rule_id,
        event_type=1,
        alarm_code="soc_low",
        alarm_name="SOC 低告警",
        alarm_level="critical",
        alarm_category="point",
        event_desc="SOC 低于阈值",
        event_time=datetime.datetime.utcnow(),
        sector_id=sector.id,
        equipment_id=equipment_id,
        point_code="soc",
        current_value=15.0,
        threshold_value=20.0,
        status="open",
        is_handle=False,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)

    acknowledge_response = await client.patch(
        f"/api/data/alarm-events/{event.id}",
        json={"status": "acknowledged", "handled_by": "tester", "handle_note": "已确认"},
    )
    assert acknowledge_response.status_code == 200

    await session.refresh(event)
    assert event.status == "acknowledged"
    assert event.is_handle is True
    assert event.resolved_at is None

    resolve_response = await client.patch(
        f"/api/data/alarm-events/{event.id}",
        json={"status": "resolved"},
    )
    assert resolve_response.status_code == 200

    await session.refresh(event)
    assert event.status == "resolved"
    assert event.is_handle is True
    assert event.resolved_at is not None

    list_response = await client.get("/api/data/alarm-events", params={"status": "resolved"})
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert any(item["id"] == event.id and item["point_code"] == "soc" and item["alarm_level"] == "critical" for item in items)
