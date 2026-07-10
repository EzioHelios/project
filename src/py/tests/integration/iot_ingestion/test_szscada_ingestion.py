from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.db import models as m
from app.domain.iot_ingestion.usecases import MqttIngestionUseCase
from app.lib.tenancy import TENANT_ID_SESSION_KEY

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
    assert await session.scalar(select(func.count()).select_from(m.MeterPointReading)) == 28
    assert await session.scalar(select(func.count()).select_from(m.AmmeterIndexValue)) == 2

    invalid_rows = (
        await session.scalars(select(m.MeterPointReading).where(m.MeterPointReading.quality_status == "invalid"))
    ).all()
    assert len(invalid_rows) == 4
    assert all(row.normalized_value == 0 for row in invalid_rows)

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
    assert await session.scalar(select(func.count()).select_from(m.AmmeterIndexValue)) == 2


async def test_existing_carbon_telemetry_is_ingested_by_the_same_mqtt_pipeline(session) -> None:
    team = m.Team(name="Legacy MQTT Tenant", slug="legacy-mqtt-tenant")
    session.add(team)
    await session.flush()
    session.info[TENANT_ID_SESSION_KEY] = team.id

    source = m.MqttDataSource(
        code="legacy-carbon-mqtt",
        name="Legacy carbon telemetry",
        broker_host="broker.example",
        client_id="legacy-carbon-ingest",
    )
    session.add(source)
    await session.flush()
    subscription = m.MqttSubscription(
        source_id=source.id,
        topic_filter="carbon/site/+/device/+/telemetry",
        parser_code="carbon_telemetry_v1",
    )
    session.add(subscription)
    await session.commit()

    payload = {
        "ts": 1_720_000_000_123,
        "values": {
            "active_power": 12.5,
            "reactive_power": 3.2,
            "voltage_a": 220.1,
            "current_a": 11.3,
            "total_energy": 456.7,
        },
    }
    use_case = MqttIngestionUseCase(session)
    message, created = await use_case.receive_message(
        source_id=source.id,
        subscription_id=subscription.id,
        topic="carbon/site/site-a/device/meter-001/telemetry",
        payload=payload,
    )
    assert created is True

    processed = await use_case.process_message(message.id)
    assert processed.status == "processed"
    telemetry = await session.scalar(select(m.IotTelemetry))
    assert telemetry is not None
    assert telemetry.site_id == "site-a"
    assert telemetry.device_id == "meter-001"
    assert telemetry.total_energy == 456.7
    assert telemetry.source_message_id == message.id

    duplicate, created_again = await use_case.receive_message(
        source_id=source.id,
        subscription_id=subscription.id,
        topic="carbon/site/site-a/device/meter-001/telemetry",
        payload=payload,
    )
    assert created_again is False
    assert duplicate.id == message.id
    assert await session.scalar(select(func.count()).select_from(m.IotTelemetry)) == 1
