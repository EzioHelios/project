"""Interval arithmetic for the explicit hourly uniform-intensity assumption."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal

from app.domain.material_allocation.schemas import Interval


class MaterialAllocationError(ValueError):
    """A business invariant prevents an operation or calculation."""


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        msg = "输入时间必须包含时区"
        raise MaterialAllocationError(msg)
    return value.astimezone(UTC).replace(tzinfo=None)


def intervals(values: list[dict] | list[Interval]) -> list[tuple[datetime, datetime]]:
    ordered = sorted((utc(i.start), utc(i.end)) for v in values for i in [Interval.model_validate(v)])
    merged: list[tuple[datetime, datetime]] = []
    for start, end in ordered:
        if end <= start:
            msg = "有效时段的结束时间必须晚于开始时间"
            raise MaterialAllocationError(msg)
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    if not merged:
        msg = "请维护有效作业时段"
        raise MaterialAllocationError(msg)
    return merged


def interval_payload(values: list[tuple[datetime, datetime]]) -> list[dict[str, str]]:
    return [{"start": a.replace(tzinfo=UTC).isoformat(), "end": b.replace(tzinfo=UTC).isoformat()} for a, b in values]


def overlap_seconds(values: list[tuple[datetime, datetime]], start: datetime, end: datetime) -> Decimal:
    return sum((Decimal(str(max(0, (min(b, end) - max(a, start)).total_seconds()))) for a, b in values), Decimal(0))


def allocate(energy: Decimal, seconds: Decimal) -> Decimal:
    return (energy * seconds / Decimal(3600)).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)


def fingerprint(data: dict) -> str:
    def serialize(value: object) -> str:
        return str(value.normalize()) if isinstance(value, Decimal) else str(value)

    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, default=serialize).encode()).hexdigest()
