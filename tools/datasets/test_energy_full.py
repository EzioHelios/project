"""Focused regression tests for full-batch export and archived record handling."""

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from tools.datasets.build_energy_datasets import calibrate_events, make_native, normalize_meter
from tools.datasets.build_energy_full import full_forecasts
from tools.datasets.test_energy_processing import registers


class FullEnergyChecks(unittest.TestCase):
    def test_canonical_record_wins_archive_but_conflicting_endpoint_is_invalid(self) -> None:
        raw = pd.DataFrame(
            {
                "id": [10, 999, 11],
                "reading_time": pd.to_datetime(["2026-01-01", "2026-01-01", "2026-01-01 00:15"], format="mixed"),
                "normalized_value": [10, 11, 12],
                "source_system": ["yunji", "yunji_legacy_archive", "yunji_legacy_archive"],
                "received_at": pd.to_datetime([None] * 3),
                "quality_status": "valid",
                "unit": "kWh",
                "source_time_field": ["reading_time", "legacy_period_end", "legacy_ingest_time"],
            }
        )
        result, removed = normalize_meter(raw, "S01")
        self.assertEqual(removed, 1)
        self.assertEqual(result.cumulative_energy_kwh.iloc[0], 10)
        self.assertTrue(result.duplicate_conflict.iloc[0])
        self.assertFalse(result.valid_register.any())

    def test_hourly_curve_uses_one_hour_smoothing_and_no_fabricated_samples(self) -> None:
        source = registers(pd.date_range("2026-01-01", periods=6, freq="h"), [0.0, 1.0, 3.0, 4.0, 7.0, 8.0])
        native = make_native(source, 3600)
        smooth, _, rule = calibrate_events(native, pd.Timestamp("2026-01-02", tz="Asia/Shanghai"), 3600)
        self.assertEqual(rule["smoothing_window_minutes"], 60)
        self.assertEqual(len(native), 6)
        self.assertTrue(np.allclose(smooth.iloc[1:], [1, 2, 1, 3, 1]))

    def test_batch_rotation_preserves_all_sequences_and_receipt_lag(self) -> None:
        starts = pd.date_range("2026-08-27", periods=310, freq="15min", tz="Asia/Shanghai").as_unit("us")
        values = np.arange(len(starts), dtype=float) + 1
        parent = pd.DataFrame(
            {
                "interval_start": starts,
                "interval_end": starts + pd.Timedelta(minutes=15),
                "average_power_kw": values,
                "electricity_kwh": values / 4,
                "quality_flag": "measured",
                "availability_status": "message_received_time",
                "available_at": starts + pd.Timedelta(minutes=15, seconds=0.5),
                "primary_evaluation_eligible": True,
                "start_source_ref": [f"s{i}" for i in range(len(starts))],
                "end_source_ref": [f"e{i}" for i in range(len(starts))],
                "segment_id": 1,
            }
        )
        with tempfile.TemporaryDirectory() as directory, patch("tools.datasets.build_energy_full.BATCH_SIZE", 3):
            root = Path(directory)
            eligibility = []
            index = pd.DataFrame(
                full_forecasts(parent, {"site_id": "S02", "meter_id": "S02_M01"}, root, {}, eligibility)
            )
            self.assertGreater(len(index), 30)
            self.assertEqual(sum(r["exported_windows"] for r in eligibility), len(index))
            for input_path, group in index.groupby("input_path"):
                history = pd.read_csv(root / input_path / "history.csv.gz")
                future = pd.read_csv(root / group.target_path.iloc[0] / "future.csv.gz")
                predictions = pd.read_csv(root / group.target_path.iloc[0] / "baseline_predictions.csv.gz")
                self.assertLessEqual(len(group), 3)
                for row in group.itertuples():
                    block = history[history.sequence_id == row.sequence_id]
                    expected = parent.iloc[
                        row.history_parent_start_row : row.history_parent_start_row + row.history_length
                    ]
                    self.assertTrue(np.array_equal(block.average_power_kw, expected.average_power_kw))
                    self.assertEqual(len(future[future.sequence_id == row.sequence_id]), row.forecast_horizon)
                    origin = pd.Timestamp(row.prediction_origin)
                    self.assertEqual(origin - pd.Timestamp(block.interval_end.iloc[-1]), pd.Timedelta(minutes=15))
                self.assertGreater(predictions.previous_day.notna().sum(), 0)
                with gzip.open(root / input_path / "metadata.jsonl.gz", "rt") as stream:
                    metadata = [json.loads(line) for line in stream]
                self.assertEqual(len(metadata), len(group))
                self.assertTrue(all("future_parent_start_row" not in m and "target_path" not in m for m in metadata))


if __name__ == "__main__":
    unittest.main()
