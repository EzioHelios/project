"""Canonical organization GHG inventory and import workbench API."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
from litestar import Controller, get, post, put
from litestar.exceptions import ClientException
from litestar.response import Response
from sqlalchemy import select

from app.domain.accounts.guards import requires_permission
from app.domain.carbon.models import MonitorEquipment, MonitorSector, ReportingOrganization, ReportingPeriod
from app.domain.ghg_inventory.domain.catalog import (
    CATEGORIES,
    METHODS,
    REPORTING_PROFILES,
    category_payload,
    method_payload,
)
from app.domain.ghg_inventory.infrastructure.workbook import TEMPLATE_VERSION, build_template_bytes
from app.domain.ghg_inventory.queries.analytics import GhgAnalyticsQueryService
from app.domain.ghg_inventory.queries.inventory import GhgInventoryQueryService
from app.domain.ghg_inventory.schemas import (
    GhgActivityAllocationListResponse,
    GhgActivityListResponse,
    GhgAreaSummaryResponse,
    GhgCalculationRunListResponse,
    GhgCalculationRunRequest,
    GhgCalculationRunResponse,
    GhgCatalogResponse,
    GhgImportBatchListResponse,
    GhgImportBatchResponse,
    ReplaceActivityAllocationsRequest,
    WorkbookCommitRequest,
    WorkbookPreviewRequest,
)
from app.domain.ghg_inventory.usecases.allocations import ReplaceActivityAllocations
from app.domain.ghg_inventory.usecases.calculation import RunInventoryCalculation
from app.domain.ghg_inventory.usecases.import_workbook import CommitCategoryWorkbook, PreviewCategoryWorkbook
from app.domain.metering.models import MeasurementBoundary

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class GhgInventoryController(Controller):
    """Single write path for standards-aligned organization inventory data."""

    path = "/api/ghg-inventory"
    tags = ["GHG Inventory"]

    @get("/catalog", operation_id="GhgInventoryGetCatalog", guards=[requires_permission("carbon.inventory.view")])
    async def catalog(self, db_session: AsyncSession) -> GhgCatalogResponse:
        periods = list(
            (
                await db_session.execute(
                    select(ReportingPeriod).order_by(ReportingPeriod.period_start.desc()).limit(100)
                )
            ).scalars()
        )
        organizations = list(
            (
                await db_session.execute(select(ReportingOrganization).order_by(ReportingOrganization.name).limit(100))
            ).scalars()
        )
        areas = list(
            (await db_session.scalars(select(MonitorSector).order_by(MonitorSector.level, MonitorSector.code))).all()
        )
        equipment = list(
            (
                await db_session.scalars(
                    select(MonitorEquipment).order_by(MonitorEquipment.sector_id, MonitorEquipment.code)
                )
            ).all()
        )
        measurement_boundaries = list(
            (await db_session.scalars(select(MeasurementBoundary).order_by(MeasurementBoundary.code))).all()
        )
        area_by_id = {row.id: row for row in areas}
        return msgspec.convert(
            {
                "templateVersion": TEMPLATE_VERSION,
                "categories": [category_payload(item) for item in CATEGORIES],
                "methods": [method_payload(item) for item in METHODS],
                "reportingProfiles": list(REPORTING_PROFILES),
                "periods": [
                    {
                        "id": row.id,
                        "code": row.code,
                        "name": row.name,
                        "reportingOrgId": row.reporting_org_id,
                        "organizationCode": row.organization.code,
                        "periodStart": row.period_start.isoformat(),
                        "periodEnd": row.period_end.isoformat(),
                        "status": row.status,
                    }
                    for row in periods
                ],
                "organizations": [
                    {"id": row.id, "code": row.code, "name": row.name, "organizationType": row.organization_type}
                    for row in organizations
                ],
                "areas": [
                    {
                        "id": row.id,
                        "code": row.code,
                        "name": row.name or row.code,
                        "parentId": row.parent_id,
                        "level": row.level or 0,
                    }
                    for row in areas
                ],
                "equipment": [
                    {
                        "id": row.id,
                        "code": row.code,
                        "name": row.name or row.code,
                        "areaId": row.sector_id,
                        "areaCode": area_by_id[row.sector_id].code if row.sector_id in area_by_id else None,
                        "deviceType": row.device_type.name if row.device_type else None,
                    }
                    for row in equipment
                ],
                "measurementBoundaries": [
                    {
                        "id": row.id,
                        "code": row.code,
                        "name": row.name,
                        "areaId": row.sector_id,
                        "meterEquipmentId": row.meter_equipment_id,
                    }
                    for row in measurement_boundaries
                ],
            },
            type=GhgCatalogResponse,
        )

    @get(
        "/activities", operation_id="GhgInventoryListActivities", guards=[requires_permission("carbon.inventory.view")]
    )
    async def activities(
        self,
        db_session: AsyncSession,
        inventory_code: str | None = None,
        category_code: str | None = None,
        quality_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> GhgActivityListResponse:
        payload = await GhgInventoryQueryService(db_session).activities(
            inventory_code=inventory_code,
            category_code=category_code,
            quality_status=quality_status,
            limit=min(max(limit, 1), 500),
            offset=max(offset, 0),
        )
        return msgspec.convert(payload, type=GhgActivityListResponse)

    @get(
        "/import/template",
        operation_id="GhgInventoryDownloadTemplate",
        guards=[requires_permission("carbon.inventory.import")],
    )
    async def template(
        self,
        db_session: AsyncSession,
        inventory_code: str,
        organization_code: str,
        facility_code: str,
        iso_category_code: str,
        reporting_profile_code: str,
        method_code: str,
    ) -> Response[bytes]:
        try:
            areas = list((await db_session.scalars(select(MonitorSector).order_by(MonitorSector.code))).all())
            equipment = list((await db_session.scalars(select(MonitorEquipment).order_by(MonitorEquipment.code))).all())
            measurement_boundaries = list(
                (await db_session.scalars(select(MeasurementBoundary).order_by(MeasurementBoundary.code))).all()
            )
            content = build_template_bytes(
                {
                    "inventory_code": inventory_code,
                    "organization_code": organization_code,
                    "facility_code": facility_code,
                    "iso_category_code": iso_category_code,
                    "reporting_profile_code": reporting_profile_code,
                    "method_code": method_code,
                    "area_codes": [row.code for row in areas],
                    "equipment_codes": [row.code for row in equipment],
                    "measurement_boundary_codes": [row.code for row in measurement_boundaries],
                }
            )
        except (KeyError, ValueError) as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        file_name = f"ghg-{iso_category_code.replace('.', '-')}-{TEMPLATE_VERSION}.xlsx"
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
        )

    @get(
        "/activities/{record_code:str}/allocations",
        operation_id="GhgInventoryGetActivityAllocations",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def activity_allocations(
        self,
        db_session: AsyncSession,
        record_code: str,
        inventory_code: str,
    ) -> GhgActivityAllocationListResponse:
        try:
            payload = await GhgInventoryQueryService(db_session).activity_allocations(
                inventory_code=inventory_code,
                record_code=record_code,
            )
        except ValueError as exc:
            raise ClientException(status_code=404, detail=str(exc)) from exc
        return msgspec.convert(payload, type=GhgActivityAllocationListResponse)

    @put(
        "/activities/{record_code:str}/allocations",
        operation_id="GhgInventoryReplaceActivityAllocations",
        guards=[requires_permission("carbon.inventory.import")],
    )
    async def replace_activity_allocations(
        self,
        db_session: AsyncSession,
        record_code: str,
        data: ReplaceActivityAllocationsRequest,
    ) -> GhgActivityAllocationListResponse:
        try:
            await ReplaceActivityAllocations(db_session).execute(
                inventory_code=data.inventory_code,
                record_code=record_code,
                allocations=[item.to_dict() for item in data.allocations],
            )
            payload = await GhgInventoryQueryService(db_session).activity_allocations(
                inventory_code=data.inventory_code,
                record_code=record_code,
            )
        except ValueError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        return msgspec.convert(payload, type=GhgActivityAllocationListResponse)

    @get(
        "/area-summary",
        operation_id="GhgInventoryGetAreaSummary",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def area_summary(
        self,
        db_session: AsyncSession,
        inventory_code: str,
        run_code: str | None = None,
    ) -> GhgAreaSummaryResponse:
        return msgspec.convert(
            await GhgInventoryQueryService(db_session).area_summary(
                inventory_code=inventory_code,
                run_code=run_code,
            ),
            type=GhgAreaSummaryResponse,
        )

    @post(
        "/import/preview",
        operation_id="GhgInventoryPreviewWorkbook",
        guards=[requires_permission("carbon.inventory.import")],
    )
    async def preview(self, db_session: AsyncSession, data: WorkbookPreviewRequest) -> GhgImportBatchResponse:
        try:
            batch = await PreviewCategoryWorkbook(db_session).execute(data.to_dict())
        except ValueError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        return msgspec.convert(GhgInventoryQueryService.import_batch_payload(batch), type=GhgImportBatchResponse)

    @post(
        "/import/commit",
        operation_id="GhgInventoryCommitWorkbook",
        guards=[requires_permission("carbon.inventory.import")],
    )
    async def commit(self, db_session: AsyncSession, data: WorkbookCommitRequest) -> GhgImportBatchResponse:
        try:
            batch = await CommitCategoryWorkbook(db_session).execute(
                data.batch_code,
                acknowledge_warnings=data.acknowledge_warnings,
                warning_acknowledgement=data.warning_acknowledgement,
            )
        except ValueError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        return msgspec.convert(GhgInventoryQueryService.import_batch_payload(batch), type=GhgImportBatchResponse)

    @get(
        "/import/batches",
        operation_id="GhgInventoryListImportBatches",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def import_batches(self, db_session: AsyncSession, limit: int = 50) -> GhgImportBatchListResponse:
        rows = await GhgInventoryQueryService(db_session).import_batches(limit=min(max(limit, 1), 100))
        return msgspec.convert({"items": rows, "total": len(rows)}, type=GhgImportBatchListResponse)

    @get(
        "/calculation-runs",
        operation_id="GhgInventoryListCalculationRuns",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def calculation_runs(
        self,
        db_session: AsyncSession,
        inventory_code: str | None = None,
        reporting_org_id: int | None = None,
        reporting_period_id: int | None = None,
        organization_boundary_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> GhgCalculationRunListResponse:
        payload = await GhgAnalyticsQueryService(db_session).calculation_runs(
            inventory_code=inventory_code,
            reporting_org_id=reporting_org_id,
            reporting_period_id=reporting_period_id,
            organization_boundary_id=organization_boundary_id,
            status=status,
            limit=min(max(limit, 1), 200),
            offset=max(offset, 0),
        )
        return msgspec.convert(payload, type=GhgCalculationRunListResponse)

    @post(
        "/calculation-runs",
        operation_id="GhgInventoryRunCalculation",
        guards=[requires_permission("carbon.inventory.calculate")],
    )
    async def run_calculation(
        self, db_session: AsyncSession, data: GhgCalculationRunRequest
    ) -> GhgCalculationRunResponse:
        try:
            run = await RunInventoryCalculation(db_session).execute(
                inventory_code=data.inventory_code,
                reporting_profile_code=data.reporting_profile_code,
                reporting_period_id=data.reporting_period_id,
                reporting_org_id=data.reporting_org_id,
                organization_boundary_id=data.organization_boundary_id,
                default_scope2_method=data.default_scope2_method,
            )
        except ValueError as exc:
            raise ClientException(status_code=422, detail=str(exc)) from exc
        return msgspec.convert(
            await GhgInventoryQueryService(db_session).calculation_run(run.run_code),
            type=GhgCalculationRunResponse,
        )

    @get(
        "/calculation-runs/{run_code:str}",
        operation_id="GhgInventoryGetCalculationRun",
        guards=[requires_permission("carbon.inventory.view")],
    )
    async def calculation_run(self, db_session: AsyncSession, run_code: str) -> GhgCalculationRunResponse:
        try:
            return msgspec.convert(
                await GhgInventoryQueryService(db_session).calculation_run(run_code),
                type=GhgCalculationRunResponse,
            )
        except ValueError as exc:
            raise ClientException(status_code=404, detail=str(exc)) from exc
