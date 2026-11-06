"""Enforce current-only derived statistics after explicit, audited cleanup."""

# SQL identifiers below are fixed constants.
# ruff: noqa: S608

import sqlalchemy as sa
from alembic import op

revision = "c0261026a001"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None

TABLES = (
    (
        "dataapp_energyintervalfact",
        ["team_id", "source_system", "source_record_id"],
        "uq_energy_interval_team_source_record",
        "ck_energy_interval_current_only",
    ),
    (
        "dataapp_scope2meteraggregate",
        ["team_id", "ammeter_id", "billing_month"],
        "uq_scope2_meter_aggregate_team_meter_month",
        "ck_scope2_meter_current_only",
    ),
    (
        "metering_scope2_electricity_reconciliation",
        ["team_id", "billing_month"],
        "uq_scope2_reconciliation_team_month",
        "ck_scope2_reconciliation_current_only",
    ),
)


def upgrade() -> None:
    """Never silently delete operational records inside a schema migration."""
    bind = op.get_bind()
    bind.execute(sa.text("SET LOCAL lock_timeout = '2s'"))
    bind.execute(sa.text("SET LOCAL statement_timeout = '120s'"))
    for table, keys, _unique, _check in TABLES:
        if bind.scalar(
            sa.text(
                f"SELECT EXISTS (SELECT 1 FROM {table} WHERE NOT is_current OR revision_no < 1 OR supersedes_id IS NOT NULL)"
            )
        ):
            msg = f"{table}: run audited projection cleanup before this migration"
            raise RuntimeError(msg)
        columns = ", ".join(keys)
        if bind.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table} GROUP BY {columns} HAVING count(*) > 1)")):
            msg = f"{table}: duplicate business keys must be resolved before migration"
            raise RuntimeError(msg)
    for table, keys, unique, check in TABLES:
        op.create_unique_constraint(unique, table, keys)
        op.create_check_constraint(check, table, "is_current AND revision_no >= 1 AND supersedes_id IS NULL")


def downgrade() -> None:
    """Remove enforcement only; deleted data cannot be reconstructed by downgrade."""
    for table, _keys, unique, check in reversed(TABLES):
        op.drop_constraint(check, table, type_="check")
        op.drop_constraint(unique, table, type_="unique")
