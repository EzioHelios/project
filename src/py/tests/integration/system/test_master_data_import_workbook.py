from __future__ import annotations

import base64
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import func, select

from app.db import models as m
from app.domain.master_data.import_workbook import (
    build_master_data_template_bytes,
    import_master_data_workbook,
    preview_master_data_workbook,
)
from app.lib.tenancy import TENANT_ID_SESSION_KEY

pytestmark = pytest.mark.anyio


def _workbook_payload(rows_by_sheet: dict[str, list[dict[str, object]]]) -> str:
    workbook = load_workbook(BytesIO(build_master_data_template_bytes()))
    for sheet_name, rows in rows_by_sheet.items():
        sheet = workbook[sheet_name]
        keys = [str(cell.value) for cell in sheet[2] if cell.value]
        for row in rows:
            sheet.append([row.get(key) for key in keys])
    output = BytesIO()
    workbook.save(output)
    return base64.b64encode(output.getvalue()).decode("ascii")


async def test_master_data_workbook_preview_and_import_are_tenant_bound_and_idempotent(session) -> None:
    team = m.Team(name="安方中心库", slug="anfang")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id

    source = m.MqttDataSource(
        code="anfang-mqtt",
        name="安方 MQTT",
        broker_host="broker.example",
        client_id="anfang-test",
    )
    session.add(source)
    await session.flush()
    session.add(m.MqttSubscription(source_id=source.id, topic_filter="szscada/xc"))
    await session.commit()

    payload = _workbook_payload(
        {
            "01_区域": [
                {"code": "HMAZ", "name": "安方中心库", "area_type": "warehouse"},
                {"code": "HMAZ-PZK", "name": "平置库", "parent_code": "HMAZ", "area_type": "zone"},
            ],
            "02_设备设备组": [
                {
                    "code": "AF-M002",
                    "name": "安方2号-平置库东南-行",
                    "asset_kind": "meter",
                    "area_code": "HMAZ-PZK",
                    "external_device_id": "202507210255",
                    "energy_type": "electricity",
                    "protocol": "mqtt",
                },
                {
                    "code": "AF-PZK-AGV-GRP",
                    "name": "平置库AGV设备组",
                    "asset_kind": "device_group",
                    "area_code": "HMAZ-PZK",
                },
            ],
            "03_电表绑定": [
                {
                    "source_code": "anfang-mqtt",
                    "topic_filter": "szscada/xc",
                    "gateway_key": "gateway-001",
                    "meter_key": "M002",
                    "selector_name_pattern": "安方2号",
                    "equipment_code": "AF-M002",
                    "external_device_id": "202507210255",
                    "temporary_address": "TEMP-AF-M002",
                    "identity_status": "confirmed",
                }
            ],
            "04_用能系统": [{"code": "AGV", "name": "AGV作业系统", "system_type": "material_handling"}],
            "05_用能系统绑定": [
                {
                    "system_code": "AGV",
                    "equipment_code": "AF-M002",
                    "area_code": "HMAZ-PZK",
                    "confidence_level": "confirmed",
                    "is_primary": True,
                }
            ],
            "06_计量边界": [
                {
                    "code": "AF-B-M002",
                    "name": "安方2号计量边界",
                    "boundary_type": "compound_circuit",
                    "meter_equipment_code": "AF-M002",
                    "area_code": "HMAZ-PZK",
                    "use_system_code": "AGV",
                    "energy_direction": "import",
                    "include_in_scope2": True,
                    "status": "active",
                    "mapping_version": "anfang-v1",
                }
            ],
            "07_边界成员": [
                {
                    "boundary_code": "AF-B-M002",
                    "member_code": "AF-PZK-AGV-GRP",
                    "member_type": "equipment_group",
                    "equipment_code": "AF-PZK-AGV-GRP",
                    "confirmation_status": "candidate",
                }
            ],
        }
    )

    preview = await preview_master_data_workbook(session, payload)

    assert preview["valid"] is True
    assert preview["row_count"] == 9
    assert await session.scalar(select(func.count()).select_from(m.MonitorSector)) == 0

    first_import = await import_master_data_workbook(session, payload)
    second_import = await import_master_data_workbook(session, payload)

    assert first_import["row_count"] == 9
    assert await session.scalar(select(func.count()).select_from(m.MonitorSector)) == 2
    assert await session.scalar(select(func.count()).select_from(m.MonitorEquipment)) == 2
    assert await session.scalar(select(func.count()).select_from(m.MqttDeviceBinding)) == 1
    assert await session.scalar(select(func.count()).select_from(m.MeasurementBoundary)) == 1
    assert await session.scalar(select(func.count()).select_from(m.MeasurementBoundaryMember)) == 1
    assert sum(sheet["created"] for sheet in second_import["sheets"]) == 0
    assert sum(sheet["updated"] for sheet in second_import["sheets"]) == 9


async def test_master_data_workbook_preview_rejects_area_cycles(session) -> None:
    team = m.Team(name="循环校验租户", slug="cycle-check")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id
    payload = _workbook_payload(
        {
            "01_区域": [
                {"code": "A", "name": "区域A", "parent_code": "B"},
                {"code": "B", "name": "区域B", "parent_code": "A"},
            ]
        }
    )

    preview = await preview_master_data_workbook(session, payload)

    assert preview["valid"] is False
    assert any(error["message"] == "层级关系存在循环" for error in preview["errors"])
