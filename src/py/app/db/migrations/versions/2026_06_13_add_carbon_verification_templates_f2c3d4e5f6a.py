"""add carbon verification template versions

Revision ID: f2c3d4e5f6a
Revises: f1b2c3d4e5f
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "f2c3d4e5f6a"
down_revision = "f1b2c3d4e5f"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

TEMPLATE_TABLE = "carbon_verification_template_version"


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
        TEMPLATE_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("template_code", sa.String(length=64), nullable=False),
        sa.Column("template_name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="v1.0"),
        sa.Column("template_format", sa.String(length=16), nullable=False, server_default="docx"),
        sa.Column("template_path", sa.String(length=512), nullable=False),
        sa.Column("applicable_industry", sa.String(length=128), nullable=True),
        sa.Column("applicable_scope", sa.String(length=255), nullable=True),
        sa.Column("standard_name", sa.String(length=255), nullable=True),
        sa.Column("standard_code", sa.String(length=128), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk(TEMPLATE_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{TEMPLATE_TABLE}")),
        sa.UniqueConstraint("team_id", "template_code", "version", name="uq_carbon_verification_template_team_code_version"),
    )
    for column in ("template_code", "version", "applicable_industry", "standard_code", "status", "is_default", "team_id"):
        op.create_index(op.f(f"ix_{TEMPLATE_TABLE}_{column}"), TEMPLATE_TABLE, [column])
    op.create_index("ix_carbon_verification_template_team_status_default", TEMPLATE_TABLE, ["team_id", "status", "is_default"])
    op.create_index("ix_carbon_verification_template_standard", TEMPLATE_TABLE, ["team_id", "standard_code", "applicable_industry"])
    for column in ("version", "template_format", "status", "is_default"):
        op.alter_column(TEMPLATE_TABLE, column, server_default=None)
    _enable_tenant_rls(TEMPLATE_TABLE)


def downgrade() -> None:
    _disable_tenant_rls(TEMPLATE_TABLE)
    op.drop_table(TEMPLATE_TABLE)
