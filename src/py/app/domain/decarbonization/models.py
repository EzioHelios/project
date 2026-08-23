"""SQLAlchemy persistence models for reduction projects and offline CCER development."""

from __future__ import annotations

# ruff: noqa: TC003 - SQLAlchemy resolves mapped annotations at runtime.
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
from sqlalchemy.orm import Mapped, mapped_column

from app.lib.tenancy import TeamScopedMixin


class ReductionMethodologyVersion(BigIntAuditBase):
    """Global immutable reference to one formally published or internal method version."""

    __tablename__ = "decarbonization_methodology_version"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_decarb_method_code_version"),)

    code: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(128), index=True)
    method_kind: Mapped[str] = mapped_column(String(24), default="ccer", index=True)
    status: Mapped[str] = mapped_column(String(24), default="published", index=True)
    published_on: Mapped[date | None] = mapped_column(Date)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(String(512))
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    executable: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    adapter_code: Mapped[str | None] = mapped_column(String(96))
    parameter_schema: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    applicability_schema: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    monitoring_schema: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_schema: Mapped[list[str]] = mapped_column(JSON, default=list)


class ReductionTarget(TeamScopedMixin, BigIntAuditBase):
    """Published or draft reduction target without mutating organization inventory."""

    __tablename__ = "decarbonization_target"
    __table_args__ = (
        UniqueConstraint("team_id", "code", "version", name="uq_decarb_target_version"),
        Index("ix_decarb_target_period", "team_id", "target_year", "status"),
    )

    code: Mapped[str] = mapped_column(String(96), index=True)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    target_year: Mapped[int] = mapped_column(Integer, index=True)
    baseline_year: Mapped[int] = mapped_column(Integer)
    target_type: Mapped[str] = mapped_column(String(24), default="absolute")
    baseline_tco2e: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    target_reduction_tco2e: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    target_reduction_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    organization_boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_organization_boundary.id", ondelete="SET NULL"), index=True
    )
    area_id: Mapped[int | None] = mapped_column(ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"), index=True)
    business_unit: Mapped[str | None] = mapped_column(String(128), index=True)
    trajectory: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    source_name: Mapped[str] = mapped_column(String(255), default="企业目标")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReductionProject(TeamScopedMixin, BigIntAuditBase):
    """Project aggregate root for internal, ISO 14064-2, and CCER tracks."""

    __tablename__ = "decarbonization_project"
    __table_args__ = (
        UniqueConstraint("team_id", "code", name="uq_decarb_project_code"),
        Index("ix_decarb_project_portfolio", "team_id", "track", "category", "status"),
    )

    code: Mapped[str] = mapped_column(String(96), index=True)
    name: Mapped[str] = mapped_column(String(255))
    track: Mapped[str] = mapped_column(String(24), index=True)
    category: Mapped[str] = mapped_column(String(48), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    reduction_status: Mapped[str] = mapped_column(String(32), default="estimated", index=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    owner_name: Mapped[str] = mapped_column(String(128))
    department_name: Mapped[str | None] = mapped_column(String(128), index=True)
    organization_boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_organization_boundary.id", ondelete="SET NULL"), index=True
    )
    methodology_id: Mapped[int | None] = mapped_column(
        ForeignKey("decarbonization_methodology_version.id", ondelete="RESTRICT"), index=True
    )
    target_id: Mapped[int | None] = mapped_column(ForeignKey("decarbonization_target.id", ondelete="SET NULL"), index=True)
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_end: Mapped[date | None] = mapped_column(Date)
    actual_start: Mapped[date | None] = mapped_column(Date)
    progress_pct: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal(0))
    investment_cny: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    expected_reduction_tco2e: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal(0))
    monitored_reduction_tco2e: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal(0))
    verified_reduction_tco2e: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal(0))
    objective: Mapped[str | None] = mapped_column(Text)
    implementation_plan: Mapped[str | None] = mapped_column(Text)
    evaluation_summary: Mapped[str | None] = mapped_column(Text)
    inventory_impact_kind: Mapped[str] = mapped_column(String(32), default="none", index=True)
    source_name: Mapped[str] = mapped_column(String(255), default="企业立项")


class ReductionProjectResourceLink(TeamScopedMixin, BigIntAuditBase):
    """Effective project attribution to an area, equipment, or metering boundary."""

    __tablename__ = "decarbonization_project_resource_link"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "project_id",
            "resource_type",
            "resource_key",
            "role",
            name="uq_decarb_project_resource",
        ),
    )

    project_id: Mapped[int] = mapped_column(ForeignKey("decarbonization_project.id", ondelete="CASCADE"), index=True)
    resource_type: Mapped[str] = mapped_column(String(32), index=True)
    resource_key: Mapped[str] = mapped_column(String(96), index=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"), index=True)
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True
    )
    measurement_boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("metering_measurement_boundary.id", ondelete="SET NULL"), index=True
    )
    role: Mapped[str] = mapped_column(String(32), default="affected", index=True)
    allocation_ratio: Mapped[Decimal] = mapped_column(Numeric(9, 6), default=Decimal(1))
    resource_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ReductionProjectBoundary(TeamScopedMixin, BigIntAuditBase):
    """Versioned project assessment boundary and source/sink selection."""

    __tablename__ = "decarbonization_project_boundary"
    __table_args__ = (UniqueConstraint("team_id", "project_id", "version", name="uq_decarb_boundary_version"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("decarbonization_project.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    physical_boundary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ghg_sources_sinks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    included_gases: Mapped[list[str]] = mapped_column(JSON, default=list)
    exclusions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    organization_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReductionBaselineScenario(TeamScopedMixin, BigIntAuditBase):
    """Immutable-on-lock counterfactual baseline scenario."""

    __tablename__ = "decarbonization_baseline_scenario"
    __table_args__ = (UniqueConstraint("team_id", "project_id", "version", name="uq_decarb_baseline_version"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("decarbonization_project.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    model_kind: Mapped[str] = mapped_column(String(48), index=True)
    model_parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    normalization_variables: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    factor_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    inventory_reference: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    baseline_tco2e: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReductionApplicabilityAssessment(TeamScopedMixin, BigIntAuditBase):
    """One auditable applicability screen against a frozen method version."""

    __tablename__ = "decarbonization_applicability_assessment"
    __table_args__ = (Index("ix_decarb_applicability_project", "team_id", "project_id", "created_at"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("decarbonization_project.id", ondelete="CASCADE"), index=True)
    methodology_id: Mapped[int] = mapped_column(
        ForeignKey("decarbonization_methodology_version.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), index=True)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    blocking_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    methodology_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    assessed_by: Mapped[str | None] = mapped_column(String(128))


class ReductionMonitoringPlan(TeamScopedMixin, BigIntAuditBase):
    """Versioned monitoring parameters, controls, and evidence obligations."""

    __tablename__ = "decarbonization_monitoring_plan"
    __table_args__ = (UniqueConstraint("team_id", "project_id", "version", name="uq_decarb_monitoring_version"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("decarbonization_project.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    parameters: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    quality_controls: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    evidence_requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    data_retention_years: Mapped[int] = mapped_column(Integer, default=10)
    readiness_status: Mapped[str] = mapped_column(String(24), default="incomplete", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReductionCalculationRun(TeamScopedMixin, BigIntAuditBase):
    """Frozen ex-ante or ex-post calculation and its semantic assurance status."""

    __tablename__ = "decarbonization_calculation_run"
    __table_args__ = (
        UniqueConstraint("team_id", "idempotency_key", name="uq_decarb_calculation_key"),
        Index("ix_decarb_calc_project_status", "team_id", "project_id", "status"),
    )

    project_id: Mapped[int] = mapped_column(ForeignKey("decarbonization_project.id", ondelete="CASCADE"), index=True)
    methodology_id: Mapped[int] = mapped_column(
        ForeignKey("decarbonization_methodology_version.id", ondelete="RESTRICT"), index=True
    )
    baseline_id: Mapped[int] = mapped_column(
        ForeignKey("decarbonization_baseline_scenario.id", ondelete="RESTRICT"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    run_kind: Mapped[str] = mapped_column(String(24), default="ex_ante", index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    assurance_status: Mapped[str] = mapped_column(String(32), default="estimated", index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    methodology_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    baseline_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    factor_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    baseline_tco2e: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    project_tco2e: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    leakage_tco2e: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    deduction_tco2e: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    reduction_tco2e: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    components: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    diagnostics: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class ReductionFinancialScenario(TeamScopedMixin, BigIntAuditBase):
    """Financial interpretation kept separate from physical reduction results."""

    __tablename__ = "decarbonization_financial_scenario"
    __table_args__ = (UniqueConstraint("team_id", "project_id", "version", name="uq_decarb_financial_version"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("decarbonization_project.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(255))
    capex_cny: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    annual_opex_cny: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    annual_energy_savings_cny: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    carbon_price_cny_per_t: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal(0))
    annual_reduction_tco2e: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal(0))
    project_life_years: Mapped[int] = mapped_column(Integer, default=10)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), default=Decimal("0.08"))
    npv_cny: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    irr: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    payback_years: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    macc_cny_per_t: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)


class ReductionProjectReview(TeamScopedMixin, BigIntAuditBase):
    """Internal review or offline third-party validation/verification event."""

    __tablename__ = "decarbonization_project_review"
    __table_args__ = (Index("ix_decarb_review_project_type", "team_id", "project_id", "review_type"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("decarbonization_project.id", ondelete="CASCADE"), index=True)
    calculation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("decarbonization_calculation_run.id", ondelete="SET NULL"), index=True
    )
    review_type: Mapped[str] = mapped_column(String(32), index=True)
    decision: Mapped[str] = mapped_column(String(24), index=True)
    reviewer_name: Mapped[str] = mapped_column(String(128))
    organization_name: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    conclusion: Mapped[str | None] = mapped_column(Text)


class CcerDossier(TeamScopedMixin, BigIntAuditBase):
    """Offline CCER application, registration, and issuance ledger."""

    __tablename__ = "decarbonization_ccer_dossier"
    __table_args__ = (UniqueConstraint("team_id", "project_id", name="uq_decarb_ccer_project"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("decarbonization_project.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="preparing", index=True)
    project_design_document_no: Mapped[str | None] = mapped_column(String(128))
    validation_body: Mapped[str | None] = mapped_column(String(255))
    verification_body: Mapped[str | None] = mapped_column(String(255))
    registration_no: Mapped[str | None] = mapped_column(String(128), index=True)
    registration_date: Mapped[date | None] = mapped_column(Date)
    issuance_no: Mapped[str | None] = mapped_column(String(128), index=True)
    issuance_date: Mapped[date | None] = mapped_column(Date)
    issued_quantity_tco2e: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    material_checklist: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    milestones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    carbon_asset_lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_asset_lot.id", ondelete="SET NULL"), index=True
    )


class ReductionAuditEvent(TeamScopedMixin, BigIntAuditBase):
    """Append-only business audit event for the reduction bounded context."""

    __tablename__ = "decarbonization_audit_event"
    __table_args__ = (Index("ix_decarb_audit_project_time", "team_id", "project_id", "created_at"),)

    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("decarbonization_project.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(48), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor_name: Mapped[str | None] = mapped_column(String(128))
    before_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    after_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str | None] = mapped_column(Text)
