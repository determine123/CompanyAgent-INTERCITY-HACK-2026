"""v2.4: judge-only scenario diff and read-only enterprise handoff regressions."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from server import app
from enterprise.judge_workflow import workflow_preview


def test_scenario_comparison_is_calculated_from_actual_allocations():
    r = workflow_preview(200, "both", 100, "both", "creative_revision")
    assert r["simulation_only"] and not r["real_api_accessed"]
    assert not r["changed_enterprise_records"] and not r["production_ready"]
    assert r["current"]["budget_wan"] == 200
    assert r["previous"]["budget_wan"] == 100
    assert r["impact"]["spent_delta_wan"] == round(
        r["current"]["spent_wan"] - r["previous"]["spent_wan"], 2
    )
    assert r["impact"]["net_units"] == (
        r["impact"]["added_units"] - r["impact"]["removed_units"]
    )
    assert r["impact"]["net_units"] == (
        r["current"]["unit_count"] - r["previous"]["unit_count"]
    )
    assert len(r["scenario_summary"]) == 3
    assert [x["budget_wan"] for x in r["scenario_summary"]] == [100, 200, 500]
    assert all(x["spent_wan"] <= x["budget_wan"] for x in r["scenario_summary"])
    assert r["data_lineage"]["status"] == "synthetic_and_unverified"
    assert len(r["data_lineage"]["sha256_prefix"]) == 16


@pytest.mark.parametrize("budgets", [(100, 200), (200, 500), (500, 100), (200, 200)])
@pytest.mark.parametrize("media", [("both", "metro"), ("bus", "both"), ("metro", "bus")])
def test_deltas_reconcile_for_all_media_budget_combinations(budgets, media):
    r = workflow_preview(budgets[1], media[1], budgets[0], media[0], "vehicle_reassignment")
    assert r["impact"]["net_units"] == r["current"]["unit_count"] - r["previous"]["unit_count"]
    assert r["impact"]["added_units"] >= 0
    assert r["impact"]["removed_units"] >= 0
    assert r["impact"]["changed_media_count"] >= len(r["impact"]["changed_rows"])
    assert r["handoff"]["customer_notified"] is False
    assert r["handoff"]["inventory_reserved"] is False
    assert r["handoff"]["real_system_mutated"] is False


def test_handoff_has_owners_dependencies_and_never_writes():
    r = workflow_preview(500, "bus", 100, "metro", "weather_monitoring")
    stages = r["handoff"]["dependency_steps"]
    assert stages and stages[0]["depends_on"] == []
    assert all(x["owner"] and x["title"] and x["status"] == "requires_human_confirmation" for x in stages)
    assert [x["order"] for x in stages] == list(range(1, len(stages) + 1))
    assert all(x["depends_on"] == [stages[i-1]["id"]] for i, x in enumerate(stages) if i > 0)
    assert "不构成正式变更承诺" in r["handoff"]["customer_notice_draft"]
    assert r["skill_improvement"]["human_approval_required"]
    assert not r["skill_improvement"]["auto_executed"]
    assert r["skill_improvement"]["status"] == "suggested_not_installed"


def test_quality_checks_never_pretend_real_booking():
    r = workflow_preview(200, "both", 100, "both", "creative_revision")
    statuses = {x["id"]: x["status"] for x in r["checks"]}
    assert len(statuses) == 9
    assert r["not_official_rubric"]
    assert statuses["industry_scope"] == "evidence_present"
    assert statuses["source_fingerprint"] == "evidence_present"
    assert statuses["scenario_recalculation"] == "evidence_present"
    assert all(statuses[k] == "needs_review" for k in
               ("campaign_brief", "coverage_evidence", "future_inventory", "formal_quote", "human_approval"))


@pytest.mark.parametrize("params", [
    (201, "both", 100, "both", "creative_revision"),
    (200, "both", 101, "both", "creative_revision"),
    (200.0, "both", 100, "both", "creative_revision"),
    (200, "both", 100.0, "both", "creative_revision"),
    (200, "other", 100, "both", "creative_revision"),
    (200, "both", 100, "other", "creative_revision"),
    (200, "both", 100, "both", "unrestricted_tool"),
])
def test_server_logic_rejects_unapproved_inputs(params):
    with pytest.raises(ValueError):
        workflow_preview(*params)


def test_judge_workflow_unauthenticated_but_enterprise_still_protected(monkeypatch):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE", "cloud_synthetic")
    with TestClient(app) as c:
        r = c.get("/judge/api/workflow?budget_wan=200&medium=both&prior_budget_wan=100&prior_medium=both&change_type=creative_revision")
        assert r.status_code == 200, r.text
        report = r.json()
        assert report["real_api_accessed"] is False
        assert report["checks_with_evidence"] < len(report["checks"])
        assert c.post("/judge/api/workflow").status_code == 405
        assert c.get("/enterprise/api/insights").status_code == 401
        assert c.get("/api/demo").status_code == 403


@pytest.mark.parametrize("query", [
    "budget_wan=999",
    "medium=arbitrary",
    "prior_budget_wan=0",
    "prior_medium=unknown",
    "change_type=unsafe",
])
def test_judge_workflow_endpoint_invalid_values_get_422(monkeypatch, query):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE", "cloud_synthetic")
    with TestClient(app) as c:
        assert c.get("/judge/api/workflow?" + query).status_code == 422


def test_workflow_is_only_available_in_synthetic_mode(monkeypatch):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE", "local")
    with TestClient(app) as c:
        assert c.get("/judge/api/workflow").status_code == 404
