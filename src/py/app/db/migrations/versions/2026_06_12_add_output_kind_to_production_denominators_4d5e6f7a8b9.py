"""add output kind to production denominator tables

Revision ID: 4d5e6f7a8b9
Revises: 3c4d5e6f7a9
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "4d5e6f7a8b9"
down_revision = "3c4d5e6f7a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dataapp_productionproduct",
        sa.Column("output_kind", sa.String(length=32), nullable=False, server_default="product"),
    )
    op.add_column(
        "dataapp_productionoutputfact",
        sa.Column("output_kind", sa.String(length=32), nullable=False, server_default="product"),
    )
    op.create_index(
        op.f("ix_dataapp_productionproduct_output_kind"),
        "dataapp_productionproduct",
        ["output_kind"],
    )
    op.create_index(
        op.f("ix_dataapp_productionoutputfact_output_kind"),
        "dataapp_productionoutputfact",
        ["output_kind"],
    )
    op.alter_column("dataapp_productionproduct", "output_kind", server_default=None)
    op.alter_column("dataapp_productionoutputfact", "output_kind", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_dataapp_productionoutputfact_output_kind"), table_name="dataapp_productionoutputfact")
    op.drop_index(op.f("ix_dataapp_productionproduct_output_kind"), table_name="dataapp_productionproduct")
    op.drop_column("dataapp_productionoutputfact", "output_kind")
    op.drop_column("dataapp_productionproduct", "output_kind")
