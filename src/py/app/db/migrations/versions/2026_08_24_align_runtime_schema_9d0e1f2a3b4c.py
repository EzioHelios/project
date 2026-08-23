"""Align runtime constraints and indexes with canonical model metadata.

Revision ID: 9d0e1f2a3b4c
Revises: 8c9d0e1f2a3b
Create Date: 2026-08-24
"""

from __future__ import annotations

from alembic import op

revision = "9d0e1f2a3b4c"
down_revision = "8c9d0e1f2a3b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create model-declared constraints and normalize permission uniqueness."""
    with op.batch_alter_table("dataapp_monitorequipment") as batch_op:
        batch_op.create_foreign_key(
            "fk_dataapp_monitorequipment_device_type_id_dataapp_devicetype",
            "dataapp_devicetype",
            ["device_type_id"],
            ["id"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("dataapp_monitorsector") as batch_op:
        batch_op.create_index("ix_dataapp_monitorsector_code", ["code"])
    with op.batch_alter_table("dataapp_warningrule") as batch_op:
        batch_op.create_foreign_key(
            "fk_dataapp_warningrule_equipment_id_dataapp_monitorequipment",
            "dataapp_monitorequipment",
            ["equipment_id"],
            ["id"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("microgrid_asset_meter_binding") as batch_op:
        batch_op.create_index("ix_microgrid_asset_meter_binding_enabled", ["enabled"])
        batch_op.create_index("ix_microgrid_asset_meter_binding_role", ["role"])
    with op.batch_alter_table("permission") as batch_op:
        batch_op.drop_constraint("uq_permission_code", type_="unique")
        batch_op.drop_index("ix_permission_code_unique")
        batch_op.create_index("ix_permission_code", ["code"], unique=True)


def downgrade() -> None:
    """Reverse schema-alignment constraints and indexes."""
    with op.batch_alter_table("permission") as batch_op:
        batch_op.drop_index("ix_permission_code")
        batch_op.create_index("ix_permission_code_unique", ["code"], unique=True)
        batch_op.create_unique_constraint("uq_permission_code", ["code"])
    with op.batch_alter_table("microgrid_asset_meter_binding") as batch_op:
        batch_op.drop_index("ix_microgrid_asset_meter_binding_role")
        batch_op.drop_index("ix_microgrid_asset_meter_binding_enabled")
    with op.batch_alter_table("dataapp_warningrule") as batch_op:
        batch_op.drop_constraint(
            "fk_dataapp_warningrule_equipment_id_dataapp_monitorequipment",
            type_="foreignkey",
        )
    with op.batch_alter_table("dataapp_monitorsector") as batch_op:
        batch_op.drop_index("ix_dataapp_monitorsector_code")
    with op.batch_alter_table("dataapp_monitorequipment") as batch_op:
        batch_op.drop_constraint(
            "fk_dataapp_monitorequipment_device_type_id_dataapp_devicetype",
            type_="foreignkey",
        )
