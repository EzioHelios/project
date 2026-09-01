"""add GHG emission sources and area/equipment allocations

Revision ID: c2d3e4f5a6b
Revises: b1c2d3e4f6a
Create Date: 2026-08-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.domain.ghg_inventory import models

revision = "c2d3e4f5a6b"
down_revision = "b1c2d3e4f6a"
branch_labels = None
depends_on = None

TENANT_TABLES = (models.GhgEmissionSource.__table__.name, models.GhgActivityAllocation.__table__.name)


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _foreign_key_exists(table_name: str, constrained_columns: list[str], referred_table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    constrained = set(constrained_columns)
    for foreign_key in inspector.get_foreign_keys(table_name):
        if foreign_key.get("referred_table") != referred_table:
            continue
        if set(foreign_key.get("constrained_columns") or []) == constrained:
            return True
    return False


def _enable_tenant_rls(table_name: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    policy_name = f"rls_{table_name}_tenant_scope"
    op.execute(sa.text(f"alter table {table_name} enable row level security"))
    op.execute(sa.text(f"alter table {table_name} force row level security"))
    op.execute(sa.text(f"drop policy if exists {policy_name} on {table_name}"))
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


def upgrade() -> None:
    bind = op.get_bind()
    models.GhgEmissionSource.__table__.create(bind, checkfirst=True)
    needs_organization_boundary_id = not _column_exists("ghg_activity_record", "organization_boundary_id")
    needs_emission_source_id = not _column_exists("ghg_activity_record", "emission_source_id")
    needs_organization_boundary_index = not _index_exists(
        "ghg_activity_record",
        "ix_ghg_activity_record_organization_boundary_id",
    )
    needs_emission_source_index = not _index_exists("ghg_activity_record", "ix_ghg_activity_record_emission_source_id")
    needs_organization_boundary_fk = not _foreign_key_exists(
        "ghg_activity_record",
        ["organization_boundary_id"],
        "carbon_organization_boundary",
    )
    needs_emission_source_fk = not _foreign_key_exists(
        "ghg_activity_record",
        ["emission_source_id"],
        "ghg_emission_source",
    )
    if any(
        (
            needs_organization_boundary_id,
            needs_emission_source_id,
            needs_organization_boundary_index,
            needs_emission_source_index,
            needs_organization_boundary_fk,
            needs_emission_source_fk,
        )
    ):
        with op.batch_alter_table("ghg_activity_record") as batch_op:
            if needs_organization_boundary_id:
                batch_op.add_column(sa.Column("organization_boundary_id", sa.BigInteger(), nullable=True))
            if needs_emission_source_id:
                batch_op.add_column(sa.Column("emission_source_id", sa.BigInteger(), nullable=True))
            if needs_organization_boundary_index:
                batch_op.create_index("ix_ghg_activity_record_organization_boundary_id", ["organization_boundary_id"])
            if needs_emission_source_index:
                batch_op.create_index("ix_ghg_activity_record_emission_source_id", ["emission_source_id"])
            if needs_organization_boundary_fk:
                batch_op.create_foreign_key(
                    "fk_ghg_activity_org_boundary",
                    "carbon_organization_boundary",
                    ["organization_boundary_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            if needs_emission_source_fk:
                batch_op.create_foreign_key(
                    "fk_ghg_activity_emission_source",
                    "ghg_emission_source",
                    ["emission_source_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
    models.GhgActivityAllocation.__table__.create(bind, checkfirst=True)
    for table_name in TENANT_TABLES:
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    bind = op.get_bind()
    models.GhgActivityAllocation.__table__.drop(bind, checkfirst=True)
    with op.batch_alter_table("ghg_activity_record") as batch_op:
        batch_op.drop_constraint(
            "fk_ghg_activity_emission_source",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_ghg_activity_org_boundary",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_ghg_activity_record_emission_source_id")
        batch_op.drop_index("ix_ghg_activity_record_organization_boundary_id")
        batch_op.drop_column("emission_source_id")
        batch_op.drop_column("organization_boundary_id")
    models.GhgEmissionSource.__table__.drop(bind, checkfirst=True)
