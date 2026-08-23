"""Tenant-scoped carbon and environmental asset ledger models."""

from __future__ import annotations

# ruff: noqa: TC003
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from advanced_alchemy.base import BigIntAuditBase
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.tenancy import TeamScopedMixin


class CarbonAssetInstrument(TeamScopedMixin, BigIntAuditBase):
    """A registry-backed asset instrument with one immutable native unit."""

    __tablename__ = "carbon_asset_instrument"
    __table_args__ = (
        UniqueConstraint("team_id", "code", name="uq_carbon_asset_instrument_team_code"),
        Index("ix_carbon_asset_instrument_class_status", "team_id", "instrument_class", "status"),
    )

    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    instrument_class: Mapped[str] = mapped_column(String(32), index=True)
    native_unit: Mapped[str] = mapped_column(String(32))
    market: Mapped[str] = mapped_column(String(64), index=True)
    registry: Mapped[str | None] = mapped_column(String(128))
    region: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(16), default="CNY")
    compliance_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source_name: Mapped[str | None] = mapped_column(String(128))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(String(512))


class CarbonAssetAccount(TeamScopedMixin, BigIntAuditBase):
    """Registry or custody account dedicated to exactly one instrument."""

    __tablename__ = "carbon_asset_account"
    __table_args__ = (
        UniqueConstraint("team_id", "account_code", name="uq_carbon_asset_account_team_code"),
        Index("ix_carbon_asset_account_instrument_status", "team_id", "instrument_id", "status"),
    )

    instrument_id: Mapped[int] = mapped_column(ForeignKey("carbon_asset_instrument.id", ondelete="RESTRICT"), index=True)
    account_code: Mapped[str] = mapped_column(String(64), index=True)
    account_name: Mapped[str] = mapped_column(String(128))
    registry_account_no: Mapped[str | None] = mapped_column(String(128))
    owner_name: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    source_name: Mapped[str | None] = mapped_column(String(128))
    remark: Mapped[str | None] = mapped_column(Text)

    instrument: Mapped[CarbonAssetInstrument] = relationship(lazy="selectin")


class CarbonAssetLot(TeamScopedMixin, BigIntAuditBase):
    """Traceable issuance, allocation, or purchase lot."""

    __tablename__ = "carbon_asset_lot"
    __table_args__ = (
        UniqueConstraint("team_id", "lot_no", name="uq_carbon_asset_lot_team_no"),
        Index("ix_carbon_asset_lot_account_status", "team_id", "account_id", "status"),
        Index("ix_carbon_asset_lot_instrument_vintage", "team_id", "instrument_id", "vintage_year"),
    )

    account_id: Mapped[int] = mapped_column(ForeignKey("carbon_asset_account.id", ondelete="RESTRICT"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("carbon_asset_instrument.id", ondelete="RESTRICT"), index=True)
    lot_no: Mapped[str] = mapped_column(String(96), index=True)
    registry_serial_no: Mapped[str | None] = mapped_column(String(160), index=True)
    project_code: Mapped[str | None] = mapped_column(String(64), index=True)
    project_name: Mapped[str | None] = mapped_column(String(160))
    vintage_year: Mapped[int | None] = mapped_column(Integer, index=True)
    issued_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    acquisition_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(16), default="CNY")
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_name: Mapped[str | None] = mapped_column(String(128))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    evidence_ref: Mapped[str | None] = mapped_column(String(512))
    remark: Mapped[str | None] = mapped_column(Text)

    account: Mapped[CarbonAssetAccount] = relationship(lazy="selectin")
    instrument: Mapped[CarbonAssetInstrument] = relationship(lazy="selectin")


class CarbonAssetMovement(TeamScopedMixin, BigIntAuditBase):
    """Append-only posted ledger movement; corrections are reversing movements."""

    __tablename__ = "carbon_asset_movement"
    __table_args__ = (
        UniqueConstraint("team_id", "movement_no", name="uq_carbon_asset_movement_team_no"),
        Index("ix_carbon_asset_movement_account_time", "team_id", "account_id", "posted_at"),
        Index("ix_carbon_asset_movement_lot_time", "team_id", "lot_id", "posted_at"),
        Index("ix_carbon_asset_movement_reference", "team_id", "reference_type", "reference_id"),
    )

    movement_no: Mapped[str] = mapped_column(String(96), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("carbon_asset_account.id", ondelete="RESTRICT"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("carbon_asset_instrument.id", ondelete="RESTRICT"), index=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("carbon_asset_lot.id", ondelete="RESTRICT"), index=True)
    movement_type: Mapped[str] = mapped_column(String(32), index=True)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal(0))
    currency: Mapped[str] = mapped_column(String(16), default="CNY")
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    counterparty: Mapped[str | None] = mapped_column(String(160))
    reference_type: Mapped[str | None] = mapped_column(String(48))
    reference_id: Mapped[int | None] = mapped_column(Integer)
    reverses_movement_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_asset_movement.id", ondelete="RESTRICT"), index=True
    )
    source_name: Mapped[str | None] = mapped_column(String(128))
    evidence_ref: Mapped[str | None] = mapped_column(String(512))
    remark: Mapped[str | None] = mapped_column(Text)

    account: Mapped[CarbonAssetAccount] = relationship(lazy="selectin")
    instrument: Mapped[CarbonAssetInstrument] = relationship(lazy="selectin")
    lot: Mapped[CarbonAssetLot] = relationship(lazy="selectin")


class CarbonComplianceRuleVersion(TeamScopedMixin, BigIntAuditBase):
    """Versioned rule parameters used by a compliance cycle."""

    __tablename__ = "carbon_compliance_rule_version"
    __table_args__ = (
        UniqueConstraint("team_id", "rule_code", "version", name="uq_carbon_compliance_rule_team_version"),
        Index("ix_carbon_compliance_rule_status", "team_id", "status", "effective_from"),
    )

    rule_code: Mapped[str] = mapped_column(String(64), index=True)
    rule_name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer)
    market: Mapped[str] = mapped_column(String(64), index=True)
    eligible_instrument_classes: Mapped[list[str]] = mapped_column(JSON, default=list)
    max_offset_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal(0))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    source_name: Mapped[str] = mapped_column(String(160))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(String(512))


class CarbonComplianceCycle(TeamScopedMixin, BigIntAuditBase):
    """Compliance obligation and frozen accounting source for one cycle."""

    __tablename__ = "carbon_compliance_cycle"
    __table_args__ = (
        UniqueConstraint("team_id", "cycle_code", name="uq_carbon_compliance_cycle_team_code"),
        Index("ix_carbon_compliance_cycle_status_due", "team_id", "status", "surrender_due_date"),
    )

    cycle_code: Mapped[str] = mapped_column(String(64), index=True)
    cycle_name: Mapped[str] = mapped_column(String(160))
    market: Mapped[str] = mapped_column(String(64), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    surrender_due_date: Mapped[date | None] = mapped_column(Date)
    rule_version_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_compliance_rule_version.id", ondelete="RESTRICT"), index=True
    )
    boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_organization_boundary.id", ondelete="SET NULL"), index=True
    )
    covered_emissions_tco2e: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal(0))
    required_surrender_tco2e: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal(0))
    obligation_source: Mapped[str] = mapped_column(String(32), default="manual")
    obligation_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    source_name: Mapped[str | None] = mapped_column(String(128))
    evidence_ref: Mapped[str | None] = mapped_column(String(512))
    remark: Mapped[str | None] = mapped_column(Text)

    rule_version: Mapped[CarbonComplianceRuleVersion] = relationship(lazy="selectin")


class CarbonComplianceSettlement(TeamScopedMixin, BigIntAuditBase):
    """A draft or posted compliance settlement."""

    __tablename__ = "carbon_compliance_settlement"
    __table_args__ = (
        UniqueConstraint("team_id", "settlement_no", name="uq_carbon_compliance_settlement_team_no"),
        Index("ix_carbon_compliance_settlement_cycle_status", "team_id", "cycle_id", "status"),
    )

    settlement_no: Mapped[str] = mapped_column(String(96), index=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("carbon_compliance_cycle.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_cea_tco2e: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal(0))
    total_ccer_tco2e: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal(0))
    rule_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_name: Mapped[str | None] = mapped_column(String(128))
    evidence_ref: Mapped[str | None] = mapped_column(String(512))
    remark: Mapped[str | None] = mapped_column(Text)

    cycle: Mapped[CarbonComplianceCycle] = relationship(lazy="selectin")


class CarbonComplianceSettlementLine(TeamScopedMixin, BigIntAuditBase):
    """A lot-level surrender or offset line."""

    __tablename__ = "carbon_compliance_settlement_line"
    __table_args__ = (Index("ix_carbon_compliance_line_settlement", "team_id", "settlement_id", "instrument_class"),)

    settlement_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_compliance_settlement.id", ondelete="CASCADE"), index=True
    )
    lot_id: Mapped[int] = mapped_column(ForeignKey("carbon_asset_lot.id", ondelete="RESTRICT"), index=True)
    instrument_class: Mapped[str] = mapped_column(String(32), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    purpose: Mapped[str] = mapped_column(String(32))
    movement_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_asset_movement.id", ondelete="RESTRICT"), index=True
    )

    lot: Mapped[CarbonAssetLot] = relationship(lazy="selectin")


class EnvironmentalAssetUsage(TeamScopedMixin, BigIntAuditBase):
    """Non-compliance use of environmental attributes such as green certificates."""

    __tablename__ = "carbon_environmental_asset_usage"
    __table_args__ = (
        UniqueConstraint("team_id", "usage_no", name="uq_carbon_environmental_usage_team_no"),
        Index("ix_carbon_environmental_usage_target", "team_id", "target_type", "target_id"),
    )

    usage_no: Mapped[str] = mapped_column(String(96), index=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("carbon_asset_lot.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    purpose: Mapped[str] = mapped_column(String(48), index=True)
    target_type: Mapped[str] = mapped_column(String(48), index=True)
    target_id: Mapped[int | None] = mapped_column(Integer, index=True)
    reporting_period: Mapped[str | None] = mapped_column(String(32))
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    movement_id: Mapped[int] = mapped_column(ForeignKey("carbon_asset_movement.id", ondelete="RESTRICT"), index=True)
    evidence_ref: Mapped[str | None] = mapped_column(String(512))
    remark: Mapped[str | None] = mapped_column(Text)

    lot: Mapped[CarbonAssetLot] = relationship(lazy="selectin")


class CarbonMarketQuote(TeamScopedMixin, BigIntAuditBase):
    """Observed or imported market quote; never synthetically expanded into history."""

    __tablename__ = "carbon_market_quote"
    __table_args__ = (
        UniqueConstraint(
            "team_id", "instrument_id", "trade_date", "source_name", "source_version", name="uq_carbon_market_quote_source"
        ),
        Index("ix_carbon_market_quote_instrument_date", "team_id", "instrument_id", "trade_date"),
    )

    instrument_id: Mapped[int] = mapped_column(ForeignKey("carbon_asset_instrument.id", ondelete="RESTRICT"), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    close_price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    turnover: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(16), default="CNY")
    quote_unit: Mapped[str] = mapped_column(String(32))
    source_kind: Mapped[str] = mapped_column(String(24), default="observed")
    source_name: Mapped[str] = mapped_column(String(128))
    source_version: Mapped[str] = mapped_column(String(64), default="1")
    source_url: Mapped[str | None] = mapped_column(String(512))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    instrument: Mapped[CarbonAssetInstrument] = relationship(lazy="selectin")


class CarbonCostScenario(TeamScopedMixin, BigIntAuditBase):
    """Editable carbon cost assumptions; runs remain immutable snapshots."""

    __tablename__ = "carbon_cost_scenario"
    __table_args__ = (
        UniqueConstraint("team_id", "scenario_code", name="uq_carbon_cost_scenario_team_code"),
        Index("ix_carbon_cost_scenario_team_status", "team_id", "status", "updated_at"),
    )

    scenario_code: Mapped[str] = mapped_column(String(64), index=True)
    scenario_name: Mapped[str] = mapped_column(String(160))
    cycle_id: Mapped[int | None] = mapped_column(ForeignKey("carbon_compliance_cycle.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_name: Mapped[str | None] = mapped_column(String(128))
    remark: Mapped[str | None] = mapped_column(Text)


class CarbonCostRun(TeamScopedMixin, BigIntAuditBase):
    """Immutable result of a cost scenario calculation."""

    __tablename__ = "carbon_cost_run"
    __table_args__ = (
        UniqueConstraint("team_id", "run_no", name="uq_carbon_cost_run_team_no"),
        Index("ix_carbon_cost_run_scenario_time", "team_id", "scenario_id", "created_at"),
    )

    run_no: Mapped[str] = mapped_column(String(96), index=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("carbon_cost_scenario.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="completed", index=True)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    quote_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    balance_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_summary: Mapped[dict[str, Any]] = mapped_column(JSON)
    period_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
