"""add scope2 meter aggregate

Revision ID: d4e5f6a7b8c9
Revises: b7c9d2e4f6a8
Create Date: 2026-05-14
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "b7c9d2e4f6a8"
branch_labels = None
depends_on = None


def _id_column() -> sa.Column:
    return sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False)


def _audit_columns() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "dataapp_scope2meteraggregate",
        _id_column(),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("ammeter_id", sa.String(length=20), nullable=False),
        sa.Column("ammeter_name", sa.String(length=30), nullable=True),
        sa.Column("area_id", sa.String(length=20), nullable=True),
        sa.Column("area_name", sa.String(length=50), nullable=True),
        sa.Column("billing_month", sa.String(length=7), nullable=False),
        sa.Column("first_reading_time", sa.DateTime(), nullable=True),
        sa.Column("last_reading_time", sa.DateTime(), nullable=True),
        sa.Column("start_total_energy", sa.Numeric(precision=16, scale=4), nullable=True),
        sa.Column("end_total_energy", sa.Numeric(precision=16, scale=4), nullable=True),
        sa.Column("total_kwh", sa.Numeric(precision=16, scale=4), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("calc_status", sa.String(length=24), nullable=False),
        sa.Column("aggregation_note", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_scope2meteraggregate")),
        sa.UniqueConstraint("ammeter_id", "billing_month", name="uq_scope2_meter_aggregate_meter_month"),
    )
    op.create_index(
        "ix_scope2_meter_aggregate_month_area",
        "dataapp_scope2meteraggregate",
        ["billing_month", "area_id"],
    )
    op.create_index(op.f("ix_dataapp_scope2meteraggregate_ammeter_id"), "dataapp_scope2meteraggregate", ["ammeter_id"])
    op.create_index(op.f("ix_dataapp_scope2meteraggregate_area_id"), "dataapp_scope2meteraggregate", ["area_id"])
    op.create_index(op.f("ix_dataapp_scope2meteraggregate_billing_month"), "dataapp_scope2meteraggregate", ["billing_month"])
    op.create_index(op.f("ix_dataapp_scope2meteraggregate_calc_status"), "dataapp_scope2meteraggregate", ["calc_status"])
    op.create_index(op.f("ix_dataapp_scope2meteraggregate_status"), "dataapp_scope2meteraggregate", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_dataapp_scope2meteraggregate_status"), table_name="dataapp_scope2meteraggregate")
    op.drop_index(op.f("ix_dataapp_scope2meteraggregate_calc_status"), table_name="dataapp_scope2meteraggregate")
    op.drop_index(op.f("ix_dataapp_scope2meteraggregate_billing_month"), table_name="dataapp_scope2meteraggregate")
    op.drop_index(op.f("ix_dataapp_scope2meteraggregate_area_id"), table_name="dataapp_scope2meteraggregate")
    op.drop_index(op.f("ix_dataapp_scope2meteraggregate_ammeter_id"), table_name="dataapp_scope2meteraggregate")
    op.drop_index("ix_scope2_meter_aggregate_month_area", table_name="dataapp_scope2meteraggregate")
    op.drop_table("dataapp_scope2meteraggregate")
