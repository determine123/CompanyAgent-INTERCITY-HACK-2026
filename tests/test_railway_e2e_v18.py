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


def test_demo_seed_created_even_with_another_inventory_dataset(isolated_demo_db):
    """Presence of an existing non-demo inventory must not suppress demo bootstrap."""
    isolated_demo_db.init()
    with isolated_demo_db.db() as c:
        c.execute("DELETE FROM datasets WHERE origin=?",("demo_synthetic_repo_seed",))
        admin=c.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]
        c.execute(
            """INSERT INTO datasets(owner_id,kind,name,origin,records_json,count,checksum,
               visibility,imported_at,source_id,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (admin,"inventory","Other isolated test inventory","non_demo_existing",
             "[]",0,"0"*64,"team",store.now(),None,"Synthetic unit-test placeholder"),
        )
    isolated_demo_db.init()
    with isolated_demo_db.db() as c:
        rows=c.execute("SELECT origin,count,notes FROM datasets ORDER BY id").fetchall()
        assert len(rows)==2
        assert {r["origin"] for r in rows}=={"non_demo_existing","demo_synthetic_repo_seed"}
        assert next(r["count"] for r in rows if r["origin"]=="demo_synthetic_repo_seed") == 80
        assert next(r["count"] for r in rows if r["origin"]=="non_demo_existing") == 0
    # Restart must not create duplicate records, or modify the other dataset.
    isolated_demo_db.init()
    with isolated_demo_db.db() as c:
        assert c.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]==2


def test_missing_demo_seed_is_recovered_on_later_startup(isolated_demo_db):
    isolated_demo_db.init()
    with isolated_demo_db.db() as c:
        c.execute("DELETE FROM datasets WHERE origin=?",("demo_synthetic_repo_seed",))
        assert c.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]==0
    isolated_demo_db.init()
    with isolated_demo_db.db() as c:
        restored=c.execute(
            "SELECT kind,origin,count,name FROM datasets WHERE origin=?",
            ("demo_synthetic_repo_seed",),
        ).fetchall()
        assert len(restored)==1
        assert restored[0]["count"]==80
        assert "虚构" in restored[0]["name"]


def test_fastapi_startup_hook_rechecks_demo_dataset(monkeypatch,tmp_path):
    """Starting the HTTP service re-seeds the scoped synthetic inventory."""
    from fastapi.testclient import TestClient
    from server import app
    monkeypatch.setattr(store,"STATE",tmp_path)
    monkeypatch.setattr(store,"DB",tmp_path/"companyagent-restart-test.sqlite3")
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","cloud_synthetic")
    monkeypatch.setenv("COMPANYAGENT_ADMIN_PASSWORD","CI-app-restart-isolated-fixture-password")
    with TestClient(app):
        with store.db() as c:
            assert c.execute(
                "SELECT COUNT(*) FROM datasets WHERE origin=?",
                ("demo_synthetic_repo_seed",),
            ).fetchone()[0]==1
    with store.db() as c:
        c.execute("DELETE FROM datasets WHERE origin=?",("demo_synthetic_repo_seed",))
    with TestClient(app):
        with store.db() as c:
            assert c.execute(
                "SELECT COUNT(*) FROM datasets WHERE origin=?",
                ("demo_synthetic_repo_seed",),
            ).fetchone()[0]==1


def test_demo_fixture_media_mix_is_bus_and_metro_only(isolated_demo_db):
    import json
    isolated_demo_db.init()
    with isolated_demo_db.db() as c:
        raw=c.execute("SELECT records_json FROM datasets WHERE origin=?",
                      ("demo_synthetic_repo_seed",)).fetchone()["records_json"]
    records=json.loads(raw)
    assert len(records)==80
    assert {item["media_type"] for item in records}=={"bus","metro"}
    assert all(str(item["source"]).startswith("DEMO-") for item in records)
