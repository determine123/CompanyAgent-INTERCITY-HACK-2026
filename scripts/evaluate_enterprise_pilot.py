"""Local-only anonymous pilot workload analysis; never upload samples to public demo."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
# Direct execution with "python scripts/..." excludes the repository root by default.
# Add only the known, trusted current project root; never load outside content.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enterprise.deployment_policy import deployment_mode
from enterprise.evidence_benchmark import evaluate_cohort, CohortInvalid


def main(argv: list[str]) -> int:
    if deployment_mode() != "local" or len(argv) != 2:
        print("Local-only evaluation: provide exactly one private JSON file path", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        if not path.is_file() or path.stat().st_size > 250000:
            raise CohortInvalid("Trial file missing or exceeds 250 KB")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"trials"}:
            raise CohortInvalid("Expected a JSON object with only trials")
        result = evaluate_cohort(data["trials"])
    except (OSError, UnicodeError, ValueError, CohortInvalid):
        print("Invalid paired-case dataset; raw contents not displayed", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
