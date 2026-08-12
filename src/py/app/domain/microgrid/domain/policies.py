"""Physics-based microgrid domain policies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoragePolicy:
    """Battery operating envelope."""

    capacity_kwh: float
    minimum_soc: float
    maximum_soc: float
    charging_efficiency: float
    discharging_efficiency: float

    def __post_init__(self) -> None:
        if self.capacity_kwh <= 0:
            msg = "storage capacity must be positive"
            raise ValueError(msg)
        if not 0 <= self.minimum_soc < self.maximum_soc <= 1:
            msg = "storage SOC bounds are invalid"
            raise ValueError(msg)
        if not 0 < self.charging_efficiency <= 1 or not 0 < self.discharging_efficiency <= 1:
            msg = "storage efficiencies must be in (0, 1]"
            raise ValueError(msg)


def advance_soc(
    *,
    soc: float,
    charge_kw: float,
    discharge_kw: float,
    interval_hours: float,
    policy: StoragePolicy,
) -> float:
    """Advance SOC using the signed storage energy balance."""
    if charge_kw < 0 or discharge_kw < 0 or interval_hours <= 0:
        msg = "power must be non-negative and interval must be positive"
        raise ValueError(msg)
    next_soc = (
        soc
        + (
            policy.charging_efficiency * charge_kw * interval_hours
            - discharge_kw * interval_hours / policy.discharging_efficiency
        )
        / policy.capacity_kwh
    )
    return min(policy.maximum_soc, max(policy.minimum_soc, next_soc))
