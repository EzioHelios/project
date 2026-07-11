"""drop deprecated IoT telemetry table

Revision ID: 7e8f9a0b1c2d
Revises: 6d7e8f9a0b1c
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "7e8f9a0b1c2d"
down_revision = "6d7e8f9a0b1c"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]

TABLE_NAME = "dataapp_iottelemetry"
INBOUND_TABLE = "iot_mqtt_inbound_message"


def _id_type() -> sa.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _json_type() -> sa.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _enable_tenant_rls() -> None:
    if not _is_postgresql():
        return
    op.execute(sa.text(f"alter table {TABLE_NAME} enable row level security"))
    op.execute(sa.text(f"alter table {TABLE_NAME} force row level security"))
    op.execute(
        sa.text(
            f"""
            create policy rls_{TABLE_NAME}_tenant_scope on {TABLE_NAME}
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


def upgrade() -> None:
    op.execute(sa.text(f"drop table if exists {TABLE_NAME}"))


def downgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("reading_time", sa.DateTime(), nullable=False),
        sa.Column("active_power", sa.Float(), nullable=True),
        sa.Column("reactive_power", sa.Float(), nullable=True),
        sa.Column("voltage_a", sa.Float(), nullable=True),
        sa.Column("current_a", sa.Float(), nullable=True),
        sa.Column("total_energy", sa.Float(), nullable=True),
        sa.Column("interval", sa.String(length=8), nullable=False),
        sa.Column("raw_payload", _json_type(), nullable=True, comment="原始 JSON 报文"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("team_id", sa.GUID(length=16), nullable=False),
        sa.Column("source_message_id", _id_type(), nullable=True),
        sa.Column("mapping_version", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], name=f"fk_{TABLE_NAME}_team_id_team", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            [f"{INBOUND_TABLE}.id"],
            name=f"fk_{TABLE_NAME}_source_message",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{TABLE_NAME}")),
        sa.UniqueConstraint("team_id", "source_message_id", "device_id", name=f"uq_{TABLE_NAME}_source_device"),
    )
    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.create_index(batch_op.f(f"ix_{TABLE_NAME}_device_id"), ["device_id"], unique=False)
        batch_op.create_index(batch_op.f(f"ix_{TABLE_NAME}_reading_time"), ["reading_time"], unique=False)
        batch_op.create_index(batch_op.f(f"ix_{TABLE_NAME}_site_id"), ["site_id"], unique=False)
        batch_op.create_index(batch_op.f(f"ix_{TABLE_NAME}_team_id"), ["team_id"], unique=False)
        batch_op.create_index(batch_op.f(f"ix_{TABLE_NAME}_source_message_id"), ["source_message_id"], unique=False)
    _enable_tenant_rls()
