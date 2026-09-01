from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import func, select

from app.db import models as m
from app.domain.iot_ingestion.usecases import MqttIngestionUseCase
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

FIXTURE_PATH = Path(__file__).parents[2] / "fixtures" / "carbon" / "mqtt" / "szscada_xc_v1.json"

pytestmark = pytest.mark.anyio


async def test_szscada_message_is_durable_idempotent_and_projects_valid_totals(session) -> None:
    team = m.Team(name="MQTT Tenant", slug="mqtt-tenant")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id

    source = m.MqttDataSource(
        code="szscada-xc",
        name="SZSCADA XC",
        broker_host="broker.example",
        client_id="test-mqtt-ingest",
    )
    session.add(source)
    await session.flush()
    subscription = m.MqttSubscription(source_id=source.id, topic_filter="szscada/xc")
    session.add(subscription)
    await session.commit()

    payload = json.loads(FIXTURE_PATH.read_text())
    use_case = MqttIngestionUseCase(session)
    message, created = await use_case.receive_message(
        source_id=source.id,
        subscription_id=subscription.id,
        topic="szscada/xc",
        payload=payload,
    )
    assert created is True

    processed = await use_case.process_message(message.id)
    assert processed.status == "processed"

    assert await session.scalar(select(func.count()).select_from(m.MqttDeviceBinding)) == 3
    assert await session.scalar(select(func.count()).select_from(m.MeterReadingFact)) == 28

    invalid_rows = (
        await session.scalars(select(m.MeterReadingFact).where(m.MeterReadingFact.quality_status == "invalid"))
    ).all()
    assert len(invalid_rows) == 4
    assert all(row.normalized_value == 0 for row in invalid_rows)
    assert {row.point_code for row in invalid_rows} <= {
        "forward_active_total",
        "forward_active_sharp",
        "forward_active_peak",
        "forward_active_flat",
        "forward_active_valley",
        "forward_reactive_total",
        "forward_reactive_sharp",
        "forward_reactive_peak",
        "forward_reactive_flat",
        "forward_reactive_valley",
        "reverse_active_total",
        "reverse_active_sharp",
        "reverse_active_peak",
        "reverse_active_flat",
        "reverse_active_valley",
        "reverse_reactive_total",
        "reverse_reactive_sharp",
        "reverse_reactive_peak",
        "reverse_reactive_flat",
        "reverse_reactive_valley",
    }

    bindings = (await session.scalars(select(m.MqttDeviceBinding).order_by(m.MqttDeviceBinding.meter_key))).all()
    assert [binding.temporary_address for binding in bindings] == [
        "TEMP-SZXC-gateway-fixture-001-M001",
        "TEMP-SZXC-gateway-fixture-001-M002",
        "TEMP-SZXC-gateway-fixture-001-M004",
    ]

    duplicate, created_again = await use_case.receive_message(
        source_id=source.id,
        subscription_id=subscription.id,
        topic="szscada/xc",
        payload=payload,
    )
    assert created_again is False
    assert duplicate.id == message.id
    assert await session.scalar(select(func.count()).select_from(m.MqttInboundMessage)) == 1
    assert await session.scalar(select(func.count()).select_from(m.MeterReadingFact)) == 28


async def test_mqtt_test_message_projects_to_bound_device_point(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    team = m.Team(name="MQTT Test Tenant", slug="mqtt-test-tenant")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id

    area = m.MonitorSector(code="ROOT", name="测试厂区", area_type="site", path="/ROOT", level=0)
    source = m.MqttDataSource(
        code="test-source",
        name="测试 MQTT 网关",
        broker_host="127.0.0.1",
        client_id="test-source-client",
    )
    session.add_all([area, source])
    await session.flush()
    equipment = m.MonitorEquipment(
        code="METER-001",
        name="总进线电表",
        sector_id=area.id,
        category=0,
        protocol="mqtt",
        data_acquisition_method="mqtt",
        external_device_id="WH-TEST-M001",
        is_enable=True,
    )
    session.add(equipment)
    await session.flush()
    subscription = m.MqttSubscription(
        source_id=source.id,
        topic_filter="woheng/test/meters/+/telemetry",
        parser_code="szscada_scada_v1",
    )
    session.add(subscription)
    await session.flush()
    binding = m.MqttDeviceBinding(
        subscription_id=subscription.id,
        gateway_key="WH-GW-TEST",
        meter_key="m001",
        selector_name_pattern="总进线电表*",
        equipment_id=equipment.id,
        external_device_id="WH-TEST-M001",
        temporary_address="001",
        identity_status="confirmed",
    )
    session.add(binding)
    await session.flush()
    session.add(
        m.MqttPointMapping(
            binding_id=binding.id,
            source_tag="EPI",
            source_name_suffix="正向有功总电能",
            point_code="forward_active_total",
            point_name="正向有功总电能",
            unit="kWh",
            mapping_version="v1",
            enabled=True,
        )
    )
    await session.commit()

    response = await client.post(
        "/api/iot-ingestion/mqtt-test-messages",
        json={"binding_id": binding.id, "source_tag": "EPI", "value": "901.25"},
        headers={**superuser_token_headers, "X-Team-Id": str(team.id)},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["message"]["status"] == "processed"
    assert data["reading_count"] == 1
    reading = data["readings"][0]
    assert reading["equipment_id"] == equipment.id
    assert reading["source_point_code"] == "EPI"
    assert reading["point_code"] == "forward_active_total"
    assert reading["normalized_value"] == 901.25
