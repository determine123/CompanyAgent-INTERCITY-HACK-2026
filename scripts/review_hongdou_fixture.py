"""Offline supplier mapping review. Input stays within the operator's environment."""
import argparse
import json
from pathlib import Path

from enterprise.supplier_schema_review import inspect_candidate_mapping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("bus", "metro"))
    parser.add_argument("fixture", type=Path)
    parser.add_argument("mapping", type=Path)
    args = parser.parse_args()
    try:
        values = []
        for path in (args.fixture, args.mapping):
            with path.open("rb") as handle:
                raw = handle.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError
            values.append(json.loads(raw))
        report = inspect_candidate_mapping(*values, kind=args.kind)
        if not report["fixture_rows_inspected"]:
            raise ValueError
    except (OSError, ValueError, RecursionError):
        print("Review blocked: missing, empty or incompatible evidence")
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
