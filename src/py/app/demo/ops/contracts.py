"""Contracts for versioned reusable demo packages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def _empty_settings() -> Mapping[str, str]:
    return {}


def _empty_details() -> Mapping[str, object]:
    return {}


class DemoAction(StrEnum):
    """Supported demo package lifecycle actions."""

    PREFLIGHT = "preflight"
    INSTALL = "install"
    VALIDATE = "validate"
    CLEANUP = "cleanup"

    @property
    def mutates_data(self) -> bool:
        """Return whether the action can change persisted business data."""
        return self in {DemoAction.INSTALL, DemoAction.CLEANUP}


class DemoStepStatus(StrEnum):
    """Execution status for one demo plan step."""

    PLANNED = "planned"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DemoExecutionContext:
    """Runtime parameters for one demo package operation."""

    package_key: str
    namespace: str
    profile: str = "full"
    apply: bool = False
    settings: Mapping[str, str] = field(default_factory=_empty_settings)


@dataclass(frozen=True, slots=True)
class DemoPlanStep:
    """One visible unit of work in a package plan or run."""

    module_key: str
    action: DemoAction
    status: DemoStepStatus
    summary: str
    details: Mapping[str, object] = field(default_factory=_empty_details)


@dataclass(frozen=True, slots=True)
class DemoRunResult:
    """Result returned by a demo package action."""

    package_key: str
    namespace: str
    profile: str
    action: DemoAction
    applied: bool
    status: DemoStepStatus
    steps: Sequence[DemoPlanStep]


class DemoPackage(Protocol):
    """Package boundary implemented by one reusable demo scenario."""

    @property
    def key(self) -> str:
        """Stable package key."""
        ...

    @property
    def version(self) -> str:
        """Package contract version."""
        ...

    @property
    def description(self) -> str:
        """Human-readable package description."""
        ...

    @property
    def supported_profiles(self) -> Sequence[str]:
        """Supported profile keys."""
        ...

    async def execute(self, context: DemoExecutionContext, action: DemoAction) -> DemoRunResult:
        """Plan or run one supported demo action."""
        ...
