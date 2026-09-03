from __future__ import annotations

# ruff: noqa: RUF002, RUF003, TC003
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from advanced_alchemy.base import BigIntAuditBase, BigIntBase
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.tenancy import TeamScopedMixin


def utc_now_naive() -> datetime:
    """Return naive UTC for legacy timestamp-without-time-zone columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class DataFeatureMixin:
    """通用数据特征属性（Scope1/2/3 公共）。"""

    data_source: Mapped[str] = mapped_column(String(20))
    collection_method: Mapped[str] = mapped_column(String(20))
    confidence_level: Mapped[str] = mapped_column(String(10))
    data_year_type: Mapped[str] = mapped_column(String(20))
    data_year: Mapped[int | None] = mapped_column(Integer)
    record_usage: Mapped[str] = mapped_column(String(24), default="operational", index=True)
    source_record_no: Mapped[str | None] = mapped_column(String(128), index=True)
    source_version: Mapped[int] = mapped_column(Integer, default=1)
    voucher_no: Mapped[str | None] = mapped_column(String(128), index=True)
    evidence_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    source_hash: Mapped[str | None] = mapped_column(String(64), index=True)


class EnterpriseInfo(TeamScopedMixin, BigIntBase):
    """企业信息（对应 Django dataapp.EnterpriseInfo）。"""

    __tablename__ = "dataapp_enterpriseinfo"

    name: Mapped[str | None] = mapped_column(String(100))
    belong_unit: Mapped[str | None] = mapped_column(String(100))
    people_count: Mapped[int | None] = mapped_column(Integer)
    park_area: Mapped[float | None] = mapped_column(Float)
    unify_code: Mapped[str | None] = mapped_column(String(30))
    industry: Mapped[str | None] = mapped_column(String(30))
    store_area: Mapped[float | None] = mapped_column(Float)
    green_area: Mapped[float | None] = mapped_column(Float)
    location: Mapped[str | None] = mapped_column(String(50))
    other_info: Mapped[dict[str, Any] | None] = mapped_column(comment="其他信息")


class EmployeeCommute(TeamScopedMixin, BigIntBase):
    """员工通勤（对应 Django dataapp.EmployeeCommute）。"""

    __tablename__ = "dataapp_employeecommute"

    name: Mapped[str] = mapped_column(String(10))
    category: Mapped[str | None] = mapped_column(String(10))
    car_power_type: Mapped[int | None] = mapped_column(Integer, default=1, doc="0=柴油, 1=汽油, 2=电力")
    mileage: Mapped[float | None] = mapped_column(Float, default=0.0)
    unit_consumption: Mapped[float | None] = mapped_column(Float, default=0.0)


class MonitorSector(TeamScopedMixin, BigIntBase):
    """监控区域（对应 Django dataapp.MonitorSector）。"""

    __tablename__ = "dataapp_monitorsector"

    __table_args__ = (UniqueConstraint("team_id", "code", name="uq_dataapp_monitorsector_team_code"),)

    code: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"),
        index=True,
    )
    area_type: Mapped[str | None] = mapped_column(String(32), index=True)
    path: Mapped[str | None] = mapped_column(String(255), index=True)
    level: Mapped[int | None] = mapped_column(Integer, default=0)
    sort_index: Mapped[int | None] = mapped_column(Integer, default=0)
    area: Mapped[str | None] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(Text)
    manager_name: Mapped[str | None] = mapped_column(String(64))
    owner_department: Mapped[str | None] = mapped_column(String(64))
    location_desc: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)
    area_id: Mapped[int | None] = mapped_column(Integer)
    is_enable: Mapped[bool | None] = mapped_column(Boolean, default=True)

    parent: Mapped[MonitorSector | None] = relationship(
        remote_side="MonitorSector.id",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[list[MonitorSector]] = relationship(
        back_populates="parent",
        lazy="selectin",
    )
    photos: Mapped[list[MonitorSectorPhoto]] = relationship(
        back_populates="sector",
        lazy="selectin",
    )


class MonitorSectorPhoto(TeamScopedMixin, BigIntBase):
    """监控区域照片（对应 Django dataapp.MonitorSectorPhoto）。"""

    __tablename__ = "dataapp_monitorsectorphoto"

    path: Mapped[str | None] = mapped_column(String(255))
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"),
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)
    area_id: Mapped[int | None] = mapped_column(Integer)

    sector: Mapped[MonitorSector | None] = relationship(
        back_populates="photos",
        lazy="selectin",
    )


class DeviceType(BigIntBase):
    """设备类型字典。"""

    __tablename__ = "dataapp_devicetype"
    __table_args__ = (UniqueConstraint("code", name="uq_dataapp_devicetype_code"),)

    code: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(64))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_devicetype.id", ondelete="SET NULL"),
        index=True,
    )
    parent_code: Mapped[str | None] = mapped_column(String(32), index=True)
    energy_type: Mapped[str | None] = mapped_column(String(32))
    is_energy_device: Mapped[bool] = mapped_column(Boolean, default=False)
    is_special_equipment: Mapped[bool] = mapped_column(Boolean, default=False)
    default_protocol: Mapped[str | None] = mapped_column(String(20))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    remark: Mapped[str | None] = mapped_column(Text)

    parent: Mapped[DeviceType | None] = relationship(
        remote_side="DeviceType.id",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[list[DeviceType]] = relationship(
        back_populates="parent",
        lazy="selectin",
    )
    equipments: Mapped[list[MonitorEquipment]] = relationship(
        back_populates="device_type",
        lazy="selectin",
    )


class EnergyType(BigIntBase):
    """能源品种与折标口径字典。"""

    __tablename__ = "dataapp_energytype"
    __table_args__ = (
        UniqueConstraint("code", name="uq_dataapp_energytype_code"),
        Index("ix_dataapp_energytype_category_scope", "category", "default_scope"),
    )

    code: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32), index=True)
    default_scope: Mapped[str] = mapped_column(String(16), index=True)
    original_unit: Mapped[str | None] = mapped_column(String(16))
    standard_unit: Mapped[str | None] = mapped_column(String(16), default="kgce")
    standard_factor: Mapped[Numeric | None] = mapped_column(Numeric(18, 8), doc="原始单位折算为 standard_unit 的系数")
    standard_code: Mapped[str | None] = mapped_column(String(64))
    conversion_factor_source: Mapped[str | None] = mapped_column(String(255))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    remark: Mapped[str | None] = mapped_column(Text)


class EnergyUnitConversion(BigIntBase):
    """能源业务单位到折标基准单位的换算字典。"""

    __tablename__ = "dataapp_energyunitconversion"
    __table_args__ = (
        UniqueConstraint("energy_type_code", "from_unit", "to_unit", name="uq_energy_unit_conversion_type_units"),
        Index("ix_energy_unit_conversion_type_enabled", "energy_type_code", "is_enabled"),
    )

    energy_type_code: Mapped[str] = mapped_column(String(32), index=True)
    from_unit: Mapped[str] = mapped_column(String(16))
    to_unit: Mapped[str] = mapped_column(String(16))
    multiply_factor: Mapped[Numeric] = mapped_column(Numeric(18, 10))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    conversion_factor_source: Mapped[str | None] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    remark: Mapped[str | None] = mapped_column(Text)


class EnergyUseSystem(TeamScopedMixin, BigIntAuditBase):
    """用能系统字典, 用于能源分析和策略推荐."""

    __tablename__ = "dataapp_energyusesystem"
    __table_args__ = (
        UniqueConstraint("team_id", "code", name="uq_energy_use_system_team_code"),
        Index("ix_energy_use_system_team_type", "team_id", "system_type"),
    )

    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    system_type: Mapped[str] = mapped_column(String(32), index=True)
    parent_code: Mapped[str | None] = mapped_column(String(64), index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    remark: Mapped[str | None] = mapped_column(Text)


class EnergyUseSystemBinding(TeamScopedMixin, BigIntAuditBase):
    """设备、区域与用能系统的归类关系."""

    __tablename__ = "dataapp_energyusesystembinding"
    __table_args__ = (
        UniqueConstraint("team_id", "system_code", "equipment_id", name="uq_energy_use_system_binding_equipment"),
        Index("ix_energy_use_system_binding_system", "team_id", "system_code"),
        Index("ix_energy_use_system_binding_resource", "equipment_id", "sector_id"),
    )

    system_code: Mapped[str] = mapped_column(String(64), index=True)
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True
    )
    equipment_code: Mapped[str | None] = mapped_column(String(64), index=True)
    equipment_name: Mapped[str | None] = mapped_column(String(128))
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"), index=True
    )
    area_id: Mapped[str | None] = mapped_column(String(32), index=True)
    area_name: Mapped[str | None] = mapped_column(String(128))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    remark: Mapped[str | None] = mapped_column(Text)


class EnergyTariffPlan(TeamScopedMixin, BigIntAuditBase):
    """能源价格方案, 支持尖峰平谷等分时成本分析."""

    __tablename__ = "dataapp_energytariffplan"
    __table_args__ = (
        UniqueConstraint("team_id", "code", name="uq_energy_tariff_plan_team_code"),
        Index("ix_energy_tariff_plan_team_type", "team_id", "energy_type_code"),
    )

    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    energy_type_code: Mapped[str] = mapped_column(String(32), index=True)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    remark: Mapped[str | None] = mapped_column(Text)


class EnergyTariffSegment(TeamScopedMixin, BigIntAuditBase):
    """能源价格方案的分时段价格."""

    __tablename__ = "dataapp_energytariffsegment"
    __table_args__ = (Index("ix_energy_tariff_segment_plan", "team_id", "plan_id", "segment_type"),)

    plan_id: Mapped[int] = mapped_column(ForeignKey("dataapp_energytariffplan.id", ondelete="CASCADE"), index=True)
    segment_type: Mapped[str] = mapped_column(String(16), index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(16), default="CNY/kWh")
    sort_index: Mapped[int] = mapped_column(Integer, default=0)
    remark: Mapped[str | None] = mapped_column(Text)


class EnergyBenchmarkProfile(TeamScopedMixin, BigIntAuditBase):
    """行业标杆方案。"""

    __tablename__ = "dataapp_energybenchmarkprofile"
    __table_args__ = (Index("ix_energy_benchmark_profile_enabled", "team_id", "is_enabled"),)

    name: Mapped[str] = mapped_column(String(128), index=True)
    industry_name: Mapped[str | None] = mapped_column(String(128), index=True)
    scenario: Mapped[str | None] = mapped_column(String(128), index=True)
    library_type: Mapped[str | None] = mapped_column(String(32), default="enterprise_internal", index=True)
    source_name: Mapped[str | None] = mapped_column(String(128))
    source_url: Mapped[str | None] = mapped_column(String(512))
    source_hash: Mapped[str | None] = mapped_column(String(64))
    source_file_name: Mapped[str | None] = mapped_column(String(255))
    standard_code: Mapped[str | None] = mapped_column(String(128), index=True)
    version_status: Mapped[str | None] = mapped_column(String(32), default="active", index=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    remark: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list[EnergyBenchmarkItem]] = relationship(
        back_populates="profile",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class EnergyBenchmarkItem(TeamScopedMixin, BigIntAuditBase):
    """行业标杆指标项。"""

    __tablename__ = "dataapp_energybenchmarkitem"
    __table_args__ = (
        Index("ix_energy_benchmark_item_profile_metric", "team_id", "profile_id", "target_type", "metric_code"),
        Index("ix_energy_benchmark_item_enabled", "team_id", "is_enabled"),
        Index("ix_energy_benchmark_item_target", "team_id", "target_type", "target_code"),
    )

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("dataapp_energybenchmarkprofile.id", ondelete="CASCADE"), index=True
    )
    target_type: Mapped[str] = mapped_column(String(32), index=True)
    target_code: Mapped[str | None] = mapped_column(String(128), index=True)
    target_name: Mapped[str | None] = mapped_column(String(128))
    metric_code: Mapped[str] = mapped_column(String(64), index=True)
    metric_name: Mapped[str] = mapped_column(String(128))
    benchmark_value: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(32))
    standard_code: Mapped[str | None] = mapped_column(String(128), index=True)
    source_url: Mapped[str | None] = mapped_column(String(512))
    source_hash: Mapped[str | None] = mapped_column(String(64))
    applicable_industry: Mapped[str | None] = mapped_column(String(128), index=True)
    applicable_category: Mapped[str | None] = mapped_column(String(128), index=True)
    applicable_condition: Mapped[str | None] = mapped_column(Text)
    metric_direction: Mapped[str | None] = mapped_column(String(32), default="lower_is_better")
    advanced_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    saving_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    access_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    advanced_level: Mapped[str | None] = mapped_column(String(64))
    saving_level: Mapped[str | None] = mapped_column(String(64))
    access_level: Mapped[str | None] = mapped_column(String(64))
    standard_level: Mapped[str | None] = mapped_column(String(32), index=True)
    version_status: Mapped[str | None] = mapped_column(String(32), default="active", index=True)
    reference_standard: Mapped[str | None] = mapped_column(String(255))
    excellent_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    warning_threshold_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), default=10)
    severe_threshold_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), default=25)
    source_name: Mapped[str | None] = mapped_column(String(128))
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    remark: Mapped[str | None] = mapped_column(Text)

    profile: Mapped[EnergyBenchmarkProfile] = relationship(
        back_populates="items",
        lazy="selectin",
    )


class EnergyOptimizationRecord(TeamScopedMixin, BigIntAuditBase):
    """能效平衡优化前后对比记录。"""

    __tablename__ = "dataapp_energyoptimizationrecord"
    __table_args__ = (
        Index("ix_energy_optimization_record_period", "team_id", "period_start", "period_end"),
        Index("ix_energy_optimization_record_object", "team_id", "balance_object_type", "balance_object_code"),
        Index("ix_energy_optimization_record_scenario", "team_id", "scenario_type"),
    )

    balance_object_type: Mapped[str] = mapped_column(String(32), default="enterprise", index=True)
    balance_object_code: Mapped[str | None] = mapped_column(String(128), index=True)
    balance_object_name: Mapped[str | None] = mapped_column(String(128))
    period_start: Mapped[date | None] = mapped_column(Date, index=True)
    period_end: Mapped[date | None] = mapped_column(Date, index=True)
    scenario_type: Mapped[str] = mapped_column(String(48), index=True)
    scenario_name: Mapped[str] = mapped_column(String(128))
    before_parameters: Mapped[dict | None] = mapped_column(JSON)
    after_parameters: Mapped[dict | None] = mapped_column(JSON)
    baseline_energy: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    expected_energy: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    saving_energy: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    saving_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    cost_delta_cny: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    method: Mapped[str | None] = mapped_column(String(64))
    assumptions: Mapped[dict | None] = mapped_column(JSON)
    source_name: Mapped[str | None] = mapped_column(String(128))
    source_type: Mapped[str | None] = mapped_column(String(32))
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="simulated", index=True)
    remark: Mapped[str | None] = mapped_column(Text)


class EnergyCarbonBudgetPlan(TeamScopedMixin, BigIntAuditBase):
    """用能与碳排放预算方案。"""

    __tablename__ = "dataapp_energycarbonbudgetplan"
    __table_args__ = (
        UniqueConstraint("team_id", "code", name="uq_energy_carbon_budget_plan_team_code"),
        Index("ix_energy_carbon_budget_plan_year_status", "team_id", "budget_year", "status"),
        Index("ix_energy_carbon_budget_plan_scope", "team_id", "target_scope", "target_code"),
    )

    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    budget_year: Mapped[int] = mapped_column(Integer, index=True)
    period_type: Mapped[str] = mapped_column(String(16), default="annual", index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    target_scope: Mapped[str] = mapped_column(String(32), default="enterprise", index=True)
    target_code: Mapped[str | None] = mapped_column(String(128), index=True)
    target_name: Mapped[str | None] = mapped_column(String(128))
    energy_budget_tce: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    carbon_budget_co2e: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    denominator_plan: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    denominator_unit: Mapped[str | None] = mapped_column(String(32))
    energy_intensity_budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    carbon_intensity_budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    source_name: Mapped[str | None] = mapped_column(String(128))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    remark: Mapped[str | None] = mapped_column(Text)

    allocations: Mapped[list[EnergyCarbonBudgetAllocation]] = relationship(
        back_populates="plan",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    adjustments: Mapped[list[EnergyCarbonBudgetAdjustment]] = relationship(
        back_populates="plan",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class EnergyCarbonBudgetAllocation(TeamScopedMixin, BigIntAuditBase):
    """能碳预算月度分解。"""

    __tablename__ = "dataapp_energycarbonbudgetallocation"
    __table_args__ = (
        UniqueConstraint("team_id", "plan_id", "period_month", name="uq_energy_carbon_budget_allocation_plan_month"),
        Index("ix_energy_carbon_budget_allocation_plan", "team_id", "plan_id", "period_month"),
        Index("ix_energy_carbon_budget_allocation_scope", "team_id", "target_scope", "target_code"),
    )

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("dataapp_energycarbonbudgetplan.id", ondelete="CASCADE"), index=True
    )
    period_month: Mapped[date] = mapped_column(Date, index=True)
    target_scope: Mapped[str] = mapped_column(String(32), default="enterprise", index=True)
    target_code: Mapped[str | None] = mapped_column(String(128), index=True)
    target_name: Mapped[str | None] = mapped_column(String(128))
    energy_budget_tce: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    carbon_budget_co2e: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    denominator_budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    denominator_unit: Mapped[str | None] = mapped_column(String(32))
    energy_intensity_budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    carbon_intensity_budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    source_name: Mapped[str | None] = mapped_column(String(128))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    remark: Mapped[str | None] = mapped_column(Text)

    plan: Mapped[EnergyCarbonBudgetPlan] = relationship(
        back_populates="allocations",
        lazy="selectin",
    )
    adjustments: Mapped[list[EnergyCarbonBudgetAdjustment]] = relationship(
        back_populates="allocation",
        lazy="selectin",
    )


class EnergyCarbonBudgetAdjustment(TeamScopedMixin, BigIntAuditBase):
    """能碳预算调整记录。"""

    __tablename__ = "dataapp_energycarbonbudgetadjustment"
    __table_args__ = (
        UniqueConstraint("team_id", "adjustment_no", name="uq_energy_carbon_budget_adjustment_team_no"),
        Index("ix_energy_carbon_budget_adjustment_plan", "team_id", "plan_id", "status"),
        Index("ix_energy_carbon_budget_adjustment_month", "team_id", "effective_month"),
    )

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("dataapp_energycarbonbudgetplan.id", ondelete="CASCADE"), index=True
    )
    allocation_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_energycarbonbudgetallocation.id", ondelete="SET NULL"),
        index=True,
    )
    adjustment_no: Mapped[str] = mapped_column(String(64), index=True)
    adjustment_type: Mapped[str] = mapped_column(String(32), default="reforecast", index=True)
    effective_month: Mapped[date | None] = mapped_column(Date, index=True)
    original_energy_budget_tce: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    original_carbon_budget_co2e: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    adjusted_energy_budget_tce: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    adjusted_carbon_budget_co2e: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    requested_by: Mapped[str | None] = mapped_column(String(64))
    approved_by: Mapped[str | None] = mapped_column(String(64))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_name: Mapped[str | None] = mapped_column(String(128))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    remark: Mapped[str | None] = mapped_column(Text)

    plan: Mapped[EnergyCarbonBudgetPlan] = relationship(
        back_populates="adjustments",
        lazy="selectin",
    )
    allocation: Mapped[EnergyCarbonBudgetAllocation | None] = relationship(
        back_populates="adjustments",
        lazy="selectin",
    )


class EnergyIntervalFact(TeamScopedMixin, BigIntAuditBase):
    """由原始计量数据聚合得到的小时/日能源消费事实."""

    __tablename__ = "dataapp_energyintervalfact"
    __current_revision_scoped__ = True
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "source_system",
            "source_record_id",
            "revision_no",
            name="uq_energy_interval_team_source_record_revision",
        ),
        Index("ix_energy_interval_team_period", "team_id", "period_start", "period_end"),
        Index("ix_energy_interval_resource", "equipment_id", "area_id", "energy_type_code"),
        Index("ix_energy_interval_current_period", "team_id", "is_current", "granularity", "period_start"),
    )

    source_system: Mapped[str] = mapped_column(String(32), default="meter_interval")
    source_record_id: Mapped[str] = mapped_column(String(128))
    energy_type_code: Mapped[str] = mapped_column(String(32), index=True)
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True
    )
    equipment_code: Mapped[str | None] = mapped_column(String(64), index=True)
    equipment_name: Mapped[str | None] = mapped_column(String(128))
    area_id: Mapped[str | None] = mapped_column(String(32), index=True)
    area_name: Mapped[str | None] = mapped_column(String(128))
    use_system_code: Mapped[str | None] = mapped_column(String(64), index=True)
    use_system_name: Mapped[str | None] = mapped_column(String(128))
    granularity: Mapped[str] = mapped_column(String(16), default="hour", index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(16), default="kWh")
    cost_cny: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    tariff_segment_type: Mapped[str | None] = mapped_column(String(16), index=True)
    reading_count: Mapped[int | None] = mapped_column(Integer)
    data_quality: Mapped[str] = mapped_column(String(24), default="measured", index=True)
    projection_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("metering_energy_projection_run.id", ondelete="SET NULL"), index=True
    )
    measurement_boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("metering_measurement_boundary.id", ondelete="SET NULL"), index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_energyintervalfact.id", ondelete="SET NULL"), index=True
    )
    source_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    remark: Mapped[str | None] = mapped_column(Text)


class EquipmentWorkloadFact(TeamScopedMixin, BigIntAuditBase):
    """设备运行时间、处理量、作业次数等负荷事实."""

    __tablename__ = "dataapp_equipmentworkloadfact"
    __table_args__ = (
        UniqueConstraint(
            "team_id", "source_system", "source_record_id", name="uq_equipment_workload_team_source_record"
        ),
        Index("ix_equipment_workload_team_period", "team_id", "period_start", "period_end"),
        Index("ix_equipment_workload_resource", "equipment_id", "area_id", "workload_type"),
    )

    source_system: Mapped[str] = mapped_column(String(32), default="manual")
    source_record_id: Mapped[str] = mapped_column(String(128))
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True
    )
    equipment_code: Mapped[str | None] = mapped_column(String(64), index=True)
    equipment_name: Mapped[str | None] = mapped_column(String(128))
    area_id: Mapped[str | None] = mapped_column(String(32), index=True)
    area_name: Mapped[str | None] = mapped_column(String(128))
    use_system_code: Mapped[str | None] = mapped_column(String(64), index=True)
    workload_type: Mapped[str] = mapped_column(String(32), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime, index=True)
    workload_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    workload_unit: Mapped[str] = mapped_column(String(16))
    run_hours: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    record_status: Mapped[str] = mapped_column(String(16), default="confirmed", index=True)
    remark: Mapped[str | None] = mapped_column(Text)


class InMoney(TeamScopedMixin, BigIntBase):
    """入库金额管理（对应 Django dataapp.InMoney）。"""

    __tablename__ = "dataapp_inmoney"

    rkdbh: Mapped[str] = mapped_column(String(20), default="")
    gysmc: Mapped[str | None] = mapped_column(String(100))
    gysbm: Mapped[str | None] = mapped_column(String(15))
    rkrq: Mapped[str | None] = mapped_column(String(30))
    wlbh: Mapped[str | None] = mapped_column(String(15))
    wlms: Mapped[str | None] = mapped_column(String(300))
    pc: Mapped[str | None] = mapped_column(String(15))
    jldw: Mapped[str | None] = mapped_column(String(10))
    shsl: Mapped[float | None] = mapped_column(Float)
    shdj: Mapped[float | None] = mapped_column(Float)
    shje: Mapped[float | None] = mapped_column(Float)
    ckmc: Mapped[str | None] = mapped_column(String(50))
    add_time: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)


class OutMoney(TeamScopedMixin, BigIntBase):
    """出库金额管理（对应 Django dataapp.OutMoney）。"""

    __tablename__ = "dataapp_outmoney"

    ckdbh: Mapped[str] = mapped_column(String(20), default="")
    xmmc: Mapped[str | None] = mapped_column(String(200))
    xmdy: Mapped[str | None] = mapped_column(String(15))
    wlbm: Mapped[str | None] = mapped_column(String(15))
    wlms: Mapped[str | None] = mapped_column(String(300))
    pc: Mapped[str | None] = mapped_column(String(15))
    jldw: Mapped[str | None] = mapped_column(String(10))
    sfsl: Mapped[float | None] = mapped_column(Float)
    dj: Mapped[float | None] = mapped_column(Float)
    je: Mapped[float | None] = mapped_column(Float)
    gzrq: Mapped[str | None] = mapped_column(String(30))
    gysmc: Mapped[str | None] = mapped_column(String(100))
    gc: Mapped[str | None] = mapped_column(String(100))
    lldh: Mapped[str | None] = mapped_column(String(15))
    ckdd: Mapped[str | None] = mapped_column(String(100))
    add_time: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)


class ProductionProduct(TeamScopedMixin, BigIntAuditBase):
    """产品/产出对象字典, 服务能源强度分母, 不承载产品碳足迹模型."""

    __tablename__ = "dataapp_productionproduct"
    __table_args__ = (
        UniqueConstraint("team_id", "code", name="uq_dataapp_productionproduct_team_code"),
        Index("ix_production_product_team_category", "team_id", "category"),
    )

    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    spec: Mapped[str | None] = mapped_column(String(128))
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    output_kind: Mapped[str] = mapped_column(String(32), default="product", index=True)
    default_unit: Mapped[str | None] = mapped_column(String(16))
    standard_unit: Mapped[str | None] = mapped_column(String(16))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    remark: Mapped[str | None] = mapped_column(Text)


class ProductPrice(TeamScopedMixin, BigIntAuditBase):
    """产品/产出对象价格台账, 服务产值分母和经济分配辅助."""

    __tablename__ = "dataapp_productprice"
    __table_args__ = (
        Index("ix_product_price_team_product_type", "team_id", "product_code", "price_type"),
        Index("ix_product_price_validity", "valid_from", "valid_to"),
    )

    product_code: Mapped[str] = mapped_column(String(64), index=True)
    price_type: Mapped[str] = mapped_column(String(32), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    tax_included: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_from: Mapped[date] = mapped_column(Date, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, index=True)
    source_system: Mapped[str | None] = mapped_column(String(32))
    source_record_id: Mapped[str | None] = mapped_column(String(128))
    remark: Mapped[str | None] = mapped_column(Text)


class ProductionOutputFact(TeamScopedMixin, BigIntAuditBase):
    """产量/处理量/作业量事实, 服务能源强度分母."""

    __tablename__ = "dataapp_productionoutputfact"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "source_system",
            "source_record_id",
            name="uq_production_output_team_source_record",
        ),
        Index("ix_production_output_team_product_period", "team_id", "product_code", "period_start"),
        Index("ix_production_output_resource", "line_code", "area_id", "equipment_code"),
    )

    source_system: Mapped[str] = mapped_column(String(32), default="manual")
    source_record_id: Mapped[str] = mapped_column(String(128))
    production_order_no: Mapped[str | None] = mapped_column(String(64), index=True)
    batch_no: Mapped[str | None] = mapped_column(String(64), index=True)
    product_code: Mapped[str] = mapped_column(String(64), index=True)
    product_name: Mapped[str | None] = mapped_column(String(128))
    product_spec: Mapped[str | None] = mapped_column(String(128))
    output_kind: Mapped[str] = mapped_column(String(32), default="product", index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    good_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    scrap_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    rework_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(16))
    standard_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    standard_unit: Mapped[str | None] = mapped_column(String(16))
    quality_status: Mapped[str | None] = mapped_column(String(32), index=True)
    record_status: Mapped[str] = mapped_column(String(16), default="confirmed", index=True)
    work_center_code: Mapped[str | None] = mapped_column(String(64), index=True)
    line_code: Mapped[str | None] = mapped_column(String(64), index=True)
    area_id: Mapped[int | None] = mapped_column(Integer, index=True)
    area_name: Mapped[str | None] = mapped_column(String(128))
    equipment_code: Mapped[str | None] = mapped_column(String(64), index=True)
    equipment_name: Mapped[str | None] = mapped_column(String(128))
    remark: Mapped[str | None] = mapped_column(Text)


class ProductionResourceBinding(TeamScopedMixin, BigIntAuditBase):
    """产品/产出对象与产线/区域/设备可选挂接关系."""

    __tablename__ = "dataapp_productionresourcebinding"
    __table_args__ = (
        Index("ix_production_binding_team_product", "team_id", "product_code"),
        Index("ix_production_binding_resource", "work_center_code", "line_code", "area_id", "equipment_id"),
    )

    product_code: Mapped[str] = mapped_column(String(64), index=True)
    work_center_code: Mapped[str | None] = mapped_column(String(64), index=True)
    line_code: Mapped[str | None] = mapped_column(String(64), index=True)
    area_id: Mapped[int | None] = mapped_column(Integer, index=True)
    equipment_id: Mapped[int | None] = mapped_column(Integer, index=True)
    binding_type: Mapped[str] = mapped_column(String(16), default="primary", index=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    remark: Mapped[str | None] = mapped_column(Text)


class ProductFootprintStudy(TeamScopedMixin, BigIntAuditBase):
    """Product carbon footprint study aggregate root."""

    __tablename__ = "carbon_product_footprint_study"
    __table_args__ = (
        UniqueConstraint("team_id", "study_code", name="uq_product_footprint_study_team_code"),
        Index("ix_product_footprint_study_product", "team_id", "product_code", "status"),
        Index("ix_product_footprint_study_period", "team_id", "period_start", "period_end"),
    )

    study_code: Mapped[str] = mapped_column(String(64), index=True)
    study_name: Mapped[str] = mapped_column(String(128))
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_productionproduct.id", ondelete="SET NULL"), index=True
    )
    product_code: Mapped[str] = mapped_column(String(64), index=True)
    product_name: Mapped[str | None] = mapped_column(String(128))
    product_spec: Mapped[str | None] = mapped_column(String(128))
    product_category: Mapped[str | None] = mapped_column(String(64), index=True)
    standard_code: Mapped[str] = mapped_column(String(64), default="ISO 14067")
    standard_name: Mapped[str | None] = mapped_column(String(255))
    pcr_code: Mapped[str | None] = mapped_column(String(128))
    functional_unit: Mapped[str | None] = mapped_column(String(128))
    declared_unit: Mapped[str | None] = mapped_column(String(128))
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    boundary_type: Mapped[str] = mapped_column(String(32), default="cradle_to_gate", index=True)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    result_status: Mapped[str] = mapped_column(String(32), default="not_calculated", index=True)
    source_name: Mapped[str | None] = mapped_column(String(128))
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    remark: Mapped[str | None] = mapped_column(Text)

    product: Mapped[ProductionProduct | None] = relationship(lazy="selectin")
    boundary: Mapped[ProductSystemBoundary | None] = relationship(
        back_populates="study",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    stages: Mapped[list[ProductLifeCycleStage]] = relationship(
        back_populates="study",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    inventory_items: Mapped[list[ProductFootprintInventoryItem]] = relationship(
        back_populates="study",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    allocation_rules: Mapped[list[ProductFootprintAllocationRule]] = relationship(
        back_populates="study",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    results: Mapped[list[ProductFootprintResult]] = relationship(
        back_populates="study",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ProductSystemBoundary(TeamScopedMixin, BigIntAuditBase):
    """Lifecycle and product-system boundary for one PCF study."""

    __tablename__ = "carbon_product_system_boundary"
    __table_args__ = (
        UniqueConstraint("team_id", "study_id", name="uq_product_system_boundary_team_study"),
        Index("ix_product_system_boundary_type", "team_id", "boundary_type"),
    )

    study_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_product_footprint_study.id", ondelete="CASCADE"), index=True
    )
    boundary_type: Mapped[str] = mapped_column(String(32), default="cradle_to_gate", index=True)
    included_stages: Mapped[list | None] = mapped_column(JSON)
    excluded_stages: Mapped[list | None] = mapped_column(JSON)
    cutoff_rule: Mapped[str | None] = mapped_column(Text)
    geography: Mapped[str | None] = mapped_column(String(128))
    technology_scope: Mapped[str | None] = mapped_column(String(255))
    temporal_scope: Mapped[str | None] = mapped_column(String(128))
    assumption: Mapped[str | None] = mapped_column(Text)
    standard_code: Mapped[str | None] = mapped_column(String(64))
    source_name: Mapped[str | None] = mapped_column(String(128))

    study: Mapped[ProductFootprintStudy] = relationship(back_populates="boundary", lazy="selectin")


class ProductLifeCycleStage(TeamScopedMixin, BigIntAuditBase):
    """Lifecycle stage included in a product carbon footprint study."""

    __tablename__ = "carbon_product_lifecycle_stage"
    __table_args__ = (
        UniqueConstraint("team_id", "study_id", "stage_code", name="uq_product_lifecycle_stage_team_code"),
        Index("ix_product_lifecycle_stage_study", "team_id", "study_id", "sequence"),
    )

    study_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_product_footprint_study.id", ondelete="CASCADE"), index=True
    )
    stage_code: Mapped[str] = mapped_column(String(64), index=True)
    stage_name: Mapped[str] = mapped_column(String(128))
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    included: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    study: Mapped[ProductFootprintStudy] = relationship(back_populates="stages", lazy="selectin")
    inventory_items: Mapped[list[ProductFootprintInventoryItem]] = relationship(back_populates="stage", lazy="selectin")


class ProductFootprintInventoryItem(TeamScopedMixin, BigIntAuditBase):
    """Activity-data row inside a product carbon footprint study."""

    __tablename__ = "carbon_product_footprint_inventory_item"
    __table_args__ = (
        UniqueConstraint("team_id", "study_id", "item_no", name="uq_product_footprint_item_team_no"),
        Index("ix_product_footprint_item_stage", "team_id", "study_id", "stage_id"),
        Index("ix_product_footprint_item_status", "team_id", "study_id", "calc_status"),
    )

    study_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_product_footprint_study.id", ondelete="CASCADE"), index=True
    )
    stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_product_lifecycle_stage.id", ondelete="SET NULL"), index=True
    )
    item_no: Mapped[str] = mapped_column(String(64), index=True)
    activity_type: Mapped[str] = mapped_column(String(32), index=True)
    item_name: Mapped[str] = mapped_column(String(255))
    activity_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    activity_unit: Mapped[str | None] = mapped_column(String(32))
    factor_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_emissionfactor.id", ondelete="SET NULL"), index=True
    )
    factor_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    factor_unit: Mapped[str | None] = mapped_column(String(64))
    factor_source: Mapped[str | None] = mapped_column(String(255))
    supplier_pcf_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    supplier_pcf_unit: Mapped[str | None] = mapped_column(String(64))
    supplier_name: Mapped[str | None] = mapped_column(String(128))
    allocation_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal(1))
    computed_co2e: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    calc_status: Mapped[str] = mapped_column(String(32), default="pending_factor", index=True)
    data_quality: Mapped[str | None] = mapped_column(String(32), index=True)
    source_type: Mapped[str | None] = mapped_column(String(32), index=True)
    source_ref: Mapped[str | None] = mapped_column(String(255))
    evidence_path: Mapped[str | None] = mapped_column(String(512))
    included: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    remark: Mapped[str | None] = mapped_column(Text)

    study: Mapped[ProductFootprintStudy] = relationship(back_populates="inventory_items", lazy="selectin")
    stage: Mapped[ProductLifeCycleStage | None] = relationship(back_populates="inventory_items", lazy="selectin")
    factor: Mapped[EmissionFactor | None] = relationship(lazy="selectin")


class ProductFootprintAllocationRule(TeamScopedMixin, BigIntAuditBase):
    """Allocation rule used by a product carbon footprint study."""

    __tablename__ = "carbon_product_footprint_allocation_rule"
    __table_args__ = (
        Index("ix_product_footprint_allocation_study", "team_id", "study_id"),
        Index("ix_product_footprint_allocation_method", "team_id", "allocation_method"),
    )

    study_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_product_footprint_study.id", ondelete="CASCADE"), index=True
    )
    process_code: Mapped[str | None] = mapped_column(String(64), index=True)
    process_name: Mapped[str] = mapped_column(String(128))
    allocation_method: Mapped[str] = mapped_column(String(32), default="physical", index=True)
    basis: Mapped[str | None] = mapped_column(String(128))
    ratio: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal(1))
    source_name: Mapped[str | None] = mapped_column(String(128))
    remark: Mapped[str | None] = mapped_column(Text)

    study: Mapped[ProductFootprintStudy] = relationship(back_populates="allocation_rules", lazy="selectin")


class ProductFootprintResult(TeamScopedMixin, BigIntAuditBase):
    """Versioned calculation result of a product carbon footprint study."""

    __tablename__ = "carbon_product_footprint_result"
    __table_args__ = (
        UniqueConstraint("team_id", "study_id", "result_version", name="uq_product_footprint_result_team_version"),
        Index("ix_product_footprint_result_status", "team_id", "study_id", "result_status"),
    )

    study_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_product_footprint_study.id", ondelete="CASCADE"), index=True
    )
    result_version: Mapped[int] = mapped_column(Integer, default=1)
    total_co2e: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(0))
    unit: Mapped[str] = mapped_column(String(32), default="kgCO2e")
    footprint_per_declared_unit: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    result_status: Mapped[str] = mapped_column(String(32), default="calculated", index=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    inventory_count: Mapped[int] = mapped_column(Integer, default=0)
    missing_factor_count: Mapped[int] = mapped_column(Integer, default=0)
    stage_payload: Mapped[list | None] = mapped_column(JSON)
    result_payload: Mapped[dict | None] = mapped_column(JSON)
    report_status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    remark: Mapped[str | None] = mapped_column(Text)

    study: Mapped[ProductFootprintStudy] = relationship(back_populates="results", lazy="selectin")


class SupplyChainSupplier(TeamScopedMixin, BigIntAuditBase):
    """Supplier profile for supply-chain carbon collaboration."""

    __tablename__ = "carbon_supply_chain_supplier"
    __table_args__ = (
        UniqueConstraint("team_id", "supplier_code", name="uq_supply_chain_supplier_team_code"),
        Index("ix_supply_chain_supplier_status", "team_id", "status", "risk_level"),
        Index("ix_supply_chain_supplier_industry", "team_id", "industry"),
    )

    supplier_code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128), index=True)
    supplier_type: Mapped[str | None] = mapped_column(String(32), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(64))
    contact_email: Mapped[str | None] = mapped_column(String(128))
    country_region: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    source_name: Mapped[str | None] = mapped_column(String(128))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    remark: Mapped[str | None] = mapped_column(Text)

    sites: Mapped[list[SupplierSite]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan", lazy="selectin"
    )
    tasks: Mapped[list[SupplierDisclosureTask]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan", lazy="selectin"
    )


class SupplierSite(TeamScopedMixin, BigIntAuditBase):
    """Supplier site or facility used for supplier carbon data scope."""

    __tablename__ = "carbon_supplier_site"
    __table_args__ = (
        UniqueConstraint("team_id", "supplier_id", "site_code", name="uq_supplier_site_team_code"),
        Index("ix_supplier_site_supplier_status", "team_id", "supplier_id", "status"),
    )

    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_supply_chain_supplier.id", ondelete="CASCADE"), index=True
    )
    site_code: Mapped[str] = mapped_column(String(64), index=True)
    site_name: Mapped[str] = mapped_column(String(128))
    country_region: Mapped[str | None] = mapped_column(String(128))
    address: Mapped[str | None] = mapped_column(String(255))
    facility_scope: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    remark: Mapped[str | None] = mapped_column(Text)

    supplier: Mapped[SupplyChainSupplier] = relationship(back_populates="sites", lazy="selectin")


class SupplierDisclosureTask(TeamScopedMixin, BigIntAuditBase):
    """Supplier disclosure and data-collection task aggregate root."""

    __tablename__ = "carbon_supplier_disclosure_task"
    __table_args__ = (
        UniqueConstraint("team_id", "task_no", name="uq_supplier_disclosure_task_team_no"),
        Index("ix_supplier_disclosure_task_supplier_status", "team_id", "supplier_id", "status"),
        Index("ix_supplier_disclosure_task_period", "team_id", "period_start", "period_end"),
    )

    task_no: Mapped[str] = mapped_column(String(64), index=True)
    task_name: Mapped[str] = mapped_column(String(128))
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_supply_chain_supplier.id", ondelete="CASCADE"), index=True
    )
    task_type: Mapped[str] = mapped_column(String(32), default="mixed", index=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_productionproduct.id", ondelete="SET NULL"), index=True
    )
    product_code: Mapped[str | None] = mapped_column(String(64), index=True)
    product_name: Mapped[str | None] = mapped_column(String(128))
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime)
    requested_by: Mapped[str | None] = mapped_column(String(128))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    source_name: Mapped[str | None] = mapped_column(String(128))
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    remark: Mapped[str | None] = mapped_column(Text)

    supplier: Mapped[SupplyChainSupplier] = relationship(back_populates="tasks", lazy="selectin")
    product: Mapped[ProductionProduct | None] = relationship(lazy="selectin")
    data_items: Mapped[list[SupplierCarbonData]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin"
    )
    evidence_items: Mapped[list[SupplierEvidence]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin"
    )
    review_decisions: Mapped[list[SupplierReviewDecision]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin"
    )
    releases: Mapped[list[SupplierDisclosureRelease]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin"
    )


class SupplierCarbonData(TeamScopedMixin, BigIntAuditBase):
    """Supplier activity or PCF data submitted under a disclosure task."""

    __tablename__ = "carbon_supplier_carbon_data"
    __table_args__ = (
        UniqueConstraint("team_id", "task_id", "data_no", name="uq_supplier_carbon_data_team_no"),
        Index("ix_supplier_carbon_data_supplier_type", "team_id", "supplier_id", "data_type"),
        Index("ix_supplier_carbon_data_status", "team_id", "task_id", "status"),
    )

    task_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_supplier_disclosure_task.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_supply_chain_supplier.id", ondelete="CASCADE"), index=True
    )
    data_no: Mapped[str] = mapped_column(String(64), index=True)
    data_type: Mapped[str] = mapped_column(String(32), default="activity", index=True)
    scope_category: Mapped[str | None] = mapped_column(String(64), index=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_productionproduct.id", ondelete="SET NULL"), index=True
    )
    product_code: Mapped[str | None] = mapped_column(String(64), index=True)
    product_name: Mapped[str | None] = mapped_column(String(128))
    material_code: Mapped[str | None] = mapped_column(String(64), index=True)
    material_name: Mapped[str | None] = mapped_column(String(128))
    activity_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    activity_unit: Mapped[str | None] = mapped_column(String(32))
    pcf_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pcf_unit: Mapped[str | None] = mapped_column(String(64))
    co2e_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    factor_source: Mapped[str | None] = mapped_column(String(255))
    boundary_type: Mapped[str | None] = mapped_column(String(32), index=True)
    data_quality: Mapped[str] = mapped_column(String(32), default="supplier_reported", index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    validity_start: Mapped[date | None] = mapped_column(Date)
    validity_end: Mapped[date | None] = mapped_column(Date)
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_ref: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    published_to_scope3: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_to_pcf: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    remark: Mapped[str | None] = mapped_column(Text)

    task: Mapped[SupplierDisclosureTask] = relationship(back_populates="data_items", lazy="selectin")
    supplier: Mapped[SupplyChainSupplier] = relationship(lazy="selectin")
    product: Mapped[ProductionProduct | None] = relationship(lazy="selectin")


class SupplierEvidence(TeamScopedMixin, BigIntAuditBase):
    """Evidence submitted for a supplier disclosure task."""

    __tablename__ = "carbon_supplier_evidence"
    __table_args__ = (
        UniqueConstraint("team_id", "task_id", "evidence_no", name="uq_supplier_evidence_team_no"),
        Index("ix_supplier_evidence_task_status", "team_id", "task_id", "review_status"),
    )

    task_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_supplier_disclosure_task.id", ondelete="CASCADE"), index=True
    )
    evidence_no: Mapped[str] = mapped_column(String(64), index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(String(512))
    file_sha256: Mapped[str | None] = mapped_column(String(64))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    review_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    submitted_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(Text)

    task: Mapped[SupplierDisclosureTask] = relationship(back_populates="evidence_items", lazy="selectin")


class SupplierReviewDecision(TeamScopedMixin, BigIntAuditBase):
    """Review decision for supplier task submission."""

    __tablename__ = "carbon_supplier_review_decision"
    __table_args__ = (Index("ix_supplier_review_decision_task", "team_id", "task_id", "decision"),)

    task_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_supplier_disclosure_task.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(24), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

    task: Mapped[SupplierDisclosureTask] = relationship(back_populates="review_decisions", lazy="selectin")


class SupplierDisclosureRelease(TeamScopedMixin, BigIntAuditBase):
    """Frozen downstream disclosure record for approved supplier data."""

    __tablename__ = "carbon_supplier_disclosure_release"
    __table_args__ = (
        UniqueConstraint("team_id", "release_no", name="uq_supplier_disclosure_release_team_no"),
        Index("ix_supplier_disclosure_release_task", "team_id", "task_id", "status"),
    )

    release_no: Mapped[str] = mapped_column(String(64), index=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_supplier_disclosure_task.id", ondelete="CASCADE"), index=True
    )
    release_type: Mapped[str] = mapped_column(String(32), default="customer_disclosure", index=True)
    recipient_name: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    payload: Mapped[dict | None] = mapped_column(JSON)
    remark: Mapped[str | None] = mapped_column(Text)

    task: Mapped[SupplierDisclosureTask] = relationship(back_populates="releases", lazy="selectin")


class MonitorEquipment(TeamScopedMixin, BigIntBase):
    """监控终端：电表、光伏、摄像头（对应 Django dataapp.MonitorEquipment）。"""

    __tablename__ = "dataapp_monitorequipment"

    __table_args__ = (UniqueConstraint("team_id", "code", name="uq_dataapp_monitorequipment_team_code"),)

    code: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str | None] = mapped_column(String(30))
    external_device_id: Mapped[str | None] = mapped_column(String(64), index=True)
    device_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_devicetype.id", ondelete="SET NULL"),
        index=True,
    )
    parent_device_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"),
        index=True,
    )
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"),
        index=True,
    )
    category: Mapped[int | None] = mapped_column(Integer, doc="0=电表,1=光伏,2=视频摄像头")
    asset_code: Mapped[str | None] = mapped_column(String(64), index=True)
    model: Mapped[str | None] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    owner_unit: Mapped[str | None] = mapped_column(String(100))
    maintainer_name: Mapped[str | None] = mapped_column(String(64))
    warehouse_name: Mapped[str | None] = mapped_column(String(100), index=True)
    warehouse_code: Mapped[str | None] = mapped_column(String(32), index=True)
    energy_type: Mapped[str | None] = mapped_column(String(32), index=True)
    rated_power_kw: Mapped[float | None] = mapped_column(Float)
    energy_efficiency_level: Mapped[int | None] = mapped_column(Integer, index=True)
    energy_efficiency_standard: Mapped[str | None] = mapped_column(String(128))
    network_env: Mapped[str | None] = mapped_column(String(100))
    data_acquisition_method: Mapped[str | None] = mapped_column(String(30))
    running_status: Mapped[str | None] = mapped_column(String(30), index=True)
    commissioning_status: Mapped[str | None] = mapped_column(String(32), index=True)
    supplier: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[int | None] = mapped_column(Integer, doc="0=在线,1=故障")
    trip_state: Mapped[int | None] = mapped_column(Integer, doc="0=合闸,1=跳闸")
    location: Mapped[str | None] = mapped_column(String(50))
    install_time: Mapped[datetime | None] = mapped_column(DateTime)
    last_inspection_at: Mapped[datetime | None] = mapped_column(DateTime)
    inspection_due_at: Mapped[datetime | None] = mapped_column(DateTime)
    registration_code: Mapped[str | None] = mapped_column(String(64))
    remark: Mapped[str | None] = mapped_column(Text)
    sort_index: Mapped[int | None] = mapped_column(Integer, default=0)
    is_enable: Mapped[bool | None] = mapped_column(Boolean, default=True)
    # 采集协议：用于 DataCollectorFactory 选择适配器（参考 PRD 4.1）
    protocol: Mapped[str | None] = mapped_column(String(20), default="http_yunji", doc="MQTT | modbus | http_yunji")

    sector: Mapped[MonitorSector | None] = relationship(
        backref="equipments",
        lazy="selectin",
    )
    parent_device: Mapped[MonitorEquipment | None] = relationship(
        remote_side="MonitorEquipment.id",
        back_populates="child_devices",
        lazy="selectin",
    )
    child_devices: Mapped[list[MonitorEquipment]] = relationship(
        back_populates="parent_device",
        lazy="selectin",
    )
    device_type: Mapped[DeviceType | None] = relationship(
        back_populates="equipments",
        lazy="selectin",
    )
    device_points: Mapped[list[DevicePoint]] = relationship(
        back_populates="device",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class DevicePoint(TeamScopedMixin, BigIntBase):
    """设备测点定义。"""

    __tablename__ = "dataapp_devicepoint"
    __table_args__ = (UniqueConstraint("device_id", "point_code", name="uq_dataapp_devicepoint_device_point"),)

    device_id: Mapped[int] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="CASCADE"),
        index=True,
    )
    point_code: Mapped[str] = mapped_column(String(64))
    point_name: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str | None] = mapped_column(String(20))
    value_type: Mapped[str] = mapped_column(String(16), default="float")
    source_field: Mapped[str | None] = mapped_column(String(64))
    sampling_interval_seconds: Mapped[int | None] = mapped_column(Integer)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_alarm_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    upper_limit: Mapped[float | None] = mapped_column(Float)
    lower_limit: Mapped[float | None] = mapped_column(Float)
    remark: Mapped[str | None] = mapped_column(Text)

    device: Mapped[MonitorEquipment] = relationship(
        back_populates="device_points",
        lazy="selectin",
    )


class VideoMonitor(TeamScopedMixin, BigIntBase):
    """视频监控（对应 Django dataapp.VideoMonitor）。"""

    __tablename__ = "dataapp_videomonitor"

    location: Mapped[str | None] = mapped_column(String(100))
    f_area: Mapped[str | None] = mapped_column(String(50))
    f_area_type: Mapped[str | None] = mapped_column(String(10))
    video_url: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[int | None] = mapped_column(Integer, doc="0=在线,1=故障")
    ip_address: Mapped[str | None] = mapped_column(String(20))
    install_height: Mapped[float | None] = mapped_column(Float, default=0.0)
    install_method: Mapped[str | None] = mapped_column(String(20))
    vedio_type: Mapped[str | None] = mapped_column(String(20))
    pixel: Mapped[str | None] = mapped_column(String(10))
    brand: Mapped[str | None] = mapped_column(String(20))
    b_model: Mapped[str | None] = mapped_column(String(30))
    install_time: Mapped[str | None] = mapped_column(String(30))
    install_x: Mapped[float | None] = mapped_column(Float)
    install_y: Mapped[float | None] = mapped_column(Float)
    add_time: Mapped[datetime | None] = mapped_column(DateTime, default=utc_now_naive)


class ApiResultKeyMapping(BigIntBase):
    """API 结果中英文映射（对应 Django dataapp.ApiResultKeyMapping）。"""

    __tablename__ = "dataapp_apiresultkeymapping"

    key_name: Mapped[str | None] = mapped_column(String(30))
    cn_name: Mapped[str | None] = mapped_column(String(30))


class WarningRule(TeamScopedMixin, BigIntBase):
    """预警规则设置（对应 Django dataapp.WarningRule）。"""

    __tablename__ = "dataapp_warningrule"

    name: Mapped[str] = mapped_column(String(30), default="")
    description: Mapped[str | None] = mapped_column(Text)
    range_val: Mapped[dict | None] = mapped_column(comment="取值范围")
    event_type: Mapped[int] = mapped_column(Integer, default=1, doc="1=设备故障, 2=用电异常, 3=发电异常, 4=碳排放异常")
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"),
        index=True,
    )
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"),
        index=True,
    )
    point_code: Mapped[str | None] = mapped_column(String(64), index=True)
    alarm_code: Mapped[str | None] = mapped_column(String(64), index=True)
    alarm_name: Mapped[str | None] = mapped_column(String(64))
    alarm_level: Mapped[str | None] = mapped_column(String(16), default="warning", index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    table_name: Mapped[str | None] = mapped_column(String(30))


class AlarmEvent(TeamScopedMixin, BigIntBase):
    """预警事件（对应 Django dataapp.AlarmEvent）。"""

    __tablename__ = "dataapp_alarmevent"

    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_warningrule.id", ondelete="SET NULL"),
        index=True,
    )
    event_type: Mapped[int] = mapped_column(Integer, doc="1=设备故障, 2=用电异常, 3=发电异常, 4=碳排放异常")
    alarm_code: Mapped[str | None] = mapped_column(String(64), index=True)
    alarm_name: Mapped[str | None] = mapped_column(String(64))
    alarm_level: Mapped[str | None] = mapped_column(String(16), default="warning", index=True)
    alarm_category: Mapped[str | None] = mapped_column(String(16), default="device", index=True)
    event_desc: Mapped[str | None] = mapped_column(String(300))
    event_time: Mapped[datetime | None] = mapped_column(DateTime)
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"),
        index=True,
    )
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"),
        index=True,
    )
    point_code: Mapped[str | None] = mapped_column(String(64), index=True)
    current_value: Mapped[float | None] = mapped_column(Float)
    threshold_value: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(String(20), default="open", index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    handled_by: Mapped[str | None] = mapped_column(String(64))
    handle_note: Mapped[str | None] = mapped_column(Text)
    add_time: Mapped[datetime | None] = mapped_column(DateTime, default=utc_now_naive)
    is_handle: Mapped[bool | None] = mapped_column(Boolean, default=False)


class VedioAlarmEvent(TeamScopedMixin, BigIntBase):
    """摄像头预警事件（对应 Django dataapp.VedioAlarmEvent）。"""

    __tablename__ = "dataapp_vedioalarmevent"

    event_type: Mapped[int] = mapped_column(Integer, doc="1=未佩戴安全帽, 2=烟火, 3=火点, 4=区域入侵")
    event_desc: Mapped[str | None] = mapped_column(String(300))
    event_time: Mapped[datetime | None] = mapped_column(DateTime)
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_videomonitor.id", ondelete="SET NULL"),
        index=True,
    )
    add_time: Mapped[datetime | None] = mapped_column(DateTime, default=utc_now_naive)
    is_handle: Mapped[bool | None] = mapped_column(Boolean, default=False)


class EnergyStorageValue(TeamScopedMixin, BigIntBase):
    """储能量（对应 Django dataapp.EnergyStorageValue）。"""

    __tablename__ = "dataapp_energystoragevalue"

    cn_total: Mapped[float | None] = mapped_column(Float, default=100)
    ratio_total: Mapped[float | None] = mapped_column(Float, default=1)
    cn1: Mapped[float | None] = mapped_column(Float, default=50)
    ratio1: Mapped[float | None] = mapped_column(Float, default=0.5)
    cn2: Mapped[float | None] = mapped_column(Float, default=50)
    ratio2: Mapped[float | None] = mapped_column(Float, default=0.5)


class Scope2MeterAggregate(TeamScopedMixin, BigIntAuditBase):
    """Scope2 电表月度聚合快照。"""

    __tablename__ = "dataapp_scope2meteraggregate"
    __current_revision_scoped__ = True
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "ammeter_id",
            "billing_month",
            "revision_no",
            name="uq_scope2_meter_aggregate_team_meter_month_revision",
        ),
        Index("ix_scope2_meter_aggregate_team_month_area", "team_id", "billing_month", "area_id"),
        Index("ix_scope2_meter_aggregate_current_month", "team_id", "is_current", "billing_month"),
        Index(
            "uq_scope2_meter_aggregate_one_current",
            "team_id",
            "ammeter_id",
            "billing_month",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
    )

    source_kind: Mapped[str] = mapped_column(String(24), default="meter_aggregate")
    ammeter_id: Mapped[str] = mapped_column(String(20), index=True)
    ammeter_name: Mapped[str | None] = mapped_column(String(30))
    area_id: Mapped[str | None] = mapped_column(String(20), index=True)
    area_name: Mapped[str | None] = mapped_column(String(50))
    billing_month: Mapped[str] = mapped_column(String(7), index=True)
    first_reading_time: Mapped[datetime | None] = mapped_column(DateTime)
    last_reading_time: Mapped[datetime | None] = mapped_column(DateTime)
    start_total_energy: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    end_total_energy: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    total_kwh: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    calc_status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    factor_source: Mapped[str | None] = mapped_column(String(128))
    factor_year: Mapped[int | None] = mapped_column(Integer)
    factor_unit: Mapped[str | None] = mapped_column(String(32))
    activity_amount: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    activity_unit: Mapped[str | None] = mapped_column(String(16))
    computed_co2e: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    computation_note: Mapped[str | None] = mapped_column(Text)
    aggregation_note: Mapped[str | None] = mapped_column(Text)
    projection_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("metering_energy_projection_run.id", ondelete="SET NULL"), index=True
    )
    measurement_boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("metering_measurement_boundary.id", ondelete="SET NULL"), index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_scope2meteraggregate.id", ondelete="SET NULL"), index=True
    )
    source_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class EmissionFactor(BigIntAuditBase):
    """排放因子库（对应 Django dataapp.EmissionFactor）。"""

    __tablename__ = "dataapp_emissionfactor"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "scope",
            "category",
            "sub_category",
            "unit",
            "year",
            name="uq_dataapp_emissionfactor_team_business_key",
        ),
    )

    team_id: Mapped[UUID | None] = mapped_column(ForeignKey("team.id", ondelete="CASCADE"), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(20))
    sub_category: Mapped[str] = mapped_column(String(64))
    unit: Mapped[str] = mapped_column(String(20))
    factor_value: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    factor_unit: Mapped[str] = mapped_column(String(32), default="kgCO2e")
    year: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(Text)
    source_system: Mapped[str | None] = mapped_column(String(64), index=True)
    source_snapshot_id: Mapped[str | None] = mapped_column(String(64), index=True)
    raw_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_factor_raw_record.id", ondelete="SET NULL"),
        index=True,
    )
    projection_status: Mapped[str | None] = mapped_column(String(24), default="manual")
    review_status: Mapped[str | None] = mapped_column(String(24), default="approved")


class CarbonFactorImportBatch(BigIntAuditBase):
    """Official factor source import batch.

    This is intentionally source-system neutral so NCSC, ecoinvent, IPCC, and local factor packs can share the
    same governance surface while keeping their native payloads.
    """

    __tablename__ = "carbon_factor_import_batch"
    __table_args__ = (UniqueConstraint("source_system", "snapshot_id", name="uq_carbon_factor_batch_source_snapshot"),)

    snapshot_id: Mapped[str] = mapped_column(String(64), index=True)
    package_name: Mapped[str | None] = mapped_column(String(255))
    package_version: Mapped[str | None] = mapped_column(String(32))
    package_type: Mapped[str | None] = mapped_column(String(64))
    source_system: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[str | None] = mapped_column(String(512))
    built_at: Mapped[datetime | None] = mapped_column(DateTime)
    crawl_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    crawl_finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    checksum_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    import_status: Mapped[str] = mapped_column(String(24), default="imported")
    library_count: Mapped[int] = mapped_column(Integer, default=0)
    category_count: Mapped[int] = mapped_column(Integer, default=0)
    leaf_category_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    detail_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    xlsx_count: Mapped[int] = mapped_column(Integer, default=0)
    manifest_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class CarbonFactorLibrary(BigIntAuditBase):
    """A library/version inside a factor source, e.g. NCSC 2026 G02 or ecoinvent 3.x."""

    __tablename__ = "carbon_factor_library"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "library_year", "library_code", name="uq_carbon_factor_library_source_year_code"
        ),
    )

    source_system: Mapped[str] = mapped_column(String(64), index=True)
    library_year: Mapped[str] = mapped_column(String(16), index=True)
    library_code: Mapped[str] = mapped_column(String(32), index=True)
    library_name: Mapped[str] = mapped_column(String(255))
    institution: Mapped[str | None] = mapped_column(String(255))
    source_pkid: Mapped[str | None] = mapped_column(String(64))
    source_year_id: Mapped[str | None] = mapped_column(String(64))
    raw_payload: Mapped[dict | None] = mapped_column(JSON)


class CarbonFactorCategory(BigIntAuditBase):
    """Source-native category tree with a flattened path for search and display."""

    __tablename__ = "carbon_factor_category"
    __table_args__ = (
        UniqueConstraint("source_system", "source_category_id", name="uq_carbon_factor_category_source_id"),
        Index("ix_carbon_factor_category_path", "category_path"),
    )

    source_system: Mapped[str] = mapped_column(String(64), index=True)
    source_category_id: Mapped[str] = mapped_column(String(64), index=True)
    parent_source_category_id: Mapped[str | None] = mapped_column(String(64), index=True)
    library_year: Mapped[str | None] = mapped_column(String(16), index=True)
    library_code: Mapped[str | None] = mapped_column(String(32), index=True)
    category_name: Mapped[str] = mapped_column(String(255), index=True)
    category_path: Mapped[str] = mapped_column(String(1024))
    depth: Mapped[int] = mapped_column(Integer, default=0)
    is_leaf: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)


class CarbonFactorRawRecord(BigIntAuditBase):
    """Source-native factor record preserved for audit, search, and later projection."""

    __tablename__ = "carbon_factor_raw_record"
    __table_args__ = (
        UniqueConstraint(
            "source_system", "snapshot_id", "stable_hash", name="uq_carbon_factor_raw_source_snapshot_hash"
        ),
        Index("ix_carbon_factor_raw_lookup", "source_system", "library_year", "library_code"),
    )

    snapshot_id: Mapped[str] = mapped_column(String(64), index=True)
    source_system: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[str | None] = mapped_column(String(512))
    library_year: Mapped[str | None] = mapped_column(String(16), index=True)
    library_code: Mapped[str | None] = mapped_column(String(32), index=True)
    library_name: Mapped[str | None] = mapped_column(String(255))
    category_path: Mapped[str] = mapped_column(String(1024), index=True)
    top_category: Mapped[str | None] = mapped_column(String(255), index=True)
    second_category: Mapped[str | None] = mapped_column(String(255), index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(128), index=True)
    stable_hash: Mapped[str] = mapped_column(String(64), index=True)
    factor_name: Mapped[str] = mapped_column(String(1024), index=True)
    factor_value_raw: Mapped[str | None] = mapped_column(Text)
    factor_unit_raw: Mapped[str | None] = mapped_column(String(128), index=True)
    region_raw: Mapped[str | None] = mapped_column(String(255), index=True)
    gas_raw: Mapped[str | None] = mapped_column(String(64), index=True)
    time_representativeness: Mapped[str | None] = mapped_column(String(128))
    provider: Mapped[str | None] = mapped_column(String(255), index=True)
    source_description: Mapped[str | None] = mapped_column(Text)
    projection_status: Mapped[str] = mapped_column(String(24), default="raw_only", index=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)


class CarbonVerificationExportJob(TeamScopedMixin, BigIntAuditBase):
    """Carbon verification report/material package export job."""

    __tablename__ = "carbon_verification_export_job"
    __table_args__ = (
        UniqueConstraint("team_id", "job_no", name="uq_carbon_verification_export_job_team_no"),
        Index("ix_carbon_verification_export_job_team_status", "team_id", "status"),
        Index("ix_carbon_verification_export_job_period", "team_id", "report_year", "scope_filter"),
    )

    job_no: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_verification_project.id", ondelete="SET NULL"), index=True
    )
    export_type: Mapped[str] = mapped_column(String(32), default="material_package", index=True)
    report_year: Mapped[int | None] = mapped_column(Integer, index=True)
    scope_filter: Mapped[str | None] = mapped_column(String(16), index=True)
    status_filter: Mapped[str | None] = mapped_column(String(24), index=True)
    status: Mapped[str] = mapped_column(String(24), default="completed", index=True)
    template_name: Mapped[str | None] = mapped_column(String(255))
    template_path: Mapped[str | None] = mapped_column(String(512))
    standard_name: Mapped[str | None] = mapped_column(String(255))
    standard_code: Mapped[str | None] = mapped_column(String(128))
    file_path: Mapped[str | None] = mapped_column(String(512))
    file_sha256: Mapped[str | None] = mapped_column(String(64))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    manifest_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(String(128))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    project: Mapped[CarbonVerificationProject | None] = relationship(back_populates="export_jobs", lazy="selectin")
    files: Mapped[list[CarbonVerificationExportFile]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CarbonVerificationExportFile(TeamScopedMixin, BigIntAuditBase):
    """A generated file entry inside a carbon verification export package."""

    __tablename__ = "carbon_verification_export_file"
    __table_args__ = (
        Index("ix_carbon_verification_export_file_job", "team_id", "job_id"),
        Index("ix_carbon_verification_export_file_type", "team_id", "file_type"),
    )

    job_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_verification_export_job.id", ondelete="CASCADE"),
        index=True,
    )
    file_type: Mapped[str] = mapped_column(String(64), index=True)
    path: Mapped[str] = mapped_column(String(512))
    source_name: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(128))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))

    job: Mapped[CarbonVerificationExportJob] = relationship(
        back_populates="files",
        lazy="selectin",
    )


class CarbonVerificationFinding(TeamScopedMixin, BigIntAuditBase):
    """Verification finding with correction and review lifecycle."""

    __tablename__ = "carbon_verification_finding"
    __table_args__ = (
        UniqueConstraint("team_id", "finding_no", name="uq_carbon_verification_finding_team_no"),
        Index("ix_carbon_verification_finding_team_status_severity", "team_id", "status", "severity"),
        Index("ix_carbon_verification_finding_record", "team_id", "record_type", "record_id", "issue_type"),
        Index("ix_carbon_verification_finding_due", "team_id", "due_date", "status"),
    )

    finding_no: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_verification_project.id", ondelete="SET NULL"), index=True
    )
    issue_type: Mapped[str] = mapped_column(String(64), index=True)
    finding_type: Mapped[str] = mapped_column(String(64), default="data_quality", index=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    action_required: Mapped[str | None] = mapped_column(Text)
    record_type: Mapped[str | None] = mapped_column(String(128), index=True)
    record_id: Mapped[int | None] = mapped_column(Integer, index=True)
    record_code: Mapped[str | None] = mapped_column(String(96), index=True)
    scope: Mapped[str | None] = mapped_column(String(16), index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    period: Mapped[str | None] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    owner: Mapped[str | None] = mapped_column(String(128))
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    correction_comment: Mapped[str | None] = mapped_column(Text)
    correction_evidence: Mapped[str | None] = mapped_column(String(512))
    reviewer: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_name: Mapped[str | None] = mapped_column(String(128))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    source_payload: Mapped[dict | None] = mapped_column(JSON)
    remark: Mapped[str | None] = mapped_column(Text)

    project: Mapped[CarbonVerificationProject | None] = relationship(back_populates="findings", lazy="selectin")


class CarbonVerificationTemplateVersion(TeamScopedMixin, BigIntAuditBase):
    """Report template version metadata for carbon verification exports."""

    __tablename__ = "carbon_verification_template_version"
    __table_args__ = (
        UniqueConstraint(
            "team_id", "template_code", "version", name="uq_carbon_verification_template_team_code_version"
        ),
        Index("ix_carbon_verification_template_team_status_default", "team_id", "status", "is_default"),
        Index("ix_carbon_verification_template_standard", "team_id", "standard_code", "applicable_industry"),
    )

    template_code: Mapped[str] = mapped_column(String(64), index=True)
    template_name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(32), default="v1.0", index=True)
    template_format: Mapped[str] = mapped_column(String(16), default="docx")
    template_path: Mapped[str] = mapped_column(String(512))
    applicable_industry: Mapped[str | None] = mapped_column(String(128), index=True)
    applicable_scope: Mapped[str | None] = mapped_column(String(255))
    standard_name: Mapped[str | None] = mapped_column(String(255))
    standard_code: Mapped[str | None] = mapped_column(String(128), index=True)
    source_name: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    remark: Mapped[str | None] = mapped_column(Text)

    projects: Mapped[list[CarbonVerificationProject]] = relationship(back_populates="template_version", lazy="selectin")


class CarbonVerificationProject(TeamScopedMixin, BigIntAuditBase):
    """Formal organization-carbon verification project lifecycle."""

    __tablename__ = "carbon_verification_project"
    __table_args__ = (
        UniqueConstraint("team_id", "project_no", name="uq_carbon_verification_project_team_no"),
        Index("ix_carbon_verification_project_team_status_type", "team_id", "status", "project_type"),
        Index("ix_carbon_verification_project_scope", "team_id", "reporting_org_id", "period_id", "boundary_id"),
        Index("ix_carbon_verification_project_report", "team_id", "inventory_report_id", "status"),
        Index("ix_carbon_verification_project_run", "team_id", "calculation_run_id", "status"),
    )

    project_no: Mapped[str] = mapped_column(String(64), index=True)
    project_name: Mapped[str] = mapped_column(String(128))
    project_type: Mapped[str] = mapped_column(String(32), default="organization_inventory", index=True)
    reporting_org_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_reporting_organization.id", ondelete="SET NULL"), index=True
    )
    period_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_reporting_period.id", ondelete="SET NULL"), index=True
    )
    boundary_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_organization_boundary.id", ondelete="SET NULL"), index=True
    )
    inventory_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("ghg_inventory_report.id", ondelete="RESTRICT"), index=True
    )
    calculation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ghg_calculation_run.id", ondelete="RESTRICT"), index=True
    )
    template_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("carbon_verification_template_version.id", ondelete="SET NULL"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    verification_year: Mapped[int | None] = mapped_column(Integer, index=True)
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_end: Mapped[date | None] = mapped_column(Date)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    lead_reviewer: Mapped[str | None] = mapped_column(String(128))
    responsible_person: Mapped[str | None] = mapped_column(String(128))
    verifier_org: Mapped[str | None] = mapped_column(String(128))
    assurance_level: Mapped[str] = mapped_column(String(24), default="internal_review", index=True)
    materiality_threshold_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    verification_basis: Mapped[str | None] = mapped_column(String(255))
    sampling_strategy: Mapped[str | None] = mapped_column(Text)
    site_visit_required: Mapped[bool] = mapped_column(Boolean, default=False)
    site_visit_status: Mapped[str] = mapped_column(String(24), default="not_planned", index=True)
    conclusion_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    readiness_status: Mapped[str] = mapped_column(String(24), default="empty", index=True)
    conclusion: Mapped[str | None] = mapped_column(Text)
    scope_description: Mapped[str | None] = mapped_column(Text)
    finding_summary: Mapped[dict | None] = mapped_column(JSON)
    source_name: Mapped[str | None] = mapped_column(String(128))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    remark: Mapped[str | None] = mapped_column(Text)

    organization: Mapped[ReportingOrganization | None] = relationship(lazy="selectin")
    period: Mapped[ReportingPeriod | None] = relationship(lazy="selectin")
    boundary: Mapped[OrganizationBoundary | None] = relationship(lazy="selectin")
    inventory_report: Mapped[Any | None] = relationship("GhgInventoryReport", lazy="selectin")
    calculation_run: Mapped[Any | None] = relationship("GhgCalculationRun", lazy="selectin")
    template_version: Mapped[CarbonVerificationTemplateVersion | None] = relationship(
        back_populates="projects", lazy="selectin"
    )
    findings: Mapped[list[CarbonVerificationFinding]] = relationship(back_populates="project", lazy="selectin")
    export_jobs: Mapped[list[CarbonVerificationExportJob]] = relationship(back_populates="project", lazy="selectin")


class ReportingOrganization(TeamScopedMixin, BigIntAuditBase):
    """Reporting organization for organization-level GHG inventories."""

    __tablename__ = "carbon_reporting_organization"
    __table_args__ = (
        UniqueConstraint("team_id", "code", name="uq_carbon_reporting_organization_team_code"),
        Index("ix_carbon_reporting_organization_team_status", "team_id", "status"),
    )

    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    enterprise_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_enterpriseinfo.id", ondelete="SET NULL"),
        index=True,
    )
    organization_type: Mapped[str] = mapped_column(String(32), default="enterprise", index=True)
    legal_entity_code: Mapped[str | None] = mapped_column(String(64))
    control_method: Mapped[str] = mapped_column(String(32), default="operational_control", index=True)
    equity_share_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    source_name: Mapped[str | None] = mapped_column(String(128))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    remark: Mapped[str | None] = mapped_column(Text)

    periods: Mapped[list[ReportingPeriod]] = relationship(back_populates="organization", lazy="selectin")
    boundaries: Mapped[list[OrganizationBoundary]] = relationship(back_populates="organization", lazy="selectin")


class ReportingPeriod(TeamScopedMixin, BigIntAuditBase):
    """Reporting period for organization-level GHG inventories."""

    __tablename__ = "carbon_reporting_period"
    __table_args__ = (
        UniqueConstraint("team_id", "reporting_org_id", "code", name="uq_carbon_reporting_period_org_code"),
        Index("ix_carbon_reporting_period_org_range", "team_id", "reporting_org_id", "period_start", "period_end"),
    )

    reporting_org_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_reporting_organization.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    period_type: Mapped[str] = mapped_column(String(16), default="annual", index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    base_year: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_name: Mapped[str | None] = mapped_column(String(128))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    remark: Mapped[str | None] = mapped_column(Text)

    organization: Mapped[ReportingOrganization] = relationship(back_populates="periods", lazy="selectin")
    boundaries: Mapped[list[OrganizationBoundary]] = relationship(back_populates="period", lazy="selectin")


class OrganizationBoundary(TeamScopedMixin, BigIntAuditBase):
    """Versioned organization and operational boundary."""

    __tablename__ = "carbon_organization_boundary"
    __table_args__ = (
        UniqueConstraint("team_id", "boundary_no", name="uq_carbon_organization_boundary_team_no"),
        UniqueConstraint(
            "team_id", "reporting_org_id", "period_id", "boundary_type", "version", name="uq_carbon_boundary_version"
        ),
        Index("ix_carbon_boundary_org_period_status", "team_id", "reporting_org_id", "period_id", "status"),
    )

    reporting_org_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_reporting_organization.id", ondelete="CASCADE"), index=True
    )
    period_id: Mapped[int] = mapped_column(ForeignKey("carbon_reporting_period.id", ondelete="CASCADE"), index=True)
    boundary_no: Mapped[str] = mapped_column(String(64), index=True)
    boundary_name: Mapped[str] = mapped_column(String(128))
    boundary_type: Mapped[str] = mapped_column(String(32), default="organization", index=True)
    boundary_method: Mapped[str] = mapped_column(String(32), default="operational_control", index=True)
    operational_boundary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_name: Mapped[str | None] = mapped_column(String(128))
    standard_code: Mapped[str | None] = mapped_column(String(64))
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    remark: Mapped[str | None] = mapped_column(Text)

    organization: Mapped[ReportingOrganization] = relationship(back_populates="boundaries", lazy="selectin")
    period: Mapped[ReportingPeriod] = relationship(back_populates="boundaries", lazy="selectin")
    facilities: Mapped[list[BoundaryFacility]] = relationship(
        back_populates="boundary",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class BoundaryFacility(TeamScopedMixin, BigIntAuditBase):
    """Area/equipment/facility included in or excluded from an organization boundary."""

    __tablename__ = "carbon_boundary_facility"
    __table_args__ = (
        Index("ix_carbon_boundary_facility_boundary", "team_id", "boundary_id", "included"),
        Index("ix_carbon_boundary_facility_reference", "team_id", "facility_type", "area_id", "equipment_id"),
    )

    boundary_id: Mapped[int] = mapped_column(
        ForeignKey("carbon_organization_boundary.id", ondelete="CASCADE"), index=True
    )
    facility_type: Mapped[str] = mapped_column(String(32), default="area", index=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"), index=True)
    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True
    )
    facility_code: Mapped[str | None] = mapped_column(String(128), index=True)
    facility_name: Mapped[str | None] = mapped_column(String(128))
    facility_role: Mapped[str | None] = mapped_column(String(64))
    included: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    exclusion_reason: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source_name: Mapped[str | None] = mapped_column(String(128))
    remark: Mapped[str | None] = mapped_column(Text)

    boundary: Mapped[OrganizationBoundary] = relationship(back_populates="facilities", lazy="selectin")
