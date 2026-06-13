from __future__ import annotations

from typing import Any

GOOD_METERING_COVERAGE_PCT = 90
WARNING_METERING_COVERAGE_PCT = 70

OPTIMIZATION_SCENARIOS: dict[str, dict[str, Any]] = {
    "warehouse_lighting": {
        "name": "仓库照明分区降载",
        "parameter_schema": {
            "controlled_load_pct": 25,
            "reduction_pct": 30,
        },
        "method": "measure_based_rule",
        "source_name": "企业运行假设",
    },
    "warehouse_idle_reduction": {
        "name": "仓储设备空转压降",
        "parameter_schema": {
            "idle_energy_pct": 18,
            "idle_reduction_pct": 35,
        },
        "method": "measure_based_rule",
        "source_name": "企业运行假设",
    },
    "off_peak_charging": {
        "name": "充电负荷错峰",
        "parameter_schema": {
            "shifted_energy_pct": 40,
            "price_delta_cny_per_kwh": 0.35,
        },
        "method": "tariff_shift",
        "source_name": "企业分时电价假设",
    },
    "compressed_air_pressure": {
        "name": "空压站参数优化",
        "parameter_schema": {
            "current_pressure_mpa": 0.8,
            "target_pressure_mpa": 0.75,
            "expected_saving_pct": 5,
        },
        "method": "engineering_assumption",
        "source_name": "企业运行假设",
    },
}


def scenario_config(scenario_type: str) -> dict[str, Any]:
    """Return scenario configuration or raise for invalid scenario."""
    if scenario_type not in OPTIMIZATION_SCENARIOS:
        msg = "优化场景无效"
        raise ValueError(msg)
    return OPTIMIZATION_SCENARIOS[scenario_type]


def data_quality_status(record_count: int, metering_coverage_pct: float, estimated_count: int) -> str:
    if record_count <= 0:
        return "missing"
    if metering_coverage_pct >= GOOD_METERING_COVERAGE_PCT and estimated_count == 0:
        return "good"
    if metering_coverage_pct >= WARNING_METERING_COVERAGE_PCT:
        return "warning"
    return "low"


def data_quality_label(value: str) -> str:
    return {
        "good": "良好",
        "warning": "需复核",
        "low": "覆盖不足",
        "missing": "暂无数据",
    }.get(value, value)


def confidence_level(summary: dict[str, Any]) -> str:
    if summary["quality"] == "good" and summary["workload_record_count"]:
        return "medium"
    if summary["quality"] in {"good", "warning"}:
        return "low"
    return "reference"


def scenario_options(summary: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for scenario_type, config in OPTIMIZATION_SCENARIOS.items():
        items.append(
            {
                "scenario_type": scenario_type,
                "scenario_name": config["name"],
                "method": config["method"],
                "source_name": config["source_name"],
                "default_parameters": config["parameter_schema"],
                "baseline_energy": summary["total_input"],
                "baseline_cost": summary["total_cost"],
                "confidence_level": confidence_level(summary),
            }
        )
    return items


def merge_parameters(scenario_type: str, parameters: dict[str, Any] | None) -> dict[str, Any]:
    config = scenario_config(scenario_type)
    return {**config["parameter_schema"], **(parameters or {})}


def simulate_scenario(scenario_type: str, baseline_energy: float, baseline_cost: float, parameters: dict[str, Any]) -> dict[str, Any]:
    scenario_config(scenario_type)
    status = "ok" if baseline_energy > 0 else "invalid_baseline"
    saving_energy = 0.0
    cost_delta = 0.0
    if scenario_type == "warehouse_lighting":
        saving_energy = baseline_energy * _pct(parameters, "controlled_load_pct") * _pct(parameters, "reduction_pct")
    elif scenario_type == "warehouse_idle_reduction":
        saving_energy = baseline_energy * _pct(parameters, "idle_energy_pct") * _pct(parameters, "idle_reduction_pct")
    elif scenario_type == "off_peak_charging":
        shifted_energy = baseline_energy * _pct(parameters, "shifted_energy_pct")
        cost_delta = -shifted_energy * _float(parameters.get("price_delta_cny_per_kwh"), 0.0)
    elif scenario_type == "compressed_air_pressure":
        saving_energy = baseline_energy * _pct(parameters, "expected_saving_pct")
    saving_energy = max(0.0, saving_energy)
    expected_energy = max(0.0, baseline_energy - saving_energy)
    saving_rate_pct = _ratio_or_zero(saving_energy * 100, baseline_energy)
    if scenario_type != "off_peak_charging" and baseline_energy > 0 and baseline_cost > 0:
        cost_delta = -(baseline_cost * saving_rate_pct / 100)
    return {
        "status": status,
        "baseline_energy": round(baseline_energy, 4),
        "expected_energy": round(expected_energy, 4),
        "saving_energy": round(saving_energy, 4),
        "saving_rate_pct": saving_rate_pct,
        "cost_delta_cny": round(cost_delta, 4),
        "unit": "kWh",
    }


def before_parameters(scenario_type: str, parameters: dict[str, Any], baseline_energy: float) -> dict[str, Any]:
    result = {"baseline_energy": round(baseline_energy, 4)}
    if scenario_type == "compressed_air_pressure":
        result["current_pressure_mpa"] = parameters.get("current_pressure_mpa")
    return result


def assumptions(scenario_type: str, parameters: dict[str, Any]) -> dict[str, Any]:
    result = {"scenario_type": scenario_type, "parameters": parameters}
    if scenario_type == "off_peak_charging":
        result["energy_saving_note"] = "错峰仅测算费用变化, 不计入节能量。"
    return result


def _ratio_or_zero(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0
    return round(numerator / denominator, 4)


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pct(parameters: dict[str, Any], key: str) -> float:
    return max(0.0, min(_float(parameters.get(key), 0.0), 100.0)) / 100
