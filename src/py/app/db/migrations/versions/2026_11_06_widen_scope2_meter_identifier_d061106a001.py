"""Widen Scope 2 aggregate meter identifiers to match equipment codes."""

import sqlalchemy as sa
from alembic import op

revision = "d061106a001"
down_revision = "c0261026a001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allow canonical equipment codes in the aggregate business key."""
    op.alter_column(
        "dataapp_scope2meteraggregate",
        "ammeter_id",
        existing_type=sa.String(length=20),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Restore the legacy width when all identifiers still fit."""
    op.alter_column(
        "dataapp_scope2meteraggregate",
        "ammeter_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
