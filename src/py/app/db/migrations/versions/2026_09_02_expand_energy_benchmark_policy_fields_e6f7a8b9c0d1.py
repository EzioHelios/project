"""Expand energy benchmark policy library fields.

Revision ID: e6f7a8b9c0d1
Revises: c3d4e5f6a7b8
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add policy source, applicability, and level fields to benchmark tables."""
    op.add_column(
        "dataapp_energybenchmarkprofile",
        sa.Column("library_type", sa.String(length=32), nullable=True, server_default="enterprise_internal"),
    )
    op.add_column("dataapp_energybenchmarkprofile", sa.Column("source_url", sa.String(length=512), nullable=True))
    op.add_column("dataapp_energybenchmarkprofile", sa.Column("source_hash", sa.String(length=64), nullable=True))
    op.add_column("dataapp_energybenchmarkprofile", sa.Column("source_file_name", sa.String(length=255), nullable=True))
    op.add_column("dataapp_energybenchmarkprofile", sa.Column("standard_code", sa.String(length=128), nullable=True))
    op.add_column(
        "dataapp_energybenchmarkprofile",
        sa.Column("version_status", sa.String(length=32), nullable=True, server_default="active"),
    )
    op.create_index(op.f("ix_dataapp_energybenchmarkprofile_library_type"), "dataapp_energybenchmarkprofile", ["library_type"])
    op.create_index(op.f("ix_dataapp_energybenchmarkprofile_standard_code"), "dataapp_energybenchmarkprofile", ["standard_code"])
    op.create_index(op.f("ix_dataapp_energybenchmarkprofile_version_status"), "dataapp_energybenchmarkprofile", ["version_status"])
    op.alter_column("dataapp_energybenchmarkprofile", "library_type", server_default=None)
    op.alter_column("dataapp_energybenchmarkprofile", "version_status", server_default=None)

    op.add_column("dataapp_energybenchmarkitem", sa.Column("standard_code", sa.String(length=128), nullable=True))
    op.add_column("dataapp_energybenchmarkitem", sa.Column("source_url", sa.String(length=512), nullable=True))
    op.add_column("dataapp_energybenchmarkitem", sa.Column("source_hash", sa.String(length=64), nullable=True))
    op.add_column("dataapp_energybenchmarkitem", sa.Column("applicable_industry", sa.String(length=128), nullable=True))
    op.add_column("dataapp_energybenchmarkitem", sa.Column("applicable_category", sa.String(length=128), nullable=True))
    op.add_column("dataapp_energybenchmarkitem", sa.Column("applicable_condition", sa.Text(), nullable=True))
    op.add_column(
        "dataapp_energybenchmarkitem",
        sa.Column("metric_direction", sa.String(length=32), nullable=True, server_default="lower_is_better"),
    )
    op.add_column("dataapp_energybenchmarkitem", sa.Column("advanced_value", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("dataapp_energybenchmarkitem", sa.Column("saving_value", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("dataapp_energybenchmarkitem", sa.Column("access_value", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("dataapp_energybenchmarkitem", sa.Column("baseline_value", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("dataapp_energybenchmarkitem", sa.Column("advanced_level", sa.String(length=64), nullable=True))
    op.add_column("dataapp_energybenchmarkitem", sa.Column("saving_level", sa.String(length=64), nullable=True))
    op.add_column("dataapp_energybenchmarkitem", sa.Column("access_level", sa.String(length=64), nullable=True))
    op.add_column("dataapp_energybenchmarkitem", sa.Column("standard_level", sa.String(length=32), nullable=True))
    op.add_column(
        "dataapp_energybenchmarkitem",
        sa.Column("version_status", sa.String(length=32), nullable=True, server_default="active"),
    )
    op.add_column("dataapp_energybenchmarkitem", sa.Column("reference_standard", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_dataapp_energybenchmarkitem_standard_code"), "dataapp_energybenchmarkitem", ["standard_code"])
    op.create_index(op.f("ix_dataapp_energybenchmarkitem_applicable_industry"), "dataapp_energybenchmarkitem", ["applicable_industry"])
    op.create_index(op.f("ix_dataapp_energybenchmarkitem_applicable_category"), "dataapp_energybenchmarkitem", ["applicable_category"])
    op.create_index(op.f("ix_dataapp_energybenchmarkitem_standard_level"), "dataapp_energybenchmarkitem", ["standard_level"])
    op.create_index(op.f("ix_dataapp_energybenchmarkitem_version_status"), "dataapp_energybenchmarkitem", ["version_status"])
    op.alter_column("dataapp_energybenchmarkitem", "metric_direction", server_default=None)
    op.alter_column("dataapp_energybenchmarkitem", "version_status", server_default=None)


def downgrade() -> None:
    """Remove policy source and level fields from benchmark tables."""
    op.drop_index(op.f("ix_dataapp_energybenchmarkitem_version_status"), table_name="dataapp_energybenchmarkitem")
    op.drop_index(op.f("ix_dataapp_energybenchmarkitem_standard_level"), table_name="dataapp_energybenchmarkitem")
    op.drop_index(op.f("ix_dataapp_energybenchmarkitem_applicable_category"), table_name="dataapp_energybenchmarkitem")
    op.drop_index(op.f("ix_dataapp_energybenchmarkitem_applicable_industry"), table_name="dataapp_energybenchmarkitem")
    op.drop_index(op.f("ix_dataapp_energybenchmarkitem_standard_code"), table_name="dataapp_energybenchmarkitem")
    for column in (
        "reference_standard",
        "version_status",
        "standard_level",
        "access_level",
        "saving_level",
        "advanced_level",
        "baseline_value",
        "access_value",
        "saving_value",
        "advanced_value",
        "metric_direction",
        "applicable_condition",
        "applicable_category",
        "applicable_industry",
        "source_hash",
        "source_url",
        "standard_code",
    ):
        op.drop_column("dataapp_energybenchmarkitem", column)

    op.drop_index(op.f("ix_dataapp_energybenchmarkprofile_version_status"), table_name="dataapp_energybenchmarkprofile")
    op.drop_index(op.f("ix_dataapp_energybenchmarkprofile_standard_code"), table_name="dataapp_energybenchmarkprofile")
    op.drop_index(op.f("ix_dataapp_energybenchmarkprofile_library_type"), table_name="dataapp_energybenchmarkprofile")
    for column in ("version_status", "standard_code", "source_file_name", "source_hash", "source_url", "library_type"):
        op.drop_column("dataapp_energybenchmarkprofile", column)
