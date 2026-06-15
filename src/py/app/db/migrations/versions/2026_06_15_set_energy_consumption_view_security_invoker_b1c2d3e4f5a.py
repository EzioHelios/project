"""set energy consumption view to security invoker

Revision ID: b1c2d3e4f5a
Revises: a6b7c8d9e0f
Create Date: 2026-06-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b1c2d3e4f5a"
down_revision = "a6b7c8d9e0f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("alter view if exists energy_consumption_fact_v set (security_invoker = true)"))


def downgrade() -> None:
    op.execute(sa.text("alter view if exists energy_consumption_fact_v set (security_invoker = false)"))
