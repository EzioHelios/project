from __future__ import annotations

from typing import TYPE_CHECKING

from advanced_alchemy.base import UUIDv7AuditBase
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from sqlalchemy.sql.schema import Table

    from app.db.models._role import Role
    from app.db.models._role_permission import RolePermission


class Permission(UUIDv7AuditBase):
    """Permission code assignable to roles."""

    __tablename__ = "permission"
    __table_args__ = {"comment": "Permission codes used by lightweight RBAC"}

    code: Mapped[str] = mapped_column(String(length=120), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(length=120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(length=255), nullable=True, default=None)
    module: Mapped[str] = mapped_column(String(length=50), nullable=False, index=True)

    role_links: Mapped[list[RolePermission]] = relationship(
        back_populates="permission",
        lazy="noload",
        cascade="all, delete-orphan",
    )
    roles: Mapped[list[Role]] = relationship(
        secondary=lambda: _role_permission_table(),
        back_populates="permissions",
        viewonly=True,
        lazy="noload",
    )


def _role_permission_table() -> Table:
    from app.db.models._role_permission import RolePermission

    return RolePermission.__table__
