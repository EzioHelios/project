"""Add tenant ownership for enterprise calculation factors.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allow shared calculation factors and tenant-owned enterprise factors."""
    op.add_column("dataapp_emissionfactor", sa.Column("team_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_dataapp_emissionfactor_team_id"), "dataapp_emissionfactor", ["team_id"])
    op.create_foreign_key(
        op.f("fk_dataapp_emissionfactor_team_id_team"),
        "dataapp_emissionfactor",
        "team",
        ["team_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_dataapp_emissionfactor_team_business_key",
        "dataapp_emissionfactor",
        ["team_id", "scope", "category", "sub_category", "unit", "year"],
    )


def downgrade() -> None:
    """Remove tenant ownership from calculation factors."""
    op.drop_constraint("uq_dataapp_emissionfactor_team_business_key", "dataapp_emissionfactor", type_="unique")
    op.drop_constraint(op.f("fk_dataapp_emissionfactor_team_id_team"), "dataapp_emissionfactor", type_="foreignkey")
    op.drop_index(op.f("ix_dataapp_emissionfactor_team_id"), table_name="dataapp_emissionfactor")
    op.drop_column("dataapp_emissionfactor", "team_id")
