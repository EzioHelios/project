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


class UpdateScenarioRequest(CamelizedBaseStruct, kw_only=True):
    """Update the site's working draft, creating it from a published version when needed."""

    parameters: dict[str, Any]
    name: str | None = None
    tariff_plan_id: int | None = None
    grid_emission_factor_id: int | None = None
    change_summary: str | None = None


class MeterBindingItemRequest(CamelizedBaseStruct, kw_only=True):
    """One manually confirmed meter binding."""

    asset_id: int
    equipment_id: int
    role: str
    point_code: str = "forward_active_total"
    direction: str = "import"
    sign: float = 1
    enabled: bool = True


class ReplaceMeterBindingsRequest(CamelizedBaseStruct, kw_only=True):
    """Replace a site's confirmed binding set."""

    monitor_sector_id: int | None = None
    bindings: list[MeterBindingItemRequest]


class ApplyBindingTemplateRequest(CamelizedBaseStruct, kw_only=True):
    """Explicit confirmation for the Xiangtai binding template."""

    confirm: bool = False


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
    hard_constraint: bool = True
    enabled: bool = True


class RunForecastRequest(CamelizedBaseStruct, kw_only=True):
    """Launch a forecast run."""

    site_id: int
    scenario_id: int | None = None
    start: str | None = None


class RunOptimizationRequest(CamelizedBaseStruct, kw_only=True):
    """Launch an optimization run."""

    forecast_run_id: int
    scenario_id: int | None = None
    purpose: str = "operational"
    acknowledge_quality_warning: bool = False


class CreateDispatchBatchRequest(CamelizedBaseStruct, kw_only=True):
    """Submit a feasible run to shadow dispatch."""

    optimization_run_id: int


__all__ = (
    "ApplyBindingTemplateRequest",
    "BootstrapDemoRequest",
    "CreateDispatchBatchRequest",
    "CreateFlexibilityContractRequest",
    "CreateScenarioRequest",
    "MeterBindingItemRequest",
    "ReplaceMeterBindingsRequest",
    "RunForecastRequest",
    "RunOptimizationRequest",
    "UpdateScenarioRequest",
)
