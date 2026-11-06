# ruff: noqa: T201, PLR2004, RUF001, SIM115
"""Build full real-record energy datasets, storing complete windows in gzip batches."""

# Dynamic gzip handles are owned by ExitStack and closed on every exception path.

import argparse
import csv
import gzip
import hashlib
import json
import zipfile
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tools.datasets.build_energy_datasets import (
    PROFILES,
    SEMANTICS,
    calibrate_events,
    find_events,
    get_split,
    make_forecast_series,
    make_native,
    normalize_meter,
    purpose,
    sha,
    write_csv,
    write_json,
    write_review_html,
)

VERSION = "full-1.0.0"
BATCH_SIZE = 500
CUTS = {
    "S01": [pd.Timestamp(x, tz="Asia/Shanghai") for x in ("2026-03-31", "2026-06-30")],
    "S02": [pd.Timestamp(x, tz="Asia/Shanghai") for x in ("2026-08-28", "2026-09-13")],
}
HISTORY_COLUMNS = ["interval_start", "interval_end", "average_power_kw", "quality_flag", "availability_status"]
TARGET_COLUMNS = [
    "interval_start",
    "interval_end",
    "average_power_kw",
    "electricity_kwh",
    "quality_flag",
    "primary_evaluation_eligible",
    "start_source_ref",
    "end_source_ref",
]


def cache_snapshot(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[tuple[str, int], Path], int]:
    """Stream the private snapshot into per-meter caches; require completed site markers."""
    cache = root / "internal" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    files, writers, sites, counts, ends = {}, {}, {}, Counter(), {}
    stack = ExitStack()
    header: dict[str, Any] = {}
    scope = []
    try:
        with gzip.open(root / "internal" / "source_snapshot.ndjson.gz", "rt", encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(line)
                kind = record["kind"]
                if kind == "snapshot":
                    header = record
                elif kind == "site":
                    sites[record["site_id"]] = record
                elif kind == "site_end":
                    ends[record["site_id"]] = record["rows"]
                elif kind == "legacy_scope":
                    scope.append(record)
                elif kind == "fact":
                    site, values = record["site_id"], record["values"]
                    key = (site, int(values[1]))
                    if key not in writers:
                        files[key] = cache / f"{site}_{values[1]}.csv.gz"
                        handle = stack.enter_context(
                            gzip.open(files[key], "wt", encoding="utf-8", newline="", compresslevel=1)
                        )
                        writers[key] = csv.writer(handle)
                        writers[key].writerow(["site_id", *header["fact_columns"]])
                    writers[key].writerow([site, *values])
                    counts[site] += 1
    finally:
        stack.close()
    if dict(counts) != ends or set(ends) != {"S01", "S02"}:
        raise ValueError(f"Incomplete snapshot: counts={dict(counts)}, end markers={ends}")
    write_json(
        root / "internal" / "source_scope_audit.json", {"header": header, "legacy_scopes": scope, "counts": counts}
    )
    print(f"Snapshot complete: {sum(counts.values()):,} source rows, {len(files)} meters", flush=True)
    return header, sites, files, sum(counts.values())


def load_cache(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype={"source_record_id": "str", "raw_value": "str"})
    for column in ("reading_time", "received_at"):
        raw[column] = pd.to_datetime(raw[column], format="mixed")
    raw["normalized_value"] = pd.to_numeric(raw.normalized_value, errors="coerce")
    raw["source_ref"] = [
        hashlib.sha256(f"{site}:{ref}".encode()).hexdigest()[:24]
        for site, ref in zip(raw.site_id, raw.source_record_id, strict=True)
    ]
    return raw


def cadence(registers: pd.DataFrame, site: str) -> int:
    if site == "S02":
        return 300
    seconds = registers.observed_at.diff().dt.total_seconds()
    # Recognize observed 15 min / 1 h native cadences; never upsample a sparse meter.
    candidates = seconds.round().value_counts()
    score = {n: int(candidates.loc[candidates.index.to_series().between(n - 60, n + 60)].sum()) for n in (900, 3600)}
    return max(score, key=score.get)


def csv_rows(frame: pd.DataFrame, columns: list[str]) -> list[list[str]]:
    data = frame[columns].copy()
    for column in columns:
        if pd.api.types.is_numeric_dtype(data[column]) and not pd.api.types.is_bool_dtype(data[column]):
            data[column] = data[column].map(lambda x: "" if pd.isna(x) else f"{x:.6f}")
        else:
            data[column] = data[column].map(lambda x: "" if pd.isna(x) else str(x))
    return data.to_numpy().tolist()


class WindowBatch:
    """Write actual histories/targets without creating one directory per window."""

    def __init__(self, package: Path, key: str, number: int) -> None:
        self.input_path = Path("task2_forecast/inputs") / key / f"batch_{number:05d}"
        self.target_path = Path("task2_forecast/evaluator_only") / key / f"batch_{number:05d}"
        self.stack = ExitStack()
        self.writers: dict[str, Any] = {}
        self.metadata = None
        for name, columns, relative in (
            ("history", HISTORY_COLUMNS, self.input_path),
            ("future_covariates", ["interval_start", "interval_end", "hour", "minute", "weekday"], self.input_path),
            ("future", TARGET_COLUMNS, self.target_path),
            (
                "baseline_predictions",
                ["interval_start", "interval_end", "last_observed_value", "previous_day", "previous_week"],
                self.target_path,
            ),
        ):
            directory = package / relative
            directory.mkdir(parents=True, exist_ok=True)
            handle = self.stack.enter_context(
                gzip.open(directory / f"{name}.csv.gz", "wt", encoding="utf-8", newline="", compresslevel=5)
            )
            self.writers[name] = csv.writer(handle)
            self.writers[name].writerow(["sequence_id", "step", *columns])
        self.metadata = self.stack.enter_context(
            gzip.open(package / self.input_path / "metadata.jsonl.gz", "wt", encoding="utf-8")
        )
        self.count = 0

    def add(
        self,
        sequence: str,
        history: list[Any],
        covariates: list[Any],
        future: list[Any],
        predictions: list[Any],
        metadata: dict[str, Any],
    ) -> None:
        for name, rows in (
            ("history", history),
            ("future_covariates", covariates),
            ("future", future),
            ("baseline_predictions", predictions),
        ):
            self.writers[name].writerows([sequence, step, *row] for step, row in enumerate(rows))
        self.metadata.write(json.dumps(metadata, ensure_ascii=False, default=str) + "\n")
        self.count += 1

    def close(self) -> None:
        self.stack.close()


def full_forecasts(
    series: pd.DataFrame, meta: dict[str, Any], package: Path, metrics: dict[Any, Any], eligibility: list[Any]
) -> list[dict[str, Any]]:
    if series.empty:
        return []
    site, meter = meta["site_id"], meta["meter_id"]
    cuts, lag = CUTS[site], int(site == "S02")
    train = series.loc[series.interval_end <= cuts[0], "average_power_kw"]
    information_ok = len(train) >= 96 and train.std() > 1e-9 and (train > 0).mean() >= 0.005
    histories = csv_rows(series, HISTORY_COLUMNS)
    targets = csv_rows(series, TARGET_COLUMNS)
    cov = series[["interval_start", "interval_end"]].copy()
    cov["hour"], cov["minute"], cov["weekday"] = (
        series.interval_start.dt.hour,
        series.interval_start.dt.minute,
        series.interval_start.dt.dayofweek,
    )
    covariates = csv_rows(cov, list(cov.columns))
    power = series.average_power_kw.to_numpy()
    times = pd.DatetimeIndex(series.interval_start).as_unit("ns").asi8
    time_index = {int(t): i for i, t in enumerate(times)}
    ends = series.interval_end.tolist()
    available = pd.DatetimeIndex(series.available_at).as_unit("ns").asi8
    primary = series.primary_evaluation_eligible.to_numpy(bool)
    windows: list[dict[str, Any]] = []
    for profile in PROFILES:
        counts = Counter()
        batches: dict[str, WindowBatch] = {}
        try:
            if information_ok:
                for _, segment in series.groupby("segment_id", sort=False):
                    offset = int(segment.index[0])
                    for local in range(
                        profile["history"] + lag, len(segment) - profile["horizon"] + 1, profile["stride"]
                    ):
                        j = offset + local
                        a, b, c = j - lag - profile["history"], j - lag, j + profile["horizon"]
                        origin = series.interval_start.iloc[j]
                        split = get_split(origin, ends[c - 1], cuts)
                        if not split or np.any(available[a:b] > origin.value):
                            continue
                        number = counts[split]
                        if number % BATCH_SIZE == 0:
                            if split in batches:
                                batches[split].close()
                            batches[split] = WindowBatch(
                                package, f"{split}/{meter}/{profile['id']}", number // BATCH_SIZE + 1
                            )
                        batch = batches[split]
                        sequence = f"{meter}_{profile['id']}_{split}_{number + 1:07d}"
                        forecasts = {"last_observed_value": np.repeat(power[b - 1], c - j)}
                        for model, days in (("previous_day", 1), ("previous_week", 7)):
                            relative = [time_index.get(int(t) - days * 86400 * 1_000_000_000, -1) for t in times[j:c]]
                            forecasts[model] = np.array([power[i] if a <= i < b else np.nan for i in relative])
                        predicted_rows = [
                            [
                                targets[k][0],
                                targets[k][1],
                                *[
                                    "" if np.isnan(forecasts[m][k - j]) else f"{forecasts[m][k - j]:.6f}"
                                    for m in forecasts
                                ],
                            ]
                            for k in range(j, c)
                        ]
                        record = {
                            "sequence_id": sequence,
                            "site_id": site,
                            "meter_id": meter,
                            "profile": profile["id"],
                            "split": split,
                            "prediction_origin": str(origin),
                            "history_length": b - a,
                            "forecast_horizon": c - j,
                            "history_parent_start_row": a,
                            "future_parent_start_row": j,
                            "observation_lag_steps": lag,
                            "input_path": str(batch.input_path),
                            "target_path": str(batch.target_path),
                            "sequence_position_in_batch": batch.count,
                        }
                        sequence_meta = {
                            **record,
                            "timezone": "Asia/Shanghai",
                            "sampling_interval_seconds": 900,
                            "target_columns": ["average_power_kw"],
                            "power_unit": "kW",
                            "history_source_start": series.start_source_ref.iloc[a],
                            "history_source_end": series.end_source_ref.iloc[b - 1],
                            "processing_version": VERSION,
                            "metering_semantics_status": SEMANTICS,
                        }
                        # Metadata stored with inputs carries no target source records or target values.
                        sequence_meta.pop("target_path")
                        sequence_meta.pop("future_parent_start_row")
                        batch.add(
                            sequence, histories[a:b], covariates[j:c], targets[j:c], predicted_rows, sequence_meta
                        )
                        windows.append(record)
                        counts[split] += 1
                        for model, prediction in forecasts.items():
                            for scope, mask in (
                                ("primary_without_time_alignment_targets", primary[j:c]),
                                ("all_targets_including_alignment_assumption", np.ones(c - j, bool)),
                            ):
                                mask = mask & np.isfinite(prediction)
                                if not mask.any():
                                    continue
                                residual = power[j:c][mask] - prediction[mask]
                                key = (site, profile["id"], split, model, scope)
                                accumulator = metrics.setdefault(key, np.zeros(5))
                                accumulator += [
                                    mask.sum(),
                                    abs(residual).sum(),
                                    (residual**2).sum(),
                                    abs(power[j:c][mask]).sum(),
                                    1,
                                ]
        finally:
            for batch in batches.values():
                batch.close()
        eligibility.extend(
            {
                "meter_id": meter,
                "profile": profile["id"],
                "split": split,
                "eligible_nonoverlapping_target_windows": counts[split],
                "exported_windows": counts[split],
                "status": "usable"
                if counts[split]
                else "low_training_information"
                if not information_ok
                else "insufficient_contiguous_valid_history_and_future",
            }
            for split in ("train", "validation", "test")
        )
    return windows


def event_sequences(
    native: pd.DataFrame, states: pd.Series, smooth: pd.Series, events: list[Any], meta: dict[str, Any], package: Path
) -> list[dict[str, Any]]:
    """Publish the complete native timeline in monthly sequences, including background and gaps."""
    site, meter = meta["site_id"], meta["meter_id"]
    splits = [
        get_split(a, b, CUTS[site]) or "boundary"
        for a, b in zip(native.interval_start, native.interval_end, strict=True)
    ]
    # The first reading has no interval start; it is retained in the period containing its endpoint.
    if len(native):
        splits[0] = get_split(native.interval_end.iloc[0], native.interval_end.iloc[0], CUTS[site]) or "boundary"
    keys = pd.DataFrame({"split": splits, "month": native.interval_end.dt.strftime("%Y-%m")}, index=native.index)
    result = []
    for (split, month), group in keys.groupby(["split", "month"], sort=True):
        selected = native.loc[group.index]
        sequence = f"{meter}_{month}_{split}"
        input_dir = Path("task1_events/inputs") / split / sequence
        label_dir = Path("task1_events/evaluator_only/sequences") / split / sequence
        output = selected.drop(columns=["segment_id"]).copy()
        output.insert(0, "step", range(len(output)))
        write_csv(package / input_dir / "observations.csv.gz", output)
        write_json(
            package / input_dir / "metadata.json",
            {
                **meta,
                "sequence_id": sequence,
                "split": split,
                "observations": len(output),
                "processing_version": VERSION,
            },
        )
        labels = pd.DataFrame(
            {
                "step": range(len(output)),
                "state": states.loc[selected.index].to_numpy(),
                "smoothed_power_kw": smooth.loc[selected.index].to_numpy(),
                "verification_level": "weak_rule_label",
            }
        )
        write_csv(package / label_dir / "state_labels.csv.gz", labels)
        start = selected.interval_start.dropna().min()
        end = selected.interval_end.max()
        annotations = []
        for event in events:
            a, b = pd.Timestamp(event["interval_start"]), pd.Timestamp(event["interval_end_exclusive"])
            if b > start and a < end:
                annotations.append(
                    {
                        **event,
                        "visible_start": str(max(a, start)),
                        "visible_end_exclusive": str(min(b, end)),
                        "continues_before_sequence": a < start,
                        "continues_after_sequence": b > end,
                    }
                )
        write_json(
            package / label_dir / "annotations.json",
            {
                "sequence_id": sequence,
                "events": annotations,
                "label_quality": "weak_rule_candidates_no_independent_business_truth",
            },
        )
        result.append(
            {
                "sequence_id": sequence,
                "site_id": site,
                "meter_id": meter,
                "split": split,
                "month": month,
                "observations": len(output),
                "parent_first_row": int(selected.index[0]),
                "parent_last_row": int(selected.index[-1]),
                "input_path": str(input_dir),
                "label_path": str(label_dir),
            }
        )
    return result


def summarize_metrics(metrics: dict[Any, Any]) -> pd.DataFrame:
    rows = []
    for key, (n, absolute, squared, actual, sequences) in sorted(metrics.items()):
        rows.append(
            dict(zip(("site_id", "profile", "split", "model", "scope"), key, strict=True))
            | {
                "target_steps": int(n),
                "sequences": int(sequences),
                "MAE_kw": absolute / n,
                "RMSE_kw": np.sqrt(squared / n),
                "WAPE_percent": absolute / actual * 100 if actual else np.nan,
            }
        )
    return pd.DataFrame(rows)


def build(root: Path) -> None:
    package = root / "package"
    if package.exists():
        raise RuntimeError("Package exists; preserve it and choose a new output directory")
    header, sites, files, source_count = cache_snapshot(root)
    package.mkdir()
    summaries, metadata, identity, forecast_index, event_index, all_events, eligibility, charts = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    metrics: dict[Any, Any] = {}
    for (site, equipment), path in sorted(files.items()):
        raw = load_cache(path)
        registers, removed = normalize_meter(raw, site)
        inventory = next(x for x in sites[site]["equipment"] if x["id"] == equipment)
        meter = f"{site}_M{equipment if site == 'S01' else equipment - 20:02d}"
        role = purpose(inventory["name"] or "")
        seconds = cadence(registers, site)
        excluded = role.endswith("direction_pending")
        meta = {
            "site_id": site,
            "meter_id": meter,
            "timezone": "Asia/Shanghai",
            "meter_purpose": role,
            "meter_purpose_confirmation": "platform_inventory_not_independent_operation_log",
            "meter_scope": "circuit_or_equipment_group_individual_member_unverified",
            "source_type": "measured_cumulative_register_derived_intervals",
            "energy_unit": "kWh",
            "power_unit": "kW",
            "metering_semantics_status": SEMANTICS,
            "native_interval_seconds": seconds,
            "physical_rated_power_verified": False,
            "mapping_version": sorted(registers.mapping_version.dropna().unique().tolist()),
            "source_time_basis": "MQTT UTC contract"
            if site == "S02"
            else "enterprise assumption: site local China time; archived period end accepted",
            "legacy_quality_basis": "numeric non-null cumulative values plus derived consistency checks; legacy table has no source quality flag",
        }
        metadata.append(meta)
        identity.append(
            {
                "meter_id": meter,
                "site_id": site,
                "source_equipment_id": equipment,
                "source_code": inventory["code"],
                "source_name": inventory["name"],
            }
        )
        published = registers[
            [
                "observed_at",
                "available_at",
                "availability_status",
                "cumulative_energy_kwh",
                "quality_status",
                "source_system",
                "source_ref",
                "mapping_version",
                "source_time_field",
                "duplicate_conflict",
                "valid_register",
            ]
        ].copy()
        published.insert(0, "meter_id", meter)
        write_csv(package / "base/registers" / f"{meter}.csv.gz", published)
        conflicts = raw[raw.reading_time.isin(registers.loc[registers.duplicate_conflict, "reading_time"])]
        if len(conflicts):
            evidence = conflicts[
                ["reading_time", "normalized_value", "source_system", "source_ref", "source_time_field"]
            ].copy()
            evidence.insert(0, "meter_id", meter)
            write_csv(package / "quality/duplicate_conflicts" / f"{meter}.csv.gz", evidence)
        native = make_native(registers, seconds)
        native.insert(0, "meter_id", meter)
        write_csv(package / "base/native_intervals" / f"{meter}.csv.gz", native)
        forecast = make_forecast_series(registers, native, site) if not excluded and seconds != 3600 else pd.DataFrame()
        if not forecast.empty:
            forecast.insert(0, "meter_id", meter)
            write_csv(package / "base/forecast_15min" / f"{meter}.csv.gz", forecast)
            windows = full_forecasts(forecast, meta, package, metrics, eligibility)
            forecast_index.extend(windows)
        else:
            windows = []
            eligibility.append(
                {
                    "meter_id": meter,
                    "profile": "all",
                    "split": "all",
                    "eligible_nonoverlapping_target_windows": 0,
                    "exported_windows": 0,
                    "status": "excluded_generation_or_storage"
                    if excluded
                    else "hourly_native_series_preserved_no_upsampling",
                }
            )
        smooth, states, rules = calibrate_events(native, CUTS[site][0], seconds)
        rules.update(
            {
                "rule_version": VERSION,
                "source_name": "enterprise_curve_rule_train_only",
                "valid_from": str(registers.observed_at.min()),
                "observed_native_interval_seconds": seconds,
            }
        )
        far = pd.Timestamp(header["cutoff_local_exclusive"]) + pd.Timedelta(days=1)
        events = (
            []
            if excluded
            else find_events(native, smooth, states, rules, meter, role, [far, far + pd.Timedelta(days=1)])
        )
        if excluded:
            states[:] = "unknown"
        for event in events:
            event.update(
                {
                    "split": get_split(
                        pd.Timestamp(event["interval_start"]), pd.Timestamp(event["interval_end_exclusive"]), CUTS[site]
                    )
                    or "boundary",
                    "rule_version": VERSION,
                    "boundary_resolution_seconds": seconds,
                    "boundary_semantics": f"threshold crossing in trailing {rules['smoothing_window_minutes']:g}min curve; not physical work/charging start or end",
                    "smoothing_window_minutes": rules["smoothing_window_minutes"],
                }
            )
            event["max_smoothed_power_kw"] = event.pop("max_smoothed_30min_power_kw")
        write_json(package / "task1_events/evaluator_only/calibration" / f"{meter}.json", rules)
        all_events.extend(events)
        event_index.extend(event_sequences(native, states, smooth, events, meta, package))
        valid = native[native.is_valid_interval]
        summary = {
            "site_id": site,
            "meter_id": meter,
            "meter_purpose": role,
            "raw_source_records": len(raw),
            "deduplicated_register_observations": len(registers),
            "duplicate_records_removed": removed,
            "duplicate_conflict_readings": int(registers.duplicate_conflict.sum()),
            "first_observed_at": str(registers.observed_at.min()),
            "last_observed_at": str(registers.observed_at.max()),
            "invalid_register_readings": int((~registers.valid_register).sum()),
            "native_interval_seconds": seconds,
            "valid_native_intervals": len(valid),
            "invalid_or_gap_intervals": int((~native.is_valid_interval).sum()),
            "maximum_observation_gap_hours": float(native.duration_seconds.max() / 3600),
            "register_decrease_intervals": int((native.quality_flag == "register_decrease_review").sum()),
            "candidate_events": len(events),
            "extended_activity_candidates": sum("extended_activity_review" in e["candidate_tags"] for e in events),
            "forecast_15min_intervals": len(forecast),
            "forecast_sequences": len(windows),
            "time_alignment_assumption_intervals": int(
                (forecast.quality_flag == "day_boundary_time_alignment_assumption").sum()
            )
            if len(forecast)
            else 0,
            "activity_timing_usable_under_pilot_rule": rules["activity_timing_usable_under_pilot_rule"],
            "role_status": "excluded_generation_storage" if excluded else "load_circuit",
        }
        summaries.append(summary)
        if events:
            event = max(events, key=lambda e: e["electricity_kwh"])
            start, end = pd.Timestamp(event["interval_start"]), pd.Timestamp(event["interval_end_exclusive"])
            view = native[
                (native.interval_end > start - pd.Timedelta(hours=3))
                & (native.interval_start < end + pd.Timedelta(hours=3))
            ]
            charts.append(
                {
                    "meter_id": meter,
                    "purpose": role,
                    "event": event,
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
            f"{meter}: {len(registers):,} actual registers; {len(windows):,} forecast windows; {len(events):,} candidate events",
            flush=True,
        )
    write_csv(root / "internal/identity_mapping_RESTRICTED.csv", pd.DataFrame(identity))
    write_json(package / "base/meter_metadata.json", metadata)
    write_csv(package / "quality/meter_quality_report.csv", pd.DataFrame(summaries))
    write_csv(package / "task1_events/sequence_index.csv", pd.DataFrame(event_index))
    events_frame = pd.DataFrame(all_events)
    events_frame["candidate_tags"] = events_frame.candidate_tags.map(lambda tags: "|".join(tags))
    write_csv(package / "task1_events/evaluator_only/all_candidate_events.csv", events_frame)
    review = events_frame[
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
    for column in ("reviewed_label", "independent_evidence", "reviewer", "reviewed_at", "boundary_review", "notes"):
        review[column] = ""
    write_csv(package / "task1_events/review_template.csv", review)
    write_csv(package / "task2_forecast/sequence_index.csv.gz", pd.DataFrame(forecast_index))
    write_csv(package / "task2_forecast/eligibility_report.csv", pd.DataFrame(eligibility))
    metric_frame = summarize_metrics(metrics)
    write_csv(package / "task2_forecast/baseline_metrics.csv", metric_frame)
    manifest = {
        "schema_version": "1.0",
        "processing_version": VERSION,
        "status": "full_real_record_dataset_pending_metering_business_verification",
        "cutoff_local_exclusive": header["cutoff_local_exclusive"],
        "created_at": header["created_at"],
        "source_snapshot_sha256": sha(root / "internal/source_snapshot.ndjson.gz"),
        "source_readonly_and_tenant_scoped": True,
        "source_observations": source_count,
        "independent_register_observations": sum(s["deduplicated_register_observations"] for s in summaries),
        "duplicates_removed": sum(s["duplicate_records_removed"] for s in summaries),
        "meters_with_observations": len(summaries),
        "sites": sorted(sites),
        "first_observed_at": min(s["first_observed_at"] for s in summaries),
        "last_observed_at": max(s["last_observed_at"] for s in summaries),
        "forecast_sequences": len(forecast_index),
        "event_review_sequences": len(event_index),
        "candidate_events": len(all_events),
        "verified_business_events": 0,
        "synthetic_observations": 0,
        "imputed_intervals": 0,
        "external_sample_rows_used": 0,
        "max_exported_windows_per_meter_profile_split": None,
        "sampling_policy": "all eligible continuous windows; stride equals forecast horizon, overlapping histories do not count as new observations",
        "batch_size_max_sequences": BATCH_SIZE,
        "event_sequence_policy": "all native rows exactly once; monthly per meter per time split, gaps preserved",
        "time_splits": {
            s: {"training_target_end_exclusive": str(c[0]), "validation_target_end_exclusive": str(c[1])}
            for s, c in CUTS.items()
        },
        "time_splits_basis": "same dates as pilot; added historical observations belong to training",
        "metering_semantics_status": SEMANTICS,
        "assumption_sources": [
            "existing application point mapping and legacy migration zygdnsz",
            "inventory circuit purpose",
            "enterprise train-only event rule",
        ],
        "operational_asof_limit": "Yunji receipt time unknown: retrospective measurement-time backtest; MQTT receipt checked with one-step history lag",
        "identity_policy": "pseudonymous site/meter IDs; original equipment addresses retained only in restricted internal directory",
        "full_package_contains_evaluation_answers": True,
        "full_base_series_must_not_be_shared_with_hidden_test_participants": True,
        "distribution_authorization_status": "customer review package; competition sharing permission and competition rules to be confirmed",
    }
    write_json(package / "manifest.json", manifest)
    write_json(
        package / "task1_events/task_spec.json",
        {
            "task_id": "load_state_and_sustained_energy_events",
            "version": VERSION,
            "mode": "offline_curve_review",
            "verified_operation_labels": 0,
            "candidate_labels": len(all_events),
            "candidate_duration_is_not_equipment_hours": True,
            "sequence_coverage": "complete native observation timeline including unknown/background/invalid intervals",
        },
    )
    write_json(
        package / "task2_forecast/task_spec.json",
        {
            "task_id": "short_term_meter_load_forecast",
            "version": VERSION,
            "profiles": PROFILES,
            "sampling_interval_seconds": 900,
            "target": "average_power_kw",
            "future_actuals_are_not_in_inputs": True,
            "history_observation_lag_steps_by_site": {"S01": 0, "S02": 1},
            "training_validation_test_target_periods_are_disjoint": True,
            "primary_mask_column": "primary_evaluation_eligible",
            "storage": "complete CSV gzip batches, <=500 sequences per batch; sequence_id and step identify every row",
        },
    )
    write_review_html(root, manifest, summaries, charts, metric_frame)
    review_path = root / "数据集评审.html"
    review_path.write_text(
        review_path.read_text().replace("首版", "全量版").replace("30分钟尾随平滑", "按原生采样粒度尾随平滑"),
        encoding="utf-8",
    )
    write_documentation(root, manifest, summaries, pd.DataFrame(forecast_index))
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


def write_documentation(root: Path, manifest: dict[str, Any], summaries: list[Any], windows: pd.DataFrame) -> None:
    package = root / "package"
    quality = pd.DataFrame(summaries)
    site_rows = []
    for site, title in (("S01", "祥泰"), ("S02", "安方")):
        group = quality[quality.site_id == site]
        site_rows.append(
            f"| {title}（{site}） | {len(group)} | {group.deduplicated_register_observations.sum():,} | {group.first_observed_at.min()} | {group.last_observed_at.max()} |"
        )
    forecast_counts = windows.groupby(["site_id", "profile", "split"]).size().reset_index(name="sequences")
    write_csv(package / "task2_forecast/sequence_counts.csv", forecast_counts)
    fields = [
        ("sequence_id", "唯一序列编号", "string"),
        ("step", "序列内从0起的区间序号；历史和未来各自计数", "integer"),
        ("observed_at", "累计读数原始观测时间，归一化为东八区显示", "ISO8601+08:00"),
        ("interval_start", "区间开始，含该时刻", "ISO8601+08:00"),
        ("interval_end", "区间结束，不含该时刻", "ISO8601+08:00"),
        ("cumulative_energy_kwh", "系统映射累计有功电量，不重复乘倍率", "system-mapped kWh"),
        ("electricity_kwh", "相邻有效累计值的非负差；缺口、复位和无效端点留空", "system-mapped kWh"),
        ("average_power_kw", "有效区间电量除以区间小时数", "system-mapped kW"),
        ("available_at", "原始MQTT消息接收时间，云集未知时为空", "ISO8601+08:00/null"),
        ("source_ref", "来源记录稳定摘要；原始地址仅存内部", "24 hex"),
        (
            "source_time_field",
            "reading_time原始读数时间；legacy_period_end旧区间结束时间；其他回退时间不进入有效差分",
            "enum",
        ),
        ("valid_register", "非空、来源单位有效、无同时间冲突、时间来源可接受", "boolean"),
        (
            "quality_flag",
            "measured实测差分；day_boundary_time_alignment_assumption日末对齐；data_gap_or_cadence_change缺口或频率变化；register_decrease_review累计值下降；invalid_endpoint_or_conflict无效或冲突",
            "enum",
        ),
        ("primary_evaluation_eligible", "预测主要评分可用，不依赖日末对齐假设", "boolean"),
        ("state", "unknown/low_load/active_load/high_load；来自训练期曲线规则，非业务工时", "weak rule label"),
        ("verification_level", "rule_candidate候选；独立确认标签当前为0", "enum"),
        ("history_parent_start_row", "完整15分钟底表内0起的历史第一行", "integer"),
        ("future_parent_start_row", "完整15分钟底表内0起的目标第一行，仅评审索引", "integer"),
        ("sequence_position_in_batch", "该序列在批文件中的0起位置", "integer"),
        ("hour/minute/weekday", "来自预先可知区间时间；weekday周一0到周日6，无未来实测负荷", "calendar"),
    ]
    write_csv(
        package / "quality/data_dictionary.csv", pd.DataFrame(fields, columns=["field", "meaning", "unit_or_type"])
    )
    text = f"""# 两套仓储能耗数据集 v1.0：全量真实记录版

已补入现有生产库旧历史，保留原始累计值、原生频率和缺口，并导出全部满足连续性及可用时间条件的预测序列。数据截至2026-09-28 00:00（北京时间，不含）。

## 数据规模

| 现场 | 电表数 | 去重累计读数 | 最早观测 | 最晚观测 |
|---|---:|---:|---|---|
{chr(10).join(site_rows)}

来源记录 **{manifest["source_observations"]:,}** 条，去重后独立累计读数 **{manifest["independent_register_observations"]:,}** 条。两套任务共用这些来源，重叠历史窗口不算新增观测。模拟、插补、外部示例记录均为 **0**。

- 用能事件集：**{manifest["event_review_sequences"]:,}** 个完整月度曲线序列，覆盖全部电表底表；**{manifest["candidate_events"]:,}** 个规则候选事件，附逐区间状态、事件表和人工复核模板。
- 短期负荷预测集：**{manifest["forecast_sequences"]:,}** 个完整预测序列，取消每表每分区12条的试验版上限。历史、未来日历、未来真值、基线结果均已实际写入CSV文件。

## 文件组织与读取

`base/registers` 是累计读数，`base/native_intervals` 是按原生频率计算的完整区间，`base/forecast_15min` 是有效连续15分钟预测底表。

事件集在 `task1_events/inputs/<分区>/<序列>/` 放 `observations.csv.gz` 和 `metadata.json`；`evaluator_only/sequences` 放逐区间状态和候选标注。`sequence_index.csv` 提供完整目录。普通低负荷、未知状态和缺口同样保留，不只挑选明显事件。

预测集在 `task2_forecast/inputs/<分区>/<电表>/<任务>/batch_xxxxx/` 放 `history.csv.gz`、`future_covariates.csv.gz`、`metadata.jsonl.gz`；`evaluator_only` 对应批次放 `future.csv.gz`、`baseline_predictions.csv.gz`。一个批次最多500条独立编号序列，每行使用 `sequence_id + step` 区分。可用 pandas.read_csv 直接读取 `.csv.gz`。`sequence_index.csv.gz` 的路径、批次位置和长度可直接定位一条序列，不必同时读全部数据。`read_sequence.py` 为读取示例。

预测任务为：24小时历史→未来1小时（96→4点）、7天历史→未来24小时（672→96点）、24小时历史→未来24小时（96→96点）。均为15分钟粒度。单表单任务目标窗口不重叠，历史允许重叠。整日任务为连续24小时，不保证午夜起点。序列数明细见 `sequence_counts.csv`。

分区沿用试验版日期，新补旧历史进入训练集。祥泰：训练目标结束≤2026-03-31，验证目标位于3月31日至6月30日，测试目标起点≥6月30日；安方对应8月28日、9月13日。所有日期均为东八区00:00，区间采用左闭右开。跨分区预测目标不导出；事件完整底表跨分区原生区间单独列为boundary，不用于训练评分。

## 处理与质量

旧表使用应用迁移定义的 `ZYGDNSZ` 累计电量；优先reading_time，其次旧区间end_time并保留时间来源。仅start_time或add_time的回退记录保留在底表但不参与有效差分。旧库无quality_status列，数值非空通过来源层检查，另经重复冲突、时间、下降和差分检查；不声称来源已校验。

同表同时间重复记录去重，规范点位优先于旧表；有不同值时保留冲突证据并排除相关区间。300秒、900秒、3600秒原生频率分别保留；小时表不扩写成15分钟。安方严格3个连续5分钟区间聚合；祥泰允许日末±60秒对齐，原时间仍保留，两侧涉及对齐的目标不进入主要指标。缺口不插值，累计下降不当作零电量。

系统映射kWh及派生kW保留现有单位；CT/PT、寄存器分辨率和设备额定值尚未现场确认。事件阈值为明示的企业曲线假设，仅由训练期拟合，见逐表calibration文件；候选持续时间不能写成设备工时。独立确认业务事件 **0**。光伏/储能方向待核实，保留底表，排除负荷任务与作业候选。

安方预测历史末端比预测起点早15分钟，且消息接收时间≤起点；祥泰消息入库时间未知，仅支持按观测时间回测。没有用未来负荷、接收时间或目标摘要构造模型输入。季节性基线匹配真实可用历史，缺少位置则预测留空，指标同步排除。

## 交付与授权

两个完整ZIP供客户内部评审，含真实底表及评测答案。预测隐藏测试只能分发独立的 `预测任务输入包.zip`；不能同时分发完整底表、事件集测试期曲线或未来真值。`internal` 中来源快照和身份映射不会进入ZIP。

化名处理保留了真实曲线，实际对外使用需按客户授权范围及大赛正式要求选择。当前没有填造授权证明或使用许可。包体按实际字节统计，不把填报截图中的5GB视为已确认最低要求，也不为达到5GB增加模拟数据。校验结果和SHA256见validation_report及checksums。
"""
    (root / "制作结果与使用说明.md").write_text(text, encoding="utf-8")
    (package / "README.md").write_text(text, encoding="utf-8")
    for task in ("task1_events", "task2_forecast"):
        (package / task / "README.md").write_text(text, encoding="utf-8")
    loader = '''"""Read a complete forecast sequence from a batch. pandas is required."""
import argparse
import json
from pathlib import Path
import gzip
import pandas as pd

def read_sequence(package, sequence_id, evaluator=False):
    package = Path(package)
    index = pd.read_csv(package / "task2_forecast/sequence_index.csv.gz")
    row = index.loc[index.sequence_id == sequence_id].iloc[0]
    n, h, f = int(row.sequence_position_in_batch), int(row.history_length), int(row.forecast_horizon)
    def block(directory, filename, length):
        return pd.read_csv(package / directory / filename, skiprows=range(1, 1+n*length), nrows=length)
    result = {"history": block(row.input_path,"history.csv.gz",h), "future_covariates": block(row.input_path,"future_covariates.csv.gz",f)}
    with gzip.open(package / row.input_path / "metadata.jsonl.gz", "rt", encoding="utf-8") as stream:
        for i, line in enumerate(stream):
            if i == n:
                result["metadata"] = json.loads(line)
                break
    if evaluator:
        result["future"] = block(row.target_path,"future.csv.gz",f)
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package")
    parser.add_argument("sequence_id")
    parser.add_argument("--evaluator", action="store_true")
    args = parser.parse_args()
    result = read_sequence(args.package,args.sequence_id,args.evaluator)
    print(json.dumps(result["metadata"],ensure_ascii=False,indent=2))
    for name, value in result.items():
        if isinstance(value,pd.DataFrame):
            print(name, value.shape, value.head())
'''
    (package / "task2_forecast/read_sequence.py").write_text(loader, encoding="utf-8")


def archives(root: Path) -> None:
    package = root / "package"
    sizes = []
    for task, filename in (
        ("task1_events", "仓储设备用能事件数据集_v1.0.zip"),
        ("task2_forecast", "仓储短期电力负荷预测数据集_v1.0.zip"),
    ):
        paths = [p for folder in ("base", "quality", task) for p in (package / folder).rglob("*") if p.is_file()]
        paths += [package / "manifest.json", package / "README.md"]
        if (package / "validation_report.json").exists():
            paths.append(package / "validation_report.json")
        with zipfile.ZipFile(root / filename, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as archive:
            for path in sorted(paths):
                archive.write(path, str(path.relative_to(package)))
        sizes.append({"filename": filename, "bytes": (root / filename).stat().st_size, "sha256": sha(root / filename)})
    filename = "预测任务输入包.zip"
    with zipfile.ZipFile(root / filename, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as archive:
        for path in sorted((package / "task2_forecast/inputs").rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(package)))
        # Remove evaluator index columns while preserving sequence and batch identifiers.
        index = pd.read_csv(package / "task2_forecast/sequence_index.csv.gz").drop(
            columns=["target_path", "future_parent_start_row"]
        )
        archive.writestr("task2_forecast/sequence_index.csv", index.to_csv(index=False))
        for name in ("task_spec.json", "README.md"):
            path = package / "task2_forecast" / name
            archive.write(path, str(path.relative_to(package)))
    sizes.append({"filename": filename, "bytes": (root / filename).stat().st_size, "sha256": sha(root / filename)})
    write_json(root / "archive_sizes.json", sizes)
    write_csv(
        root / "checksums.csv",
        pd.DataFrame(
            [
                {"path": str(path.relative_to(package)), "bytes": path.stat().st_size, "sha256": sha(path)}
                for path in sorted(package.rglob("*"))
                if path.is_file()
            ]
        ),
    )
    print(json.dumps(sizes, ensure_ascii=False, indent=2), flush=True)


def audit_legacy_times(root: Path) -> None:
    """Record source alignment evidence without guessing or rewriting old timestamps."""
    rows = []
    for path in sorted((root / "internal/cache").glob("S01_*.csv.gz")):
        raw = load_cache(path)
        canonical = (
            raw[raw.source_system == "yunji"].drop_duplicates("reading_time").set_index("reading_time").normalized_value
        )
        archived = (
            raw[raw.source_system == "yunji_legacy_archive"]
            .drop_duplicates("reading_time")
            .set_index("reading_time")
            .normalized_value
        )
        meter = f"S01_M{int(raw.equipment_id.iloc[0]):02d}"
        for offset in (0, 8):
            candidate = archived.copy()
            candidate.index += pd.Timedelta(hours=offset)
            paired = pd.concat([canonical, candidate], axis=1, join="inner").dropna()
            difference = (paired.iloc[:, 0] - paired.iloc[:, 1]).abs()
            rows.append(
                {
                    "meter_id": meter,
                    "archive_comparison_offset_hours": offset,
                    "overlapping_numeric_pairs": len(paired),
                    "equal_value_fraction": float((difference <= 1e-6).mean()) if len(paired) else None,
                    "median_absolute_register_difference_kwh": float(difference.median()) if len(paired) else None,
                    "offset_applied_to_dataset": False,
                    "conclusion": "comparison_evidence_only_timezone_requires_source_confirmation",
                }
            )
    package = root / "package"
    write_csv(package / "quality/legacy_time_alignment_audit.csv", pd.DataFrame(rows))
    path = package / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest.update(
        {
            "observation_count_semantics": "unique meter plus recorded timestamp cumulative rows; physical independence across timezone-ambiguous sources not certified",
            "legacy_time_semantics_status": "some archived readings show +8h alignment evidence; no timezone correction applied without acquisition evidence; conflicting same-time endpoints excluded",
            "script_sha256": {p.name: sha(p) for p in Path(__file__).parent.glob("*.py")},
        }
    )
    write_json(path, manifest)
    metadata_path = package / "base/meter_metadata.json"
    metadata = json.loads(metadata_path.read_text())
    for meter in metadata:
        if meter["site_id"] == "S01":
            meter["legacy_time_semantics_status"] = (
                "recorded naive time interpreted provisionally as site local; archive timezone unconfirmed"
            )
    write_json(metadata_path, metadata)
    note = "\n旧表时区复核：部分祥泰旧累计值与规范表按+8小时比较时更一致，提示时间口径可能不同，但目前缺少旧采集接口的时区证据。数据集保留库中时间，不据数值相似程度自行平移；同时间冲突端点已排除，比较证据见 quality/legacy_time_alignment_audit.csv。最早/最晚时间及去重计数均为库中记录口径，不能当作跨来源已认证的物理独立观测。按小时段分析、日期对齐和正式比赛评测前应核实该时间口径。\n"
    for path in [
        root / "制作结果与使用说明.md",
        package / "README.md",
        package / "task1_events/README.md",
        package / "task2_forecast/README.md",
    ]:
        contents = (
            path.read_text()
            .replace("全量真实记录版", "全量生产库记录版")
            .replace("去重后独立累计读数", "按表和记录时间去重后的累计记录")
        )
        if "旧表时区复核：" not in contents:
            contents += note
        path.write_text(contents, encoding="utf-8")
    review = root / "数据集评审.html"
    review.write_text(review.read_text().replace("独立累计读数", "去重累计记录"), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--archives-only", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.archives_only:
        archives(arguments.root)
    elif arguments.audit_only:
        audit_legacy_times(arguments.root)
    else:
        build(arguments.root)
        audit_legacy_times(arguments.root)
