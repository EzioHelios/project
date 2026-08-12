"""add microgrid forecasting optimization and shadow dispatch domain

Revision ID: a0b1c2d3e4f5
Revises: 9a0b1c2d3e4f
Create Date: 2026-08-12
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.domain.microgrid import models

revision = "a0b1c2d3e4f5"
down_revision = "9a0b1c2d3e4f"
branch_labels = None
depends_on = None

MICROGRID_TABLES = (
    models.MicrogridSite.__table__,
    models.MicrogridAsset.__table__,
    models.MicrogridScenario.__table__,
    models.FlexibilityContract.__table__,
    models.MicrogridTelemetryFact.__table__,
    models.MicrogridWeatherFact.__table__,
    models.MicrogridAssetState.__table__,
    models.ForecastRun.__table__,
    models.ForecastPoint.__table__,
    models.OptimizationRun.__table__,
    models.OptimizationSchedulePoint.__table__,
    models.DispatchBatch.__table__,
    models.DispatchReceipt.__table__,
)

PERMISSIONS = (
    ("microgrid.view", "查看微电网", "查看微电网运行、预测和优化结果"),
    ("microgrid.configure", "配置微电网", "维护场景、设备参数和柔性契约"),
    ("microgrid.forecast.run", "运行微电网预测", "创建负荷、光伏和SOC预测"),
    ("microgrid.optimize.run", "运行微电网优化", "执行滚动调度优化"),
    ("microgrid.dispatch.simulate", "模拟微电网调度", "将可行计划提交到模拟调度适配器"),
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
    connection = op.get_bind()
    permission_table = sa.table(
        "permission",
        sa.column("id"),
        sa.column("code"),
        sa.column("name"),
        sa.column("description"),
        sa.column("module"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    role_table = sa.table("role", sa.column("id"), sa.column("name"))
    role_permission_table = sa.table(
        "role_permission",
        sa.column("id"),
        sa.column("role_id"),
        sa.column("permission_id"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    now = sa.func.now()
    for code, name, description in PERMISSIONS:
        permission_id = connection.scalar(sa.select(permission_table.c.id).where(permission_table.c.code == code))
        if permission_id is None:
            permission_id = uuid4()
            connection.execute(
                permission_table.insert().values(
                    id=permission_id,
                    code=code,
                    name=name,
                    description=description,
                    module="microgrid",
                    created_at=now,
                    updated_at=now,
                )
            )
        if code == "microgrid.view":
            role_id = connection.scalar(sa.select(role_table.c.id).where(role_table.c.name == "User"))
            if role_id is not None:
                existing = connection.scalar(
                    sa.select(role_permission_table.c.id).where(
                        role_permission_table.c.role_id == role_id,
                        role_permission_table.c.permission_id == permission_id,
                    )
                )
                if existing is None:
                    connection.execute(
                        role_permission_table.insert().values(
                            id=uuid4(),
                            role_id=role_id,
                            permission_id=permission_id,
                            created_at=now,
                            updated_at=now,
                        )
                    )


def upgrade() -> None:
    bind = op.get_bind()
    for table in MICROGRID_TABLES:
        table.create(bind=bind, checkfirst=False)
        _enable_tenant_rls(table.name)
    _insert_permissions()


def downgrade() -> None:
    bind = op.get_bind()
    permission_codes = [code for code, _, _ in PERMISSIONS]
    permission_table = sa.table("permission", sa.column("id"), sa.column("code"))
    role_permission_table = sa.table("role_permission", sa.column("permission_id"))
    permission_ids = sa.select(permission_table.c.id).where(permission_table.c.code.in_(permission_codes))
    bind.execute(
        sa.delete(role_permission_table).where(role_permission_table.c.permission_id.in_(permission_ids))
    )
    bind.execute(sa.delete(permission_table).where(permission_table.c.code.in_(permission_codes)))
    for table in reversed(MICROGRID_TABLES):
        table.drop(bind=bind, checkfirst=True)
