"""add carbon verification findings

Revision ID: f0a1b2c3d4e
Revises: ef5a6b7c8d9
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "f0a1b2c3d4e"
down_revision = "ef5a6b7c8d9"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

FINDING_TABLE = "carbon_verification_finding"


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
        FINDING_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("finding_no", sa.String(length=64), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("finding_type", sa.String(length=64), nullable=False, server_default="data_quality"),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("action_required", sa.Text(), nullable=True),
        sa.Column("record_type", sa.String(length=128), nullable=True),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("scope", sa.String(length=16), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("period", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("owner", sa.String(length=128), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("correction_comment", sa.Text(), nullable=True),
        sa.Column("correction_evidence", sa.String(length=512), nullable=True),
        sa.Column("reviewer", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("source_payload", sa.JSON(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk(FINDING_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{FINDING_TABLE}")),
        sa.UniqueConstraint("team_id", "finding_no", name="uq_carbon_verification_finding_team_no"),
    )
    for column in (
        "finding_no",
        "issue_type",
        "finding_type",
        "severity",
        "record_type",
        "record_id",
        "scope",
        "period",
        "status",
        "due_date",
        "team_id",
    ):
        op.create_index(op.f(f"ix_{FINDING_TABLE}_{column}"), FINDING_TABLE, [column])
    op.create_index("ix_carbon_verification_finding_team_status_severity", FINDING_TABLE, ["team_id", "status", "severity"])
    op.create_index("ix_carbon_verification_finding_record", FINDING_TABLE, ["team_id", "record_type", "record_id", "issue_type"])
    op.create_index("ix_carbon_verification_finding_due", FINDING_TABLE, ["team_id", "due_date", "status"])
    for column in ("finding_type", "severity", "status"):
        op.alter_column(FINDING_TABLE, column, server_default=None)
    _enable_tenant_rls(FINDING_TABLE)


def downgrade() -> None:
    _disable_tenant_rls(FINDING_TABLE)
    op.drop_table(FINDING_TABLE)
