"""add device foundation tables

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-05-22
"""

import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def _id_type() -> sa.BigInteger:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _device_type_seed_rows() -> list[dict[str, object]]:
    return [
        {"id": 1, "code": "meter", "name": "电表", "parent_code": None, "energy_type": "electricity", "is_energy_device": True, "is_special_equipment": False, "default_protocol": "http_yunji", "is_enabled": True, "remark": None},
        {"id": 2, "code": "pv_inverter", "name": "光伏逆变器", "parent_code": None, "energy_type": "electricity", "is_energy_device": True, "is_special_equipment": False, "default_protocol": "mqtt", "is_enabled": True, "remark": None},
        {"id": 3, "code": "storage_bms", "name": "储能 BMS", "parent_code": None, "energy_type": "electricity", "is_energy_device": True, "is_special_equipment": False, "default_protocol": "mqtt", "is_enabled": True, "remark": None},
        {"id": 4, "code": "charger", "name": "充电桩", "parent_code": None, "energy_type": "electricity", "is_energy_device": True, "is_special_equipment": False, "default_protocol": "mqtt", "is_enabled": True, "remark": None},
        {"id": 5, "code": "forklift", "name": "叉车", "parent_code": None, "energy_type": "electricity", "is_energy_device": False, "is_special_equipment": True, "default_protocol": None, "is_enabled": True, "remark": None},
        {"id": 6, "code": "crane", "name": "起重机", "parent_code": None, "energy_type": "electricity", "is_energy_device": False, "is_special_equipment": True, "default_protocol": None, "is_enabled": True, "remark": None},
        {"id": 7, "code": "weighbridge", "name": "衡器设备", "parent_code": None, "energy_type": "electricity", "is_energy_device": False, "is_special_equipment": True, "default_protocol": None, "is_enabled": True, "remark": None},
        {"id": 8, "code": "automation_equipment", "name": "自动化及辅助设备", "parent_code": None, "energy_type": "electricity", "is_energy_device": False, "is_special_equipment": False, "default_protocol": None, "is_enabled": True, "remark": None},
        {"id": 9, "code": "camera", "name": "摄像头", "parent_code": None, "energy_type": "electricity", "is_energy_device": False, "is_special_equipment": False, "default_protocol": "mqtt", "is_enabled": True, "remark": None},
    ]


def upgrade() -> None:
    op.create_table(
        "dataapp_devicetype",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("parent_code", sa.String(length=32), nullable=True),
        sa.Column("energy_type", sa.String(length=20), nullable=True),
        sa.Column("is_energy_device", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_special_equipment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_protocol", sa.String(length=20), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_devicetype")),
        sa.UniqueConstraint("code", name="uq_dataapp_devicetype_code"),
    )
    op.create_index(op.f("ix_dataapp_devicetype_code"), "dataapp_devicetype", ["code"])
    op.create_index(op.f("ix_dataapp_devicetype_parent_code"), "dataapp_devicetype", ["parent_code"])

    op.create_table(
        "dataapp_devicepoint",
        sa.Column("id", _id_type(), nullable=False),
        sa.Column("device_id", _id_type(), nullable=False),
        sa.Column("point_code", sa.String(length=64), nullable=False),
        sa.Column("point_name", sa.String(length=100), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("value_type", sa.String(length=16), nullable=False, server_default="float"),
        sa.Column("source_field", sa.String(length=64), nullable=True),
        sa.Column("sampling_interval_seconds", sa.Integer(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_alarm_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("upper_limit", sa.Float(), nullable=True),
        sa.Column("lower_limit", sa.Float(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataapp_devicepoint")),
        sa.ForeignKeyConstraint(["device_id"], ["dataapp_monitorequipment.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("device_id", "point_code", name="uq_dataapp_devicepoint_device_point"),
    )
    op.create_index(op.f("ix_dataapp_devicepoint_device_id"), "dataapp_devicepoint", ["device_id"])

    device_type = sa.table(
        "dataapp_devicetype",
        sa.column("id", _id_type()),
        sa.column("code", sa.String(length=32)),
        sa.column("name", sa.String(length=64)),
        sa.column("parent_code", sa.String(length=32)),
        sa.column("energy_type", sa.String(length=20)),
        sa.column("is_energy_device", sa.Boolean()),
        sa.column("is_special_equipment", sa.Boolean()),
        sa.column("default_protocol", sa.String(length=20)),
        sa.column("is_enabled", sa.Boolean()),
        sa.column("remark", sa.Text()),
    )
    op.bulk_insert(device_type, _device_type_seed_rows())

    op.add_column("dataapp_monitorequipment", sa.Column("device_type_id", _id_type(), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("asset_code", sa.String(length=64), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("model", sa.String(length=100), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("manufacturer", sa.String(length=100), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("owner_unit", sa.String(length=100), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("warehouse_name", sa.String(length=100), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("warehouse_code", sa.String(length=32), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("energy_type", sa.String(length=20), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("rated_power_kw", sa.Float(), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("network_env", sa.String(length=100), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("data_acquisition_method", sa.String(length=30), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("running_status", sa.String(length=30), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("last_inspection_at", sa.DateTime(), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("inspection_due_at", sa.DateTime(), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("registration_code", sa.String(length=64), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("remark", sa.Text(), nullable=True))
    op.create_index(op.f("ix_dataapp_monitorequipment_asset_code"), "dataapp_monitorequipment", ["asset_code"])
    op.create_index(op.f("ix_dataapp_monitorequipment_device_type_id"), "dataapp_monitorequipment", ["device_type_id"])
    op.create_index(op.f("ix_dataapp_monitorequipment_energy_type"), "dataapp_monitorequipment", ["energy_type"])
    op.create_index(op.f("ix_dataapp_monitorequipment_running_status"), "dataapp_monitorequipment", ["running_status"])
    op.create_index(op.f("ix_dataapp_monitorequipment_warehouse_code"), "dataapp_monitorequipment", ["warehouse_code"])
    op.create_index(op.f("ix_dataapp_monitorequipment_warehouse_name"), "dataapp_monitorequipment", ["warehouse_name"])

    op.execute(
        sa.text(
            """
            update dataapp_monitorequipment
            set device_type_id = case
                when category = 0 then 1
                when category = 1 then 2
                when category = 2 then 9
                else device_type_id
            end
            """
        )
    )

    op.add_column("dataapp_warningrule", sa.Column("equipment_id", _id_type(), nullable=True))
    op.add_column("dataapp_warningrule", sa.Column("point_code", sa.String(length=64), nullable=True))
    op.add_column("dataapp_warningrule", sa.Column("alarm_code", sa.String(length=64), nullable=True))
    op.add_column("dataapp_warningrule", sa.Column("alarm_name", sa.String(length=64), nullable=True))
    op.add_column("dataapp_warningrule", sa.Column("alarm_level", sa.String(length=16), nullable=True, server_default="warning"))
    op.add_column("dataapp_warningrule", sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index(op.f("ix_dataapp_warningrule_alarm_code"), "dataapp_warningrule", ["alarm_code"])
    op.create_index(op.f("ix_dataapp_warningrule_alarm_level"), "dataapp_warningrule", ["alarm_level"])
    op.create_index(op.f("ix_dataapp_warningrule_equipment_id"), "dataapp_warningrule", ["equipment_id"])
    op.create_index(op.f("ix_dataapp_warningrule_point_code"), "dataapp_warningrule", ["point_code"])

    op.add_column("dataapp_alarmevent", sa.Column("alarm_code", sa.String(length=64), nullable=True))
    op.add_column("dataapp_alarmevent", sa.Column("alarm_name", sa.String(length=64), nullable=True))
    op.add_column("dataapp_alarmevent", sa.Column("alarm_level", sa.String(length=16), nullable=True, server_default="warning"))
    op.add_column("dataapp_alarmevent", sa.Column("alarm_category", sa.String(length=16), nullable=True, server_default="device"))
    op.add_column("dataapp_alarmevent", sa.Column("point_code", sa.String(length=64), nullable=True))
    op.add_column("dataapp_alarmevent", sa.Column("current_value", sa.Float(), nullable=True))
    op.add_column("dataapp_alarmevent", sa.Column("threshold_value", sa.Float(), nullable=True))
    op.add_column("dataapp_alarmevent", sa.Column("status", sa.String(length=20), nullable=True, server_default="open"))
    op.add_column("dataapp_alarmevent", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.add_column("dataapp_alarmevent", sa.Column("handled_by", sa.String(length=64), nullable=True))
    op.add_column("dataapp_alarmevent", sa.Column("handle_note", sa.Text(), nullable=True))
    op.create_index(op.f("ix_dataapp_alarmevent_alarm_code"), "dataapp_alarmevent", ["alarm_code"])
    op.create_index(op.f("ix_dataapp_alarmevent_alarm_level"), "dataapp_alarmevent", ["alarm_level"])
    op.create_index(op.f("ix_dataapp_alarmevent_alarm_category"), "dataapp_alarmevent", ["alarm_category"])
    op.create_index(op.f("ix_dataapp_alarmevent_point_code"), "dataapp_alarmevent", ["point_code"])
    op.create_index(op.f("ix_dataapp_alarmevent_status"), "dataapp_alarmevent", ["status"])

    op.execute(
        sa.text(
            """
            update dataapp_alarmevent
            set status = case when is_handle then 'resolved' else 'open' end
            """
        )
    )

    op.alter_column("dataapp_devicetype", "is_energy_device", server_default=None)
    op.alter_column("dataapp_devicetype", "is_special_equipment", server_default=None)
    op.alter_column("dataapp_devicetype", "is_enabled", server_default=None)
    op.alter_column("dataapp_devicepoint", "value_type", server_default=None)
    op.alter_column("dataapp_devicepoint", "is_enabled", server_default=None)
    op.alter_column("dataapp_devicepoint", "is_alarm_enabled", server_default=None)
    op.alter_column("dataapp_warningrule", "alarm_level", server_default=None)
    op.alter_column("dataapp_warningrule", "is_enabled", server_default=None)
    op.alter_column("dataapp_alarmevent", "alarm_level", server_default=None)
    op.alter_column("dataapp_alarmevent", "alarm_category", server_default=None)
    op.alter_column("dataapp_alarmevent", "status", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_dataapp_alarmevent_status"), table_name="dataapp_alarmevent")
    op.drop_index(op.f("ix_dataapp_alarmevent_point_code"), table_name="dataapp_alarmevent")
    op.drop_index(op.f("ix_dataapp_alarmevent_alarm_category"), table_name="dataapp_alarmevent")
    op.drop_index(op.f("ix_dataapp_alarmevent_alarm_level"), table_name="dataapp_alarmevent")
    op.drop_index(op.f("ix_dataapp_alarmevent_alarm_code"), table_name="dataapp_alarmevent")
    op.drop_column("dataapp_alarmevent", "handle_note")
    op.drop_column("dataapp_alarmevent", "handled_by")
    op.drop_column("dataapp_alarmevent", "resolved_at")
    op.drop_column("dataapp_alarmevent", "status")
    op.drop_column("dataapp_alarmevent", "threshold_value")
    op.drop_column("dataapp_alarmevent", "current_value")
    op.drop_column("dataapp_alarmevent", "point_code")
    op.drop_column("dataapp_alarmevent", "alarm_category")
    op.drop_column("dataapp_alarmevent", "alarm_level")
    op.drop_column("dataapp_alarmevent", "alarm_name")
    op.drop_column("dataapp_alarmevent", "alarm_code")

    op.drop_index(op.f("ix_dataapp_warningrule_point_code"), table_name="dataapp_warningrule")
    op.drop_index(op.f("ix_dataapp_warningrule_equipment_id"), table_name="dataapp_warningrule")
    op.drop_index(op.f("ix_dataapp_warningrule_alarm_level"), table_name="dataapp_warningrule")
    op.drop_index(op.f("ix_dataapp_warningrule_alarm_code"), table_name="dataapp_warningrule")
    op.drop_column("dataapp_warningrule", "is_enabled")
    op.drop_column("dataapp_warningrule", "alarm_level")
    op.drop_column("dataapp_warningrule", "alarm_name")
    op.drop_column("dataapp_warningrule", "alarm_code")
    op.drop_column("dataapp_warningrule", "point_code")
    op.drop_column("dataapp_warningrule", "equipment_id")

    op.drop_index(op.f("ix_dataapp_monitorequipment_warehouse_name"), table_name="dataapp_monitorequipment")
    op.drop_index(op.f("ix_dataapp_monitorequipment_warehouse_code"), table_name="dataapp_monitorequipment")
    op.drop_index(op.f("ix_dataapp_monitorequipment_running_status"), table_name="dataapp_monitorequipment")
    op.drop_index(op.f("ix_dataapp_monitorequipment_energy_type"), table_name="dataapp_monitorequipment")
    op.drop_index(op.f("ix_dataapp_monitorequipment_device_type_id"), table_name="dataapp_monitorequipment")
    op.drop_index(op.f("ix_dataapp_monitorequipment_asset_code"), table_name="dataapp_monitorequipment")
    op.drop_column("dataapp_monitorequipment", "remark")
    op.drop_column("dataapp_monitorequipment", "registration_code")
    op.drop_column("dataapp_monitorequipment", "inspection_due_at")
    op.drop_column("dataapp_monitorequipment", "last_inspection_at")
    op.drop_column("dataapp_monitorequipment", "running_status")
    op.drop_column("dataapp_monitorequipment", "data_acquisition_method")
    op.drop_column("dataapp_monitorequipment", "network_env")
    op.drop_column("dataapp_monitorequipment", "rated_power_kw")
    op.drop_column("dataapp_monitorequipment", "energy_type")
    op.drop_column("dataapp_monitorequipment", "warehouse_code")
    op.drop_column("dataapp_monitorequipment", "warehouse_name")
    op.drop_column("dataapp_monitorequipment", "owner_unit")
    op.drop_column("dataapp_monitorequipment", "manufacturer")
    op.drop_column("dataapp_monitorequipment", "model")
    op.drop_column("dataapp_monitorequipment", "asset_code")
    op.drop_column("dataapp_monitorequipment", "device_type_id")

    op.drop_index(op.f("ix_dataapp_devicepoint_device_id"), table_name="dataapp_devicepoint")
    op.drop_table("dataapp_devicepoint")

    op.drop_index(op.f("ix_dataapp_devicetype_parent_code"), table_name="dataapp_devicetype")
    op.drop_index(op.f("ix_dataapp_devicetype_code"), table_name="dataapp_devicetype")
    op.drop_table("dataapp_devicetype")
