"""Dispatch port and v1 shadow-control adapter."""

from __future__ import annotations

# ruff: noqa: TC003
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class DispatchCommand:
    """One time-bounded asset power target."""

    command_key: str
    asset_code: str
    scheduled_at: datetime
    target_power_kw: float
    minimum_power_kw: float
    maximum_power_kw: float


@dataclass(frozen=True)
class DispatchOutcome:
    """Adapter receipt returned to the application layer."""

    command_key: str
    status: str
    executed_power_kw: float | None
    reason: str | None = None


class DispatchAdapter(Protocol):
    """Port implemented by a field MGCC/PMS or a simulator."""

    async def dispatch(self, commands: list[DispatchCommand]) -> list[DispatchOutcome]: ...


class SimulationDispatchAdapter:
    """Deterministic adapter that enforces resource guardrails and returns receipts."""

    async def dispatch(self, commands: list[DispatchCommand]) -> list[DispatchOutcome]:
        outcomes: list[DispatchOutcome] = []
        for command in commands:
            clipped = min(command.maximum_power_kw, max(command.minimum_power_kw, command.target_power_kw))
            status = "clipped" if clipped != command.target_power_kw else "executed"
            outcomes.append(
                DispatchOutcome(
                    command_key=command.command_key,
                    status=status,
                    executed_power_kw=clipped,
                    reason="目标功率已按设备边界裁剪" if status == "clipped" else None,
                )
            )
        return outcomes
