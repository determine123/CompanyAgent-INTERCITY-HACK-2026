"""Paired case-study analysis with zero invented measured ROI.

This can compute an *observed, unaudited* time difference from actual
pseudonymous paired observations. Independent source verification and
commercial cost accounting are external approvals and cannot be self-declared.
"""
from __future__ import annotations

import math
import random
import re
from typing import Any

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{3,63}$")
_SHA = re.compile(r"^[a-fA-F0-9]{64}$")


class CohortInvalid(ValueError):
    pass


def _minutes(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1440:
        raise CohortInvalid("All durations must be finite numeric minutes between 0 and 1440")
    return float(value)


def _pct(manual: float, assisted: float) -> float:
    return round(100 * (manual - assisted) / manual, 2)


def evaluate_cohort(trials: list[dict], *, synthetic: bool = False) -> dict:
    if not isinstance(trials, list) or not 1 <= len(trials) <= 100:
        raise CohortInvalid("Expected 1–100 paired cases")
    seen, pairs = set(), []
    for row in trials:
        if not isinstance(row, dict) or set(row) != {
            "case_id", "manual_minutes", "generation_minutes", "review_minutes",
            "rework_minutes", "manual_errors", "assisted_errors", "comparable_scope",
            "manual_evidence_sha256", "assisted_evidence_sha256", "reviewer_ref",
        }:
            raise CohortInvalid("Case fields are incomplete or unapproved")
        case_id = row["case_id"]
        if not isinstance(case_id, str) or not _ID.fullmatch(case_id) or case_id in seen:
            raise CohortInvalid("Case identifier missing, duplicated or unsafe")
        seen.add(case_id)
        manual = _minutes(row["manual_minutes"])
        if manual <= 0:
            raise CohortInvalid("Manual baseline must be positive")
        assisted = sum(_minutes(row[key]) for key in (
            "generation_minutes", "review_minutes", "rework_minutes"))
        if type(row["comparable_scope"]) is not bool or row["comparable_scope"] is not True:
            raise CohortInvalid("Each pair must cover comparable work scope")
        for key in ("manual_errors", "assisted_errors"):
            value = row[key]
            if type(value) is not int or not 0 <= value <= 100:
                raise CohortInvalid("Error counts must be bounded integers")
        for key in ("manual_evidence_sha256", "assisted_evidence_sha256"):
            value = row[key]
            if not isinstance(value, str) or not _SHA.fullmatch(value):
                raise CohortInvalid("Missing or invalid evidence fingerprint")
        reviewer = row["reviewer_ref"]
        if not isinstance(reviewer, str) or not _ID.fullmatch(reviewer):
            raise CohortInvalid("An independently accountable reviewer reference is required")
        if reviewer == case_id:
            raise CohortInvalid("Reviewer and case identifier must be distinct")
        pairs.append((manual, assisted, row["manual_errors"], row["assisted_errors"]))
    n = len(pairs)
    total_manual = sum(p[0] for p in pairs)
    total_assisted = sum(p[1] for p in pairs)
    observed = _pct(total_manual, total_assisted)
    ci = None
    if n >= 10:
        randomizer = random.Random(20261122)
        bootstrap = []
        for _ in range(1000):
            sample = [pairs[randomizer.randrange(n)] for _ in range(n)]
            m, a = sum(p[0] for p in sample), sum(p[1] for p in sample)
            bootstrap.append(_pct(m, a))
        bootstrap.sort()
        ci = [bootstrap[24], bootstrap[975]]
    return {
        "status": ("synthetic_only" if synthetic else
                   "awaiting_independent_evidence_audit" if n >= 10 else "insufficient_sample"),
        "case_count": n,
        "manual_total_minutes": round(total_manual, 2),
        "assisted_total_minutes_including_review_rework": round(total_assisted, 2),
        "observed_unverified_time_change_pct": observed,
        "bootstrap_ci95_pct": ci,
        "manual_error_total": sum(p[2] for p in pairs),
        "assisted_error_total": sum(p[3] for p in pairs),
        "sample_adequacy_threshold": 10,
        "independent_evidence_verified": False,
        "monetary_roi_verified": False,
        "enterprise_savings_verified": False,
        "commercial_claim_permitted": False,
        "trial_data_persisted": False,
        "reported_scope": "Pseudonymous paired proposal cases only; no causal attribution or generalization",
        "next_audit": [
            "An independent reviewer checks original signed timestamps and case-equivalence",
            "Compare acceptance quality, errors and downstream rework; stratify by proposal complexity",
            "Pre-register an adequately powered prospective control/assisted trial",
            "Verify labor rates, rollout costs and control of confounders before monetary ROI claims",
        ],
    }
