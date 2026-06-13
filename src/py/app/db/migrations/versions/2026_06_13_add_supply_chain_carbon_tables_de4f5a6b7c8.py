"""add supply chain carbon tables

Revision ID: de4f5a6b7c8
Revises: cd3e4f5a6b7
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "de4f5a6b7c8"
down_revision = "cd3e4f5a6b7"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

SUPPLIER_TABLE = "carbon_supply_chain_supplier"
SITE_TABLE = "carbon_supplier_site"
TASK_TABLE = "carbon_supplier_disclosure_task"
DATA_TABLE = "carbon_supplier_carbon_data"
EVIDENCE_TABLE = "carbon_supplier_evidence"
DECISION_TABLE = "carbon_supplier_review_decision"
RELEASE_TABLE = "carbon_supplier_disclosure_release"
TABLES = (SUPPLIER_TABLE, SITE_TABLE, TASK_TABLE, DATA_TABLE, EVIDENCE_TABLE, DECISION_TABLE, RELEASE_TABLE)


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
        SUPPLIER_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("supplier_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("supplier_type", sa.String(length=32), nullable=True),
        sa.Column("contact_name", sa.String(length=64), nullable=True),
        sa.Column("contact_email", sa.String(length=128), nullable=True),
        sa.Column("country_region", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk(SUPPLIER_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{SUPPLIER_TABLE}")),
        sa.UniqueConstraint("team_id", "supplier_code", name="uq_supply_chain_supplier_team_code"),
    )
    for column in ("supplier_code", "industry", "supplier_type", "status", "risk_level", "team_id"):
        op.create_index(op.f(f"ix_{SUPPLIER_TABLE}_{column}"), SUPPLIER_TABLE, [column])
    op.create_index("ix_supply_chain_supplier_status", SUPPLIER_TABLE, ["team_id", "status", "risk_level"])
    op.create_index("ix_supply_chain_supplier_industry", SUPPLIER_TABLE, ["team_id", "industry"])
    for column in ("status", "risk_level"):
        op.alter_column(SUPPLIER_TABLE, column, server_default=None)

    op.create_table(
        SITE_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("supplier_id", _id_type(), nullable=False),
        sa.Column("site_code", sa.String(length=64), nullable=False),
        sa.Column("site_name", sa.String(length=128), nullable=False),
        sa.Column("country_region", sa.String(length=128), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("facility_scope", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["supplier_id"], [f"{SUPPLIER_TABLE}.id"], name="fk_supplier_site_supplier", ondelete="CASCADE"),
        _tenant_fk(SITE_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{SITE_TABLE}")),
        sa.UniqueConstraint("team_id", "supplier_id", "site_code", name="uq_supplier_site_team_code"),
    )
    for column in ("supplier_id", "site_code", "status", "team_id"):
        op.create_index(op.f(f"ix_{SITE_TABLE}_{column}"), SITE_TABLE, [column])
    op.create_index("ix_supplier_site_supplier_status", SITE_TABLE, ["team_id", "supplier_id", "status"])
    op.alter_column(SITE_TABLE, "status", server_default=None)

    op.create_table(
        TASK_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("task_no", sa.String(length=64), nullable=False),
        sa.Column("task_name", sa.String(length=128), nullable=False),
        sa.Column("supplier_id", _id_type(), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False, server_default="mixed"),
        sa.Column("product_id", _id_type(), nullable=True),
        sa.Column("product_code", sa.String(length=64), nullable=True),
        sa.Column("product_name", sa.String(length=128), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("requested_by", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["supplier_id"], [f"{SUPPLIER_TABLE}.id"], name="fk_supplier_disclosure_task_supplier", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["dataapp_productionproduct.id"], name="fk_supplier_disclosure_task_product", ondelete="SET NULL"),
        _tenant_fk(TASK_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{TASK_TABLE}")),
        sa.UniqueConstraint("team_id", "task_no", name="uq_supplier_disclosure_task_team_no"),
    )
    for column in ("task_no", "supplier_id", "task_type", "product_id", "product_code", "period_start", "period_end", "due_date", "status", "team_id"):
        op.create_index(op.f(f"ix_{TASK_TABLE}_{column}"), TASK_TABLE, [column])
    op.create_index("ix_supplier_disclosure_task_supplier_status", TASK_TABLE, ["team_id", "supplier_id", "status"])
    op.create_index("ix_supplier_disclosure_task_period", TASK_TABLE, ["team_id", "period_start", "period_end"])
    for column in ("task_type", "status"):
        op.alter_column(TASK_TABLE, column, server_default=None)

    op.create_table(
        DATA_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("task_id", _id_type(), nullable=False),
        sa.Column("supplier_id", _id_type(), nullable=False),
        sa.Column("data_no", sa.String(length=64), nullable=False),
        sa.Column("data_type", sa.String(length=32), nullable=False, server_default="activity"),
        sa.Column("scope_category", sa.String(length=64), nullable=True),
        sa.Column("product_id", _id_type(), nullable=True),
        sa.Column("product_code", sa.String(length=64), nullable=True),
        sa.Column("product_name", sa.String(length=128), nullable=True),
        sa.Column("material_code", sa.String(length=64), nullable=True),
        sa.Column("material_name", sa.String(length=128), nullable=True),
        sa.Column("activity_amount", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("activity_unit", sa.String(length=32), nullable=True),
        sa.Column("pcf_value", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("pcf_unit", sa.String(length=64), nullable=True),
        sa.Column("co2e_amount", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("factor_source", sa.String(length=255), nullable=True),
        sa.Column("boundary_type", sa.String(length=32), nullable=True),
        sa.Column("data_quality", sa.String(length=32), nullable=False, server_default="supplier_reported"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("validity_start", sa.Date(), nullable=True),
        sa.Column("validity_end", sa.Date(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=True),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("published_to_scope3", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("published_to_pcf", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["task_id"], [f"{TASK_TABLE}.id"], name="fk_supplier_carbon_data_task", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], [f"{SUPPLIER_TABLE}.id"], name="fk_supplier_carbon_data_supplier", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["dataapp_productionproduct.id"], name="fk_supplier_carbon_data_product", ondelete="SET NULL"),
        _tenant_fk(DATA_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{DATA_TABLE}")),
        sa.UniqueConstraint("team_id", "task_id", "data_no", name="uq_supplier_carbon_data_team_no"),
    )
    for column in (
        "task_id",
        "supplier_id",
        "data_no",
        "data_type",
        "scope_category",
        "product_id",
        "product_code",
        "material_code",
        "boundary_type",
        "data_quality",
        "verified",
        "status",
        "published_to_scope3",
        "published_to_pcf",
        "team_id",
    ):
        op.create_index(op.f(f"ix_{DATA_TABLE}_{column}"), DATA_TABLE, [column])
    op.create_index("ix_supplier_carbon_data_supplier_type", DATA_TABLE, ["team_id", "supplier_id", "data_type"])
    op.create_index("ix_supplier_carbon_data_status", DATA_TABLE, ["team_id", "task_id", "status"])
    for column in ("data_type", "data_quality", "verified", "status", "published_to_scope3", "published_to_pcf"):
        op.alter_column(DATA_TABLE, column, server_default=None)

    op.create_table(
        EVIDENCE_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("task_id", _id_type(), nullable=False),
        sa.Column("evidence_no", sa.String(length=64), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("review_status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("submitted_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["task_id"], [f"{TASK_TABLE}.id"], name="fk_supplier_evidence_task", ondelete="CASCADE"),
        _tenant_fk(EVIDENCE_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{EVIDENCE_TABLE}")),
        sa.UniqueConstraint("team_id", "task_id", "evidence_no", name="uq_supplier_evidence_team_no"),
    )
    for column in ("task_id", "evidence_no", "evidence_type", "review_status", "team_id"):
        op.create_index(op.f(f"ix_{EVIDENCE_TABLE}_{column}"), EVIDENCE_TABLE, [column])
    op.create_index("ix_supplier_evidence_task_status", EVIDENCE_TABLE, ["team_id", "task_id", "review_status"])
    op.alter_column(EVIDENCE_TABLE, "review_status", server_default=None)

    op.create_table(
        DECISION_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("task_id", _id_type(), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["task_id"], [f"{TASK_TABLE}.id"], name="fk_supplier_review_decision_task", ondelete="CASCADE"),
        _tenant_fk(DECISION_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{DECISION_TABLE}")),
    )
    for column in ("task_id", "decision", "team_id"):
        op.create_index(op.f(f"ix_{DECISION_TABLE}_{column}"), DECISION_TABLE, [column])
    op.create_index("ix_supplier_review_decision_task", DECISION_TABLE, ["team_id", "task_id", "decision"])

    op.create_table(
        RELEASE_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("release_no", sa.String(length=64), nullable=False),
        sa.Column("task_id", _id_type(), nullable=False),
        sa.Column("release_type", sa.String(length=32), nullable=False, server_default="customer_disclosure"),
        sa.Column("recipient_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["task_id"], [f"{TASK_TABLE}.id"], name="fk_supplier_disclosure_release_task", ondelete="CASCADE"),
        _tenant_fk(RELEASE_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{RELEASE_TABLE}")),
        sa.UniqueConstraint("team_id", "release_no", name="uq_supplier_disclosure_release_team_no"),
    )
    for column in ("release_no", "task_id", "release_type", "status", "team_id"):
        op.create_index(op.f(f"ix_{RELEASE_TABLE}_{column}"), RELEASE_TABLE, [column])
    op.create_index("ix_supplier_disclosure_release_task", RELEASE_TABLE, ["team_id", "task_id", "status"])
    for column in ("release_type", "status"):
        op.alter_column(RELEASE_TABLE, column, server_default=None)

    for table_name in TABLES:
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        _disable_tenant_rls(table_name)
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
