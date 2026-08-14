"""SQLAlchemy persistence models owned by the microgrid bounded context."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from advanced_alchemy.base import BigIntAuditBase
from sqlalchemy import (
    JSON,
    Boolean,
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


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(UTC)


class MicrogridSite(TeamScopedMixin, BigIntAuditBase):
    """Tenant-owned microgrid site and topology root."""

    __tablename__ = "microgrid_site"
    __table_args__ = (UniqueConstraint("team_id", "code", name="uq_microgrid_site_team_code"),)

    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    pcc_capacity_kw: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    monitor_sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"), index=True
    )
    topology_version: Mapped[int] = mapped_column(Integer, default=1)
    topology: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="shadow", index=True)
    source_name: Mapped[str] = mapped_column(String(128), default="企业配置")


class MicrogridAsset(TeamScopedMixin, BigIntAuditBase):
    """Dispatchable or observable resource within a microgrid site."""

    __tablename__ = "microgrid_asset"
    __table_args__ = (
        UniqueConstraint("team_id", "site_id", "code", name="uq_microgrid_asset_team_site_code"),
        Index("ix_microgrid_asset_site_type", "team_id", "site_id", "asset_type"),
    )

    site_id: Mapped[int] = mapped_column(ForeignKey("microgrid_site.id", ondelete="CASCADE"), index=True)
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True
    )
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    asset_type: Mapped[str] = mapped_column(String(32), index=True)
    rated_power_kw: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    rated_energy_kwh: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    controllable: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_kind: Mapped[str] = mapped_column(String(32), default="enterprise_assumption", index=True)
    source_name: Mapped[str] = mapped_column(String(128), default="祥泰演示V1")
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.50"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class MicrogridAssetMeterBinding(TeamScopedMixin, BigIntAuditBase):
    """Explicit, effective-dated mapping from a microgrid resource to a platform meter."""

    __tablename__ = "microgrid_asset_meter_binding"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "site_id",
            "asset_id",
            "equipment_id",
            "point_code",
            "direction",
            name="uq_microgrid_binding_resource_meter",
        ),
        Index("ix_microgrid_binding_site_role", "team_id", "site_id", "role", "enabled"),
    )

    site_id: Mapped[int] = mapped_column(ForeignKey("microgrid_site.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("microgrid_asset.id", ondelete="CASCADE"), index=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("dataapp_monitorequipment.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    point_code: Mapped[str] = mapped_column(String(64), default="forward_active_total")
    direction: Mapped[str] = mapped_column(String(16), default="import")
    sign: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal(1))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_kind: Mapped[str] = mapped_column(String(32), default="manual_configuration")
    source_name: Mapped[str] = mapped_column(String(128), default="管理员手工绑定")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class MicrogridScenario(TeamScopedMixin, BigIntAuditBase):
    """Immutable-on-publish operating parameter snapshot."""

    __tablename__ = "microgrid_scenario"
    __table_args__ = (
        UniqueConstraint("team_id", "site_id", "code", "version", name="uq_microgrid_scenario_version"),
        Index("ix_microgrid_scenario_site_status", "team_id", "site_id", "status"),
    )

    site_id: Mapped[int] = mapped_column(ForeignKey("microgrid_site.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    asset_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    source_kind: Mapped[str] = mapped_column(String(32), default="enterprise_assumption")
    source_name: Mapped[str] = mapped_column(String(128), default="祥泰演示V1")
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.50"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tariff_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_energytariffplan.id", ondelete="SET NULL"), index=True
    )
    grid_emission_factor_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_emissionfactor.id", ondelete="SET NULL"), index=True
    )
    based_on_scenario_id: Mapped[int | None] = mapped_column(
        ForeignKey("microgrid_scenario.id", ondelete="SET NULL"), index=True
    )
    change_summary: Mapped[str | None] = mapped_column(String(255))


class FlexibilityContract(TeamScopedMixin, BigIntAuditBase):
    """Versioned dispatch envelope for a controllable resource."""

    __tablename__ = "microgrid_flexibility_contract"
    __table_args__ = (
        UniqueConstraint("team_id", "scenario_id", "asset_id", name="uq_microgrid_flex_contract_asset"),
        Index("ix_microgrid_flex_contract_active", "team_id", "scenario_id", "enabled"),
    )

    scenario_id: Mapped[int] = mapped_column(ForeignKey("microgrid_scenario.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("microgrid_asset.id", ondelete="CASCADE"), index=True)
    contract_type: Mapped[str] = mapped_column(String(32), index=True)
    start_minute: Mapped[int] = mapped_column(Integer, default=0)
    end_minute: Mapped[int] = mapped_column(Integer, default=1440)
    minimum_power_kw: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal(0))
    maximum_power_kw: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    target_energy_kwh: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    priority: Mapped[int] = mapped_column(Integer, default=50)
    penalty_cny_per_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal(5))
    recovery_constraints: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class MicrogridTelemetryFact(TeamScopedMixin, BigIntAuditBase):
    """Normalized microgrid telemetry and derived time-series fact."""

    __tablename__ = "microgrid_telemetry_fact"
    __table_args__ = (
        UniqueConstraint(
            "team_id", "asset_id", "metric_code", "observed_at", "source_kind", name="uq_microgrid_telemetry_point"
        ),
        Index("ix_microgrid_telemetry_series", "team_id", "asset_id", "metric_code", "observed_at"),
    )

    site_id: Mapped[int] = mapped_column(ForeignKey("microgrid_site.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("microgrid_asset.id", ondelete="CASCADE"), index=True)
    metric_code: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(24))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_kind: Mapped[str] = mapped_column(String(32), index=True)
    source_ref: Mapped[str | None] = mapped_column(String(255))
    quality: Mapped[str] = mapped_column(String(24), default="A", index=True)


class MicrogridWeatherFact(TeamScopedMixin, BigIntAuditBase):
    """Weather observation, reanalysis, or forecast valid for a site."""

    __tablename__ = "microgrid_weather_fact"
    __table_args__ = (
        UniqueConstraint("team_id", "site_id", "valid_at", "source_kind", name="uq_microgrid_weather_valid"),
        Index("ix_microgrid_weather_series", "team_id", "site_id", "valid_at"),
    )

    site_id: Mapped[int] = mapped_column(ForeignKey("microgrid_site.id", ondelete="CASCADE"), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    relative_humidity_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    cloud_cover_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    wind_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    ghi_wm2: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    dni_wm2: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    dhi_wm2: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    source_kind: Mapped[str] = mapped_column(String(32), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    provider_model: Mapped[str | None] = mapped_column(String(64))


class MicrogridAssetState(TeamScopedMixin, BigIntAuditBase):
    """Latest asset-state projection optimized for operations pages."""

    __tablename__ = "microgrid_asset_state"
    __table_args__ = (UniqueConstraint("team_id", "asset_id", name="uq_microgrid_asset_state_asset"),)

    asset_id: Mapped[int] = mapped_column(ForeignKey("microgrid_asset.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    online: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    operating_mode: Mapped[str] = mapped_column(String(32), default="shadow")
    active_power_kw: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal(0))
    soc_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    alarm_level: Mapped[str] = mapped_column(String(24), default="normal", index=True)
    source_kind: Mapped[str] = mapped_column(String(32), default="simulated")


class ForecastRun(TeamScopedMixin, BigIntAuditBase):
    """Forecast execution and frozen input metadata."""

    __tablename__ = "microgrid_forecast_run"
    __table_args__ = (UniqueConstraint("team_id", "idempotency_key", name="uq_microgrid_forecast_idempotency"),)

    site_id: Mapped[int] = mapped_column(ForeignKey("microgrid_site.id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("microgrid_scenario.id", ondelete="RESTRICT"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    horizon_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    horizon_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    model_version: Mapped[str] = mapped_column(String(64), default="hybrid-demo-v1")
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    quality_status: Mapped[str] = mapped_column(String(16), default="warning", index=True)
    quality_checks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    history_source_kind: Mapped[str] = mapped_column(String(32), default="simulated", index=True)
    history_coverage_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))


class ForecastPoint(TeamScopedMixin, BigIntAuditBase):
    """Quantile point produced by a forecast run."""

    __tablename__ = "microgrid_forecast_point"
    __table_args__ = (
        UniqueConstraint("team_id", "run_id", "series_code", "valid_at", name="uq_microgrid_forecast_point"),
        Index("ix_microgrid_forecast_point_series", "team_id", "run_id", "series_code", "valid_at"),
    )

    run_id: Mapped[int] = mapped_column(ForeignKey("microgrid_forecast_run.id", ondelete="CASCADE"), index=True)
    series_code: Mapped[str] = mapped_column(String(32), index=True)
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    p10: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    p50: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    p90: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(24))


class OptimizationRun(TeamScopedMixin, BigIntAuditBase):
    """MILP execution, objective breakdown, and constraint diagnostics."""

    __tablename__ = "microgrid_optimization_run"
    __table_args__ = (UniqueConstraint("team_id", "idempotency_key", name="uq_microgrid_optimization_idempotency"),)

    site_id: Mapped[int] = mapped_column(ForeignKey("microgrid_site.id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("microgrid_scenario.id", ondelete="RESTRICT"), index=True)
    forecast_run_id: Mapped[int] = mapped_column(
        ForeignKey("microgrid_forecast_run.id", ondelete="RESTRICT"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    solver: Mapped[str] = mapped_column(String(32), default="highs")
    solver_seconds: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    mip_gap: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    objective_cny: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    baseline_cost_cny: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    savings_cny: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    peak_reduction_kw: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    carbon_reduction_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cost_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    diagnostics: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(String(16), default="operational", index=True)
    baseline_peak_kw: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    optimized_peak_kw: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    peak_change_kw: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))


class OptimizationSchedulePoint(TeamScopedMixin, BigIntAuditBase):
    """One interval of an optimized dispatch plan."""

    __tablename__ = "microgrid_optimization_schedule_point"
    __table_args__ = (
        UniqueConstraint("team_id", "run_id", "valid_at", name="uq_microgrid_schedule_point"),
        Index("ix_microgrid_schedule_series", "team_id", "run_id", "valid_at"),
    )

    run_id: Mapped[int] = mapped_column(ForeignKey("microgrid_optimization_run.id", ondelete="CASCADE"), index=True)
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    load_kw: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    pv_kw: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    grid_import_kw: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    grid_export_kw: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(0))
    battery_charge_kw: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(0))
    battery_discharge_kw: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(0))
    charger_kw: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(0))
    lighting_kw: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(0))
    generator_kw: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(0))
    curtailed_pv_kw: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(0))
    soc_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    tariff_cny_per_kwh: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    interval_cost_cny: Mapped[Decimal] = mapped_column(Numeric(18, 6))


class DispatchBatch(TeamScopedMixin, BigIntAuditBase):
    """Shadow dispatch batch submitted from a feasible schedule."""

    __tablename__ = "microgrid_dispatch_batch"
    __table_args__ = (UniqueConstraint("team_id", "idempotency_key", name="uq_microgrid_dispatch_idempotency"),)

    optimization_run_id: Mapped[int] = mapped_column(
        ForeignKey("microgrid_optimization_run.id", ondelete="RESTRICT"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    adapter_code: Mapped[str] = mapped_column(String(64), default="simulation-v1")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    command_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DispatchReceipt(TeamScopedMixin, BigIntAuditBase):
    """Auditable shadow-control command receipt."""

    __tablename__ = "microgrid_dispatch_receipt"
    __table_args__ = (
        UniqueConstraint("team_id", "batch_id", "command_key", name="uq_microgrid_dispatch_receipt_command"),
        Index("ix_microgrid_dispatch_receipt_batch_status", "team_id", "batch_id", "status"),
    )

    batch_id: Mapped[int] = mapped_column(ForeignKey("microgrid_dispatch_batch.id", ondelete="CASCADE"), index=True)
    command_key: Mapped[str] = mapped_column(String(128), index=True)
    asset_code: Mapped[str] = mapped_column(String(64), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    target_power_kw: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    executed_power_kw: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    status: Mapped[str] = mapped_column(String(24), index=True)
    reason: Mapped[str | None] = mapped_column(String(255))


__all__ = (
    "DispatchBatch",
    "DispatchReceipt",
    "FlexibilityContract",
    "ForecastPoint",
    "ForecastRun",
    "MicrogridAsset",
    "MicrogridAssetMeterBinding",
    "MicrogridAssetState",
    "MicrogridScenario",
    "MicrogridSite",
    "MicrogridTelemetryFact",
    "MicrogridWeatherFact",
    "OptimizationRun",
    "OptimizationSchedulePoint",
)
