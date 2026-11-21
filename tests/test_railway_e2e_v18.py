"""Synthetic Railway fixture + real HTTPS probe configuration regression tests."""
from __future__ import annotations
import pytest
from enterprise import store
from scripts.verify_railway_live_end_to_end import check_env, AcceptanceFailed

@pytest.fixture
def isolated_demo_db(monkeypatch,tmp_path):
    monkeypatch.setattr(store,"STATE",tmp_path)
    monkeypatch.setattr(store,"DB",tmp_path/"companyagent-ci-test.sqlite3")
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","cloud_synthetic")
    monkeypatch.setenv("COMPANYAGENT_ADMIN_PASSWORD","CI-genuine-but-fake-unit-test-secret-long")
    return store

def test_cloud_demo_bootstraps_fictional_inventory_without_import(isolated_demo_db):
    isolated_demo_db.init()
    with isolated_demo_db.db() as c:
        inv=c.execute("SELECT * FROM datasets WHERE kind='inventory'").fetchall()
        assert len(inv)==1
        dataset=inv[0]
        assert dataset["origin"]=="demo_synthetic_repo_seed"
        assert dataset["count"]>0
        assert "虚构" in dataset["name"]
        assert "真实红豆" in dataset["notes"]
    isolated_demo_db.init()
    with isolated_demo_db.db() as c:
        assert c.execute("SELECT count(*) FROM datasets WHERE kind='inventory'").fetchone()[0]==1

def test_non_demo_local_mode_does_not_bootstrap_inventory(monkeypatch,tmp_path):
    monkeypatch.setattr(store,"STATE",tmp_path)
    monkeypatch.setattr(store,"DB",tmp_path/"companyagent-local-test.sqlite3")
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","local")
    monkeypatch.setenv("COMPANYAGENT_ADMIN_PASSWORD","CI-local-unit-test-secret-long")
    store.init()
    with store.db() as c:
        assert c.execute("SELECT count(*) FROM datasets").fetchone()[0]==0

def public_probe_env():
    return {
        "RAILWAY_LIVE_BASE":"https://example.up.railway.app",
        "RAILWAY_LIVE_GATEWAY_USER":"ci-reviewer",
        "RAILWAY_LIVE_GATEWAY_PASSWORD":"ci-fake-gateway-password",
        "RAILWAY_LIVE_APP_PASSWORD":"ci-fake-app-password",
        "RAILWAY_LIVE_EXPLICIT_CONSENT":"synthetic-only",
    }

def test_live_probe_accepts_only_railway_https_hostname():
    assert check_env(public_probe_env())=="https://example.up.railway.app"

@pytest.mark.parametrize("bad",[
    {"RAILWAY_LIVE_BASE":"http://example.up.railway.app"},
    {"RAILWAY_LIVE_BASE":"https://example.org"},
    {"RAILWAY_LIVE_BASE":"https://localhost"},
    {"RAILWAY_LIVE_BASE":"https://example.up.railway.app:8765"},
    {"RAILWAY_LIVE_BASE":"https://example.up.railway.app/path"},
    {"RAILWAY_LIVE_BASE":"https://example.up.railway.app/?q=1"},
    {"RAILWAY_LIVE_BASE":"https://password@example.up.railway.app"},
    {"RAILWAY_LIVE_GATEWAY_PASSWORD":""},
    {"RAILWAY_LIVE_APP_PASSWORD":""},
    {"RAILWAY_LIVE_EXPLICIT_CONSENT":"false"},
])
def test_live_probe_rejects_unsafe_targets_missing_secrets_and_no_consent(bad):
    env=public_probe_env()
    env.update(bad)
    with pytest.raises(AcceptanceFailed):
        check_env(env)
