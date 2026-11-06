# ruff: noqa: T201
"""Verify every published file against the dataset SHA256 inventory."""

import argparse
import csv
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    """Calculate the SHA256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(root: Path) -> int:
    """Verify file hashes, byte counts, and complete inventory coverage."""
    with (root / "checksums.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = {row["path"] for row in rows}
    actual = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()} - {"checksums.csv"}
    if expected != actual or len(expected) != len(rows):
        msg = "Inventory coverage mismatch."
        raise ValueError(msg)
    for row in rows:
        path = root / row["path"]
        if path.stat().st_size != int(row["bytes"]) or sha256(path) != row["sha256"]:
            msg = f"Checksum mismatch: {row['path']}"
            raise ValueError(msg)
    return len(rows)


def main() -> None:
    """Verify the package root supplied on the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    print(f"Verified {verify(args.root)} files.")


if __name__ == "__main__":
    main()
