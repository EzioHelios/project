"""Add equipment energy efficiency fields.

Revision ID: f6a7b8c9d0e1
Revises: e6f7a8b9c0d1
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add device efficiency level and source standard fields."""
    op.add_column("dataapp_monitorequipment", sa.Column("energy_efficiency_level", sa.Integer(), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("energy_efficiency_standard", sa.String(length=128), nullable=True))
    op.create_index(
        op.f("ix_dataapp_monitorequipment_energy_efficiency_level"),
        "dataapp_monitorequipment",
        ["energy_efficiency_level"],
    )


def downgrade() -> None:
    """Remove device efficiency fields."""
    op.drop_index(op.f("ix_dataapp_monitorequipment_energy_efficiency_level"), table_name="dataapp_monitorequipment")
    op.drop_column("dataapp_monitorequipment", "energy_efficiency_standard")
    op.drop_column("dataapp_monitorequipment", "energy_efficiency_level")
