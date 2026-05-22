"""drop code2 from monitor equipment

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
Create Date: 2026-05-22
"""

import sqlalchemy as sa
from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            update dataapp_monitorequipment
            set asset_code = coalesce(nullif(asset_code, ''), nullif(code2, ''))
            where coalesce(nullif(code2, ''), '') <> ''
            """
        )
    )
    op.drop_column("dataapp_monitorequipment", "code2")


def downgrade() -> None:
    op.add_column("dataapp_monitorequipment", sa.Column("code2", sa.String(length=30), nullable=True))
    op.execute(
        sa.text(
            """
            update dataapp_monitorequipment
            set code2 = coalesce(nullif(code2, ''), nullif(asset_code, ''))
            where coalesce(nullif(asset_code, ''), '') <> ''
            """
        )
    )
