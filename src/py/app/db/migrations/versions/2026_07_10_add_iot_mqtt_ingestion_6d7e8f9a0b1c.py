"""add IoT MQTT ingestion tables

Revision ID: 6d7e8f9a0b1c
Revises: b1c2d3e4f5a
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "6d7e8f9a0b1c"
down_revision = "b1c2d3e4f5a"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

SOURCE_TABLE = "iot_mqtt_data_source"
SUBSCRIPTION_TABLE = "iot_mqtt_subscription"
BINDING_TABLE = "iot_mqtt_device_binding"
MAPPING_TABLE = "iot_mqtt_point_mapping"
INBOUND_TABLE = "iot_mqtt_inbound_message"
READING_TABLE = "iot_meter_point_reading"
TENANT_TABLES = (SOURCE_TABLE, SUBSCRIPTION_TABLE, BINDING_TABLE, MAPPING_TABLE, INBOUND_TABLE, READING_TABLE)


def _id_type() -> sa.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("team_id", sa.GUID(length=16), nullable=False),
        sa.Column("created_at", sa.DateTimeUTC(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTimeUTC(timezone=True), nullable=False),
    ]


def _tenant_fk(table_name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(["team_id"], ["team.id"], name=f"fk_{table_name}_team_id_team", ondelete="CASCADE")


def _enable_tenant_rls(table_name: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    policy_name = f"rls_{table_name}_tenant_scope"
    op.execute(sa.text(f"alter table {table_name} enable row level security"))
    op.execute(sa.text(f"alter table {table_name} force row level security"))
    op.execute(sa.text(f"drop policy if exists {policy_name} on {table_name}"))
    op.execute(
        sa.text(
            f"""
            create policy {policy_name} on {table_name}
            using (
                current_setting('app.tenant_bypass', true) = 'true'
                or team_id::text = nullif(current_setting('app.tenant_id', true), '')
            )
            with check (
                current_setting('app.tenant_bypass', true) = 'true'
                or team_id::text = nullif(current_setting('app.tenant_id', true), '')
            )
            """
        )
    )


def _disable_tenant_rls(table_name: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(sa.text(f"drop policy if exists rls_{table_name}_tenant_scope on {table_name}"))
    op.execute(sa.text(f"alter table {table_name} no force row level security"))
    op.execute(sa.text(f"alter table {table_name} disable row level security"))


def upgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    existing_iot_tables = existing_tables.intersection(TENANT_TABLES)
    if existing_iot_tables:
        if existing_iot_tables != set(TENANT_TABLES):
            missing = sorted(set(TENANT_TABLES) - existing_iot_tables)
            msg = f"Partial IoT schema detected; missing tables: {', '.join(missing)}"
            raise RuntimeError(msg)
        _validate_existing_schema()
        for table_name in TENANT_TABLES:
            _enable_tenant_rls(table_name)
        return

    op.create_table(
        SOURCE_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("broker_host", sa.String(length=255), nullable=False),
        sa.Column("broker_port", sa.Integer(), nullable=False, server_default="1883"),
        sa.Column("username_env", sa.String(length=128), nullable=True),
        sa.Column("password_env", sa.String(length=128), nullable=True),
        sa.Column("client_id", sa.String(length=128), nullable=False),
        sa.Column("tls_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
        _tenant_fk(SOURCE_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{SOURCE_TABLE}")),
        sa.UniqueConstraint("team_id", "code", name="uq_iot_mqtt_data_source_team_code"),
    )
    for column in ("code", "enabled", "team_id"):
        op.create_index(op.f(f"ix_{SOURCE_TABLE}_{column}"), SOURCE_TABLE, [column])
    op.alter_column(SOURCE_TABLE, "broker_port", server_default=None)
    op.alter_column(SOURCE_TABLE, "tls_enabled", server_default=None)
    op.alter_column(SOURCE_TABLE, "enabled", server_default=None)

    op.create_table(
        SUBSCRIPTION_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("source_id", _id_type(), nullable=False),
        sa.Column("topic_filter", sa.String(length=255), nullable=False),
        sa.Column("parser_code", sa.String(length=64), nullable=False, server_default="szscada_scada_v1"),
        sa.Column("contract_version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("qos", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expected_interval_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["source_id"], [f"{SOURCE_TABLE}.id"], name="fk_iot_mqtt_subscription_source", ondelete="CASCADE"
        ),
        _tenant_fk(SUBSCRIPTION_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{SUBSCRIPTION_TABLE}")),
        sa.UniqueConstraint("source_id", "topic_filter", name="uq_iot_mqtt_subscription_source_topic"),
    )
    for column in ("source_id", "enabled", "team_id"):
        op.create_index(op.f(f"ix_{SUBSCRIPTION_TABLE}_{column}"), SUBSCRIPTION_TABLE, [column])
    for column in ("parser_code", "contract_version", "qos", "expected_interval_seconds", "enabled"):
        op.alter_column(SUBSCRIPTION_TABLE, column, server_default=None)

    op.create_table(
        BINDING_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("subscription_id", _id_type(), nullable=False),
        sa.Column("gateway_key", sa.String(length=64), nullable=False),
        sa.Column("meter_key", sa.String(length=64), nullable=False),
        sa.Column("selector_name_pattern", sa.String(length=128), nullable=False),
        sa.Column("equipment_id", _id_type(), nullable=True),
        sa.Column("external_device_id", sa.String(length=64), nullable=False),
        sa.Column("temporary_address", sa.String(length=64), nullable=False),
        sa.Column("identity_status", sa.String(length=24), nullable=False, server_default="temporary"),
        sa.Column("scaling_mode", sa.String(length=24), nullable=False, server_default="upstream_scaled"),
        sa.Column("multiplier", sa.Numeric(precision=18, scale=6), nullable=False, server_default="1"),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            [f"{SUBSCRIPTION_TABLE}.id"],
            name="fk_iot_mqtt_binding_subscription",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_id"], ["dataapp_monitorequipment.id"], name="fk_iot_mqtt_binding_equipment", ondelete="SET NULL"
        ),
        _tenant_fk(BINDING_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{BINDING_TABLE}")),
        sa.UniqueConstraint(
            "subscription_id", "gateway_key", "meter_key", name="uq_iot_mqtt_binding_subscription_gateway_meter"
        ),
    )
    for column in (
        "subscription_id",
        "gateway_key",
        "equipment_id",
        "external_device_id",
        "temporary_address",
        "identity_status",
        "team_id",
    ):
        op.create_index(op.f(f"ix_{BINDING_TABLE}_{column}"), BINDING_TABLE, [column])
    for column in ("identity_status", "scaling_mode", "multiplier"):
        op.alter_column(BINDING_TABLE, column, server_default=None)

    op.create_table(
        MAPPING_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("binding_id", _id_type(), nullable=False),
        sa.Column("source_tag", sa.String(length=64), nullable=False),
        sa.Column("source_name_suffix", sa.String(length=128), nullable=True),
        sa.Column("point_code", sa.String(length=64), nullable=False),
        sa.Column("target_field", sa.String(length=64), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("multiplier", sa.Numeric(precision=18, scale=6), nullable=False, server_default="1"),
        sa.Column("mapping_version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["binding_id"], [f"{BINDING_TABLE}.id"], name="fk_iot_mqtt_mapping_binding", ondelete="CASCADE"
        ),
        _tenant_fk(MAPPING_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{MAPPING_TABLE}")),
        sa.UniqueConstraint(
            "binding_id", "source_tag", "mapping_version", name="uq_iot_mqtt_mapping_binding_tag_version"
        ),
    )
    for column in ("binding_id", "team_id"):
        op.create_index(op.f(f"ix_{MAPPING_TABLE}_{column}"), MAPPING_TABLE, [column])
    for column in ("multiplier", "mapping_version", "enabled"):
        op.alter_column(MAPPING_TABLE, column, server_default=None)

    op.create_table(
        INBOUND_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("source_id", _id_type(), nullable=False),
        sa.Column("subscription_id", _id_type(), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("contract_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="received"),
        sa.Column("dispatch_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["source_id"], [f"{SOURCE_TABLE}.id"], name="fk_iot_mqtt_inbound_source", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            [f"{SUBSCRIPTION_TABLE}.id"],
            name="fk_iot_mqtt_inbound_subscription",
            ondelete="RESTRICT",
        ),
        _tenant_fk(INBOUND_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{INBOUND_TABLE}")),
        sa.UniqueConstraint("source_id", "payload_hash", name="uq_iot_mqtt_inbound_source_payload_hash"),
    )
    for column in (
        "source_id",
        "subscription_id",
        "topic",
        "received_at",
        "published_at",
        "payload_hash",
        "status",
        "team_id",
    ):
        op.create_index(op.f(f"ix_{INBOUND_TABLE}_{column}"), INBOUND_TABLE, [column])
    op.create_index("ix_iot_mqtt_inbound_status_received", INBOUND_TABLE, ["team_id", "status", "received_at"])
    for column in ("status", "dispatch_attempts"):
        op.alter_column(INBOUND_TABLE, column, server_default=None)

    op.create_table(
        READING_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("source_message_id", _id_type(), nullable=False),
        sa.Column("binding_id", _id_type(), nullable=False),
        sa.Column("equipment_id", _id_type(), nullable=False),
        sa.Column("source_tag", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("point_code", sa.String(length=64), nullable=False),
        sa.Column("raw_value", sa.String(length=64), nullable=True),
        sa.Column("normalized_value", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("quality_status", sa.String(length=24), nullable=False),
        sa.Column("source_type", sa.Integer(), nullable=True),
        sa.Column("reading_time", sa.DateTime(), nullable=False),
        sa.Column("mapping_version", sa.String(length=32), nullable=False),
        sa.Column("team_id", sa.GUID(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_message_id"], [f"{INBOUND_TABLE}.id"], name="fk_iot_meter_reading_message", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["binding_id"], [f"{BINDING_TABLE}.id"], name="fk_iot_meter_reading_binding", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["equipment_id"], ["dataapp_monitorequipment.id"], name="fk_iot_meter_reading_equipment", ondelete="CASCADE"
        ),
        _tenant_fk(READING_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{READING_TABLE}")),
        sa.UniqueConstraint(
            "source_message_id", "binding_id", "source_tag", name="uq_iot_meter_reading_message_binding_tag"
        ),
    )
    for column in ("source_message_id", "binding_id", "equipment_id", "quality_status", "reading_time", "team_id"):
        op.create_index(op.f(f"ix_{READING_TABLE}_{column}"), READING_TABLE, [column])
    op.create_index("ix_iot_meter_reading_equipment_time", READING_TABLE, ["team_id", "equipment_id", "reading_time"])

    op.add_column("dataapp_ammeterindexvalue", sa.Column("source_message_id", _id_type(), nullable=True))
    op.add_column("dataapp_ammeterindexvalue", sa.Column("mapping_version", sa.String(length=32), nullable=True))
    op.create_foreign_key(
        "fk_dataapp_ammeterindexvalue_source_message",
        "dataapp_ammeterindexvalue",
        INBOUND_TABLE,
        ["source_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_dataapp_ammeterindexvalue_source_message_id", "dataapp_ammeterindexvalue", ["source_message_id"]
    )
    op.create_unique_constraint(
        "uq_dataapp_ammeterindexvalue_source_equipment",
        "dataapp_ammeterindexvalue",
        ["team_id", "source_message_id", "equipment_id"],
    )

    op.add_column("dataapp_iottelemetry", sa.Column("source_message_id", _id_type(), nullable=True))
    op.add_column("dataapp_iottelemetry", sa.Column("mapping_version", sa.String(length=32), nullable=True))
    op.create_foreign_key(
        "fk_dataapp_iottelemetry_source_message",
        "dataapp_iottelemetry",
        INBOUND_TABLE,
        ["source_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_dataapp_iottelemetry_source_message_id", "dataapp_iottelemetry", ["source_message_id"])
    op.create_unique_constraint(
        "uq_dataapp_iottelemetry_source_device",
        "dataapp_iottelemetry",
        ["team_id", "source_message_id", "device_id"],
    )

    for table_name in TENANT_TABLES:
        _enable_tenant_rls(table_name)


def _validate_existing_schema() -> None:
    """Validate a schema created before Alembic registration without mutating its data."""
    inspector = sa.inspect(op.get_bind())
    required_columns = {
        SOURCE_TABLE: {"id", "team_id", "code", "broker_host", "enabled"},
        SUBSCRIPTION_TABLE: {"id", "team_id", "source_id", "topic_filter", "enabled"},
        BINDING_TABLE: {"id", "team_id", "subscription_id", "equipment_id", "gateway_key", "meter_key"},
        MAPPING_TABLE: {"id", "team_id", "binding_id", "source_tag", "point_code", "target_field"},
        INBOUND_TABLE: {"id", "team_id", "source_id", "subscription_id", "payload", "payload_hash", "status"},
        READING_TABLE: {
            "id",
            "team_id",
            "source_message_id",
            "binding_id",
            "equipment_id",
            "source_tag",
            "point_code",
            "normalized_value",
            "quality_status",
            "reading_time",
        },
    }
    problems: list[str] = []
    for table_name, expected in required_columns.items():
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        missing = sorted(expected - actual)
        if missing:
            problems.append(f"{table_name}: missing {', '.join(missing)}")

    for table_name in ("dataapp_ammeterindexvalue", "dataapp_iottelemetry"):
        if table_name not in inspector.get_table_names():
            problems.append(f"{table_name}: table is missing")
            continue
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        missing = sorted({"source_message_id", "mapping_version"} - actual)
        if missing:
            problems.append(f"{table_name}: missing {', '.join(missing)}")

    if problems:
        msg = "Existing IoT schema does not match revision 6d7e8f9a0b1c: " + "; ".join(problems)
        raise RuntimeError(msg)


def downgrade() -> None:
    for table_name in reversed(TENANT_TABLES):
        _disable_tenant_rls(table_name)

    op.drop_constraint("uq_dataapp_iottelemetry_source_device", "dataapp_iottelemetry", type_="unique")
    op.drop_index("ix_dataapp_iottelemetry_source_message_id", table_name="dataapp_iottelemetry")
    op.drop_constraint("fk_dataapp_iottelemetry_source_message", "dataapp_iottelemetry", type_="foreignkey")
    op.drop_column("dataapp_iottelemetry", "mapping_version")
    op.drop_column("dataapp_iottelemetry", "source_message_id")

    op.drop_constraint("uq_dataapp_ammeterindexvalue_source_equipment", "dataapp_ammeterindexvalue", type_="unique")
    op.drop_index("ix_dataapp_ammeterindexvalue_source_message_id", table_name="dataapp_ammeterindexvalue")
    op.drop_constraint("fk_dataapp_ammeterindexvalue_source_message", "dataapp_ammeterindexvalue", type_="foreignkey")
    op.drop_column("dataapp_ammeterindexvalue", "mapping_version")
    op.drop_column("dataapp_ammeterindexvalue", "source_message_id")

    op.drop_table(READING_TABLE)
    op.drop_table(INBOUND_TABLE)
    op.drop_table(MAPPING_TABLE)
    op.drop_table(BINDING_TABLE)
    op.drop_table(SUBSCRIPTION_TABLE)
    op.drop_table(SOURCE_TABLE)
