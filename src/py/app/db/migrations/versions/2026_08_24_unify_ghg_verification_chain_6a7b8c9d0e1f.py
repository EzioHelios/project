"""Unify organization inventory reports and carbon verification projects.

Revision ID: 6a7b8c9d0e1f
Revises: 5f6a7b8c9d0e
Create Date: 2026-08-24
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "6a7b8c9d0e1f"
down_revision = "5f6a7b8c9d0e"
branch_labels = None
depends_on = None

PROJECT_TABLE = "carbon_verification_project"
PERMISSIONS = (
    ("carbon.verification.view", "查看碳核查项目", "查看核查项目、证据、发现和材料包"),
    ("carbon.verification.manage", "管理碳核查项目", "创建和维护核查项目及核查计划"),
    ("carbon.verification.evidence.manage", "管理核查证据", "上传、审核和关联核查证据"),
    ("carbon.verification.review", "复核碳核查发现", "复核发现整改并形成内部核查结论"),
    ("carbon.verification.export", "导出核查材料包", "生成并下载盘查报告与核查材料包"),
)


def upgrade() -> None:
    with op.batch_alter_table("carbon_verification_finding") as batch_op:
        batch_op.add_column(sa.Column("record_code", sa.String(length=96), nullable=True))
        batch_op.create_index("ix_carbon_verification_finding_record_code", ["record_code"])
    with op.batch_alter_table(PROJECT_TABLE) as batch_op:
        batch_op.add_column(sa.Column("inventory_report_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("calculation_run_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(
            sa.Column("assurance_level", sa.String(length=24), nullable=False, server_default="internal_review")
        )
        batch_op.add_column(sa.Column("materiality_threshold_pct", sa.Numeric(precision=7, scale=4), nullable=True))
        batch_op.add_column(sa.Column("verification_basis", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("sampling_strategy", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("site_visit_required", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(
            sa.Column("site_visit_status", sa.String(length=24), nullable=False, server_default="not_planned")
        )
        batch_op.add_column(
            sa.Column("conclusion_status", sa.String(length=24), nullable=False, server_default="pending")
        )
        batch_op.create_foreign_key(
            "fk_carbon_verification_project_inventory_report",
            "ghg_inventory_report",
            ["inventory_report_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_carbon_verification_project_calculation_run",
            "ghg_calculation_run",
            ["calculation_run_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_carbon_verification_project_inventory_report_id", ["inventory_report_id"])
        batch_op.create_index("ix_carbon_verification_project_calculation_run_id", ["calculation_run_id"])
        batch_op.create_index("ix_carbon_verification_project_assurance_level", ["assurance_level"])
        batch_op.create_index("ix_carbon_verification_project_site_visit_status", ["site_visit_status"])
        batch_op.create_index("ix_carbon_verification_project_conclusion_status", ["conclusion_status"])
        batch_op.create_index("ix_carbon_verification_project_report", ["team_id", "inventory_report_id", "status"])
        batch_op.create_index("ix_carbon_verification_project_run", ["team_id", "calculation_run_id", "status"])

    # Preserve existing projects when an unambiguous new report exists for the same
    # organization, period and boundary. Unmatched historical rows remain archived
    # records and are never used as a fallback calculation source.
    op.execute(
        sa.text(
            """
            update carbon_verification_project project
            set inventory_report_id = candidate.report_id,
                calculation_run_id = candidate.run_id
            from (
                select distinct on (report.team_id, report.reporting_org_id, report.reporting_period_id, report.organization_boundary_id)
                    report.team_id,
                    report.reporting_org_id,
                    report.reporting_period_id,
                    report.organization_boundary_id,
                    report.id as report_id,
                    report.run_id
                from ghg_inventory_report report
                order by report.team_id, report.reporting_org_id, report.reporting_period_id,
                         report.organization_boundary_id, report.version desc, report.id desc
            ) candidate
            where project.team_id = candidate.team_id
              and project.reporting_org_id = candidate.reporting_org_id
              and project.period_id = candidate.reporting_period_id
              and project.boundary_id = candidate.organization_boundary_id
              and project.inventory_report_id is null
            """
        )
    )
    op.execute(
        sa.text(
            """
            update carbon_verification_project
            set status = 'archived',
                readiness_status = 'blocked',
                remark = coalesce(remark || E'\n', '') || '历史项目未匹配到新版盘查报告, 已归档待迁移。'
            where inventory_report_id is null and status <> 'archived'
            """
        )
    )
    _insert_permissions()


def downgrade() -> None:
    _delete_permissions()
    with op.batch_alter_table(PROJECT_TABLE) as batch_op:
        batch_op.drop_index("ix_carbon_verification_project_run")
        batch_op.drop_index("ix_carbon_verification_project_report")
        batch_op.drop_index("ix_carbon_verification_project_conclusion_status")
        batch_op.drop_index("ix_carbon_verification_project_site_visit_status")
        batch_op.drop_index("ix_carbon_verification_project_assurance_level")
        batch_op.drop_index("ix_carbon_verification_project_calculation_run_id")
        batch_op.drop_index("ix_carbon_verification_project_inventory_report_id")
        batch_op.drop_constraint("fk_carbon_verification_project_calculation_run", type_="foreignkey")
        batch_op.drop_constraint("fk_carbon_verification_project_inventory_report", type_="foreignkey")
        batch_op.drop_column("conclusion_status")
        batch_op.drop_column("site_visit_status")
        batch_op.drop_column("site_visit_required")
        batch_op.drop_column("sampling_strategy")
        batch_op.drop_column("verification_basis")
        batch_op.drop_column("materiality_threshold_pct")
        batch_op.drop_column("assurance_level")
        batch_op.drop_column("calculation_run_id")
        batch_op.drop_column("inventory_report_id")
    with op.batch_alter_table("carbon_verification_finding") as batch_op:
        batch_op.drop_index("ix_carbon_verification_finding_record_code")
        batch_op.drop_column("record_code")


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
                module="carbon",
                created_at=sa.func.now(),
                updated_at=sa.func.now(),
            )
        )


def _delete_permissions() -> None:
    permission = sa.table("permission", sa.column("code"))
    op.get_bind().execute(permission.delete().where(permission.c.code.in_([item[0] for item in PERMISSIONS])))
