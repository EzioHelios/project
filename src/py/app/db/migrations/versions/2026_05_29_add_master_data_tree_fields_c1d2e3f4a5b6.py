"""add master data tree fields

Revision ID: c1d2e3f4a5b6
Revises: 9c8b7a6d5e4f
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "9c8b7a6d5e4f"
branch_labels = None
depends_on = None


def _id_type() -> sa.BigInteger:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.add_column("dataapp_monitorsector", sa.Column("parent_id", _id_type(), nullable=True))
    op.add_column("dataapp_monitorsector", sa.Column("area_type", sa.String(length=32), nullable=True))
    op.add_column("dataapp_monitorsector", sa.Column("path", sa.String(length=255), nullable=True))
    op.add_column("dataapp_monitorsector", sa.Column("level", sa.Integer(), nullable=True))
    op.add_column("dataapp_monitorsector", sa.Column("sort_index", sa.Integer(), nullable=True))
    op.add_column("dataapp_monitorsector", sa.Column("manager_name", sa.String(length=64), nullable=True))
    op.add_column("dataapp_monitorsector", sa.Column("owner_department", sa.String(length=64), nullable=True))
    op.add_column("dataapp_monitorsector", sa.Column("location_desc", sa.String(length=255), nullable=True))
    op.add_column("dataapp_monitorsector", sa.Column("remark", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_monitorsector_parent",
        "dataapp_monitorsector",
        "dataapp_monitorsector",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_dataapp_monitorsector_parent_id"), "dataapp_monitorsector", ["parent_id"])
    op.create_index(op.f("ix_dataapp_monitorsector_area_type"), "dataapp_monitorsector", ["area_type"])
    op.create_index(op.f("ix_dataapp_monitorsector_path"), "dataapp_monitorsector", ["path"])

    op.add_column("dataapp_devicetype", sa.Column("parent_id", _id_type(), nullable=True))
    op.create_foreign_key(
        "fk_devicetype_parent",
        "dataapp_devicetype",
        "dataapp_devicetype",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_dataapp_devicetype_parent_id"), "dataapp_devicetype", ["parent_id"])

    op.add_column("dataapp_monitorequipment", sa.Column("parent_device_id", _id_type(), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("maintainer_name", sa.String(length=64), nullable=True))
    op.add_column("dataapp_monitorequipment", sa.Column("commissioning_status", sa.String(length=32), nullable=True))
    op.create_foreign_key(
        "fk_monitorequipment_parent",
        "dataapp_monitorequipment",
        "dataapp_monitorequipment",
        ["parent_device_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_dataapp_monitorequipment_parent_device_id"), "dataapp_monitorequipment", ["parent_device_id"])
    op.create_index(op.f("ix_dataapp_monitorequipment_commissioning_status"), "dataapp_monitorequipment", ["commissioning_status"])

    bind = op.get_bind()
    root_id = bind.execute(sa.text("select coalesce(max(id), 0) + 1 from dataapp_monitorsector")).scalar_one()
    bind.execute(
        sa.text(
            """
            insert into dataapp_monitorsector (
                id, code, name, parent_id, area_type, path, level, sort_index,
                description, manager_name, owner_department, location_desc, remark, area_id, is_enable
            ) values (
                :id, 'ROOT', '区域主数据', null, 'site', :path, 0, 0,
                '系统根节点', null, null, null, '系统自动创建的根区域', null, false
            )
            """
        ),
        {"id": root_id, "path": f"/{root_id}"},
    )
    bind.execute(
        sa.text(
            """
            update dataapp_monitorsector
            set parent_id = :root_id,
                area_type = coalesce(area_type, 'zone'),
                path = :root_prefix || '/' || cast(id as varchar),
                level = 1,
                sort_index = coalesce(sort_index, 0),
                remark = coalesce(remark, description)
            where id <> :root_id
            """
        ),
        {"root_id": root_id, "root_prefix": f"/{root_id}"},
    )
    bind.execute(
        sa.text(
            """
            update dataapp_devicetype child
            set parent_id = parent.id
            from dataapp_devicetype parent
            where child.parent_code is not null
              and parent.code = child.parent_code
              and child.parent_id is null
            """
        )
    )
    bind.execute(
        sa.text(
            """
            update dataapp_monitorequipment
            set commissioning_status = coalesce(commissioning_status, running_status, 'active')
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_dataapp_monitorequipment_commissioning_status"), table_name="dataapp_monitorequipment")
    op.drop_index(op.f("ix_dataapp_monitorequipment_parent_device_id"), table_name="dataapp_monitorequipment")
    op.drop_constraint(
        "fk_monitorequipment_parent",
        "dataapp_monitorequipment",
        type_="foreignkey",
    )
    op.drop_column("dataapp_monitorequipment", "commissioning_status")
    op.drop_column("dataapp_monitorequipment", "maintainer_name")
    op.drop_column("dataapp_monitorequipment", "parent_device_id")

    op.drop_index(op.f("ix_dataapp_devicetype_parent_id"), table_name="dataapp_devicetype")
    op.drop_constraint("fk_devicetype_parent", "dataapp_devicetype", type_="foreignkey")
    op.drop_column("dataapp_devicetype", "parent_id")

    op.execute(sa.text("delete from dataapp_monitorsector where code = 'ROOT'"))
    op.drop_index(op.f("ix_dataapp_monitorsector_path"), table_name="dataapp_monitorsector")
    op.drop_index(op.f("ix_dataapp_monitorsector_area_type"), table_name="dataapp_monitorsector")
    op.drop_index(op.f("ix_dataapp_monitorsector_parent_id"), table_name="dataapp_monitorsector")
    op.drop_constraint(
        "fk_monitorsector_parent",
        "dataapp_monitorsector",
        type_="foreignkey",
    )
    op.drop_column("dataapp_monitorsector", "remark")
    op.drop_column("dataapp_monitorsector", "location_desc")
    op.drop_column("dataapp_monitorsector", "owner_department")
    op.drop_column("dataapp_monitorsector", "manager_name")
    op.drop_column("dataapp_monitorsector", "sort_index")
    op.drop_column("dataapp_monitorsector", "level")
    op.drop_column("dataapp_monitorsector", "path")
    op.drop_column("dataapp_monitorsector", "area_type")
    op.drop_column("dataapp_monitorsector", "parent_id")
