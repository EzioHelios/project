"""add lightweight SBTi, CDP, and RE100 climate-governance workbench

Revision ID: 1b2c3d4e5f6a
Revises: 0a1b2c3d4e5f
Create Date: 2026-08-24
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.domain.climate_governance import models

revision = "1b2c3d4e5f6a"
down_revision = "0a1b2c3d4e5f"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    models.ClimateProgram.__table__,
    models.ClimateTarget.__table__,
    models.ClimateDisclosureCycle.__table__,
    models.RenewableElectricityClaim.__table__,
    models.ClimateAssessmentRun.__table__,
)

PERMISSIONS = (
    ("carbon.climate.view", "查看气候目标与披露", "查看SBTi、CDP和RE100自动跟踪结果"),
    ("carbon.climate.manage", "管理气候计划", "维护气候计划、目标、披露周期和可再生电力属性"),
    ("carbon.climate.assess", "执行气候评估", "根据冻结数据和规则版本生成内部评估记录"),
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
                    module="climate_governance",
                    created_at=sa.func.now(),
                    updated_at=sa.func.now(),
                )
            )
        if code != "carbon.climate.view":
            continue
        role_id = bind.scalar(
            sa.select(role.c.id).where(sa.or_(role.c.slug == "application-access", role.c.name == "User"))
        )
        if role_id is None:
            continue
        existing = bind.scalar(
            sa.select(role_permission.c.id).where(
                role_permission.c.role_id == role_id,
                role_permission.c.permission_id == permission_id,
            )
        )
        if existing is None:
            bind.execute(
                role_permission.insert().values(
                    id=uuid4(),
                    role_id=role_id,
                    permission_id=permission_id,
                    created_at=sa.func.now(),
                    updated_at=sa.func.now(),
                )
            )


def upgrade() -> None:
    bind = op.get_bind()
    for table in TENANT_TABLES:
        table.create(bind=bind, checkfirst=False)
        _enable_tenant_rls(table.name)
    # This constraint was introduced in the follow-up 4e5f migration. The
    # imported model metadata already contains it on a fresh install, so remove
    # it here to keep this historical revision deterministic.
    op.drop_constraint(
        "uq_climate_claim_certificate_year",
        "climate_governance_renewable_claim",
        type_="unique",
    )
    _insert_permissions()


def downgrade() -> None:
    bind = op.get_bind()
    permission = sa.table("permission", sa.column("id"), sa.column("code"))
    role_permission = sa.table("role_permission", sa.column("permission_id"))
    permission_ids = sa.select(permission.c.id).where(permission.c.code.in_([code for code, _, _ in PERMISSIONS]))
    bind.execute(sa.delete(role_permission).where(role_permission.c.permission_id.in_(permission_ids)))
    bind.execute(sa.delete(permission).where(permission.c.code.in_([code for code, _, _ in PERMISSIONS])))
    for table in reversed(TENANT_TABLES):
        table.drop(bind=bind, checkfirst=True)
