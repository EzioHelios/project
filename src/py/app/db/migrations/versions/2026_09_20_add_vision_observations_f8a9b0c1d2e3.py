"""Add camera recognition configuration and tenant-scoped observations."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f8a9b0c1d2e3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dataapp_videomonitor", sa.Column("recognition_config", sa.JSON(), nullable=True))
    op.add_column("dataapp_videomonitor", sa.Column("recognition_state", sa.JSON(), nullable=True))
    op.add_column("dataapp_videomonitor", sa.Column("recognition_preview", sa.LargeBinary(), nullable=True))
    op.create_table(
        "vision_observation",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("team.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("camera_id", sa.BigInteger(), sa.ForeignKey("dataapp_videomonitor.id"), nullable=False),
        sa.Column("event_key", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("end_reason", sa.String(32), nullable=False),
        sa.Column("single_subject", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("binding_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_jpeg", sa.LargeBinary(), nullable=True),
        sa.Column(
            "operation_id", sa.BigInteger(), sa.ForeignKey("dataapp_materialhandlingoperation.id", ondelete="SET NULL")
        ),
        sa.UniqueConstraint("team_id", "event_key", name="uq_vision_observation_team_event"),
    )
    op.create_index("ix_vision_observation_team_id", "vision_observation", ["team_id"])
    op.create_index("ix_vision_observation_camera_time", "vision_observation", ["team_id", "camera_id", "started_at"])
    op.execute("ALTER TABLE vision_observation ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE vision_observation FORCE ROW LEVEL SECURITY")
    rule = "current_setting('app.tenant_bypass', true) = 'true' OR team_id::text = nullif(current_setting('app.tenant_id', true), '')"
    op.execute(f"CREATE POLICY vision_tenant_scope ON vision_observation USING ({rule}) WITH CHECK ({rule})")


def downgrade() -> None:
    op.drop_table("vision_observation")
    for column in ("recognition_preview", "recognition_state", "recognition_config"):
        op.drop_column("dataapp_videomonitor", column)
