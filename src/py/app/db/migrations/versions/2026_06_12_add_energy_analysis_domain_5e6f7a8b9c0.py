"""add energy analysis domain

Revision ID: 5e6f7a8b9c0
Revises: 4d5e6f7a8b9
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from advanced_alchemy.types import GUID, DateTimeUTC
from alembic import op

revision = "5e6f7a8b9c0"
down_revision = "4d5e6f7a8b9"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]
sa.DateTimeUTC = DateTimeUTC  # pyright: ignore[attr-defined]


TABLES = (
    "dataapp_energyusesystem",
    "dataapp_energyusesystembinding",
    "dataapp_energytariffplan",
    "dataapp_energytariffsegment",
    "dataapp_energyintervalfact",
    "dataapp_equipmentworkloadfact",
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
    return sa.ForeignKeyConstraint(
        ["team_id"],
        ["team.id"],
        name=f"fk_{table_name}_team_id_team",
        ondelete="CASCADE",
    )


def _tenant_policy_name(table_name: str) -> str:
    return f"rls_{table_name}_tenant_scope"


def _enable_tenant_rls(table_name: str) -> None:
    policy_name = _tenant_policy_name(table_name)
    op.execute(sa.text(f"alter table {table_name} enable row level security"))
    op.execute(sa.text(f"alter table {table_name} force row level security"))
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
            )
            """
        )
    )


def _disable_tenant_rls(table_name: str) -> None:
    policy_name = _tenant_policy_name(table_name)
    op.execute(sa.text(f"drop policy if exists {policy_name} on {table_name}"))
    op.execute(sa.text(f"alter table {table_name} no force row level security"))
    op.execute(sa.text(f"alter table {table_name} disable row level security"))


def upgrade() -> None:
    op.create_table(
        "dataapp_energyusesystem",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("system_type", sa.String(length=32), nullable=False),
        sa.Column("parent_code", sa.String(length=64), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk("dataapp_energyusesystem"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_energyusesystem")),
        sa.UniqueConstraint("team_id", "code", name="uq_energy_use_system_team_code"),
    )
    op.create_index(op.f("ix_dataapp_energyusesystem_code"), "dataapp_energyusesystem", ["code"])
    op.create_index(op.f("ix_dataapp_energyusesystem_system_type"), "dataapp_energyusesystem", ["system_type"])
    op.create_index(op.f("ix_dataapp_energyusesystem_parent_code"), "dataapp_energyusesystem", ["parent_code"])
    op.create_index(op.f("ix_dataapp_energyusesystem_is_enabled"), "dataapp_energyusesystem", ["is_enabled"])
    op.create_index(op.f("ix_dataapp_energyusesystem_team_id"), "dataapp_energyusesystem", ["team_id"])
    op.create_index("ix_energy_use_system_team_type", "dataapp_energyusesystem", ["team_id", "system_type"])
    op.alter_column("dataapp_energyusesystem", "is_enabled", server_default=None)

    op.create_table(
        "dataapp_energyusesystembinding",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("system_code", sa.String(length=64), nullable=False),
        sa.Column("equipment_id", _id_type(), nullable=True),
        sa.Column("equipment_code", sa.String(length=64), nullable=True),
        sa.Column("equipment_name", sa.String(length=128), nullable=True),
        sa.Column("sector_id", _id_type(), nullable=True),
        sa.Column("area_id", sa.String(length=32), nullable=True),
        sa.Column("area_name", sa.String(length=128), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["equipment_id"], ["dataapp_monitorequipment.id"], name="fk_energy_use_system_binding_equipment", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sector_id"], ["dataapp_monitorsector.id"], name="fk_energy_use_system_binding_sector", ondelete="SET NULL"),
        _tenant_fk("dataapp_energyusesystembinding"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_energyusesystembinding")),
        sa.UniqueConstraint("team_id", "system_code", "equipment_id", name="uq_energy_use_system_binding_equipment"),
    )
    for column in ("system_code", "equipment_id", "equipment_code", "sector_id", "area_id", "is_primary", "team_id"):
        op.create_index(op.f(f"ix_dataapp_energyusesystembinding_{column}"), "dataapp_energyusesystembinding", [column])
    op.create_index("ix_energy_use_system_binding_system", "dataapp_energyusesystembinding", ["team_id", "system_code"])
    op.create_index("ix_energy_use_system_binding_resource", "dataapp_energyusesystembinding", ["equipment_id", "sector_id"])
    op.alter_column("dataapp_energyusesystembinding", "is_primary", server_default=None)

    op.create_table(
        "dataapp_energytariffplan",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("energy_type_code", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        _tenant_fk("dataapp_energytariffplan"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_energytariffplan")),
        sa.UniqueConstraint("team_id", "code", name="uq_energy_tariff_plan_team_code"),
    )
    for column in ("code", "energy_type_code", "is_enabled", "team_id"):
        op.create_index(op.f(f"ix_dataapp_energytariffplan_{column}"), "dataapp_energytariffplan", [column])
    op.create_index("ix_energy_tariff_plan_team_type", "dataapp_energytariffplan", ["team_id", "energy_type_code"])
    op.alter_column("dataapp_energytariffplan", "currency", server_default=None)
    op.alter_column("dataapp_energytariffplan", "is_enabled", server_default=None)

    op.create_table(
        "dataapp_energytariffsegment",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("plan_id", _id_type(), nullable=False),
        sa.Column("segment_type", sa.String(length=16), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False, server_default="CNY/kWh"),
        sa.Column("sort_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["plan_id"], ["dataapp_energytariffplan.id"], name="fk_energy_tariff_segment_plan", ondelete="CASCADE"),
        _tenant_fk("dataapp_energytariffsegment"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_energytariffsegment")),
    )
    for column in ("plan_id", "segment_type", "team_id"):
        op.create_index(op.f(f"ix_dataapp_energytariffsegment_{column}"), "dataapp_energytariffsegment", [column])
    op.create_index("ix_energy_tariff_segment_plan", "dataapp_energytariffsegment", ["team_id", "plan_id", "segment_type"])
    op.alter_column("dataapp_energytariffsegment", "unit", server_default=None)
    op.alter_column("dataapp_energytariffsegment", "sort_index", server_default=None)

    op.create_table(
        "dataapp_energyintervalfact",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False, server_default="meter_interval"),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("energy_type_code", sa.String(length=32), nullable=False),
        sa.Column("equipment_id", _id_type(), nullable=True),
        sa.Column("equipment_code", sa.String(length=64), nullable=True),
        sa.Column("equipment_name", sa.String(length=128), nullable=True),
        sa.Column("area_id", sa.String(length=32), nullable=True),
        sa.Column("area_name", sa.String(length=128), nullable=True),
        sa.Column("use_system_code", sa.String(length=64), nullable=True),
        sa.Column("use_system_name", sa.String(length=128), nullable=True),
        sa.Column("granularity", sa.String(length=16), nullable=False, server_default="hour"),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False, server_default="kWh"),
        sa.Column("cost_cny", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("tariff_segment_type", sa.String(length=16), nullable=True),
        sa.Column("reading_count", sa.Integer(), nullable=True),
        sa.Column("data_quality", sa.String(length=24), nullable=False, server_default="measured"),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["equipment_id"], ["dataapp_monitorequipment.id"], name="fk_energy_interval_equipment", ondelete="SET NULL"),
        _tenant_fk("dataapp_energyintervalfact"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_energyintervalfact")),
        sa.UniqueConstraint("team_id", "source_system", "source_record_id", name="uq_energy_interval_team_source_record"),
    )
    for column in ("energy_type_code", "equipment_id", "equipment_code", "area_id", "use_system_code", "granularity", "period_start", "period_end", "tariff_segment_type", "data_quality", "team_id"):
        op.create_index(op.f(f"ix_dataapp_energyintervalfact_{column}"), "dataapp_energyintervalfact", [column])
    op.create_index("ix_energy_interval_team_period", "dataapp_energyintervalfact", ["team_id", "period_start", "period_end"])
    op.create_index("ix_energy_interval_resource", "dataapp_energyintervalfact", ["equipment_id", "area_id", "energy_type_code"])
    op.alter_column("dataapp_energyintervalfact", "source_system", server_default=None)
    op.alter_column("dataapp_energyintervalfact", "granularity", server_default=None)
    op.alter_column("dataapp_energyintervalfact", "unit", server_default=None)
    op.alter_column("dataapp_energyintervalfact", "data_quality", server_default=None)

    op.create_table(
        "dataapp_equipmentworkloadfact",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("equipment_id", _id_type(), nullable=True),
        sa.Column("equipment_code", sa.String(length=64), nullable=True),
        sa.Column("equipment_name", sa.String(length=128), nullable=True),
        sa.Column("area_id", sa.String(length=32), nullable=True),
        sa.Column("area_name", sa.String(length=128), nullable=True),
        sa.Column("use_system_code", sa.String(length=64), nullable=True),
        sa.Column("workload_type", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("workload_amount", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("workload_unit", sa.String(length=16), nullable=False),
        sa.Column("run_hours", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("record_status", sa.String(length=16), nullable=False, server_default="confirmed"),
        sa.Column("remark", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["equipment_id"], ["dataapp_monitorequipment.id"], name="fk_equipment_workload_equipment", ondelete="SET NULL"),
        _tenant_fk("dataapp_equipmentworkloadfact"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_equipmentworkloadfact")),
        sa.UniqueConstraint("team_id", "source_system", "source_record_id", name="uq_equipment_workload_team_source_record"),
    )
    for column in ("equipment_id", "equipment_code", "area_id", "use_system_code", "workload_type", "period_start", "period_end", "record_status", "team_id"):
        op.create_index(op.f(f"ix_dataapp_equipmentworkloadfact_{column}"), "dataapp_equipmentworkloadfact", [column])
    op.create_index("ix_equipment_workload_team_period", "dataapp_equipmentworkloadfact", ["team_id", "period_start", "period_end"])
    op.create_index("ix_equipment_workload_resource", "dataapp_equipmentworkloadfact", ["equipment_id", "area_id", "workload_type"])
    op.alter_column("dataapp_equipmentworkloadfact", "source_system", server_default=None)
    op.alter_column("dataapp_equipmentworkloadfact", "record_status", server_default=None)

    for table_name in TABLES:
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(TABLES):
        _disable_tenant_rls(table_name)
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
