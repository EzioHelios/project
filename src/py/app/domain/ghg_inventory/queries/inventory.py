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
    GhgEmissionSource,
    GhgEvidenceLink,
    GhgImportBatch,
    GhgParameterAssignment,
    GhgReportingProfile,
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
                self.activity_payload(row, allocations_by_activity.get(row.id, []))
                for row in rows
            ],
            "total": int(total),
        }

    async def activity(self, *, inventory_code: str, record_code: str) -> dict[str, Any]:
        row = await self.session.scalar(
            select(GhgActivityRecord).where(
                GhgActivityRecord.inventory_code == inventory_code,
                GhgActivityRecord.record_code == record_code,
            )
        )
        if row is None:
            msg = "温室气体活动记录不存在"
            raise ValueError(msg)
        allocations = list(
            (
                await self.session.scalars(
                    select(GhgActivityAllocation).where(GhgActivityAllocation.activity_id == row.id)
                )
            ).all()
        )
        return self.activity_payload(row, allocations)

    def activity_payload(self, row: GhgActivityRecord, allocations: list[GhgActivityAllocation]) -> dict[str, Any]:
        return {
            "recordCode": row.record_code,
            "inventoryCode": row.inventory_code,
            "reportingPeriodId": row.reporting_period_id,
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
            "measurementMethod": row.measurement_method,
            "qualityStatus": row.quality_status,
            "status": row.status,
            "parameterSetCode": row.parameter_set_code,
            "organizationBoundaryId": row.organization_boundary_id,
            "remarks": row.remarks,
            "sourceSystem": row.source_system,
            "sourceRecordType": row.source_record_type,
            "sourceRecordId": row.source_record_id,
            "allocationStatus": "complete" if allocations else "unallocated",
            "allocationCount": len(allocations),
            "allocatedAreaNames": sorted({item.area_name_snapshot for item in allocations}),
            "allocatedEquipmentNames": sorted(
                {item.equipment_name_snapshot for item in allocations if item.equipment_name_snapshot}
            ),
            "activityDetails": self.activity_details(row),
        }

    @staticmethod
    def activity_details(row: GhgActivityRecord) -> dict[str, Any]:
        """Return only the business fields defined for the activity category."""
        category = CATEGORY_BY_CODE[row.iso_category_code]
        field_codes = {field.code for field in CATEGORY_ACTIVITY_FIELDS.get(category.package_code, ())}
        return {code: row.source_payload.get(code) for code in field_codes if row.source_payload.get(code) is not None}

    async def emission_sources(
        self,
        *,
        inventory_code: str | None,
        category_code: str | None,
        status: str | None,
        keyword: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        filters: list[ColumnElement[bool]] = []
        if inventory_code:
            filters.append(GhgEmissionSource.inventory_code == inventory_code)
        if category_code:
            filters.append(GhgEmissionSource.iso_category_code == category_code)
        if status:
            filters.append(GhgEmissionSource.status == status)
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            filters.append(GhgEmissionSource.source_code.ilike(pattern) | GhgEmissionSource.source_name.ilike(pattern))
        total = await self.session.scalar(select(func.count()).select_from(GhgEmissionSource).where(*filters)) or 0
        rows = list(
            (
                await self.session.scalars(
                    select(GhgEmissionSource)
                    .where(*filters)
                    .order_by(GhgEmissionSource.iso_category_code, GhgEmissionSource.source_code)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        counts = await self._activity_counts_for_sources(rows)
        return {"items": [self.source_payload(row, counts.get(row.source_code, 0)) for row in rows], "total": int(total)}

    async def emission_source(self, *, inventory_code: str, source_code: str) -> dict[str, Any]:
        row = await self.session.scalar(
            select(GhgEmissionSource).where(
                GhgEmissionSource.inventory_code == inventory_code,
                GhgEmissionSource.source_code == source_code,
            )
        )
        if row is None:
            msg = "排放源不存在"
            raise ValueError(msg)
        count = await self.session.scalar(
            select(func.count()).select_from(GhgActivityRecord).where(
                GhgActivityRecord.inventory_code == inventory_code,
                GhgActivityRecord.source_code == source_code,
            )
        )
        return self.source_payload(row, int(count or 0))

    async def _activity_counts_for_sources(self, rows: list[GhgEmissionSource]) -> dict[str, int]:
        if not rows:
            return {}
        result = await self.session.execute(
            select(GhgActivityRecord.source_code, func.count())
            .where(
                GhgActivityRecord.inventory_code.in_({row.inventory_code for row in rows}),
                GhgActivityRecord.source_code.in_({row.source_code for row in rows}),
            )
            .group_by(GhgActivityRecord.source_code)
        )
        return {str(source_code): int(count) for source_code, count in result.all()}

    @staticmethod
    def source_payload(row: GhgEmissionSource, activity_count: int) -> dict[str, Any]:
        return {
            "inventoryCode": row.inventory_code,
            "organizationCode": row.organization_code,
            "facilityCode": row.facility_code,
            "sourceCode": row.source_code,
            "sourceName": row.source_name,
            "isoCategoryCode": row.iso_category_code,
            "sourceMechanism": row.source_mechanism,
            "originKind": row.origin_kind,
            "organizationBoundaryId": row.organization_boundary_id,
            "reportingPeriodId": row.reporting_period_id,
            "defaultAreaId": row.default_area_id,
            "defaultEquipmentId": row.default_equipment_id,
            "defaultMeasurementBoundaryId": row.default_measurement_boundary_id,
            "defaultAllocationRole": row.default_allocation_role,
            "externalFacilityCode": row.external_facility_code,
            "externalFacilityName": row.external_facility_name,
            "validFrom": row.valid_from.isoformat() if row.valid_from else None,
            "validTo": row.valid_to.isoformat() if row.valid_to else None,
            "sourceSystem": row.source_system,
            "sourcePayload": row.source_payload or {},
            "status": row.status,
            "activityCount": activity_count,
        }

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
            "totalCo2EKg": str(total),
            "allocatedCo2EKg": str(allocated),
            "unallocatedCo2EKg": str(unallocated),
            "coveragePct": str(coverage.quantize(Decimal("0.01"))),
            "items": [
                {
                    "areaId": area.id,
                    "areaCode": area.code,
                    "areaName": area.name or area.code,
                    "parentId": area.parent_id,
                    "level": area.level or 0,
                    "directCo2EKg": str(direct.get(area.id, Decimal(0))),
                    "rolledUpCo2EKg": str(rolled.get(area.id, Decimal(0))),
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
        profile = await self.session.get(GhgReportingProfile, run.reporting_profile_id)
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
            "totalCo2EKg": str(run.total_co2e_kg or 0),
            "reportingOrgId": run.reporting_org_id,
            "reportingPeriodId": run.reporting_period_id,
            "organizationBoundaryId": run.organization_boundary_id,
            "reportingProfileCode": profile.code if profile else "",
            "reportingProfileName": profile.name if profile else "",
            "defaultScope2Method": run.default_scope2_method,
            "inputSnapshot": run.input_snapshot,
            "summarySnapshot": run.summary_snapshot,
            "qualitySnapshot": run.quality_snapshot,
            "startedAt": run.started_at.isoformat(),
            "completedAt": run.completed_at.isoformat() if run.completed_at else None,
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
