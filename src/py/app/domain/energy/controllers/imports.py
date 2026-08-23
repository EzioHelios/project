from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar import Controller, post
from litestar.response import Response

from app.domain.accounts.guards import requires_superuser
from app.domain.energy.controllers._utils import ok_data
from app.domain.energy.usecases.imports import EnergyDatasetImportUseCase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EnergyImportController(Controller):
    tags = ["Energy"]

    @post(
        "/api/energy/imports/datasets",
        operation_id="EnergyImportDataset",
        guards=[requires_superuser],
    )
    async def import_energy_dataset(self, db_session: AsyncSession, data: dict[str, Any]) -> Response[dict[str, Any]]:
        result = await EnergyDatasetImportUseCase(db_session).import_rows(
            dataset=str(data.get("dataset") or ""),
            rows=list(data.get("rows") or []),
            source_name=data.get("source_name"),
        )
        return Response(
            content=ok_data(
                {
                    "dataset": result.dataset,
                    "received_count": result.received_count,
                    "imported_count": result.imported_count,
                    "skipped_count": result.skipped_count,
                    "errors": result.errors,
                }
            )
        )
