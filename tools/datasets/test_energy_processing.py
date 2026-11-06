# ruff: noqa: PLR2004
"""Focused checks for gaps, timing assumptions, aggregation and train-only rules."""

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tools.datasets.build_energy_datasets import (
    calibrate_events,
    get_split,
    make_forecast_cases,
    make_forecast_series,
    make_native,
)


def registers(times: Any, values: Any, valid: Any = None) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "observed_at": pd.to_datetime(times).tz_localize("Asia/Shanghai"),
            "cumulative_energy_kwh": values,
            "valid_register": valid if valid is not None else [True] * len(values),
            "source_ref": [f"r{i}" for i in range(len(values))],
            "available_at": pd.Series(pd.NaT, index=range(len(values)), dtype="datetime64[ns, Asia/Shanghai]"),
            "availability_status": "ingestion_time_unknown",
        }
    )


class EnergyProcessingChecks(unittest.TestCase):
    def test_gap_and_reset_are_unknown_not_zero_or_spread(self) -> None:
        r = registers(
            ["2026-01-01 00:00", "2026-01-01 00:05", "2026-01-01 01:05", "2026-01-01 01:10"], [10.0, 11.0, 20.0, 1.0]
        )
        n = make_native(r, 300)
        self.assertEqual(n.electricity_kwh.iloc[1], 1)
        self.assertTrue(n.electricity_kwh.iloc[[0, 2, 3]].isna().all())
        self.assertEqual(n.quality_flag.iloc[2], "data_gap_or_cadence_change")
        self.assertEqual(n.quality_flag.iloc[3], "register_decrease_review")

    def test_midnight_alignment_retains_raw_times_and_masks_both_targets(self) -> None:
        r = registers(
            ["2026-01-01 23:30", "2026-01-01 23:45", "2026-01-01 23:59", "2026-01-02 00:15", "2026-01-02 00:30"],
            [10.0, 11.0, 12.0, 13.0, 14.0],
        )
        n = make_native(r, 900)
        f = make_forecast_series(r, n, "S01")
        self.assertEqual(str(r.observed_at.iloc[2]), "2026-01-01 23:59:00+08:00")
        self.assertEqual(n.duration_seconds.iloc[2], 840)
        self.assertEqual(n.duration_seconds.iloc[3], 960)
        self.assertEqual(f.primary_evaluation_eligible.tolist(), [True, False, False, True])
        self.assertTrue((f.electricity_kwh == 1).all())

    def test_mqtt_aggregation_cannot_bridge_invalid_endpoint_or_second_drift(self) -> None:
        times = pd.date_range("2026-01-01 00:00", periods=10, freq="5min")
        r = registers(times, np.arange(10.0), [True, True, True, True, False, True, True, True, True, True])
        n = make_native(r, 300)
        f = make_forecast_series(r, n, "S02")
        self.assertEqual(len(f), 2)
        self.assertTrue((f.electricity_kwh == 3).all())
        self.assertEqual(f.segment_id.nunique(), 2)
        r2 = registers(
            ["2026-01-01 00:00:00", "2026-01-01 00:05:00", "2026-01-01 00:10:01", "2026-01-01 00:15:01"],
            [0.0, 1.0, 2.0, 3.0],
        )
        self.assertTrue(make_forecast_series(r2, make_native(r2, 300), "S02").empty)

    def test_split_rejects_targets_crossing_boundary(self) -> None:
        cuts = [pd.Timestamp("2026-01-02", tz="Asia/Shanghai"), pd.Timestamp("2026-01-03", tz="Asia/Shanghai")]
        self.assertEqual(get_split(cuts[0] - pd.Timedelta(hours=1), cuts[0], cuts), "train")
        self.assertEqual(get_split(cuts[0], cuts[1], cuts), "validation")
        self.assertIsNone(get_split(cuts[0] - pd.Timedelta(minutes=15), cuts[0] + pd.Timedelta(minutes=15), cuts))

    def test_future_load_does_not_change_calibration(self) -> None:
        r = registers(pd.date_range("2026-01-01", periods=300, freq="5min"), np.arange(300.0) * 0.01)
        n = make_native(r, 300)
        cut = pd.Timestamp("2026-01-01 12:00", tz="Asia/Shanghai")
        _, _, before = calibrate_events(n, cut, 300)
        changed = n.copy()
        changed.loc[changed.interval_end > cut, "electricity_kwh"] = 9999
        _, _, after = calibrate_events(changed, cut, 300)
        self.assertEqual(before, after)
        self.assertFalse(before["activity_timing_usable_under_pilot_rule"])

    def test_mqtt_receipt_delay_yields_lagged_forecast_inputs(self) -> None:
        starts = pd.date_range("2026-01-01", periods=300, freq="15min", tz="Asia/Shanghai")
        series = pd.DataFrame(
            {
                "interval_start": starts,
                "interval_end": starts + pd.Timedelta(minutes=15),
                "average_power_kw": np.arange(300.0) + 1,
                "electricity_kwh": (np.arange(300.0) + 1) / 4,
                "available_at": starts + pd.Timedelta(minutes=15, seconds=0.5),
                "availability_status": "message_received_time",
                "quality_flag": "measured",
                "primary_evaluation_eligible": True,
                "segment_id": 1,
                "start_source_ref": [f"s{i}" for i in range(300)],
                "end_source_ref": [f"e{i}" for i in range(300)],
            }
        )
        cuts = [pd.Timestamp("2026-01-03", tz="Asia/Shanghai"), pd.Timestamp("2026-01-04", tz="Asia/Shanghai")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = make_forecast_cases(series, {"meter_id": "S02_M01", "site_id": "S02"}, cuts, root, 1, [], [])
            self.assertGreater(len(index), 0)
            for record in index:
                meta = json.loads((root / record["input_path"] / "metadata.json").read_text())
                history = pd.read_csv(root / record["input_path"] / "history.csv")
                origin = pd.Timestamp(meta["prediction_origin"])
                self.assertEqual(meta["observation_lag_steps"], 1)
                self.assertEqual(origin - pd.Timestamp(history.interval_end.iloc[-1]), pd.Timedelta(minutes=15))


if __name__ == "__main__":
    unittest.main()
