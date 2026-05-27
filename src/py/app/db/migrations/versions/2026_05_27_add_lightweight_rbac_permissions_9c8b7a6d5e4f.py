"""add lightweight rbac permissions

Revision ID: 9c8b7a6d5e4f
Revises: b1c2d3e4f5a6
Create Date: 2026-05-27
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "9c8b7a6d5e4f"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "permission",
        sa.Column("id", sa.GUID(length=16), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.Column("sa_orm_sentinel", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTimeUTC(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTimeUTC(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permission")),
        sa.UniqueConstraint("code", name=op.f("uq_permission_code")),
        comment="Permission codes used by lightweight RBAC",
    )
    with op.batch_alter_table("permission", schema=None) as batch_op:
        batch_op.create_index("ix_permission_code_unique", ["code"], unique=True)
        batch_op.create_index(batch_op.f("ix_permission_module"), ["module"], unique=False)

    op.create_table(
        "role_permission",
        sa.Column("id", sa.GUID(length=16), nullable=False),
        sa.Column("role_id", sa.GUID(length=16), nullable=False),
        sa.Column("permission_id", sa.GUID(length=16), nullable=False),
        sa.Column("sa_orm_sentinel", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTimeUTC(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTimeUTC(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permission.id"], name=op.f("fk_role_permission_permission_id_permission"), ondelete="cascade"),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], name=op.f("fk_role_permission_role_id_role"), ondelete="cascade"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_permission")),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission_role_permission"),
        comment="Maps roles to granted permission codes",
    )
    with op.batch_alter_table("role_permission", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_role_permission_permission_id"), ["permission_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_role_permission_role_id"), ["role_id"], unique=False)

    conn = op.get_bind()

    permission_rows = [
        ("carbon.record.create", "Create carbon record", "Create carbon records", "carbon"),
        ("carbon.record.update", "Update carbon record", "Update carbon records", "carbon"),
        ("carbon.record.submit", "Submit carbon record", "Submit carbon records for review", "carbon"),
        ("carbon.record.delete", "Delete carbon record", "Delete carbon records", "carbon"),
        ("carbon.review.approve", "Approve carbon record", "Approve reviewed records", "carbon"),
        ("carbon.review.reject", "Reject carbon record", "Reject reviewed records", "carbon"),
        ("carbon.config.manage", "Manage carbon configuration", "Manage carbon data and configuration", "carbon"),
        ("carbon.alarm.handle", "Handle alarms", "Handle carbon alarm events", "carbon"),
        ("carbon.audit.view", "View carbon audit logs", "View carbon audit trails", "carbon"),
        ("auth.role.manage", "Manage roles", "Create and update roles and permissions", "auth"),
        ("auth.user.manage", "Manage users", "Create and update user accounts", "auth"),
        ("admin.audit.view", "View admin audit logs", "View system audit logs", "admin"),
        ("admin.team.manage", "Manage teams", "Create and update teams", "admin"),
    ]
    insert_permission_sql = sa.text(
        """
        insert into permission (
            id, code, name, description, module, sa_orm_sentinel, created_at, updated_at
        ) values (
            :id, :code, :name, :description, :module, null, now(), now()
        )
        """
    )
    for code, name, description, module in permission_rows:
        permission_id = uuid4()
        conn.execute(
            insert_permission_sql,
            {
                "id": permission_id,
                "code": code,
                "name": name,
                "description": description,
                "module": module,
            },
        )

    insert_role_permission_sql = sa.text(
        """
        insert into role_permission (
            id, role_id, permission_id, sa_orm_sentinel, created_at, updated_at
        )
        select :id, role.id, permission.id, null, now(), now()
        from role
        join permission on permission.code = :permission_code
        where role.name = :role_name
        """
    )
    default_role_permissions = [
        ("User", "carbon.record.create"),
        ("User", "carbon.record.update"),
        ("User", "carbon.record.submit"),
    ]
    for role_name, permission_code in default_role_permissions:
        conn.execute(
            insert_role_permission_sql,
            {
                "id": uuid4(),
                "role_name": role_name,
                "permission_code": permission_code,
            },
        )


def downgrade() -> None:
    with op.batch_alter_table("role_permission", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_role_permission_role_id"))
        batch_op.drop_index(batch_op.f("ix_role_permission_permission_id"))
    op.drop_table("role_permission")

    with op.batch_alter_table("permission", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_permission_module"))
        batch_op.drop_index("ix_permission_code_unique")
    op.drop_table("permission")
