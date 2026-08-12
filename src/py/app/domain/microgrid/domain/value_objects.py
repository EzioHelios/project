"""Immutable microgrid value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ScenarioStatus(StrEnum):
    """Lifecycle of a parameter scenario."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SourceKind(StrEnum):
    """Traceable origin of a microgrid datum."""

    MEASURED = "measured"
    REANALYSIS = "reanalysis"
    FORECAST = "forecast"
    ENTERPRISE_ASSUMPTION = "enterprise_assumption"
    SIMULATED = "simulated"
    OPTIMIZED = "optimized"
    EXECUTED = "executed"


@dataclass(frozen=True)
class Confidence:
    """Normalized confidence from zero to one."""

    value: float

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 1:
            msg = "confidence must be between zero and one"
            raise ValueError(msg)
