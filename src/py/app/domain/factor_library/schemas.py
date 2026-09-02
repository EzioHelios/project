"""Transport schemas for factor library maintenance APIs."""

from __future__ import annotations

# ruff: noqa: TC003
from decimal import Decimal
from typing import Any

from app.lib.schema import CamelizedBaseStruct


class CalculationFactorWriteRequest(CamelizedBaseStruct, kw_only=True):
    scope: str
    category: str
    sub_category: str
    unit: str
    factor_value: Decimal
    factor_unit: str
    year: int
    source: str
    source_system: str | None = None
    source_snapshot_id: str | None = None
    raw_record_id: int | None = None
    projection_status: str = "manual"
    review_status: str = "approved"
    is_active: bool = True
    note: str | None = None


class CalculationFactorResponse(CamelizedBaseStruct, kw_only=True):
    id: int
    owner_type: str
    editable: bool
    scope: str
    category: str
    sub_category: str
    unit: str
    factor_value: str
    factor_unit: str
    year: int
    source: str
    source_system: str | None
    source_snapshot_id: str | None
    raw_record_id: int | None
    projection_status: str | None
    review_status: str | None
    is_active: bool
    note: str | None


class CalculationFactorListResponse(CamelizedBaseStruct):
    items: list[CalculationFactorResponse]
    total: int
    limit: int
    offset: int


class CalculationFactorImportRequest(CamelizedBaseStruct, kw_only=True):
    file_name: str
    csv_base64: str


class CalculationFactorImportIssue(CamelizedBaseStruct, kw_only=True):
    severity: str
    row_number: int | None
    field: str | None
    code: str
    message: str
    value: str | None = None


class CalculationFactorImportRow(CamelizedBaseStruct, kw_only=True):
    row_number: int
    action: str
    factor: CalculationFactorWriteRequest | None = None
    issues: list[CalculationFactorImportIssue]


class CalculationFactorImportPreviewResponse(CamelizedBaseStruct, kw_only=True):
    file_name: str
    row_count: int
    valid_count: int
    error_count: int
    create_count: int
    update_count: int
    rows: list[CalculationFactorImportRow]


class ActivityFactorCandidateResponse(CamelizedBaseStruct, kw_only=True):
    id: int
    owner_type: str
    scope: str
    category: str
    sub_category: str
    unit: str
    factor_value: str
    factor_unit: str
    year: int
    source: str
    source_system: str | None
    projection_status: str | None
    review_status: str | None
    is_active: bool
    match_reason: str


class ActivityFactorCandidateListResponse(CamelizedBaseStruct):
    items: list[ActivityFactorCandidateResponse]
    current_parameters: list[dict[str, Any]]


class ApplyActivityFactorRequest(CamelizedBaseStruct, kw_only=True):
    inventory_code: str
    factor_id: int
    parameter_code: str | None = None


class ApplyActivityFactorResponse(CamelizedBaseStruct, kw_only=True):
    record_code: str
    inventory_code: str
    parameter_set_code: str
    parameter_code: str
    factor_id: int
    source_name: str
    factor_value: str
    factor_unit: str
