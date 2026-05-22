"""add external device id and backfill asset code

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-05-22
"""

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dataapp_monitorequipment", sa.Column("external_device_id", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_dataapp_monitorequipment_external_device_id"), "dataapp_monitorequipment", ["external_device_id"])

    op.execute(
        sa.text(
            """
            update dataapp_monitorequipment
            set asset_code = coalesce(nullif(asset_code, ''), nullif(code2, ''))
            where coalesce(nullif(code2, ''), '') <> ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            update dataapp_monitorequipment
            set external_device_id = coalesce(nullif(external_device_id, ''), nullif(code, ''))
            where coalesce(nullif(code, ''), '') <> ''
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_dataapp_monitorequipment_external_device_id"), table_name="dataapp_monitorequipment")
    op.drop_column("dataapp_monitorequipment", "external_device_id")
