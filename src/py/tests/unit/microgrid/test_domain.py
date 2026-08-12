"""Pure microgrid domain invariant tests."""

from datetime import time

import pytest

from app.domain.microgrid.domain.entities import FlexibilityWindow, Scenario
from app.domain.microgrid.domain.exceptions import PublishedScenarioMutationError, ScenarioNotReadyError
from app.domain.microgrid.domain.policies import StoragePolicy, advance_soc

pytestmark = pytest.mark.unit


def test_scenario_publish_freezes_parameter_changes() -> None:
    scenario = Scenario(
        code="demo",
        version=1,
        parameters={"grid": {}, "pv": {}, "storage": {}, "tariff": {}},
    )
    scenario.publish()

    with pytest.raises(PublishedScenarioMutationError):
        scenario.update_parameters({})


def test_scenario_requires_core_sections() -> None:
    scenario = Scenario(code="demo", version=1, parameters={"grid": {}})

    with pytest.raises(ScenarioNotReadyError):
        scenario.publish()


def test_flexibility_window_validates_power_envelope() -> None:
    with pytest.raises(ValueError, match="power bounds"):
        FlexibilityWindow(start=time(8), end=time(18), minimum_power_kw=80, maximum_power_kw=40)


def test_soc_transition_respects_efficiency_and_bounds() -> None:
    policy = StoragePolicy(
        capacity_kwh=1000,
        minimum_soc=0.15,
        maximum_soc=0.9,
        charging_efficiency=0.95,
        discharging_efficiency=0.95,
    )
    charged = advance_soc(soc=0.5, charge_kw=100, discharge_kw=0, interval_hours=0.25, policy=policy)
    discharged = advance_soc(soc=charged, charge_kw=0, discharge_kw=100, interval_hours=0.25, policy=policy)

    assert charged == pytest.approx(0.52375)
    assert discharged == pytest.approx(0.497434, rel=1e-5)
    assert advance_soc(soc=0.89, charge_kw=500, discharge_kw=0, interval_hours=1, policy=policy) == 0.9
