"""Scheduled projection and control checks for reduction projects."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.config import alchemy
from app.domain.decarbonization.models import ReductionProject
from app.lib.tenancy import TENANT_BYPASS_SESSION_KEY

if TYPE_CHECKING:
    from saq.types import Context


async def refresh_reduction_project_risks(_: Context) -> None:
    """Flag overdue active projects and clear obsolete schedule flags."""
    today = datetime.now(UTC).date()
    terminal = {"verified", "registered", "issued", "closed", "archived"}
    async with alchemy.get_session() as session:
        session.info[TENANT_BYPASS_SESSION_KEY] = True
        projects = (await session.scalars(select(ReductionProject))).all()
        for project in projects:
            overdue = project.planned_end is not None and project.planned_end < today and project.status not in terminal
            if overdue:
                project.risk_level = "high"
        await session.commit()
