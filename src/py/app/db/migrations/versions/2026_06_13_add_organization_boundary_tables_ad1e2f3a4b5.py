"""add organization boundary tables

Revision ID: ad1e2f3a4b5
Revises: 9c0d1e2f3a4
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "ad1e2f3a4b5"
down_revision = "9c0d1e2f3a4"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

ORG_TABLE = "carbon_reporting_organization"
PERIOD_TABLE = "carbon_reporting_period"
BOUNDARY_TABLE = "carbon_organization_boundary"
FACILITY_TABLE = "carbon_boundary_facility"
TABLES = (ORG_TABLE, PERIOD_TABLE, BOUNDARY_TABLE, FACILITY_TABLE)


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
        ORG_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("enterprise_id", _id_type(), nullable=True),
        sa.Column("organization_type", sa.String(length=32), nullable=False, server_default="enterprise"),
        sa.Column("legal_entity_code", sa.String(length=64), nullable=True),
        sa.Column("control_method", sa.String(length=32), nullable=False, server_default="operational_control"),
        sa.Column("equity_share_pct", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["enterprise_id"], ["dataapp_enterpriseinfo.id"], name="fk_carbon_reporting_org_enterprise", ondelete="SET NULL"),
        _tenant_fk(ORG_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{ORG_TABLE}")),
        sa.UniqueConstraint("team_id", "code", name="uq_carbon_reporting_organization_team_code"),
    )
    for column in ("code", "enterprise_id", "organization_type", "control_method", "status", "team_id"):
        op.create_index(op.f(f"ix_{ORG_TABLE}_{column}"), ORG_TABLE, [column])
    op.create_index("ix_carbon_reporting_organization_team_status", ORG_TABLE, ["team_id", "status"])
    for column in ("organization_type", "control_method", "status"):
        op.alter_column(ORG_TABLE, column, server_default=None)

    op.create_table(
        PERIOD_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("reporting_org_id", _id_type(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("period_type", sa.String(length=16), nullable=False, server_default="annual"),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("base_year", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["reporting_org_id"], [f"{ORG_TABLE}.id"], name="fk_carbon_reporting_period_org", ondelete="CASCADE"),
        _tenant_fk(PERIOD_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{PERIOD_TABLE}")),
        sa.UniqueConstraint("team_id", "reporting_org_id", "code", name="uq_carbon_reporting_period_org_code"),
    )
    for column in ("reporting_org_id", "code", "period_type", "period_start", "period_end", "status", "team_id"):
        op.create_index(op.f(f"ix_{PERIOD_TABLE}_{column}"), PERIOD_TABLE, [column])
    op.create_index("ix_carbon_reporting_period_org_range", PERIOD_TABLE, ["team_id", "reporting_org_id", "period_start", "period_end"])
    for column in ("period_type", "status"):
        op.alter_column(PERIOD_TABLE, column, server_default=None)

    op.create_table(
        BOUNDARY_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("reporting_org_id", _id_type(), nullable=False),
        sa.Column("period_id", _id_type(), nullable=False),
        sa.Column("boundary_no", sa.String(length=64), nullable=False),
        sa.Column("boundary_name", sa.String(length=128), nullable=False),
        sa.Column("boundary_type", sa.String(length=32), nullable=False, server_default="organization"),
        sa.Column("boundary_method", sa.String(length=32), nullable=False, server_default="operational_control"),
        sa.Column("operational_boundary", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["reporting_org_id"], [f"{ORG_TABLE}.id"], name="fk_carbon_boundary_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["period_id"], [f"{PERIOD_TABLE}.id"], name="fk_carbon_boundary_period", ondelete="CASCADE"),
        _tenant_fk(BOUNDARY_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{BOUNDARY_TABLE}")),
        sa.UniqueConstraint("team_id", "boundary_no", name="uq_carbon_organization_boundary_team_no"),
        sa.UniqueConstraint("team_id", "reporting_org_id", "period_id", "boundary_type", "version", name="uq_carbon_boundary_version"),
    )
    for column in ("reporting_org_id", "period_id", "boundary_no", "boundary_type", "boundary_method", "status", "team_id"):
        op.create_index(op.f(f"ix_{BOUNDARY_TABLE}_{column}"), BOUNDARY_TABLE, [column])
    op.create_index("ix_carbon_boundary_org_period_status", BOUNDARY_TABLE, ["team_id", "reporting_org_id", "period_id", "status"])
    for column in ("boundary_type", "boundary_method", "version", "status"):
        op.alter_column(BOUNDARY_TABLE, column, server_default=None)

    op.create_table(
        FACILITY_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("boundary_id", _id_type(), nullable=False),
        sa.Column("facility_type", sa.String(length=32), nullable=False, server_default="area"),
        sa.Column("area_id", _id_type(), nullable=True),
        sa.Column("equipment_id", _id_type(), nullable=True),
        sa.Column("facility_code", sa.String(length=128), nullable=True),
        sa.Column("facility_name", sa.String(length=128), nullable=True),
        sa.Column("facility_role", sa.String(length=64), nullable=True),
        sa.Column("included", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["boundary_id"], [f"{BOUNDARY_TABLE}.id"], name="fk_carbon_boundary_facility_boundary", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["area_id"], ["dataapp_monitorsector.id"], name="fk_carbon_boundary_facility_area", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["equipment_id"], ["dataapp_monitorequipment.id"], name="fk_carbon_boundary_facility_equipment", ondelete="SET NULL"),
        _tenant_fk(FACILITY_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{FACILITY_TABLE}")),
    )
    for column in ("boundary_id", "facility_type", "area_id", "equipment_id", "facility_code", "included", "team_id"):
        op.create_index(op.f(f"ix_{FACILITY_TABLE}_{column}"), FACILITY_TABLE, [column])
    op.create_index("ix_carbon_boundary_facility_boundary", FACILITY_TABLE, ["team_id", "boundary_id", "included"])
    op.create_index("ix_carbon_boundary_facility_reference", FACILITY_TABLE, ["team_id", "facility_type", "area_id", "equipment_id"])
    op.alter_column(FACILITY_TABLE, "facility_type", server_default=None)
    op.alter_column(FACILITY_TABLE, "included", server_default=None)

    for table_name in TABLES:
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        _disable_tenant_rls(table_name)
    for table_name in reversed(TABLES):
        op.drop_table(table_name)

