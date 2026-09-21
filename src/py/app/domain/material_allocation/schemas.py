"""Strict commands for handling operations and hourly allocation."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Interval(Command):
    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            msg = "时间必须包含时区"
            raise ValueError(msg)
        return value


OperationType = Literal["inbound_putaway", "outbound_picking", "internal_transfer", "loading_unloading"]
EquipmentType = Literal["forklift", "rotary_crane", "bridge_crane", "stacker"]


class OperationCreate(Command):
    operation_no: str = Field(min_length=1, max_length=64)
    operation_type: OperationType
    equipment_id: int = Field(gt=0)
    equipment_type: EquipmentType
    material_id: int = Field(gt=0)
    batch_no: str = Field(min_length=1, max_length=64)
    quantity: Decimal = Field(gt=0)
    weight_kg: Decimal | None = Field(default=None, gt=0)
    active_intervals: list[Interval] = Field(min_length=1, max_length=200)
    remark: str | None = Field(default=None, max_length=2000)


class OperationUpdate(Command):
    operation_type: OperationType | None = None
    equipment_id: int | None = Field(default=None, gt=0)
    equipment_type: EquipmentType | None = None
    material_id: int | None = Field(default=None, gt=0)
    batch_no: str | None = Field(default=None, min_length=1, max_length=64)
    quantity: Decimal | None = Field(default=None, gt=0)
    weight_kg: Decimal | None = Field(default=None, gt=0)
    active_intervals: list[Interval] | None = Field(default=None, min_length=1, max_length=200)
    remark: str | None = Field(default=None, max_length=2000)


class HourCalculation(Command):
    equipment_id: int = Field(gt=0)
    period_start: datetime
    period_end: datetime
    energy_source_system: str = Field(min_length=1, max_length=32)
    factor_id: int = Field(gt=0)
    assumption: Literal["hourly_uniform_intensity_v1"]
    applicability_note: str = Field(min_length=4, max_length=500)

    @field_validator("period_start", "period_end")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            msg = "时间必须包含时区"
            raise ValueError(msg)
        return value


class MaterialResultImport(Command):
    result_id: int = Field(gt=0)
    stage_id: int = Field(gt=0)
