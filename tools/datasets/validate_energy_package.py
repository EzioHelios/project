# ruff: noqa: T201, PLR2004
"""Check built artifacts, target separation, temporal leakage and source masking."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


def parse_times(frame: pd.DataFrame) -> pd.DataFrame:
    for column in ("interval_start", "interval_end", "available_at"):
        if column in frame:
            frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame


def validate(root: Path) -> None:
    package = root / "package"
    manifest = json.loads((package / "manifest.json").read_text())
    checks = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    forecast_index = pd.read_csv(package / "task2_forecast" / "sequence_index.csv")
    event_index = pd.read_csv(package / "task1_events" / "sequence_index.csv")
    all_targets, input_files = [], 0
    for row in forecast_index.itertuples():
        input_dir, target_dir = package / row.input_path, package / row.target_path
        history = parse_times(pd.read_csv(input_dir / "history.csv"))
        covariates = parse_times(pd.read_csv(input_dir / "future_covariates.csv"))
        future = parse_times(pd.read_csv(target_dir / "future.csv"))
        metadata = json.loads((input_dir / "metadata.json").read_text())
        origin = pd.to_datetime(metadata["prediction_origin"], utc=True)
        check(len(history) == row.history_length and len(future) == row.forecast_horizon, f"length: {row.sequence_id}")
        check((history.interval_end <= origin).all(), f"future in history: {row.sequence_id}")
        lag = metadata["history_end_to_prediction_origin_seconds"]
        check(
            history.interval_end.iloc[-1] + pd.Timedelta(seconds=lag) == origin == future.interval_start.iloc[0],
            f"origin and observation lag: {row.sequence_id}",
        )
        for frame in (history, future, covariates):
            check(
                ((frame.interval_end - frame.interval_start).dt.total_seconds() == 900).all(),
                f"15min cadence: {row.sequence_id}",
            )
            check(
                (frame.interval_start.iloc[1:].to_numpy() == frame.interval_end.iloc[:-1].to_numpy()).all(),
                f"continuity: {row.sequence_id}",
            )
            check(frame.step.tolist() == list(range(len(frame))), f"zero-based steps: {row.sequence_id}")
        check(
            covariates.interval_start.equals(future.interval_start)
            and covariates.interval_end.equals(future.interval_end),
            f"scheduled covariates: {row.sequence_id}",
        )
        check(
            set(covariates.columns) == {"step", "interval_start", "interval_end", "hour", "minute", "weekday"},
            f"covariate load leakage: {row.sequence_id}",
        )
        check(
            not any(
                k in metadata
                for k in (
                    "future_condition_label",
                    "future_anomaly_intervals",
                    "future_observed_load_summary",
                    "future_source_refs",
                )
            ),
            f"metadata leakage: {row.sequence_id}",
        )
        check(
            np.allclose(future.average_power_kw, future.electricity_kwh * 4, atol=1e-5),
            f"energy-power consistency: {row.sequence_id}",
        )
        primary = future.primary_evaluation_eligible
        check(
            not (primary & (future.quality_flag == "day_boundary_time_alignment_assumption")).any(),
            f"alignment target in primary: {row.sequence_id}",
        )
        gt = json.loads((target_dir / "ground_truth.json").read_text())
        check(
            gt["sha256"] == hashlib.sha256((target_dir / "future.csv").read_bytes()).hexdigest(),
            f"GT hash: {row.sequence_id}",
        )
        cuts = manifest["time_splits"][row.site_id]
        c1, c2 = (
            pd.to_datetime(cuts[k], utc=True)
            for k in ("training_target_end_exclusive", "validation_target_end_exclusive")
        )
        start, end = future.interval_start.iloc[0], future.interval_end.iloc[-1]
        valid_split = (
            end <= c1
            if row.split == "train"
            else (start >= c1 and end <= c2 if row.split == "validation" else start >= c2)
        )
        check(valid_split, f"cross-split target: {row.sequence_id}")
        all_targets.append((row.meter_id, row.profile, start, end, row.split))
        if row.site_id == "S02":
            series = parse_times(pd.read_csv(package / "base" / "forecast_15min" / f"{row.meter_id}.csv.gz"))
            actual_history = series[
                (series.interval_start >= history.interval_start.iloc[0])
                & (series.interval_end <= history.interval_end.iloc[-1])
            ]
            check(
                len(actual_history) == len(history) and (actual_history.available_at <= origin).all(),
                f"availability-time leakage: {row.sequence_id}",
            )
        input_files += len(list(input_dir.iterdir()))
    periods = pd.DataFrame(all_targets, columns=["meter_id", "profile", "start", "end", "split"])
    for _, group in periods.groupby(["meter_id", "profile"]):
        group = group.sort_values("start")
        check(
            (group.start.iloc[1:].to_numpy() >= group.end.iloc[:-1].to_numpy()).all(),
            "overlapping target windows within profile",
        )
    checks.append(
        f"{len(forecast_index)} forecast sequences: exact cadence, disjoint targets, no future input, hashes and known receipt times checked"
    )
    for row in event_index.itertuples():
        input_dir, label_dir = package / row.input_path, package / row.label_path
        observations = parse_times(pd.read_csv(input_dir / "observations.csv"))
        labels = json.loads((label_dir / "annotations.json").read_text())
        check(
            {p.name for p in input_dir.iterdir()} == {"observations.csv", "metadata.json"},
            f"event labels in input: {row.sequence_id}",
        )
        check(
            not any(c in observations for c in ("state", "event_type", "smoothed_30min_power_kw")),
            f"event answer leakage: {row.sequence_id}",
        )
        for event in labels["events"]:
            check(event["split"] == row.split, f"event split leakage: {row.sequence_id}")
            start, end = event["start_interval"], event["end_interval_exclusive"]
            check(0 <= start < end <= len(observations), f"annotation step boundaries: {row.sequence_id}")
            check(
                observations.interval_start.iloc[start] == pd.to_datetime(event["interval_start"], utc=True),
                f"event start: {row.sequence_id}",
            )
            check(
                observations.interval_end.iloc[end - 1] == pd.to_datetime(event["interval_end_exclusive"], utc=True),
                f"event end: {row.sequence_id}",
            )
            check(event["verification_level"] == "rule_candidate", "unsupported verified event")
        input_files += len(list(input_dir.iterdir()))
    checks.append(
        f"{len(event_index)} event review sequences: labels separated, zero-based half-open boundaries, weak label status checked"
    )
    base_observations = 0
    for path in (package / "base" / "native_intervals").glob("*.csv.gz"):
        native = pd.read_csv(path)
        invalid = ~native.is_valid_interval
        check(
            native.loc[invalid, ["electricity_kwh", "average_power_kw"]].isna().all().all(),
            f"invalid values replaced with energy: {path.name}",
        )
        base_observations += len(native)
    check(base_observations == manifest["independent_register_observations"], "observation count mismatch")
    checks.append(
        "Invalid endpoint, reset and gap intervals retain null energy/power; independent observation counts match"
    )
    events = pd.read_csv(package / "task1_events" / "evaluator_only" / "all_candidate_events.csv")
    for path in (package / "task1_events" / "evaluator_only" / "calibration").glob("*.json"):
        rule = json.loads(path.read_text())
        if not rule["activity_timing_usable_under_pilot_rule"]:
            check(not (events.meter_id == path.stem).any(), f"coarse-resolution event timing: {path.stem}")
    checks.append("Coarse/no-dynamic-range meters have no operation timing candidates")
    with zipfile.ZipFile(root / "任务输入包_不含未来真值与事件标签.zip") as z:
        paths = z.namelist()
        check(
            not any(
                "evaluator_only" in p or "/base/" in p or "future.csv" in p or "annotations.json" in p for p in paths
            ),
            "answers or test base data in input archive",
        )
        check(sum("/inputs/" in p for p in paths) == input_files, "input archive missing files")
        check(z.testzip() is None, "input archive corruption")
    with zipfile.ZipFile(root / "两套能耗数据集_内部评审版.zip") as z:
        check(
            not any("internal/" in p or "identity_mapping" in p or "source_snapshot" in p for p in z.namelist()),
            "restricted raw source in archive",
        )
        check(z.testzip() is None, "review archive corruption")
    checks.append(
        "Two zip archives readable; restricted identity map/raw source absent; input-only archive excludes answers"
    )
    report = {
        "status": "passed",
        "processing_version": manifest["processing_version"],
        "checks": checks,
        "forecast_sequences": len(forecast_index),
        "event_sequences": len(event_index),
        "independently_confirmed_business_events": 0,
        "limits": [
            "No CT/PT or field unit certification performed",
            "No WMS/charging order/work-hour business accuracy validation",
            "No operational as-of receipt validation possible for Yunji",
        ],
    }
    (root / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    validate(parser.parse_args().root.resolve())
