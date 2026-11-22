"""Pseudo-anonymous paired-workload analysis; observational, never proof of ROI."""
from __future__ import annotations
import math
import pytest
from fastapi.testclient import TestClient
from enterprise.evidence_benchmark import evaluate_cohort,CohortInvalid
from enterprise.production_readiness import production_readiness
from server import app


def cases(n=12):
    return [{
        "case_id":f"proposal_{i:03d}",
        "manual_minutes":100+i*5,
        "generation_minutes":20,
        "review_minutes":20,
        "rework_minutes":5,
        "manual_errors":2,
        "assisted_errors":1,
        "comparable_scope":True,
        "manual_evidence_sha256":f"{i+100:064x}",
        "assisted_evidence_sha256":f"{i+200:064x}",
        "reviewer_ref":"audit_team_01",
    } for i in range(n)]


def test_cohort_has_repeatable_ci_and_no_false_verified_roi():
    a=evaluate_cohort(cases())
    b=evaluate_cohort(cases())
    assert a==b
    assert a["case_count"]==12
    assert a["status"]=="awaiting_independent_evidence_audit"
    assert a["observed_unverified_time_change_pct"]>0
    assert len(a["bootstrap_ci95_pct"])==2
    assert a["bootstrap_ci95_pct"][0]<=a["observed_unverified_time_change_pct"]<=a["bootstrap_ci95_pct"][1]
    assert a["manual_total_minutes"]>a["assisted_total_minutes_including_review_rework"]
    assert not a["independent_evidence_verified"]
    assert not a["enterprise_savings_verified"]
    assert not a["monetary_roi_verified"]
    assert not a["commercial_claim_permitted"]
    assert not a["trial_data_persisted"]
    assert "proposal_000" not in str(a)


def test_small_sample_and_negative_outcome_never_become_claims():
    short=evaluate_cohort(cases(2))
    assert short["status"]=="insufficient_sample"
    assert short["bootstrap_ci95_pct"] is None
    assert not short["commercial_claim_permitted"]
    slower=cases(10)
    for x in slower:
        x["generation_minutes"]=300
    report=evaluate_cohort(slower)
    assert report["observed_unverified_time_change_pct"]<0
    assert report["commercial_claim_permitted"] is False
    assert evaluate_cohort(cases(10),synthetic=True)["status"]=="synthetic_only"


@pytest.mark.parametrize("change",[
    lambda a: a[1].update(case_id=a[0]["case_id"]),
    lambda a: a[0].update(manual_minutes=0),
    lambda a: a[0].update(manual_minutes=float("nan")),
    lambda a: a[0].update(generation_minutes=-5),
    lambda a: a[0].update(rework_minutes=1e300),
    lambda a: a[0].update(assisted_errors=True),
    lambda a: a[0].update(manual_evidence_sha256=""),
    lambda a: a[0].update(comparable_scope=False),
    lambda a: a[0].update(reviewer_ref="bad/email@corp.com"),
])
def test_incomparable_or_unverified_cases_fail_closed(change):
    sample=cases(10)
    change(sample)
    with pytest.raises(CohortInvalid):
        evaluate_cohort(sample)


def test_production_readiness_lists_actual_blockers_and_cannot_self_certify():
    r=production_readiness(deployment_mode="cloud_synthetic")
    assert r["status"]=="blocked_not_production_ready"
    assert r["blocking_count"]==9
    assert not r["production_deployment_permitted"]
    assert not r["real_inventory_verified"]
    assert not r["validated_cost_reduction_claim"]
    assert all(not x["passed"] for x in r["checks"])


def test_admin_endpoints_are_authenticated_local_only_and_never_persist_cases(monkeypatch):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","local")
    with TestClient(app) as c:
        assert c.get("/enterprise/api/pilot/readiness").status_code==401
        assert c.post("/enterprise/api/pilot/paired-evaluation",json={"trials":cases(10)}).status_code==401
        login=c.post("/enterprise/api/auth/login",json={
            "username":"admin","password":"CI-generated-isolated-password-ONLY"})
        assert login.status_code==200,login.text
        c.headers["X-CSRF-Token"]=login.json()["csrf"]
        status=c.get("/enterprise/api/pilot/readiness")
        assert status.status_code==200 and not status.json()["production_deployment_permitted"]
        result=c.post("/enterprise/api/pilot/paired-evaluation",json={"trials":cases(10)})
        assert result.status_code==200,result.text
        assert result.json()["case_count"]==10
        assert result.json()["trial_data_persisted"] is False
        del c.headers["X-CSRF-Token"]
        assert c.post("/enterprise/api/pilot/paired-evaluation",json={"trials":cases(10)}).status_code==403
        c.headers["X-CSRF-Token"]=login.json()["csrf"]
        monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","cloud_synthetic")
        assert c.post("/enterprise/api/pilot/paired-evaluation",json={"trials":cases(10)}).status_code==403
