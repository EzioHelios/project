from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.tenancy import TeamScopedMixin


class DataFeatureMixin:
    """通用数据特征属性（Scope1/2/3 公共）。"""

    data_source: Mapped[str] = mapped_column(String(20))
    collection_method: Mapped[str] = mapped_column(String(20))
    confidence_level: Mapped[str] = mapped_column(String(10))
    data_year_type: Mapped[str] = mapped_column(String(20))
    data_year: Mapped[int | None] = mapped_column(Integer)


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
    other_info: Mapped[dict | None] = mapped_column(comment="其他信息")


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

    __table_args__ = (
        UniqueConstraint("team_id", "code", name="uq_dataapp_monitorsector_team_code"),
    )

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
    __table_args__ = (
        UniqueConstraint("code", name="uq_dataapp_devicetype_code"),
    )

    code: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(64))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_devicetype.id", ondelete="SET NULL"),
        index=True,
    )
    parent_code: Mapped[str | None] = mapped_column(String(32), index=True)
    energy_type: Mapped[str | None] = mapped_column(String(20))
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
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True)
    equipment_code: Mapped[str | None] = mapped_column(String(64), index=True)
    equipment_name: Mapped[str | None] = mapped_column(String(128))
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("dataapp_monitorsector.id", ondelete="SET NULL"), index=True)
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
    __table_args__ = (
        Index("ix_energy_tariff_segment_plan", "team_id", "plan_id", "segment_type"),
    )

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
    __table_args__ = (
        Index("ix_energy_benchmark_profile_enabled", "team_id", "is_enabled"),
    )

    name: Mapped[str] = mapped_column(String(128), index=True)
    industry_name: Mapped[str | None] = mapped_column(String(128), index=True)
    scenario: Mapped[str | None] = mapped_column(String(128), index=True)
    source_name: Mapped[str | None] = mapped_column(String(128))
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

    profile_id: Mapped[int] = mapped_column(ForeignKey("dataapp_energybenchmarkprofile.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(32), index=True)
    target_code: Mapped[str | None] = mapped_column(String(128), index=True)
    target_name: Mapped[str | None] = mapped_column(String(128))
    metric_code: Mapped[str] = mapped_column(String(64), index=True)
    metric_name: Mapped[str] = mapped_column(String(128))
    benchmark_value: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(32))
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


class EnergyIntervalFact(TeamScopedMixin, BigIntAuditBase):
    """由原始计量数据聚合得到的小时/日能源消费事实."""

    __tablename__ = "dataapp_energyintervalfact"
    __table_args__ = (
        UniqueConstraint("team_id", "source_system", "source_record_id", name="uq_energy_interval_team_source_record"),
        Index("ix_energy_interval_team_period", "team_id", "period_start", "period_end"),
        Index("ix_energy_interval_resource", "equipment_id", "area_id", "energy_type_code"),
    )

    source_system: Mapped[str] = mapped_column(String(32), default="meter_interval")
    source_record_id: Mapped[str] = mapped_column(String(128))
    energy_type_code: Mapped[str] = mapped_column(String(32), index=True)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True)
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
    remark: Mapped[str | None] = mapped_column(Text)


class EquipmentWorkloadFact(TeamScopedMixin, BigIntAuditBase):
    """设备运行时间、处理量、作业次数等负荷事实."""

    __tablename__ = "dataapp_equipmentworkloadfact"
    __table_args__ = (
        UniqueConstraint("team_id", "source_system", "source_record_id", name="uq_equipment_workload_team_source_record"),
        Index("ix_equipment_workload_team_period", "team_id", "period_start", "period_end"),
        Index("ix_equipment_workload_resource", "equipment_id", "area_id", "workload_type"),
    )

    source_system: Mapped[str] = mapped_column(String(32), default="manual")
    source_record_id: Mapped[str] = mapped_column(String(128))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"), index=True)
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
    add_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    add_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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


class MonitorEquipment(TeamScopedMixin, BigIntBase):
    """监控终端：电表、光伏、摄像头（对应 Django dataapp.MonitorEquipment）。"""

    __tablename__ = "dataapp_monitorequipment"

    __table_args__ = (
        UniqueConstraint("team_id", "code", name="uq_dataapp_monitorequipment_team_code"),
    )

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
    energy_type: Mapped[str | None] = mapped_column(String(20), index=True)
    rated_power_kw: Mapped[float | None] = mapped_column(Float)
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
    protocol: Mapped[str | None] = mapped_column(
        String(20), default="http_yunji", doc="MQTT | modbus | http_yunji"
    )

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
    __table_args__ = (
        UniqueConstraint("device_id", "point_code", name="uq_dataapp_devicepoint_device_point"),
    )

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


class AmmeterIndexValue(TeamScopedMixin, BigIntBase):
    """电表终端数值管理（对应 Django dataapp.AmmeterIndexValue）。"""

    __tablename__ = "dataapp_ammeterindexvalue"

    equipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataapp_monitorequipment.id", ondelete="SET NULL"),
        index=True,
    )
    zygdn: Mapped[float | None] = mapped_column(Float)
    fygdn: Mapped[float | None] = mapped_column(Float)
    zwgdn: Mapped[float | None] = mapped_column(Float)
    fwgdn: Mapped[float | None] = mapped_column(Float)
    zygdnsz: Mapped[float | None] = mapped_column(Float)
    fygdnsz: Mapped[float | None] = mapped_column(Float)
    zwgdnsz: Mapped[float | None] = mapped_column(Float)
    fwgdnsz: Mapped[float | None] = mapped_column(Float)
    reading_time: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    ammeter_id: Mapped[str | None] = mapped_column(String(20), index=True)
    ammeter_name: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(50))
    area_id: Mapped[str | None] = mapped_column(String(20), index=True)
    area_name: Mapped[str | None] = mapped_column(String(50))
    radio: Mapped[int | None] = mapped_column(Integer, default=1)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)
    data_source: Mapped[int | None] = mapped_column(Integer, doc="0=云集,1=红外")
    add_time: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)


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
    add_time: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)


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
    add_time: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
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
    add_time: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
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


class CarbonAuditBase(TeamScopedMixin, BigIntAuditBase, DataFeatureMixin):
    """碳排放业务记录基类。"""

    __abstract__ = True

    status: Mapped[str] = mapped_column(String(20), default="draft")
    creator_id: Mapped[int | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"), index=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    reject_reason: Mapped[str | None] = mapped_column(Text)


class Scope1MobileCombustion(CarbonAuditBase):
    """Scope1 移动源燃烧（自有车辆/叉车）。"""

    __tablename__ = "dataapp_scope1mobilecombustion"

    record_date: Mapped[date] = mapped_column(Date)
    asset_id: Mapped[str | None] = mapped_column(String(64))
    asset_name: Mapped[str | None] = mapped_column(String(64))
    fuel_type: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 4))
    unit: Mapped[str] = mapped_column(String(5))
    mileage_km: Mapped[Numeric | None] = mapped_column(Numeric(10, 2))
    work_hours: Mapped[Numeric | None] = mapped_column(Numeric(10, 2))
    attachment: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)


class Scope1StationaryCombustion(CarbonAuditBase):
    """Scope1 固定源燃烧（食堂/锅炉/发电机等）。"""

    __tablename__ = "dataapp_scope1stationarycombustion"

    facility_name: Mapped[str] = mapped_column(String(64))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    fuel_type: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 4))
    unit: Mapped[str] = mapped_column(String(5))
    meter_reading_start: Mapped[Numeric | None] = mapped_column(Numeric(14, 4))
    meter_reading_end: Mapped[Numeric | None] = mapped_column(Numeric(14, 4))
    attachment: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)


class Scope1RefrigerantLeak(CarbonAuditBase):
    """Scope1 逸散排放（制冷剂填充/泄漏）。"""

    __tablename__ = "dataapp_scope1refrigerantleak"

    device_id: Mapped[str | None] = mapped_column(String(64))
    device_name: Mapped[str | None] = mapped_column(String(64))
    fill_date: Mapped[date] = mapped_column(Date)
    refrigerant_type: Mapped[str] = mapped_column(String(32))
    amount_kg: Mapped[Numeric] = mapped_column(Numeric(12, 4))
    leak_type: Mapped[str] = mapped_column(String(16))
    attachment: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)


class Scope2ElectricityBill(CarbonAuditBase):
    """Scope2 电费账单（用于校准/补全电力数据）。"""

    __tablename__ = "dataapp_scope2electricitybill"

    account_number: Mapped[str] = mapped_column(String(64))
    billing_month: Mapped[str] = mapped_column(String(7))
    total_kwh: Mapped[Numeric] = mapped_column(Numeric(16, 4))
    peak_kwh: Mapped[Numeric | None] = mapped_column(Numeric(16, 4))
    flat_kwh: Mapped[Numeric | None] = mapped_column(Numeric(16, 4))
    valley_kwh: Mapped[Numeric | None] = mapped_column(Numeric(16, 4))
    amount_cny: Mapped[Numeric | None] = mapped_column(Numeric(16, 2))
    attachment: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)
    calc_status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    factor_source: Mapped[str | None] = mapped_column(String(128))
    factor_year: Mapped[int | None] = mapped_column(Integer)
    factor_unit: Mapped[str | None] = mapped_column(String(32))
    activity_amount: Mapped[Numeric | None] = mapped_column(Numeric(16, 4))
    activity_unit: Mapped[str | None] = mapped_column(String(16))
    computed_co2e: Mapped[Numeric | None] = mapped_column(Numeric(18, 6))
    computation_note: Mapped[str | None] = mapped_column(Text)


class Scope2PurchasedEnergy(CarbonAuditBase):
    """Scope2 外购热力、蒸汽、冷量。"""

    __tablename__ = "dataapp_scope2purchasedenergy"
    __table_args__ = (
        Index("ix_scope2_purchased_energy_team_period", "team_id", "period_start", "period_end"),
        Index("ix_scope2_purchased_energy_team_type", "team_id", "energy_type_code"),
    )

    energy_type_code: Mapped[str] = mapped_column(String(32), index=True)
    energy_type_name: Mapped[str | None] = mapped_column(String(64))
    supplier_name: Mapped[str | None] = mapped_column(String(128))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    amount: Mapped[Numeric] = mapped_column(Numeric(16, 4))
    unit: Mapped[str] = mapped_column(String(16))
    standard_amount: Mapped[Numeric | None] = mapped_column(Numeric(18, 6))
    standard_unit: Mapped[str | None] = mapped_column(String(16))
    tce_amount: Mapped[Numeric | None] = mapped_column(Numeric(18, 6))
    amount_cny: Mapped[Numeric | None] = mapped_column(Numeric(16, 2))
    area_id: Mapped[str | None] = mapped_column(String(20), index=True)
    area_name: Mapped[str | None] = mapped_column(String(50))
    facility_name: Mapped[str | None] = mapped_column(String(128))
    attachment: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)
    calc_status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    factor_source: Mapped[str | None] = mapped_column(String(128))
    factor_year: Mapped[int | None] = mapped_column(Integer)
    factor_unit: Mapped[str | None] = mapped_column(String(32))
    activity_amount: Mapped[Numeric | None] = mapped_column(Numeric(16, 4))
    activity_unit: Mapped[str | None] = mapped_column(String(16))
    computed_co2e: Mapped[Numeric | None] = mapped_column(Numeric(18, 6))
    computation_note: Mapped[str | None] = mapped_column(Text)
    standard_code: Mapped[str | None] = mapped_column(String(64))
    conversion_factor_source: Mapped[str | None] = mapped_column(String(255))


class Scope2MeterAggregate(TeamScopedMixin, BigIntAuditBase):
    """Scope2 电表月度聚合快照。"""

    __tablename__ = "dataapp_scope2meteraggregate"
    __table_args__ = (
        UniqueConstraint("team_id", "ammeter_id", "billing_month", name="uq_scope2_meter_aggregate_team_meter_month"),
        Index("ix_scope2_meter_aggregate_team_month_area", "team_id", "billing_month", "area_id"),
    )

    source_kind: Mapped[str] = mapped_column(String(24), default="meter_aggregate")
    ammeter_id: Mapped[str] = mapped_column(String(20), index=True)
    ammeter_name: Mapped[str | None] = mapped_column(String(30))
    area_id: Mapped[str | None] = mapped_column(String(20), index=True)
    area_name: Mapped[str | None] = mapped_column(String(50))
    billing_month: Mapped[str] = mapped_column(String(7), index=True)
    first_reading_time: Mapped[datetime | None] = mapped_column(DateTime)
    last_reading_time: Mapped[datetime | None] = mapped_column(DateTime)
    start_total_energy: Mapped[Numeric | None] = mapped_column(Numeric(16, 4))
    end_total_energy: Mapped[Numeric | None] = mapped_column(Numeric(16, 4))
    total_kwh: Mapped[Numeric | None] = mapped_column(Numeric(16, 4))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    calc_status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    factor_source: Mapped[str | None] = mapped_column(String(128))
    factor_year: Mapped[int | None] = mapped_column(Integer)
    factor_unit: Mapped[str | None] = mapped_column(String(32))
    activity_amount: Mapped[Numeric | None] = mapped_column(Numeric(16, 4))
    activity_unit: Mapped[str | None] = mapped_column(String(16))
    computed_co2e: Mapped[Numeric | None] = mapped_column(Numeric(18, 6))
    computation_note: Mapped[str | None] = mapped_column(Text)
    aggregation_note: Mapped[str | None] = mapped_column(Text)


class Scope3WasteDisposal(CarbonAuditBase):
    """Scope3 废弃物处理。"""

    __tablename__ = "dataapp_scope3wastedisposal"

    date: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(32))
    weight_ton: Mapped[Numeric] = mapped_column(Numeric(12, 4))
    treatment_method: Mapped[str] = mapped_column(String(16))
    vendor_name: Mapped[str | None] = mapped_column(String(128))
    attachment: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)


class Scope3ThirdPartyTransport(CarbonAuditBase):
    """Scope3 外购运输（外包车队）。"""

    __tablename__ = "dataapp_scope3thirdpartytransport"

    waybill_no: Mapped[str] = mapped_column(String(64))
    origin: Mapped[str] = mapped_column(String(128))
    destination: Mapped[str] = mapped_column(String(128))
    vehicle_type: Mapped[str] = mapped_column(String(32))
    distance_km: Mapped[Numeric] = mapped_column(Numeric(12, 2))
    load_ton: Mapped[Numeric] = mapped_column(Numeric(12, 4))
    fuel_amount: Mapped[Numeric | None] = mapped_column(Numeric(12, 4))
    attachment: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(Text)


class EmissionFactor(BigIntAuditBase):
    """排放因子库（对应 Django dataapp.EmissionFactor）。"""

    __tablename__ = "dataapp_emissionfactor"

    scope: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(20))
    sub_category: Mapped[str] = mapped_column(String(64))
    unit: Mapped[str] = mapped_column(String(20))
    factor_value: Mapped[Numeric] = mapped_column(Numeric(18, 8))
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
    __table_args__ = (
        UniqueConstraint("source_system", "snapshot_id", name="uq_carbon_factor_batch_source_snapshot"),
    )

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
    manifest_payload: Mapped[dict | None] = mapped_column(JSON)


class CarbonFactorLibrary(BigIntAuditBase):
    """A library/version inside a factor source, e.g. NCSC 2026 G02 or ecoinvent 3.x."""

    __tablename__ = "carbon_factor_library"
    __table_args__ = (
        UniqueConstraint("source_system", "library_year", "library_code", name="uq_carbon_factor_library_source_year_code"),
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
        UniqueConstraint("source_system", "snapshot_id", "stable_hash", name="uq_carbon_factor_raw_source_snapshot_hash"),
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


class IotTelemetry(TeamScopedMixin, BigIntBase):
    """IoT 设备上报时序数据（对应 Django dataapp.IotTelemetry）。"""

    __tablename__ = "dataapp_iottelemetry"

    site_id: Mapped[str] = mapped_column(String(64), index=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    ts: Mapped[int] = mapped_column(Integer)
    reading_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    active_power: Mapped[float | None] = mapped_column(Float)
    reactive_power: Mapped[float | None] = mapped_column(Float)
    voltage_a: Mapped[float | None] = mapped_column(Float)
    current_a: Mapped[float | None] = mapped_column(Float)
    total_energy: Mapped[float | None] = mapped_column(Float)
    interval: Mapped[str] = mapped_column(String(8), default="raw")
    raw_payload: Mapped[dict | None] = mapped_column(comment="原始 JSON 报文")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)


class CarbonAuditLog(TeamScopedMixin, BigIntBase):
    """审核操作日志（对应 Django dataapp.AuditLog，表名与 Django 一致）。"""

    __tablename__ = "dataapp_carbonauditlog"

    record_type: Mapped[str] = mapped_column(String(64))
    record_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(16))
    operator_id: Mapped[UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"), index=True)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
