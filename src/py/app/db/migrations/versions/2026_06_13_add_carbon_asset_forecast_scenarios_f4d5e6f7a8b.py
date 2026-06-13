"""add carbon asset forecast scenarios

Revision ID: f4d5e6f7a8b
Revises: f3c4d5e6f7a
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "f4d5e6f7a8b"
down_revision = "f3c4d5e6f7a"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

SCENARIO_TABLE = "carbon_asset_forecast_scenario"


def _id_type() -> sa.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("team_id", sa.GUID(length=16), nullable=False),
        sa.Column("created_at", sa.DateTimeUTC(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTimeUTC(timezone=True), nullable=False),
    ]


def _tenant_fk(table_name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(["team_id"], ["team.id"], name=f"fk_{table_name}_team_id_team", ondelete="CASCADE")


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
        SCENARIO_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("period_id", _id_type(), nullable=False),
        sa.Column("scenario_code", sa.String(length=64), nullable=False),
        sa.Column("scenario_name", sa.String(length=128), nullable=False),
        sa.Column("base_year", sa.Integer(), nullable=True),
        sa.Column("forecast_start", sa.Date(), nullable=True),
        sa.Column("forecast_end", sa.Date(), nullable=True),
        sa.Column("emission_growth_rate", sa.Numeric(precision=10, scale=6), nullable=False, server_default="0"),
        sa.Column("planned_reduction", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("planned_allowance_purchase", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("planned_credit_purchase", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("planned_surrender", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("allowance_price", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("credit_price", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="CNY"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["period_id"], ["carbon_compliance_period.id"], name="fk_carbon_asset_forecast_scenario_period", ondelete="CASCADE"),
        _tenant_fk(SCENARIO_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{SCENARIO_TABLE}")),
        sa.UniqueConstraint("team_id", "scenario_code", name="uq_carbon_asset_forecast_scenario_team_code"),
    )
    for column in ("period_id", "scenario_code", "base_year", "forecast_end", "status", "team_id"):
        op.create_index(op.f(f"ix_{SCENARIO_TABLE}_{column}"), SCENARIO_TABLE, [column])
    op.create_index("ix_carbon_asset_forecast_scenario_period", SCENARIO_TABLE, ["team_id", "period_id", "status"])
    op.create_index("ix_carbon_asset_forecast_scenario_status", SCENARIO_TABLE, ["team_id", "status", "forecast_end"])
    for column in (
        "emission_growth_rate",
        "planned_reduction",
        "planned_allowance_purchase",
        "planned_credit_purchase",
        "planned_surrender",
        "allowance_price",
        "credit_price",
        "currency",
        "status",
    ):
        op.alter_column(SCENARIO_TABLE, column, server_default=None)
    _enable_tenant_rls(SCENARIO_TABLE)


def downgrade() -> None:
    _disable_tenant_rls(SCENARIO_TABLE)
    op.drop_table(SCENARIO_TABLE)
