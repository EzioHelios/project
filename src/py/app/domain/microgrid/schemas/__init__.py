"""HTTP input schemas for microgrid commands."""

from typing import Any

from app.lib.schema import CamelizedBaseStruct


class BootstrapDemoRequest(CamelizedBaseStruct, kw_only=True):
    """Request to initialize the tenant's Xiangtai demo."""

    site_code: str = "xiangtai-taizhou"


class CreateScenarioRequest(CamelizedBaseStruct, kw_only=True):
    """Create a draft scenario version."""

    site_id: int
    code: str
    name: str
    parameters: dict[str, Any]
    source_name: str
    confidence_level: float = 0.5


class CreateFlexibilityContractRequest(CamelizedBaseStruct, kw_only=True):
    """Create or update a flexible-load envelope."""

    scenario_id: int
    asset_id: int
    contract_type: str
    start_minute: int
    end_minute: int
    minimum_power_kw: float
    maximum_power_kw: float
    target_energy_kwh: float | None = None
    priority: int = 50
    penalty_cny_per_kwh: float = 5
    enabled: bool = True


class RunForecastRequest(CamelizedBaseStruct, kw_only=True):
    """Launch a forecast run."""

    site_id: int
    scenario_id: int | None = None
    start: str | None = None


class RunOptimizationRequest(CamelizedBaseStruct, kw_only=True):
    """Launch an optimization run."""

    forecast_run_id: int


class CreateDispatchBatchRequest(CamelizedBaseStruct, kw_only=True):
    """Submit a feasible run to shadow dispatch."""

    optimization_run_id: int


__all__ = (
    "BootstrapDemoRequest",
    "CreateDispatchBatchRequest",
    "CreateFlexibilityContractRequest",
    "CreateScenarioRequest",
    "RunForecastRequest",
    "RunOptimizationRequest",
)
