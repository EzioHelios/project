"""Public msgspec request and response structures for the reduction API."""

# pyright: reportUnknownVariableType=false

from __future__ import annotations

# ruff: noqa: TC003 - msgspec resolves date and datetime field types at runtime.
from datetime import date, datetime
from typing import Any

import msgspec

from app.lib.schema import CamelizedBaseStruct


class ReductionTargetRequest(CamelizedBaseStruct, kw_only=True):
    code: str
    name: str
    target_year: int
    baseline_year: int
    baseline_tco2e: float
    target_reduction_tco2e: float
    target_reduction_pct: float | None = None
    organization_boundary_id: int | None = None
    area_id: int | None = None
    business_unit: str | None = None
    trajectory: list[dict[str, Any]] = msgspec.field(default_factory=list)
    source_name: str = "企业目标"


class ReductionProjectRequest(CamelizedBaseStruct, kw_only=True):
    code: str
    name: str
    track: str
    category: str
    owner_name: str
    department_name: str | None = None
    organization_boundary_id: int | None = None
    methodology_id: int | None = None
    target_id: int | None = None
    planned_start: date | None = None
    planned_end: date | None = None
    investment_cny: float = 0
    expected_reduction_tco2e: float = 0
    objective: str | None = None
    implementation_plan: str | None = None
    inventory_impact_kind: str = "none"


class ReductionProjectUpdateRequest(CamelizedBaseStruct, kw_only=True, omit_defaults=True):
    name: str | msgspec.UnsetType = msgspec.UNSET
    owner_name: str | msgspec.UnsetType = msgspec.UNSET
    department_name: str | None | msgspec.UnsetType = msgspec.UNSET
    methodology_id: int | None | msgspec.UnsetType = msgspec.UNSET
    target_id: int | None | msgspec.UnsetType = msgspec.UNSET
    planned_start: date | None | msgspec.UnsetType = msgspec.UNSET
    planned_end: date | None | msgspec.UnsetType = msgspec.UNSET
    actual_start: date | None | msgspec.UnsetType = msgspec.UNSET
    progress_pct: float | msgspec.UnsetType = msgspec.UNSET
    investment_cny: float | msgspec.UnsetType = msgspec.UNSET
    expected_reduction_tco2e: float | msgspec.UnsetType = msgspec.UNSET
    objective: str | None | msgspec.UnsetType = msgspec.UNSET
    implementation_plan: str | None | msgspec.UnsetType = msgspec.UNSET
    evaluation_summary: str | None | msgspec.UnsetType = msgspec.UNSET
    risk_level: str | msgspec.UnsetType = msgspec.UNSET


class ProjectTransitionRequest(CamelizedBaseStruct, kw_only=True):
    target_status: str
    reason: str | None = None
    actor_name: str | None = None


class ProjectBoundaryRequest(CamelizedBaseStruct, kw_only=True):
    physical_boundary: dict[str, Any] = msgspec.field(default_factory=dict)
    ghg_sources_sinks: list[dict[str, Any]] = msgspec.field(default_factory=list)
    included_gases: list[str] = msgspec.field(default_factory=list)
    exclusions: list[dict[str, Any]] = msgspec.field(default_factory=list)
    resources: list[dict[str, Any]] = msgspec.field(default_factory=list)


class BaselineScenarioRequest(CamelizedBaseStruct, kw_only=True):
    name: str
    period_start: date
    period_end: date
    model_kind: str
    model_parameters: dict[str, Any] = msgspec.field(default_factory=dict)
    normalization_variables: list[dict[str, Any]] = msgspec.field(default_factory=list)
    factor_snapshot: dict[str, Any] = msgspec.field(default_factory=dict)
    inventory_reference: dict[str, Any] = msgspec.field(default_factory=dict)
    baseline_tco2e: float | None = None


class ApplicabilityAssessmentRequest(CamelizedBaseStruct, kw_only=True):
    methodology_id: int
    answers: dict[str, Any] = msgspec.field(default_factory=dict)
    assessed_by: str | None = None


class MonitoringPlanRequest(CamelizedBaseStruct, kw_only=True):
    parameters: list[dict[str, Any]] = msgspec.field(default_factory=list)
    quality_controls: list[dict[str, Any]] = msgspec.field(default_factory=list)
    evidence_requirements: list[dict[str, Any]] = msgspec.field(default_factory=list)
    data_retention_years: int = 10
    publish: bool = False


class CalculationRunRequest(CamelizedBaseStruct, kw_only=True):
    methodology_id: int
    baseline_id: int
    run_kind: str
    period_start: date
    period_end: date
    inputs: dict[str, Any] = msgspec.field(default_factory=dict)
    factor_snapshot: dict[str, Any] = msgspec.field(default_factory=dict)
    idempotency_key: str | None = None


class FinancialScenarioRequest(CamelizedBaseStruct, kw_only=True):
    name: str
    capex_cny: float
    annual_opex_cny: float
    annual_energy_savings_cny: float
    carbon_price_cny_per_t: float
    annual_reduction_tco2e: float
    project_life_years: int = 10
    discount_rate: float = 0.08


class ProjectReviewRequest(CamelizedBaseStruct, kw_only=True):
    calculation_run_id: int | None = None
    review_type: str
    decision: str
    reviewer_name: str
    organization_name: str | None = None
    reviewed_at: datetime
    findings: list[dict[str, Any]] = msgspec.field(default_factory=list)
    conclusion: str | None = None


class CcerDossierRequest(CamelizedBaseStruct, kw_only=True):
    status: str
    project_design_document_no: str | None = None
    validation_body: str | None = None
    verification_body: str | None = None
    registration_no: str | None = None
    registration_date: date | None = None
    issuance_no: str | None = None
    issuance_date: date | None = None
    issued_quantity_tco2e: float | None = None
    material_checklist: list[dict[str, Any]] = msgspec.field(default_factory=list)
    milestones: list[dict[str, Any]] = msgspec.field(default_factory=list)


class IssuanceLinkRequest(CamelizedBaseStruct, kw_only=True):
    account_id: int
    market_price: float | None = None


class MonitoringWorkbookRequest(CamelizedBaseStruct, kw_only=True):
    file_name: str
    workbook_base64: str
    commit: bool = False


class ReductionTargetResponse(CamelizedBaseStruct, kw_only=True):
    id: int
    code: str
    name: str
    version: int
    target_year: int
    baseline_year: int
    target_type: str
    baseline_tco2e: float
    target_reduction_tco2e: float
    target_reduction_pct: float | None
    organization_boundary_id: int | None
    area_id: int | None
    business_unit: str | None
    trajectory: list[dict[str, Any]]
    status: str
    source_name: str
    published_at: str | None


class ReductionTargetListResponse(CamelizedBaseStruct):
    items: list[ReductionTargetResponse]


class ReductionProjectSummaryResponse(CamelizedBaseStruct, kw_only=True):
    id: int
    code: str
    name: str
    track: str
    category: str
    status: str
    reduction_status: str
    risk_level: str
    owner_name: str
    department_name: str | None
    organization_boundary_id: int | None
    methodology_id: int | None
    target_id: int | None
    planned_start: str | None
    planned_end: str | None
    actual_start: str | None
    progress_pct: float
    investment_cny: float
    expected_reduction_tco2e: float
    monitored_reduction_tco2e: float
    verified_reduction_tco2e: float
    latest_locked_baseline_tco2e: float | None = None
    latest_calculation_baseline_tco2e: float | None = None
    latest_calculation_project_tco2e: float | None = None
    latest_calculation_reduction_tco2e: float | None = None
    latest_calculation_status: str | None = None
    objective: str | None
    implementation_plan: str | None
    evaluation_summary: str | None
    inventory_impact_kind: str
    source_name: str
    created_at: str
    updated_at: str
    methodology: dict[str, Any] | None


class ReductionProjectListResponse(CamelizedBaseStruct):
    items: list[ReductionProjectSummaryResponse]
    total: int
    limit: int
    offset: int


class ReductionProjectDetailResponse(ReductionProjectSummaryResponse, kw_only=True):
    resources: list[dict[str, Any]]
    boundaries: list[dict[str, Any]]
    baselines: list[dict[str, Any]]
    assessments: list[dict[str, Any]]
    monitoring_plans: list[dict[str, Any]]
    calculations: list[dict[str, Any]]
    financial_scenarios: list[dict[str, Any]]
    reviews: list[dict[str, Any]]
    ccer_dossier: dict[str, Any] | None
    evidence_count: int


class ReductionMethodologyResponse(CamelizedBaseStruct, kw_only=True):
    id: int
    code: str
    version: str
    name: str
    sector: str
    method_kind: str
    status: str
    published_on: str | None
    effective_from: str | None
    effective_to: str | None
    source_url: str
    source_sha256: str | None
    executable: bool
    adapter_code: str | None
    parameter_schema: list[dict[str, Any]]
    applicability_schema: list[dict[str, Any]]
    monitoring_schema: list[str]
    evidence_schema: list[str]


class ReductionMethodologyListResponse(CamelizedBaseStruct):
    items: list[ReductionMethodologyResponse]


class ReductionCalculationResponse(CamelizedBaseStruct, kw_only=True):
    id: int
    project_id: int
    methodology_id: int
    baseline_id: int
    run_kind: str
    status: str
    assurance_status: str
    period_start: str
    period_end: str
    input_snapshot: dict[str, Any]
    methodology_snapshot: dict[str, Any]
    baseline_snapshot: dict[str, Any]
    factor_snapshot: dict[str, Any]
    baseline_tco2e: float | None
    project_tco2e: float | None
    leakage_tco2e: float | None
    deduction_tco2e: float | None
    reduction_tco2e: float | None
    components: dict[str, Any]
    diagnostics: list[dict[str, Any]]
    completed_at: str | None
    error_message: str | None
    created_at: str


class ReductionOverviewMetrics(CamelizedBaseStruct, kw_only=True):
    actual_inventory_tco2e: float
    target_emissions_tco2e: float
    target_gap_tco2e: float
    expected_reduction_tco2e: float
    monitored_reduction_tco2e: float
    verified_reduction_tco2e: float
    issued_ccer_tco2e: float
    project_count: int
    on_track_count: int


class ReductionOverviewResponse(CamelizedBaseStruct, kw_only=True):
    metrics: ReductionOverviewMetrics
    inventory_reference: dict[str, Any]
    target: ReductionTargetResponse | None
    trend: list[dict[str, Any]]
    waterfall: list[dict[str, Any]]
    project_reduction: dict[str, Any]
    contribution: list[dict[str, Any]]
    portfolio: list[dict[str, Any]]
    key_measures: list[ReductionProjectSummaryResponse]


class ReductionAuditListResponse(CamelizedBaseStruct):
    items: list[dict[str, Any]]


__all__ = (
    "ApplicabilityAssessmentRequest",
    "BaselineScenarioRequest",
    "CalculationRunRequest",
    "CcerDossierRequest",
    "FinancialScenarioRequest",
    "IssuanceLinkRequest",
    "MonitoringPlanRequest",
    "MonitoringWorkbookRequest",
    "ProjectBoundaryRequest",
    "ProjectReviewRequest",
    "ProjectTransitionRequest",
    "ReductionAuditListResponse",
    "ReductionCalculationResponse",
    "ReductionMethodologyListResponse",
    "ReductionMethodologyResponse",
    "ReductionOverviewResponse",
    "ReductionProjectDetailResponse",
    "ReductionProjectListResponse",
    "ReductionProjectRequest",
    "ReductionProjectSummaryResponse",
    "ReductionProjectUpdateRequest",
    "ReductionTargetListResponse",
    "ReductionTargetRequest",
    "ReductionTargetResponse",
)
