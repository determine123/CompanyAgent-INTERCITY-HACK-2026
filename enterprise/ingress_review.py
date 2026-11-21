"""Offline review of an enterprise-provided export before ANY import or cloud upload.

A manifest alone is not an authorization. Real enterprise data is never
ingested into CompanyAgent by this module; no network or model is called.
"""
from __future__ import annotations
import hashlib
import re
from datetime import date
from pathlib import Path

from .dataflows import MAX_BYTES, parse_bytes

ALLOWED_KINDS = frozenset({"inventory", "coverage", "pricing"})
ALLOWED_CLASSIFICATION = frozenset({"synthetic", "public", "internal", "restricted"})
REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{4,119}$")

class IngressRejected(ValueError):
    pass

def inspect_export(raw: bytes, filename: str, manifest: dict) -> dict:
    """Return counts and scope flags only; never write source data to database."""
    if not isinstance(manifest, dict) or len(raw) > MAX_BYTES:
        raise IngressRejected("manifest invalid or data exceeds size limit")
    mandatory = {"kind", "sha256", "classification", "tenant", "purpose",
                 "source_ref", "data_owner_ticket", "security_ticket",
                 "retention_days", "model_export_allowed"}
    if not mandatory.issubset(manifest):
        raise IngressRejected("missing required provenance, classification, or review metadata")
    kind = manifest["kind"]
    classification = manifest["classification"]
    if kind not in ALLOWED_KINDS or classification not in ALLOWED_CLASSIFICATION:
        raise IngressRejected("unsupported export kind or classification")
    if manifest.get("model_export_allowed") is not False:
        raise IngressRejected("external model export must be explicitly forbidden")
    if type(manifest["retention_days"]) is not int or not 1 <= manifest["retention_days"] <= 30:
        raise IngressRejected("retention must be 1..30 days for offline review")
    for field in ("tenant", "purpose", "source_ref", "data_owner_ticket", "security_ticket"):
        v = manifest[field]
        if not isinstance(v, str) or not REFERENCE.fullmatch(v):
            raise IngressRejected("review fields must use opaque, non-secret references")
    given = manifest["sha256"]
    if not isinstance(given, str) or not re.fullmatch(r"[0-9a-f]{64}",given):
        raise IngressRejected("expected SHA-256 missing or invalid")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != given:
        raise IngressRejected("source checksum mismatch")
    if classification == "restricted":
        raise IngressRejected("restricted enterprise export cannot be reviewed in this prototype")
    if classification in ("public", "internal"):
        # The ticket strings are claims, not proof. No real import or cloud transfer is allowed.
        stage = "manual_owner_and_security_review_required"
    else:
        stage = "synthetic_schema_checked"
    try:
        parsed = parse_bytes(kind,raw,filename)
    except Exception as exc:
        raise IngressRejected("source schema invalid for selected kind") from None
    return {
        "status": stage,
        "dataset_kind": kind,
        "classification": classification,
        "record_count": len(parsed["records"]),
        "sha256": actual,
        "tenant_ref": manifest["tenant"],
        "source_ref": manifest["source_ref"],
        "data_transferred": False,
        "database_written": False,
        "remote_model_called": False,
        "enterprise_ingress_approved": False,
        "next_action": "verify owner/security tickets independently and perform an isolated enterprise pilot",
    }
