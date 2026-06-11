from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from app.db import models as dbm
from app.domain.carbon import models as m
from app.lib.tenancy import DEFAULT_TENANT_ID, TENANT_BYPASS_SESSION_KEY

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

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


@pytest.fixture(autouse=True)
async def _carbon_tenant_test_context(
    client: AsyncClient,
    request: pytest.FixtureRequest,
    session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    session.add(dbm.Team(id=DEFAULT_TENANT_ID, name="Default Tenant", slug="default-tenant"))
    await session.commit()
    session.info[TENANT_BYPASS_SESSION_KEY] = True
    if request.node.name != "test_data_write_endpoints_require_superuser":
        client.headers.update(superuser_token_headers)


async def test_carbon_orm_endpoints_return_json(client: AsyncClient) -> None:
    """连通性测试: ORM 端点不应返回 5xx。"""
    for path in CARBON_ORM_ENDPOINTS:
        response = await client.get(path)
        assert response.status_code < 500, f"{path} 返回 {response.status_code}"
        if response.content:
            _ = response.json()


async def test_carbon_view_endpoints_return_json(client: AsyncClient) -> None:
    """连通性测试: 大屏视图端点应优雅处理视图不存在的情况。

    这些端点查询数据库视图(如 yj_day_sum_view), 在测试数据库中不存在。
    当前预期行为是返回 500(因 controller 缺少错误处理), 标记为 xfail。
    """
    for path in CARBON_VIEW_ENDPOINTS:
        response = await client.get(path)
        # 这些端点查询不存在的视图会 500, 这是已知的 controller 层缺陷
        # 当 controller 加上错误处理后, 应改为 assert < 500
        assert response.status_code < 500, f"{path} 返回 {response.status_code}"


async def test_device_types_endpoint_seeds_defaults(client: AsyncClient) -> None:
    response = await client.get("/api/data/device-types")

    assert response.status_code == 200
    payload = response.json()
    codes = {item["code"] for item in payload["items"]}
    assert {"meter", "pv_inverter", "storage_bms", "charger", "camera"}.issubset(codes)


async def test_data_write_endpoints_require_superuser(client: AsyncClient) -> None:
    response = await client.post("/api/data/monitor-sectors", json={"code": "SEC-01", "name": "安全一区"})
    assert response.status_code == 401


async def test_monitor_equipment_create_backfills_category_and_default_points(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict[str, str],
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
        headers=superuser_token_headers,
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


async def test_monitor_equipment_create_preserves_asset_code(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
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
        headers=superuser_token_headers,
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
        reading_time=datetime.datetime.now(datetime.UTC).replace(tzinfo=None),
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


async def test_device_point_duplicate_code_is_rejected(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
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
        headers=superuser_token_headers,
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
        headers=superuser_token_headers,
    )

    assert response.status_code == 400
    assert response.json()["msg"] == "同一设备下测点编码不能重复"


async def test_alarm_rule_and_event_status_flow(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
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
        headers=superuser_token_headers,
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
        headers=superuser_token_headers,
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
        event_time=datetime.datetime.now(datetime.UTC).replace(tzinfo=None),
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
        headers=superuser_token_headers,
    )
    assert acknowledge_response.status_code == 200

    await session.refresh(event)
    assert event.status == "acknowledged"
    assert event.is_handle is True
    assert event.resolved_at is None

    resolve_response = await client.patch(
        f"/api/data/alarm-events/{event.id}",
        json={"status": "resolved"},
        headers=superuser_token_headers,
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


async def test_master_data_area_tree_and_summary(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    create_response = await client.post(
        "/api/master-data/areas",
        json={"code": "WH-A", "name": "A仓", "area_type": "warehouse"},
        headers=superuser_token_headers,
    )
    assert create_response.status_code == 201
    area_id = create_response.json()["data"]["id"]

    child_response = await client.post(
        "/api/master-data/areas",
        json={"code": "ZONE-A1", "name": "A1库区", "parent_id": area_id, "area_type": "zone"},
        headers=superuser_token_headers,
    )
    assert child_response.status_code == 201
    child_id = child_response.json()["data"]["id"]

    tree_response = await client.get("/api/master-data/areas/tree")
    assert tree_response.status_code == 200
    tree = tree_response.json()["data"]["items"]
    assert any(node["code"] == "ROOT" for node in tree)

    summary_response = await client.get(f"/api/master-data/areas/{area_id}/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()["data"]
    assert summary["area"]["code"] == "WH-A"
    assert any(item["id"] == child_id for item in summary["children"])


async def test_master_data_area_rejects_cycle_and_delete_with_children(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    parent = m.MonitorSector(code="TREE-P", name="父区域", area_type="warehouse", path="/1/100", level=1, sort_index=0)
    child = m.MonitorSector(code="TREE-C", name="子区域", area_type="zone", path="/1/100/101", level=2, sort_index=0, parent=parent)
    session.add(parent)
    session.add(child)
    await session.commit()
    await session.refresh(parent)
    await session.refresh(child)

    cycle_response = await client.patch(
        f"/api/master-data/areas/{parent.id}",
        json={"parent_id": child.id},
        headers=superuser_token_headers,
    )
    assert cycle_response.status_code == 400
    assert cycle_response.json()["msg"] == "区域不能挂到自己的子区域下"

    delete_response = await client.delete(f"/api/master-data/areas/{parent.id}", headers=superuser_token_headers)
    assert delete_response.status_code == 400
    assert delete_response.json()["msg"] == "区域下仍有子区域，禁止删除"  # noqa: RUF001


async def test_master_data_devices_support_tree_filters_and_detail(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    warehouse = m.MonitorSector(code="FILTER-WH", name="过滤仓", area_type="warehouse", path="/900/901", level=1, sort_index=0)
    zone = m.MonitorSector(code="FILTER-ZONE", name="过滤库区", area_type="zone", path="/900/901/902", level=2, sort_index=0, parent=warehouse)
    device_type_parent = m.DeviceType(code="power", name="电力设备", is_enabled=True)
    device_type_child = m.DeviceType(code="sub-meter", name="回路电表", is_enabled=True, parent=device_type_parent)
    session.add_all([warehouse, zone, device_type_parent, device_type_child])
    await session.commit()
    await session.refresh(warehouse)
    await session.refresh(zone)
    await session.refresh(device_type_parent)
    await session.refresh(device_type_child)

    create_parent = await client.post(
        "/api/master-data/devices",
        json={"code": "CAB-001", "name": "配电柜1", "area_id": warehouse.id, "device_type_id": device_type_parent.id},
        headers=superuser_token_headers,
    )
    assert create_parent.status_code == 201
    parent_id = create_parent.json()["data"]["id"]

    create_child = await client.post(
        "/api/master-data/devices",
        json={
            "code": "METER-CHILD-01",
            "name": "回路电表1",
            "area_id": zone.id,
            "device_type_id": device_type_child.id,
            "parent_device_id": parent_id,
        },
        headers=superuser_token_headers,
    )
    assert create_child.status_code == 201
    child_id = create_child.json()["data"]["id"]

    list_response = await client.get("/api/master-data/devices", params={"area_id": warehouse.id, "device_type_id": device_type_parent.id})
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert any(item["id"] == child_id for item in items)

    detail_response = await client.get(f"/api/master-data/devices/{parent_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["device"]["code"] == "CAB-001"
    assert any(item["id"] == child_id for item in detail["children"])


async def test_master_data_device_delete_rejects_children(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    area = m.MonitorSector(code="DEL-WH", name="待删仓", area_type="warehouse", path="/1000/1001", level=1, sort_index=0)
    session.add(area)
    await session.commit()
    await session.refresh(area)
    await client.get("/api/data/device-types")

    parent = m.MonitorEquipment(code="PARENT-DEL", name="父设备", sector_id=area.id, device_type_id=1)
    child = m.MonitorEquipment(code="CHILD-DEL", name="子设备", sector_id=area.id, device_type_id=1, parent_device=parent)
    session.add_all([parent, child])
    await session.commit()
    await session.refresh(parent)

    response = await client.delete(f"/api/master-data/devices/{parent.id}", headers=superuser_token_headers)
    assert response.status_code == 400
    assert response.json()["msg"] == "设备下仍有子设备，禁止删除"  # noqa: RUF001
