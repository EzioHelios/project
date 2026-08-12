"""Hybrid statistical and physics-based microgrid forecasting."""

from __future__ import annotations

# ruff: noqa: PLR2004, TC003
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pvlib
from sklearn.ensemble import HistGradientBoostingRegressor  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class QuantileForecastPoint:
    """One ordered P10/P50/P90 forecast point."""

    valid_at: datetime
    p10: float
    p50: float
    p90: float


def _lagged_feature(valid_at: datetime, temperature_c: float, series: list[float]) -> np.ndarray:
    """Build leakage-safe calendar, lag, rolling, and change features."""
    minute = valid_at.hour * 60 + valid_at.minute
    angle = 2 * np.pi * minute / 1440
    weekday_angle = 2 * np.pi * valid_at.weekday() / 7

    def lag(periods: int) -> float:
        return series[-periods] if len(series) >= periods else series[0]

    def rolling(periods: int) -> float:
        window = series[-min(periods, len(series)) :]
        return float(np.mean(window))

    return np.asarray(
        [
            np.sin(angle),
            np.cos(angle),
            np.sin(weekday_angle),
            np.cos(weekday_angle),
            temperature_c,
            float(valid_at.weekday() < 5),
            lag(4),
            lag(96),
            lag(672),
            rolling(4),
            rolling(96),
            rolling(672),
            float(max(series[-min(96, len(series)) :])),
            lag(1) - lag(4),
        ],
        dtype=float,
    )


def _fit_quantile_models(
    index: Sequence[datetime], load: Sequence[float], temperature: Sequence[float], *, end_position: int
) -> dict[float, HistGradientBoostingRegressor]:
    minimum_lag = 672
    positions = range(minimum_lag, end_position)
    features = np.vstack(
        [
            _lagged_feature(index[position], float(temperature[position]), list(load[:position]))
            for position in positions
        ]
    )
    target = np.asarray(load[minimum_lag:end_position], dtype=float)
    models: dict[float, HistGradientBoostingRegressor] = {}
    for quantile in (0.1, 0.5, 0.9):
        model = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=quantile,
            max_iter=180,
            max_leaf_nodes=24,
            learning_rate=0.06,
            random_state=20260812,
        )
        model.fit(features, target)
        models[quantile] = model
    return models


def _recursive_quantile_prediction(
    *,
    models: dict[float, HistGradientBoostingRegressor],
    history: Sequence[float],
    target_index: Sequence[datetime],
    target_temperature: Sequence[float],
) -> dict[float, np.ndarray]:
    extended = [float(value) for value in history]
    output = {0.1: [], 0.5: [], 0.9: []}
    for valid_at, temperature_c in zip(target_index, target_temperature, strict=True):
        features = _lagged_feature(valid_at, float(temperature_c), extended).reshape(1, -1)
        raw = {quantile: max(float(model.predict(features)[0]), 0) for quantile, model in models.items()}
        p50 = raw[0.5]
        output[0.1].append(min(raw[0.1], p50))
        output[0.5].append(p50)
        output[0.9].append(max(raw[0.9], p50))
        extended.append(p50)
    return {quantile: np.asarray(values, dtype=float) for quantile, values in output.items()}


def forecast_load_quantiles(
    *,
    history_index: Sequence[datetime],
    history_kw: Sequence[float],
    history_temperature_c: Sequence[float],
    forecast_index: Sequence[datetime],
    forecast_temperature_c: Sequence[float],
) -> tuple[list[QuantileForecastPoint], dict[str, float | str]]:
    """Forecast load with quantile gradient boosting and a calendar fallback."""
    target_index = pd.DatetimeIndex(forecast_index)
    history = np.asarray(history_kw, dtype=float)
    predictions: dict[float, np.ndarray] = {}
    enough_history = len(history) >= 672 + 192 and len(history_index) == len(history_temperature_c) == len(history)
    if not enough_history:
        base = max(float(np.nanmean(history)) if history.size else 420.0, 1.0)
        minutes = target_index.hour * 60 + target_index.minute
        daily = 0.72 + 0.28 * np.sin((minutes - 390) * np.pi / 720) ** 2
        weekday = np.where(target_index.dayofweek < 5, 1.0, 0.88)
        p50_values = base * daily * weekday
        model_name = "calendar-baseline-v1"
        mae = float(base * 0.08)
        baseline_mae = mae
        coverage = 0.8
    else:
        holdout_start = len(history) - 96
        backtest_models = _fit_quantile_models(
            history_index,
            history,
            history_temperature_c,
            end_position=holdout_start,
        )
        backtest = _recursive_quantile_prediction(
            models=backtest_models,
            history=history[:holdout_start],
            target_index=history_index[holdout_start:],
            target_temperature=history_temperature_c[holdout_start:],
        )
        mae = float(np.mean(np.abs(history[holdout_start:] - backtest[0.5])))
        coverage = float(
            np.mean((history[holdout_start:] >= backtest[0.1]) & (history[holdout_start:] <= backtest[0.9]))
        )
        seasonal_baseline = history[holdout_start - 96 : holdout_start]
        baseline_mae = float(np.mean(np.abs(history[holdout_start:] - seasonal_baseline)))
        if mae < baseline_mae:
            models = _fit_quantile_models(
                history_index,
                history,
                history_temperature_c,
                end_position=len(history),
            )
            predictions = _recursive_quantile_prediction(
                models=models,
                history=history,
                target_index=forecast_index,
                target_temperature=forecast_temperature_c,
            )
            p50_values = predictions[0.5]
            model_name = "hist-gradient-boosting-quantile-v1"
        else:
            p50_values = np.resize(history[-96:], len(target_index))
            model_name = "yesterday-same-interval-baseline-v1"
            mae = baseline_mae

    points: list[QuantileForecastPoint] = []
    for idx, valid_at in enumerate(target_index.to_pydatetime()):
        p50 = max(float(p50_values[idx]), 0)
        if predictions:
            p10 = min(float(predictions[0.1][idx]), p50)
            p90 = max(float(predictions[0.9][idx]), p50)
        else:
            p10, p90 = p50 * 0.9, p50 * 1.1
        points.append(QuantileForecastPoint(valid_at=valid_at, p10=p10, p50=p50, p90=p90))
    return points, {
        "model": model_name,
        "mae_kw": round(mae, 3),
        "baseline_mae_kw": round(baseline_mae, 3),
        "coverage": round(coverage, 4),
    }


def forecast_pv_quantiles(
    *,
    latitude: float,
    longitude: float,
    dc_capacity_kw: float,
    ac_capacity_kw: float,
    tilt_deg: float,
    azimuth_deg: float,
    weather: pd.DataFrame,
) -> list[QuantileForecastPoint]:
    """Produce a PVWatts forecast through pvlib ModelChain."""
    if weather.empty:
        return []
    location = pvlib.location.Location(latitude, longitude, tz=str(weather.index.tz or "Asia/Shanghai"))
    mount = pvlib.pvsystem.FixedMount(surface_tilt=tilt_deg, surface_azimuth=azimuth_deg)
    array = pvlib.pvsystem.Array(
        mount=mount,
        module_parameters={"pdc0": dc_capacity_kw * 1000, "gamma_pdc": -0.0035},
        temperature_model_parameters=pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_glass"],
    )
    system = pvlib.pvsystem.PVSystem(
        arrays=[array],
        inverter_parameters={"pdc0": ac_capacity_kw * 1000, "eta_inv_nom": 0.96},
    )
    model = pvlib.modelchain.ModelChain.with_pvwatts(system, location)
    model.run_model(weather[["ghi", "dni", "dhi", "temp_air", "wind_speed"]])
    ac_result = model.results.ac
    if isinstance(ac_result, tuple):
        ac_result = ac_result[0]
    ac_kw = np.nan_to_num(np.maximum(np.asarray(ac_result, dtype=float) / 1000, 0), nan=0.0)
    ac_kw = np.minimum(ac_kw, ac_capacity_kw)
    return [
        QuantileForecastPoint(
            valid_at=valid_at.to_pydatetime(),
            p10=float(value * 0.82),
            p50=float(value),
            p90=float(min(value * 1.12, ac_capacity_kw)),
        )
        for valid_at, value in zip(weather.index, ac_kw, strict=True)
    ]


def propagate_soc_quantiles(
    *,
    index: Sequence[datetime],
    initial_soc_pct: float,
    minimum_soc_pct: float,
    maximum_soc_pct: float,
) -> list[QuantileForecastPoint]:
    """Create an unconstrained SOC envelope for pre-optimization visualization."""
    return [
        QuantileForecastPoint(
            valid_at=valid_at,
            p10=max(minimum_soc_pct, initial_soc_pct - 5),
            p50=min(maximum_soc_pct, max(minimum_soc_pct, initial_soc_pct)),
            p90=min(maximum_soc_pct, initial_soc_pct + 5),
        )
        for valid_at in index
    ]
