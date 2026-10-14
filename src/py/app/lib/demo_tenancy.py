"""Restrict synthetic business data to the two explicitly owned showcase tenants."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from litestar.exceptions import PermissionDeniedException

from app.lib.tenancy import DEFAULT_TENANT_ID, TENANT_BYPASS_SESSION_KEY, require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import Team

WOHENG_TENANT_SLUGS = frozenset({"woheng-taizhou-production-base", "woheng-huzhou-production-base"})
CUSTOMER_TENANT_IDS = frozenset({DEFAULT_TENANT_ID, UUID("00000000-0000-7000-8000-000000000002")})


def validate_demo_team(team: Team | None) -> None:
    """Fail closed even if a protected customer tenant has been renamed."""
    if team is None or team.id in CUSTOMER_TENANT_IDS or team.slug not in WOHENG_TENANT_SLUGS or not team.is_active:
        raise PermissionDeniedException(detail="Synthetic data is restricted to the Woheng showcase tenants.")


async def require_demo_tenant(session: AsyncSession) -> UUID:
    """Require explicit tenant identity and isolation before any synthetic write."""
    from app.db.models import Team

    tenant_id = require_session_tenant_id(session)
    if session.info.get(TENANT_BYPASS_SESSION_KEY):
        raise PermissionDeniedException(detail="Demo business writes must not bypass tenant isolation.")
    with session.no_autoflush:
        team = await session.get(Team, tenant_id)
    validate_demo_team(team)
    return tenant_id
