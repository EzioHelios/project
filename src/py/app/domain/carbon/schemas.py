"""Carbon operational-domain API models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from advanced_alchemy.extensions.litestar import SQLAlchemyDTO

from app.db import models as m
from app.utils.dto import config


class EnterpriseInfoDTO(SQLAlchemyDTO[m.EnterpriseInfo]):
    """Enterprise information DTO."""

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


class EmissionFactorDTO(SQLAlchemyDTO[m.EmissionFactor]):
    """排放因子 DTO."""

    config = config(backend="sqlalchemy")


@dataclass
class ApiResponse:
    """常规 API 响应结构。"""

    code: int
    msg: str
    data: Any


@dataclass
class Page1CkInformation(ApiResponse):
    """Big-screen overview response."""


@dataclass
class Page1JcdwStatis(ApiResponse):
    """Big-screen monitoring-point statistics response."""
