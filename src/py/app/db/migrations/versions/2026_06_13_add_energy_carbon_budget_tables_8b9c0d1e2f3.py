"""add energy carbon budget tables

Revision ID: 8b9c0d1e2f3
Revises: 7a8b9c0d1e2
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "8b9c0d1e2f3"
down_revision = "7a8b9c0d1e2"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

PLAN_TABLE = "dataapp_energycarbonbudgetplan"
ALLOCATION_TABLE = "dataapp_energycarbonbudgetallocation"
ADJUSTMENT_TABLE = "dataapp_energycarbonbudgetadjustment"
TABLES = (PLAN_TABLE, ALLOCATION_TABLE, ADJUSTMENT_TABLE)


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
        PLAN_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("budget_year", sa.Integer(), nullable=False),
        sa.Column("period_type", sa.String(length=16), nullable=False, server_default="annual"),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("target_scope", sa.String(length=32), nullable=False, server_default="enterprise"),
        sa.Column("target_code", sa.String(length=128), nullable=True),
        sa.Column("target_name", sa.String(length=128), nullable=True),
        sa.Column("energy_budget_tce", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("carbon_budget_co2e", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("denominator_plan", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("denominator_unit", sa.String(length=32), nullable=True),
        sa.Column("energy_intensity_budget", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("carbon_intensity_budget", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk(PLAN_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{PLAN_TABLE}")),
        sa.UniqueConstraint("team_id", "code", name="uq_energy_carbon_budget_plan_team_code"),
    )
    for column in ("code", "budget_year", "period_type", "period_start", "period_end", "target_scope", "target_code", "status", "team_id"):
        op.create_index(op.f(f"ix_{PLAN_TABLE}_{column}"), PLAN_TABLE, [column])
    op.create_index("ix_energy_carbon_budget_plan_year_status", PLAN_TABLE, ["team_id", "budget_year", "status"])
    op.create_index("ix_energy_carbon_budget_plan_scope", PLAN_TABLE, ["team_id", "target_scope", "target_code"])
    for column in ("period_type", "target_scope", "status"):
        op.alter_column(PLAN_TABLE, column, server_default=None)

    op.create_table(
        ALLOCATION_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("plan_id", _id_type(), nullable=False),
        sa.Column("period_month", sa.Date(), nullable=False),
        sa.Column("target_scope", sa.String(length=32), nullable=False, server_default="enterprise"),
        sa.Column("target_code", sa.String(length=128), nullable=True),
        sa.Column("target_name", sa.String(length=128), nullable=True),
        sa.Column("energy_budget_tce", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("carbon_budget_co2e", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("denominator_budget", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("denominator_unit", sa.String(length=32), nullable=True),
        sa.Column("energy_intensity_budget", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("carbon_intensity_budget", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["plan_id"], [f"{PLAN_TABLE}.id"], name="fk_energy_carbon_budget_allocation_plan", ondelete="CASCADE"),
        _tenant_fk(ALLOCATION_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{ALLOCATION_TABLE}")),
        sa.UniqueConstraint("team_id", "plan_id", "period_month", name="uq_energy_carbon_budget_allocation_plan_month"),
    )
    for column in ("plan_id", "period_month", "target_scope", "target_code", "status", "team_id"):
        op.create_index(op.f(f"ix_{ALLOCATION_TABLE}_{column}"), ALLOCATION_TABLE, [column])
    op.create_index("ix_energy_carbon_budget_allocation_plan", ALLOCATION_TABLE, ["team_id", "plan_id", "period_month"])
    op.create_index("ix_energy_carbon_budget_allocation_scope", ALLOCATION_TABLE, ["team_id", "target_scope", "target_code"])
    op.alter_column(ALLOCATION_TABLE, "target_scope", server_default=None)
    op.alter_column(ALLOCATION_TABLE, "status", server_default=None)

    op.create_table(
        ADJUSTMENT_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("plan_id", _id_type(), nullable=False),
        sa.Column("allocation_id", _id_type(), nullable=True),
        sa.Column("adjustment_no", sa.String(length=64), nullable=False),
        sa.Column("adjustment_type", sa.String(length=32), nullable=False, server_default="reforecast"),
        sa.Column("effective_month", sa.Date(), nullable=True),
        sa.Column("original_energy_budget_tce", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("original_carbon_budget_co2e", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("adjusted_energy_budget_tce", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("adjusted_carbon_budget_co2e", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("requested_by", sa.String(length=64), nullable=True),
        sa.Column("approved_by", sa.String(length=64), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["plan_id"], [f"{PLAN_TABLE}.id"], name="fk_energy_carbon_budget_adjustment_plan", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["allocation_id"],
            [f"{ALLOCATION_TABLE}.id"],
            name="fk_energy_carbon_budget_adjustment_allocation",
            ondelete="SET NULL",
        ),
        _tenant_fk(ADJUSTMENT_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{ADJUSTMENT_TABLE}")),
        sa.UniqueConstraint("team_id", "adjustment_no", name="uq_energy_carbon_budget_adjustment_team_no"),
    )
    for column in ("plan_id", "allocation_id", "adjustment_no", "adjustment_type", "effective_month", "status", "team_id"):
        op.create_index(op.f(f"ix_{ADJUSTMENT_TABLE}_{column}"), ADJUSTMENT_TABLE, [column])
    op.create_index("ix_energy_carbon_budget_adjustment_plan", ADJUSTMENT_TABLE, ["team_id", "plan_id", "status"])
    op.create_index("ix_energy_carbon_budget_adjustment_month", ADJUSTMENT_TABLE, ["team_id", "effective_month"])
    op.alter_column(ADJUSTMENT_TABLE, "adjustment_type", server_default=None)
    op.alter_column(ADJUSTMENT_TABLE, "status", server_default=None)

    for table_name in TABLES:
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        _disable_tenant_rls(table_name)
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
