"""add carbon accounting revision fields

Revision ID: a6b7c8d9e0f
Revises: f4d5e6f7a8b
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a6b7c8d9e0f"
down_revision = "f4d5e6f7a8b"
branch_labels = None
depends_on = None

BATCH_TABLE = "carbon_accounting_batch"


def _id_type() -> sa.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.add_column(BATCH_TABLE, sa.Column("parent_batch_id", _id_type(), nullable=True))
    op.add_column(BATCH_TABLE, sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(BATCH_TABLE, sa.Column("revision_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_carbon_accounting_batch_parent",
        BATCH_TABLE,
        BATCH_TABLE,
        ["parent_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f(f"ix_{BATCH_TABLE}_parent_batch_id"), BATCH_TABLE, ["parent_batch_id"])
    op.create_index("ix_carbon_accounting_batch_revision", BATCH_TABLE, ["team_id", "parent_batch_id", "revision_no"])
    op.alter_column(BATCH_TABLE, "revision_no", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_carbon_accounting_batch_revision", table_name=BATCH_TABLE)
    op.drop_index(op.f(f"ix_{BATCH_TABLE}_parent_batch_id"), table_name=BATCH_TABLE)
    op.drop_constraint("fk_carbon_accounting_batch_parent", BATCH_TABLE, type_="foreignkey")
    op.drop_column(BATCH_TABLE, "revision_reason")
    op.drop_column(BATCH_TABLE, "revision_no")
    op.drop_column(BATCH_TABLE, "parent_batch_id")
