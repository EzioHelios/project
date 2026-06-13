"""add carbon verification export tables

Revision ID: 9c0d1e2f3a4
Revises: 8b9c0d1e2f3
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "9c0d1e2f3a4"
down_revision = "8b9c0d1e2f3"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

JOB_TABLE = "carbon_verification_export_job"
FILE_TABLE = "carbon_verification_export_file"
TABLES = (JOB_TABLE, FILE_TABLE)


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
        JOB_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("job_no", sa.String(length=64), nullable=False),
        sa.Column("export_type", sa.String(length=32), nullable=False, server_default="material_package"),
        sa.Column("report_year", sa.Integer(), nullable=True),
        sa.Column("scope_filter", sa.String(length=16), nullable=True),
        sa.Column("status_filter", sa.String(length=24), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="completed"),
        sa.Column("template_name", sa.String(length=255), nullable=True),
        sa.Column("template_path", sa.String(length=512), nullable=True),
        sa.Column("standard_name", sa.String(length=255), nullable=True),
        sa.Column("standard_code", sa.String(length=128), nullable=True),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("manifest_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.String(length=128), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        *_audit_columns(),
        _tenant_fk(JOB_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{JOB_TABLE}")),
        sa.UniqueConstraint("team_id", "job_no", name="uq_carbon_verification_export_job_team_no"),
    )
    for column in ("job_no", "export_type", "report_year", "scope_filter", "status_filter", "status", "team_id"):
        op.create_index(op.f(f"ix_{JOB_TABLE}_{column}"), JOB_TABLE, [column])
    op.create_index("ix_carbon_verification_export_job_team_status", JOB_TABLE, ["team_id", "status"])
    op.create_index("ix_carbon_verification_export_job_period", JOB_TABLE, ["team_id", "report_year", "scope_filter"])
    op.alter_column(JOB_TABLE, "export_type", server_default=None)
    op.alter_column(JOB_TABLE, "status", server_default=None)

    op.create_table(
        FILE_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("job_id", _id_type(), nullable=False),
        sa.Column("file_type", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["job_id"], [f"{JOB_TABLE}.id"], name="fk_carbon_verification_export_file_job", ondelete="CASCADE"),
        _tenant_fk(FILE_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{FILE_TABLE}")),
    )
    for column in ("job_id", "file_type", "team_id"):
        op.create_index(op.f(f"ix_{FILE_TABLE}_{column}"), FILE_TABLE, [column])
    op.create_index("ix_carbon_verification_export_file_job", FILE_TABLE, ["team_id", "job_id"])
    op.create_index("ix_carbon_verification_export_file_type", FILE_TABLE, ["team_id", "file_type"])

    for table_name in TABLES:
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        _disable_tenant_rls(table_name)
    for table_name in reversed(TABLES):
        op.drop_table(table_name)

