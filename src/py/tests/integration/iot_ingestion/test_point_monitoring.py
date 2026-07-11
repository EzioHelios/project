from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db import models as m
from app.domain.iot_ingestion.usecases import MqttIngestionUseCase
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

FIXTURE_PATH = Path(__file__).parents[2] / "fixtures" / "carbon" / "mqtt" / "szscada_xc_v1.json"

pytestmark = pytest.mark.anyio


async def _seed_szscada_readings(
    session: AsyncSession,
    *,
    team_id: UUID | None = None,
    team_slug: str = "monitoring-tenant",
) -> tuple[m.MqttDataSource, m.MqttSubscription]:
    if team_id is None:
        team = m.Team(name="Monitoring Tenant", slug=team_slug)
        session.add(team)
        await session.flush()
        team_id = team.id
    session.info[TENANT_ID_SESSION_KEY] = team_id

    source = m.MqttDataSource(
        code="szscada-xc",
        name="SZSCADA XC",
        broker_host="broker.example",
        client_id="test-monitoring-ingest",
    )
    session.add(source)
    await session.flush()
    subscription = m.MqttSubscription(source_id=source.id, topic_filter="szscada/xc", expected_interval_seconds=300)
    session.add(subscription)
    await session.commit()

    payload = json.loads(FIXTURE_PATH.read_text())
    use_case = MqttIngestionUseCase(session)
    message, _ = await use_case.receive_message(
        source_id=source.id,
        subscription_id=subscription.id,
        topic="szscada/xc",
        payload=payload,
    )
    await use_case.process_message(message.id)
    await session.commit()
    return source, subscription


async def test_point_monitoring_lists_latest_points_and_summary(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    source, subscription = await _seed_szscada_readings(session)

    response = await client.get(
        "/api/iot-monitoring/points",
        params={"source_id": source.id, "subscription_id": subscription.id, "limit": 100},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 28
    assert data["summary"]["total_points"] == 28
    assert data["summary"]["valid_points"] == 24
    assert data["summary"]["invalid_points"] == 4
    assert data["summary"]["latest_reading_time"] is not None
    assert "payload" not in json.dumps(data)

    first = data["items"][0]
    assert first["selection_key"] == f"{first['binding_id']}:{first['source_point_code']}:{first['mapping_version']}"
    assert first["equipment_name"]
    assert first["point_name"]
    assert not first["point_code"].startswith("tag_")
    assert first["source_message_id"] is not None


async def test_point_monitoring_filters_and_returns_series_in_ascending_order(
    client: AsyncClient,
    session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    await _seed_szscada_readings(session)
    invalid_reading = await session.scalar(
        select(m.MeterReadingFact).where(m.MeterReadingFact.quality_status == "invalid").limit(1)
    )
    assert invalid_reading is not None

    points_response = await client.get(
        "/api/iot-monitoring/points",
        params={
            "quality_status": "invalid",
            "equipment_id": invalid_reading.equipment_id,
            "keyword": invalid_reading.source_point_code,
            "limit": 100,
        },
        headers=superuser_token_headers,
    )
    assert points_response.status_code == 200
    points = points_response.json()["data"]["items"]
    assert points
    assert all(row["quality_status"] == "invalid" for row in points)
    assert all(row["equipment_id"] == invalid_reading.equipment_id for row in points)

    original_message = await session.get(m.MqttInboundMessage, invalid_reading.source_message_id)
    assert original_message is not None
    second_message = m.MqttInboundMessage(
        source_id=original_message.source_id,
        subscription_id=original_message.subscription_id,
        topic=original_message.topic,
        received_at=original_message.received_at + timedelta(minutes=5),
        published_at=original_message.published_at + timedelta(minutes=5) if original_message.published_at else None,
        payload={"test": "second-point-monitoring-sample"},
        payload_hash=f"second-point-monitoring-sample-{invalid_reading.id}",
        contract_version=original_message.contract_version,
        status="processed",
    )
    session.add(second_message)
    await session.flush()

    second_reading = m.MeterReadingFact(
        source_system=invalid_reading.source_system,
        source_record_id=f"test-second:{invalid_reading.id}",
        source_message_id=second_message.id,
        binding_id=invalid_reading.binding_id,
        equipment_id=invalid_reading.equipment_id,
        source_point_code=invalid_reading.source_point_code,
        source_point_name=invalid_reading.source_point_name,
        point_code=invalid_reading.point_code,
        point_name=invalid_reading.point_name,
        energy_direction=invalid_reading.energy_direction,
        energy_kind=invalid_reading.energy_kind,
        tou_period=invalid_reading.tou_period,
        value_kind=invalid_reading.value_kind,
        raw_value="12.34",
        normalized_value=12.34,
        unit=invalid_reading.unit,
        quality_status="valid",
        source_type=invalid_reading.source_type,
        reading_time=invalid_reading.reading_time + timedelta(minutes=5),
        mapping_version=invalid_reading.mapping_version,
    )
    session.add(second_reading)
    await session.commit()

    series_response = await client.get(
        "/api/iot-monitoring/point-series",
        params={
            "binding_id": invalid_reading.binding_id,
            "source_point_code": invalid_reading.source_point_code,
            "mapping_version": invalid_reading.mapping_version,
            "limit": 10,
        },
        headers=superuser_token_headers,
    )

    assert series_response.status_code == 200
    series = series_response.json()["data"]["items"]
    assert len(series) == 2
    assert [row["reading_time"] for row in series] == sorted(row["reading_time"] for row in series)
    assert {row["quality_status"] for row in series} == {"invalid", "valid"}


async def test_point_monitoring_is_tenant_scoped(
    client: AsyncClient,
    session: AsyncSession,
    user_token_headers: dict[str, str],
    seeded_db: None,
) -> None:
    user_team_id = UUID("97108ac1-ffcb-411d-8b1e-d9183399f63b")
    await _seed_szscada_readings(session, team_id=user_team_id)
    await _seed_szscada_readings(session, team_slug="other-monitoring-tenant")

    response = await client.get("/api/iot-monitoring/points", params={"limit": 100}, headers=user_token_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 28
    assert data["summary"]["total_points"] == 28
