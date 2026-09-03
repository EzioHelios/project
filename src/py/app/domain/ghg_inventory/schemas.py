"""Msgspec transport schemas for the organization GHG inventory APIs."""

from __future__ import annotations

from typing import Any

import msgspec

from app.lib.schema import CamelizedBaseStruct

MAX_WARNING_ACKNOWLEDGEMENT_LENGTH = 500
MAX_REPORT_REVIEW_COMMENT_LENGTH = 1000


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


class GhgCalculationRunRequest(CamelizedBaseStruct, kw_only=True):
    """Create a reproducible calculation run for an inventory."""

    inventory_code: str
    reporting_profile_code: str
    reporting_period_id: int | None = None
    reporting_org_id: int | None = None
    organization_boundary_id: int | None = None
    default_scope2_method: str = "location"

    def __post_init__(self) -> None:
        _bounded(self.inventory_code, "盘查任务编号", 96)
        _bounded(self.reporting_profile_code, "报告配置编号", 96)
        if self.default_scope2_method not in {"location", "market"}:
            msg = "Scope 2口径只能选择地点法或市场法"
            raise ValueError(msg)


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
    reporting_org_id: int
    organization_code: str
    period_start: str
    period_end: str
    status: str


class GhgOrganizationResponse(CamelizedBaseStruct):
    id: int
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
    reporting_period_id: int | None
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
    measurement_method: str
    quality_status: str
    status: str
    parameter_set_code: str | None
    organization_boundary_id: int | None
    remarks: str | None
    source_system: str
    source_record_type: str | None
    source_record_id: int | None
    allocation_status: str
    allocation_count: int
    allocated_area_names: list[str]
    allocated_equipment_names: list[str]
    activity_details: dict[str, Any]


class GhgActivityListResponse(CamelizedBaseStruct):
    items: list[GhgActivityResponse]
    total: int


class GhgEmissionSourceResponse(CamelizedBaseStruct):
    inventory_code: str
    organization_code: str
    facility_code: str
    source_code: str
    source_name: str
    iso_category_code: str
    source_mechanism: str
    origin_kind: str
    organization_boundary_id: int | None
    reporting_period_id: int | None
    default_area_id: int | None
    default_equipment_id: int | None
    default_measurement_boundary_id: int | None
    default_allocation_role: str
    external_facility_code: str | None
    external_facility_name: str | None
    valid_from: str | None
    valid_to: str | None
    source_system: str
    source_payload: dict[str, Any]
    status: str
    activity_count: int


class GhgEmissionSourceListResponse(CamelizedBaseStruct):
    items: list[GhgEmissionSourceResponse]
    total: int


class GhgEmissionSourceWriteRequest(CamelizedBaseStruct, kw_only=True):
    inventory_code: str
    organization_code: str
    facility_code: str
    source_code: str
    source_name: str
    iso_category_code: str
    source_mechanism: str | None = None
    origin_kind: str = "internal"
    organization_boundary_id: int | None = None
    reporting_period_id: int | None = None
    default_area_id: int | None = None
    default_equipment_id: int | None = None
    default_measurement_boundary_id: int | None = None
    default_allocation_role: str = "responsibility"
    external_facility_code: str | None = None
    external_facility_name: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    source_system: str = "manual"
    source_payload: dict[str, Any] | None = None
    status: str = "active"

    def __post_init__(self) -> None:
        _bounded(self.inventory_code, "盘查任务编号", 96)
        _bounded(self.organization_code, "组织编号", 96)
        _bounded(self.facility_code, "设施编号", 96)
        _bounded(self.source_code, "排放源编号", 96)
        _bounded(self.source_name, "排放源名称", 255)


class GhgActivityWriteRequest(CamelizedBaseStruct, kw_only=True):
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
    activity_amount: str
    activity_unit: str
    data_source_type: str
    measurement_method: str
    reporting_period_id: int | None = None
    organization_boundary_id: int | None = None
    emission_source_id: int | None = None
    quality_status: str = "pass"
    parameter_set_code: str | None = None
    source_payload: dict[str, Any] | None = None
    remarks: str | None = None
    status: str = "approved"
    source_system: str = "manual"
    source_record_type: str | None = None
    source_record_id: int | None = None

    def __post_init__(self) -> None:
        _bounded(self.record_code, "活动记录编号", 96)
        _bounded(self.inventory_code, "盘查任务编号", 96)
        _bounded(self.organization_code, "组织编号", 96)
        _bounded(self.facility_code, "设施编号", 96)
        _bounded(self.source_code, "排放源编号", 96)
        _bounded(self.activity_code, "活动编号", 96)
        _bounded(self.activity_name, "活动名称", 255)
        _bounded(self.activity_unit, "活动量单位", 64)
        _bounded(self.data_source_type, "数据来源类型", 32)
        _bounded(self.measurement_method, "测量方法", 255)


class GhgActivityGenerateRequest(CamelizedBaseStruct, kw_only=True):
    inventory_code: str
    reporting_period_id: int
    organization_boundary_id: int | None = None
    source_types: list[str]

    def __post_init__(self) -> None:
        _bounded(self.inventory_code, "盘查任务编号", 96)
        if self.reporting_period_id <= 0:
            msg = "报告期必须为有效主数据"
            raise ValueError(msg)
        if not self.source_types:
            msg = "至少选择一种生成来源"
            raise ValueError(msg)


class GhgActivityGenerateResponse(CamelizedBaseStruct):
    inventory_code: str
    created_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    messages: list[str]


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
    reporting_org_id: int | None
    reporting_period_id: int | None
    organization_boundary_id: int | None
    reporting_profile_code: str
    reporting_profile_name: str
    default_scope2_method: str
    input_snapshot: dict[str, Any]
    summary_snapshot: dict[str, Any]
    quality_snapshot: dict[str, Any]
    started_at: str
    completed_at: str | None
    results: list[dict[str, Any]]
    assignments: list[dict[str, Any]]


class GhgCalculationRunListItemResponse(CamelizedBaseStruct):
    run_code: str
    inventory_code: str
    status: str
    reporting_org_id: int | None
    reporting_org_name: str | None
    reporting_period_id: int | None
    reporting_period_name: str | None
    organization_boundary_id: int | None
    organization_boundary_name: str | None
    reporting_profile_code: str
    reporting_profile_name: str
    default_scope2_method: str
    total_co2e_kg: str | None
    quality_status: str
    started_at: str
    completed_at: str | None


class GhgCalculationRunListResponse(CamelizedBaseStruct):
    items: list[GhgCalculationRunListItemResponse]
    total: int


class GhgAnalyticsBreakdownItemResponse(CamelizedBaseStruct):
    code: str
    name: str
    value_co2e_kg: str
    percentage: str
    record_count: int
    warning_count: int
    evidence_coverage_pct: str


class GhgBudgetTargetResponse(CamelizedBaseStruct):
    plan_id: int
    plan_name: str
    target_scope: str
    target_code: str | None
    budget_co2e_tonnes: str
    actual_co2e_tonnes: str | None
    variance_co2e_tonnes: str | None
    execution_rate_pct: str | None
    status: str
    reporting_period_name: str | None


class GhgAnalyticsOverviewResponse(CamelizedBaseStruct):
    run_code: str
    inventory_code: str
    status: str
    reporting_org_id: int | None
    reporting_org_name: str | None
    reporting_period_id: int | None
    reporting_period_name: str | None
    organization_boundary_id: int | None
    organization_boundary_name: str | None
    reporting_profile_code: str
    reporting_profile_name: str
    scope2_method: str
    scope2_available: bool
    total_co2e_kg: str | None
    activity_count: int
    result_count: int
    data_completeness_pct: str
    allocation_coverage_pct: str
    evidence_coverage_pct: str
    quality_status: str
    scope_breakdown: list[GhgAnalyticsBreakdownItemResponse]
    iso_breakdown: list[GhgAnalyticsBreakdownItemResponse]
    source_ranking: list[GhgAnalyticsBreakdownItemResponse]
    area_ranking: list[GhgAnalyticsBreakdownItemResponse]
    equipment_ranking: list[GhgAnalyticsBreakdownItemResponse]
    budget_target: GhgBudgetTargetResponse | None
    completed_at: str | None


class GhgAnalyticsBreakdownResponse(CamelizedBaseStruct):
    run_code: str
    dimension: str
    items: list[GhgAnalyticsBreakdownItemResponse]


class GhgAnalyticsTrendPointResponse(CamelizedBaseStruct):
    run_code: str
    period_id: int | None
    period_name: str
    period_start: str | None
    period_end: str | None
    total_co2e_kg: str | None
    scope1_co2e_kg: str
    scope2_co2e_kg: str | None
    scope3_co2e_kg: str
    scope2_method: str
    boundary_version: int | None


class GhgAnalyticsTrendResponse(CamelizedBaseStruct):
    items: list[GhgAnalyticsTrendPointResponse]
    total: int
    grain: str
    current_total_co2e_kg: str
    previous_total_co2e_kg: str | None
    previous_change_co2e_kg: str | None
    previous_change_pct: str | None
    year_on_year_total_co2e_kg: str | None
    year_on_year_change_co2e_kg: str | None
    year_on_year_change_pct: str | None
    trend_coverage_pct: str
    excluded_cross_period_count: int
    excluded_cross_period_co2e_kg: str


class GhgFlowNodeResponse(CamelizedBaseStruct):
    id: str
    name: str
    value: str
    category: str
    record_count: int
    evidence_coverage_pct: str
    drilldown: dict[str, Any]


class GhgFlowLinkResponse(CamelizedBaseStruct):
    source: str
    target: str
    value: str


class GhgFlowPathResponse(CamelizedBaseStruct):
    path: list[str]
    value: str
    record_count: int
    drilldown: dict[str, Any]


class GhgAnalyticsFlowResponse(CamelizedBaseStruct):
    run_code: str
    classification: str
    scope2_method: str
    total_co2e_kg: str | None
    nodes: list[GhgFlowNodeResponse]
    links: list[GhgFlowLinkResponse]
    top_paths: list[GhgFlowPathResponse]


class GhgResultListItemResponse(CamelizedBaseStruct):
    record_code: str
    activity_name: str
    inventory_code: str
    organization_code: str
    facility_code: str
    source_code: str
    source_name: str
    source_mechanism: str
    period_start: str
    period_end: str
    iso_category_code: str
    iso_category_name: str
    ghg_scope: str
    activity_amount: str
    activity_unit: str
    method_code: str
    method_name: str
    gas_code: str
    co2e_kg: str
    calculated_co2e_kg: str
    attributed_co2e_kg: str
    attribution_ratio: str
    scope2_method: str
    quality_status: str
    evidence_count: int
    allocation_status: str
    area_names: list[str]
    equipment_names: list[str]


class GhgResultListResponse(CamelizedBaseStruct):
    items: list[GhgResultListItemResponse]
    total: int
    limit: int
    offset: int


class GhgResultSummaryResponse(CamelizedBaseStruct):
    run_code: str
    scope2_method: str
    total_co2e_kg: str | None
    activity_count: int
    result_count: int
    missing_evidence_count: int
    unallocated_count: int
    scope_breakdown: list[GhgAnalyticsBreakdownItemResponse]
    iso_breakdown: list[GhgAnalyticsBreakdownItemResponse]
    source_breakdown: list[GhgAnalyticsBreakdownItemResponse]
    area_breakdown: list[GhgAnalyticsBreakdownItemResponse]
    equipment_breakdown: list[GhgAnalyticsBreakdownItemResponse]


class GhgComparisonItemResponse(CamelizedBaseStruct):
    run_code: str
    reporting_period_name: str | None
    organization_boundary_name: str | None
    boundary_version: int | None
    total_co2e_kg: str | None
    scope_breakdown: list[GhgAnalyticsBreakdownItemResponse]
    iso_breakdown: list[GhgAnalyticsBreakdownItemResponse]
    area_breakdown: list[GhgAnalyticsBreakdownItemResponse]
    equipment_breakdown: list[GhgAnalyticsBreakdownItemResponse]


class GhgComparisonDeltaResponse(CamelizedBaseStruct):
    from_run_code: str
    to_run_code: str
    change_co2e_kg: str
    change_pct: str | None


class GhgComparisonResponse(CamelizedBaseStruct):
    scope2_method: str
    items: list[GhgComparisonItemResponse]
    deltas: list[GhgComparisonDeltaResponse]


class GhgResultDetailResponse(CamelizedBaseStruct):
    result: GhgResultListItemResponse
    activity_details: dict[str, Any]
    formula_snapshot: dict[str, Any]
    assignments: list[dict[str, Any]]
    allocations: list[dict[str, Any]]
    evidence: list[dict[str, Any]]


class GhgReadinessCheckResponse(CamelizedBaseStruct):
    code: str
    name: str
    status: str
    completed_count: int
    total_count: int
    coverage_pct: str
    blocking_count: int


class GhgInventoryReadinessResponse(CamelizedBaseStruct):
    inventory_code: str
    reporting_period_id: int | None
    organization_boundary_id: int | None
    ready_for_calculation: bool
    activity_count: int
    checks: list[GhgReadinessCheckResponse]
    blocking_issues: list[str]
    latest_run_code: str | None
    latest_run_status: str | None


class GhgInventoryReportCreateRequest(CamelizedBaseStruct, kw_only=True):
    run_code: str
    title: str
    change_summary: str | None = None

    def __post_init__(self) -> None:
        _bounded(self.run_code, "核算运行编号", 96)
        _bounded(self.title, "报告名称", 255)


class GhgInventoryReportUpdateRequest(CamelizedBaseStruct, kw_only=True):
    title: str
    change_summary: str | None = None

    def __post_init__(self) -> None:
        _bounded(self.title, "报告名称", 255)


class GhgInventoryReportDeleteResponse(CamelizedBaseStruct):
    report_code: str
    version: int
    deleted: bool
    status: str | None


class GhgInventoryReportActionRequest(CamelizedBaseStruct, kw_only=True):
    comment: str | None = None

    def __post_init__(self) -> None:
        if self.comment is not None and len(self.comment) > MAX_REPORT_REVIEW_COMMENT_LENGTH:
            msg = "审核意见不能超过1000字"
            raise ValueError(msg)


class GhgInventoryReportReviewResponse(CamelizedBaseStruct):
    action: str
    from_status: str
    to_status: str
    actor: str
    comment: str | None
    acted_at: str


class GhgInventoryReportResponse(CamelizedBaseStruct):
    id: int
    report_code: str
    version: int
    title: str
    inventory_code: str
    run_code: str
    reporting_org_id: int
    reporting_period_id: int
    organization_boundary_id: int
    reporting_profile_code: str
    status: str
    metrics_snapshot: dict[str, Any]
    evidence_snapshot: dict[str, Any]
    change_summary: str | None
    submitted_by: str | None
    submitted_at: str | None
    approved_by: str | None
    approved_at: str | None
    published_at: str | None
    reviews: list[GhgInventoryReportReviewResponse]


class GhgInventoryReportListResponse(CamelizedBaseStruct):
    items: list[GhgInventoryReportResponse]
    total: int


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
