"""add metering governance, projection revisions, and source classification

Revision ID: 9a0b1c2d3e4f
Revises: 8f9a0b1c2d3e
Create Date: 2026-08-09
"""

from __future__ import annotations

# ruff: noqa: S608
import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "9a0b1c2d3e4f"
down_revision = "8f9a0b1c2d3e"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]

BOUNDARY_TABLE = "metering_measurement_boundary"
BOUNDARY_MEMBER_TABLE = "metering_measurement_boundary_member"
CURSOR_TABLE = "metering_acquisition_cursor"
MIGRATION_RUN_TABLE = "metering_data_migration_run"
PROJECTION_RUN_TABLE = "metering_energy_projection_run"
QUALITY_ISSUE_TABLE = "metering_quality_issue"
RECONCILIATION_TABLE = "metering_scope2_electricity_reconciliation"
ENERGY_FACT_TABLE = "dataapp_energyintervalfact"
SCOPE2_AGGREGATE_TABLE = "dataapp_scope2meteraggregate"
CARBON_ACTIVITY_TABLES = (
    "dataapp_scope1mobilecombustion",
    "dataapp_scope1stationarycombustion",
    "dataapp_scope1refrigerantleak",
    "dataapp_scope2electricitybill",
    "dataapp_scope2purchasedenergy",
    "dataapp_scope3wastedisposal",
    "dataapp_scope3thirdpartytransport",
)
CARBON_SOURCE_CONSTRAINTS = {
    "dataapp_scope1mobilecombustion": "uq_scope1_mobile_source_version",
    "dataapp_scope1stationarycombustion": "uq_scope1_stationary_source_version",
    "dataapp_scope1refrigerantleak": "uq_scope1_refrigerant_source_version",
    "dataapp_scope2electricitybill": "uq_scope2_bill_source_version",
    "dataapp_scope2purchasedenergy": "uq_scope2_purchased_source_version",
    "dataapp_scope3wastedisposal": "uq_scope3_waste_source_version",
    "dataapp_scope3thirdpartytransport": "uq_scope3_transport_source_version",
}
TENANT_TABLES = (
    BOUNDARY_TABLE,
    BOUNDARY_MEMBER_TABLE,
    CURSOR_TABLE,
    MIGRATION_RUN_TABLE,
    PROJECTION_RUN_TABLE,
    QUALITY_ISSUE_TABLE,
    RECONCILIATION_TABLE,
)


def _id_type() -> sa.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("team_id", sa.GUID(length=16), nullable=False),
        sa.Column("created_at", sa.DateTimeUTC(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTimeUTC(timezone=True), nullable=False),
    ]


def _tenant_fk(table_name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(["team_id"], ["team.id"], name=f"fk_{table_name}_team_id_team", ondelete="CASCADE")


def _enable_tenant_rls(table_name: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    policy_name = f"rls_{table_name}_tenant_scope"
    op.execute(sa.text(f"alter table {table_name} enable row level security"))
    op.execute(sa.text(f"alter table {table_name} force row level security"))
    op.execute(sa.text(f"drop policy if exists {policy_name} on {table_name}"))
    op.execute(
        sa.text(
            f"""
            create policy {policy_name} on {table_name}
            using (
                current_setting('app.tenant_bypass', true) = 'true'
                or team_id::text = nullif(current_setting('app.tenant_id', true), '')
            )
            with check (
                current_setting('app.tenant_bypass', true) = 'true'
                or team_id::text = nullif(current_setting('app.tenant_id', true), '')
            );
            """
        )
    )


def _replace_energy_consumption_view() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(sa.text("alter view energy_consumption_fact_v rename to energy_consumption_fact_all_v"))
    op.execute(sa.text("alter view energy_consumption_fact_all_v set (security_invoker = true)"))
    op.execute(
        sa.text(
            """
            create view energy_consumption_fact_v with (security_invoker = true) as
            select source.*
            from energy_consumption_fact_all_v source
            where
                case source.source_record_type
                    when 'Scope1MobileCombustion' then exists (
                        select 1
                        from dataapp_scope1mobilecombustion record
                        where record.id = source.source_record_id
                          and record.team_id = source.team_id
                          and coalesce(record.record_usage, 'operational') <> 'reference'
                    )
                    when 'Scope1StationaryCombustion' then exists (
                        select 1
                        from dataapp_scope1stationarycombustion record
                        where record.id = source.source_record_id
                          and record.team_id = source.team_id
                          and coalesce(record.record_usage, 'operational') <> 'reference'
                    )
                    when 'Scope2ElectricityBill' then exists (
                        select 1
                        from dataapp_scope2electricitybill record
                        join metering_scope2_electricity_reconciliation reconciliation
                          on reconciliation.team_id = record.team_id
                         and reconciliation.billing_month = record.billing_month
                         and reconciliation.is_current = true
                         and reconciliation.source_priority = 'electricity_bill'
                        where record.id = source.source_record_id
                          and record.team_id = source.team_id
                          and record.status = 'approved'
                          and coalesce(record.record_usage, 'operational') <> 'reference'
                    )
                    when 'Scope2MeterAggregate' then exists (
                        select 1
                        from dataapp_scope2meteraggregate record
                        join metering_scope2_electricity_reconciliation reconciliation
                          on reconciliation.team_id = record.team_id
                         and reconciliation.billing_month = record.billing_month
                         and reconciliation.is_current = true
                         and reconciliation.source_priority = 'meter_aggregate'
                        where record.id = source.source_record_id
                          and record.team_id = source.team_id
                          and record.is_current = true
                          and record.calc_status in ('ready', 'missing_factor')
                    )
                    when 'Scope2PurchasedEnergy' then exists (
                        select 1
                        from dataapp_scope2purchasedenergy record
                        where record.id = source.source_record_id
                          and record.team_id = source.team_id
                          and record.energy_type_code <> 'purchased_electricity'
                          and coalesce(record.record_usage, 'operational') <> 'reference'
                    )
                    else false
                end
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        BOUNDARY_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("boundary_type", sa.String(length=32), nullable=False, server_default="meter_circuit"),
        sa.Column("meter_equipment_id", _id_type(), nullable=True),
        sa.Column("sector_id", _id_type(), nullable=True),
        sa.Column("use_system_code", sa.String(length=64), nullable=True),
        sa.Column("energy_direction", sa.String(length=16), nullable=False, server_default="import"),
        sa.Column("include_in_scope2", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("mapping_version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk(BOUNDARY_TABLE),
        sa.ForeignKeyConstraint(
            ["meter_equipment_id"],
            ["dataapp_monitorequipment.id"],
            name=op.f("fk_metering_measurement_boundary_meter_equipment_id_dataapp_monitorequipment"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sector_id"],
            ["dataapp_monitorsector.id"],
            name=op.f("fk_metering_measurement_boundary_sector_id_dataapp_monitorsector"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "code", name="uq_metering_boundary_team_code"),
    )
    for column in (
        "boundary_type",
        "code",
        "include_in_scope2",
        "meter_equipment_id",
        "sector_id",
        "status",
        "team_id",
        "use_system_code",
    ):
        op.create_index(op.f(f"ix_{BOUNDARY_TABLE}_{column}"), BOUNDARY_TABLE, [column])
    op.create_index(
        "ix_metering_boundary_scope2_active", BOUNDARY_TABLE, ["team_id", "include_in_scope2", "status", "valid_from"]
    )

    op.create_table(
        CURSOR_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("equipment_id", _id_type(), nullable=False),
        sa.Column("last_attempt_time", sa.DateTime(), nullable=True),
        sa.Column("last_success_time", sa.DateTime(), nullable=True),
        sa.Column("source_watermark", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="ready"),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("cursor_metadata", sa.JSON(), nullable=True),
        *_audit_columns(),
        _tenant_fk(CURSOR_TABLE),
        sa.ForeignKeyConstraint(
            ["equipment_id"],
            ["dataapp_monitorequipment.id"],
            name=op.f("fk_metering_acquisition_cursor_equipment_id_dataapp_monitorequipment"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "source_system", "equipment_id", name="uq_metering_cursor_source_equipment"),
    )
    for column in ("equipment_id", "source_system", "status", "team_id"):
        op.create_index(op.f(f"ix_{CURSOR_TABLE}_{column}"), CURSOR_TABLE, [column])
    op.create_index("ix_metering_cursor_status", CURSOR_TABLE, ["team_id", "source_system", "status"])

    op.create_table(
        MIGRATION_RUN_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("run_code", sa.String(length=96), nullable=False),
        sa.Column("migration_type", sa.String(length=48), nullable=False),
        sa.Column("source_table", sa.String(length=96), nullable=False),
        sa.Column("target_table", sa.String(length=96), nullable=False),
        sa.Column("from_time", sa.DateTime(), nullable=True),
        sa.Column("to_time", sa.DateTime(), nullable=True),
        sa.Column("source_high_watermark", sa.String(length=160), nullable=True),
        sa.Column("last_source_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("source_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_checksum", sa.String(length=64), nullable=True),
        sa.Column("target_checksum", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("run_config", sa.JSON(), nullable=True),
        *_audit_columns(),
        _tenant_fk(MIGRATION_RUN_TABLE),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "run_code", name="uq_metering_migration_run_team_code"),
    )
    for column in ("migration_type", "run_code", "status", "team_id"):
        op.create_index(op.f(f"ix_{MIGRATION_RUN_TABLE}_{column}"), MIGRATION_RUN_TABLE, [column])
    op.create_index("ix_metering_migration_status", MIGRATION_RUN_TABLE, ["team_id", "migration_type", "status"])

    op.create_table(
        PROJECTION_RUN_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("run_code", sa.String(length=96), nullable=False),
        sa.Column("projection_type", sa.String(length=32), nullable=False, server_default="electricity_interval"),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="running"),
        sa.Column("mapping_version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("source_high_watermark", sa.String(length=160), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issue_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_checksum", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("run_config", sa.JSON(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk(PROJECTION_RUN_TABLE),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "run_code", name="uq_metering_projection_run_team_code"),
    )
    for column in ("period_end", "period_start", "projection_type", "run_code", "status", "team_id"):
        op.create_index(op.f(f"ix_{PROJECTION_RUN_TABLE}_{column}"), PROJECTION_RUN_TABLE, [column])
    op.create_index(
        "ix_metering_projection_period", PROJECTION_RUN_TABLE, ["team_id", "period_start", "period_end", "status"]
    )

    op.create_table(
        BOUNDARY_MEMBER_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("boundary_id", _id_type(), nullable=False),
        sa.Column("member_code", sa.String(length=64), nullable=False),
        sa.Column("member_type", sa.String(length=24), nullable=False),
        sa.Column("sector_id", _id_type(), nullable=True),
        sa.Column("equipment_id", _id_type(), nullable=True),
        sa.Column("member_role", sa.String(length=24), nullable=False, server_default="covered"),
        sa.Column("allocation_weight", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("confirmation_status", sa.String(length=24), nullable=False, server_default="candidate"),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk(BOUNDARY_MEMBER_TABLE),
        sa.ForeignKeyConstraint(
            ["boundary_id"],
            [f"{BOUNDARY_TABLE}.id"],
            name=op.f("fk_metering_measurement_boundary_member_boundary_id_metering_measurement_boundary"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sector_id"],
            ["dataapp_monitorsector.id"],
            name=op.f("fk_metering_measurement_boundary_member_sector_id_dataapp_monitorsector"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_id"],
            ["dataapp_monitorequipment.id"],
            name=op.f("fk_metering_measurement_boundary_member_equipment_id_dataapp_monitorequipment"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "boundary_id", "member_code", name="uq_metering_boundary_member_code"),
    )
    for column in ("boundary_id", "confirmation_status", "equipment_id", "member_type", "sector_id", "team_id"):
        op.create_index(op.f(f"ix_{BOUNDARY_MEMBER_TABLE}_{column}"), BOUNDARY_MEMBER_TABLE, [column])
    op.create_index(
        "ix_metering_boundary_member_effective",
        BOUNDARY_MEMBER_TABLE,
        ["team_id", "confirmation_status", "valid_from", "valid_to"],
    )

    op.create_table(
        QUALITY_ISSUE_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("issue_key", sa.String(length=160), nullable=False),
        sa.Column("projection_run_id", _id_type(), nullable=True),
        sa.Column("equipment_id", _id_type(), nullable=True),
        sa.Column("point_code", sa.String(length=64), nullable=True),
        sa.Column("reading_time", sa.DateTime(), nullable=True),
        sa.Column("issue_type", sa.String(length=48), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="warning"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("issue_payload", sa.JSON(), nullable=True),
        *_audit_columns(),
        _tenant_fk(QUALITY_ISSUE_TABLE),
        sa.ForeignKeyConstraint(
            ["projection_run_id"],
            [f"{PROJECTION_RUN_TABLE}.id"],
            name=op.f("fk_metering_quality_issue_projection_run_id_metering_energy_projection_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_id"],
            ["dataapp_monitorequipment.id"],
            name=op.f("fk_metering_quality_issue_equipment_id_dataapp_monitorequipment"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "issue_key", name="uq_metering_quality_issue_team_key"),
    )
    for column in (
        "equipment_id",
        "issue_key",
        "issue_type",
        "projection_run_id",
        "reading_time",
        "severity",
        "status",
        "team_id",
    ):
        op.create_index(op.f(f"ix_{QUALITY_ISSUE_TABLE}_{column}"), QUALITY_ISSUE_TABLE, [column])
    op.create_index("ix_metering_quality_issue_team_status", QUALITY_ISSUE_TABLE, ["team_id", "status", "severity"])

    _add_fact_revision_columns()
    _add_carbon_source_columns()

    op.create_table(
        RECONCILIATION_TABLE,
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("billing_month", sa.String(length=7), nullable=False),
        sa.Column("projection_run_id", _id_type(), nullable=True),
        sa.Column("electricity_bill_id", _id_type(), nullable=True),
        sa.Column("source_priority", sa.String(length=24), nullable=False, server_default="meter_aggregate"),
        sa.Column("organization_total_kwh", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("meter_total_kwh", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("bill_total_kwh", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("allocated_kwh", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("unallocated_kwh", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("supersedes_id", _id_type(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="ready"),
        sa.Column("source_snapshot", sa.JSON(), nullable=True),
        *_audit_columns(),
        _tenant_fk(RECONCILIATION_TABLE),
        sa.ForeignKeyConstraint(
            ["projection_run_id"],
            [f"{PROJECTION_RUN_TABLE}.id"],
            name=op.f("fk_metering_scope2_electricity_reconciliation_projection_run_id_metering_energy_projection_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["electricity_bill_id"],
            ["dataapp_scope2electricitybill.id"],
            name=op.f(
                "fk_metering_scope2_electricity_reconciliation_electricity_bill_id_dataapp_scope2electricitybill"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            [f"{RECONCILIATION_TABLE}.id"],
            name=op.f(
                "fk_metering_scope2_electricity_reconciliation_supersedes_id_metering_scope2_electricity_reconciliation"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "billing_month", "revision_no", name="uq_scope2_reconciliation_month_revision"),
    )
    for column in (
        "billing_month",
        "electricity_bill_id",
        "is_current",
        "projection_run_id",
        "source_priority",
        "status",
        "supersedes_id",
        "team_id",
    ):
        op.create_index(op.f(f"ix_{RECONCILIATION_TABLE}_{column}"), RECONCILIATION_TABLE, [column])
    op.create_index(
        "ix_scope2_reconciliation_current", RECONCILIATION_TABLE, ["team_id", "billing_month", "is_current"]
    )

    for table_name in TENANT_TABLES:
        _enable_tenant_rls(table_name)

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                f"create unique index uq_scope2_reconciliation_one_current on {RECONCILIATION_TABLE} "
                "(team_id, billing_month) where is_current"
            )
        )
        op.execute(
            sa.text(
                f"create unique index uq_scope2_meter_aggregate_one_current on {SCOPE2_AGGREGATE_TABLE} "
                "(team_id, ammeter_id, billing_month) where is_current"
            )
        )
        _replace_energy_consumption_view()


def _add_fact_revision_columns() -> None:
    with op.batch_alter_table(ENERGY_FACT_TABLE) as batch_op:
        batch_op.drop_constraint("uq_energy_interval_team_source_record", type_="unique")
        batch_op.add_column(sa.Column("projection_run_id", _id_type(), nullable=True))
        batch_op.add_column(sa.Column("measurement_boundary_id", _id_type(), nullable=True))
        batch_op.add_column(sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("supersedes_id", _id_type(), nullable=True))
        batch_op.add_column(sa.Column("source_snapshot", sa.JSON(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_dataapp_energyintervalfact_projection_run_id_metering_energy_projection_run"),
            PROJECTION_RUN_TABLE,
            ["projection_run_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            op.f("fk_dataapp_energyintervalfact_measurement_boundary_id_metering_measurement_boundary"),
            BOUNDARY_TABLE,
            ["measurement_boundary_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            op.f("fk_dataapp_energyintervalfact_supersedes_id_dataapp_energyintervalfact"),
            ENERGY_FACT_TABLE,
            ["supersedes_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_unique_constraint(
            "uq_energy_interval_team_source_record_revision",
            ["team_id", "source_system", "source_record_id", "revision_no"],
        )
        for column in ("is_current", "measurement_boundary_id", "projection_run_id", "supersedes_id"):
            batch_op.create_index(op.f(f"ix_{ENERGY_FACT_TABLE}_{column}"), [column])
        batch_op.create_index(
            "ix_energy_interval_current_period", ["team_id", "is_current", "granularity", "period_start"]
        )

    with op.batch_alter_table(SCOPE2_AGGREGATE_TABLE) as batch_op:
        batch_op.drop_constraint("uq_scope2_meter_aggregate_team_meter_month", type_="unique")
        batch_op.add_column(sa.Column("projection_run_id", _id_type(), nullable=True))
        batch_op.add_column(sa.Column("measurement_boundary_id", _id_type(), nullable=True))
        batch_op.add_column(sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("supersedes_id", _id_type(), nullable=True))
        batch_op.add_column(sa.Column("source_snapshot", sa.JSON(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_dataapp_scope2meteraggregate_projection_run_id_metering_energy_projection_run"),
            PROJECTION_RUN_TABLE,
            ["projection_run_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            op.f("fk_dataapp_scope2meteraggregate_measurement_boundary_id_metering_measurement_boundary"),
            BOUNDARY_TABLE,
            ["measurement_boundary_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            op.f("fk_dataapp_scope2meteraggregate_supersedes_id_dataapp_scope2meteraggregate"),
            SCOPE2_AGGREGATE_TABLE,
            ["supersedes_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_unique_constraint(
            "uq_scope2_meter_aggregate_team_meter_month_revision",
            ["team_id", "ammeter_id", "billing_month", "revision_no"],
        )
        for column in ("is_current", "measurement_boundary_id", "projection_run_id", "supersedes_id"):
            batch_op.create_index(op.f(f"ix_{SCOPE2_AGGREGATE_TABLE}_{column}"), [column])
        batch_op.create_index("ix_scope2_meter_aggregate_current_month", ["team_id", "is_current", "billing_month"])


def _add_carbon_source_columns() -> None:
    for table_name in CARBON_ACTIVITY_TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(
                sa.Column("record_usage", sa.String(length=24), nullable=False, server_default="operational")
            )
            batch_op.add_column(sa.Column("source_record_no", sa.String(length=128), nullable=True))
            batch_op.add_column(sa.Column("source_version", sa.Integer(), nullable=False, server_default="1"))
            batch_op.add_column(sa.Column("voucher_no", sa.String(length=128), nullable=True))
            batch_op.add_column(
                sa.Column("evidence_status", sa.String(length=24), nullable=False, server_default="pending")
            )
            batch_op.add_column(sa.Column("source_hash", sa.String(length=64), nullable=True))
            batch_op.create_index(f"ix_{table_name}_record_usage", ["record_usage"])
            batch_op.create_index(f"ix_{table_name}_source_record_no", ["source_record_no"])
            batch_op.create_index(f"ix_{table_name}_voucher_no", ["voucher_no"])
            batch_op.create_index(f"ix_{table_name}_evidence_status", ["evidence_status"])
            batch_op.create_index(f"ix_{table_name}_source_hash", ["source_hash"])
            batch_op.create_unique_constraint(
                CARBON_SOURCE_CONSTRAINTS[table_name],
                ["team_id", "source_record_no", "source_version"],
            )

        columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
        marker_conditions: list[str] = []
        if "attachment" in columns:
            marker_conditions.append("lower(coalesce(attachment, '')) like '/demo/%'")
        if "remark" in columns:
            marker_conditions.extend(
                [
                    "lower(coalesce(remark, '')) like '%carbon_mvp_seed%'",
                    "lower(coalesce(remark, '')) like '%demo%'",
                    "lower(coalesce(remark, '')) like '%mock%'",
                    "lower(coalesce(remark, '')) like '%seed%'",
                    "coalesce(remark, '') like '%MVP补录%'",
                ]
            )
        if marker_conditions:
            op.execute(
                sa.text(
                    f"update {table_name} set record_usage = 'reference', evidence_status = 'unverified' "
                    f"where {' or '.join(marker_conditions)}"
                )
            )


def downgrade() -> None:
    msg = "This release retains source and revision history; database downgrade is intentionally disabled."
    raise RuntimeError(msg)
