"""add product footprint tables

Revision ID: cd3e4f5a6b7
Revises: bc2d3e4f5a6
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "cd3e4f5a6b7"
down_revision = "bc2d3e4f5a6"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

STUDY_TABLE = "carbon_product_footprint_study"
BOUNDARY_TABLE = "carbon_product_system_boundary"
STAGE_TABLE = "carbon_product_lifecycle_stage"
ITEM_TABLE = "carbon_product_footprint_inventory_item"
ALLOCATION_TABLE = "carbon_product_footprint_allocation_rule"
RESULT_TABLE = "carbon_product_footprint_result"
TABLES = (STUDY_TABLE, BOUNDARY_TABLE, STAGE_TABLE, ITEM_TABLE, ALLOCATION_TABLE, RESULT_TABLE)


def _id_type() -> sa.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


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
        STUDY_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("study_code", sa.String(length=64), nullable=False),
        sa.Column("study_name", sa.String(length=128), nullable=False),
        sa.Column("product_id", _id_type(), nullable=True),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("product_name", sa.String(length=128), nullable=True),
        sa.Column("product_spec", sa.String(length=128), nullable=True),
        sa.Column("product_category", sa.String(length=64), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=False, server_default="ISO 14067"),
        sa.Column("standard_name", sa.String(length=255), nullable=True),
        sa.Column("pcr_code", sa.String(length=128), nullable=True),
        sa.Column("functional_unit", sa.String(length=128), nullable=True),
        sa.Column("declared_unit", sa.String(length=128), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("boundary_type", sa.String(length=32), nullable=False, server_default="cradle_to_gate"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("result_status", sa.String(length=32), nullable=False, server_default="not_calculated"),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["product_id"], ["dataapp_productionproduct.id"], name="fk_product_footprint_study_product", ondelete="SET NULL"),
        _tenant_fk(STUDY_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{STUDY_TABLE}")),
        sa.UniqueConstraint("team_id", "study_code", name="uq_product_footprint_study_team_code"),
    )
    for column in (
        "study_code",
        "product_id",
        "product_code",
        "product_category",
        "period_start",
        "period_end",
        "boundary_type",
        "status",
        "result_status",
        "team_id",
    ):
        op.create_index(op.f(f"ix_{STUDY_TABLE}_{column}"), STUDY_TABLE, [column])
    op.create_index("ix_product_footprint_study_product", STUDY_TABLE, ["team_id", "product_code", "status"])
    op.create_index("ix_product_footprint_study_period", STUDY_TABLE, ["team_id", "period_start", "period_end"])
    for column in ("standard_code", "boundary_type", "status", "result_status"):
        op.alter_column(STUDY_TABLE, column, server_default=None)

    op.create_table(
        BOUNDARY_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("study_id", _id_type(), nullable=False),
        sa.Column("boundary_type", sa.String(length=32), nullable=False, server_default="cradle_to_gate"),
        sa.Column("included_stages", sa.JSON(), nullable=True),
        sa.Column("excluded_stages", sa.JSON(), nullable=True),
        sa.Column("cutoff_rule", sa.Text(), nullable=True),
        sa.Column("geography", sa.String(length=128), nullable=True),
        sa.Column("technology_scope", sa.String(length=255), nullable=True),
        sa.Column("temporal_scope", sa.String(length=128), nullable=True),
        sa.Column("assumption", sa.Text(), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["study_id"], [f"{STUDY_TABLE}.id"], name="fk_product_system_boundary_study", ondelete="CASCADE"),
        _tenant_fk(BOUNDARY_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{BOUNDARY_TABLE}")),
        sa.UniqueConstraint("team_id", "study_id", name="uq_product_system_boundary_team_study"),
    )
    for column in ("study_id", "boundary_type", "team_id"):
        op.create_index(op.f(f"ix_{BOUNDARY_TABLE}_{column}"), BOUNDARY_TABLE, [column])
    op.create_index("ix_product_system_boundary_type", BOUNDARY_TABLE, ["team_id", "boundary_type"])
    op.alter_column(BOUNDARY_TABLE, "boundary_type", server_default=None)

    op.create_table(
        STAGE_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("study_id", _id_type(), nullable=False),
        sa.Column("stage_code", sa.String(length=64), nullable=False),
        sa.Column("stage_name", sa.String(length=128), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("included", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["study_id"], [f"{STUDY_TABLE}.id"], name="fk_product_lifecycle_stage_study", ondelete="CASCADE"),
        _tenant_fk(STAGE_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{STAGE_TABLE}")),
        sa.UniqueConstraint("team_id", "study_id", "stage_code", name="uq_product_lifecycle_stage_team_code"),
    )
    for column in ("study_id", "stage_code", "included", "team_id"):
        op.create_index(op.f(f"ix_{STAGE_TABLE}_{column}"), STAGE_TABLE, [column])
    op.create_index("ix_product_lifecycle_stage_study", STAGE_TABLE, ["team_id", "study_id", "sequence"])
    op.alter_column(STAGE_TABLE, "sequence", server_default=None)
    op.alter_column(STAGE_TABLE, "included", server_default=None)

    op.create_table(
        ITEM_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("study_id", _id_type(), nullable=False),
        sa.Column("stage_id", _id_type(), nullable=True),
        sa.Column("item_no", sa.String(length=64), nullable=False),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("activity_amount", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("activity_unit", sa.String(length=32), nullable=True),
        sa.Column("factor_id", _id_type(), nullable=True),
        sa.Column("factor_value", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("factor_unit", sa.String(length=64), nullable=True),
        sa.Column("factor_source", sa.String(length=255), nullable=True),
        sa.Column("supplier_pcf_value", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("supplier_pcf_unit", sa.String(length=64), nullable=True),
        sa.Column("supplier_name", sa.String(length=128), nullable=True),
        sa.Column("allocation_ratio", sa.Numeric(precision=10, scale=6), nullable=False, server_default="1"),
        sa.Column("computed_co2e", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("calc_status", sa.String(length=32), nullable=False, server_default="pending_factor"),
        sa.Column("data_quality", sa.String(length=32), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=True),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("evidence_path", sa.String(length=512), nullable=True),
        sa.Column("included", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["study_id"], [f"{STUDY_TABLE}.id"], name="fk_product_footprint_item_study", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_id"], [f"{STAGE_TABLE}.id"], name="fk_product_footprint_item_stage", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["factor_id"], ["dataapp_emissionfactor.id"], name="fk_product_footprint_item_factor", ondelete="SET NULL"),
        _tenant_fk(ITEM_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{ITEM_TABLE}")),
        sa.UniqueConstraint("team_id", "study_id", "item_no", name="uq_product_footprint_item_team_no"),
    )
    for column in ("study_id", "stage_id", "item_no", "activity_type", "factor_id", "calc_status", "data_quality", "source_type", "included", "team_id"):
        op.create_index(op.f(f"ix_{ITEM_TABLE}_{column}"), ITEM_TABLE, [column])
    op.create_index("ix_product_footprint_item_stage", ITEM_TABLE, ["team_id", "study_id", "stage_id"])
    op.create_index("ix_product_footprint_item_status", ITEM_TABLE, ["team_id", "study_id", "calc_status"])
    for column in ("allocation_ratio", "calc_status", "included"):
        op.alter_column(ITEM_TABLE, column, server_default=None)

    op.create_table(
        ALLOCATION_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("study_id", _id_type(), nullable=False),
        sa.Column("process_code", sa.String(length=64), nullable=True),
        sa.Column("process_name", sa.String(length=128), nullable=False),
        sa.Column("allocation_method", sa.String(length=32), nullable=False, server_default="physical"),
        sa.Column("basis", sa.String(length=128), nullable=True),
        sa.Column("ratio", sa.Numeric(precision=10, scale=6), nullable=False, server_default="1"),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["study_id"], [f"{STUDY_TABLE}.id"], name="fk_product_footprint_allocation_study", ondelete="CASCADE"),
        _tenant_fk(ALLOCATION_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{ALLOCATION_TABLE}")),
    )
    for column in ("study_id", "process_code", "allocation_method", "team_id"):
        op.create_index(op.f(f"ix_{ALLOCATION_TABLE}_{column}"), ALLOCATION_TABLE, [column])
    op.create_index("ix_product_footprint_allocation_study", ALLOCATION_TABLE, ["team_id", "study_id"])
    op.create_index("ix_product_footprint_allocation_method", ALLOCATION_TABLE, ["team_id", "allocation_method"])
    op.alter_column(ALLOCATION_TABLE, "allocation_method", server_default=None)
    op.alter_column(ALLOCATION_TABLE, "ratio", server_default=None)

    op.create_table(
        RESULT_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("study_id", _id_type(), nullable=False),
        sa.Column("result_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_co2e", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=32), nullable=False, server_default="kgCO2e"),
        sa.Column("footprint_per_declared_unit", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("result_status", sa.String(length=32), nullable=False, server_default="calculated"),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.Column("inventory_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_factor_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage_payload", sa.JSON(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("report_status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["study_id"], [f"{STUDY_TABLE}.id"], name="fk_product_footprint_result_study", ondelete="CASCADE"),
        _tenant_fk(RESULT_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{RESULT_TABLE}")),
        sa.UniqueConstraint("team_id", "study_id", "result_version", name="uq_product_footprint_result_team_version"),
    )
    for column in ("study_id", "result_status", "report_status", "team_id"):
        op.create_index(op.f(f"ix_{RESULT_TABLE}_{column}"), RESULT_TABLE, [column])
    op.create_index("ix_product_footprint_result_status", RESULT_TABLE, ["team_id", "study_id", "result_status"])
    for column in ("result_version", "total_co2e", "unit", "result_status", "inventory_count", "missing_factor_count", "report_status"):
        op.alter_column(RESULT_TABLE, column, server_default=None)

    for table_name in TABLES:
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        _disable_tenant_rls(table_name)
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
