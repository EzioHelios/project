"""add energy optimization records

Revision ID: 7a8b9c0d1e2
Revises: 6f7a8b9c0d1
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "7a8b9c0d1e2"
down_revision = "6f7a8b9c0d1"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

TABLE_NAME = "dataapp_energyoptimizationrecord"


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


def _enable_tenant_rls(table_name: str) -> None:
    policy_name = f"rls_{table_name}_tenant_scope"
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
    policy_name = f"rls_{table_name}_tenant_scope"
    op.execute(sa.text(f"drop policy if exists {policy_name} on {table_name}"))
    op.execute(sa.text(f"alter table {table_name} no force row level security"))
    op.execute(sa.text(f"alter table {table_name} disable row level security"))


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("balance_object_type", sa.String(length=32), nullable=False, server_default="enterprise"),
        sa.Column("balance_object_code", sa.String(length=128), nullable=True),
        sa.Column("balance_object_name", sa.String(length=128), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("scenario_type", sa.String(length=48), nullable=False),
        sa.Column("scenario_name", sa.String(length=128), nullable=False),
        sa.Column("before_parameters", sa.JSON(), nullable=True),
        sa.Column("after_parameters", sa.JSON(), nullable=True),
        sa.Column("baseline_energy", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("expected_energy", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("saving_energy", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("saving_rate_pct", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("cost_delta_cny", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=True),
        sa.Column("assumptions", sa.JSON(), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="simulated"),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk(TABLE_NAME),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{TABLE_NAME}")),
    )
    for column in ("team_id", "balance_object_type", "balance_object_code", "period_start", "period_end", "scenario_type", "status"):
        op.create_index(op.f(f"ix_{TABLE_NAME}_{column}"), TABLE_NAME, [column])
    op.create_index("ix_energy_optimization_record_period", TABLE_NAME, ["team_id", "period_start", "period_end"])
    op.create_index("ix_energy_optimization_record_object", TABLE_NAME, ["team_id", "balance_object_type", "balance_object_code"])
    op.create_index("ix_energy_optimization_record_scenario", TABLE_NAME, ["team_id", "scenario_type"])
    op.alter_column(TABLE_NAME, "balance_object_type", server_default=None)
    op.alter_column(TABLE_NAME, "status", server_default=None)
    _enable_tenant_rls(TABLE_NAME)


def downgrade() -> None:
    _disable_tenant_rls(TABLE_NAME)
    op.drop_table(TABLE_NAME)
