"""add scope2 computation snapshot fields

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-14
"""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dataapp_scope2electricitybill",
        sa.Column("calc_status", sa.String(length=24), nullable=False, server_default="ready"),
    )
    op.add_column("dataapp_scope2electricitybill", sa.Column("factor_source", sa.String(length=128), nullable=True))
    op.add_column("dataapp_scope2electricitybill", sa.Column("factor_year", sa.Integer(), nullable=True))
    op.add_column("dataapp_scope2electricitybill", sa.Column("factor_unit", sa.String(length=32), nullable=True))
    op.add_column("dataapp_scope2electricitybill", sa.Column("activity_amount", sa.Numeric(precision=16, scale=4), nullable=True))
    op.add_column("dataapp_scope2electricitybill", sa.Column("activity_unit", sa.String(length=16), nullable=True))
    op.add_column("dataapp_scope2electricitybill", sa.Column("computed_co2e", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("dataapp_scope2electricitybill", sa.Column("computation_note", sa.Text(), nullable=True))
    op.create_index(op.f("ix_dataapp_scope2electricitybill_calc_status"), "dataapp_scope2electricitybill", ["calc_status"])
    op.alter_column("dataapp_scope2electricitybill", "calc_status", server_default=None)

    op.add_column("dataapp_scope2meteraggregate", sa.Column("factor_source", sa.String(length=128), nullable=True))
    op.add_column("dataapp_scope2meteraggregate", sa.Column("factor_year", sa.Integer(), nullable=True))
    op.add_column("dataapp_scope2meteraggregate", sa.Column("factor_unit", sa.String(length=32), nullable=True))
    op.add_column("dataapp_scope2meteraggregate", sa.Column("activity_amount", sa.Numeric(precision=16, scale=4), nullable=True))
    op.add_column("dataapp_scope2meteraggregate", sa.Column("activity_unit", sa.String(length=16), nullable=True))
    op.add_column("dataapp_scope2meteraggregate", sa.Column("computed_co2e", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("dataapp_scope2meteraggregate", sa.Column("computation_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("dataapp_scope2meteraggregate", "computation_note")
    op.drop_column("dataapp_scope2meteraggregate", "computed_co2e")
    op.drop_column("dataapp_scope2meteraggregate", "activity_unit")
    op.drop_column("dataapp_scope2meteraggregate", "activity_amount")
    op.drop_column("dataapp_scope2meteraggregate", "factor_unit")
    op.drop_column("dataapp_scope2meteraggregate", "factor_year")
    op.drop_column("dataapp_scope2meteraggregate", "factor_source")

    op.drop_index(op.f("ix_dataapp_scope2electricitybill_calc_status"), table_name="dataapp_scope2electricitybill")
    op.drop_column("dataapp_scope2electricitybill", "computation_note")
    op.drop_column("dataapp_scope2electricitybill", "computed_co2e")
    op.drop_column("dataapp_scope2electricitybill", "activity_unit")
    op.drop_column("dataapp_scope2electricitybill", "activity_amount")
    op.drop_column("dataapp_scope2electricitybill", "factor_unit")
    op.drop_column("dataapp_scope2electricitybill", "factor_year")
    op.drop_column("dataapp_scope2electricitybill", "factor_source")
    op.drop_column("dataapp_scope2electricitybill", "calc_status")
