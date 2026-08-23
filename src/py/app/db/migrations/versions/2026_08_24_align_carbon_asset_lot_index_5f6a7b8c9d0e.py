"""Align the renamed CCER dossier asset-lot index.

Revision ID: 5f6a7b8c9d0e
Revises: 4e5f6a7b8c9d
Create Date: 2026-08-24
"""

from __future__ import annotations

from alembic import op

revision = "5f6a7b8c9d0e"
down_revision = "4e5f6a7b8c9d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "alter index if exists ix_decarbonization_ccer_dossier_carbon_credit_holding_id "
        "rename to ix_decarbonization_ccer_dossier_carbon_asset_lot_id"
    )


def downgrade() -> None:
    op.execute(
        "alter index if exists ix_decarbonization_ccer_dossier_carbon_asset_lot_id "
        "rename to ix_decarbonization_ccer_dossier_carbon_credit_holding_id"
    )
