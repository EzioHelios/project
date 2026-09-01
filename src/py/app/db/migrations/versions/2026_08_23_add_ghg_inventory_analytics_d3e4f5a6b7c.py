"""add organization GHG analytics context and internal reports

Revision ID: d3e4f5a6b7c
Revises: c2d3e4f5a6b
Create Date: 2026-08-23
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.domain.ghg_inventory import models

revision = "d3e4f5a6b7c"
down_revision = "c2d3e4f5a6b"
branch_labels = None
depends_on = None

REPORT_TABLES = (models.GhgInventoryReport.__table__, models.GhgInventoryReportReview.__table__)
PERMISSIONS = (
    ("carbon.inventory.report.manage", "编制温室气体盘查报告", "根据正式核算运行编制盘查报告"),
    ("carbon.inventory.report.review", "审核温室气体盘查报告", "提交、审核或退回盘查报告"),
    ("carbon.inventory.report.publish", "发布温室气体盘查报告", "发布已批准的盘查报告"),
    ("carbon.inventory.export", "导出温室气体盘查成果", "导出盘查结果、证据索引和报告"),
)


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


def _insert_permissions() -> None:
    bind = op.get_bind()
    permission = sa.table(
        "permission",
        sa.column("id"),
        sa.column("code"),
        sa.column("name"),
        sa.column("description"),
        sa.column("module"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    for code, name, description in PERMISSIONS:
        if bind.scalar(sa.select(permission.c.id).where(permission.c.code == code)) is not None:
            continue
        bind.execute(
            permission.insert().values(
                id=uuid4(),
                code=code,
                name=name,
                description=description,
                module="carbon_inventory",
                created_at=sa.func.now(),
                updated_at=sa.func.now(),
            )
        )


def upgrade() -> None:
    needs_reporting_org_id = not _column_exists("ghg_calculation_run", "reporting_org_id")
    needs_organization_boundary_id = not _column_exists("ghg_calculation_run", "organization_boundary_id")
    needs_default_scope2_method = not _column_exists("ghg_calculation_run", "default_scope2_method")
    needs_summary_snapshot = not _column_exists("ghg_calculation_run", "summary_snapshot")
    needs_quality_snapshot = not _column_exists("ghg_calculation_run", "quality_snapshot")
    needs_reporting_org_index = not _index_exists("ghg_calculation_run", "ix_ghg_calculation_run_reporting_org_id")
    needs_boundary_index = not _index_exists("ghg_calculation_run", "ix_ghg_calculation_run_organization_boundary_id")
    needs_scope2_method_index = not _index_exists("ghg_calculation_run", "ix_ghg_calculation_run_default_scope2_method")
    needs_reporting_org_fk = not _foreign_key_exists(
        "ghg_calculation_run",
        ["reporting_org_id"],
        "carbon_reporting_organization",
    )
    needs_boundary_fk = not _foreign_key_exists(
        "ghg_calculation_run",
        ["organization_boundary_id"],
        "carbon_organization_boundary",
    )
    if any(
        (
            needs_reporting_org_id,
            needs_organization_boundary_id,
            needs_default_scope2_method,
            needs_summary_snapshot,
            needs_quality_snapshot,
            needs_reporting_org_index,
            needs_boundary_index,
            needs_scope2_method_index,
            needs_reporting_org_fk,
            needs_boundary_fk,
        )
    ):
        with op.batch_alter_table("ghg_calculation_run") as batch_op:
            if needs_reporting_org_id:
                batch_op.add_column(sa.Column("reporting_org_id", sa.BigInteger(), nullable=True))
            if needs_organization_boundary_id:
                batch_op.add_column(sa.Column("organization_boundary_id", sa.BigInteger(), nullable=True))
            if needs_default_scope2_method:
                batch_op.add_column(
                    sa.Column("default_scope2_method", sa.String(length=24), server_default="location", nullable=False)
                )
            if needs_summary_snapshot:
                batch_op.add_column(
                    sa.Column("summary_snapshot", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False)
                )
            if needs_quality_snapshot:
                batch_op.add_column(
                    sa.Column("quality_snapshot", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False)
                )
            if needs_reporting_org_index:
                batch_op.create_index("ix_ghg_calculation_run_reporting_org_id", ["reporting_org_id"])
            if needs_boundary_index:
                batch_op.create_index("ix_ghg_calculation_run_organization_boundary_id", ["organization_boundary_id"])
            if needs_scope2_method_index:
                batch_op.create_index("ix_ghg_calculation_run_default_scope2_method", ["default_scope2_method"])
            if needs_reporting_org_fk:
                batch_op.create_foreign_key(
                    "fk_ghg_calculation_run_reporting_org",
                    "carbon_reporting_organization",
                    ["reporting_org_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            if needs_boundary_fk:
                batch_op.create_foreign_key(
                    "fk_ghg_calculation_run_boundary",
                    "carbon_organization_boundary",
                    ["organization_boundary_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                update ghg_calculation_run as run
                set reporting_org_id = period.reporting_org_id
                from carbon_reporting_period as period
                where run.reporting_period_id = period.id
                  and run.reporting_org_id is null
                """
            )
        )
        op.execute(
            sa.text(
                """
                update ghg_calculation_run as run
                set organization_boundary_id = candidate.organization_boundary_id
                from (
                    select team_id, inventory_code, min(organization_boundary_id) as organization_boundary_id
                    from ghg_activity_record
                    where organization_boundary_id is not null
                    group by team_id, inventory_code
                    having count(distinct organization_boundary_id) = 1
                ) as candidate
                where run.team_id = candidate.team_id
                  and run.inventory_code = candidate.inventory_code
                  and run.organization_boundary_id is null
                """
            )
        )

    bind = op.get_bind()
    for table in REPORT_TABLES:
        table.create(bind=bind, checkfirst=False)
        _enable_tenant_rls(table.name)
    _insert_permissions()


def downgrade() -> None:
    bind = op.get_bind()
    permission = sa.table("permission", sa.column("id"), sa.column("code"))
    role_permission = sa.table("role_permission", sa.column("permission_id"))
    permission_ids = sa.select(permission.c.id).where(permission.c.code.in_([code for code, _, _ in PERMISSIONS]))
    bind.execute(sa.delete(role_permission).where(role_permission.c.permission_id.in_(permission_ids)))
    bind.execute(sa.delete(permission).where(permission.c.code.in_([code for code, _, _ in PERMISSIONS])))
    for table in reversed(REPORT_TABLES):
        table.drop(bind=bind, checkfirst=True)
    with op.batch_alter_table("ghg_calculation_run") as batch_op:
        batch_op.drop_constraint("fk_ghg_calculation_run_boundary", type_="foreignkey")
        batch_op.drop_constraint("fk_ghg_calculation_run_reporting_org", type_="foreignkey")
        batch_op.drop_index("ix_ghg_calculation_run_default_scope2_method")
        batch_op.drop_index("ix_ghg_calculation_run_organization_boundary_id")
        batch_op.drop_index("ix_ghg_calculation_run_reporting_org_id")
        batch_op.drop_column("quality_snapshot")
        batch_op.drop_column("summary_snapshot")
        batch_op.drop_column("default_scope2_method")
        batch_op.drop_column("organization_boundary_id")
        batch_op.drop_column("reporting_org_id")
