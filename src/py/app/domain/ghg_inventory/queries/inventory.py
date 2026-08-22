"""Read models for the canonical organization GHG inventory."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.domain.carbon.models import MonitorSector
from app.domain.ghg_inventory.domain.activity_fields import CATEGORY_ACTIVITY_FIELDS
from app.domain.ghg_inventory.domain.catalog import CATEGORY_BY_CODE
from app.domain.ghg_inventory.models import (
    GhgActivityAllocation,
    GhgActivityRecord,
    GhgCalculationMethodDefinition,
    GhgCalculationResult,
    GhgCalculationRun,
    GhgEvidenceLink,
    GhgImportBatch,
    GhgParameterAssignment,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement


class GhgInventoryQueryService:
    """Return business-facing projections without exposing storage identifiers."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def activities(
        self,
        *,
        inventory_code: str | None,
        category_code: str | None,
        quality_status: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        filters: list[ColumnElement[bool]] = []
        if inventory_code:
            filters.append(GhgActivityRecord.inventory_code == inventory_code)
        if category_code:
            filters.append(GhgActivityRecord.iso_category_code == category_code)
        if quality_status:
            filters.append(GhgActivityRecord.quality_status == quality_status)
        total = await self.session.scalar(select(func.count()).select_from(GhgActivityRecord).where(*filters)) or 0
        rows = list(
            (
                await self.session.execute(
                    select(GhgActivityRecord)
                    .where(*filters)
                    .order_by(GhgActivityRecord.period_start.desc(), GhgActivityRecord.record_code)
                    .limit(limit)
                    .offset(offset)
                )
            ).scalars()
        )
        activity_ids = [row.id for row in rows]
        allocation_rows = (
            list(
                (
                    await self.session.scalars(
                        select(GhgActivityAllocation).where(GhgActivityAllocation.activity_id.in_(activity_ids))
                    )
                ).all()
            )
            if activity_ids
            else []
        )
        allocations_by_activity: dict[int, list[GhgActivityAllocation]] = {}
        for allocation in allocation_rows:
            allocations_by_activity.setdefault(allocation.activity_id, []).append(allocation)
        return {
            "items": [
                {
                    "recordCode": row.record_code,
                    "inventoryCode": row.inventory_code,
                    "organizationCode": row.organization_code,
                    "facilityCode": row.facility_code,
                    "sourceCode": row.source_code,
                    "activityCode": row.activity_code,
                    "activityName": row.activity_name,
                    "periodStart": row.period_start.isoformat(),
                    "periodEnd": row.period_end.isoformat(),
                    "isoCategoryCode": row.iso_category_code,
                    "ghgScope": row.ghg_scope,
                    "scope3Category": row.scope3_category,
                    "activityAmount": str(row.activity_amount),
                    "activityUnit": row.activity_unit,
                    "dataSourceType": row.data_source_type,
                    "qualityStatus": row.quality_status,
                    "status": row.status,
                    "parameterSetCode": row.parameter_set_code,
                    "organizationBoundaryId": row.organization_boundary_id,
                    "allocationStatus": "complete" if allocations_by_activity.get(row.id) else "unallocated",
                    "allocationCount": len(allocations_by_activity.get(row.id, [])),
                    "allocatedAreaNames": sorted(
                        {item.area_name_snapshot for item in allocations_by_activity.get(row.id, [])}
                    ),
                    "allocatedEquipmentNames": sorted(
                        {
                            item.equipment_name_snapshot
                            for item in allocations_by_activity.get(row.id, [])
                            if item.equipment_name_snapshot
                        }
                    ),
                    "activityDetails": self.activity_details(row),
                }
                for row in rows
            ],
            "total": int(total),
        }

    @staticmethod
    def activity_details(row: GhgActivityRecord) -> dict[str, Any]:
        """Return only the business fields defined for the activity category."""
        category = CATEGORY_BY_CODE[row.iso_category_code]
        field_codes = {field.code for field in CATEGORY_ACTIVITY_FIELDS.get(category.package_code, ())}
        return {code: row.source_payload.get(code) for code in field_codes if row.source_payload.get(code) is not None}

    async def activity_allocations(self, *, inventory_code: str, record_code: str) -> dict[str, Any]:
        activity = await self.session.scalar(
            select(GhgActivityRecord).where(
                GhgActivityRecord.inventory_code == inventory_code,
                GhgActivityRecord.record_code == record_code,
            )
        )
        if activity is None:
            msg = "温室气体活动记录不存在"
            raise ValueError(msg)
        rows = list(
            (
                await self.session.scalars(
                    select(GhgActivityAllocation)
                    .where(GhgActivityAllocation.activity_id == activity.id)
                    .order_by(GhgActivityAllocation.allocation_code)
                )
            ).all()
        )
        return {"items": [self.allocation_payload(row, activity.record_code) for row in rows], "total": len(rows)}

    @staticmethod
    def allocation_payload(row: GhgActivityAllocation, record_code: str) -> dict[str, Any]:
        return {
            "allocationCode": row.allocation_code,
            "recordCode": record_code,
            "areaId": row.area_id,
            "areaCode": row.area_code_snapshot,
            "areaName": row.area_name_snapshot,
            "areaPath": row.area_path_snapshot,
            "equipmentId": row.equipment_id,
            "equipmentCode": row.equipment_code_snapshot,
            "equipmentName": row.equipment_name_snapshot,
            "measurementBoundaryId": row.measurement_boundary_id,
            "allocationRole": row.allocation_role,
            "allocationRatio": str(row.allocation_ratio),
            "externalFacilityCode": row.external_facility_code,
            "externalFacilityName": row.external_facility_name,
            "sourceKind": row.source_kind,
        }

    async def area_summary(self, *, inventory_code: str, run_code: str | None) -> dict[str, Any]:
        if run_code:
            run = await self.session.scalar(
                select(GhgCalculationRun).where(
                    GhgCalculationRun.inventory_code == inventory_code,
                    GhgCalculationRun.run_code == run_code,
                )
            )
        else:
            run = await self.session.scalar(
                select(GhgCalculationRun)
                .where(
                    GhgCalculationRun.inventory_code == inventory_code,
                    GhgCalculationRun.status == "completed",
                )
                .order_by(GhgCalculationRun.completed_at.desc(), GhgCalculationRun.id.desc())
                .limit(1)
            )
        areas = list(
            (await self.session.scalars(select(MonitorSector).order_by(MonitorSector.level, MonitorSector.code))).all()
        )
        direct: dict[int, Decimal] = {area.id: Decimal(0) for area in areas}
        activity_ids: dict[int, set[int]] = {area.id: set() for area in areas}
        equipment_ids: dict[int, set[int]] = {area.id: set() for area in areas}
        total = Decimal(str(run.total_co2e_kg or 0)) if run is not None else Decimal(0)
        allocated = Decimal(0)
        if run is not None:
            result_rows = (
                await self.session.execute(
                    select(GhgCalculationResult, GhgActivityAllocation)
                    .join(GhgActivityAllocation, GhgActivityAllocation.activity_id == GhgCalculationResult.activity_id)
                    .where(GhgCalculationResult.run_id == run.id)
                )
            ).all()
            for result, allocation in result_rows:
                amount = Decimal(str(result.co2e_kg)) * Decimal(str(allocation.allocation_ratio))
                direct[allocation.area_id] = direct.get(allocation.area_id, Decimal(0)) + amount
                allocated += amount
                activity_ids.setdefault(allocation.area_id, set()).add(allocation.activity_id)
                if allocation.equipment_id is not None:
                    equipment_ids.setdefault(allocation.area_id, set()).add(allocation.equipment_id)
        by_id = {area.id: area for area in areas}
        rolled = dict(direct)
        for area in sorted(areas, key=lambda item: item.level or 0, reverse=True):
            if area.parent_id in by_id:
                rolled[area.parent_id] = rolled.get(area.parent_id, Decimal(0)) + rolled.get(area.id, Decimal(0))
                activity_ids.setdefault(area.parent_id, set()).update(activity_ids.get(area.id, set()))
                equipment_ids.setdefault(area.parent_id, set()).update(equipment_ids.get(area.id, set()))
        unallocated = max(total - allocated, Decimal(0))
        coverage = Decimal(100) if total == 0 and allocated == 0 else (allocated / total * 100 if total else Decimal(0))
        return {
            "inventoryCode": inventory_code,
            "runCode": run.run_code if run else None,
            "totalCo2eKg": str(total),
            "allocatedCo2eKg": str(allocated),
            "unallocatedCo2eKg": str(unallocated),
            "coveragePct": str(coverage.quantize(Decimal("0.01"))),
            "items": [
                {
                    "areaId": area.id,
                    "areaCode": area.code,
                    "areaName": area.name or area.code,
                    "parentId": area.parent_id,
                    "level": area.level or 0,
                    "directCo2eKg": str(direct.get(area.id, Decimal(0))),
                    "rolledUpCo2eKg": str(rolled.get(area.id, Decimal(0))),
                    "activityCount": len(activity_ids.get(area.id, set())),
                    "equipmentCount": len(equipment_ids.get(area.id, set())),
                }
                for area in areas
            ],
        }

    async def import_batches(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = list(
            (
                await self.session.execute(
                    select(GhgImportBatch).order_by(GhgImportBatch.created_at.desc()).limit(limit)
                )
            ).scalars()
        )
        return [self.import_batch_payload(row) for row in rows]

    @staticmethod
    def import_batch_payload(batch: GhgImportBatch) -> dict[str, Any]:
        return {
            "batchCode": batch.batch_code,
            "inventoryCode": batch.inventory_code,
            "organizationCode": batch.organization_code,
            "facilityCode": batch.facility_code,
            "isoCategoryCode": batch.iso_category_code,
            "reportingProfileCode": batch.reporting_profile_code,
            "methodCode": batch.method_code,
            "templateVersion": batch.template_version,
            "fileName": batch.file_name,
            "status": batch.status,
            "rowCount": batch.row_count,
            "validCount": batch.valid_count,
            "warningCount": batch.warning_count,
            "errorCount": batch.error_count,
            "missingEvidenceCount": batch.missing_evidence_count,
            "preview": batch.preview_snapshot,
            "createdAt": batch.created_at.isoformat(),
            "committedAt": batch.committed_at.isoformat() if batch.committed_at else None,
        }

    async def calculation_run(self, run_code: str) -> dict[str, Any]:
        run = await self.session.scalar(select(GhgCalculationRun).where(GhgCalculationRun.run_code == run_code))
        if run is None:
            msg = "核算运行不存在"
            raise ValueError(msg)
        results = list(
            (
                await self.session.execute(
                    select(GhgCalculationResult, GhgActivityRecord, GhgCalculationMethodDefinition)
                    .join(GhgActivityRecord, GhgActivityRecord.id == GhgCalculationResult.activity_id)
                    .join(
                        GhgCalculationMethodDefinition,
                        GhgCalculationMethodDefinition.id == GhgCalculationResult.method_id,
                    )
                    .where(GhgCalculationResult.run_id == run.id)
                    .order_by(GhgActivityRecord.record_code)
                )
            ).all()
        )
        assignments = list(
            (
                await self.session.execute(
                    select(GhgParameterAssignment).where(GhgParameterAssignment.run_id == run.id)
                )
            ).scalars()
        )
        evidence_rows = (
            await self.session.execute(
                select(GhgEvidenceLink.record_code, func.count(GhgEvidenceLink.id))
                .where(GhgEvidenceLink.record_type == "activity")
                .group_by(GhgEvidenceLink.record_code)
            )
        ).tuples()
        evidence_counts: dict[str, int] = {record_code: int(count) for record_code, count in evidence_rows.all()}
        return {
            "runCode": run.run_code,
            "inventoryCode": run.inventory_code,
            "status": run.status,
            "totalCo2eKg": str(run.total_co2e_kg or 0),
            "inputSnapshot": run.input_snapshot,
            "results": [
                {
                    "recordCode": activity.record_code,
                    "activityName": activity.activity_name,
                    "isoCategoryCode": result.iso_category_code,
                    "ghgScope": result.ghg_scope,
                    "methodCode": method.code,
                    "methodName": method.name,
                    "gasCode": result.gas_code,
                    "gasMassKg": str(result.gas_mass_kg),
                    "co2eKg": str(result.co2e_kg),
                    "scope2Method": result.scope2_method,
                    "qualityStatus": result.quality_status,
                    "evidenceCount": int(evidence_counts.get(activity.record_code, 0)),
                    "formulaSnapshot": result.formula_snapshot,
                }
                for result, activity, method in results
            ],
            "assignments": [
                {
                    "recordCode": next(
                        (activity.record_code for _, activity, _ in results if activity.id == assignment.activity_id),
                        "",
                    ),
                    "parameterCode": assignment.parameter_code,
                    "parameterRole": assignment.parameter_role,
                    "value": str(assignment.value),
                    "unit": assignment.unit,
                    "sourceMode": assignment.source_mode,
                    "sourceName": assignment.source_name,
                    "sourceVersion": assignment.source_version,
                    "standardCode": assignment.standard_code,
                    "clauseReference": assignment.clause_reference,
                    "selectionRule": assignment.selection_rule,
                }
                for assignment in assignments
            ],
        }
