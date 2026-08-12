"""Microgrid domain exceptions."""


class MicrogridDomainError(ValueError):
    """Base exception for a violated microgrid business rule."""


class PublishedScenarioMutationError(MicrogridDomainError):
    """Raised when a published scenario is mutated."""


class ScenarioNotReadyError(MicrogridDomainError):
    """Raised when a scenario cannot be published or executed."""


class InfeasibleDispatchError(MicrogridDomainError):
    """Raised when a non-feasible schedule is dispatched."""
