"""Validation rules for the remaining operational-data endpoints."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


class CarbonValidationError(ValueError):
    """碳数据校验错误。"""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message)


def _to_decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except (ArithmeticError, ValueError):
        return None


def validate_amount_non_negative(amount: Any, field_name: str = "消耗量") -> None:
    """校验数量/消耗量非负。"""
    d = _to_decimal(amount)
    if d is None:
        msg = f"{field_name}必须为有效数值"
        raise CarbonValidationError(msg, field=field_name)
    if d < 0:
        msg = f"{field_name}不能为负数"
        raise CarbonValidationError(msg, field=field_name)
