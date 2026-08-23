"""Lifecycle and double-counting policies for project-based reductions."""

from __future__ import annotations

from decimal import Decimal

# ruff: noqa: EM101, TRY003 - concise domain invariant messages belong at the guard site.


class ReductionDomainError(ValueError):
    """Raised when a reduction-domain invariant is violated."""


class ProjectLifecyclePolicy:
    """Validate explicit project transitions instead of accepting arbitrary status edits."""

    TRANSITIONS: dict[str, frozenset[str]] = {
        "draft": frozenset({"screening", "archived"}),
        "screening": frozenset({"approved", "draft", "archived"}),
        "approved": frozenset({"baseline_locked", "archived"}),
        "baseline_locked": frozenset({"implementing", "archived"}),
        "implementing": frozenset({"monitoring", "archived"}),
        "monitoring": frozenset({"calculated", "archived"}),
        "calculated": frozenset({"internally_reviewed", "monitoring", "archived"}),
        "internally_reviewed": frozenset({"verified", "calculated", "archived"}),
        "verified": frozenset({"registered", "closed", "archived"}),
        "registered": frozenset({"issued", "archived"}),
        "issued": frozenset({"closed", "archived"}),
        "closed": frozenset({"archived"}),
        "archived": frozenset(),
    }
    CATEGORIES = frozenset(
        {
            "energy_efficiency",
            "renewable_energy",
            "green_power",
            "fuel_switching",
            "process_material",
            "refrigerant_industrial_gas",
            "logistics",
            "waste_resource",
            "forestry_removal",
            "operational_optimization",
        }
    )

    @classmethod
    def ensure_transition(cls, current: str, target: str) -> None:
        if target not in cls.TRANSITIONS.get(current, frozenset()):
            msg = f"Project status cannot transition from {current!r} to {target!r}."
            raise ReductionDomainError(msg)

    @staticmethod
    def ensure_track(track: str) -> None:
        if track not in {"internal_action", "iso_14064_2", "ccer_project"}:
            raise ReductionDomainError("Unsupported reduction project track.")

    @classmethod
    def ensure_category(cls, category: str) -> None:
        if category not in cls.CATEGORIES:
            raise ReductionDomainError("Unsupported reduction project category.")


class CcerIssuancePolicy:
    """Protect the semantic boundary between estimates and issued carbon assets."""

    @staticmethod
    def ensure_asset_eligible(*, project_track: str, dossier_status: str, verified_tco2e: object) -> None:
        if project_track != "ccer_project":
            raise ReductionDomainError("Only a CCER project can create a CCER holding.")
        if dossier_status != "issued":
            raise ReductionDomainError("Only issued CCER can be posted to the carbon-asset ledger.")
        if Decimal(str(verified_tco2e or 0)) <= 0:
            raise ReductionDomainError("Issued quantity must be greater than zero.")

    @staticmethod
    def ensure_independent_validation(validation_body: str | None, verification_body: str | None) -> None:
        if validation_body and verification_body and validation_body.strip() == verification_body.strip():
            raise ReductionDomainError("The same organization cannot validate and verify one CCER project.")
