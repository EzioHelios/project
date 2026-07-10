"""SAQ tasks for durable MQTT ingestion."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.config import alchemy
from app.db import models as m
from app.domain.iot_ingestion.usecases import MqttIngestionUseCase
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY, TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from saq.types import Context


logger = logging.getLogger(__name__)
RETRY_BATCH_SIZE = 100


async def ingest_mqtt_message(
    _: Context,
    *,
    team_id: str,
    source_id: int,
    subscription_id: int,
    topic: str,
    payload: dict,
) -> None:
    """Persist one broker-delivered message, then run its idempotent projection."""
    async with alchemy.get_session() as session:
        session.info[TENANT_ID_SESSION_KEY] = UUID(team_id)
        use_case = MqttIngestionUseCase(session)
        message, _created = await use_case.receive_message(
            source_id=source_id,
            subscription_id=subscription_id,
            topic=topic,
            payload=payload,
        )
        await use_case.process_message(message.id)


async def retry_pending_mqtt_messages(_: Context) -> None:
    """Retry messages that were persisted but not projected because a worker stopped mid-flight."""
    async with alchemy.get_session() as lookup_session:
        lookup_session.info[TENANT_BYPASS_SESSION_KEY] = True
        pending = (
            await lookup_session.execute(
                select(m.MqttInboundMessage.id, m.MqttInboundMessage.team_id)
                .where(m.MqttInboundMessage.status == "received")
                .order_by(m.MqttInboundMessage.received_at.asc())
                .limit(RETRY_BATCH_SIZE)
            )
        ).all()

    for message_id, team_id in pending:
        try:
            async with alchemy.get_session() as session:
                session.info[TENANT_ID_SESSION_KEY] = team_id
                await MqttIngestionUseCase(session).process_message(message_id)
        except Exception:
            logger.exception("MQTT pending message projection failed: message_id=%s", message_id)
