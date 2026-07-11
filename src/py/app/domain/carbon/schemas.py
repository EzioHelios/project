"""
碳管理领域的 API 模型（Pydantic / DTO）。

说明：
- 这里主要定义对外暴露给前端的响应结构
- 字段保持与原 Django 接口返回尽量一致，便于前端平滑迁移
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from advanced_alchemy.extensions.litestar import SQLAlchemyDTO

from app.db import models as m
from app.utils.dto import config


class EnterpriseInfoDTO(SQLAlchemyDTO[m.EnterpriseInfo]):
    """企业信息 DTO，对应 Django EnterpriseInfoSerializer."""

    config = config(backend="sqlalchemy")


class MonitorSectorDTO(SQLAlchemyDTO[m.MonitorSector]):
    """监控区域 DTO."""

    config = config(backend="sqlalchemy")


class MonitorEquipmentDTO(SQLAlchemyDTO[m.MonitorEquipment]):
    """监控终端 DTO."""

    config = config(backend="sqlalchemy")


class MonitorSectorPhotoDTO(SQLAlchemyDTO[m.MonitorSectorPhoto]):
    """监控区域照片 DTO."""

    config = config(backend="sqlalchemy")


class EmployeeCommuteDTO(SQLAlchemyDTO[m.EmployeeCommute]):
    """员工通勤 DTO."""

    config = config(backend="sqlalchemy")


class InMoneyDTO(SQLAlchemyDTO[m.InMoney]):
    """入库金额 DTO."""

    config = config(backend="sqlalchemy")


class OutMoneyDTO(SQLAlchemyDTO[m.OutMoney]):
    """出库金额 DTO."""

    config = config(backend="sqlalchemy")


class VideoMonitorDTO(SQLAlchemyDTO[m.VideoMonitor]):
    """视频监控 DTO."""

    config = config(backend="sqlalchemy")


class ApiResultKeyMappingDTO(SQLAlchemyDTO[m.ApiResultKeyMapping]):
    """API 结果映射 DTO."""

    config = config(backend="sqlalchemy")


class WarningRuleDTO(SQLAlchemyDTO[m.WarningRule]):
    """预警规则 DTO."""

    config = config(backend="sqlalchemy")


class AlarmEventDTO(SQLAlchemyDTO[m.AlarmEvent]):
    """预警事件 DTO."""

    config = config(backend="sqlalchemy")


class VedioAlarmEventDTO(SQLAlchemyDTO[m.VedioAlarmEvent]):
    """摄像头预警事件 DTO."""

    config = config(backend="sqlalchemy")


class EnergyStorageValueDTO(SQLAlchemyDTO[m.EnergyStorageValue]):
    """储能量 DTO."""

    config = config(backend="sqlalchemy")


class Scope1MobileCombustionDTO(SQLAlchemyDTO[m.Scope1MobileCombustion]):
    """Scope1 移动源燃烧 DTO."""

    config = config(backend="sqlalchemy")


class Scope1StationaryCombustionDTO(SQLAlchemyDTO[m.Scope1StationaryCombustion]):
    """Scope1 固定源燃烧 DTO."""

    config = config(backend="sqlalchemy")


class Scope1RefrigerantLeakDTO(SQLAlchemyDTO[m.Scope1RefrigerantLeak]):
    """Scope1 逸散排放 DTO."""

    config = config(backend="sqlalchemy")


class Scope2ElectricityBillDTO(SQLAlchemyDTO[m.Scope2ElectricityBill]):
    """Scope2 电费账单 DTO."""

    config = config(backend="sqlalchemy")


class Scope3WasteDisposalDTO(SQLAlchemyDTO[m.Scope3WasteDisposal]):
    """Scope3 废弃物处理 DTO."""

    config = config(backend="sqlalchemy")


class Scope3ThirdPartyTransportDTO(SQLAlchemyDTO[m.Scope3ThirdPartyTransport]):
    """Scope3 外购运输 DTO."""

    config = config(backend="sqlalchemy")


class EmissionFactorDTO(SQLAlchemyDTO[m.EmissionFactor]):
    """排放因子 DTO."""

    config = config(backend="sqlalchemy")


class CarbonAuditLogDTO(SQLAlchemyDTO[m.CarbonAuditLog]):
    """审核操作日志 DTO."""

    config = config(backend="sqlalchemy")


@dataclass
class ApiResponse:
    """常规 API 响应结构。"""

    code: int
    msg: str
    data: Any


@dataclass
class Page1CkInformation(ApiResponse):
    """态势总览：信息概况接口数据结构。"""


@dataclass
class Page1JcdwStatis(ApiResponse):
    """态势总览：监测点位在线统计数据结构。"""
