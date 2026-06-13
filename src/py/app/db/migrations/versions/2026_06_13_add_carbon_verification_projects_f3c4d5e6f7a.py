"""add carbon verification projects

Revision ID: f3c4d5e6f7a
Revises: f2c3d4e5f6a
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "f3c4d5e6f7a"
down_revision = "f2c3d4e5f6a"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

PROJECT_TABLE = "carbon_verification_project"


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
        PROJECT_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("project_no", sa.String(length=64), nullable=False),
        sa.Column("project_name", sa.String(length=128), nullable=False),
        sa.Column("project_type", sa.String(length=32), nullable=False, server_default="organization_inventory"),
        sa.Column("reporting_org_id", _id_type(), nullable=True),
        sa.Column("period_id", _id_type(), nullable=True),
        sa.Column("boundary_id", _id_type(), nullable=True),
        sa.Column("accounting_batch_id", _id_type(), nullable=True),
        sa.Column("template_version_id", _id_type(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("verification_year", sa.Integer(), nullable=True),
        sa.Column("planned_start", sa.Date(), nullable=True),
        sa.Column("planned_end", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("lead_reviewer", sa.String(length=128), nullable=True),
        sa.Column("responsible_person", sa.String(length=128), nullable=True),
        sa.Column("verifier_org", sa.String(length=128), nullable=True),
        sa.Column("readiness_status", sa.String(length=24), nullable=False, server_default="empty"),
        sa.Column("conclusion", sa.Text(), nullable=True),
        sa.Column("scope_description", sa.Text(), nullable=True),
        sa.Column("finding_summary", sa.JSON(), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk(PROJECT_TABLE),
        sa.ForeignKeyConstraint(["reporting_org_id"], ["carbon_reporting_organization.id"], name="fk_cv_project_reporting_org", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["period_id"], ["carbon_reporting_period.id"], name="fk_cv_project_period", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["boundary_id"], ["carbon_organization_boundary.id"], name="fk_cv_project_boundary", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["accounting_batch_id"], ["carbon_accounting_batch.id"], name="fk_cv_project_batch", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["carbon_verification_template_version.id"],
            name="fk_cv_project_template_version",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{PROJECT_TABLE}")),
        sa.UniqueConstraint("team_id", "project_no", name="uq_carbon_verification_project_team_no"),
    )
    for column in (
        "project_no",
        "project_type",
        "reporting_org_id",
        "period_id",
        "boundary_id",
        "accounting_batch_id",
        "template_version_id",
        "status",
        "verification_year",
        "readiness_status",
        "team_id",
    ):
        op.create_index(op.f(f"ix_{PROJECT_TABLE}_{column}"), PROJECT_TABLE, [column])
    op.create_index("ix_carbon_verification_project_status", PROJECT_TABLE, ["team_id", "status", "project_type"])
    op.create_index("ix_carbon_verification_project_scope", PROJECT_TABLE, ["team_id", "reporting_org_id", "period_id", "boundary_id"])
    op.create_index("ix_carbon_verification_project_batch", PROJECT_TABLE, ["team_id", "accounting_batch_id", "status"])
    for column in ("project_type", "status", "readiness_status"):
        op.alter_column(PROJECT_TABLE, column, server_default=None)
    _enable_tenant_rls(PROJECT_TABLE)

    for table_name in ("carbon_verification_attachment", "carbon_verification_finding", "carbon_verification_export_job"):
        op.add_column(table_name, sa.Column("project_id", _id_type(), nullable=True))
        op.create_foreign_key(
            f"fk_{table_name}_project_id_cv_project",
            table_name,
            PROJECT_TABLE,
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(op.f(f"ix_{table_name}_project_id"), table_name, ["project_id"])


def downgrade() -> None:
    for table_name in ("carbon_verification_export_job", "carbon_verification_finding", "carbon_verification_attachment"):
        op.drop_index(op.f(f"ix_{table_name}_project_id"), table_name=table_name)
        op.drop_constraint(f"fk_{table_name}_project_id_cv_project", table_name, type_="foreignkey")
        op.drop_column(table_name, "project_id")

    _disable_tenant_rls(PROJECT_TABLE)
    op.drop_table(PROJECT_TABLE)
