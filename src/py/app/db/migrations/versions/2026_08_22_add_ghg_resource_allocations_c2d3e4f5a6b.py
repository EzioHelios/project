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
    with op.batch_alter_table("ghg_activity_record") as batch_op:
        batch_op.add_column(sa.Column("organization_boundary_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("emission_source_id", sa.BigInteger(), nullable=True))
        batch_op.create_index("ix_ghg_activity_record_organization_boundary_id", ["organization_boundary_id"])
        batch_op.create_index("ix_ghg_activity_record_emission_source_id", ["emission_source_id"])
        batch_op.create_foreign_key(
            "fk_ghg_activity_org_boundary",
            "carbon_organization_boundary",
            ["organization_boundary_id"],
            ["id"],
            ondelete="SET NULL",
        )
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
