"""Public synthetic demo hard gates. No corporate data and no network."""
from __future__ import annotations
from fastapi.testclient import TestClient
import pytest

from server import app
from enterprise.deployment_policy import forbidden_cloud_request


@pytest.fixture
def synthetic_client(monkeypatch):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","cloud_synthetic")
    with TestClient(app) as c:
        r=c.post("/enterprise/api/auth/login",
                 json={"username":"admin","password":"CI-generated-isolated-password-ONLY"})
        assert r.status_code==200, r.text
        c.headers["X-CSRF-Token"]=r.json()["csrf"]
        yield c


def test_only_food_beverage_allowed_in_public_synthetic(synthetic_client):
    c=synthetic_client
    bad=c.post("/enterprise/api/runs",json={
        "agent_id":1,"industry":"银行保险","brand":"合成银行","budget_wan":200,
        "landmark":"正大广场","coverage_only":False})
    assert bad.status_code==400
    assert "食品饮料" in bad.json()["detail"]

    okay=c.post("/enterprise/api/runs",json={
        "agent_id":1,"industry":"食品饮料","brand":"合成食品品牌","budget_wan":200,
        "landmark":"正大广场","coverage_only":False})
    assert okay.status_code==200
    assert okay.json()["plan"]["industry"]=="食品饮料"


def test_public_synthetic_status_never_claims_real_api(synthetic_client):
    r=synthetic_client.get("/enterprise/api/status")
    assert r.status_code==200
    x=r.json()
    assert x["deployment_mode"]=="cloud_synthetic"
    assert x["fixed_industry"]=="食品饮料"
    assert x["visual_coverage_api_available"] is False
    assert x["hongdou_real_api_connected"] is False


@pytest.mark.parametrize("path,method",[
    ("/api/demo","GET"),("/enterprise/api/datasets/upload","POST"),
    ("/enterprise/api/sources","POST"),("/enterprise/api/users","POST"),
    ("/enterprise/api/sources/1/sync","POST")])
def test_public_layer_rejects_legacy_ingress_and_user_provisioning(synthetic_client,path,method):
    r=synthetic_client.request(method,path)
    assert r.status_code==403


def test_local_user_creation_remains_allowed_by_policy_not_public(monkeypatch):
    assert not forbidden_cloud_request("/enterprise/api/users","POST",{"COMPANYAGENT_DEPLOYMENT_MODE":"local"})
