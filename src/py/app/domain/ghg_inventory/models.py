"""Persistence models for the canonical organization GHG inventory."""

from __future__ import annotations

# ruff: noqa: TC003 - SQLAlchemy resolves mapped date/datetime annotations at runtime.
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from advanced_alchemy.base import BigIntAuditBase
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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


class GhgReportingProfile(BigIntAuditBase):
    """Immutable reporting rule set used to classify and render one inventory."""

    __tablename__ = "ghg_reporting_profile"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_ghg_reporting_profile_code_version"),)

    code: Mapped[str] = mapped_column(String(96), index=True)
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(32))
    standard_code: Mapped[str] = mapped_column(String(128))
    standard_version: Mapped[str] = mapped_column(String(32))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    boundary_rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_mappings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default="published", index=True)


class GhgCalculationMethodDefinition(BigIntAuditBase):
    """Published, immutable calculation method and controlled expression metadata."""

    __tablename__ = "ghg_calculation_method_definition"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_ghg_method_code_version"),)

    code: Mapped[str] = mapped_column(String(32), index=True)
    version: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(160))
    formula_family: Mapped[str] = mapped_column(String(16), index=True)
    formula_variant: Mapped[str] = mapped_column(String(48), default="default")
    formula_expression: Mapped[dict[str, Any]] = mapped_column(JSON)
    human_formula: Mapped[str] = mapped_column(Text)
    standard_code: Mapped[str] = mapped_column(String(128))
    clause_reference: Mapped[str | None] = mapped_column(String(128))
    applicable_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    applicable_gases: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_priority: Mapped[list[str]] = mapped_column(JSON, default=list)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), default="published", index=True)


class GhgMethodParameterDefinition(BigIntAuditBase):
    """One independently sourced input required by a calculation method."""

    __tablename__ = "ghg_method_parameter_definition"
    __table_args__ = (
        UniqueConstraint("method_id", "parameter_code", name="uq_ghg_method_parameter_code"),
        Index("ix_ghg_method_parameter_method_order", "method_id", "sort_order"),
    )

    method_id: Mapped[int] = mapped_column(
        ForeignKey("ghg_calculation_method_definition.id", ondelete="CASCADE"), index=True
    )
    parameter_code: Mapped[str] = mapped_column(String(64), index=True)
    parameter_name: Mapped[str] = mapped_column(String(128))
    parameter_role: Mapped[str] = mapped_column(String(32), index=True)
    value_type: Mapped[str] = mapped_column(String(24), default="decimal")
    unit_dimension: Mapped[str | None] = mapped_column(String(64))
    allowed_units: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_source_modes: Mapped[list[str]] = mapped_column(JSON, default=list)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    condition: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class GhgParameterValue(TeamScopedMixin, BigIntAuditBase):
    """Tenant-owned measured, supplied, published, or approved parameter candidate."""

    __tablename__ = "ghg_parameter_value"
    __table_args__ = (
        UniqueConstraint("team_id", "value_code", "version", name="uq_ghg_parameter_value_version"),
        Index(
            "ix_ghg_parameter_value_resolution",
            "team_id",
            "parameter_code",
            "reference_year",
            "geography",
            "status",
        ),
    )

    value_code: Mapped[str] = mapped_column(String(96), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parameter_code: Mapped[str] = mapped_column(String(64), index=True)
    parameter_name: Mapped[str] = mapped_column(String(128))
    parameter_role: Mapped[str] = mapped_column(String(32), index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 12))
    unit: Mapped[str] = mapped_column(String(64))
    source_mode: Mapped[str] = mapped_column(String(32), index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    source_version: Mapped[str | None] = mapped_column(String(64))
    standard_code: Mapped[str | None] = mapped_column(String(128))
    clause_reference: Mapped[str | None] = mapped_column(String(128))
    table_reference: Mapped[str | None] = mapped_column(String(128))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    reference_year: Mapped[int | None] = mapped_column(Integer, index=True)
    geography: Mapped[str | None] = mapped_column(String(96), index=True)
    technology: Mapped[str | None] = mapped_column(String(128))
    fuel_or_material: Mapped[str | None] = mapped_column(String(128), index=True)
    measurement_method: Mapped[str | None] = mapped_column(String(255))
    laboratory: Mapped[str | None] = mapped_column(String(255))
    uncertainty: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    quality_grade: Mapped[str | None] = mapped_column(String(24))
    evidence_code: Mapped[str | None] = mapped_column(String(96), index=True)
    approval_status: Mapped[str] = mapped_column(String(24), default="approved", index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)


class GhgEmissionSource(TeamScopedMixin, BigIntAuditBase):
    """Stable inventory source with a default internal-resource attribution."""

    __tablename__ = "ghg_emission_source"
    __table_args__ = (
        UniqueConstraint("team_id", "inventory_code", "source_code", name="uq_ghg_source_inventory_code"),
        Index("ix_ghg_source_category", "team_id", "inventory_code", "iso_category_code"),
        Index("ix_ghg_source_resource", "team_id", "default_area_id", "default_equipment_id"),
    )

    inventory_code: Mapped[str] = mapped_column(String(96), index=True)
    organization_boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_organization_boundary.id", ondelete="SET NULL"), index=True
    )
    reporting_period_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_reporting_period.id", ondelete="SET NULL"), index=True
    )
    organization_code: Mapped[str] = mapped_column(String(96), index=True)
    facility_code: Mapped[str] = mapped_column(String(96), index=True)
    source_code: Mapped[str] = mapped_column(String(96), index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    iso_category_code: Mapped[str] = mapped_column(String(8), index=True)
    source_mechanism: Mapped[str] = mapped_column(String(32), index=True)
    origin_kind: Mapped[str] = mapped_column(String(24), default="internal", index=True)
    default_area_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"), index=True
    )
    default_equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True
    )
    default_measurement_boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("metering_measurement_boundary.id", ondelete="SET NULL"), index=True
    )
    default_allocation_role: Mapped[str] = mapped_column(String(32), default="responsibility", index=True)
    external_facility_code: Mapped[str | None] = mapped_column(String(96), index=True)
    external_facility_name: Mapped[str | None] = mapped_column(String(255))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source_system: Mapped[str] = mapped_column(String(64), default="manual")
    source_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)


class GhgActivityRecord(TeamScopedMixin, BigIntAuditBase):
    """Method-neutral organization inventory activity fact."""

    __tablename__ = "ghg_activity_record"
    __table_args__ = (
        UniqueConstraint("team_id", "inventory_code", "record_code", name="uq_ghg_activity_inventory_record"),
        Index("ix_ghg_activity_inventory_category", "team_id", "inventory_code", "iso_category_code"),
        Index("ix_ghg_activity_period", "team_id", "period_start", "period_end"),
        Index("ix_ghg_activity_period_mechanism", "team_id", "period_start", "period_end", "source_mechanism"),
    )

    record_code: Mapped[str] = mapped_column(String(96), index=True)
    inventory_code: Mapped[str] = mapped_column(String(96), index=True)
    reporting_period_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_reporting_period.id", ondelete="SET NULL"), index=True
    )
    organization_boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_organization_boundary.id", ondelete="SET NULL"), index=True
    )
    emission_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("ghg_emission_source.id", ondelete="SET NULL"), index=True
    )
    organization_code: Mapped[str] = mapped_column(String(96), index=True)
    facility_code: Mapped[str] = mapped_column(String(96), index=True)
    source_code: Mapped[str] = mapped_column(String(96), index=True)
    activity_code: Mapped[str] = mapped_column(String(96), index=True)
    activity_name: Mapped[str] = mapped_column(String(255))
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    iso_category_code: Mapped[str] = mapped_column(String(8), index=True)
    ghg_scope: Mapped[str] = mapped_column(String(16), index=True)
    scope3_category: Mapped[int | None] = mapped_column(Integer, index=True)
    source_mechanism: Mapped[str] = mapped_column(String(32), index=True)
    value_chain_position: Mapped[str] = mapped_column(String(16), index=True)
    boundary_status: Mapped[str] = mapped_column(String(32), default="included", index=True)
    national_source_category: Mapped[str | None] = mapped_column(String(160))
    activity_amount: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    activity_unit: Mapped[str] = mapped_column(String(64))
    data_source_type: Mapped[str] = mapped_column(String(32), index=True)
    measurement_method: Mapped[str] = mapped_column(String(255))
    quality_status: Mapped[str] = mapped_column(String(24), default="pass", index=True)
    parameter_set_code: Mapped[str | None] = mapped_column(String(96), index=True)
    source_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    remarks: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    source_system: Mapped[str] = mapped_column(String(64), default="manual")
    source_record_type: Mapped[str | None] = mapped_column(String(64), index=True)
    source_record_id: Mapped[int | None] = mapped_column(Integer, index=True)


class GhgActivityAllocation(TeamScopedMixin, BigIntAuditBase):
    """Immutable-at-calculation allocation of one activity to an area and optional resource."""

    __tablename__ = "ghg_activity_allocation"
    __table_args__ = (
        UniqueConstraint("team_id", "activity_id", "allocation_code", name="uq_ghg_activity_allocation_code"),
        Index("ix_ghg_allocation_area", "team_id", "area_id", "allocation_role"),
        Index("ix_ghg_allocation_equipment", "team_id", "equipment_id", "allocation_role"),
        Index(
            "ix_ghg_allocation_resource_activity",
            "team_id",
            "area_id",
            "equipment_id",
            "activity_id",
            "status",
        ),
        CheckConstraint("allocation_ratio > 0 and allocation_ratio <= 1", name="ck_ghg_allocation_ratio"),
    )

    activity_id: Mapped[int] = mapped_column(ForeignKey("ghg_activity_record.id", ondelete="CASCADE"), index=True)
    emission_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("ghg_emission_source.id", ondelete="SET NULL"), index=True
    )
    allocation_code: Mapped[str] = mapped_column(String(96), index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("dataapp_monitorsector.id", ondelete="RESTRICT"), index=True)
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True
    )
    measurement_boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("metering_measurement_boundary.id", ondelete="SET NULL"), index=True
    )
    allocation_role: Mapped[str] = mapped_column(String(32), index=True)
    allocation_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    external_facility_code: Mapped[str | None] = mapped_column(String(96), index=True)
    external_facility_name: Mapped[str | None] = mapped_column(String(255))
    area_code_snapshot: Mapped[str] = mapped_column(String(64))
    area_name_snapshot: Mapped[str] = mapped_column(String(128))
    area_path_snapshot: Mapped[str | None] = mapped_column(String(512))
    equipment_code_snapshot: Mapped[str | None] = mapped_column(String(96))
    equipment_name_snapshot: Mapped[str | None] = mapped_column(String(128))
    source_kind: Mapped[str] = mapped_column(String(32), default="manual", index=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)


class GhgEvidenceFile(TeamScopedMixin, BigIntAuditBase):
    """Versioned evidence metadata with a content hash."""

    __tablename__ = "ghg_evidence_file"
    __table_args__ = (UniqueConstraint("team_id", "evidence_code", name="uq_ghg_evidence_code"),)

    evidence_code: Mapped[str] = mapped_column(String(96), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(64), index=True)
    document_no: Mapped[str | None] = mapped_column(String(128))
    issuer: Mapped[str | None] = mapped_column(String(255))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    storage_key: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    confidentiality: Mapped[str] = mapped_column(String(24), default="internal")
    verification_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)


class GhgEvidenceLink(TeamScopedMixin, BigIntAuditBase):
    """Many-to-many evidence link to a canonical business record."""

    __tablename__ = "ghg_evidence_link"
    __table_args__ = (
        UniqueConstraint("team_id", "link_code", name="uq_ghg_evidence_link_code"),
        Index("ix_ghg_evidence_link_record", "team_id", "record_type", "record_code"),
    )

    link_code: Mapped[str] = mapped_column(String(96), index=True)
    record_type: Mapped[str] = mapped_column(String(48), index=True)
    record_code: Mapped[str] = mapped_column(String(96), index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("ghg_evidence_file.id", ondelete="CASCADE"), index=True)
    evidence_role: Mapped[str] = mapped_column(String(32), index=True)
    page_or_cell_reference: Mapped[str | None] = mapped_column(String(128))
    coverage_ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    review_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    reviewer: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GhgCalculationRun(TeamScopedMixin, BigIntAuditBase):
    """Frozen calculation context for a reporting profile and inventory."""

    __tablename__ = "ghg_calculation_run"
    __table_args__ = (
        UniqueConstraint("team_id", "run_code", name="uq_ghg_calculation_run_code"),
        Index("ix_ghg_calculation_run_inventory", "team_id", "inventory_code", "status"),
    )

    run_code: Mapped[str] = mapped_column(String(96), index=True)
    inventory_code: Mapped[str] = mapped_column(String(96), index=True)
    reporting_profile_id: Mapped[int] = mapped_column(
        ForeignKey("ghg_reporting_profile.id", ondelete="RESTRICT"), index=True
    )
    reporting_org_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_reporting_organization.id", ondelete="SET NULL"), index=True
    )
    reporting_period_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_reporting_period.id", ondelete="SET NULL"), index=True
    )
    organization_boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_organization_boundary.id", ondelete="SET NULL"), index=True
    )
    default_scope2_method: Mapped[str] = mapped_column(String(24), default="location", index=True)
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    summary_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    quality_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    total_co2e_kg: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GhgParameterAssignment(TeamScopedMixin, BigIntAuditBase):
    """Parameter value selected for one activity within one calculation run."""

    __tablename__ = "ghg_parameter_assignment"
    __table_args__ = (
        UniqueConstraint("team_id", "run_id", "activity_id", "parameter_code", name="uq_ghg_assignment_parameter"),
        Index("ix_ghg_assignment_activity_run", "team_id", "activity_id", "run_id"),
    )

    run_id: Mapped[int] = mapped_column(ForeignKey("ghg_calculation_run.id", ondelete="CASCADE"), index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("ghg_activity_record.id", ondelete="CASCADE"), index=True)
    method_id: Mapped[int] = mapped_column(
        ForeignKey("ghg_calculation_method_definition.id", ondelete="RESTRICT"), index=True
    )
    parameter_value_id: Mapped[int | None] = mapped_column(
        ForeignKey("ghg_parameter_value.id", ondelete="SET NULL"), index=True
    )
    parameter_code: Mapped[str] = mapped_column(String(64), index=True)
    parameter_role: Mapped[str] = mapped_column(String(32))
    value: Mapped[Decimal] = mapped_column(Numeric(24, 12))
    unit: Mapped[str] = mapped_column(String(64))
    source_mode: Mapped[str] = mapped_column(String(32))
    source_name: Mapped[str] = mapped_column(String(255))
    source_version: Mapped[str | None] = mapped_column(String(64))
    standard_code: Mapped[str | None] = mapped_column(String(128))
    clause_reference: Mapped[str | None] = mapped_column(String(128))
    table_reference: Mapped[str | None] = mapped_column(String(128))
    selection_rule: Mapped[str] = mapped_column(String(255))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class GhgCalculationResult(TeamScopedMixin, BigIntAuditBase):
    """Per-gas result and complete reproducible calculation snapshot."""

    __tablename__ = "ghg_calculation_result"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "run_id",
            "activity_id",
            "gas_code",
            "scope2_method",
            "result_kind",
            name="uq_ghg_calculation_result_dimension",
        ),
        Index("ix_ghg_calculation_result_inventory", "team_id", "run_id", "iso_category_code"),
        Index(
            "ix_ghg_result_run_scope_method_quality",
            "team_id",
            "run_id",
            "ghg_scope",
            "scope2_method",
            "quality_status",
        ),
    )

    run_id: Mapped[int] = mapped_column(ForeignKey("ghg_calculation_run.id", ondelete="CASCADE"), index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("ghg_activity_record.id", ondelete="CASCADE"), index=True)
    method_id: Mapped[int] = mapped_column(
        ForeignKey("ghg_calculation_method_definition.id", ondelete="RESTRICT"), index=True
    )
    iso_category_code: Mapped[str] = mapped_column(String(8), index=True)
    ghg_scope: Mapped[str] = mapped_column(String(16), index=True)
    gas_code: Mapped[str] = mapped_column(String(32), index=True)
    gas_mass_kg: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    gwp_value: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal(1))
    gwp_version: Mapped[str] = mapped_column(String(64))
    co2e_kg: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    scope2_method: Mapped[str] = mapped_column(String(24), default="not_applicable")
    result_kind: Mapped[str] = mapped_column(String(24), default="emission", index=True)
    formula_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    quality_status: Mapped[str] = mapped_column(String(24), default="pass", index=True)


class GhgInventoryReport(TeamScopedMixin, BigIntAuditBase):
    """Versioned internal organization-inventory report frozen from one run."""

    __tablename__ = "ghg_inventory_report"
    __table_args__ = (
        UniqueConstraint("team_id", "report_code", "version", name="uq_ghg_inventory_report_version"),
        Index("ix_ghg_inventory_report_context", "team_id", "reporting_org_id", "reporting_period_id", "status"),
    )

    report_code: Mapped[str] = mapped_column(String(96), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(255))
    inventory_code: Mapped[str] = mapped_column(String(96), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ghg_calculation_run.id", ondelete="RESTRICT"), index=True)
    reporting_org_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_reporting_organization.id", ondelete="RESTRICT"), index=True
    )
    reporting_period_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_reporting_period.id", ondelete="RESTRICT"), index=True
    )
    organization_boundary_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_organization_boundary.id", ondelete="RESTRICT"), index=True
    )
    reporting_profile_id: Mapped[int] = mapped_column(
        ForeignKey("ghg_reporting_profile.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    content_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metrics_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    change_summary: Mapped[str | None] = mapped_column(Text)
    submitted_by: Mapped[str | None] = mapped_column(String(128))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GhgInventoryReportReview(TeamScopedMixin, BigIntAuditBase):
    """Immutable internal review action for an inventory report version."""

    __tablename__ = "ghg_inventory_report_review"
    __table_args__ = (Index("ix_ghg_inventory_report_review", "team_id", "report_id", "acted_at"),)

    report_id: Mapped[int] = mapped_column(ForeignKey("ghg_inventory_report.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(24), index=True)
    from_status: Mapped[str] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    actor: Mapped[str] = mapped_column(String(128))
    comment: Mapped[str | None] = mapped_column(Text)
    acted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GhgImportBatch(TeamScopedMixin, BigIntAuditBase):
    """Auditable preview/commit lifecycle for one category workbook."""

    __tablename__ = "ghg_import_batch"
    __table_args__ = (
        UniqueConstraint("team_id", "batch_code", name="uq_ghg_import_batch_code"),
        Index("ix_ghg_import_batch_inventory", "team_id", "inventory_code", "status"),
    )

    batch_code: Mapped[str] = mapped_column(String(96), index=True)
    inventory_code: Mapped[str] = mapped_column(String(96), index=True)
    reporting_period_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_reporting_period.id", ondelete="SET NULL"), index=True
    )
    organization_code: Mapped[str] = mapped_column(String(96))
    facility_code: Mapped[str] = mapped_column(String(96))
    iso_category_code: Mapped[str] = mapped_column(String(8), index=True)
    reporting_profile_code: Mapped[str] = mapped_column(String(96))
    method_code: Mapped[str] = mapped_column(String(32))
    template_version: Mapped[str] = mapped_column(String(32))
    file_name: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), default="previewed", index=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    missing_evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    preview_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GhgImportIssue(TeamScopedMixin, BigIntAuditBase):
    """Stable, row-level workbook validation result."""

    __tablename__ = "ghg_import_issue"
    __table_args__ = (Index("ix_ghg_import_issue_batch_severity", "team_id", "batch_id", "severity"),)

    batch_id: Mapped[int] = mapped_column(ForeignKey("ghg_import_batch.id", ondelete="CASCADE"), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    sheet_name: Mapped[str] = mapped_column(String(64))
    row_number: Mapped[int | None] = mapped_column(Integer)
    field_code: Mapped[str | None] = mapped_column(String(96))
    issue_code: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(String(512))
    current_value: Mapped[str | None] = mapped_column(String(255))
    suggestion: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
