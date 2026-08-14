"""Pyomo/HiGHS rolling-horizon microgrid optimizer."""

from __future__ import annotations

# ruff: noqa: PLR0915, PLR2004, RUF001, TC003
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition


@dataclass(frozen=True)
class SchedulePoint:
    """One optimized interval."""

    valid_at: datetime
    load_kw: float
    pv_kw: float
    grid_import_kw: float
    grid_export_kw: float
    battery_charge_kw: float
    battery_discharge_kw: float
    charger_kw: float
    lighting_kw: float
    generator_kw: float
    curtailed_pv_kw: float
    soc_pct: float
    tariff_cny_per_kwh: float
    interval_cost_cny: float


@dataclass(frozen=True)
class OptimizationResult:
    """Solver result and business comparison to the inflexible baseline."""

    status: str
    solver_seconds: float
    mip_gap: float | None
    objective_cny: float | None
    baseline_cost_cny: float
    savings_cny: float | None
    peak_reduction_kw: float | None
    baseline_peak_kw: float | None
    optimized_peak_kw: float | None
    peak_change_kw: float | None
    carbon_reduction_kg: float | None
    schedule: list[SchedulePoint]
    cost_breakdown: dict[str, float]
    diagnostics: list[dict[str, Any]]


def optimize_dispatch(
    *,
    index: list[datetime],
    fixed_load_kw: list[float],
    pv_available_kw: list[float],
    tariff_cny_per_kwh: list[float],
    parameters: dict[str, Any],
) -> OptimizationResult:
    """Solve a deterministic 15-minute MILP for the published scenario."""
    count = len(index)
    if not count or not (count == len(fixed_load_kw) == len(pv_available_kw) == len(tariff_cny_per_kwh)):
        msg = "optimization series lengths must be non-zero and equal"
        raise ValueError(msg)

    interval_hours = float(parameters.get("interval_minutes", 15)) / 60
    grid = parameters["grid"]
    storage = parameters["storage"]
    charger = parameters.get("charger", {})
    lighting = parameters.get("lighting", {})
    generator = parameters.get("generator", {})
    economics = parameters.get("economics", {})

    pcc_capacity = float(grid["pcc_capacity_kw"])
    export_capacity = float(grid.get("export_capacity_kw", 0))
    battery_power = float(storage["power_kw"])
    battery_capacity = float(storage["capacity_kwh"])
    minimum_energy = battery_capacity * float(storage.get("minimum_soc_pct", 15)) / 100
    maximum_energy = battery_capacity * float(storage.get("maximum_soc_pct", 90)) / 100
    initial_energy = battery_capacity * float(storage.get("initial_soc_pct", 50)) / 100
    eta_charge = float(storage.get("charging_efficiency", 0.95))
    eta_discharge = float(storage.get("discharging_efficiency", 0.95))
    charger_max = float(charger.get("maximum_power_kw", 0))
    charger_min = float(charger.get("minimum_power_kw", 0))
    charger_target = float(charger.get("target_energy_kwh", 0))
    charger_start = int(charger.get("start_interval", 0))
    charger_end = min(int(charger.get("end_interval", count)), count)
    charger_allowed = {int(value) for value in charger.get("enabled_intervals", range(charger_start, charger_end))}
    lighting_baseline = float(lighting.get("baseline_power_kw", 0))
    lighting_minimum = float(lighting.get("minimum_power_kw", lighting_baseline))
    lighting_minimums = [float(value) for value in lighting.get("minimum_by_interval_kw", [lighting_minimum] * count)]
    lighting_maximums = [float(value) for value in lighting.get("maximum_by_interval_kw", [lighting_baseline] * count)]
    generator_max = float(generator.get("maximum_power_kw", 0))
    generator_min = float(generator.get("minimum_power_kw", 0))
    generator_ramp = float(generator.get("ramp_kw_per_interval", generator_max))
    reserve_margin = float(parameters.get("reserve_margin_pct", 8)) / 100
    objective_weights = parameters.get("objective_weights", {})
    energy_weight = float(objective_weights.get("energy", 1))
    peak_weight = float(objective_weights.get("peak", 1))
    carbon_weight = float(objective_weights.get("carbon", 1))
    terminal_soc_pct = float(storage.get("terminal_soc_pct", storage.get("initial_soc_pct", 50)))
    terminal_energy = battery_capacity * terminal_soc_pct / 100
    charger_hard_constraint = bool(charger.get("hard_constraint", True))
    charger_penalty = float(charger.get("penalty_cny_per_kwh", 8))

    model = pyo.ConcreteModel()
    model.t = pyo.RangeSet(0, count - 1)
    model.grid_import = pyo.Var(model.t, domain=pyo.NonNegativeReals, bounds=(0, pcc_capacity))
    model.grid_export = pyo.Var(model.t, domain=pyo.NonNegativeReals, bounds=(0, export_capacity))
    model.pv_used = pyo.Var(model.t, domain=pyo.NonNegativeReals)
    model.charge = pyo.Var(model.t, domain=pyo.NonNegativeReals, bounds=(0, battery_power))
    model.discharge = pyo.Var(model.t, domain=pyo.NonNegativeReals, bounds=(0, battery_power))
    model.charge_mode = pyo.Var(model.t, domain=pyo.Binary)
    model.energy = pyo.Var(model.t, domain=pyo.NonNegativeReals, bounds=(minimum_energy, maximum_energy))
    model.charger = pyo.Var(model.t, domain=pyo.NonNegativeReals, bounds=(0, charger_max))
    model.lighting = pyo.Var(model.t, domain=pyo.NonNegativeReals, bounds=(0, lighting_baseline))
    model.generator = pyo.Var(model.t, domain=pyo.NonNegativeReals, bounds=(0, generator_max))
    model.generator_on = pyo.Var(model.t, domain=pyo.Binary)
    model.generator_start = pyo.Var(model.t, domain=pyo.Binary)
    model.peak = pyo.Var(domain=pyo.NonNegativeReals, bounds=(0, pcc_capacity))
    model.charger_shortfall = pyo.Var(domain=pyo.NonNegativeReals)

    model.pv_limit = pyo.Constraint(model.t, rule=lambda _, t: model.pv_used[t] <= pv_available_kw[t])
    model.charge_exclusive = pyo.Constraint(
        model.t, rule=lambda _, t: model.charge[t] <= battery_power * model.charge_mode[t]
    )
    model.discharge_exclusive = pyo.Constraint(
        model.t, rule=lambda _, t: model.discharge[t] <= battery_power * (1 - model.charge_mode[t])
    )
    model.peak_limit = pyo.Constraint(model.t, rule=lambda _, t: model.grid_import[t] <= model.peak)
    model.power_balance = pyo.Constraint(
        model.t,
        rule=lambda _, t: model.grid_import[t] + model.pv_used[t] + model.discharge[t] + model.generator[t]
        == fixed_load_kw[t] + model.charger[t] + model.lighting[t] + model.charge[t] + model.grid_export[t],
    )

    def energy_balance(_: pyo.ConcreteModel, t: int) -> pyo.Constraint:
        previous = initial_energy if t == 0 else model.energy[t - 1]
        return model.energy[t] == previous + interval_hours * (
            eta_charge * model.charge[t] - model.discharge[t] / eta_discharge
        )

    model.energy_balance = pyo.Constraint(model.t, rule=energy_balance)
    model.terminal_energy = pyo.Constraint(expr=model.energy[count - 1] >= terminal_energy)
    for t in range(count):
        if t not in charger_allowed:
            model.charger[t].fix(0)
        elif charger_min > 0:
            model.charger[t].setlb(charger_min)
        model.lighting[t].setlb(lighting_minimums[t])
        model.lighting[t].setub(lighting_maximums[t])
    if charger_target > 0:
        delivered_energy = sum(model.charger[t] * interval_hours for t in charger_allowed)
        if charger_hard_constraint:
            model.charger_shortfall.fix(0)
            model.charger_target = pyo.Constraint(expr=delivered_energy >= charger_target)
        else:
            model.charger_target = pyo.Constraint(expr=delivered_energy + model.charger_shortfall >= charger_target)
    else:
        model.charger_shortfall.fix(0)

    model.generator_minimum = pyo.Constraint(
        model.t, rule=lambda _, t: model.generator[t] >= generator_min * model.generator_on[t]
    )
    model.generator_maximum = pyo.Constraint(
        model.t, rule=lambda _, t: model.generator[t] <= generator_max * model.generator_on[t]
    )

    def generator_start_rule(_: pyo.ConcreteModel, t: int) -> pyo.Constraint:
        previous_on = 0 if t == 0 else model.generator_on[t - 1]
        return model.generator_start[t] >= model.generator_on[t] - previous_on

    model.generator_start_rule = pyo.Constraint(model.t, rule=generator_start_rule)
    if generator_ramp > 0 and count > 1:
        model.generator_ramp_up = pyo.Constraint(
            pyo.RangeSet(1, count - 1),
            rule=lambda _, t: model.generator[t] - model.generator[t - 1] <= generator_ramp,
        )
        model.generator_ramp_down = pyo.Constraint(
            pyo.RangeSet(1, count - 1),
            rule=lambda _, t: model.generator[t - 1] - model.generator[t] <= generator_ramp,
        )
    model.reserve_margin = pyo.Constraint(
        model.t,
        rule=lambda _, t: pcc_capacity
        - model.grid_import[t]
        + battery_power
        - model.discharge[t]
        + generator_max
        - model.generator[t]
        >= fixed_load_kw[t] * reserve_margin,
    )

    degradation_cost = float(economics.get("battery_degradation_cny_per_kwh", 0.08))
    export_price = float(economics.get("export_cny_per_kwh", 0.25))
    demand_cost = float(economics.get("demand_cny_per_kw_day", 0.35))
    carbon_factor = float(economics.get("grid_carbon_kg_per_kwh", 0.5703))
    carbon_price = float(economics.get("carbon_cny_per_kg", 0.08))
    curtailment_cost = float(economics.get("curtailment_cny_per_kwh", 0.02))
    generator_cost = float(generator.get("fuel_cny_per_kwh", 1.8))
    generator_start_cost = float(generator.get("start_cost_cny", 0))
    model.objective = pyo.Objective(
        expr=sum(
            interval_hours
            * (
                energy_weight
                * (
                    model.grid_import[t] * tariff_cny_per_kwh[t]
                    - model.grid_export[t] * export_price
                    + (model.charge[t] + model.discharge[t]) * degradation_cost
                    + (pv_available_kw[t] - model.pv_used[t]) * curtailment_cost
                    + model.generator[t] * generator_cost
                )
                + carbon_weight * model.grid_import[t] * carbon_factor * carbon_price
            )
            + energy_weight * model.generator_start[t] * generator_start_cost
            for t in range(count)
        )
        + peak_weight * model.peak * demand_cost
        + model.charger_shortfall * charger_penalty,
        sense=pyo.minimize,
    )

    started = time.perf_counter()
    solver = pyo.SolverFactory("appsi_highs")
    solver.options["time_limit"] = 30
    solver.options["mip_gap"] = 0.01
    results = solver.solve(model, tee=False, load_solutions=False)
    solver_seconds = time.perf_counter() - started
    termination = results.solver.termination_condition
    feasible = results.solver.status in {SolverStatus.ok, SolverStatus.warning} and termination in {
        TerminationCondition.optimal,
        TerminationCondition.feasible,
        TerminationCondition.maxTimeLimit,
    }

    available_charging_hours = len(charger_allowed) * interval_hours
    baseline_charger_kw = (
        min(charger_max, max(charger_min, charger_target / available_charging_hours))
        if charger_target > 0 and available_charging_hours > 0
        else 0.0
    )
    baseline_demand = [
        fixed_load_kw[t] + lighting_baseline + (baseline_charger_kw if t in charger_allowed else 0.0)
        for t in range(count)
    ]
    baseline_import = [max(baseline_demand[t] - pv_available_kw[t], 0) for t in range(count)]
    baseline_export = [min(max(pv_available_kw[t] - baseline_demand[t], 0), export_capacity) for t in range(count)]
    baseline_curtailment = [max(pv_available_kw[t] - baseline_demand[t] - baseline_export[t], 0) for t in range(count)]
    baseline_energy_cost = sum(
        (
            baseline_import[t] * (tariff_cny_per_kwh[t] + carbon_factor * carbon_price)
            - baseline_export[t] * export_price
            + baseline_curtailment[t] * curtailment_cost
        )
        * interval_hours
        for t in range(count)
    )
    baseline_cost = baseline_energy_cost + max(baseline_import) * demand_cost
    diagnostics: list[dict[str, Any]] = []
    if not feasible:
        deliverable_charger_kwh = len(charger_allowed) * charger_max * interval_hours
        if charger_target > deliverable_charger_kwh + 1e-6:
            diagnostics.append(
                {
                    "constraint": "charger_energy_deadline",
                    "severity": "error",
                    "message": (
                        f"充电目标 {charger_target:.1f} kWh 超过时窗最大可交付电量 {deliverable_charger_kwh:.1f} kWh"
                    ),
                }
            )
        shortage_intervals = [
            t
            for t in range(count)
            if fixed_load_kw[t] + lighting_minimums[t] + (charger_min if t in charger_allowed else 0)
            > pcc_capacity + pv_available_kw[t] + battery_power + generator_max
        ]
        if shortage_intervals:
            diagnostics.append(
                {
                    "constraint": "power_adequacy",
                    "severity": "error",
                    "message": f"{len(shortage_intervals)} 个时段的最小负荷超过PCC、PV、储能与机组总供给能力",
                }
            )
        diagnostics.append(
            {
                "constraint": "system_feasibility",
                "severity": "error",
                "message": f"HiGHS termination: {termination}",
            }
        )
        return OptimizationResult(
            status="infeasible",
            solver_seconds=solver_seconds,
            mip_gap=None,
            objective_cny=None,
            baseline_cost_cny=baseline_cost,
            savings_cny=None,
            peak_reduction_kw=None,
            baseline_peak_kw=max(baseline_import),
            optimized_peak_kw=None,
            peak_change_kw=None,
            carbon_reduction_kg=None,
            schedule=[],
            cost_breakdown={},
            diagnostics=diagnostics,
        )
    model.solutions.load_from(results)

    schedule: list[SchedulePoint] = []
    energy_cost = degradation_total = carbon_cost_total = curtailment_total = generator_total = 0.0
    for t, valid_at in enumerate(index):
        imported = pyo.value(model.grid_import[t])
        exported = pyo.value(model.grid_export[t])
        charge = pyo.value(model.charge[t])
        discharge = pyo.value(model.discharge[t])
        pv_used = pyo.value(model.pv_used[t])
        generated = pyo.value(model.generator[t])
        interval_energy_cost = interval_hours * (imported * tariff_cny_per_kwh[t] - exported * export_price)
        interval_degradation = interval_hours * (charge + discharge) * degradation_cost
        interval_carbon = interval_hours * imported * carbon_factor * carbon_price
        interval_curtailment = interval_hours * max(pv_available_kw[t] - pv_used, 0) * curtailment_cost
        interval_generator = (
            interval_hours * generated * generator_cost + pyo.value(model.generator_start[t]) * generator_start_cost
        )
        energy_cost += interval_energy_cost
        degradation_total += interval_degradation
        carbon_cost_total += interval_carbon
        curtailment_total += interval_curtailment
        generator_total += interval_generator
        schedule.append(
            SchedulePoint(
                valid_at=valid_at,
                load_kw=fixed_load_kw[t],
                pv_kw=pv_used,
                grid_import_kw=imported,
                grid_export_kw=exported,
                battery_charge_kw=charge,
                battery_discharge_kw=discharge,
                charger_kw=pyo.value(model.charger[t]),
                lighting_kw=pyo.value(model.lighting[t]),
                generator_kw=generated,
                curtailed_pv_kw=max(pv_available_kw[t] - pv_used, 0),
                soc_pct=max(
                    minimum_energy / battery_capacity * 100,
                    min(maximum_energy / battery_capacity * 100, pyo.value(model.energy[t]) / battery_capacity * 100),
                ),
                tariff_cny_per_kwh=tariff_cny_per_kwh[t],
                interval_cost_cny=(
                    interval_energy_cost
                    + interval_degradation
                    + interval_carbon
                    + interval_curtailment
                    + interval_generator
                ),
            )
        )
    optimized_peak = max(point.grid_import_kw for point in schedule)
    shortfall = float(pyo.value(model.charger_shortfall))
    optimized_cost = (
        energy_cost
        + optimized_peak * demand_cost
        + degradation_total
        + carbon_cost_total
        + curtailment_total
        + generator_total
        + shortfall * charger_penalty
    )
    optimized_grid_kwh = sum(point.grid_import_kw * interval_hours for point in schedule)
    baseline_grid_kwh = sum(baseline_import) * interval_hours
    if shortfall > 1e-6:
        diagnostics.append(
            {
                "constraint": "charger_energy_deadline",
                "severity": "warning",
                "message": f"充电任务欠交 {shortfall:.1f} kWh，已计入违约成本",
                "shortfallKwh": shortfall,
            }
        )
    return OptimizationResult(
        status="optimal" if termination == TerminationCondition.optimal else "feasible",
        solver_seconds=solver_seconds,
        mip_gap=0.0 if termination == TerminationCondition.optimal else 0.01,
        objective_cny=optimized_cost,
        baseline_cost_cny=baseline_cost,
        savings_cny=baseline_cost - optimized_cost,
        peak_reduction_kw=max(baseline_import) - optimized_peak,
        baseline_peak_kw=max(baseline_import),
        optimized_peak_kw=optimized_peak,
        peak_change_kw=optimized_peak - max(baseline_import),
        carbon_reduction_kg=(baseline_grid_kwh - optimized_grid_kwh) * carbon_factor,
        schedule=schedule,
        cost_breakdown={
            "energy_cost_cny": energy_cost,
            "demand_cost_cny": optimized_peak * demand_cost,
            "battery_degradation_cny": degradation_total,
            "carbon_cost_cny": carbon_cost_total,
            "curtailment_cost_cny": curtailment_total,
            "generator_cost_cny": generator_total,
            "flexibility_penalty_cny": shortfall * charger_penalty,
        },
        diagnostics=diagnostics,
    )
