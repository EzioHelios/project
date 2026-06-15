from __future__ import annotations

from app.domain.energy.queries.common import ratio_or_none


def test_ratio_or_none_returns_none_for_missing_denominator() -> None:
    assert ratio_or_none(10, None) is None


def test_ratio_or_none_returns_none_for_zero_denominator() -> None:
    assert ratio_or_none(10, 0) is None


def test_ratio_or_none_rounds_non_zero_ratio() -> None:
    assert ratio_or_none(1, 3, 4) == 0.3333
