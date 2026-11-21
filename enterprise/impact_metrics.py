"""Compare paired staff effort for ONE media proposal; never claim proven enterprise ROI.

These values are self-reported numeric observations. No billing, inventory write,
customer PII, model access, or extrapolation is performed here.
"""
from __future__ import annotations

import math
from typing import Any


def _minutes(value: Any, name: str, *, nonzero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a number")
    if not math.isfinite(value) or value < (0.001 if nonzero else 0) or value > 1440:
        raise ValueError(f"{name} must be finite and between {'0.001' if nonzero else '0'} and 1440")
    return float(value)


def evaluate_pair(inputs: dict[str, Any], *, synthetic_mode: bool) -> dict[str, Any]:
    """Only paired inputs are comparable. Review/rework must be included in AI effort."""
    baseline = _minutes(inputs.get("manual_minutes"), "manual_minutes", nonzero=True)
    generated = _minutes(inputs.get("generation_minutes"), "generation_minutes")
    reviewed = _minutes(inputs.get("review_minutes"), "review_minutes")
    reworked = _minutes(inputs.get("rework_minutes"), "rework_minutes")
    m_errors = inputs.get("manual_errors")
    a_errors = inputs.get("assistant_errors")
    if (m_errors is None) != (a_errors is None):
        raise ValueError("Both error counts must be provided together, or omitted")
    for name, count in (("manual_errors", m_errors), ("assistant_errors", a_errors)):
        if count is not None and (isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 100):
            raise ValueError(f"{name} must be an integer between 0 and 100")
    if not isinstance(inputs.get("comparable_scope"), bool) or not isinstance(inputs.get("evidence_attested"), bool):
        raise ValueError("Comparison and evidence checks must be explicit booleans")

    total = generated + reviewed + reworked
    delta = baseline - total
    matched = inputs["comparable_scope"]
    evidenced = inputs["evidence_attested"]
    # Attestation by the author is NOT independent verification. Never claim validated ROI.
    status = ("synthetic_illustration" if synthetic_mode else
              "single_case_self_reported" if matched and evidenced else "not_comparable")
    return {
        "status": status,
        "manual_minutes": round(baseline, 3),
        "ai_total_minutes": round(total, 3),
        "generation_minutes": round(generated, 3),
        "review_minutes": round(reviewed, 3),
        "rework_minutes": round(reworked, 3),
        "delta_minutes": round(delta, 3),
        "time_change_pct": round(delta / baseline * 100, 2),
        "error_delta": (m_errors - a_errors) if m_errors is not None else None,
        "comparable_scope": matched,
        "evidence_attested_by_user": evidenced,
        "public_synthetic": synthetic_mode,
        "roi_verified": False,
        "enterprise_savings_verified": False,
        "scope": "One self-reported comparison on this run; no extrapolation to the company",
        "next_evidence": [
            "Record same-complexity manual and AI-assisted cases with independent timestamps",
            "Include review, correction and downstream handoff time for both workflows",
            "Have the business owner check error definitions, case comparability and a multi-case sample",
            "Verify financial labor costs before any monetary ROI claim",
        ],
    }
