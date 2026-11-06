# ruff: noqa: T201, PLR2004, RUF001
"""Build two reviewable pilot datasets from the restricted read-only snapshot.

Usage: python tools/datasets/build_energy_datasets.py --root outputs/<run>
Only the standard library, numpy and pandas are required. No database writes,
external load samples, synthetic observations, or imputation are used.
"""

import argparse
import gzip
import hashlib
import html
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

VERSION = "pilot-1.2.0"
SPLIT_NAMES = ("train", "validation", "test")
PROFILES = [
    {"id": "next_hour", "history": 96, "horizon": 4, "stride": 4},
    {"id": "next_day", "history": 672, "horizon": 96, "stride": 96},
    {"id": "next_day_short_history", "history": 96, "horizon": 96, "stride": 96},
]
SEMANTICS = "system_kWh_mapping_pending_field_CT_PT_and_register_resolution_check"
PURPOSE_LABELS = {
    "charging_facilities": "充电设施",
    "lifting_equipment_group": "行吊设备组",
    "stacking_equipment_group": "堆垛设备组",
    "agv_circuit": "AGV回路",
    "lighting_circuit": "照明回路",
    "office_circuit": "办公回路",
    "forklift_circuit": "叉车回路",
    "equipment_or_area_circuit": "设备或区域回路",
    "storage_direction_pending": "储能回路（方向待核实）",
    "photovoltaic_direction_pending": "光伏回路（方向待核实）",
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(
        path,
        index=False,
        encoding="utf-8",
        float_format="%.6f",
        compression={"method": "gzip", "mtime": 0} if str(path).endswith(".gz") else None,
    )


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def purpose(name: str) -> str:
    rules = [
        (("充电",), "charging_facilities"),
        (("行吊", "航吊"), "lifting_equipment_group"),
        (("堆垛",), "stacking_equipment_group"),
        (("AGV",), "agv_circuit"),
        (("照明",), "lighting_circuit"),
        (("办公",), "office_circuit"),
        (("叉车",), "forklift_circuit"),
        (("储能",), "storage_direction_pending"),
        (("光伏",), "photovoltaic_direction_pending"),
    ]
    for tokens, purpose_name in rules:
        if any(token in name for token in tokens):
            return purpose_name
    return "equipment_or_area_circuit"


def read_snapshot(path: Path) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
    sites, records, ends = {}, [], {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec["kind"] == "snapshot":
                header = rec
            elif rec["kind"] == "site":
                sites[rec["site_id"]] = rec
            elif rec["kind"] == "fact":
                records.append([rec["site_id"]] + rec["values"])
            elif rec["kind"] == "site_end":
                ends[rec["site_id"]] = rec["rows"]
    frame = pd.DataFrame(records, columns=["site_id"] + header["fact_columns"])
    if ends != frame.site_id.value_counts().to_dict():
        raise ValueError("Incomplete source snapshot")
    frame["reading_time"] = pd.to_datetime(frame.reading_time)
    frame["received_at"] = pd.to_datetime(frame.received_at)
    frame["normalized_value"] = pd.to_numeric(frame.normalized_value, errors="coerce")
    frame["source_ref"] = [
        hashlib.sha256(f"{s}:{r}".encode()).hexdigest()[:24]
        for s, r in zip(frame.site_id, frame.source_record_id, strict=True)
    ]
    return header, sites, frame


def normalize_meter(raw: pd.DataFrame, site: str) -> tuple[pd.DataFrame, int]:
    """Preserve timestamps/values and reject conflicting same-time readings."""
    raw = raw.sort_values(["reading_time", "id"]).copy()
    raw["priority"] = raw.source_system.map(
        {
            "yunji": 4,
            "yunji_legacy": 3,
            "mqtt_szscada": 4,
            "yunji_legacy_archive": 1,
            "infrared_legacy_archive": 1,
            "legacy_meter_archive": 1,
        }
    ).fillna(0)
    conflict = raw.groupby("reading_time").normalized_value.agg(lambda s: len(s.dropna().unique()) > 1)
    raw["duplicate_conflict"] = raw.reading_time.map(conflict)
    before = len(raw)
    raw = raw.sort_values(["reading_time", "priority", "id"]).drop_duplicates("reading_time", keep="last")
    raw = raw.sort_values("reading_time").reset_index(drop=True)
    # MQTT Unix timestamps are parsed as UTC by the app contract; Yunji is naive site local time.
    local = raw.reading_time + (pd.Timedelta(hours=8) if site == "S02" else pd.Timedelta(0))
    raw["observed_at"] = local.dt.tz_localize("Asia/Shanghai")
    raw["available_at"] = raw.received_at.dt.tz_localize("UTC").dt.tz_convert("Asia/Shanghai")
    raw["availability_status"] = np.where(raw.available_at.notna(), "message_received_time", "ingestion_time_unknown")
    raw["valid_register"] = (
        (raw.quality_status == "valid") & (raw.unit == "kWh") & raw.normalized_value.notna() & ~raw.duplicate_conflict
    )
    if "source_time_field" in raw:
        raw["valid_register"] &= raw.source_time_field.isin(["reading_time", "legacy_period_end"])
    raw["cumulative_energy_kwh"] = raw.normalized_value
    return raw, before - len(raw)


def make_native(registers: pd.DataFrame, native_seconds: int) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "interval_start": registers.observed_at.shift(),
            "interval_end": registers.observed_at,
            "start_source_ref": registers.source_ref.shift(),
            "end_source_ref": registers.source_ref,
            "available_at": registers.available_at,
            "availability_status": registers.availability_status,
        }
    )
    duration = (out.interval_end - out.interval_start).dt.total_seconds()
    delta = registers.cumulative_energy_kwh.diff().round(6)
    endpoint_valid = registers.valid_register & registers.valid_register.shift(fill_value=False)
    tolerance = 60 if native_seconds == 900 else 1
    temporal = duration.between(native_seconds - tolerance, native_seconds + tolerance)
    usable = endpoint_valid & temporal & (delta >= 0)
    quality = np.select(
        [out.interval_start.isna(), ~endpoint_valid, delta < 0, ~temporal, duration != native_seconds],
        [
            "first_reading_no_interval",
            "invalid_endpoint_or_conflict",
            "register_decrease_review",
            "data_gap_or_cadence_change",
            "measured_irregular_duration",
        ],
        default="measured",
    )
    out["duration_seconds"] = duration
    out["electricity_kwh"] = delta.where(usable)
    out["average_power_kw"] = (delta * 3600 / duration).where(usable)
    out["quality_flag"] = quality
    out["is_valid_interval"] = usable
    out["segment_id"] = (~usable).cumsum()
    return out


def make_forecast_series(registers: pd.DataFrame, native: pd.DataFrame, site: str) -> pd.DataFrame:
    if site == "S01":
        r = registers.copy()
        r["grid_time"] = r.observed_at.dt.round("15min")
        r["time_offset_seconds"] = (r.grid_time - r.observed_at).dt.total_seconds()
        aligned = r.time_offset_seconds.abs() <= 60
        no_duplicate_grid = ~r.grid_time.duplicated(keep=False)
        nominal_seconds = r.grid_time.diff().dt.total_seconds()
        delta = r.cumulative_energy_kwh.diff().round(6)
        valid = (
            aligned
            & aligned.shift(fill_value=False)
            & no_duplicate_grid
            & no_duplicate_grid.shift(fill_value=False)
            & r.valid_register
            & r.valid_register.shift(fill_value=False)
            & (nominal_seconds == 900)
            & (delta >= 0)
        )
        corrected = (r.time_offset_seconds != 0) | (r.time_offset_seconds.shift() != 0)
        out = pd.DataFrame(
            {
                "interval_start": r.grid_time.shift(),
                "interval_end": r.grid_time,
                "electricity_kwh": delta.where(valid),
                "average_power_kw": (delta * 4).where(valid),
                "quality_flag": np.where(corrected, "day_boundary_time_alignment_assumption", "measured"),
                "primary_evaluation_eligible": valid & ~corrected,
                "available_at": r.available_at,
                "availability_status": r.availability_status,
                "start_source_ref": r.source_ref.shift(),
                "end_source_ref": r.source_ref,
            }
        )
        out = out[valid].reset_index(drop=True)
    else:
        rows = []
        # No snapping or interpolating MQTT readings: aggregate only exact consecutive 300 s intervals.
        strict = native.is_valid_interval & (native.duration_seconds == 300)
        segments = (~strict).cumsum()
        for _, chunk in native[strict].groupby(segments[strict]):
            for j in range(0, len(chunk) - 2, 3):
                block = chunk.iloc[j : j + 3]
                if (block.interval_end.iloc[-1] - block.interval_start.iloc[0]).total_seconds() != 900:
                    continue
                energy = float(block.electricity_kwh.sum())
                rows.append(
                    {
                        "interval_start": block.interval_start.iloc[0],
                        "interval_end": block.interval_end.iloc[-1],
                        "electricity_kwh": energy,
                        "average_power_kw": energy * 4,
                        "quality_flag": "measured_3x5min_aggregate",
                        "primary_evaluation_eligible": True,
                        "available_at": block.available_at.max(),
                        "availability_status": "message_received_time",
                        "start_source_ref": block.start_source_ref.iloc[0],
                        "end_source_ref": block.end_source_ref.iloc[-1],
                    }
                )
        out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = out.sort_values("interval_start").reset_index(drop=True)
    out["segment_id"] = (out.interval_start != out.interval_end.shift()).cumsum()
    return out


def get_split(start: pd.Timestamp, end: pd.Timestamp, cuts: list[pd.Timestamp]) -> str | None:
    # Target intervals, not complete history+target windows, determine split membership.
    if end <= cuts[0]:
        return "train"
    if start >= cuts[0] and end <= cuts[1]:
        return "validation"
    if start >= cuts[1]:
        return "test"
    return None


def calibrate_events(
    native: pd.DataFrame, train_end: pd.Timestamp, native_seconds: int
) -> tuple[pd.Series, pd.Series, dict[str, Any]]:
    n = max(1, int(np.ceil(1800 / native_seconds)))
    smoothing_hours = n * native_seconds / 3600
    smoothed = pd.Series(np.nan, index=native.index)
    for _, block in native[native.is_valid_interval].groupby("segment_id"):
        values = (
            block.electricity_kwh.rolling(n, min_periods=n).sum()
            * 3600
            / block.duration_seconds.rolling(n, min_periods=n).sum()
        )
        smoothed.loc[block.index] = values
    training = smoothed[(native.interval_end <= train_end) & smoothed.notna()]
    increments = native.loc[(native.interval_end <= train_end) & (native.electricity_kwh > 0), "electricity_kwh"]
    # These are pilot enterprise assumptions, not equipment-rated-power or national-standard thresholds.
    quantum = float(increments.min()) if len(increments) else None
    if not len(training) or quantum is None:
        low, high = None, None
    else:
        background = float(training.median())
        # A complete observed increment over the smoothing window is the noise margin.
        # A smaller fraction produced false activity on quasi-periodic rounded registers.
        margin = max(1e-6, quantum / smoothing_hours)
        low = max(float(training.quantile(0.9)), background + margin)
        high = max(float(training.quantile(0.99)), low + margin)
    dynamic_range = float(training.quantile(0.99) - training.median()) if len(training) else 0
    quantization_ratio = quantum / (dynamic_range * smoothing_hours) if quantum and dynamic_range > 0 else None
    timing_usable = quantum is not None and quantization_ratio is not None and quantization_ratio < 0.5
    rules = {
        "rule_version": VERSION,
        "source_name": "pilot_enterprise_assumptions_train_only",
        "standard_code": None,
        "confidence_level": "uncalibrated_rule_candidate",
        "training_end_exclusive": str(train_end),
        "calibration_observations": len(training),
        "smoothing_window_minutes": smoothing_hours * 60,
        "minimum_activity_duration_minutes": 30,
        "extended_activity_review_minutes": 120,
        "observed_min_positive_increment_kwh": quantum,
        "increment_is_verified_register_resolution": False,
        "active_threshold_kw": low,
        "high_threshold_kw": high,
        "observed_increment_to_30min_dynamic_energy_ratio": quantization_ratio,
        "activity_timing_usable_under_pilot_rule": timing_usable,
        "quantization_screen_source": "enterprise assumption: suppress event timing if increment / ((training p99 - median smoothed power)*smoothing_hours) >= 0.5, or dynamic range is absent",
        "threshold_derivation": "active=max(training p90, median+increment/smoothing_hours); high=max(training p99, active+increment/smoothing_hours)",
        "interpretation": "above local background; not verified equipment running or charging duration",
    }
    states = pd.Series("unknown", index=native.index)
    if low is not None and timing_usable:
        states.loc[smoothed.notna()] = "low_load"
        states.loc[smoothed > low + 1e-6] = "active_load"
        states.loc[smoothed >= high + 1e-6] = "high_load"
    return smoothed, states, rules


def find_events(
    native: pd.DataFrame,
    smooth: pd.Series,
    states: pd.Series,
    rules: dict[str, Any],
    meter_id: str,
    meter_purpose: str,
    cuts: list[pd.Timestamp],
) -> list[dict[str, Any]]:
    if rules["active_threshold_kw"] is None or not rules["activity_timing_usable_under_pilot_rule"]:
        return []
    active = states.isin(["active_load", "high_load"])
    groups = ((active != active.shift()) | (native.segment_id != native.segment_id.shift())).cumsum()
    events = []
    for _, block in native[active].groupby(groups[active]):
        start, end = block.interval_start.iloc[0], block.interval_end.iloc[-1]
        minutes = (end - start).total_seconds() / 60
        if minutes < 30:
            continue
        split = get_split(start, end, cuts)
        if split is None:
            continue
        flags = ["activity_above_background"]
        if meter_purpose == "charging_facilities":
            flags.append("charging_activity_candidate")
        high_duration = block.loc[states.loc[block.index] == "high_load", "duration_seconds"].sum() / 60
        if high_duration >= 30:
            flags.append("high_load_within_activity")
        if minutes >= 120:
            flags.append("extended_activity_review")
        energy = float(block.electricity_kwh.sum())
        events.append(
            {
                "event_id": f"{meter_id}_E{len(events) + 1:05d}",
                "meter_id": meter_id,
                "interval_start": str(start),
                "interval_end_exclusive": str(end),
                "duration_minutes": minutes,
                "event_type": "charging_activity_candidate"
                if meter_purpose == "charging_facilities"
                else "activity_above_background",
                "candidate_tags": flags,
                "electricity_kwh": energy,
                "average_power_kw": energy * 60 / minutes,
                "max_interval_average_power_kw": float(block.average_power_kw.max()),
                "max_smoothed_30min_power_kw": float(smooth.loc[block.index].max()),
                "boundary_resolution_seconds": 300 if meter_id.startswith("S02") else 900,
                "boundary_semantics": "threshold crossing in trailing-30min curve; not physical work/charging start or end",
                "start_source_ref": block.start_source_ref.iloc[0],
                "end_source_ref": block.end_source_ref.iloc[-1],
                "label_source": "meter_purpose_inventory_and_train_calibrated_curve_rule",
                "verification_level": "rule_candidate",
                "split": split,
                "rule_version": VERSION,
            }
        )
    return events


def choose_spread(items: list[Any], limit: int) -> list[Any]:
    if len(items) <= limit:
        return items
    return [items[i] for i in np.linspace(0, len(items) - 1, limit).round().astype(int)]


def make_forecast_cases(
    series: pd.DataFrame,
    meter_meta: dict[str, Any],
    cuts: list[pd.Timestamp],
    package: Path,
    max_cases: int,
    baseline_rows: list[dict[str, Any]],
    eligibility: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    index = []
    if series.empty:
        return index
    train_values = series.loc[series.interval_end <= cuts[0], "average_power_kw"]
    information_ok = len(train_values) >= 96 and train_values.std() > 1e-9 and (train_values > 0).mean() >= 0.005
    observation_lag = 1 if meter_meta["site_id"] == "S02" else 0
    for profile in PROFILES:
        options = {s: [] for s in SPLIT_NAMES}
        if information_ok:
            for segment_id, chunk in series.groupby("segment_id"):
                chunk = chunk.reset_index(drop=True)
                for j in range(
                    profile["history"] + observation_lag, len(chunk) - profile["horizon"] + 1, profile["stride"]
                ):
                    history = chunk.iloc[
                        j - observation_lag - profile["history"] : j - observation_lag if observation_lag else j
                    ]
                    future = chunk.iloc[j : j + profile["horizon"]]
                    origin = future.interval_start.iloc[0]
                    split = get_split(origin, future.interval_end.iloc[-1], cuts)
                    known_history = history.available_at.dropna()
                    if split and (known_history <= origin).all():
                        options[split].append((segment_id, history, future))
        for split in SPLIT_NAMES:
            candidates = options[split]
            selected = choose_spread(candidates, max_cases)
            eligibility.append(
                {
                    "meter_id": meter_meta["meter_id"],
                    "profile": profile["id"],
                    "split": split,
                    "eligible_nonoverlapping_target_windows": len(candidates),
                    "exported_windows": len(selected),
                    "status": "usable"
                    if candidates
                    else (
                        "low_training_information"
                        if not information_ok
                        else "insufficient_contiguous_valid_history_and_future"
                    ),
                }
            )
            for number, (_segment_id, history, future) in enumerate(selected, 1):
                sequence = f"{meter_meta['meter_id']}_{profile['id']}_{split}_{number:03d}"
                input_dir = package / "task2_forecast" / "inputs" / split / sequence
                target_dir = package / "task2_forecast" / "evaluator_only" / split / sequence
                origin = future.interval_start.iloc[0]
                columns = ["interval_start", "interval_end", "average_power_kw", "quality_flag", "availability_status"]
                hist = history[columns].copy().reset_index(drop=True)
                hist.insert(0, "step", range(len(hist)))
                write_csv(input_dir / "history.csv", hist)
                covariates = future[["interval_start", "interval_end"]].copy().reset_index(drop=True)
                covariates.insert(0, "step", range(len(covariates)))
                covariates["hour"] = covariates.interval_start.dt.hour
                covariates["minute"] = covariates.interval_start.dt.minute
                covariates["weekday"] = covariates.interval_start.dt.dayofweek
                write_csv(input_dir / "future_covariates.csv", covariates)
                # Planned exact 15min timestamps only; no future receipt times or observed load summaries in input.
                meta = {
                    **meter_meta,
                    "sequence_id": sequence,
                    "parent_series_id": meter_meta["meter_id"],
                    "prediction_origin": str(origin),
                    "sampling_interval_seconds": 900,
                    "history_length": profile["history"],
                    "forecast_horizon": profile["horizon"],
                    "observation_lag_steps": observation_lag,
                    "history_end_to_prediction_origin_seconds": observation_lag * 900,
                    "target_columns": ["average_power_kw"],
                    "profile": profile["id"],
                    "split": split,
                    "source_record_refs": {
                        "history_start": history.start_source_ref.iloc[0],
                        "history_end": history.end_source_ref.iloc[-1],
                    },
                    "processing_version": VERSION,
                    "asof_validation": "MQTT receipt times checked; Yunji ingestion time unavailable, retrospective measurement-time backtest",
                }
                write_json(input_dir / "metadata.json", meta)
                target = (
                    future[
                        [
                            "interval_start",
                            "interval_end",
                            "average_power_kw",
                            "electricity_kwh",
                            "quality_flag",
                            "primary_evaluation_eligible",
                            "start_source_ref",
                            "end_source_ref",
                        ]
                    ]
                    .copy()
                    .reset_index(drop=True)
                )
                target.insert(0, "step", range(len(target)))
                write_csv(target_dir / "future.csv", target)
                write_json(
                    target_dir / "ground_truth.json",
                    {
                        "sequence_id": sequence,
                        "canonical_target_file": "future.csv",
                        "sha256": sha(target_dir / "future.csv"),
                        "verification_level": SEMANTICS,
                        "primary_mask_column": "primary_evaluation_eligible",
                        "values_are_not_duplicated_in_json": True,
                    },
                )
                historical_by_start = dict(zip(history.interval_start, history.average_power_kw, strict=True))
                forecasts = {
                    "last_observed_value": np.repeat(history.average_power_kw.iloc[-1], len(future)),
                    "previous_day": np.array(
                        [historical_by_start.get(t - pd.Timedelta(days=1), np.nan) for t in future.interval_start]
                    ),
                }
                if len(history) >= 672:
                    forecasts["previous_week"] = np.array(
                        [historical_by_start.get(t - pd.Timedelta(days=7), np.nan) for t in future.interval_start]
                    )
                actual = future.average_power_kw.to_numpy()
                mask = future.primary_evaluation_eligible.to_numpy(bool)
                predictions = target[["step", "interval_start", "interval_end"]].copy()
                for model, predicted in forecasts.items():
                    predictions[model] = predicted
                    for scope, selected_mask in [
                        ("primary_without_time_alignment_targets", mask),
                        ("all_targets_including_alignment_assumption", np.ones(len(mask), bool)),
                    ]:
                        selected_mask = selected_mask & np.isfinite(predicted)
                        if not selected_mask.any():
                            continue
                        residual = actual[selected_mask] - predicted[selected_mask]
                        baseline_rows.append(
                            {
                                "sequence_id": sequence,
                                "site_id": meter_meta["site_id"],
                                "meter_id": meter_meta["meter_id"],
                                "profile": profile["id"],
                                "split": split,
                                "model": model,
                                "scope": scope,
                                "n": int(selected_mask.sum()),
                                "sum_abs_error": float(abs(residual).sum()),
                                "sum_squared_error": float((residual**2).sum()),
                                "sum_actual": float(abs(actual[selected_mask]).sum()),
                            }
                        )
                write_csv(target_dir / "baseline_predictions.csv", predictions)
                index.append(
                    {
                        "sequence_id": sequence,
                        "site_id": meter_meta["site_id"],
                        "meter_id": meter_meta["meter_id"],
                        "profile": profile["id"],
                        "split": split,
                        "prediction_origin": str(origin),
                        "history_length": len(history),
                        "forecast_horizon": len(future),
                        "input_path": str(input_dir.relative_to(package)),
                        "target_path": str(target_dir.relative_to(package)),
                    }
                )
    return index


def make_event_cases(
    native: pd.DataFrame,
    states: pd.Series,
    smooth: pd.Series,
    events: list[dict[str, Any]],
    metadata: dict[str, Any],
    package: Path,
    cuts: list[pd.Timestamp],
) -> list[dict[str, Any]]:
    index = []
    for split in SPLIT_NAMES:
        group = [e for e in events if e["split"] == split]
        # Review pack intentionally selects representative long and high-energy candidates; not an unbiased benchmark.
        chosen = {e["event_id"]: e for e in choose_spread(group, 2)}
        if group:
            for key in ("duration_minutes", "electricity_kwh"):
                event = max(group, key=lambda e: e[key])
                chosen[event["event_id"]] = event
        for number, event in enumerate(chosen.values(), 1):
            start, end = pd.Timestamp(event["interval_start"]), pd.Timestamp(event["interval_end_exclusive"])
            window = native[
                (native.interval_end > start - pd.Timedelta(hours=2))
                & (native.interval_start < end + pd.Timedelta(hours=2))
            ].copy()
            if split == "train":
                window = window[window.interval_end <= cuts[0]]
            elif split == "validation":
                window = window[(window.interval_start >= cuts[0]) & (window.interval_end <= cuts[1])]
            else:
                window = window[window.interval_start >= cuts[1]]
            sequence = f"{metadata['meter_id']}_events_{split}_{number:03d}"
            input_dir = package / "task1_events" / "inputs" / split / sequence
            label_dir = package / "task1_events" / "evaluator_only" / split / sequence
            observed = window[
                [
                    "interval_start",
                    "interval_end",
                    "duration_seconds",
                    "electricity_kwh",
                    "average_power_kw",
                    "quality_flag",
                    "start_source_ref",
                    "end_source_ref",
                ]
            ].reset_index(drop=True)
            observed.insert(0, "step", range(len(observed)))
            write_csv(input_dir / "observations.csv", observed)
            write_json(
                input_dir / "metadata.json",
                {
                    **metadata,
                    "sequence_id": sequence,
                    "split": split,
                    "task_mode": "offline_curve_review",
                    "processing_version": VERSION,
                    "annotations_are_not_input": True,
                    "selection": "representative_review_sample_not_random_benchmark",
                },
            )
            annotation = []
            for e in events:
                if (
                    e["split"] == split
                    and pd.Timestamp(e["interval_start"]) >= window.interval_start.min()
                    and pd.Timestamp(e["interval_end_exclusive"]) <= window.interval_end.max()
                ):
                    mask = (window.interval_start >= pd.Timestamp(e["interval_start"])) & (
                        window.interval_end <= pd.Timestamp(e["interval_end_exclusive"])
                    )
                    positions = np.flatnonzero(mask.to_numpy())
                    if len(positions):
                        annotation.append(
                            {**e, "start_interval": int(positions[0]), "end_interval_exclusive": int(positions[-1] + 1)}
                        )
            write_json(
                label_dir / "annotations.json",
                {
                    "sequence_id": sequence,
                    "events": annotation,
                    "label_quality": "weak_rule_candidates_no_independent_business_truth",
                },
            )
            labels = pd.DataFrame(
                {
                    "step": range(len(window)),
                    "state": states.loc[window.index].to_numpy(),
                    "smoothed_30min_power_kw": smooth.loc[window.index].to_numpy(),
                }
            )
            write_csv(label_dir / "state_labels.csv", labels)
            index.append(
                {
                    "sequence_id": sequence,
                    "site_id": metadata["site_id"],
                    "meter_id": metadata["meter_id"],
                    "split": split,
                    "review_focus_event_id": event["event_id"],
                    "observations": len(window),
                    "input_path": str(input_dir.relative_to(package)),
                    "label_path": str(label_dir.relative_to(package)),
                }
            )
    return index


def metrics_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    keys = ["site_id", "profile", "split", "model", "scope"]
    out = frame.groupby(keys, as_index=False).agg(
        target_steps=("n", "sum"),
        sum_abs_error=("sum_abs_error", "sum"),
        sum_squared_error=("sum_squared_error", "sum"),
        sum_actual=("sum_actual", "sum"),
        sequences=("sequence_id", "count"),
    )
    out["MAE_kw"] = out.sum_abs_error / out.target_steps
    out["RMSE_kw"] = np.sqrt(out.sum_squared_error / out.target_steps)
    out["WAPE_percent"] = (out.sum_abs_error / out.sum_actual.where(out.sum_actual > 0)) * 100
    return out.drop(columns=["sum_abs_error", "sum_squared_error", "sum_actual"])


def build(root: Path, max_cases: int) -> None:
    package = root / "package"
    if package.exists():
        raise RuntimeError("Output package exists; use a new run directory to preserve previous results")
    package.mkdir(parents=True)
    (package / "README.md").write_text("构建中，请等待验证完成。\n", encoding="utf-8")
    snapshot = root / "internal" / "source_snapshot.ndjson.gz"
    header, sites, raw = read_snapshot(snapshot)
    cuts = {}
    for site, group in raw.groupby("site_id"):
        shift = pd.Timedelta(hours=8) if site == "S02" else pd.Timedelta(0)
        begin = (group.reading_time.min() + shift).tz_localize("Asia/Shanghai")
        end = pd.Timestamp(header["cutoff_local_exclusive"])
        cuts[site] = [(begin + (end - begin) * fraction).ceil("D") for fraction in (0.6, 0.8)]
    summaries, meter_metadata, forecast_index, event_index = [], [], [], []
    all_events, baselines, eligibility, charts, identity_map = [], [], [], [], []
    total_deduplicated = 0
    for (site, equipment), group in raw.groupby(["site_id", "equipment_id"], sort=True):
        equipment_meta = next(x for x in sites[site]["equipment"] if x["id"] == equipment)
        ordinal = equipment if site == "S01" else equipment - 20
        meter = f"{site}_M{ordinal:02d}"
        meter_purpose = purpose(equipment_meta["name"] or "")
        native_seconds = 900 if site == "S01" else 300
        registers, duplicates = normalize_meter(group, site)
        total_deduplicated += duplicates
        identity_map.append(
            {
                "site_id": site,
                "meter_id": meter,
                "source_equipment_id": equipment,
                "source_code": equipment_meta["code"],
                "source_name": equipment_meta["name"],
            }
        )
        meta = {
            "site_id": site,
            "meter_id": meter,
            "timezone": "Asia/Shanghai",
            "meter_purpose": meter_purpose,
            "meter_purpose_confirmation": "platform_inventory_not_independent_operation_log",
            "meter_scope": "circuit_or_equipment_group_individual_member_unverified",
            "source_type": "measured_cumulative_register_derived_intervals",
            "power_unit": "kW",
            "energy_unit": "kWh",
            "metering_semantics_status": SEMANTICS,
            "mapping_version": sorted(registers.mapping_version.unique().tolist()),
            "native_interval_seconds": native_seconds,
            "physical_rated_power_verified": False,
            "timezone_basis": "MQTT Unix timestamp UTC contract"
            if site == "S02"
            else "enterprise assumption: Yunji site-local China time",
        }
        meter_metadata.append(meta)
        published_registers = registers[
            [
                "observed_at",
                "available_at",
                "availability_status",
                "cumulative_energy_kwh",
                "quality_status",
                "source_system",
                "source_ref",
                "mapping_version",
                "duplicate_conflict",
            ]
        ].copy()
        published_registers.insert(0, "meter_id", meter)
        write_csv(package / "base" / "registers" / f"{meter}.csv.gz", published_registers)
        native = make_native(registers, native_seconds)
        native.insert(0, "meter_id", meter)
        write_csv(package / "base" / "native_intervals" / f"{meter}.csv.gz", native)
        excluded_role = meter_purpose.endswith("direction_pending")
        forecast = make_forecast_series(registers, native, site) if not excluded_role else pd.DataFrame()
        if not forecast.empty:
            forecast.insert(0, "meter_id", meter)
            write_csv(package / "base" / "forecast_15min" / f"{meter}.csv.gz", forecast)
            forecast_index.extend(
                make_forecast_cases(forecast, meta, cuts[site], package, max_cases, baselines, eligibility)
            )
        smooth, states, rules = calibrate_events(native, cuts[site][0], native_seconds)
        write_json(package / "task1_events" / "evaluator_only" / "calibration" / f"{meter}.json", rules)
        events = [] if excluded_role else find_events(native, smooth, states, rules, meter, meter_purpose, cuts[site])
        all_events.extend(events)
        event_index.extend(make_event_cases(native, states, smooth, events, meta, package, cuts[site]))
        valid = native[native.is_valid_interval]
        max_gap = float(native.duration_seconds.max())
        summary = {
            "site_id": site,
            "meter_id": meter,
            "meter_purpose": meter_purpose,
            "raw_source_records": len(group),
            "deduplicated_register_observations": len(registers),
            "duplicate_records_removed": duplicates,
            "duplicate_conflict_readings": int(registers.duplicate_conflict.sum()),
            "first_observed_at": str(registers.observed_at.min()),
            "last_observed_at": str(registers.observed_at.max()),
            "invalid_register_readings": int((~registers.valid_register).sum()),
            "valid_native_intervals": len(valid),
            "invalid_or_gap_intervals": int((~native.is_valid_interval).sum()),
            "register_decrease_intervals": int((native.quality_flag == "register_decrease_review").sum()),
            "maximum_observation_gap_hours": max_gap / 3600,
            "positive_interval_fraction": float((valid.electricity_kwh > 0).mean()) if len(valid) else None,
            "median_interval_average_power_kw": float(valid.average_power_kw.median()) if len(valid) else None,
            "p99_interval_average_power_kw": float(valid.average_power_kw.quantile(0.99)) if len(valid) else None,
            "min_positive_increment_kwh": rules["observed_min_positive_increment_kwh"],
            "activity_timing_usable_under_pilot_rule": rules["activity_timing_usable_under_pilot_rule"],
            "forecast_15min_intervals": len(forecast),
            "time_alignment_assumption_intervals": int(
                (forecast.quality_flag == "day_boundary_time_alignment_assumption").sum()
            )
            if not forecast.empty
            else 0,
            "candidate_events": len(events),
            "extended_activity_candidates": sum("extended_activity_review" in e["candidate_tags"] for e in events),
            "role_status": "excluded_storage_or_generation_direction_pending"
            if excluded_role
            else "load_circuit_pilot",
        }
        summaries.append(summary)
        # Select a long candidate and surrounding native curve for a human reviewer.
        if events:
            representative = max(events, key=lambda e: e["duration_minutes"])
            start, end = (
                pd.Timestamp(representative["interval_start"]),
                pd.Timestamp(representative["interval_end_exclusive"]),
            )
            view = native[
                (native.interval_end > start - pd.Timedelta(hours=3))
                & (native.interval_start < end + pd.Timedelta(hours=3))
            ]
            charts.append(
                {
                    "meter_id": meter,
                    "purpose": meter_purpose,
                    "event": representative,
                    "points": [
                        [
                            str(r.interval_end),
                            None if pd.isna(r.average_power_kw) else float(r.average_power_kw),
                            None if pd.isna(smooth.loc[i]) else float(smooth.loc[i]),
                        ]
                        for i, r in view.iterrows()
                    ],
                    "active_threshold_kw": rules["active_threshold_kw"],
                }
            )
        print(
            f"{meter}: {len(registers)} registers, {len(valid)} valid intervals, {len(events)} candidates", flush=True
        )
    write_csv(root / "internal" / "identity_mapping_RESTRICTED.csv", pd.DataFrame(identity_map))
    write_json(package / "base" / "meter_metadata.json", meter_metadata)
    write_csv(package / "quality" / "meter_quality_report.csv", pd.DataFrame(summaries))
    write_csv(package / "task1_events" / "sequence_index.csv", pd.DataFrame(event_index))
    # All labels and fitted rule parameters stay with the evaluator, not the recognition input bundle.
    event_frame = pd.DataFrame(all_events)
    if len(event_frame):
        event_frame["candidate_tags"] = event_frame.candidate_tags.map(lambda x: "|".join(x))
    write_csv(package / "task1_events" / "evaluator_only" / "all_candidate_events.csv", event_frame)
    review = event_frame[
        [
            "event_id",
            "meter_id",
            "interval_start",
            "interval_end_exclusive",
            "event_type",
            "duration_minutes",
            "verification_level",
        ]
    ].copy()
    for col in ("reviewed_label", "independent_evidence", "reviewer", "reviewed_at", "boundary_review", "notes"):
        review[col] = ""
    write_csv(package / "task1_events" / "review_template.csv", review)
    write_csv(package / "task2_forecast" / "sequence_index.csv", pd.DataFrame(forecast_index))
    write_csv(package / "task2_forecast" / "eligibility_report.csv", pd.DataFrame(eligibility))
    metrics = metrics_frame(baselines)
    write_csv(package / "task2_forecast" / "baseline_metrics.csv", metrics)
    write_json(
        package / "task1_events" / "task_spec.json",
        {
            "task_id": "load_state_and_sustained_energy_events",
            "version": VERSION,
            "mode": "offline_curve_review",
            "verified_operation_labels": 0,
            "rule_candidate_labels": len(all_events),
            "candidate_duration_is_not_equipment_hours": True,
            "rule_parameters_are_in_evaluator_only": True,
        },
    )
    write_json(
        package / "task2_forecast" / "task_spec.json",
        {
            "task_id": "short_term_meter_load_forecast",
            "version": VERSION,
            "profiles": PROFILES,
            "sampling_interval_seconds": 900,
            "target": "average_power_kw",
            "energy_is_derived_not_independent_target": True,
            "future_actuals_are_not_in_inputs": True,
            "history_observation_lag_steps_by_site": {"S01": 0, "S02": 1},
            "training_validation_test_target_periods_are_disjoint": True,
            "time_alignment_assumption_targets_excluded_from_primary_metrics": True,
            "metering_semantics_status": SEMANTICS,
        },
    )
    manifest = {
        "schema_version": "1.0",
        "processing_version": VERSION,
        "status": "real_data_pilot_pending_metering_and_business_validation",
        "cutoff_local_exclusive": header["cutoff_local_exclusive"],
        "created_at": header["created_at"],
        "source_environment": header["source_environment"],
        "source_snapshot_sha256": sha(snapshot),
        "source_readonly_and_tenant_scoped": True,
        "source_observations": len(raw),
        "duplicates_removed": total_deduplicated,
        "independent_register_observations": int(sum(x["deduplicated_register_observations"] for x in summaries)),
        "meters_with_observations": len(summaries),
        "sites": sorted(sites),
        "time_splits": {
            s: {"training_target_end_exclusive": str(c[0]), "validation_target_end_exclusive": str(c[1])}
            for s, c in cuts.items()
        },
        "forecast_sequences": len(forecast_index),
        "event_review_sequences": len(event_index),
        "candidate_events": len(all_events),
        "verified_business_events": 0,
        "synthetic_observations": 0,
        "imputed_intervals": 0,
        "external_sample_rows_used": 0,
        "max_exported_windows_per_meter_profile_split": max_cases,
        "sampling_policy": "deterministic evenly spaced eligible windows; complete parent series included",
        "identity_policy": "pseudonymous site and meter codes; original identity mapping retained outside package",
        "operational_asof_limit": "Yunji ingest time unknown; MQTT history ends one 15min step before origin and receipt <= origin checked",
        "share_input_only_for_hidden_test": True,
        "full_package_contains_evaluation_answers": True,
        "full_base_series_must_not_be_shared_with_hidden_test_participants": True,
        "assumption_sources": [
            "existing application point/unit mappings",
            "platform equipment purpose inventory",
            "pilot enterprise curve rules",
        ],
        "not_confirmed": [
            "现场CT/PT倍率与寄存器分辨率",
            "具体设备成员与充电订单/实际工时",
            "Yunji本地时间口径与入库可用时间",
            "工业互联网大赛正式数据评审要求",
        ],
    }
    write_json(package / "manifest.json", manifest)
    write_csv(
        package / "quality" / "data_dictionary.csv",
        pd.DataFrame(
            [
                {"field": f, "meaning": m, "unit_or_type": t}
                for f, m, t in [
                    ("observed_at", "规范累计读数的原始观测时间，统一显示为东八区", "ISO8601+08:00"),
                    ("available_at", "MQTT原始消息接收时间；Yunji未知时为空", "ISO8601+08:00 or null"),
                    ("cumulative_energy_kwh", "系统规范点位的正向累计有功电量；不再重复乘倍率", "system-mapped kWh"),
                    ("electricity_kwh", "相邻有效累计值的非负差分；缺口无效区间留空", "system-mapped kWh"),
                    ("average_power_kw", "区间电量除以区间小时数；预测表使用明确标记的15分钟区间", "system-mapped kW"),
                    ("primary_evaluation_eligible", "不依赖日末时间对齐假设的有效预测目标", "boolean"),
                    ("source_ref", "来源记录的稳定SHA256摘要，不暴露电表地址", "24 hex chars"),
                    ("quality_flag", "实测差分、时间修正、无效端点、复位或缺口状态", "enum"),
                    ("step", "当前文件内从0开始的区间序号；未来独立从0开始", "integer"),
                    ("verification_level", "首版只有rule_candidate，尚无独立业务证据", "enum"),
                ]
            ]
        ),
    )
    write_review_html(root, manifest, summaries, charts, metrics)
    write_readme_and_report(root, manifest, summaries, eligibility, metrics)
    # This archive intentionally contains answers for the owner's offline review.
    zip_path = root / "两套能耗数据集_内部评审版.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(package.rglob("*")):
            if p.is_file():
                z.write(p, str(Path("energy_dataset_pilot") / p.relative_to(package)))
    inputs_zip = root / "任务输入包_不含未来真值与事件标签.zip"
    with zipfile.ZipFile(inputs_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for task in ("task1_events", "task2_forecast"):
            for p in sorted((package / task / "inputs").rglob("*")):
                if p.is_file():
                    z.write(p, str(p.relative_to(package)))
            for name in ("task_spec.json", "sequence_index.csv"):
                p = package / task / name
                z.write(p, str(p.relative_to(package)))
    checksums = [
        {"path": str(p.relative_to(package)), "sha256": sha(p), "bytes": p.stat().st_size}
        for p in sorted(package.rglob("*"))
        if p.is_file()
    ]
    write_csv(root / "checksums.csv", pd.DataFrame(checksums))
    print(
        json.dumps(
            {
                "manifest": manifest,
                "review_zip_bytes": zip_path.stat().st_size,
                "input_zip_bytes": inputs_zip.stat().st_size,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def write_readme_and_report(
    root: Path,
    manifest: dict[str, Any],
    summaries: list[dict[str, Any]],
    eligibility: list[dict[str, Any]],
    metrics: pd.DataFrame,
) -> None:
    package = root / "package"
    forecast_counts = (
        pd.read_csv(package / "task2_forecast" / "sequence_index.csv").groupby(["site_id", "profile"]).size()
    )
    rows = []
    for site, name in [("S01", "祥泰"), ("S02", "安方")]:
        meters = [s for s in summaries if s["site_id"] == site]
        rows.append(
            f"| {name}（{site}） | {len(meters)} | {sum(m['deduplicated_register_observations'] for m in meters):,} | {sum(m['valid_native_intervals'] for m in meters):,} | {sum(m['candidate_events'] for m in meters):,} |"
        )
    count_lines = [f"| {site} | {profile} | {n} |" for (site, profile), n in forecast_counts.items()]
    issues = []
    for s in summaries:
        if s["maximum_observation_gap_hours"] > 24:
            issues.append(
                f"- `{s['meter_id']}` 最大观测缺口 {s['maximum_observation_gap_hours']:.1f} 小时，未补为实测数据。"
            )
        if s["positive_interval_fraction"] is not None and s["positive_interval_fraction"] < 0.005:
            issues.append(
                f"- `{s['meter_id']}` 正电量区间比例仅 {s['positive_interval_fraction']:.2%}，低信息序列不进入主要预测样本。"
            )
    main_test = metrics[(metrics.split == "test") & (metrics.scope == "primary_without_time_alignment_targets")]
    events = pd.read_csv(package / "task1_events" / "evaluator_only" / "all_candidate_events.csv")
    charging = events[events.event_type == "charging_activity_candidate"]
    long_charging = charging[charging.duration_minutes >= 120]
    metric_lines = [
        f"| {r.site_id} | {r.profile} | {r.model} | {r.target_steps} | {r.MAE_kw:.4f} | {r.RMSE_kw:.4f} | {r.WAPE_percent:.1f}% |"
        for r in main_test.itertuples()
    ]
    text = f"""# 两套核心能耗数据集：首版制作结果

已从两仓生产库只读制作真实数据试验版。数据截至 **2026-09-28 00:00（北京时间，不含该时刻）**。输入采用匿名现场/电表码，原始地址和身份对应表保留在内部目录。

首版可用于算法开发、曲线审核和参赛方案演示；现场计量校验、业务标签核实及大赛正式规则尚待补齐。累计值单位采用现有系统的 kWh 映射，**没有依据曲线自行添加 CT/PT 倍率**。这里的 kW/kWh 是系统口径的派生值，不能据此宣称现场额定功率、正式节能量或已验证充电工时。

## 实际产出

| 现场 | 有读数电表数 | 去重累计读数 | 有效原生区间 | 用能候选事件 |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

原始规范记录 **{manifest["source_observations"]:,}** 条，去除重复 **{manifest["duplicates_removed"]:,}** 条，独立累计观测 **{manifest["independent_register_observations"]:,}** 条。窗口数不计为新增观测。没有使用示例风光负荷、轨交合成数值、插补电量或生成式真值。

第一套提供 **{manifest["event_review_sequences"]} 个曲线审核序列**和 **{manifest["candidate_events"]:,} 个规则候选事件**，并附全部事件表、逐区间状态、每表训练期规则和人工复核表。独立业务确认标签为 **0**；没有“识别准确率”指标。

其中安方叉车充电回路（`S02_M08`）有 **{len(charging)} 个充电回路用能候选**，**{len(long_charging)} 个超过或达到2小时**。电表曲线已能筛出值得复核的连续用能时段；尚未证明这些时段是一台叉车的充电订单或设备工时。曲线评审页可直接查看实际读数。

第二套提供 **{manifest["forecast_sequences"]} 个预测序列**。三种任务分别为24小时历史预测1小时、7天历史预测1天，以及为短历史/采集中断现场补充的24小时历史预测1天，均为15分钟粒度。各任务分别评测，前两种符合原设计。

| 现场 | 任务 | 已导出序列 |
|---|---|---:|
{chr(10).join(count_lines)}

完整有效15分钟底表保留在 `base/forecast_15min`，可继续生成窗口。当前每块表、每种任务、每个分区最多导出 {manifest["max_exported_windows_per_meter_profile_split"]} 个均匀分布的样本，所有可用窗口数在 `eligibility_report.csv`，不是全量窗口导出。

## 组织方式

借鉴轨交示例的一段一目录方式，使用 `history.csv + future_covariates.csv + metadata.json`，未来负荷和事件标签放在 `evaluator_only`。同时保留连续电表底表，比只给少量窗口更便于追溯和扩展。

```text
package/
  manifest.json
  base/                     # 累计读数、原生区间、15分钟预测底表
  quality/                  # 每表质量统计、字段字典
  task1_events/
    inputs/                 # observations.csv + metadata.json
    evaluator_only/         # 事件、状态、训练期规则
    review_template.csv     # 现场核实模板
  task2_forecast/
    inputs/                 # history.csv + future_covariates.csv + metadata.json
    evaluator_only/         # future.csv + ground_truth.json + baseline_predictions.csv
    baseline_metrics.csv
    eligibility_report.csv
```

## 处理规则和可用范围

1. 使用租户会话和非特权只读角色，累计事实表强制RLS；各现场分别提取、建样、校准和切分，没有合并为同一仓库总表。
2. 只取 `forward_active_total/register_index`，不混用区间语义不清的 `legacy_quantity`。同表同时间优先规范 Yunji 来源；同值重复去重，异值冲突保留质量标记并排除相邻区间。
3. 原生区间保留实际起止时间。安方严格连续的3个5分钟有效区间才能合成15分钟；秒级漂移、无效端点、缺口和复位会断开预测序列，不均摊长缺口。
4. 祥泰23:59日末读数仅在预测底表中按“距15分钟网格不超过60秒”对齐到00:00，原始时间保留。受影响的两个相邻目标标为 `day_boundary_time_alignment_assumption`，从主评测中排除；包含这些点的辅助结果另列。
5. 先按现场时间跨度约60%/20%/20%划分目标期，再生成窗口。训练/验证/测试的未来区间互不重叠；验证/测试可以使用预测起点前已观测的历史。每表事件阈值只用训练期校准，未做跨分区数据扩增。
6. 安方时间按现有Unix时间戳UTC解析合同转换东八区；祥泰暂按企业假设解释为中国本地时间，待确认。安方为保证历史读数已到达系统，历史窗口结束在预测起点前15分钟（元数据有1步观测滞后），所有历史消息接收时间须不晚于预测起点。没有把接收延迟改成负值；祥泰缺入库时间，因此其评测是按观测时间进行的历史回测，尚未证明在线实时可用性。
7. 设备名称仅支持回路用途判断。充电回路中的持续高于背景用能可以列为充电候选，但不能推出具体车辆、订单、电池状态或实际作业时长；持续时间长也不能直接判为异常。事件边界是30分钟尾随平滑曲线越过阈值的时间，存在平滑延迟和计量量化误差。
8. 用能事件阈值、30分钟平滑、最短30分钟和120分钟复核门槛均为明确登记的**试验企业假设**，不是国标节能阈值。活动门槛不低于训练期平滑负荷p90，并增加一个观测电量步进对应的30分钟平均功率作为噪声裕度。若最小正步进达到训练期动态电量范围的50%，或无动态范围，则不生成作业时间候选，状态保留unknown；这个筛选也是试验假设。最小正差分尚不是现场验证的寄存器分辨率。
9. 光伏和储能方向待明确，不纳入用电负荷任务；有真实历史但无足够正电量变化的表保留底表与质量报告，不用全零预测制造低误差结果。

## 基线回测

以下为所导出测试窗口的简单基线。MAE/RMSE单位采用系统kW映射；WAPE在实际负荷接近零时会很大，不能作为单一准确性结论。不同任务窗口会复用观测，结果分任务/现场统计。主指标排除了时间修正目标，并没有排除真实负荷尖峰；全目标结果可查CSV。前一天/前一周基线按时间精确匹配已有历史，不存在的时段保留空预测并不计该基线指标（安方一天预测中可能缺末尾1点）；没有用测试真值补齐。

| 现场 | 任务 | 基线 | 有效目标点 | MAE | RMSE | WAPE |
|---|---|---|---:|---:|---:|---:|
{chr(10).join(metric_lines)}

## 需要处理的真实问题

{chr(10).join(issues)}

安方没有可生成“连续7天有效历史+连续1天有效未来”的窗口，7天历史任务未硬凑。已补充24小时历史预测1天的任务；各表具体可用性以 `eligibility_report.csv` 为准。祥泰本次规范累计表没有覆盖外部充电桩15/16号表；内部充电回路18号表在本次导出期无正电量变化，不能生成有信息量的充电事件。

## 下一步

- 优先核实两仓电表正向累计点的单位、CT/PT是否已折算、寄存器最小步进、日末时间语义和近期换表记录；直接复用 `meter_metadata.json` 补齐验证状态。
- 从安方充电回路候选和行吊/堆垛候选各抽取若干段，用现场记录或操作人员确认，填写 `review_template.csv`。候选曲线审核与独立业务确认分开记录。
- 核实大赛是否要求真实自有结构化数据、授权证明、指定格式和最低规模，再决定正式提交内容；本次真实结构化规模按字节登记，不为5GB填报值扩充合成数据。

## 交付文件

`两套能耗数据集_内部评审版.zip` 包含完整底表、输入、未来真值和事件候选，供数据拥有者审核。**它包含评测答案**，不能直接发给隐藏测试参赛模型。`任务输入包_不含未来真值与事件标签.zip` 仅含任务输入和目录。完整底表也包含测试期真实负荷，隐藏测试时只能由评测方持有。

`internal` 中的只读快照、原始身份映射不在任何数据包中。现场/表码是化名处理，并不保证曲线不可重新识别；正式向外提供前仍需按客户授权选择可分享范围。
"""
    (root / "制作结果与使用说明.md").write_text(text, encoding="utf-8")
    (package / "README.md").write_text(text, encoding="utf-8")


def write_review_html(
    root: Path,
    manifest: dict[str, Any],
    summaries: list[dict[str, Any]],
    charts: list[dict[str, Any]],
    metrics: pd.DataFrame,
) -> None:
    def safe_data(obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False, default=str).replace("</", "<\\/")

    table_rows = "".join(
        f"<tr><td>{s['meter_id']}</td><td>{html.escape(s['meter_purpose'])}</td><td>{s['deduplicated_register_observations']:,}</td><td>{s['valid_native_intervals']:,}</td><td>{s['invalid_register_readings']:,}</td><td>{s['candidate_events']}</td><td>{s['extended_activity_candidates']}</td></tr>"
        for s in summaries
    )
    doc = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>能耗数据集首版评审</title>
<style>body{font:15px system-ui,-apple-system,'PingFang SC',sans-serif;background:#f1f4f6;color:#263943;margin:32px auto;max-width:1250px;padding:0 24px}h1{font-size:25px}h2{font-size:19px;margin-top:32px}.strip{display:flex;gap:35px;background:white;border-top:3px solid #387d83;padding:20px}b{font-size:25px;display:block;font-variant-numeric:tabular-nums}p{line-height:1.7}.panel{background:white;padding:20px;margin:18px 0}table{width:100%;border-collapse:collapse;font-size:13px;background:white}td,th{text-align:left;padding:9px;border-bottom:1px solid #d8e0e5;font-variant-numeric:tabular-nums}select{font:inherit;padding:8px;max-width:95%}svg{width:100%;height:370px}a{color:#226975}.note{border-left:3px solid #b8924b;padding-left:16px}small{color:#607580}</style>
<h1>两仓能耗数据集 · 首版真实数据评审</h1><p>S01＝祥泰，S02＝安方；数据截至2026-09-28 00:00（北京时间）。单位沿用系统kWh映射，现场倍率与计量分辨率待核实。</p>
<div class="strip"><div><b>REGISTERS</b>独立累计读数</div><div><b>FORECASTS</b>预测序列</div><div><b>EVENTS</b>用能候选</div><div><b>0</b>独立确认业务标签</div></div>
<p class="note">曲线中的候选时段可用于定位需要核实的充电或作业活动。候选持续时间不是设备工时，长时间用能也不是已验证故障。</p>
<h2>查看真实曲线与候选时段</h2><div class="panel"><select id="meter"></select><p id="detail"></p><svg id="curve" viewBox="0 0 1150 370"></svg><small>深蓝：原生区间平均功率；青色：30分钟尾随平滑；浅色区域：选中的规则候选；虚线：训练期背景活动门槛。空值断线。</small></div>
<h2>电表质量与事件覆盖</h2><table><thead><tr><th>电表</th><th>回路用途</th><th>累计读数</th><th>有效区间</th><th>无效读数</th><th>候选数</th><th>长时复核数</th></tr></thead><tbody>TABLE_ROWS</tbody></table>
<p><a href="制作结果与使用说明.md">制作结果与使用说明</a> · <a href="package/task2_forecast/baseline_metrics.csv">预测基线结果CSV</a> · <a href="package/task1_events/review_template.csv">人工复核模板CSV</a></p>
<script>const curves=CURVE_DATA;const sel=document.querySelector('#meter');const labels={charging_facilities:'充电设施',lifting_equipment_group:'行吊设备组',stacking_equipment_group:'堆垛设备组',agv_circuit:'AGV回路',lighting_circuit:'照明回路',office_circuit:'办公回路',forklift_circuit:'叉车回路',equipment_or_area_circuit:'设备或区域回路'};
for(let i=0;i<curves.length;i++){const o=document.createElement('option');o.value=i;o.textContent=curves[i].meter_id+' · '+(labels[curves[i].purpose]||curves[i].purpose);sel.append(o)}
const svg=document.querySelector('#curve');function node(tag,attrs,text){const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs))el.setAttribute(k,v);if(text!==undefined)el.textContent=text;svg.append(el);return el}
function draw(){svg.replaceChildren();const c=curves[Number(sel.value)],p=c.points,t=p.map(r=>Date.parse(r[0])),xmin=t[0],xmax=t.at(-1);const ymax=Math.max(...p.flatMap(r=>r.slice(1).filter(v=>v!==null)),c.active_threshold_kw)*1.1||1;const x=v=>65+(v-xmin)/(xmax-xmin||1)*1060,y=v=>300-v/ymax*260;node('rect',{x:x(Date.parse(c.event.interval_start)),y:35,width:x(Date.parse(c.event.interval_end_exclusive))-x(Date.parse(c.event.interval_start)),height:265,fill:'#e6efee'});for(let i=0;i<=4;i++){const yy=y(ymax*i/4);node('line',{x1:65,x2:1125,y1:yy,y2:yy,stroke:'#dbe3e8'});node('text',{x:58,y:yy+4,'text-anchor':'end',fill:'#566e7c','font-size':12},(ymax*i/4).toFixed(2))}node('text',{x:20,y:20,fill:'#566e7c','font-size':12},'系统口径 kW');node('line',{x1:65,x2:1125,y1:y(c.active_threshold_kw),y2:y(c.active_threshold_kw),stroke:'#9a7d45','stroke-dasharray':'5 4'});
for(const[k,color]of[[1,'#365e77'],[2,'#388d88']]){let d='',pen=false;for(let i=0;i<p.length;i++){const v=p[i][k];if(v===null){pen=false;continue}d+=(pen?' L':' M')+x(t[i])+','+y(v);pen=true}node('path',{d,fill:'none',stroke:color,'stroke-width':k===1?1.2:2})}
for(let i=0;i<=4;i++){const tt=xmin+(xmax-xmin)*i/4;node('text',{x:x(tt),y:325,'text-anchor':'middle',fill:'#566e7c','font-size':12},new Date(tt).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}))}
document.querySelector('#detail').textContent=c.event.event_type+' · '+c.event.interval_start+' 至 '+c.event.interval_end_exclusive+' · 候选跨度 '+c.event.duration_minutes.toFixed(0)+' 分钟 · 规则候选，待独立核实';}sel.onchange=draw;if(curves.length){sel.value=Math.max(0,curves.findIndex(c=>c.meter_id==='S02_M08'));draw()}
</script></html>"""
    doc = (
        doc.replace("REGISTERS", f"{manifest['independent_register_observations']:,}")
        .replace("FORECASTS", str(manifest["forecast_sequences"]))
        .replace("EVENTS", f"{manifest['candidate_events']:,}")
    )
    doc = doc.replace("TABLE_ROWS", table_rows).replace("CURVE_DATA", safe_data(charts))
    for key, label in PURPOSE_LABELS.items():
        doc = doc.replace(f"<td>{key}</td>", f"<td>{label}</td>")
    doc = doc.replace(
        "c.event.event_type+' · '",
        "({charging_activity_candidate:'充电回路用能候选',activity_above_background:'高于背景的持续用能'}[c.event.event_type]||c.event.event_type)+' · '",
    )
    (root / "数据集评审.html").write_text(doc, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--max-cases", type=int, default=12)
    args = parser.parse_args()
    build(args.root.resolve(), args.max_cases)
