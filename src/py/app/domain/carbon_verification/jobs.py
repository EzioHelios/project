"""SAQ jobs for carbon-verification report exports."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.config import alchemy
from app.db import models as m
from app.domain.carbon_verification.usecases.export import CarbonVerificationExportUseCase
from app.lib.tenancy import TENANT_ID_SESSION_KEY

if TYPE_CHECKING:
    from saq.types import Context


async def run_carbon_verification_export(_: Context, *, job_id: int, team_id: str) -> None:
    """Render one tenant-scoped report export outside the request process."""
    async with alchemy.get_session() as session:
        session.info[TENANT_ID_SESSION_KEY] = UUID(team_id)
        try:
            await CarbonVerificationExportUseCase(session).render_export_job(job_id)
        except Exception as exc:
            await session.rollback()
            job = await session.get(m.CarbonVerificationExportJob, job_id)
            if job is None:
                raise
            job.status = "failed"
            job.error_message = str(exc)[:4000]
            job.completed_at = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
            await session.commit()
            raise
