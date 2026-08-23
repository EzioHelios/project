"""add organization GHG analytics query indexes

Revision ID: e4f5a6b7c8d
Revises: d3e4f5a6b7c
Create Date: 2026-08-23
"""

from __future__ import annotations

from alembic import op

revision = "e4f5a6b7c8d"
down_revision = "d3e4f5a6b7c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_ghg_result_run_scope_method_quality",
        "ghg_calculation_result",
        ["team_id", "run_id", "ghg_scope", "scope2_method", "quality_status"],
    )
    op.create_index(
        "ix_ghg_activity_period_mechanism",
        "ghg_activity_record",
        ["team_id", "period_start", "period_end", "source_mechanism"],
    )
    op.create_index(
        "ix_ghg_allocation_resource_activity",
        "ghg_activity_allocation",
        ["team_id", "area_id", "equipment_id", "activity_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_ghg_allocation_resource_activity", table_name="ghg_activity_allocation")
    op.drop_index("ix_ghg_activity_period_mechanism", table_name="ghg_activity_record")
    op.drop_index("ix_ghg_result_run_scope_method_quality", table_name="ghg_calculation_result")
