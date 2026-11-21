"""Pure policy, ingress and cloud HTTP boundary regressions; synthetic only."""
from __future__ import annotations
import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from enterprise.deployment_policy import validate_deployment, forbidden_cloud_request
from enterprise.migration_gates import CHECKS, review_gates
from enterprise.ingress_review import IngressRejected, inspect_export
from server import app

ROOT = Path(__file__).resolve().parents[1]
RAW = (ROOT / "data" / "inventory_template.csv").read_bytes()


def manifest(kind="inventory",classification="synthetic"):
    return {
        "kind": kind,
        "sha256": hashlib.sha256(RAW).hexdigest(),
        "classification":classification,
        "tenant":"tenant-demo",
        "purpose":"synthetic-review",
        "source_ref":"approved-export-demo",
        "data_owner_ticket":"DO-12345",
        "security_ticket":"SEC-12345",
        "retention_days":7,
        "model_export_allowed":False,
    }


@pytest.mark.parametrize("mode", ["production", "prod", "cloud_prod", ""])
def test_production_and_unknown_modes_never_start(mode):
    with pytest.raises(RuntimeError,match="PRODUCTION_DEPLOYMENT_BLOCKED"):
        validate_deployment({"COMPANYAGENT_DEPLOYMENT_MODE":mode})


def test_cloud_synthetic_starts_without_secrets_and_real_data():
    p=validate_deployment({"COMPANYAGENT_DEPLOYMENT_MODE":"cloud_synthetic","COMPANYAGENT_AUTO_SYNC":"false"})
    assert p["mode"]=="cloud_synthetic"
    assert p["real_data_permitted"] is False and p["production_ready"] is False


@pytest.mark.parametrize("unsafe", [
    {"TOKENDANCE_API_KEY":"test-key"},
    {"B1X_API_KEY":"test-key"},
    {"COMPANYAGENT_ALLOWED_DATA_HOSTS":"corp.internal"},
    {"COMPANYAGENT_SOURCE_A_TOKEN":"test"},
    {"COMPANYAGENT_AUTO_SYNC":"true"},
    {"COMPANYAGENT_REAL_DATA_ENABLED":"true"},
    {"HONGDOU_PILOT_ACCESS_TOKEN":"synthetic-only-key"},
    {"HONGDOU_PILOT_HOST":"inventory.example.org"},
])
def test_cloud_synthetic_rejects_secrets_sync_or_real_data(unsafe):
    with pytest.raises(RuntimeError,match="CLOUD_SYNTHETIC_BLOCKED"):
        validate_deployment({"COMPANYAGENT_DEPLOYMENT_MODE":"cloud_synthetic",**unsafe})


def test_local_endpoint_policy_does_not_break_existing_demo():
    assert not forbidden_cloud_request("/api/demo","GET",{"COMPANYAGENT_DEPLOYMENT_MODE":"local"})


@pytest.mark.parametrize("path,verb", [
    ("/api/demo","GET"),("/api/import","POST"),
    ("/enterprise/api/datasets/upload","POST"),
    ("/enterprise/api/sources","POST"),
    ("/enterprise/api/sources/poll-folder","POST"),
    ("/enterprise/api/sources/5/sync","POST"),
    ("/enterprise/api/data/bridge/reconcile","POST")
])
def test_cloud_http_boundary_denies_unprotected_and_ingest(path,verb,monkeypatch):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","cloud_synthetic")
    with TestClient(app) as client:
        r=client.request(verb,path)
    assert r.status_code==403


def test_cloud_readiness_is_safe(monkeypatch):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","cloud_synthetic")
    with TestClient(app) as client:
        r=client.get("/healthz")
    assert r.status_code==200
    assert r.json()=={"ok":True,"mode":"cloud_synthetic","production_ready":False}


def test_offline_ingress_synthetic_review_never_writes_or_calls_model():
    x=inspect_export(RAW,"inventory_template.csv",manifest())
    assert x["record_count"]>=1
    assert x["status"]=="synthetic_schema_checked"
    assert x["database_written"] is False and x["data_transferred"] is False
    assert x["remote_model_called"] is False and not x["enterprise_ingress_approved"]


def test_internal_metadata_requires_out_of_band_review():
    x=inspect_export(RAW,"inventory_template.csv",manifest(classification="internal"))
    assert x["status"]=="manual_owner_and_security_review_required"
    assert not x["enterprise_ingress_approved"]


@pytest.mark.parametrize("patch", [
    {"sha256":"0"*64},
    {"model_export_allowed":True},
    {"retention_days":31},
    {"retention_days":True},
    {"security_ticket":"abc"},
    {"classification":"restricted"},
    {"kind":"exe"},
])
def test_ingress_fail_closed_on_bad_provenance_or_restricted(patch):
    m=manifest()
    m.update(patch)
    with pytest.raises(IngressRejected):
        inspect_export(RAW,"inventory_template.csv",m)


def test_ingress_rejects_missing_approval_references():
    m=manifest()
    del m["data_owner_ticket"]
    with pytest.raises(IngressRejected):
        inspect_export(RAW,"inventory_template.csv",m)


@pytest.mark.parametrize("stage",list(CHECKS))
def test_migration_gate_missing_evidence_blocks_every_stage(stage):
    x=review_gates(stage,{})
    assert x["review_state"]=="blocked" and x["verified_count"]==0
    assert not x["deployment_permitted"] and not x["production_cutover_permitted"]


def test_all_claimed_green_still_requires_external_manual_authorization():
    stage="production_migration"
    data={name:{"status":"verified","evidence_ref":"TICKET-2026-12345","reviewer":"review-owner"} for name in CHECKS[stage]}
    x=review_gates(stage,data)
    assert x["review_state"]=="ready_for_manual_go_no_go"
    assert x["verified_count"]==len(CHECKS[stage])
    assert x["approval_proven"] is False
    assert x["deployment_permitted"] is False and x["production_cutover_permitted"] is False


def test_checkmark_without_citable_ref_is_not_verified():
    x=review_gates("cloud_synthetic",{"source_ci":{"status":"verified"}})
    assert "source_ci" in x["pending"]
    assert "source_ci" not in x["verified"]
