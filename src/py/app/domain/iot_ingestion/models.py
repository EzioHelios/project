"""Persistence models for protocol-neutral IoT message ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from advanced_alchemy.base import BigIntAuditBase, BigIntBase
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.lib.tenancy import TeamScopedMixin


class MqttDataSource(TeamScopedMixin, BigIntAuditBase):
    """A tenant-owned MQTT broker connection; credentials are referenced by environment-variable names."""

    __tablename__ = "iot_mqtt_data_source"
    __table_args__ = (UniqueConstraint("team_id", "code", name="uq_iot_mqtt_data_source_team_code"),)

    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    broker_host: Mapped[str] = mapped_column(String(255))
    broker_port: Mapped[int] = mapped_column(Integer, default=1883)
    username_env: Mapped[str | None] = mapped_column(String(128))
    password_env: Mapped[str | None] = mapped_column(String(128))
    client_id: Mapped[str] = mapped_column(String(128))
    tls_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class MqttSubscription(TeamScopedMixin, BigIntAuditBase):
    """A versioned inbound MQTT topic contract."""

    __tablename__ = "iot_mqtt_subscription"
    __table_args__ = (UniqueConstraint("source_id", "topic_filter", name="uq_iot_mqtt_subscription_source_topic"),)

    source_id: Mapped[int] = mapped_column(ForeignKey("iot_mqtt_data_source.id", ondelete="CASCADE"), index=True)
    topic_filter: Mapped[str] = mapped_column(String(255))
    parser_code: Mapped[str] = mapped_column(String(64), default="szscada_scada_v1")
    contract_version: Mapped[str] = mapped_column(String(32), default="v1")
    qos: Mapped[int] = mapped_column(Integer, default=1)
    expected_interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class MqttDeviceBinding(TeamScopedMixin, BigIntAuditBase):
    """Maps one external gateway/meter selector to a platform device."""

    __tablename__ = "iot_mqtt_device_binding"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id", "gateway_key", "meter_key", name="uq_iot_mqtt_binding_subscription_gateway_meter"
        ),
    )

    subscription_id: Mapped[int] = mapped_column(ForeignKey("iot_mqtt_subscription.id", ondelete="CASCADE"), index=True)
    gateway_key: Mapped[str] = mapped_column(String(64), index=True)
    meter_key: Mapped[str] = mapped_column(String(64))
    selector_name_pattern: Mapped[str] = mapped_column(String(128))
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True
    )
    external_device_id: Mapped[str] = mapped_column(String(64), index=True)
    temporary_address: Mapped[str] = mapped_column(String(64), index=True)
    identity_status: Mapped[str] = mapped_column(String(24), default="temporary", index=True)
    scaling_mode: Mapped[str] = mapped_column(String(24), default="upstream_scaled")
    multiplier: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(1))


class MqttPointMapping(TeamScopedMixin, BigIntAuditBase):
    """Maps a source tag within a bound device to a normalized platform point."""

    __tablename__ = "iot_mqtt_point_mapping"
    __table_args__ = (
        UniqueConstraint("binding_id", "source_tag", "mapping_version", name="uq_iot_mqtt_mapping_binding_tag_version"),
    )

    binding_id: Mapped[int] = mapped_column(ForeignKey("iot_mqtt_device_binding.id", ondelete="CASCADE"), index=True)
    source_tag: Mapped[str] = mapped_column(String(64))
    source_name_suffix: Mapped[str | None] = mapped_column(String(128))
    point_code: Mapped[str] = mapped_column(String(64))
    point_name: Mapped[str | None] = mapped_column(String(128))
    unit: Mapped[str | None] = mapped_column(String(20))
    multiplier: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(1))
    mapping_version: Mapped[str] = mapped_column(String(32), default="v1")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class MqttInboundMessage(TeamScopedMixin, BigIntAuditBase):
    """Immutable raw MQTT message with processing state for replay and idempotency."""

    __tablename__ = "iot_mqtt_inbound_message"
    __table_args__ = (
        UniqueConstraint("source_id", "payload_hash", name="uq_iot_mqtt_inbound_source_payload_hash"),
        Index("ix_iot_mqtt_inbound_status_received", "team_id", "status", "received_at"),
    )

    source_id: Mapped[int] = mapped_column(ForeignKey("iot_mqtt_data_source.id", ondelete="RESTRICT"), index=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("iot_mqtt_subscription.id", ondelete="RESTRICT"), index=True
    )
    topic: Mapped[str] = mapped_column(String(255), index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    contract_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="received", index=True)
    dispatch_attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


class MeterReadingFact(TeamScopedMixin, BigIntBase):
    """Canonical meter reading fact shared by MQTT, API, and infrared ingestion."""

    __tablename__ = "metering_meter_reading_fact"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "source_system",
            "source_record_id",
            "equipment_id",
            "point_code",
            "value_kind",
            name="uq_metering_fact_source_record_point",
        ),
        Index("ix_metering_fact_equipment_time", "team_id", "equipment_id", "reading_time"),
        Index("ix_metering_fact_point_time", "team_id", "point_code", "reading_time"),
    )

    source_system: Mapped[str] = mapped_column(String(32), index=True)
    source_record_id: Mapped[str] = mapped_column(String(160), index=True)
    source_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("iot_mqtt_inbound_message.id", ondelete="SET NULL"), index=True
    )
    binding_id: Mapped[int | None] = mapped_column(
        ForeignKey("iot_mqtt_device_binding.id", ondelete="SET NULL"), index=True
    )
    equipment_id: Mapped[int] = mapped_column(ForeignKey("dataapp_monitorequipment.id", ondelete="CASCADE"), index=True)
    source_point_code: Mapped[str] = mapped_column(String(64))
    source_point_name: Mapped[str | None] = mapped_column(String(128))
    point_code: Mapped[str] = mapped_column(String(64))
    point_name: Mapped[str] = mapped_column(String(128))
    energy_direction: Mapped[str] = mapped_column(String(16))
    energy_kind: Mapped[str] = mapped_column(String(16))
    tou_period: Mapped[str] = mapped_column(String(16))
    value_kind: Mapped[str] = mapped_column(String(32), index=True)
    raw_value: Mapped[str | None] = mapped_column(String(64))
    normalized_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    unit: Mapped[str | None] = mapped_column(String(20))
    quality_status: Mapped[str] = mapped_column(String(24), index=True)
    source_type: Mapped[int | None] = mapped_column(Integer)
    reading_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    mapping_version: Mapped[str] = mapped_column(String(32))
