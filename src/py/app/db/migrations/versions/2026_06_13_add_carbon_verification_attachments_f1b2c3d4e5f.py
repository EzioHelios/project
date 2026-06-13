"""add carbon verification attachments

Revision ID: f1b2c3d4e5f
Revises: f0a1b2c3d4e
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "f1b2c3d4e5f"
down_revision = "f0a1b2c3d4e"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

ATTACHMENT_TABLE = "carbon_verification_attachment"


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
        ATTACHMENT_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("attachment_no", sa.String(length=64), nullable=False),
        sa.Column("material_group", sa.String(length=64), nullable=False, server_default="evidence"),
        sa.Column("attachment_type", sa.String(length=64), nullable=False, server_default="supporting_document"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_object_type", sa.String(length=128), nullable=False),
        sa.Column("source_object_id", sa.Integer(), nullable=True),
        sa.Column("source_object_label", sa.String(length=255), nullable=True),
        sa.Column("source_scope", sa.String(length=16), nullable=True),
        sa.Column("source_period", sa.String(length=16), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending_upload"),
        sa.Column("uploaded_by", sa.String(length=128), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("standard_code", sa.String(length=64), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("ocr_payload", sa.JSON(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk(ATTACHMENT_TABLE),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{ATTACHMENT_TABLE}")),
        sa.UniqueConstraint("team_id", "attachment_no", name="uq_carbon_verification_attachment_team_no"),
    )
    for column in (
        "attachment_no",
        "material_group",
        "attachment_type",
        "source_object_type",
        "source_object_id",
        "source_scope",
        "source_period",
        "sha256",
        "status",
        "team_id",
    ):
        op.create_index(op.f(f"ix_{ATTACHMENT_TABLE}_{column}"), ATTACHMENT_TABLE, [column])
    op.create_index("ix_carbon_verification_attachment_source", ATTACHMENT_TABLE, ["team_id", "source_object_type", "source_object_id"])
    op.create_index("ix_carbon_verification_attachment_status", ATTACHMENT_TABLE, ["team_id", "status", "material_group"])
    op.create_index("ix_carbon_verification_attachment_sha", ATTACHMENT_TABLE, ["team_id", "sha256"])
    for column in ("material_group", "attachment_type", "version_no", "status"):
        op.alter_column(ATTACHMENT_TABLE, column, server_default=None)
    _enable_tenant_rls(ATTACHMENT_TABLE)


def downgrade() -> None:
    _disable_tenant_rls(ATTACHMENT_TABLE)
    op.drop_table(ATTACHMENT_TABLE)
