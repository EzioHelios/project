"""add carbon assets tables

Revision ID: ef5a6b7c8d9
Revises: de4f5a6b7c8
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "ef5a6b7c8d9"
down_revision = "de4f5a6b7c8"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

PERIOD_TABLE = "carbon_compliance_period"
ACCOUNT_TABLE = "carbon_asset_account"
ALLOWANCE_TABLE = "carbon_quota_allocation"
CREDIT_TABLE = "carbon_credit_holding"
TRANSACTION_TABLE = "carbon_asset_transaction"
SURRENDER_TABLE = "carbon_surrender_record"
TABLES = (PERIOD_TABLE, ACCOUNT_TABLE, ALLOWANCE_TABLE, CREDIT_TABLE, TRANSACTION_TABLE, SURRENDER_TABLE)


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
        PERIOD_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("period_code", sa.String(length=64), nullable=False),
        sa.Column("period_name", sa.String(length=128), nullable=False),
        sa.Column("market", sa.String(length=64), nullable=False, server_default="national"),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("surrender_due_date", sa.Date(), nullable=True),
        sa.Column("boundary_id", _id_type(), nullable=True),
        sa.Column("accounting_batch_id", _id_type(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("risk_threshold_yellow", sa.Numeric(precision=8, scale=4), nullable=False, server_default="0.0300"),
        sa.Column("risk_threshold_orange", sa.Numeric(precision=8, scale=4), nullable=False, server_default="0.0800"),
        sa.Column("risk_threshold_red", sa.Numeric(precision=8, scale=4), nullable=False, server_default="0.1500"),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["boundary_id"], ["carbon_organization_boundary.id"], name="fk_carbon_compliance_period_boundary", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["accounting_batch_id"], ["carbon_accounting_batch.id"], name="fk_carbon_compliance_period_batch", ondelete="SET NULL"
        ),
        _tenant_fk(PERIOD_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{PERIOD_TABLE}")),
        sa.UniqueConstraint("team_id", "period_code", name="uq_carbon_compliance_period_team_code"),
    )
    for column in ("period_code", "market", "period_start", "period_end", "boundary_id", "accounting_batch_id", "status", "team_id"):
        op.create_index(op.f(f"ix_{PERIOD_TABLE}_{column}"), PERIOD_TABLE, [column])
    op.create_index("ix_carbon_compliance_period_team_status_market", PERIOD_TABLE, ["team_id", "status", "market"])
    op.create_index("ix_carbon_compliance_period_range", PERIOD_TABLE, ["team_id", "period_start", "period_end"])
    for column in ("market", "status", "risk_threshold_yellow", "risk_threshold_orange", "risk_threshold_red"):
        op.alter_column(PERIOD_TABLE, column, server_default=None)

    op.create_table(
        ACCOUNT_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("account_code", sa.String(length=64), nullable=False),
        sa.Column("account_name", sa.String(length=128), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=64), nullable=False, server_default="national"),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="CNY"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("registry_account_no", sa.String(length=128), nullable=True),
        sa.Column("owner_name", sa.String(length=128), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk(ACCOUNT_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{ACCOUNT_TABLE}")),
        sa.UniqueConstraint("team_id", "account_code", name="uq_carbon_asset_account_team_code"),
    )
    for column in ("account_code", "asset_type", "market", "status", "team_id"):
        op.create_index(op.f(f"ix_{ACCOUNT_TABLE}_{column}"), ACCOUNT_TABLE, [column])
    op.create_index("ix_carbon_asset_account_type_status", ACCOUNT_TABLE, ["team_id", "asset_type", "status"])
    op.create_index("ix_carbon_asset_account_team_market", ACCOUNT_TABLE, ["team_id", "market"])
    for column in ("market", "currency", "status"):
        op.alter_column(ACCOUNT_TABLE, column, server_default=None)

    op.create_table(
        ALLOWANCE_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("period_id", _id_type(), nullable=False),
        sa.Column("account_id", _id_type(), nullable=False),
        sa.Column("allocation_no", sa.String(length=64), nullable=False),
        sa.Column("quota_type", sa.String(length=32), nullable=False, server_default="CEA"),
        sa.Column("allocated_amount", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("adjustment_amount", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("used_amount", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("frozen_amount", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=32), nullable=False, server_default="tCO2e"),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["period_id"], [f"{PERIOD_TABLE}.id"], name="fk_carbon_quota_allocation_period", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], [f"{ACCOUNT_TABLE}.id"], name="fk_carbon_quota_allocation_account", ondelete="CASCADE"),
        _tenant_fk(ALLOWANCE_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{ALLOWANCE_TABLE}")),
        sa.UniqueConstraint("team_id", "allocation_no", name="uq_carbon_quota_allocation_team_no"),
    )
    for column in ("period_id", "account_id", "allocation_no", "quota_type", "team_id"):
        op.create_index(op.f(f"ix_{ALLOWANCE_TABLE}_{column}"), ALLOWANCE_TABLE, [column])
    op.create_index("ix_carbon_quota_allocation_period", ALLOWANCE_TABLE, ["team_id", "period_id", "quota_type"])
    op.create_index("ix_carbon_quota_allocation_account", ALLOWANCE_TABLE, ["team_id", "account_id"])
    for column in ("quota_type", "allocated_amount", "adjustment_amount", "used_amount", "frozen_amount", "unit"):
        op.alter_column(ALLOWANCE_TABLE, column, server_default=None)

    op.create_table(
        CREDIT_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("account_id", _id_type(), nullable=False),
        sa.Column("holding_no", sa.String(length=64), nullable=False),
        sa.Column("credit_type", sa.String(length=32), nullable=False),
        sa.Column("project_code", sa.String(length=64), nullable=True),
        sa.Column("project_name", sa.String(length=128), nullable=True),
        sa.Column("registry", sa.String(length=128), nullable=True),
        sa.Column("vintage_year", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("used_quantity", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("frozen_quantity", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=32), nullable=False, server_default="tCO2e"),
        sa.Column("market_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="CNY"),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["account_id"], [f"{ACCOUNT_TABLE}.id"], name="fk_carbon_credit_holding_account", ondelete="CASCADE"),
        _tenant_fk(CREDIT_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{CREDIT_TABLE}")),
        sa.UniqueConstraint("team_id", "holding_no", name="uq_carbon_credit_holding_team_no"),
    )
    for column in ("account_id", "holding_no", "credit_type", "project_code", "vintage_year", "status", "team_id"):
        op.create_index(op.f(f"ix_{CREDIT_TABLE}_{column}"), CREDIT_TABLE, [column])
    op.create_index("ix_carbon_credit_holding_account", CREDIT_TABLE, ["team_id", "account_id", "credit_type"])
    op.create_index("ix_carbon_credit_holding_team_status", CREDIT_TABLE, ["team_id", "status"])
    for column in ("quantity", "used_quantity", "frozen_quantity", "unit", "currency", "status"):
        op.alter_column(CREDIT_TABLE, column, server_default=None)

    op.create_table(
        TRANSACTION_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("account_id", _id_type(), nullable=False),
        sa.Column("transaction_no", sa.String(length=64), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="CNY"),
        sa.Column("fee_rate", sa.Numeric(precision=10, scale=6), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(precision=10, scale=6), nullable=False, server_default="0"),
        sa.Column("trade_date", sa.Date(), nullable=True),
        sa.Column("counterparty", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="simulated"),
        sa.Column("scenario_payload", sa.JSON(), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["account_id"], [f"{ACCOUNT_TABLE}.id"], name="fk_carbon_asset_transaction_account", ondelete="CASCADE"),
        _tenant_fk(TRANSACTION_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{TRANSACTION_TABLE}")),
        sa.UniqueConstraint("team_id", "transaction_no", name="uq_carbon_asset_transaction_team_no"),
    )
    for column in ("account_id", "transaction_no", "asset_type", "transaction_type", "trade_date", "status", "team_id"):
        op.create_index(op.f(f"ix_{TRANSACTION_TABLE}_{column}"), TRANSACTION_TABLE, [column])
    op.create_index("ix_carbon_asset_transaction_account", TRANSACTION_TABLE, ["team_id", "account_id", "asset_type"])
    op.create_index("ix_carbon_asset_transaction_date", TRANSACTION_TABLE, ["team_id", "trade_date", "status"])
    for column in ("amount", "unit_price", "currency", "fee_rate", "tax_rate", "status"):
        op.alter_column(TRANSACTION_TABLE, column, server_default=None)

    op.create_table(
        SURRENDER_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("period_id", _id_type(), nullable=False),
        sa.Column("account_id", _id_type(), nullable=False),
        sa.Column("surrender_no", sa.String(length=64), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("quota_allocation_id", _id_type(), nullable=True),
        sa.Column("credit_holding_id", _id_type(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=32), nullable=False, server_default="tCO2e"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="completed"),
        sa.Column("surrendered_at", sa.DateTime(), nullable=True),
        sa.Column("purpose", sa.String(length=64), nullable=False, server_default="compliance"),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["period_id"], [f"{PERIOD_TABLE}.id"], name="fk_carbon_surrender_record_period", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], [f"{ACCOUNT_TABLE}.id"], name="fk_carbon_surrender_record_account", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["quota_allocation_id"], [f"{ALLOWANCE_TABLE}.id"], name="fk_carbon_surrender_record_quota", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["credit_holding_id"], [f"{CREDIT_TABLE}.id"], name="fk_carbon_surrender_record_credit", ondelete="SET NULL"
        ),
        _tenant_fk(SURRENDER_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{SURRENDER_TABLE}")),
        sa.UniqueConstraint("team_id", "surrender_no", name="uq_carbon_surrender_record_team_no"),
    )
    for column in ("period_id", "account_id", "surrender_no", "asset_type", "quota_allocation_id", "credit_holding_id", "status", "team_id"):
        op.create_index(op.f(f"ix_{SURRENDER_TABLE}_{column}"), SURRENDER_TABLE, [column])
    op.create_index("ix_carbon_surrender_record_period", SURRENDER_TABLE, ["team_id", "period_id", "asset_type"])
    op.create_index("ix_carbon_surrender_record_team_status", SURRENDER_TABLE, ["team_id", "status"])
    for column in ("amount", "unit", "status", "purpose"):
        op.alter_column(SURRENDER_TABLE, column, server_default=None)

    for table_name in TABLES:
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        _disable_tenant_rls(table_name)
        op.drop_table(table_name)
