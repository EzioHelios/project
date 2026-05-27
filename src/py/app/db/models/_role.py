from __future__ import annotations

from typing import TYPE_CHECKING

from advanced_alchemy.base import UUIDv7AuditBase
from advanced_alchemy.mixins import SlugKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from sqlalchemy.sql.schema import Table

    from app.db.models._permission import Permission
    from app.db.models._role_permission import RolePermission
    from app.db.models._user_role import UserRole


class Role(UUIDv7AuditBase, SlugKey):
    """Role."""

    __tablename__ = "role"

    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None]
    permissions: Mapped[list[Permission]] = relationship(
        secondary=lambda: _role_permission_table(),
        back_populates="roles",
        viewonly=True,
        lazy="noload",
    )
    permission_links: Mapped[list[RolePermission]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    users: Mapped[list[UserRole]] = relationship(
        back_populates="role",
        cascade="all, delete",
        lazy="noload",
        viewonly=True,
    )


def _role_permission_table() -> Table:
    from app.db.models._role_permission import RolePermission

    return RolePermission.__table__
