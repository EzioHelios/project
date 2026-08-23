"""add project-based decarbonization and offline CCER development

Revision ID: f5a6b7c8d9e
Revises: e4f5a6b7c8d
Create Date: 2026-08-23
"""

from __future__ import annotations

# ruff: noqa: RUF001 - Chinese regulatory copy is intentional.
from datetime import date
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.domain.decarbonization import models
from app.domain.decarbonization.domain.methodologies import METHODOLOGY_CATALOG, methodology_payload

revision = "f5a6b7c8d9e"
down_revision = "e4f5a6b7c8d"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    models.ReductionTarget.__table__,
    models.ReductionProject.__table__,
    models.ReductionProjectResourceLink.__table__,
    models.ReductionProjectBoundary.__table__,
    models.ReductionBaselineScenario.__table__,
    models.ReductionApplicabilityAssessment.__table__,
    models.ReductionMonitoringPlan.__table__,
    models.ReductionCalculationRun.__table__,
    models.ReductionFinancialScenario.__table__,
    models.ReductionProjectReview.__table__,
    models.CcerDossier.__table__,
    models.ReductionAuditEvent.__table__,
)

PERMISSIONS = (
    ("carbon.reduction.view", "查看减碳管理", "查看减排目标、项目、方法学和分析结果"),
    ("carbon.reduction.target.manage", "管理减排目标", "创建、调整和发布减排目标"),
    ("carbon.reduction.project.manage", "管理减排项目", "维护项目、边界、基准线和监测计划"),
    ("carbon.reduction.calculate", "执行减排计算", "执行事前和事后项目减排量计算"),
    ("carbon.reduction.review", "复核减排项目", "执行内部复核并登记第三方审定核查结论"),
    ("carbon.reduction.methodology.manage", "管理企业方法学", "管理企业内部方法学版本"),
    ("carbon.reduction.ccer.manage", "管理CCER卷宗", "维护离线登记、签发和碳资产衔接信息"),
    ("carbon.reduction.export", "导出减碳成果", "导出项目、监测、计算和申报材料"),
)


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
    role = sa.table("role", sa.column("id"), sa.column("name"), sa.column("slug"))
    role_permission = sa.table(
        "role_permission",
        sa.column("id"),
        sa.column("role_id"),
        sa.column("permission_id"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    for code, name, description in PERMISSIONS:
        permission_id = bind.scalar(sa.select(permission.c.id).where(permission.c.code == code))
        if permission_id is None:
            permission_id = uuid4()
            bind.execute(
                permission.insert().values(
                    id=permission_id,
                    code=code,
                    name=name,
                    description=description,
                    module="carbon_reduction",
                    created_at=sa.func.now(),
                    updated_at=sa.func.now(),
                )
            )
        if code == "carbon.reduction.view":
            role_id = bind.scalar(
                sa.select(role.c.id).where(
                    sa.or_(role.c.slug == "application-access", role.c.name == "User")
                )
            )
            existing = (
                bind.scalar(
                    sa.select(role_permission.c.id).where(
                        role_permission.c.role_id == role_id,
                        role_permission.c.permission_id == permission_id,
                    )
                )
                if role_id is not None
                else None
            )
            if role_id is not None and existing is None:
                bind.execute(
                    role_permission.insert().values(
                        id=uuid4(),
                        role_id=role_id,
                        permission_id=permission_id,
                        created_at=sa.func.now(),
                        updated_at=sa.func.now(),
                    )
                )


def _insert_methodologies() -> None:
    bind = op.get_bind()
    table = models.ReductionMethodologyVersion.__table__
    for item in METHODOLOGY_CATALOG:
        payload = methodology_payload(item)
        bind.execute(
            table.insert().values(
                code=item.code,
                version=item.version,
                name=item.name,
                sector=item.sector,
                method_kind="ccer",
                status="published",
                published_on=date.fromisoformat(item.published_on),
                effective_from=date.fromisoformat(item.published_on),
                source_url=item.source_url,
                executable=item.executable,
                adapter_code=item.adapter_code,
                parameter_schema=payload["parameters"],
                applicability_schema=payload["applicabilityChecks"],
                monitoring_schema=payload["monitoringItems"],
                evidence_schema=payload["evidenceItems"],
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    models.ReductionMethodologyVersion.__table__.create(bind=bind, checkfirst=False)
    for table in TENANT_TABLES:
        table.create(bind=bind, checkfirst=False)
        _enable_tenant_rls(table.name)
    _insert_methodologies()
    _insert_permissions()

    # Remove a legacy demo claim that incorrectly presented ordinary distributed PV as a new CCER project.
    bind.execute(
        sa.text(
            """
            update carbon_credit_holding
            set project_code = 'MVP-CCER-HIST-01',
                project_name = '历史签发自愿减排项目',
                source_name = '企业历史资产台账',
                remark = '历史签发资产示例；不代表普通屋顶光伏可作为新CCER项目申报。'
            where holding_no = 'MVP-CCER-2026'
              and project_code = 'MVP-CCER-PV-01'
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    permission = sa.table("permission", sa.column("id"), sa.column("code"))
    role_permission = sa.table("role_permission", sa.column("permission_id"))
    permission_ids = sa.select(permission.c.id).where(permission.c.code.in_([code for code, _, _ in PERMISSIONS]))
    bind.execute(sa.delete(role_permission).where(role_permission.c.permission_id.in_(permission_ids)))
    bind.execute(sa.delete(permission).where(permission.c.code.in_([code for code, _, _ in PERMISSIONS])))
    for table in reversed(TENANT_TABLES):
        table.drop(bind=bind, checkfirst=True)
    models.ReductionMethodologyVersion.__table__.drop(bind=bind, checkfirst=True)
