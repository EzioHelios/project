"""Typed API contracts for carbon assets."""

from __future__ import annotations

# ruff: noqa: TC003
from datetime import date
from typing import Any

import msgspec

from app.lib.schema import CamelizedBaseStruct


def _empty_dict() -> dict[str, Any]:
    return {}


def _empty_str_list() -> list[str]:
    return []


class InstrumentRequest(CamelizedBaseStruct, kw_only=True):
    code: str
    name: str
    instrument_class: str
    native_unit: str
    market: str
    registry: str | None = None
    region: str | None = None
    currency: str = "CNY"
    compliance_eligible: bool = False
    status: str = "active"
    valid_from: date | None = None
    valid_to: date | None = None
    source_name: str | None = None
    standard_code: str | None = None
    source_url: str | None = None


class AccountRequest(CamelizedBaseStruct, kw_only=True):
    instrument_id: int
    account_code: str
    account_name: str
    registry_account_no: str | None = None
    owner_name: str | None = None
    status: str = "active"
    source_name: str | None = None
    remark: str | None = None


class LotRequest(CamelizedBaseStruct, kw_only=True):
    account_id: int
    lot_no: str
    registry_serial_no: str | None = None
    project_code: str | None = None
    project_name: str | None = None
    vintage_year: int | None = None
    issued_quantity: float
    acquisition_unit_cost: float | None = None
    currency: str = "CNY"
    valid_from: date | None = None
    valid_to: date | None = None
    attributes: dict[str, Any] = msgspec.field(default_factory=_empty_dict)
    source_name: str | None = None
    standard_code: str | None = None
    evidence_ref: str | None = None
    remark: str | None = None


class MovementRequest(CamelizedBaseStruct, kw_only=True):
    lot_id: int
    movement_type: str
    quantity_delta: float
    occurred_on: date
    unit_price: float | None = None
    fee_amount: float = 0
    currency: str = "CNY"
    counterparty: str | None = None
    reference_type: str | None = None
    reference_id: int | None = None
    source_name: str | None = None
    evidence_ref: str | None = None
    remark: str | None = None


class ReversalRequest(CamelizedBaseStruct, kw_only=True):
    occurred_on: date
    reason: str
    evidence_ref: str | None = None


class RuleVersionRequest(CamelizedBaseStruct, kw_only=True):
    rule_code: str
    rule_name: str
    version: int
    market: str
    eligible_instrument_classes: list[str] = msgspec.field(default_factory=_empty_str_list)
    max_offset_ratio: float = 0
    parameters: dict[str, Any] = msgspec.field(default_factory=_empty_dict)
    effective_from: date
    effective_to: date | None = None
    status: str = "draft"
    source_name: str
    standard_code: str | None = None
    source_url: str | None = None


class ComplianceCycleRequest(CamelizedBaseStruct, kw_only=True):
    cycle_code: str
    cycle_name: str
    market: str
    period_start: date
    period_end: date
    surrender_due_date: date | None = None
    rule_version_id: int
    boundary_id: int | None = None
    covered_emissions_tco2e: float
    required_surrender_tco2e: float
    obligation_source: str = "manual"
    obligation_snapshot: dict[str, Any] = msgspec.field(default_factory=_empty_dict)
    source_name: str | None = None
    evidence_ref: str | None = None
    remark: str | None = None


class SettlementLineRequest(CamelizedBaseStruct, kw_only=True):
    lot_id: int
    quantity: float
    purpose: str


class SettlementRequest(CamelizedBaseStruct, kw_only=True):
    cycle_id: int
    lines: list[SettlementLineRequest]
    source_name: str | None = None
    evidence_ref: str | None = None
    remark: str | None = None


class EnvironmentalUsageRequest(CamelizedBaseStruct, kw_only=True):
    lot_id: int
    quantity: float
    purpose: str
    target_type: str
    target_id: int | None = None
    reporting_period: str | None = None
    evidence_ref: str | None = None
    remark: str | None = None


class MarketQuoteRequest(CamelizedBaseStruct, kw_only=True):
    instrument_id: int
    trade_date: date
    close_price: float
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    volume: float | None = None
    turnover: float | None = None
    currency: str = "CNY"
    quote_unit: str
    source_kind: str = "observed"
    source_name: str
    source_version: str = "1"
    source_url: str | None = None


class CostScenarioRequest(CamelizedBaseStruct, kw_only=True):
    scenario_code: str
    scenario_name: str
    cycle_id: int | None = None
    parameters: dict[str, Any] = msgspec.field(default_factory=_empty_dict)
    source_name: str | None = None
    remark: str | None = None


class IdResponse(CamelizedBaseStruct):
    id: int


class PageResponse(CamelizedBaseStruct):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class AssetOverviewResponse(CamelizedBaseStruct):
    balances: list[dict[str, Any]]
    portfolio_value_cny: float
    active_cycle: dict[str, Any] | None
    compliance_position: dict[str, Any] | None
    latest_quotes: list[dict[str, Any]]
    recent_movements: list[dict[str, Any]]


class CompliancePositionResponse(CamelizedBaseStruct):
    cycle: dict[str, Any]
    position: dict[str, Any]
    eligible_lots: list[dict[str, Any]]


class CostRunResponse(CamelizedBaseStruct):
    id: int
    run_no: str
    status: str
    input_snapshot: dict[str, Any]
    quote_snapshot: dict[str, Any]
    balance_snapshot: dict[str, Any]
    result_summary: dict[str, Any]
    period_results: list[dict[str, Any]]
