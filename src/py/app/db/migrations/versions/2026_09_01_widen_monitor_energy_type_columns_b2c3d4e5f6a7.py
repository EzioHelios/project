"""Widen monitor energy type columns for standard energy codes.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e6f7
Create Date: 2026-09-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allow device energy fields to store standard energy type codes."""
    op.alter_column(
        "dataapp_devicetype",
        "energy_type",
        existing_type=sa.String(length=20),
        type_=sa.String(length=32),
        existing_nullable=True,
    )
    op.alter_column(
        "dataapp_monitorequipment",
        "energy_type",
        existing_type=sa.String(length=20),
        type_=sa.String(length=32),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Restore previous device energy field lengths."""
    op.alter_column(
        "dataapp_monitorequipment",
        "energy_type",
        existing_type=sa.String(length=32),
        type_=sa.String(length=20),
        existing_nullable=True,
    )
    op.alter_column(
        "dataapp_devicetype",
        "energy_type",
        existing_type=sa.String(length=32),
        type_=sa.String(length=20),
        existing_nullable=True,
    )
