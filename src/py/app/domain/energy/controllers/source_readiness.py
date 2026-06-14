from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get
from litestar.response import Response

from app.domain.energy.controllers._utils import ok_data
from app.domain.energy.queries.source_readiness import EnergySourceReadinessQueryService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EnergySourceReadinessController(Controller):
    tags = ["Energy"]

    @get("/api/energy/source-readiness")
    async def get_energy_source_readiness(self, db_session: AsyncSession) -> Response[dict]:
        return Response(content=ok_data(await EnergySourceReadinessQueryService(db_session).summary()))
