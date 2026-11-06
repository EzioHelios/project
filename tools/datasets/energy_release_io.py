# ruff: noqa: T201
"""Read a dataset sequence using only the Python standard library."""

import argparse
import csv
import gzip
import json
from itertools import islice
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read plain or gzip CSV records without converting their numeric values."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_block(path: Path, position: int, length: int, sequence_id: str) -> list[dict[str, str]]:
    """Read a sequence block from a batch and verify its identity and steps."""
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        rows = list(islice(csv.DictReader(stream), position * length, (position + 1) * length))
    if len(rows) != length or any(
        row["sequence_id"] != sequence_id or int(row["step"]) != step for step, row in enumerate(rows)
    ):
        msg = f"Sequence block mismatch: {path}, {sequence_id}"
        raise ValueError(msg)
    return rows


def read_sequence(
    root: Path | str, sequence_id: str, *, with_targets: bool = False, index_row: dict[str, str] | None = None
) -> dict[str, Any]:
    """Read one indexed event or forecasting sequence.

    Numeric CSV values remain strings; callers can explicitly convert selected columns.
    """
    root = Path(root)
    dataset = json.loads((root / "dataset.json").read_text(encoding="utf-8"))
    if with_targets and dataset["edition"] == "inputs_only":
        msg = "This edition contains inputs only."
        raise ValueError(msg)
    if index_row is None:
        index_path = root / ("sequence_index.csv" if dataset["task"] == "energy_events" else "sequence_index.csv.gz")
        opener = gzip.open if index_path.suffix == ".gz" else open
        with opener(index_path, "rt", encoding="utf-8-sig", newline="") as stream:
            index_row = next((row for row in csv.DictReader(stream) if row["sequence_id"] == sequence_id), None)
    if index_row is None or index_row["sequence_id"] != sequence_id:
        raise KeyError(sequence_id)
    directory = root / index_row["input_path"]
    if dataset["task"] == "energy_events":
        result = {
            "observations": read_csv(directory / "observations.csv.gz"),
            "metadata": json.loads((directory / "metadata.json").read_text(encoding="utf-8")),
        }
        if len(result["observations"]) != int(index_row["observations"]):
            msg = f"Observation count mismatch: {sequence_id}"
            raise ValueError(msg)
        if with_targets:
            annotations = root / index_row["label_path"]
            result["state_labels"] = read_csv(annotations / "state_labels.csv.gz")
            result["annotations"] = json.loads((annotations / "annotations.json").read_text(encoding="utf-8"))
        return result
    position = int(index_row["sequence_position_in_batch"])
    result = {
        "history": read_block(directory / "history.csv.gz", position, int(index_row["history_length"]), sequence_id),
        "future_covariates": read_block(
            directory / "future_covariates.csv.gz", position, int(index_row["forecast_horizon"]), sequence_id
        ),
    }
    with gzip.open(directory / "metadata.jsonl.gz", "rt", encoding="utf-8") as stream:
        result["metadata"] = json.loads(next(islice(stream, position, position + 1)))
    if result["metadata"]["sequence_id"] != sequence_id:
        msg = f"Metadata identity mismatch: {sequence_id}"
        raise ValueError(msg)
    if with_targets:
        result["future"] = read_block(
            root / index_row["target_path"] / "future.csv.gz", position, int(index_row["forecast_horizon"]), sequence_id
        )
    return result


def main() -> None:
    """Read one sequence and optionally export it as individual files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("sequence_id")
    parser.add_argument("--with-targets", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = read_sequence(args.root, args.sequence_id, with_targets=args.with_targets)
    print(json.dumps(result["metadata"], ensure_ascii=False, indent=2))
    for name, value in result.items():
        if isinstance(value, list):
            print(f"{name}: {len(value)} rows")
        if args.output:
            args.output.mkdir(parents=True, exist_ok=True)
            if isinstance(value, list) and value:
                with (args.output / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(value[0]))
                    writer.writeheader()
                    writer.writerows(value)
            elif isinstance(value, dict):
                (args.output / f"{name}.json").write_text(
                    json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )


if __name__ == "__main__":
    main()
