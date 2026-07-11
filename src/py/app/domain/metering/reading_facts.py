"""Canonical meter reading fact writer and point vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.db import models as m

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

VALUE_KIND_REGISTER_INDEX = "register_index"
VALUE_KIND_LEGACY_QUANTITY = "legacy_quantity"


@dataclass(frozen=True)
class MeterPointSpec:
    """Normalized electric energy point metadata."""

    point_code: str
    point_name: str
    unit: str
    energy_direction: str
    energy_kind: str
    tou_period: str


_DIRECTION_LABELS = {"forward": "正向", "reverse": "反向"}
_KIND_LABELS = {"active": ("有功", "kWh"), "reactive": ("无功", "kvarh")}
_TOU_LABELS = {"total": "总", "sharp": "尖", "peak": "峰", "flat": "平", "valley": "谷"}


def _build_point_specs() -> dict[str, MeterPointSpec]:
    specs: dict[str, MeterPointSpec] = {}
    for direction, direction_label in _DIRECTION_LABELS.items():
        for kind, (kind_label, unit) in _KIND_LABELS.items():
            for period, period_label in _TOU_LABELS.items():
                point_code = f"{direction}_{kind}_{period}"
                specs[point_code] = MeterPointSpec(
                    point_code=point_code,
                    point_name=f"{direction_label}{kind_label}{period_label}电能",
                    unit=unit,
                    energy_direction=direction,
                    energy_kind=kind,
                    tou_period=period,
                )
    return specs


METER_POINT_SPECS = _build_point_specs()

LEGACY_FIELD_TO_POINT: dict[str, tuple[str, str]] = {
    "ZYGDN": ("forward_active_total", VALUE_KIND_LEGACY_QUANTITY),
    "FYGDN": ("reverse_active_total", VALUE_KIND_LEGACY_QUANTITY),
    "ZWGDN": ("forward_reactive_total", VALUE_KIND_LEGACY_QUANTITY),
    "FWGDN": ("reverse_reactive_total", VALUE_KIND_LEGACY_QUANTITY),
    "ZYGDNSZ": ("forward_active_total", VALUE_KIND_REGISTER_INDEX),
    "FYGDNSZ": ("reverse_active_total", VALUE_KIND_REGISTER_INDEX),
    "ZWGDNSZ": ("forward_reactive_total", VALUE_KIND_REGISTER_INDEX),
    "FWGDNSZ": ("reverse_reactive_total", VALUE_KIND_REGISTER_INDEX),
}


SZSCADA_TAG_TO_POINT: dict[str, str] = {
    "tag_010_p001": "forward_active_total",
    "tag_010_p002": "forward_active_sharp",
    "tag_010_p003": "forward_active_peak",
    "tag_010_p004": "forward_active_flat",
    "tag_010_p005": "forward_active_valley",
    "tag_010_p006": "forward_reactive_total",
    "tag_010_p007": "forward_reactive_sharp",
    "tag_010_p008": "forward_reactive_peak",
    "tag_010_p009": "forward_reactive_flat",
    "tag_010_p010": "forward_reactive_valley",
    "tag_010_p011": "reverse_active_total",
    "tag_010_p012": "reverse_active_sharp",
    "tag_010_p013": "reverse_active_peak",
    "tag_010_p014": "reverse_active_flat",
    "tag_010_p015": "reverse_active_valley",
    "tag_010_p016": "reverse_reactive_total",
    "tag_010_p017": "reverse_reactive_sharp",
    "tag_010_p018": "reverse_reactive_peak",
    "tag_010_p019": "reverse_reactive_flat",
    "tag_010_p020": "reverse_reactive_valley",
}


@dataclass(frozen=True)
class MeterReadingFactInput:
    """Input payload for one canonical meter reading fact."""

    source_system: str
    source_record_id: str
    equipment_id: int
    point_code: str
    reading_time: datetime
    value_kind: str = VALUE_KIND_REGISTER_INDEX
    raw_value: Any | None = None
    normalized_value: Any | None = None
    unit: str | None = None
    quality_status: str = "valid"
    source_point_code: str | None = None
    source_point_name: str | None = None
    point_name: str | None = None
    source_message_id: int | None = None
    binding_id: int | None = None
    source_type: int | None = None
    mapping_version: str = "v1"


class MeterReadingFactWriter:
    """Idempotent writer for the canonical meter reading fact table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write_many(self, readings: list[MeterReadingFactInput]) -> int:
        created = 0
        for reading in readings:
            if await self._exists(reading):
                continue
            self._session.add(self._to_model(reading))
            created += 1
        return created

    async def _exists(self, reading: MeterReadingFactInput) -> bool:
        existing = await self._session.scalar(
            select(m.MeterReadingFact.id).where(
                m.MeterReadingFact.source_system == reading.source_system,
                m.MeterReadingFact.source_record_id == reading.source_record_id,
                m.MeterReadingFact.equipment_id == reading.equipment_id,
                m.MeterReadingFact.point_code == reading.point_code,
                m.MeterReadingFact.value_kind == reading.value_kind,
            )
        )
        return existing is not None

    def _to_model(self, reading: MeterReadingFactInput) -> m.MeterReadingFact:
        spec = METER_POINT_SPECS.get(reading.point_code)
        if spec is None:
            msg = f"未知电表点位编码: {reading.point_code}"
            raise ValueError(msg)
        normalized_value = _decimal_or_none(reading.normalized_value)
        unit = reading.unit or spec.unit
        return m.MeterReadingFact(
            source_system=reading.source_system,
            source_record_id=reading.source_record_id,
            source_message_id=reading.source_message_id,
            binding_id=reading.binding_id,
            equipment_id=reading.equipment_id,
            source_point_code=reading.source_point_code or reading.point_code,
            source_point_name=reading.source_point_name,
            point_code=reading.point_code,
            point_name=reading.point_name or spec.point_name,
            energy_direction=spec.energy_direction,
            energy_kind=spec.energy_kind,
            tou_period=spec.tou_period,
            value_kind=reading.value_kind,
            raw_value=None if reading.raw_value is None else str(reading.raw_value),
            normalized_value=normalized_value,
            unit=unit,
            quality_status=reading.quality_status,
            source_type=reading.source_type,
            reading_time=reading.reading_time,
            mapping_version=reading.mapping_version,
        )


def point_spec(point_code: str) -> MeterPointSpec:
    spec = METER_POINT_SPECS.get(point_code)
    if spec is None:
        msg = f"未知电表点位编码: {point_code}"
        raise ValueError(msg)
    return spec


def _decimal_or_none(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        msg = f"电表读数不是有效数值: {value}"
        raise ValueError(msg) from exc
