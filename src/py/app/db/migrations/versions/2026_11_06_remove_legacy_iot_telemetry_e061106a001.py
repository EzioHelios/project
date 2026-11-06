"""Remove the retired IoT telemetry table and reconcile model indexes.

Revision ID: e061106a001
Revises: d061106a001
Create Date: 2026-11-06
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID
from alembic import op

sa.GUID = GUID  # pyright: ignore[attr-defined]

revision = "e061106a001"
down_revision = "d061106a001"
branch_labels = None
depends_on = None

LEGACY_TABLE = "dataapp_iottelemetry"


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(index["name"] == index_name for index in sa.inspect(op.get_bind()).get_indexes(table_name))


def upgrade() -> None:
    """Remove the unused compatibility table and align physical index names."""
    if _table_exists(LEGACY_TABLE):
        op.drop_table(LEGACY_TABLE)

    if not _index_exists("carbon_material_allocation_run", "ix_carbon_material_allocation_run_equipment_id"):
        op.create_index(
            "ix_carbon_material_allocation_run_equipment_id",
            "carbon_material_allocation_run",
            ["equipment_id"],
        )

    if _index_exists("dataapp_materialhandlingoperation", "ix_handling_material"):
        op.drop_index("ix_handling_material", table_name="dataapp_materialhandlingoperation")
    if not _index_exists("dataapp_materialhandlingoperation", "ix_dataapp_materialhandlingoperation_material_id"):
        op.create_index(
            "ix_dataapp_materialhandlingoperation_material_id",
            "dataapp_materialhandlingoperation",
            ["material_id"],
        )

    if not _index_exists("decarbonization_ccer_dossier", "ix_decarbonization_ccer_dossier_team_id"):
        op.create_index(
            "ix_decarbonization_ccer_dossier_team_id",
            "decarbonization_ccer_dossier",
            ["team_id"],
        )


def downgrade() -> None:
    """Restore the retired compatibility table and previous index layout."""
    if _index_exists("decarbonization_ccer_dossier", "ix_decarbonization_ccer_dossier_team_id"):
        op.drop_index("ix_decarbonization_ccer_dossier_team_id", table_name="decarbonization_ccer_dossier")

    if _index_exists("dataapp_materialhandlingoperation", "ix_dataapp_materialhandlingoperation_material_id"):
        op.drop_index(
            "ix_dataapp_materialhandlingoperation_material_id",
            table_name="dataapp_materialhandlingoperation",
        )
    if not _index_exists("dataapp_materialhandlingoperation", "ix_handling_material"):
        op.create_index("ix_handling_material", "dataapp_materialhandlingoperation", ["material_id"])

    if _index_exists("carbon_material_allocation_run", "ix_carbon_material_allocation_run_equipment_id"):
        op.drop_index(
            "ix_carbon_material_allocation_run_equipment_id",
            table_name="carbon_material_allocation_run",
        )

    if not _table_exists(LEGACY_TABLE):
        op.create_table(
            LEGACY_TABLE,
            sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
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
            sa.Column("raw_payload", sa.JSON(), nullable=True, comment="原始 JSON 报文"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("team_id", sa.GUID(length=16), nullable=False),
            sa.Column("source_message_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
            sa.Column("mapping_version", sa.String(length=32), nullable=True),
            sa.ForeignKeyConstraint(
                ["team_id"], ["team.id"], name="fk_dataapp_iottelemetry_team_id_team", ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["source_message_id"],
                ["iot_mqtt_inbound_message.id"],
                name="fk_dataapp_iottelemetry_source_message",
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_dataapp_iottelemetry"),
            sa.UniqueConstraint(
                "team_id",
                "source_message_id",
                "device_id",
                name="uq_dataapp_iottelemetry_source_device",
            ),
        )
        op.create_index("ix_dataapp_iottelemetry_device_id", LEGACY_TABLE, ["device_id"])
        op.create_index("ix_dataapp_iottelemetry_reading_time", LEGACY_TABLE, ["reading_time"])
        op.create_index("ix_dataapp_iottelemetry_site_id", LEGACY_TABLE, ["site_id"])
        op.create_index("ix_dataapp_iottelemetry_team_id", LEGACY_TABLE, ["team_id"])
        op.create_index("ix_dataapp_iottelemetry_source_message_id", LEGACY_TABLE, ["source_message_id"])
