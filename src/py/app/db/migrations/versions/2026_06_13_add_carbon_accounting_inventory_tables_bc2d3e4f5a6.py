"""add carbon accounting inventory tables

Revision ID: bc2d3e4f5a6
Revises: ad1e2f3a4b5
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "bc2d3e4f5a6"
down_revision = "ad1e2f3a4b5"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

BATCH_TABLE = "carbon_accounting_batch"
ITEM_TABLE = "carbon_emission_inventory_item"
TABLES = (BATCH_TABLE, ITEM_TABLE)


def _id_type() -> sa.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("team_id", sa.GUID(length=16), nullable=False),
        sa.Column("created_at", sa.DateTimeUTC(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTimeUTC(timezone=True), nullable=False),
    ]


def _tenant_fk(table_name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["team_id"],
        ["team.id"],
        name=f"fk_{table_name}_team_id_team",
        ondelete="CASCADE",
    )


def _tenant_policy_name(table_name: str) -> str:
    return f"rls_{table_name}_tenant_scope"


def _enable_tenant_rls(table_name: str) -> None:
    policy_name = _tenant_policy_name(table_name)
    op.execute(sa.text(f"alter table {table_name} enable row level security"))
    op.execute(sa.text(f"alter table {table_name} force row level security"))
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
    policy_name = _tenant_policy_name(table_name)
    op.execute(sa.text(f"drop policy if exists {policy_name} on {table_name}"))
    op.execute(sa.text(f"alter table {table_name} no force row level security"))
    op.execute(sa.text(f"alter table {table_name} disable row level security"))


def upgrade() -> None:
    op.create_table(
        BATCH_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("batch_no", sa.String(length=64), nullable=False),
        sa.Column("batch_name", sa.String(length=128), nullable=False),
        sa.Column("reporting_org_id", _id_type(), nullable=False),
        sa.Column("period_id", _id_type(), nullable=False),
        sa.Column("boundary_id", _id_type(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("inventory_status", sa.String(length=24), nullable=False, server_default="empty"),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("total_co2e", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("included_record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inventory_payload", sa.JSON(), nullable=True),
        sa.Column("rebuilt_at", sa.DateTime(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["reporting_org_id"], ["carbon_reporting_organization.id"], name="fk_carbon_accounting_batch_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["period_id"], ["carbon_reporting_period.id"], name="fk_carbon_accounting_batch_period", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["boundary_id"], ["carbon_organization_boundary.id"], name="fk_carbon_accounting_batch_boundary", ondelete="CASCADE"),
        _tenant_fk(BATCH_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{BATCH_TABLE}")),
        sa.UniqueConstraint("team_id", "batch_no", name="uq_carbon_accounting_batch_team_no"),
    )
    for column in ("batch_no", "reporting_org_id", "period_id", "boundary_id", "status", "inventory_status", "team_id"):
        op.create_index(op.f(f"ix_{BATCH_TABLE}_{column}"), BATCH_TABLE, [column])
    op.create_index("ix_carbon_accounting_batch_boundary", BATCH_TABLE, ["team_id", "boundary_id", "status"])
    op.create_index("ix_carbon_accounting_batch_period", BATCH_TABLE, ["team_id", "reporting_org_id", "period_id"])
    for column in ("status", "inventory_status", "record_count", "included_record_count", "missing_result_count"):
        op.alter_column(BATCH_TABLE, column, server_default=None)

    op.create_table(
        ITEM_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("batch_id", _id_type(), nullable=False),
        sa.Column("record_type", sa.String(length=64), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("record_label", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("period", sa.String(length=16), nullable=True),
        sa.Column("source_kind", sa.String(length=32), nullable=True),
        sa.Column("activity_amount", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("activity_unit", sa.String(length=32), nullable=True),
        sa.Column("computed_co2e", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("factor_source", sa.String(length=255), nullable=True),
        sa.Column("factor_year", sa.Integer(), nullable=True),
        sa.Column("factor_unit", sa.String(length=32), nullable=True),
        sa.Column("calc_status", sa.String(length=24), nullable=True),
        sa.Column("quality_status", sa.String(length=24), nullable=False, server_default="ready"),
        sa.Column("included", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column("source_payload", sa.JSON(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["batch_id"], [f"{BATCH_TABLE}.id"], name="fk_carbon_inventory_item_batch", ondelete="CASCADE"),
        _tenant_fk(ITEM_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{ITEM_TABLE}")),
        sa.UniqueConstraint("team_id", "batch_id", "record_type", "record_id", name="uq_carbon_inventory_item_batch_record"),
    )
    for column in ("batch_id", "record_type", "record_id", "scope", "period", "source_kind", "calc_status", "quality_status", "included", "team_id"):
        op.create_index(op.f(f"ix_{ITEM_TABLE}_{column}"), ITEM_TABLE, [column])
    op.create_index("ix_carbon_inventory_item_batch_scope", ITEM_TABLE, ["team_id", "batch_id", "scope"])
    op.create_index("ix_carbon_inventory_item_record", ITEM_TABLE, ["team_id", "record_type", "record_id"])
    op.alter_column(ITEM_TABLE, "quality_status", server_default=None)
    op.alter_column(ITEM_TABLE, "included", server_default=None)

    for table_name in TABLES:
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        _disable_tenant_rls(table_name)
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
