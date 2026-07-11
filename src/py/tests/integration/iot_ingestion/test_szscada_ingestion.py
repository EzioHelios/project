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
