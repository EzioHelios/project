"""Public msgspec structures for climate-governance APIs."""

from __future__ import annotations

# ruff: noqa: TC003 - msgspec resolves date and datetime annotations at runtime.
from datetime import date, datetime
from typing import Any

import msgspec

from app.lib.schema import CamelizedBaseStruct


def _empty_dict() -> dict[str, Any]:
    return {}


def _empty_evidence_list() -> list[dict[str, Any]]:
    return []


class ClimateProgramRequest(CamelizedBaseStruct, kw_only=True):
    code: str
    name: str
    framework: str
    reporting_year: int
    organization_boundary_id: int | None = None
    owner_name: str | None = None
    configuration: dict[str, Any] = msgspec.field(default_factory=_empty_dict)
    source_name: str = "企业气候计划"


class ClimateTargetRequest(CamelizedBaseStruct, kw_only=True):
    target_kind: str
    baseline_year: int
    baseline_value: float
    target_year: int
    target_value: float | None = None
    reduction_pct: float | None = None
    scope2_method: str = "location"
    scope_coverage: dict[str, Any] = msgspec.field(default_factory=_empty_dict)
    source_name: str = "企业气候目标"
    effective_from: date | None = None


class ClimateDisclosureCycleRequest(CamelizedBaseStruct, kw_only=True):
    reporting_year: int
    status: str = "preparing"
    owner_name: str | None = None
    due_date: date | None = None
    domain_statuses: dict[str, Any] = msgspec.field(default_factory=_empty_dict)
    response_snapshot: dict[str, Any] = msgspec.field(default_factory=_empty_dict)
    evidence_snapshot: list[dict[str, Any]] = msgspec.field(default_factory=_empty_evidence_list)


class RenewableElectricityClaimRequest(CamelizedBaseStruct, kw_only=True):
    claim_no: str
    source_type: str
    reporting_year: int
    period_start: date
    period_end: date
    quantity_mwh: float
    technology: str | None = None
    generation_country: str | None = None
    consumption_country: str | None = None
    registry: str | None = None
    certificate_no: str | None = None
    vintage_year: int | None = None
    ownership_status: str = "held"
    retired_at: datetime | None = None
    evidence_reference: str | None = None
    source_name: str = "企业可再生电力台账"
    remark: str | None = None


class ClimateAssessmentRequest(CamelizedBaseStruct, kw_only=True):
    idempotency_key: str | None = None


class ClimateProgramResponse(CamelizedBaseStruct, kw_only=True):
    id: int
    code: str
    name: str
    framework: str
    reporting_year: int
    standard_version: str
    status: str
    organization_boundary_id: int | None
    owner_name: str | None
    configuration: dict[str, Any]
    source_name: str
    published_at: str | None


class ClimateProgramListResponse(CamelizedBaseStruct):
    items: list[ClimateProgramResponse]


class ClimateOverviewResponse(CamelizedBaseStruct, kw_only=True):
    reporting_year: int
    programs: list[dict[str, Any]]
    source_status: dict[str, Any]
    metrics: dict[str, Any]
    inventory_trend: list[dict[str, Any]]
    scope_breakdown: list[dict[str, Any]]
    sbti: dict[str, Any]
    cdp: dict[str, Any]
    re100: dict[str, Any]
    tasks: list[dict[str, Any]]


class ClimateTargetResponse(CamelizedBaseStruct, kw_only=True):
    id: int
    program_id: int
    version: int
    target_kind: str
    baseline_year: int
    baseline_value: float
    target_year: int
    target_value: float | None
    reduction_pct: float | None
    scope2_method: str
    scope_coverage: dict[str, Any]
    trajectory_kind: str
    status: str
    source_name: str


class RenewableElectricityClaimResponse(CamelizedBaseStruct, kw_only=True):
    id: int
    program_id: int
    claim_no: str
    source_type: str
    reporting_year: int
    period_start: str
    period_end: str
    quantity_mwh: float
    technology: str | None
    generation_country: str | None
    consumption_country: str | None
    registry: str | None
    certificate_no: str | None
    vintage_year: int | None
    ownership_status: str
    eligibility_status: str
    eligibility_reasons: list[str]
    evidence_reference: str | None
    source_name: str


class RenewableElectricityClaimListResponse(CamelizedBaseStruct):
    items: list[RenewableElectricityClaimResponse]


class ClimateAssessmentRunResponse(CamelizedBaseStruct, kw_only=True):
    id: int
    program_id: int
    framework: str
    reporting_year: int
    status: str
    metrics: dict[str, Any]
    checks: list[dict[str, Any]]
    rule_snapshot: dict[str, Any]
    completed_at: str


class ClimateAssessmentRunListResponse(CamelizedBaseStruct):
    items: list[ClimateAssessmentRunResponse]
