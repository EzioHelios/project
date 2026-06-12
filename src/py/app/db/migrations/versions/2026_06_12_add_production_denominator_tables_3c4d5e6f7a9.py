"""add production denominator tables

Revision ID: 3c4d5e6f7a9
Revises: 2b3c4d5e6f8
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "3c4d5e6f7a9"
down_revision = "2b3c4d5e6f8"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]


TABLES = (
    "dataapp_productionproduct",
    "dataapp_productprice",
    "dataapp_productionoutputfact",
    "dataapp_productionresourcebinding",
)


def _id_type() -> sa.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


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


def upgrade() -> None:
    op.create_table(
        "dataapp_productionproduct",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("spec", sa.String(length=128), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("default_unit", sa.String(length=16), nullable=True),
        sa.Column("standard_unit", sa.String(length=16), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk("dataapp_productionproduct"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_productionproduct")),
        sa.UniqueConstraint("team_id", "code", name="uq_dataapp_productionproduct_team_code"),
    )
    op.create_index(op.f("ix_dataapp_productionproduct_code"), "dataapp_productionproduct", ["code"])
    op.create_index(op.f("ix_dataapp_productionproduct_category"), "dataapp_productionproduct", ["category"])
    op.create_index(op.f("ix_dataapp_productionproduct_is_enabled"), "dataapp_productionproduct", ["is_enabled"])
    op.create_index(op.f("ix_dataapp_productionproduct_team_id"), "dataapp_productionproduct", ["team_id"])
    op.create_index("ix_production_product_team_category", "dataapp_productionproduct", ["team_id", "category"])
    op.alter_column("dataapp_productionproduct", "is_enabled", server_default=None)

    op.create_table(
        "dataapp_productprice",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("price_type", sa.String(length=32), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("tax_included", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_system", sa.String(length=32), nullable=True),
        sa.Column("source_record_id", sa.String(length=128), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk("dataapp_productprice"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_productprice")),
    )
    op.create_index(op.f("ix_dataapp_productprice_product_code"), "dataapp_productprice", ["product_code"])
    op.create_index(op.f("ix_dataapp_productprice_price_type"), "dataapp_productprice", ["price_type"])
    op.create_index(op.f("ix_dataapp_productprice_valid_from"), "dataapp_productprice", ["valid_from"])
    op.create_index(op.f("ix_dataapp_productprice_valid_to"), "dataapp_productprice", ["valid_to"])
    op.create_index(op.f("ix_dataapp_productprice_team_id"), "dataapp_productprice", ["team_id"])
    op.create_index(
        "ix_product_price_team_product_type",
        "dataapp_productprice",
        ["team_id", "product_code", "price_type"],
    )
    op.create_index("ix_product_price_validity", "dataapp_productprice", ["valid_from", "valid_to"])
    op.alter_column("dataapp_productprice", "currency", server_default=None)
    op.alter_column("dataapp_productprice", "tax_included", server_default=None)

    op.create_table(
        "dataapp_productionoutputfact",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("production_order_no", sa.String(length=64), nullable=True),
        sa.Column("batch_no", sa.String(length=64), nullable=True),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("product_name", sa.String(length=128), nullable=True),
        sa.Column("product_spec", sa.String(length=128), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("good_qty", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("scrap_qty", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("rework_qty", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("standard_qty", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("standard_unit", sa.String(length=16), nullable=True),
        sa.Column("quality_status", sa.String(length=32), nullable=True),
        sa.Column("record_status", sa.String(length=16), nullable=False, server_default="confirmed"),
        sa.Column("work_center_code", sa.String(length=64), nullable=True),
        sa.Column("line_code", sa.String(length=64), nullable=True),
        sa.Column("area_id", sa.Integer(), nullable=True),
        sa.Column("area_name", sa.String(length=128), nullable=True),
        sa.Column("equipment_code", sa.String(length=64), nullable=True),
        sa.Column("equipment_name", sa.String(length=128), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk("dataapp_productionoutputfact"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_productionoutputfact")),
        sa.UniqueConstraint(
            "team_id",
            "source_system",
            "source_record_id",
            name="uq_production_output_team_source_record",
        ),
    )
    for column in (
        "production_order_no",
        "batch_no",
        "product_code",
        "period_start",
        "period_end",
        "quality_status",
        "record_status",
        "work_center_code",
        "line_code",
        "area_id",
        "equipment_code",
        "team_id",
    ):
        op.create_index(
            op.f(f"ix_dataapp_productionoutputfact_{column}"),
            "dataapp_productionoutputfact",
            [column],
        )
    op.create_index(
        "ix_production_output_team_product_period",
        "dataapp_productionoutputfact",
        ["team_id", "product_code", "period_start"],
    )
    op.create_index(
        "ix_production_output_resource",
        "dataapp_productionoutputfact",
        ["line_code", "area_id", "equipment_code"],
    )
    op.alter_column("dataapp_productionoutputfact", "source_system", server_default=None)
    op.alter_column("dataapp_productionoutputfact", "record_status", server_default=None)

    op.create_table(
        "dataapp_productionresourcebinding",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("work_center_code", sa.String(length=64), nullable=True),
        sa.Column("line_code", sa.String(length=64), nullable=True),
        sa.Column("area_id", sa.Integer(), nullable=True),
        sa.Column("equipment_id", sa.Integer(), nullable=True),
        sa.Column("binding_type", sa.String(length=16), nullable=False, server_default="primary"),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk("dataapp_productionresourcebinding"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_productionresourcebinding")),
    )
    for column in (
        "product_code",
        "work_center_code",
        "line_code",
        "area_id",
        "equipment_id",
        "binding_type",
        "team_id",
    ):
        op.create_index(
            op.f(f"ix_dataapp_productionresourcebinding_{column}"),
            "dataapp_productionresourcebinding",
            [column],
        )
    op.create_index(
        "ix_production_binding_team_product",
        "dataapp_productionresourcebinding",
        ["team_id", "product_code"],
    )
    op.create_index(
        "ix_production_binding_resource",
        "dataapp_productionresourcebinding",
        ["work_center_code", "line_code", "area_id", "equipment_id"],
    )
    op.alter_column("dataapp_productionresourcebinding", "binding_type", server_default=None)

    for table_name in TABLES:
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        _disable_tenant_rls(table_name)
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
