"""SQLAlchemy persistence models for lightweight organization climate governance."""

from __future__ import annotations

# ruff: noqa: TC003 - SQLAlchemy resolves mapped annotations at runtime.
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from advanced_alchemy.base import BigIntAuditBase
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.lib.tenancy import TeamScopedMixin


class ClimateProgram(TeamScopedMixin, BigIntAuditBase):
    """One organization-level SBTi, CDP, or RE100 management program."""

    __tablename__ = "climate_governance_program"
    __table_args__ = (
        UniqueConstraint("team_id", "framework", "reporting_year", name="uq_climate_program_framework_year"),
        Index("ix_climate_program_status", "team_id", "framework", "status"),
    )

    code: Mapped[str] = mapped_column(String(96), index=True)
    name: Mapped[str] = mapped_column(String(255))
    framework: Mapped[str] = mapped_column(String(16), index=True)
    reporting_year: Mapped[int] = mapped_column(Integer, index=True)
    standard_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    organization_boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_organization_boundary.id", ondelete="SET NULL"), index=True
    )
    owner_name: Mapped[str | None] = mapped_column(String(128))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_name: Mapped[str] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClimateTarget(TeamScopedMixin, BigIntAuditBase):
    """Versioned target boundary and trajectory configuration."""

    __tablename__ = "climate_governance_target"
    __table_args__ = (
        UniqueConstraint("team_id", "program_id", "version", name="uq_climate_target_version"),
        Index("ix_climate_target_status", "team_id", "program_id", "status"),
    )

    program_id: Mapped[int] = mapped_column(ForeignKey("climate_governance_program.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    target_kind: Mapped[str] = mapped_column(String(32), default="absolute_reduction")
    baseline_year: Mapped[int] = mapped_column(Integer)
    baseline_value: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    target_year: Mapped[int] = mapped_column(Integer)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    reduction_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 4))
    scope2_method: Mapped[str] = mapped_column(String(24), default="location")
    scope_coverage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    trajectory_kind: Mapped[str] = mapped_column(String(32), default="internal_linear_tracking")
    status: Mapped[str] = mapped_column(String(24), default="published", index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    effective_from: Mapped[date | None] = mapped_column(Date)


class ClimateDisclosureCycle(TeamScopedMixin, BigIntAuditBase):
    """Annual CDP disclosure readiness and response ownership projection."""

    __tablename__ = "climate_governance_disclosure_cycle"
    __table_args__ = (UniqueConstraint("team_id", "program_id", "reporting_year", name="uq_climate_disclosure_cycle"),)

    program_id: Mapped[int] = mapped_column(ForeignKey("climate_governance_program.id", ondelete="CASCADE"), index=True)
    reporting_year: Mapped[int] = mapped_column(Integer, index=True)
    questionnaire_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="preparing", index=True)
    owner_name: Mapped[str | None] = mapped_column(String(128))
    due_date: Mapped[date | None] = mapped_column(Date)
    domain_statuses: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    response_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    readiness_pct: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=Decimal(0))
    last_assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RenewableElectricityClaim(TeamScopedMixin, BigIntAuditBase):
    """Renewable-electricity attribute claim with qualification and unique allocation."""

    __tablename__ = "climate_governance_renewable_claim"
    __table_args__ = (
        UniqueConstraint("team_id", "claim_no", name="uq_climate_claim_no"),
        UniqueConstraint(
            "team_id",
            "reporting_year",
            "certificate_no",
            name="uq_climate_claim_certificate_year",
        ),
        Index("ix_climate_claim_period_status", "team_id", "reporting_year", "eligibility_status"),
    )

    program_id: Mapped[int] = mapped_column(ForeignKey("climate_governance_program.id", ondelete="CASCADE"), index=True)
    claim_no: Mapped[str] = mapped_column(String(96), index=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    reporting_year: Mapped[int] = mapped_column(Integer, index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    quantity_mwh: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    technology: Mapped[str | None] = mapped_column(String(64))
    generation_country: Mapped[str | None] = mapped_column(String(64))
    consumption_country: Mapped[str | None] = mapped_column(String(64))
    registry: Mapped[str | None] = mapped_column(String(128))
    certificate_no: Mapped[str | None] = mapped_column(String(128), index=True)
    vintage_year: Mapped[int | None] = mapped_column(Integer)
    ownership_status: Mapped[str] = mapped_column(String(24), default="held", index=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    eligibility_status: Mapped[str] = mapped_column(String(24), default="needs_review", index=True)
    eligibility_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_reference: Mapped[str | None] = mapped_column(String(512))
    source_name: Mapped[str] = mapped_column(String(255))
    standard_code: Mapped[str] = mapped_column(String(128), default="RE100-TECH-2025")
    remark: Mapped[str | None] = mapped_column(Text)


class ClimateAssessmentRun(TeamScopedMixin, BigIntAuditBase):
    """Frozen automatic assessment linked to source data and one rule version."""

    __tablename__ = "climate_governance_assessment_run"
    __table_args__ = (
        UniqueConstraint("team_id", "idempotency_key", name="uq_climate_assessment_key"),
        Index("ix_climate_assessment_program", "team_id", "program_id", "completed_at"),
    )

    program_id: Mapped[int] = mapped_column(ForeignKey("climate_governance_program.id", ondelete="CASCADE"), index=True)
    framework: Mapped[str] = mapped_column(String(16), index=True)
    reporting_year: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rule_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metrics_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
