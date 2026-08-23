"""Tenant-scoped metering governance and projection models."""

from __future__ import annotations

from datetime import date, datetime  # noqa: TC003 - SQLAlchemy resolves mapped annotations at runtime.
from decimal import Decimal
from typing import Any

from advanced_alchemy.base import BigIntAuditBase
from sqlalchemy import (
    JSON,
    BigInteger,
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.lib.tenancy import TeamScopedMixin


class MeasurementBoundary(TeamScopedMixin, BigIntAuditBase):
    """A versioned electricity measurement boundary for one tenant."""

    __tablename__ = "metering_measurement_boundary"
    __table_args__ = (
        UniqueConstraint("team_id", "code", name="uq_metering_boundary_team_code"),
        Index("ix_metering_boundary_scope2_active", "team_id", "include_in_scope2", "status", "valid_from"),
    )

    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    boundary_type: Mapped[str] = mapped_column(String(32), default="meter_circuit", index=True)
    meter_equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True
    )
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"), index=True
    )
    use_system_code: Mapped[str | None] = mapped_column(String(64), index=True)
    energy_direction: Mapped[str] = mapped_column(String(16), default="import")
    include_in_scope2: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    mapping_version: Mapped[str] = mapped_column(String(32), default="v1")
    source_name: Mapped[str | None] = mapped_column(String(128))
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    remark: Mapped[str | None] = mapped_column(Text)


class MeasurementBoundaryMember(TeamScopedMixin, BigIntAuditBase):
    """An area, equipment, or equipment-group member covered by a boundary."""

    __tablename__ = "metering_measurement_boundary_member"
    __table_args__ = (
        UniqueConstraint("team_id", "boundary_id", "member_code", name="uq_metering_boundary_member_code"),
        Index("ix_metering_boundary_member_effective", "team_id", "confirmation_status", "valid_from", "valid_to"),
    )

    boundary_id: Mapped[int] = mapped_column(
        ForeignKey("metering_measurement_boundary.id", ondelete="CASCADE"), index=True
    )
    member_code: Mapped[str] = mapped_column(String(64))
    member_type: Mapped[str] = mapped_column(String(24), index=True)
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"), index=True
    )
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True
    )
    member_role: Mapped[str] = mapped_column(String(24), default="covered")
    allocation_weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    confirmation_status: Mapped[str] = mapped_column(String(24), default="candidate", index=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source_name: Mapped[str | None] = mapped_column(String(128))
    remark: Mapped[str | None] = mapped_column(Text)


class MeteringAcquisitionCursor(TeamScopedMixin, BigIntAuditBase):
    """Per-meter cursor for resumable API and collector ingestion."""

    __tablename__ = "metering_acquisition_cursor"
    __table_args__ = (
        UniqueConstraint("team_id", "source_system", "equipment_id", name="uq_metering_cursor_source_equipment"),
        Index("ix_metering_cursor_status", "team_id", "source_system", "status"),
    )

    source_system: Mapped[str] = mapped_column(String(32), index=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("dataapp_monitorequipment.id", ondelete="CASCADE"), index=True)
    last_attempt_time: Mapped[datetime | None] = mapped_column(DateTime)
    last_success_time: Mapped[datetime | None] = mapped_column(DateTime)
    source_watermark: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    error_detail: Mapped[str | None] = mapped_column(Text)
    cursor_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class DataMigrationRun(TeamScopedMixin, BigIntAuditBase):
    """Checkpoint and audit record for a resumable data migration."""

    __tablename__ = "metering_data_migration_run"
    __table_args__ = (
        UniqueConstraint("team_id", "run_code", name="uq_metering_migration_run_team_code"),
        Index("ix_metering_migration_status", "team_id", "migration_type", "status"),
    )

    run_code: Mapped[str] = mapped_column(String(96), index=True)
    migration_type: Mapped[str] = mapped_column(String(48), index=True)
    source_table: Mapped[str] = mapped_column(String(96))
    target_table: Mapped[str] = mapped_column(String(96))
    from_time: Mapped[datetime | None] = mapped_column(DateTime)
    to_time: Mapped[datetime | None] = mapped_column(DateTime)
    source_high_watermark: Mapped[str | None] = mapped_column(String(160))
    last_source_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    source_rows: Mapped[int] = mapped_column(Integer, default=0)
    target_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    source_checksum: Mapped[str | None] = mapped_column(String(64))
    target_checksum: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_detail: Mapped[str | None] = mapped_column(Text)
    run_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class EnergyProjectionRun(TeamScopedMixin, BigIntAuditBase):
    """Immutable execution record for interval and Scope 2 projections."""

    __tablename__ = "metering_energy_projection_run"
    __table_args__ = (
        UniqueConstraint("team_id", "run_code", name="uq_metering_projection_run_team_code"),
        Index("ix_metering_projection_period", "team_id", "period_start", "period_end", "status"),
    )

    run_code: Mapped[str] = mapped_column(String(96), index=True)
    projection_type: Mapped[str] = mapped_column(String(32), default="electricity_interval", index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    mapping_version: Mapped[str] = mapped_column(String(32), default="v1")
    source_high_watermark: Mapped[str | None] = mapped_column(String(160))
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    output_count: Mapped[int] = mapped_column(Integer, default=0)
    issue_count: Mapped[int] = mapped_column(Integer, default=0)
    source_checksum: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    run_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_detail: Mapped[str | None] = mapped_column(Text)


class MeteringQualityIssue(TeamScopedMixin, BigIntAuditBase):
    """An auditable data quality issue produced during projection."""

    __tablename__ = "metering_quality_issue"
    __table_args__ = (
        UniqueConstraint("team_id", "issue_key", name="uq_metering_quality_issue_team_key"),
        Index("ix_metering_quality_issue_team_status", "team_id", "status", "severity"),
    )

    issue_key: Mapped[str] = mapped_column(String(160), index=True)
    projection_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("metering_energy_projection_run.id", ondelete="CASCADE"), index=True
    )
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True
    )
    point_code: Mapped[str | None] = mapped_column(String(64))
    reading_time: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    issue_type: Mapped[str] = mapped_column(String(48), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="warning", index=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    detail: Mapped[str | None] = mapped_column(Text)
    issue_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Scope2ElectricityReconciliation(TeamScopedMixin, BigIntAuditBase):
    """Versioned organization electricity total with bill-over-meter precedence."""

    __tablename__ = "metering_scope2_electricity_reconciliation"
    __current_revision_scoped__ = True
    __table_args__ = (
        UniqueConstraint("team_id", "billing_month", "revision_no", name="uq_scope2_reconciliation_month_revision"),
        Index("ix_scope2_reconciliation_current", "team_id", "billing_month", "is_current"),
        Index("ix_scope2_reconciliation_activity", "activity_record_id"),
        Index(
            "uq_scope2_reconciliation_one_current",
            "team_id",
            "billing_month",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
    )

    billing_month: Mapped[str] = mapped_column(String(7), index=True)
    projection_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("metering_energy_projection_run.id", ondelete="SET NULL"), index=True
    )
    activity_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("ghg_activity_record.id", ondelete="SET NULL")
    )
    source_priority: Mapped[str] = mapped_column(String(24), default="meter_aggregate", index=True)
    organization_total_kwh: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    meter_total_kwh: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    bill_total_kwh: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    allocated_kwh: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(0))
    unallocated_kwh: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(0))
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("metering_scope2_electricity_reconciliation.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    source_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
