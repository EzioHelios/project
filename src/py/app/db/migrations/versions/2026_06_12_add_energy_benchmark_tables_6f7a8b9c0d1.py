"""add energy benchmark tables

Revision ID: 6f7a8b9c0d1
Revises: 5e6f7a8b9c0
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "6f7a8b9c0d1"
down_revision = "5e6f7a8b9c0"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

TABLES = (
    "dataapp_energybenchmarkprofile",
    "dataapp_energybenchmarkitem",
)


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
        "dataapp_energybenchmarkprofile",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("industry_name", sa.String(length=128), nullable=True),
        sa.Column("scenario", sa.String(length=128), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk("dataapp_energybenchmarkprofile"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_energybenchmarkprofile")),
    )
    for column in ("name", "industry_name", "scenario", "is_enabled", "team_id"):
        op.create_index(op.f(f"ix_dataapp_energybenchmarkprofile_{column}"), "dataapp_energybenchmarkprofile", [column])
    op.create_index("ix_energy_benchmark_profile_enabled", "dataapp_energybenchmarkprofile", ["team_id", "is_enabled"])
    op.alter_column("dataapp_energybenchmarkprofile", "is_enabled", server_default=None)

    op.create_table(
        "dataapp_energybenchmarkitem",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("profile_id", _id_type(), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_code", sa.String(length=128), nullable=True),
        sa.Column("target_name", sa.String(length=128), nullable=True),
        sa.Column("metric_code", sa.String(length=64), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("benchmark_value", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("excellent_value", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("warning_threshold_pct", sa.Numeric(precision=8, scale=2), nullable=True, server_default="10"),
        sa.Column("severe_threshold_pct", sa.Numeric(precision=8, scale=2), nullable=True, server_default="25"),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["profile_id"], ["dataapp_energybenchmarkprofile.id"], name="fk_energy_benchmark_item_profile", ondelete="CASCADE"),
        _tenant_fk("dataapp_energybenchmarkitem"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_energybenchmarkitem")),
    )
    for column in ("profile_id", "target_type", "target_code", "metric_code", "is_enabled", "team_id"):
        op.create_index(op.f(f"ix_dataapp_energybenchmarkitem_{column}"), "dataapp_energybenchmarkitem", [column])
    op.create_index("ix_energy_benchmark_item_profile_metric", "dataapp_energybenchmarkitem", ["team_id", "profile_id", "target_type", "metric_code"])
    op.create_index("ix_energy_benchmark_item_enabled", "dataapp_energybenchmarkitem", ["team_id", "is_enabled"])
    op.create_index("ix_energy_benchmark_item_target", "dataapp_energybenchmarkitem", ["team_id", "target_type", "target_code"])
    op.alter_column("dataapp_energybenchmarkitem", "warning_threshold_pct", server_default=None)
    op.alter_column("dataapp_energybenchmarkitem", "severe_threshold_pct", server_default=None)
    op.alter_column("dataapp_energybenchmarkitem", "is_enabled", server_default=None)

    for table_name in TABLES:
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        _disable_tenant_rls(table_name)
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
