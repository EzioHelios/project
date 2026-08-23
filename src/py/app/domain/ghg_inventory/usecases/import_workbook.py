"""Application use cases for previewing and committing category workbooks."""

from __future__ import annotations

# ruff: noqa: RUF001 - Chinese business messages are intentional.
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from app.domain.carbon import models as carbon_models
from app.domain.ghg_inventory.infrastructure.workbook import TEMPLATE_VERSION, decode_and_preview
from app.domain.ghg_inventory.models import (
    GhgActivityRecord,
    GhgEvidenceFile,
    GhgEvidenceLink,
    GhgImportBatch,
    GhgImportIssue,
    GhgParameterValue,
)
from app.domain.ghg_inventory.usecases.allocations import ReplaceActivityAllocations
from app.domain.metering.models import MeasurementBoundary
from app.lib.tenancy import require_session_tenant_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PreviewCategoryWorkbook:
    """Persist a tenant-scoped, auditable precheck result."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, data: dict[str, Any]) -> GhgImportBatch:
        require_session_tenant_id(self.session)
        preview, file_hash = decode_and_preview(str(data["workbook_base64"]), data)
        preview_payload = preview.payload()
        metrics = preview_payload["metrics"]
        batch = GhgImportBatch(
            batch_code=f"IMP-{uuid4().hex[:16].upper()}",
            inventory_code=str(data["inventory_code"]),
            reporting_period_id=data.get("reporting_period_id"),
            organization_code=str(data["organization_code"]),
            facility_code=str(data["facility_code"]),
            iso_category_code=str(data["iso_category_code"]),
            reporting_profile_code=str(data["reporting_profile_code"]),
            method_code=str(data["method_code"]),
            template_version=TEMPLATE_VERSION,
            file_name=str(data["file_name"]),
            file_sha256=file_hash,
            status="blocked" if metrics["errorCount"] else "previewed",
            row_count=metrics["rowCount"],
            valid_count=metrics["validCount"],
            warning_count=metrics["warningCount"],
            error_count=metrics["errorCount"],
            missing_evidence_count=metrics["missingEvidenceCount"],
            context_snapshot={key: value for key, value in data.items() if key not in {"workbook_base64"}},
            preview_snapshot=preview_payload,
        )
        self.session.add(batch)
        await self.session.flush()
        self.session.add_all(
            [
                GhgImportIssue(
                    batch_id=batch.id,
                    severity=issue.severity,
                    sheet_name=issue.sheet_name,
                    row_number=issue.row_number,
                    field_code=issue.field_code,
                    issue_code=issue.issue_code,
                    message=issue.message,
                    current_value=issue.current_value,
                    suggestion=issue.suggestion,
                )
                for issue in preview.issues
            ]
        )
        await self.session.commit()
        return batch


class CommitCategoryWorkbook:
    """Write only canonical activity, parameter, and evidence entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(  # noqa: C901, PLR0915 - transaction deliberately keeps validation and writes atomic
        self,
        batch_code: str,
        *,
        acknowledge_warnings: bool,
        warning_acknowledgement: str | None = None,
    ) -> GhgImportBatch:
        tenant_id = require_session_tenant_id(self.session)
        batch = await self.session.scalar(select(GhgImportBatch).where(GhgImportBatch.batch_code == batch_code))
        if batch is None:
            msg = "导入批次不存在"
            raise ValueError(msg)
        if batch.status == "committed":
            return batch
        if batch.error_count:
            msg = "工作簿仍有阻断错误，不能导入"
            raise ValueError(msg)
        if batch.warning_count and (not acknowledge_warnings or not (warning_acknowledgement or "").strip()):
            msg = "工作簿存在警告，填写确认原因后才能导入"
            raise ValueError(msg)

        snapshot = dict(batch.preview_snapshot or {})
        existing_records = set(
            (
                await self.session.execute(
                    select(GhgActivityRecord.record_code).where(
                        GhgActivityRecord.inventory_code == batch.inventory_code,
                        GhgActivityRecord.record_code.in_(
                            [str(row["record_code"]) for row in snapshot.get("activities", [])]
                        ),
                    )
                )
            ).scalars()
        )
        if existing_records:
            msg = f"盘查任务中已存在记录编号：{', '.join(sorted(existing_records))}"
            raise ValueError(msg)

        parameter_codes = [
            f"{batch.inventory_code}:{row['parameter_set_code']}:{row['parameter_code']}"
            for row in snapshot.get("parameters", [])
        ]
        existing_parameters = set(
            (
                await self.session.execute(
                    select(GhgParameterValue.value_code).where(GhgParameterValue.value_code.in_(parameter_codes))
                )
            ).scalars()
        )
        if existing_parameters:
            msg = f"盘查任务中已存在参数值：{', '.join(sorted(existing_parameters))}"
            raise ValueError(msg)

        link_codes = [str(row["link_code"]) for row in snapshot.get("links", [])]
        existing_links = set(
            (
                await self.session.execute(
                    select(GhgEvidenceLink.link_code).where(GhgEvidenceLink.link_code.in_(link_codes))
                )
            ).scalars()
        )
        if existing_links:
            msg = f"盘查任务中已存在证据关联：{', '.join(sorted(existing_links))}"
            raise ValueError(msg)

        evidence_by_code: dict[str, GhgEvidenceFile] = {}
        evidence_codes = [str(row["evidence_code"]) for row in snapshot.get("evidence", [])]
        existing_evidence = {
            row.evidence_code: row
            for row in (
                await self.session.execute(
                    select(GhgEvidenceFile).where(GhgEvidenceFile.evidence_code.in_(evidence_codes))
                )
            ).scalars()
        }
        for row in snapshot.get("evidence", []):
            evidence_code = str(row["evidence_code"])
            evidence_hash = str(row["sha256"]).lower()
            current = existing_evidence.get(evidence_code)
            if current is not None:
                if current.sha256.lower() != evidence_hash:
                    msg = f"证据编号 {evidence_code} 已存在，但文件哈希不一致"
                    raise ValueError(msg)
                evidence_by_code[evidence_code] = current
                continue
            evidence = GhgEvidenceFile(
                evidence_code=evidence_code,
                file_name=str(row["file_name"]),
                document_type=str(row["document_type"]),
                document_no=_text(row.get("document_no")),
                issuer=_text(row.get("issuer")),
                period_start=_date(row.get("period_start")),
                period_end=_date(row.get("period_end")),
                storage_key=str(row["storage_key"]),
                sha256=evidence_hash,
                confidentiality=str(row["confidentiality"]),
                verification_status=str(row["verification_status"]),
                valid_from=_date(row.get("valid_from")),
                valid_to=_date(row.get("valid_to")),
            )
            self.session.add(evidence)
            evidence_by_code[evidence.evidence_code] = evidence
        await self.session.flush()

        for row in snapshot.get("parameters", []):
            parameter_set = str(row["parameter_set_code"])
            parameter_code = str(row["parameter_code"])
            self.session.add(
                GhgParameterValue(
                    value_code=f"{batch.inventory_code}:{parameter_set}:{parameter_code}",
                    version=1,
                    parameter_code=parameter_code,
                    parameter_name=str(row["parameter_name"]),
                    parameter_role=str(row["parameter_role"]),
                    value=Decimal(str(row["value"])),
                    unit=str(row["unit"]),
                    source_mode=str(row["source_mode"]),
                    source_name=str(row["source_name"]),
                    source_version=_text(row.get("source_version")),
                    standard_code=_text(row.get("standard_code")),
                    clause_reference=_text(row.get("clause_reference")),
                    table_reference=_text(row.get("table_reference")),
                    valid_from=_date(row.get("valid_from")),
                    valid_to=_date(row.get("valid_to")),
                    reference_year=_int(row.get("reference_year")),
                    geography=_text(row.get("geography")),
                    technology=_text(row.get("technology")),
                    fuel_or_material=_text(row.get("fuel_or_material")),
                    measurement_method=_text(row.get("measurement_method")),
                    laboratory=_text(row.get("laboratory")),
                    uncertainty=_decimal(row.get("uncertainty")),
                    quality_grade=_text(row.get("quality_grade")),
                    evidence_code=_text(row.get("evidence_code")),
                    approval_status="approved",
                    status="active",
                )
            )

        common_fields = {
            "record_code",
            "inventory_code",
            "organization_code",
            "facility_code",
            "source_code",
            "activity_code",
            "activity_name",
            "period_start",
            "period_end",
            "iso_category_code",
            "ghg_scope",
            "scope3_category",
            "source_mechanism",
            "value_chain_position",
            "boundary_status",
            "national_source_category",
            "activity_amount",
            "activity_unit",
            "data_source_type",
            "measurement_method",
            "quality_status",
            "parameter_set_code",
            "remarks",
        }
        source_by_code = {
            str(row["source_code"]): {key: value for key, value in row.items() if key != "_row_number"}
            for row in snapshot.get("sources", [])
        }
        boundary_snapshot = [
            {key: value for key, value in row.items() if key != "_row_number"} for row in snapshot.get("boundaries", [])
        ]
        warning_issues = [issue for issue in snapshot.get("issues", []) if issue.get("severity") == "warning"]
        global_warning = any(issue.get("rowNumber") is None for issue in warning_issues)
        activity_warning_rows = {
            int(issue["rowNumber"])
            for issue in warning_issues
            if issue.get("sheetName") in {"03_活动数据", "06_数据证据关联"} and issue.get("rowNumber") is not None
        }
        parameter_warning_rows = {
            int(issue["rowNumber"])
            for issue in warning_issues
            if issue.get("sheetName") == "04_参数与因子" and issue.get("rowNumber") is not None
        }
        warning_parameter_sets = {
            str(row.get("parameter_set_code") or "")
            for row in snapshot.get("parameters", [])
            if int(row.get("_row_number") or 0) in parameter_warning_rows
        }
        organization_boundary_id = await self._resolve_organization_boundary_id(batch)
        activity_by_code: dict[str, GhgActivityRecord] = {}
        for row in snapshot.get("activities", []):
            payload = {
                **{key: value for key, value in row.items() if key not in common_fields and key != "_row_number"},
                "method_code": batch.method_code,
                "reporting_profile_code": batch.reporting_profile_code,
                "source_definition": source_by_code.get(str(row["source_code"]), {}),
                "boundary_definition": boundary_snapshot[0] if boundary_snapshot else {},
            }
            activity = GhgActivityRecord(
                record_code=str(row["record_code"]),
                inventory_code=batch.inventory_code,
                reporting_period_id=batch.reporting_period_id,
                organization_boundary_id=organization_boundary_id,
                organization_code=batch.organization_code,
                facility_code=batch.facility_code,
                source_code=str(row["source_code"]),
                activity_code=str(row["activity_code"]),
                activity_name=str(row["activity_name"]),
                period_start=_required_date(row["period_start"]),
                period_end=_required_date(row["period_end"]),
                iso_category_code=batch.iso_category_code,
                ghg_scope=str(row["ghg_scope"]),
                scope3_category=_int(row.get("scope3_category")),
                source_mechanism=str(row["source_mechanism"]),
                value_chain_position=str(row["value_chain_position"]),
                boundary_status=str(row.get("boundary_status") or "included"),
                national_source_category=_text(row.get("national_source_category")),
                activity_amount=Decimal(str(row["activity_amount"])),
                activity_unit=str(row["activity_unit"]),
                data_source_type=str(row["data_source_type"]),
                measurement_method=str(row["measurement_method"]),
                quality_status=(
                    "warning"
                    if global_warning
                    or int(row.get("_row_number") or 0) in activity_warning_rows
                    or str(row.get("parameter_set_code") or "") in warning_parameter_sets
                    else "pass"
                ),
                parameter_set_code=str(row["parameter_set_code"]),
                source_payload=payload,
                remarks=_text(row.get("remarks")),
                status="approved",
                source_system="xlsx_import",
            )
            self.session.add(activity)
            activity_by_code[activity.record_code] = activity
        await self.session.flush()

        allocation_rows = list(snapshot.get("allocations", []))
        area_codes = {str(row.get("area_code") or "") for row in allocation_rows}
        equipment_codes = {str(row.get("equipment_code") or "") for row in allocation_rows if row.get("equipment_code")}
        measurement_codes = {
            str(row.get("measurement_boundary_code") or "")
            for row in allocation_rows
            if row.get("measurement_boundary_code")
        }
        areas = {
            row.code: row
            for row in (
                await self.session.scalars(
                    select(carbon_models.MonitorSector).where(carbon_models.MonitorSector.code.in_(area_codes))
                )
            ).all()
        }
        equipment = {
            row.code: row
            for row in (
                await self.session.scalars(
                    select(carbon_models.MonitorEquipment).where(
                        carbon_models.MonitorEquipment.code.in_(equipment_codes)
                    )
                )
            ).all()
        }
        measurement_boundaries = {
            row.code: row
            for row in (
                await self.session.scalars(
                    select(MeasurementBoundary).where(MeasurementBoundary.code.in_(measurement_codes))
                )
            ).all()
        }
        missing_areas = area_codes - areas.keys()
        missing_equipment = equipment_codes - equipment.keys()
        missing_measurement = measurement_codes - measurement_boundaries.keys()
        if missing_areas or missing_equipment or missing_measurement:
            missing = sorted(missing_areas | missing_equipment | missing_measurement)
            msg = f"区域、设备或计量边界编码不存在：{', '.join(missing)}"
            raise ValueError(msg)
        allocations_by_record: dict[str, list[dict[str, Any]]] = {}
        for row in allocation_rows:
            record_code = str(row["record_code"])
            area = areas[str(row["area_code"])]
            equipment_row = equipment.get(str(row.get("equipment_code") or ""))
            measurement_boundary = measurement_boundaries.get(str(row.get("measurement_boundary_code") or ""))
            allocations_by_record.setdefault(record_code, []).append(
                {
                    "allocation_code": row["allocation_code"],
                    "area_id": area.id,
                    "equipment_id": equipment_row.id if equipment_row else None,
                    "measurement_boundary_id": measurement_boundary.id if measurement_boundary else None,
                    "allocation_role": row["allocation_role"],
                    "allocation_ratio": row["allocation_ratio"],
                    "external_facility_code": row.get("external_facility_code"),
                    "external_facility_name": row.get("external_facility_name"),
                    "source_kind": row.get("source_kind") or "manual",
                    "valid_from": row.get("valid_from"),
                    "valid_to": row.get("valid_to"),
                }
            )
        allocation_use_case = ReplaceActivityAllocations(self.session)
        for record_code in activity_by_code:
            await allocation_use_case.execute(
                inventory_code=batch.inventory_code,
                record_code=record_code,
                allocations=allocations_by_record.get(record_code, []),
                commit=False,
            )

        for row in snapshot.get("links", []):
            evidence = evidence_by_code[str(row["evidence_code"])]
            self.session.add(
                GhgEvidenceLink(
                    link_code=str(row["link_code"]),
                    record_type=str(row["record_type"]),
                    record_code=str(row["record_code"]),
                    evidence_id=evidence.id,
                    evidence_role=str(row["evidence_role"]),
                    page_or_cell_reference=_text(row.get("page_or_cell_reference")),
                    coverage_ratio=_decimal(row.get("coverage_ratio")),
                    review_status="pending",
                )
            )
        batch.status = "committed"
        batch.committed_at = datetime.now().astimezone()
        batch.context_snapshot = {
            **dict(batch.context_snapshot or {}),
            "committed_team_id": str(tenant_id),
            "warningAcknowledgement": (warning_acknowledgement or "").strip() or None,
        }
        await self.session.commit()
        return batch

    async def _resolve_organization_boundary_id(self, batch: GhgImportBatch) -> int | None:
        if batch.reporting_period_id is None:
            return None
        boundary_id = await self.session.scalar(
            select(carbon_models.OrganizationBoundary.id)
            .join(
                carbon_models.ReportingOrganization,
                carbon_models.ReportingOrganization.id == carbon_models.OrganizationBoundary.reporting_org_id,
            )
            .where(
                carbon_models.OrganizationBoundary.period_id == batch.reporting_period_id,
                carbon_models.OrganizationBoundary.status == "published",
                carbon_models.ReportingOrganization.code == batch.organization_code,
            )
            .order_by(carbon_models.OrganizationBoundary.version.desc())
            .limit(1)
        )
        return int(boundary_id) if boundary_id is not None else None


def _text(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _date(value: Any) -> date | None:
    return None if value in (None, "") else _required_date(value)


def _required_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _decimal(value: Any) -> Decimal | None:
    return None if value in (None, "") else Decimal(str(value))


def _int(value: Any) -> int | None:
    return None if value in (None, "") else int(value)
