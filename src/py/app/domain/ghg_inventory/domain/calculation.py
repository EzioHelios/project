"""Whitelisted calculation functions for published high-frequency methods."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class CalculationOutput:
    gas_code: str
    gas_mass_kg: Decimal
    gwp_value: Decimal
    co2e_kg: Decimal
    scope2_method: str = "not_applicable"
    result_kind: str = "emission"


def calculate(
    method_code: str,
    activity_amount: Decimal,
    parameters: dict[str, Decimal],
    payload: dict[str, Any],
) -> CalculationOutput:
    """Execute a controlled method; arbitrary expressions are never evaluated."""
    calculators = {
        "F01_NCV": _fuel_ncv,
        "F02_EF": _activity_factor,
        "F05_INVENTORY": _fugitive_inventory,
        "F08_PURCHASED_ENERGY": _purchased_energy,
        "F09_DISTANCE": _distance,
        "F09_TRANSPORT_ACTIVITY": _transport_activity,
    }
    calculator = calculators.get(method_code)
    if calculator is None:
        msg = f"计算方法 {method_code} 尚未发布为可执行方法"
        raise ValueError(msg)
    return calculator(activity_amount, parameters, payload)


def _fuel_ncv(activity: Decimal, p: dict[str, Decimal], _payload: dict[str, Any]) -> CalculationOutput:
    t_co2 = activity * p["NCV"] * p["CARBON_CONTENT"] * p["OXIDATION_FACTOR"] * Decimal(44) / Decimal(12)
    mass = t_co2 * Decimal(1000)
    return CalculationOutput("CO2", mass, Decimal(1), mass)


def _activity_factor(activity: Decimal, p: dict[str, Decimal], payload: dict[str, Any]) -> CalculationOutput:
    gas = str(payload.get("gas_code") or "CO2")
    unit_conversion = p.get("UNIT_CONVERSION", Decimal(1))
    gwp = p.get("GWP", Decimal(1))
    gas_mass = activity * p["EMISSION_FACTOR"] * unit_conversion
    return CalculationOutput(gas, gas_mass, gwp, gas_mass * gwp)


def _fugitive_inventory(_activity: Decimal, p: dict[str, Decimal], payload: dict[str, Any]) -> CalculationOutput:
    gas = str(payload.get("gas_code") or "HFC")
    gas_mass = p["OPENING_STOCK"] + p["PURCHASES"] + p["CHARGES"] - p["CLOSING_STOCK"] - p["TRANSFERS"] - p["RECOVERY"]
    if gas_mass < 0:
        msg = "逸散盘存质量平衡结果不能为负数"
        raise ValueError(msg)
    gwp = p["GWP"]
    return CalculationOutput(gas, gas_mass, gwp, gas_mass * gwp)


def _purchased_energy(activity: Decimal, p: dict[str, Decimal], payload: dict[str, Any]) -> CalculationOutput:
    co2e = activity * p["ENERGY_FACTOR"]
    scope2_method = str(payload.get("scope2_method") or "location")
    return CalculationOutput("CO2e", co2e, Decimal(1), co2e, scope2_method=scope2_method)


def _distance(activity: Decimal, p: dict[str, Decimal], _payload: dict[str, Any]) -> CalculationOutput:
    co2e = activity * p["DISTANCE_FACTOR"]
    return CalculationOutput("CO2e", co2e, Decimal(1), co2e)


def _transport_activity(activity: Decimal, p: dict[str, Decimal], _payload: dict[str, Any]) -> CalculationOutput:
    co2e = activity * p["TRANSPORT_FACTOR"]
    return CalculationOutput("CO2e", co2e, Decimal(1), co2e)
