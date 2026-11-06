# ruff: noqa: T201, PLR2004
"""Validate every full-package sequence against its measured parent series."""

import argparse
import gzip
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tools.datasets.build_energy_datasets import SEMANTICS, sha, write_json
from tools.datasets.build_energy_full import CUTS, HISTORY_COLUMNS, TARGET_COLUMNS


def require(condition: Any, message: str) -> None:
    if not bool(condition):
        raise AssertionError(message)


def equal_columns(actual: pd.DataFrame, expected: pd.DataFrame, columns: list[str], context: str) -> None:
    require(len(actual) == len(expected), f"{context}: length")
    for column in columns:
        a, b = actual[column].reset_index(drop=True), expected[column].reset_index(drop=True)
        if pd.api.types.is_numeric_dtype(b):
            require(
                np.allclose(a.to_numpy(float), b.to_numpy(float), atol=1.1e-6, rtol=0, equal_nan=True),
                f"{context}: {column}",
            )
        else:
            require(a.fillna("").astype(str).equals(b.fillna("").astype(str)), f"{context}: {column}")


def validate(root: Path) -> None:
    package = root / "package"
    manifest = json.loads((package / "manifest.json").read_text())
    require(
        manifest["synthetic_observations"]
        == manifest["imputed_intervals"]
        == manifest["external_sample_rows_used"]
        == 0,
        "provenance",
    )
    require(
        manifest["verified_business_events"] == 0 and manifest["metering_semantics_status"] == SEMANTICS,
        "unverified field semantics",
    )
    require(sha(root / "internal/source_snapshot.ndjson.gz") == manifest["source_snapshot_sha256"], "snapshot hash")
    quality = pd.read_csv(package / "quality/meter_quality_report.csv")
    require(quality.raw_source_records.sum() == manifest["source_observations"], "source count")
    require(
        quality.deduplicated_register_observations.sum() == manifest["independent_register_observations"],
        "deduplicated count",
    )
    index = pd.read_csv(package / "task2_forecast/sequence_index.csv.gz")
    require(len(index) == manifest["forecast_sequences"] and index.sequence_id.is_unique, "forecast index")
    event_index = pd.read_csv(package / "task1_events/sequence_index.csv")
    require(len(event_index) == manifest["event_review_sequences"] and event_index.sequence_id.is_unique, "event index")
    require(
        event_index.observations.sum() == manifest["independent_register_observations"],
        "complete event timeline coverage",
    )
    events = pd.read_csv(package / "task1_events/evaluator_only/all_candidate_events.csv")
    require(
        len(events) == manifest["candidate_events"] and (events.verification_level == "rule_candidate").all(),
        "candidate labels",
    )
    history_total, future_total, batch_count, native_total, event_rows = 0, 0, 0, 0, 0
    for meter in quality.meter_id:
        registers = pd.read_csv(package / "base/registers" / f"{meter}.csv.gz")
        native = pd.read_csv(package / "base/native_intervals" / f"{meter}.csv.gz")
        require(registers.source_ref.is_unique and registers.observed_at.is_unique, f"{meter}: unique sources/time")
        require(len(registers) == len(native), f"{meter}: native coverage")
        valid = native.is_valid_interval.to_numpy(bool)
        differences = registers.cumulative_energy_kwh.diff().to_numpy()
        require(
            np.allclose(native.electricity_kwh[valid], differences[valid], atol=1.1e-6, rtol=0),
            f"{meter}: actual cumulative differences",
        )
        require(
            native.electricity_kwh[~valid].isna().all() and native.average_power_kw[~valid].isna().all(),
            f"{meter}: no fill for gaps/resets",
        )
        require(
            np.allclose(
                native.average_power_kw[valid],
                native.electricity_kwh[valid] * 3600 / native.duration_seconds[valid],
                atol=1.1e-6,
                rtol=0,
            ),
            f"{meter}: power",
        )
        require((native.end_source_ref == registers.source_ref).all(), f"{meter}: native source refs")
        require(not (valid & registers.duplicate_conflict.to_numpy(bool)).any(), f"{meter}: conflict excluded")
        for row in event_index[event_index.meter_id == meter].itertuples():
            observations = pd.read_csv(package / row.input_path / "observations.csv.gz")
            expected = native.iloc[row.parent_first_row : row.parent_last_row + 1]
            equal_columns(observations, expected, [c for c in native if c != "segment_id"], row.sequence_id)
            labels = pd.read_csv(package / row.label_path / "state_labels.csv.gz")
            require(len(labels) == len(observations) == row.observations, f"{row.sequence_id}: labels complete")
            require((labels.step.to_numpy() == np.arange(len(labels))).all(), f"{row.sequence_id}: label steps")
            require(
                set(labels.state) <= {"unknown", "low_load", "active_load", "high_load"},
                f"{row.sequence_id}: allowed states",
            )
            rules = json.loads((package / "task1_events/evaluator_only/calibration" / f"{meter}.json").read_text())
            if not rules["activity_timing_usable_under_pilot_rule"]:
                require((labels.state == "unknown").all(), f"{row.sequence_id}: quantization screen")
            annotations = json.loads((package / row.label_path / "annotations.json").read_text())
            require(
                all(e["verification_level"] == "rule_candidate" for e in annotations["events"]),
                f"{row.sequence_id}: weak annotations",
            )
            event_rows += len(observations)
        require(
            event_index.loc[event_index.meter_id == meter, "observations"].sum() == len(native),
            f"{meter}: complete event input",
        )
        native_total += len(native)
        parent_path = package / "base/forecast_15min" / f"{meter}.csv.gz"
        if not parent_path.exists():
            require(not (index.meter_id == meter).any(), f"{meter}: no false forecast")
            continue
        parent = pd.read_csv(parent_path)
        starts, ends = pd.to_datetime(parent.interval_start), pd.to_datetime(parent.interval_end)
        require(((ends - starts).dt.total_seconds() == 900).all(), f"{meter}: exact 15 min")
        require(
            np.allclose(parent.average_power_kw, parent.electricity_kwh * 4, atol=1.1e-6, rtol=0),
            f"{meter}: forecast units",
        )
        lookup = registers.set_index("source_ref").cumulative_energy_kwh
        energy = parent.end_source_ref.map(lookup) - parent.start_source_ref.map(lookup)
        require(np.allclose(energy, parent.electricity_kwh, atol=1.1e-6, rtol=0), f"{meter}: forecast traceable energy")
        assumed = parent.quality_flag == "day_boundary_time_alignment_assumption"
        require(not parent.primary_evaluation_eligible[assumed].any(), f"{meter}: alignment mask")
        subset = index[index.meter_id == meter]
        for (_profile, _split), group in subset.groupby(["profile", "split"]):
            ordered = group.sort_values("future_parent_start_row")
            bounds = ordered.future_parent_start_row.to_numpy()
            lengths = ordered.forecast_horizon.to_numpy()
            require((bounds[1:] >= bounds[:-1] + lengths[:-1]).all(), f"{meter}: nonoverlapping targets")
        for input_path, group in subset.groupby("input_path", sort=False):
            group = group.sort_values("sequence_position_in_batch")
            require(
                (group.sequence_position_in_batch.to_numpy() == np.arange(len(group))).all(),
                f"{input_path}: batch positions",
            )
            require(len(group) <= 500, f"{input_path}: maximum batch size")
            h, f = int(group.history_length.iloc[0]), int(group.forecast_horizon.iloc[0])
            a, j = group.history_parent_start_row.to_numpy(), group.future_parent_start_row.to_numpy()
            hi = (a[:, None] + np.arange(h)).ravel()
            fi = (j[:, None] + np.arange(f)).ravel()
            history = pd.read_csv(package / input_path / "history.csv.gz")
            future = pd.read_csv(package / group.target_path.iloc[0] / "future.csv.gz")
            cov = pd.read_csv(package / input_path / "future_covariates.csv.gz")
            for frame, length in ((history, h), (future, f), (cov, f)):
                require(
                    np.array_equal(frame.sequence_id.to_numpy(), np.repeat(group.sequence_id.to_numpy(), length)),
                    f"{input_path}: sequence ids",
                )
                require(
                    np.array_equal(frame.step.to_numpy(), np.tile(np.arange(length), len(group))),
                    f"{input_path}: steps",
                )
            equal_columns(history, parent.iloc[hi], HISTORY_COLUMNS, input_path + ":history")
            equal_columns(future, parent.iloc[fi], TARGET_COLUMNS, input_path + ":future")
            equal_columns(cov, parent.iloc[fi], ["interval_start", "interval_end"], input_path + ":cov times")
            require(
                list(cov.columns)
                == ["sequence_id", "step", "interval_start", "interval_end", "hour", "minute", "weekday"],
                f"{input_path}: no future observed covariates",
            )
            cov_times = pd.to_datetime(cov.interval_start)
            require(
                np.array_equal(cov.hour, cov_times.dt.hour)
                and np.array_equal(cov.minute, cov_times.dt.minute)
                and np.array_equal(cov.weekday, cov_times.dt.dayofweek),
                f"{input_path}: calendar features",
            )
            # History and targets must each stay within one observed uninterrupted segment.
            require(
                (np.ptp(parent.segment_id.to_numpy()[hi].reshape(-1, h), axis=1) == 0).all(),
                f"{input_path}: uninterrupted history",
            )
            require(
                (np.ptp(parent.segment_id.to_numpy()[fi].reshape(-1, f), axis=1) == 0).all(),
                f"{input_path}: uninterrupted future",
            )
            origins = pd.to_datetime(group.prediction_origin)
            last_history_end = ends.iloc[a + h - 1].reset_index(drop=True)
            origin_series = origins.reset_index(drop=True)
            require(
                (
                    (origin_series - last_history_end).dt.total_seconds().to_numpy()
                    == group.observation_lag_steps.to_numpy() * 900
                ).all(),
                f"{input_path}: asof lag",
            )
            for split, cut_start, cut_end in (
                ("train", None, CUTS[meter[:3]][0]),
                ("validation", CUTS[meter[:3]][0], CUTS[meter[:3]][1]),
                ("test", CUTS[meter[:3]][1], None),
            ):
                if group.split.iloc[0] == split:
                    if cut_start is not None:
                        require((starts.iloc[j] >= cut_start).all(), f"{input_path}: split start")
                    if cut_end is not None:
                        require((ends.iloc[j + f - 1] <= cut_end).all(), f"{input_path}: split end")
            if meter.startswith("S02"):
                receipts = pd.to_datetime(parent.available_at.iloc[hi], format="mixed").to_numpy().reshape(-1, h)
                require(
                    all(all(t <= o for t in ts) for o, ts in zip(origins, receipts, strict=True)),
                    f"{input_path}: receipts available at origin",
                )
            with gzip.open(package / input_path / "metadata.jsonl.gz", "rt", encoding="utf-8") as stream:
                metadata = [json.loads(line) for line in stream]
            require([m["sequence_id"] for m in metadata] == group.sequence_id.tolist(), f"{input_path}: metadata")
            require(
                all("target_path" not in m and "future_parent_start_row" not in m for m in metadata),
                f"{input_path}: no evaluator metadata",
            )
            history_total += len(history)
            future_total += len(future)
            batch_count += 1
        print(f"Validated {meter}: {len(subset):,} full forecast sequences, complete event timeline", flush=True)
    eligibility = pd.read_csv(package / "task2_forecast/eligibility_report.csv")
    require(
        (eligibility.eligible_nonoverlapping_target_windows == eligibility.exported_windows).all(),
        "all eligible windows exported",
    )
    require(eligibility.exported_windows.sum() == len(index), "eligible count matches index")
    report = {
        "status": "passed",
        "forecast_sequences_checked": len(index),
        "event_sequences_checked": len(event_index),
        "all_event_observation_rows_checked": event_rows,
        "native_rows_checked": native_total,
        "materialized_history_rows_checked": history_total,
        "materialized_future_rows_checked": future_total,
        "forecast_batches_checked": batch_count,
        "candidate_events_checked": len(events),
        "synthetic_or_imputed_rows": 0,
        "checks": [
            "completed read-only source snapshot and SHA256",
            "dedup/native coverage and cumulative source differences",
            "all event input rows and weak labels",
            "all eligible forecast windows exported",
            "every history/target row equals measured parent",
            "continuous 15min segments and nonoverlapping targets",
            "time split boundaries",
            "calendar-only future input",
            "MQTT receipt availability and 15min observation lag",
            "time-alignment target exclusion mask",
            "no independently confirmed operation labels",
        ],
    }
    write_json(root / "validation_report.json", report)
    write_json(package / "validation_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


def validate_archives(root: Path) -> None:
    result = []
    for path in sorted(root.glob("*.zip")):
        with zipfile.ZipFile(path) as archive:
            require(archive.testzip() is None, f"{path.name}: ZIP CRC")
            names = archive.namelist()
            require(
                not any("internal/" in name or "RESTRICTED" in name for name in names),
                f"{path.name}: no restricted files",
            )
            if path.name == "预测任务输入包.zip":
                require(
                    not any("evaluator_only" in name or name.startswith("base/") for name in names),
                    "input bundle excludes test answers",
                )
        result.append({"archive": path.name, "files": len(names), "sha256": sha(path), "status": "passed"})
    require(len(result) == 3, "three deliverable archives")
    write_json(root / "archive_validation.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--archives-only", action="store_true")
    args = parser.parse_args()
    if args.archives_only:
        validate_archives(args.root)
    else:
        validate(args.root)
