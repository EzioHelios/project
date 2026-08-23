"""replace legacy carbon assets with instrument and movement ledger

Revision ID: 2c3d4e5f6a7b
Revises: 1b2c3d4e5f6a
Create Date: 2026-08-24
"""

from __future__ import annotations

# ruff: noqa: EM101, TRY003
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.domain.carbon_assets import models

revision = "2c3d4e5f6a7b"
down_revision = "1b2c3d4e5f6a"
branch_labels = None
depends_on = None

NEW_TABLES = (
    models.CarbonAssetInstrument.__table__,
    models.CarbonAssetAccount.__table__,
    models.CarbonAssetLot.__table__,
    models.CarbonAssetMovement.__table__,
    models.CarbonComplianceRuleVersion.__table__,
    models.CarbonComplianceCycle.__table__,
    models.CarbonComplianceSettlement.__table__,
    models.CarbonComplianceSettlementLine.__table__,
    models.EnvironmentalAssetUsage.__table__,
    models.CarbonMarketQuote.__table__,
    models.CarbonCostScenario.__table__,
    models.CarbonCostRun.__table__,
)

OLD_TABLES = (
    "carbon_asset_forecast_scenario",
    "carbon_surrender_record",
    "carbon_asset_transaction",
    "carbon_credit_holding",
    "carbon_quota_allocation",
    "carbon_asset_account",
    "carbon_compliance_period",
)

PERMISSIONS = (
    ("carbon.assets.view", "查看碳资产", "查看碳资产账户、台账、履约、行情及成本分析"),
    ("carbon.assets.configure", "配置碳资产", "维护资产工具、账户和履约规则版本"),
    ("carbon.assets.ledger.post", "登记碳资产流水", "登记批次、不可变流水和更正冲销"),
    ("carbon.assets.compliance.manage", "管理碳履约", "维护履约周期并提交履约结算"),
    ("carbon.assets.market.manage", "维护碳行情", "导入或登记可追溯的市场行情"),
    ("carbon.assets.cost.run", "运行碳成本测算", "维护成本情景并生成冻结测算结果"),
)


def _enable_rls(table_name: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    policy = f"rls_{table_name}_tenant_scope"
    op.execute(sa.text(f"alter table {table_name} enable row level security"))
    op.execute(sa.text(f"alter table {table_name} force row level security"))
    op.execute(sa.text(f"drop policy if exists {policy} on {table_name}"))
    op.execute(sa.text(f"""
        create policy {policy} on {table_name}
        using (current_setting('app.tenant_bypass', true) = 'true' or team_id::text = nullif(current_setting('app.tenant_id', true), ''))
        with check (current_setting('app.tenant_bypass', true) = 'true' or team_id::text = nullif(current_setting('app.tenant_id', true), ''))
    """))


def _insert_permissions() -> None:
    bind = op.get_bind()
    permission = sa.table("permission", sa.column("id"), sa.column("code"), sa.column("name"), sa.column("description"), sa.column("module"), sa.column("created_at"), sa.column("updated_at"))
    role = sa.table("role", sa.column("id"), sa.column("name"), sa.column("slug"))
    link = sa.table("role_permission", sa.column("id"), sa.column("role_id"), sa.column("permission_id"), sa.column("created_at"), sa.column("updated_at"))
    view_role_id = bind.scalar(sa.select(role.c.id).where(sa.or_(role.c.slug == "application-access", role.c.name == "User")))
    admin_role_ids = list(bind.scalars(sa.select(role.c.id).where(sa.or_(role.c.slug.in_(("admin", "administrator")), role.c.name.in_(("Admin", "Administrator"))))))
    for code, name, description in PERMISSIONS:
        permission_id = bind.scalar(sa.select(permission.c.id).where(permission.c.code == code))
        if permission_id is None:
            permission_id = uuid4()
            bind.execute(permission.insert().values(id=permission_id, code=code, name=name, description=description, module="carbon_assets", created_at=sa.func.now(), updated_at=sa.func.now()))
        role_ids = [*admin_role_ids]
        if code == "carbon.assets.view" and view_role_id is not None:
            role_ids.append(view_role_id)
        for role_id in set(role_ids):
            if bind.scalar(sa.select(link.c.id).where(link.c.role_id == role_id, link.c.permission_id == permission_id)) is None:
                bind.execute(link.insert().values(id=uuid4(), role_id=role_id, permission_id=permission_id, created_at=sa.func.now(), updated_at=sa.func.now()))


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("alter table decarbonization_ccer_dossier drop constraint if exists fk_decarbonization_ccer_dossier_carbon_credit_holding_i_e6c8")
    op.alter_column("decarbonization_ccer_dossier", "carbon_credit_holding_id", new_column_name="carbon_asset_lot_id")
    for table_name in OLD_TABLES:
        op.drop_table(table_name)
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=False)
        _enable_rls(table.name)
    op.create_foreign_key(
        "fk_decarbonization_ccer_dossier_carbon_asset_lot",
        "decarbonization_ccer_dossier",
        "carbon_asset_lot",
        ["carbon_asset_lot_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _insert_permissions()


def downgrade() -> None:
    raise RuntimeError("The legacy mixed-asset model is intentionally not restorable.")
