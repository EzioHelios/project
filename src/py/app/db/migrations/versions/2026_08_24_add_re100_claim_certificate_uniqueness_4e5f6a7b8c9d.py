"""Prevent duplicate RE100 certificate allocation within one reporting year.

Revision ID: 4e5f6a7b8c9d
Revises: 3d4e5f6a7b8c
Create Date: 2026-08-24
"""

from __future__ import annotations

from alembic import op

revision = "4e5f6a7b8c9d"
down_revision = "3d4e5f6a7b8c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_climate_claim_certificate_year",
        "climate_governance_renewable_claim",
        ["team_id", "reporting_year", "certificate_no"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_climate_claim_certificate_year",
        "climate_governance_renewable_claim",
        type_="unique",
    )
