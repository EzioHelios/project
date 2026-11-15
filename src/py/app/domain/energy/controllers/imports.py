from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, Request, post
from litestar.response import Response

from app.domain.accounts.guards import requires_permission, requires_resource_access, requires_superuser
from app.domain.energy.controllers._utils import ok_data
from app.domain.energy.usecases.imports import EnergyDatasetImportUseCase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EnergyImportController(Controller):
    guards = [requires_resource_access("energy.consumption.view", "energy.consumption.manage")]
    tags = ["Energy"]

    @post(
        "/api/energy/imports/datasets",
        operation_id="EnergyImportDataset",
        guards=[requires_permission("energy.consumption.manage")],
    )
    async def import_energy_dataset(
        self, request: Request, db_session: AsyncSession, data: dict[str, Any]
    ) -> Response[dict[str, Any]]:
        if data.get("dataset") != "energy_interval_facts":
            requires_superuser(request, request.route_handler)
        result = await EnergyDatasetImportUseCase(db_session).import_rows(
            dataset=str(data.get("dataset") or ""),
            rows=list(data.get("rows") or []),
            source_name=data.get("source_name"),
            preview=data.get("preview") is True,
        )
        return Response(
            content=ok_data(
                {
                    "dataset": result.dataset,
                    "received_count": result.received_count,
                    "imported_count": result.imported_count,
                    "skipped_count": result.skipped_count,
                    "errors": result.errors,
                    "preview": result.preview,
                    "records": result.records,
                    "imported_ids": result.imported_ids,
                }
            )
        )
