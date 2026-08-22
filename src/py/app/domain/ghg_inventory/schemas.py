"""Msgspec transport schemas for the organization GHG inventory APIs."""

from __future__ import annotations

from typing import Any

import msgspec

from app.lib.schema import CamelizedBaseStruct

MAX_WARNING_ACKNOWLEDGEMENT_LENGTH = 500


class ImportContext(CamelizedBaseStruct, kw_only=True):
    """Frozen workbook generation and import context."""

    inventory_code: str
    organization_code: str
    facility_code: str
    iso_category_code: str
    reporting_profile_code: str
    method_code: str
    reporting_period_id: int | None = None

    def __post_init__(self) -> None:
        from app.domain.ghg_inventory.domain.catalog import (
            CATEGORY_BY_CODE,
            METHOD_BY_CODE,
            REPORTING_PROFILES,
        )

        _bounded(self.inventory_code, "盘查任务编号", 96)
        _bounded(self.organization_code, "组织编号", 96)
        _bounded(self.facility_code, "设施编号", 96)
        _bounded(self.reporting_profile_code, "报告配置编号", 96)
        _bounded(self.method_code, "计算方法编号", 32)
        category = CATEGORY_BY_CODE.get(self.iso_category_code)
        if category is None:
            msg = "不支持的 ISO 二级分类"
            raise ValueError(msg)
        if self.method_code not in METHOD_BY_CODE or self.method_code not in category.default_methods:
            msg = "计算方法不适用于所选 ISO 二级分类"
            raise ValueError(msg)
        if self.reporting_profile_code not in {profile["code"] for profile in REPORTING_PROFILES}:
            msg = "不支持的报告配置"
            raise ValueError(msg)


class WorkbookPreviewRequest(ImportContext, kw_only=True):
    """Workbook payload submitted for server-side precheck."""

    file_name: str
    workbook_base64: str

    def __post_init__(self) -> None:
        super().__post_init__()
        _bounded(self.file_name, "文件名", 255)
        if not self.workbook_base64:
            msg = "工作簿内容不能为空"
            raise ValueError(msg)


class WorkbookCommitRequest(CamelizedBaseStruct, kw_only=True):
    """Commit a previously previewed workbook without reparsing another path."""

    batch_code: str
    acknowledge_warnings: bool = False
    warning_acknowledgement: str | None = None

    def __post_init__(self) -> None:
        _bounded(self.batch_code, "导入批次编号", 96)
        if (
            self.warning_acknowledgement is not None
            and len(self.warning_acknowledgement) > MAX_WARNING_ACKNOWLEDGEMENT_LENGTH
        ):
            msg = "警告确认原因不能超过500字"
            raise ValueError(msg)


class CalculationRunRequest(CamelizedBaseStruct, kw_only=True):
    """Create a reproducible calculation run for an inventory."""

    inventory_code: str
    reporting_profile_code: str
    reporting_period_id: int | None = None

    def __post_init__(self) -> None:
        _bounded(self.inventory_code, "盘查任务编号", 96)
        _bounded(self.reporting_profile_code, "报告配置编号", 96)


class GhgActivityFieldResponse(CamelizedBaseStruct):
    code: str
    label: str
    required: bool
    choices: list[str]


class GhgCategoryResponse(CamelizedBaseStruct):
    code: str
    name: str
    iso_category: str
    ghg_scope: str
    scope3_category: int | None
    source_mechanism: str
    value_chain_position: str
    default_methods: list[str]
    package_code: str
    activity_fields: list[GhgActivityFieldResponse]
    allocation_policy: dict[str, Any]


class GhgMethodParameterResponse(CamelizedBaseStruct):
    code: str
    name: str
    role: str
    units: list[str]
    required: bool
    source_modes: list[str]


class GhgMethodResponse(CamelizedBaseStruct):
    code: str
    name: str
    family: str
    formula: str
    parameters: list[GhgMethodParameterResponse]
    executable: bool


class GhgReportingProfileResponse(CamelizedBaseStruct):
    code: str
    name: str
    version: str
    standard_code: str


class GhgPeriodResponse(CamelizedBaseStruct):
    id: int
    code: str
    name: str
    organization_code: str
    period_start: str
    period_end: str
    status: str


class GhgOrganizationResponse(CamelizedBaseStruct):
    code: str
    name: str
    organization_type: str


class GhgAreaOptionResponse(CamelizedBaseStruct):
    id: int
    code: str
    name: str
    parent_id: int | None
    level: int


class GhgEquipmentOptionResponse(CamelizedBaseStruct):
    id: int
    code: str
    name: str
    area_id: int | None
    area_code: str | None
    device_type: str | None


class GhgMeasurementBoundaryOptionResponse(CamelizedBaseStruct):
    id: int
    code: str
    name: str
    area_id: int | None
    meter_equipment_id: int | None


class GhgCatalogResponse(CamelizedBaseStruct):
    template_version: str
    categories: list[GhgCategoryResponse]
    methods: list[GhgMethodResponse]
    reporting_profiles: list[GhgReportingProfileResponse]
    periods: list[GhgPeriodResponse]
    organizations: list[GhgOrganizationResponse]
    areas: list[GhgAreaOptionResponse]
    equipment: list[GhgEquipmentOptionResponse]
    measurement_boundaries: list[GhgMeasurementBoundaryOptionResponse]


class GhgActivityResponse(CamelizedBaseStruct):
    record_code: str
    inventory_code: str
    organization_code: str
    facility_code: str
    source_code: str
    activity_code: str
    activity_name: str
    period_start: str
    period_end: str
    iso_category_code: str
    ghg_scope: str
    scope3_category: int | None
    activity_amount: str
    activity_unit: str
    data_source_type: str
    quality_status: str
    status: str
    parameter_set_code: str | None
    organization_boundary_id: int | None
    allocation_status: str
    allocation_count: int
    allocated_area_names: list[str]
    allocated_equipment_names: list[str]
    activity_details: dict[str, Any]


class GhgActivityListResponse(CamelizedBaseStruct):
    items: list[GhgActivityResponse]
    total: int


class GhgBoundaryPreview(CamelizedBaseStruct, kw_only=True):
    row_number: int = msgspec.field(name="_row_number")
    inventory_code: str | None = None
    organization_code: str | None = None
    facility_code: str | None = None
    reporting_profile_code: str | None = None
    iso_category_code: str | None = None
    boundary_method: str | None = None


class GhgSourcePreview(CamelizedBaseStruct, kw_only=True):
    row_number: int = msgspec.field(name="_row_number")
    source_code: str | None = None
    source_name: str | None = None
    activity_type: str | None = None
    facility_code: str | None = None
    iso_category_code: str | None = None


class GhgAllocationPreview(CamelizedBaseStruct, kw_only=True):
    row_number: int = msgspec.field(name="_row_number")
    allocation_code: str | None = None
    record_code: str | None = None
    source_code: str | None = None
    area_code: str | None = None
    equipment_code: str | None = None
    measurement_boundary_code: str | None = None
    allocation_role: str | None = None
    allocation_ratio: str | int | float | None = None
    external_facility_code: str | None = None
    external_facility_name: str | None = None
    source_kind: str | None = None


class GhgActivityPreview(CamelizedBaseStruct, kw_only=True):
    row_number: int = msgspec.field(name="_row_number")
    record_code: str | None = None
    activity_name: str | None = None
    organization_code: str | None = None
    facility_code: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    activity_amount: str | int | float | None = None
    activity_unit: str | None = None
    data_source_type: str | None = None
    parameter_set_code: str | None = None


class GhgParameterPreview(CamelizedBaseStruct, kw_only=True):
    row_number: int = msgspec.field(name="_row_number")
    parameter_set_code: str | None = None
    parameter_code: str | None = None
    parameter_name: str | None = None
    parameter_role: str | None = None
    value: str | int | float | None = None
    unit: str | None = None
    source_mode: str | None = None
    source_name: str | None = None
    source_version: str | None = None
    standard_code: str | None = None
    clause_reference: str | None = None
    evidence_code: str | None = None


class GhgEvidencePreview(CamelizedBaseStruct, kw_only=True):
    row_number: int = msgspec.field(name="_row_number")
    evidence_code: str | None = None
    file_name: str | None = None
    document_type: str | None = None
    issuer: str | None = None
    verification_status: str | None = None
    valid_to: str | None = None


class GhgEvidenceLinkPreview(CamelizedBaseStruct, kw_only=True):
    row_number: int = msgspec.field(name="_row_number")
    link_code: str | None = None
    record_type: str | None = None
    record_code: str | None = None
    evidence_code: str | None = None
    evidence_role: str | None = None
    page_or_cell_reference: str | None = None
    coverage_ratio: str | int | float | None = None


class GhgImportIssueResponse(CamelizedBaseStruct):
    severity: str
    sheet_name: str
    row_number: int | None
    field_code: str | None
    issue_code: str
    message: str
    current_value: str | None
    suggestion: str | None
    status: str


class GhgImportMetricsResponse(CamelizedBaseStruct):
    row_count: int
    valid_count: int
    warning_count: int
    error_count: int
    missing_evidence_count: int


class GhgWorkbookPreviewResponse(CamelizedBaseStruct):
    boundaries: list[GhgBoundaryPreview]
    sources: list[GhgSourcePreview]
    activities: list[GhgActivityPreview]
    allocations: list[GhgAllocationPreview]
    parameters: list[GhgParameterPreview]
    evidence: list[GhgEvidencePreview]
    links: list[GhgEvidenceLinkPreview]
    issues: list[GhgImportIssueResponse]
    metadata: dict[str, str]
    metrics: GhgImportMetricsResponse


class GhgImportBatchResponse(CamelizedBaseStruct):
    batch_code: str
    inventory_code: str
    organization_code: str
    facility_code: str
    iso_category_code: str
    reporting_profile_code: str
    method_code: str
    template_version: str
    file_name: str
    status: str
    row_count: int
    valid_count: int
    warning_count: int
    error_count: int
    missing_evidence_count: int
    preview: GhgWorkbookPreviewResponse
    created_at: str
    committed_at: str | None


class GhgImportBatchListResponse(CamelizedBaseStruct):
    items: list[GhgImportBatchResponse]
    total: int


class GhgCalculationRunResponse(CamelizedBaseStruct):
    run_code: str
    inventory_code: str
    status: str
    total_co2e_kg: str
    input_snapshot: dict[str, Any]
    results: list[dict[str, Any]]
    assignments: list[dict[str, Any]]


class ActivityAllocationInput(CamelizedBaseStruct, kw_only=True):
    allocation_code: str | None = None
    area_id: int
    equipment_id: int | None = None
    measurement_boundary_id: int | None = None
    allocation_role: str
    allocation_ratio: str
    external_facility_code: str | None = None
    external_facility_name: str | None = None
    source_kind: str = "manual"
    valid_from: str | None = None
    valid_to: str | None = None

    def __post_init__(self) -> None:
        if self.area_id <= 0:
            msg = "区域必须为有效主数据"
            raise ValueError(msg)
        try:
            ratio = float(self.allocation_ratio)
        except ValueError as exc:
            msg = "归集比例必须为数字"
            raise ValueError(msg) from exc
        if ratio <= 0 or ratio > 1:
            msg = "归集比例必须大于0且不超过1"
            raise ValueError(msg)


class ReplaceActivityAllocationsRequest(CamelizedBaseStruct, kw_only=True):
    inventory_code: str
    allocations: list[ActivityAllocationInput]

    def __post_init__(self) -> None:
        _bounded(self.inventory_code, "盘查任务编号", 96)
        if not self.allocations:
            msg = "至少需要一条区域归集"
            raise ValueError(msg)


class GhgActivityAllocationResponse(CamelizedBaseStruct):
    allocation_code: str
    record_code: str
    area_id: int
    area_code: str
    area_name: str
    area_path: str | None
    equipment_id: int | None
    equipment_code: str | None
    equipment_name: str | None
    measurement_boundary_id: int | None
    allocation_role: str
    allocation_ratio: str
    external_facility_code: str | None
    external_facility_name: str | None
    source_kind: str


class GhgActivityAllocationListResponse(CamelizedBaseStruct):
    items: list[GhgActivityAllocationResponse]
    total: int


class GhgAreaSummaryItemResponse(CamelizedBaseStruct):
    area_id: int
    area_code: str
    area_name: str
    parent_id: int | None
    level: int
    direct_co2e_kg: str
    rolled_up_co2e_kg: str
    activity_count: int
    equipment_count: int


class GhgAreaSummaryResponse(CamelizedBaseStruct):
    inventory_code: str
    run_code: str | None
    total_co2e_kg: str
    allocated_co2e_kg: str
    unallocated_co2e_kg: str
    coverage_pct: str
    items: list[GhgAreaSummaryItemResponse]


def _bounded(value: str, label: str, maximum: int) -> None:
    if not value or len(value) > maximum:
        msg = f"{label}长度必须在1至{maximum}字符之间"
        raise ValueError(msg)
