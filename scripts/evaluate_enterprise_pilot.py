"""Local-only anonymous pilot workload analysis; never upload samples to public demo."""
from __future__ import annotations
import json
import sys
from pathlib import Path
# Direct execution with "python scripts/..." excludes the repository root by default.
# Add only the known, trusted current project root; never load outside content.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enterprise.deployment_policy import deployment_mode
from enterprise.evidence_benchmark import evaluate_cohort, CohortInvalid


def summarize_costs(trials: list[dict], ledger: dict) -> dict:
    """Aggregate matched case costs in integer RMB fen, including allocated overhead."""
    if not isinstance(ledger, dict) or set(ledger) != {row["case_id"] for row in trials}:
        raise CohortInvalid("Ledger must cover exactly the evaluated cases")
    fields = {"manual_labor", "manual_other", "assisted_labor", "model",
              "infrastructure", "rollout_allocation", "assisted_other"}
    manual = assisted = 0
    for costs in ledger.values():
        if not isinstance(costs, dict) or set(costs) != fields:
            raise CohortInvalid("Incomplete cost breakdown")
        if any(type(value) is not int or not 0 <= value <= 10**12 for value in costs.values()):
            raise CohortInvalid("Costs must be bounded nonnegative integer fen")
        baseline = costs["manual_labor"] + costs["manual_other"]
        manual += baseline
        assisted += sum(costs.values()) - baseline
    if not manual:
        raise CohortInvalid("Positive baseline required for cost comparison")
    return {"manual_fen": manual, "assisted_fen": assisted, "difference_fen": manual-assisted,
            "observed_unverified_cost_change_pct": round(100*(manual-assisted)/manual, 2)}


def main(argv: list[str]) -> int:
    if deployment_mode() != "local" or len(argv) != 2:
        print("Local-only evaluation: provide exactly one private JSON file path", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        if not path.is_file() or path.stat().st_size > 250000:
            raise CohortInvalid("Trial file missing or exceeds 250 KB")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) not in ({"trials"}, {"trials", "costs_cny_fen"}):
            raise CohortInvalid("Expected paired trials and an optional cost ledger")
        result = evaluate_cohort(data["trials"])
        if "costs_cny_fen" in data:
            result["observed_costs"] = summarize_costs(data["trials"], data["costs_cny_fen"])
    except (OSError, UnicodeError, ValueError, CohortInvalid):
        print("Invalid paired-case dataset; raw contents not displayed", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
