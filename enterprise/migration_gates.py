"""Evidence-first migration gates. Produces a review report; never deploys anything.

Attestations are self-reported metadata, NOT cryptographic signatures or
approval artifacts. Even all-green reports require out-of-band approval.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

CHECKS = {
    "cloud_synthetic": (
        "source_ci", "container_smoke", "legacy_api_denied",
        "loopback_only", "no_enterprise_data", "rollback_runbook",
    ),
    "enterprise_pilot": (
        "data_owner_consent", "business_scope", "classification_review",
        "connector_contract", "tenant_rbac", "secrets_rotation",
        "egress_allowlist", "audit_retention", "deletion_plan",
        "negative_tests", "approval_ticket",
    ),
    "production_migration": (
        "enterprise_pilot_accepted", "oidc_sso", "tenant_isolation",
        "kms_secret_manager", "private_vpc", "mcp_tool_pdp_pep",
        "audit_immutability", "performance_e2e", "backup_restore_drill",
        "rollback_drill", "mentor_approval", "data_owner_approval",
        "security_approval", "sre_approval",
    ),
}

def review_gates(stage: str, attestations: dict | None = None) -> dict:
    if stage not in CHECKS:
        raise ValueError("unknown release stage")
    if not isinstance(attestations, dict):
        raise ValueError("attestations must be a mapping")
    missing, pending, failed, verified = [], [], [], []
    for name in CHECKS[stage]:
        entry = attestations.get(name)
        if not isinstance(entry, dict):
            missing.append(name)
            continue
        status = entry.get("status")
        if status == "verified":
            # A plain checkmark is not evidence; require attributable, bounded metadata.
            reference = entry.get("evidence_ref")
            approver = entry.get("reviewer")
            if not isinstance(reference, str) or not (5 <= len(reference) <= 240):
                pending.append(name)
            elif not isinstance(approver, str) or not (2 <= len(approver) <= 80):
                pending.append(name)
            else:
                verified.append(name)
        elif status == "failed":
            failed.append(name)
        else:
            pending.append(name)
    ready = len(verified) == len(CHECKS[stage])
    return {
        "stage": stage,
        "review_state": "ready_for_manual_go_no_go" if ready else "blocked",
        "verified": verified, "pending": pending, "missing": missing, "failed": failed,
        "required_count": len(CHECKS[stage]), "verified_count": len(verified),
        "approval_proven": False,
        "deployment_permitted": False,
        "production_cutover_permitted": False,
        "limitations": [
            "Attestations are untrusted until checked in the enterprise approval system",
            "Manual data-owner, security, and production change approvals cannot be inferred from JSON",
            "Neither model tool-call success nor CI success permits production cutover",
        ],
    }

def review_manifest(path: Path) -> dict:
    raw = Path(path).read_bytes()
    if len(raw) > 100_000:
        raise ValueError("gate manifest too large")
    data = json.loads(raw.decode("utf-8"))
    if set(data) != {"stage", "attestations"}:
        raise ValueError("manifest must contain only stage and attestations")
    return review_gates(data["stage"], data["attestations"])
