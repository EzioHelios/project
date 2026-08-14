"""Forecast, optimization, and shadow-dispatch command API."""

from __future__ import annotations

# ruff: noqa: TC001 - Litestar resolves request DTO annotations at runtime.
from typing import TYPE_CHECKING, Any

from litestar import Controller, get, post
from litestar.exceptions import ClientException
from litestar.response import Response

from app.domain.accounts.guards import requires_permission
from app.domain.microgrid.domain.exceptions import MicrogridDomainError
from app.domain.microgrid.queries import MicrogridQueryService
from app.domain.microgrid.schemas import CreateDispatchBatchRequest
from app.domain.microgrid.usecases import CreateDispatchBatch

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MicrogridOperationsController(Controller):
    """Launch auditable long-running microgrid workflows."""

    path = "/api/microgrid"
    tags = ["Microgrid"]

    @get(
        "/dispatch-batches",
        operation_id="MicrogridListDispatchBatches",
        guards=[requires_permission("microgrid.view")],
    )
    async def dispatch_batches(
        self,
        db_session: AsyncSession,
        site_id: int | None = None,
        status: str | None = None,
        scenario_id: int | None = None,
    ) -> dict[str, Any]:
        return {
            "items": await MicrogridQueryService(db_session).dispatch_batches(
                site_id=site_id,
                status=status,
                scenario_id=scenario_id,
            )
        }

    @post(
        "/dispatch-batches",
        operation_id="MicrogridCreateDispatchBatch",
        status_code=202,
        guards=[requires_permission("microgrid.dispatch.simulate")],
    )
    async def create_dispatch_batch(
        self, db_session: AsyncSession, data: CreateDispatchBatchRequest
    ) -> Response[dict[str, Any]]:
        try:
            batch = await CreateDispatchBatch(db_session).execute(optimization_run_id=data.optimization_run_id)
            result = await MicrogridQueryService(db_session).dispatch_batch(batch.id)
            return Response(content=result or {"id": batch.id, "status": batch.status}, status_code=202)
        except MicrogridDomainError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
