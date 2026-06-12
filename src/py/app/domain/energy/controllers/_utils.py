from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any


def model_to_dict(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        if isinstance(value, (datetime.date, datetime.datetime)):
            result[column.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[column.name] = float(value)
        else:
            result[column.name] = value
    return result


def ok_data(data: Any) -> dict[str, Any]:
    return {"code": 200, "msg": "获取成功", "data": data}
