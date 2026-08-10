"""unify meter reading fact source

Revision ID: 8f9a0b1c2d3e
Revises: 7e8f9a0b1c2d
Create Date: 2026-07-10
"""

from __future__ import annotations

# ruff: noqa: S608
import sqlalchemy as sa
from advanced_alchemy.types import GUID
from alembic import op

revision = "8f9a0b1c2d3e"
down_revision = "7e8f9a0b1c2d"
branch_labels = None
depends_on = None

sa.GUID = GUID  # pyright: ignore[attr-defined]

OLD_POINT_TABLE = "iot_meter_point_reading"
FACT_TABLE = "metering_meter_reading_fact"
MAPPING_TABLE = "iot_mqtt_point_mapping"

POINT_META = {
    "forward_active_total": ("正向有功总电能", "kWh", "forward", "active", "total"),
    "forward_active_sharp": ("正向有功尖电能", "kWh", "forward", "active", "sharp"),
    "forward_active_peak": ("正向有功峰电能", "kWh", "forward", "active", "peak"),
    "forward_active_flat": ("正向有功平电能", "kWh", "forward", "active", "flat"),
    "forward_active_valley": ("正向有功谷电能", "kWh", "forward", "active", "valley"),
    "forward_reactive_total": ("正向无功总电能", "kvarh", "forward", "reactive", "total"),
    "forward_reactive_sharp": ("正向无功尖电能", "kvarh", "forward", "reactive", "sharp"),
    "forward_reactive_peak": ("正向无功峰电能", "kvarh", "forward", "reactive", "peak"),
    "forward_reactive_flat": ("正向无功平电能", "kvarh", "forward", "reactive", "flat"),
    "forward_reactive_valley": ("正向无功谷电能", "kvarh", "forward", "reactive", "valley"),
    "reverse_active_total": ("反向有功总电能", "kWh", "reverse", "active", "total"),
    "reverse_active_sharp": ("反向有功尖电能", "kWh", "reverse", "active", "sharp"),
    "reverse_active_peak": ("反向有功峰电能", "kWh", "reverse", "active", "peak"),
    "reverse_active_flat": ("反向有功平电能", "kWh", "reverse", "active", "flat"),
    "reverse_active_valley": ("反向有功谷电能", "kWh", "reverse", "active", "valley"),
    "reverse_reactive_total": ("反向无功总电能", "kvarh", "reverse", "reactive", "total"),
    "reverse_reactive_sharp": ("反向无功尖电能", "kvarh", "reverse", "reactive", "sharp"),
    "reverse_reactive_peak": ("反向无功峰电能", "kvarh", "reverse", "reactive", "peak"),
    "reverse_reactive_flat": ("反向无功平电能", "kvarh", "reverse", "reactive", "flat"),
    "reverse_reactive_valley": ("反向无功谷电能", "kvarh", "reverse", "reactive", "valley"),
}

SZSCADA_TAG_MAP = {
    "tag_010_p001": "forward_active_total",
    "tag_010_p002": "forward_active_sharp",
    "tag_010_p003": "forward_active_peak",
    "tag_010_p004": "forward_active_flat",
    "tag_010_p005": "forward_active_valley",
    "tag_010_p006": "forward_reactive_total",
    "tag_010_p007": "forward_reactive_sharp",
    "tag_010_p008": "forward_reactive_peak",
    "tag_010_p009": "forward_reactive_flat",
    "tag_010_p010": "forward_reactive_valley",
    "tag_010_p011": "reverse_active_total",
    "tag_010_p012": "reverse_active_sharp",
    "tag_010_p013": "reverse_active_peak",
    "tag_010_p014": "reverse_active_flat",
    "tag_010_p015": "reverse_active_valley",
    "tag_010_p016": "reverse_reactive_total",
    "tag_010_p017": "reverse_reactive_sharp",
    "tag_010_p018": "reverse_reactive_peak",
    "tag_010_p019": "reverse_reactive_flat",
    "tag_010_p020": "reverse_reactive_valley",
}


def _id_type() -> sa.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    with op.batch_alter_table(MAPPING_TABLE, schema=None) as batch_op:
        batch_op.add_column(sa.Column("point_name", sa.String(length=128), nullable=True))
    _backfill_mapping_point_names()
    with op.batch_alter_table(MAPPING_TABLE, schema=None) as batch_op:
        batch_op.drop_column("target_field")

    op.rename_table(OLD_POINT_TABLE, FACT_TABLE)
    if _is_postgresql():
        op.execute(sa.text(f"alter sequence if exists {OLD_POINT_TABLE}_id_seq rename to {FACT_TABLE}_id_seq"))
        op.execute(
            sa.text(f"alter table {FACT_TABLE} alter column id set default nextval('{FACT_TABLE}_id_seq'::regclass)")
        )
        op.execute(sa.text(f"alter sequence {FACT_TABLE}_id_seq owned by {FACT_TABLE}.id"))
    _replace_fact_foreign_keys_and_indexes()
    with op.batch_alter_table(FACT_TABLE, schema=None) as batch_op:
        batch_op.drop_constraint("uq_iot_meter_reading_message_binding_tag", type_="unique")
        batch_op.alter_column("source_tag", new_column_name="source_point_code", existing_type=sa.String(length=64))
        batch_op.alter_column(
            "source_name", new_column_name="source_point_name", existing_type=sa.String(length=128), nullable=True
        )
        batch_op.alter_column("source_message_id", existing_type=_id_type(), nullable=True)
        batch_op.alter_column("binding_id", existing_type=_id_type(), nullable=True)
        batch_op.add_column(sa.Column("source_system", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("source_record_id", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("point_name", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("energy_direction", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("energy_kind", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("tou_period", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("value_kind", sa.String(length=32), nullable=True))

    _backfill_existing_fact_rows()

    with op.batch_alter_table(FACT_TABLE, schema=None) as batch_op:
        batch_op.alter_column("source_system", existing_type=sa.String(length=32), nullable=False)
        batch_op.alter_column("source_record_id", existing_type=sa.String(length=160), nullable=False)
        batch_op.alter_column("point_name", existing_type=sa.String(length=128), nullable=False)
        batch_op.alter_column("energy_direction", existing_type=sa.String(length=16), nullable=False)
        batch_op.alter_column("energy_kind", existing_type=sa.String(length=16), nullable=False)
        batch_op.alter_column("tou_period", existing_type=sa.String(length=16), nullable=False)
        batch_op.alter_column("value_kind", existing_type=sa.String(length=32), nullable=False)
        batch_op.create_unique_constraint(
            "uq_metering_fact_source_record_point",
            ["team_id", "source_system", "source_record_id", "equipment_id", "point_code", "value_kind"],
        )
        batch_op.create_index("ix_metering_fact_equipment_time", ["team_id", "equipment_id", "reading_time"])
        batch_op.create_index("ix_metering_fact_point_time", ["team_id", "point_code", "reading_time"])
        for column in (
            "binding_id",
            "equipment_id",
            "quality_status",
            "reading_time",
            "source_message_id",
            "source_record_id",
            "source_system",
            "team_id",
            "value_kind",
        ):
            batch_op.create_index(op.f(f"ix_{FACT_TABLE}_{column}"), [column])

    _enable_fact_rls()


def _replace_fact_foreign_keys_and_indexes() -> None:
    """Normalize constraints for both Alembic-created and pre-registered production tables."""
    inspector = sa.inspect(op.get_bind())
    managed_fk_columns = {"source_message_id", "binding_id", "equipment_id", "team_id"}
    for foreign_key in inspector.get_foreign_keys(FACT_TABLE):
        columns = set(foreign_key.get("constrained_columns") or [])
        name = foreign_key.get("name")
        if name and columns and columns <= managed_fk_columns:
            op.drop_constraint(name, FACT_TABLE, type_="foreignkey")

    managed_index_columns = {
        ("source_message_id",),
        ("binding_id",),
        ("equipment_id",),
        ("quality_status",),
        ("reading_time",),
        ("team_id",),
        ("team_id", "equipment_id", "reading_time"),
    }
    for index in inspector.get_indexes(FACT_TABLE):
        columns = tuple(index.get("column_names") or [])
        name = index.get("name")
        if name and columns in managed_index_columns:
            op.drop_index(name, table_name=FACT_TABLE)

    with op.batch_alter_table(FACT_TABLE, schema=None) as batch_op:
        batch_op.create_foreign_key(
            op.f("fk_metering_meter_reading_fact_source_message_id_iot_mqtt_inbound_message"),
            "iot_mqtt_inbound_message",
            ["source_message_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            op.f("fk_metering_meter_reading_fact_binding_id_iot_mqtt_device_binding"),
            "iot_mqtt_device_binding",
            ["binding_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            op.f("fk_metering_meter_reading_fact_equipment_id_dataapp_monitorequipment"),
            "dataapp_monitorequipment",
            ["equipment_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            op.f("fk_metering_meter_reading_fact_team_id_team"),
            "team",
            ["team_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    msg = "Downgrade is not supported for the canonical meter fact rename. Use the query/worker rollback switches."
    raise RuntimeError(msg)


def _backfill_mapping_point_names() -> None:
    for point_code, (point_name, unit, *_rest) in POINT_META.items():
        op.execute(
            sa.text(
                f"""
                update {MAPPING_TABLE}
                set point_name = :point_name, unit = coalesce(unit, :unit)
                where point_code = :point_code
                """
            ).bindparams(point_code=point_code, point_name=point_name, unit=unit)
        )
    for source_tag, point_code in SZSCADA_TAG_MAP.items():
        point_name, unit, *_rest = POINT_META[point_code]
        op.execute(
            sa.text(
                f"""
                update {MAPPING_TABLE}
                set point_code = :point_code, point_name = :point_name, unit = coalesce(unit, :unit)
                where source_tag = :source_tag
                """
            ).bindparams(source_tag=source_tag, point_code=point_code, point_name=point_name, unit=unit)
        )


def _backfill_existing_fact_rows() -> None:
    op.execute(
        sa.text(
            f"""
            update {FACT_TABLE}
            set
                source_system = 'mqtt_szscada',
                source_record_id = 'mqtt:' || source_message_id::text || ':' || binding_id::text || ':' || source_point_code,
                value_kind = 'register_index',
                point_code = case source_point_code
                    {" ".join(f"when '{tag}' then '{code}'" for tag, code in SZSCADA_TAG_MAP.items())}
                    else point_code
                end
            """
        )
    )
    for point_code, (point_name, unit, direction, kind, period) in POINT_META.items():
        op.execute(
            sa.text(
                f"""
                update {FACT_TABLE}
                set
                    point_name = :point_name,
                    unit = coalesce(unit, :unit),
                    energy_direction = :direction,
                    energy_kind = :kind,
                    tou_period = :period
                where point_code = :point_code
                """
            ).bindparams(
                point_code=point_code,
                point_name=point_name,
                unit=unit,
                direction=direction,
                kind=kind,
                period=period,
            )
        )


def _enable_fact_rls() -> None:
    if not _is_postgresql():
        return
    op.execute(sa.text(f"alter table {FACT_TABLE} enable row level security"))
    op.execute(sa.text(f"alter table {FACT_TABLE} force row level security"))
    op.execute(sa.text(f"drop policy if exists rls_{FACT_TABLE}_tenant_scope on {FACT_TABLE}"))
    op.execute(
        sa.text(
            f"""
            create policy rls_{FACT_TABLE}_tenant_scope on {FACT_TABLE}
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
