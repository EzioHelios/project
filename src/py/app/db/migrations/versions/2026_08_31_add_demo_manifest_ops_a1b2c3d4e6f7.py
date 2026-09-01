"""Add demo manifest registry for reusable demo packages.

Revision ID: a1b2c3d4e6f7
Revises: 9d0e1f2a3b4c
Create Date: 2026-08-31
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

revision = "a1b2c3d4e6f7"
down_revision = "9d0e1f2a3b4c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the reusable demo package manifest table."""
    op.create_table(
        "demo_manifest",
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column("profile", sa.String(length=64), nullable=False),
        sa.Column("package_key", sa.String(length=96), nullable=False),
        sa.Column("module_key", sa.String(length=96), nullable=False),
        sa.Column("object_type", sa.String(length=96), nullable=False),
        sa.Column("object_key", sa.String(length=160), nullable=False),
        sa.Column("object_id", sa.String(length=160), nullable=True),
        sa.Column("team_id", sa.GUID(length=16), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTimeUTC(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTimeUTC(timezone=True), nullable=False),
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], name="fk_demo_manifest_team_id_team", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_demo_manifest")),
        sa.UniqueConstraint("namespace", "object_type", "object_key", name="uq_demo_manifest_namespace_object"),
    )
    op.create_index("ix_demo_manifest_namespace", "demo_manifest", ["namespace"])
    op.create_index("ix_demo_manifest_package_key", "demo_manifest", ["package_key"])
    op.create_index("ix_demo_manifest_module_key", "demo_manifest", ["module_key"])
    op.create_index("ix_demo_manifest_object_type", "demo_manifest", ["object_type"])
    op.create_index("ix_demo_manifest_object_key", "demo_manifest", ["object_key"])
    op.create_index("ix_demo_manifest_profile", "demo_manifest", ["profile"])
    op.create_index("ix_demo_manifest_team_id", "demo_manifest", ["team_id"])
    op.create_index(
        "ix_demo_manifest_package_namespace",
        "demo_manifest",
        ["package_key", "namespace", "profile"],
    )
    op.create_index("ix_demo_manifest_team", "demo_manifest", ["team_id", "package_key", "module_key"])


def downgrade() -> None:
    """Drop the reusable demo package manifest table."""
    op.drop_index("ix_demo_manifest_team", table_name="demo_manifest")
    op.drop_index("ix_demo_manifest_package_namespace", table_name="demo_manifest")
    op.drop_index("ix_demo_manifest_team_id", table_name="demo_manifest")
    op.drop_index("ix_demo_manifest_profile", table_name="demo_manifest")
    op.drop_index("ix_demo_manifest_object_key", table_name="demo_manifest")
    op.drop_index("ix_demo_manifest_object_type", table_name="demo_manifest")
    op.drop_index("ix_demo_manifest_module_key", table_name="demo_manifest")
    op.drop_index("ix_demo_manifest_package_key", table_name="demo_manifest")
    op.drop_index("ix_demo_manifest_namespace", table_name="demo_manifest")
    op.drop_table("demo_manifest")
