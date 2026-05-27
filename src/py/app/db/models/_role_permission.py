from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from advanced_alchemy.base import UUIDv7AuditBase
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.db.models._permission import Permission
    from app.db.models._role import Role


class RolePermission(UUIDv7AuditBase):
    """Links a role to a permission."""

    __tablename__ = "role_permission"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission_role_permission"),
        {"comment": "Maps roles to granted permission codes"},
    )

    role_id: Mapped[UUID] = mapped_column(ForeignKey("role.id", ondelete="cascade"), nullable=False, index=True)
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("permission.id", ondelete="cascade"), nullable=False, index=True
    )

    role: Mapped[Role] = relationship(back_populates="permission_links", innerjoin=True, uselist=False, lazy="joined")
    permission: Mapped[Permission] = relationship(
        back_populates="role_links", innerjoin=True, uselist=False, lazy="joined"
    )
