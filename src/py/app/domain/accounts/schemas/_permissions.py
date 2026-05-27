"""Permission-related schemas."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

from app.lib.schema import CamelizedBaseStruct


class Permission(CamelizedBaseStruct):
    """Permission details."""

    id: UUID
    code: str
    name: str
    module: str
    created_at: datetime
    updated_at: datetime
    description: str | None = None


class RolePermissionsUpdate(CamelizedBaseStruct):
    """Role permission update payload."""

    permission_codes: list[str]
