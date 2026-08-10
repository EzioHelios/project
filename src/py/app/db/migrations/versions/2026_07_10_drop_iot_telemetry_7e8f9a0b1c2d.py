"""retain deprecated IoT telemetry table during the compatibility window

Revision ID: 7e8f9a0b1c2d
Revises: 6d7e8f9a0b1c
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "7e8f9a0b1c2d"
down_revision = "6d7e8f9a0b1c"
branch_labels = None
depends_on = None

TABLE_NAME = "dataapp_iottelemetry"


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _enable_tenant_rls() -> None:
    if not _is_postgresql():
        return
    op.execute(sa.text(f"alter table {TABLE_NAME} enable row level security"))
    op.execute(sa.text(f"alter table {TABLE_NAME} force row level security"))
    op.execute(sa.text(f"drop policy if exists rls_{TABLE_NAME}_tenant_scope on {TABLE_NAME}"))
    op.execute(
        sa.text(
            f"""
            create policy rls_{TABLE_NAME}_tenant_scope on {TABLE_NAME}
            using (
                current_setting('app.tenant_bypass', true) = 'true'
                or team_id::text = nullif(current_setting('app.tenant_id', true), '')
            )
            with check (
                current_setting('app.tenant_bypass', true) = 'true'
                or team_id::text = nullif(current_setting('app.tenant_id', true), '')
            )
            """
        )
    )


def upgrade() -> None:
    if TABLE_NAME not in sa.inspect(op.get_bind()).get_table_names():
        msg = f"Expected compatibility table {TABLE_NAME} is missing; restore it before continuing."
        raise RuntimeError(msg)
    _enable_tenant_rls()


def downgrade() -> None:
    # This revision deliberately makes no physical schema change.
    return
