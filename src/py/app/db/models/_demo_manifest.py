from __future__ import annotations

from typing import Any
from uuid import UUID

from advanced_alchemy.base import BigIntAuditBase
from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models._team import Team


class DemoManifest(BigIntAuditBase):
    """Registry of objects owned by reusable demo packages."""

    __tablename__ = "demo_manifest"
    __table_args__ = (
        UniqueConstraint("namespace", "object_type", "object_key", name="uq_demo_manifest_namespace_object"),
        Index("ix_demo_manifest_package_namespace", "package_key", "namespace", "profile"),
        Index("ix_demo_manifest_team", "team_id", "package_key", "module_key"),
    )

    namespace: Mapped[str] = mapped_column(String(64), index=True)
    profile: Mapped[str] = mapped_column(String(64), default="full", index=True)
    package_key: Mapped[str] = mapped_column(String(96), index=True)
    module_key: Mapped[str] = mapped_column(String(96), index=True)
    object_type: Mapped[str] = mapped_column(String(96), index=True)
    object_key: Mapped[str] = mapped_column(String(160), index=True)
    object_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    team_id: Mapped[UUID | None] = mapped_column(ForeignKey(Team.id, ondelete="SET NULL"), nullable=True, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
