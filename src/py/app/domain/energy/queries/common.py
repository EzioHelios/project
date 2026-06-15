from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any


def jsonable_mapping(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (datetime.date, datetime.datetime)):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


def paged_payload(items: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"items": items, "total": total, "limit": limit, "offset": offset, "code": 200, "data": items}


def positive_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    number = float(value)
    return number if number > 0 else None


def ratio_or_none(numerator: Any, denominator: float | None, digits: int = 6) -> float | None:
    if denominator in (None, 0):
        return None
    return round(float(numerator or 0) / denominator, digits)
