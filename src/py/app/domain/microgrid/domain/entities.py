"""Pure aggregate behavior for microgrid scenarios and flexibility."""

from __future__ import annotations

# ruff: noqa: EM102, PLR2004, TC003, TRY003
from dataclasses import dataclass, field
from datetime import time
from typing import Any

from app.domain.microgrid.domain.exceptions import PublishedScenarioMutationError, ScenarioNotReadyError
from app.domain.microgrid.domain.value_objects import ScenarioStatus


@dataclass
class Scenario:
    """Versioned parameter snapshot used by forecasts and optimization runs."""

    code: str
    version: int
    parameters: dict[str, Any]
    status: ScenarioStatus = ScenarioStatus.DRAFT

    def update_parameters(self, parameters: dict[str, Any]) -> None:
        """Replace parameters while the scenario is editable."""
        if self.status is not ScenarioStatus.DRAFT:
            raise PublishedScenarioMutationError(self.code)
        self.parameters = parameters

    def publish(self) -> None:
        """Freeze a complete draft scenario."""
        required = {"grid", "pv", "storage", "tariff"}
        missing = required.difference(self.parameters)
        if missing:
            raise ScenarioNotReadyError(f"missing scenario sections: {', '.join(sorted(missing))}")
        self.status = ScenarioStatus.PUBLISHED


@dataclass(frozen=True)
class FlexibilityWindow:
    """Dispatch envelope for one controllable load."""

    start: time
    end: time
    minimum_power_kw: float
    maximum_power_kw: float
    target_energy_kwh: float | None = None
    priority: int = 50
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def __post_init__(self) -> None:
        if self.minimum_power_kw < 0 or self.maximum_power_kw < self.minimum_power_kw:
            msg = "flexibility power bounds are invalid"
            raise ValueError(msg)
        if self.target_energy_kwh is not None and self.target_energy_kwh < 0:
            msg = "target energy cannot be negative"
            raise ValueError(msg)
        if not 0 <= self.priority <= 100:
            msg = "priority must be between zero and one hundred"
            raise ValueError(msg)
