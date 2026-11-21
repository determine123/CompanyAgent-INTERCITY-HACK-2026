"""Black-box regression cases for deterministic replay and data provenance."""
from __future__ import annotations
import json
import secrets
from fastapi.testclient import TestClient
import pytest
from server import app
from enterprise.store import db,safe_json

@pytest.fixture
def admin():
    with TestClient(app) as client:
        login=client.post('/enterprise/api/auth/login',json={'username':'admin','password':'CI-generated-isolated-password-ONLY'})
        assert login.status_code==200
        client.headers['X-CSRF-Token']=login.json()['csrf']
        yield client

def make_run(client, **kw):
    req={'agent_id':1,'brand':'独立测试品牌','budget_wan':200,'landmark':'正大广场', 'coverage_only':False}
    req.update(kw)
    r=client.post('/enterprise/api/runs',json=req)
    assert r.status_code==200,r.text
    return r.json()

def test_manifest_and_rule_based_agent_eval(admin):
    run=make_run(admin)
    m=run['replay_manifest']
    assert m['schema_version']==1
    assert set(m['dataset_ids'])=={'inventory','coverage','pricing'}
    assert len(m['record_fingerprints']['inventory'])==64
    assert 'load_inventory' in m['skills'][0]['tools_json']
    assert len(m['plan_fingerprint'])==64
    check=run['evaluation_report']
    assert check['total']==6
    assert any(x['id']=='financial_guard' and x['passed'] for x in check['checks'])
    assert check['scope'].startswith('仅评估')
    details=admin.get(f"/enterprise/api/runs/{run['run_id']}/evaluation")
    assert details.status_code==200
    assert details.json()['manifest_available']
    assert details.json()['evaluation']==check

def test_replay_matches_original_with_no_external_network(admin,monkeypatch):
    run=make_run(admin)
    # A frozen replay must never trigger network or model calls.
    import httpx
    monkeypatch.setattr(httpx,'get',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('External network forbidden')))
    r=admin.post(f"/enterprise/api/runs/{run['run_id']}/replay")
    assert r.status_code==200,r.text
    j=r.json()
    assert j['verified'] is True
    assert j['status']=='matched'
    assert j['original_fingerprint']==j['replay_fingerprint']


def test_replay_uses_frozen_skill_configuration(admin):
    run=make_run(admin)
    skill=run['replay_manifest']['skills'][0]
    sid=skill['id']
    with db() as c:
        original=c.execute('SELECT tools_json,instructions FROM skills WHERE id=?',(sid,)).fetchone()
        c.execute('UPDATE skills SET tools_json=?,instructions=? WHERE id=?',(safe_json(['load_inventory']), 'SHOULD NOT CHANGE OLD RUN',sid))
    try:
        response=admin.post(f"/enterprise/api/runs/{run['run_id']}/replay")
        assert response.status_code==200,response.text
        assert response.json()['verified'] is True
    finally:
        with db() as c:c.execute('UPDATE skills SET tools_json=?,instructions=? WHERE id=?',
                                  (original['tools_json'],original['instructions'],sid))


def test_data_drift_is_reported_not_silently_replaced(admin):
    run=make_run(admin)
    dsid=run['replay_manifest']['dataset_ids']['inventory']
    with db() as c:
        old=c.execute('SELECT records_json FROM datasets WHERE id=?',(dsid,)).fetchone()['records_json']
        rows=json.loads(old)
        rows[0]['media_name']='CHANGED AFTER RUN'
        c.execute('UPDATE datasets SET records_json=? WHERE id=?',(safe_json(rows),dsid))
    try:
        r=admin.post(f"/enterprise/api/runs/{run['run_id']}/replay")
        assert r.status_code==200
        assert r.json()['status']=='source_drift'
        assert 'INVENTORY_RECORDS_CHANGED' in r.json()['issues']
    finally:
        with db() as c:c.execute('UPDATE datasets SET records_json=? WHERE id=?',(old,dsid))


def test_result_tampering_detected(admin):
    run=make_run(admin)
    rid=run['run_id']
    with db() as c:
        original=c.execute('SELECT result_json FROM runs WHERE id=?',(rid,)).fetchone()['result_json']
        obj=json.loads(original)
        obj['plan']['spent_wan']+=1
        c.execute('UPDATE runs SET result_json=? WHERE id=?',(safe_json(obj),rid))
    try:
        r=admin.post(f'/enterprise/api/runs/{rid}/replay')
        assert r.status_code==200
        assert r.json()['status']=='result_changed'
    finally:
        with db() as c:c.execute('UPDATE runs SET result_json=? WHERE id=?',(original,rid))


def test_private_run_replay_forbidden_for_other_employee(admin):
    rid=make_run(admin)['run_id']
    name='replay_emp_'+secrets.token_hex(5)
    resp=admin.post('/enterprise/api/users',json={'username':name,'display':'测试员工','role':'employee'})
    assert resp.status_code==200
    with TestClient(app) as client:
        l=client.post('/enterprise/api/auth/login',json={'username':name,'password':resp.json()['initial_password']})
        assert l.status_code==200
        client.headers['X-CSRF-Token']=l.json()['csrf']
        assert client.post(f'/enterprise/api/runs/{rid}/replay').status_code==404
        assert client.get(f'/enterprise/api/runs/{rid}/evaluation').status_code==404


def test_replay_requires_login_and_csrf(admin):
    rid=make_run(admin)['run_id']
    with TestClient(app) as client:
        assert client.post(f'/enterprise/api/runs/{rid}/replay').status_code==401
    token=admin.headers.pop('X-CSRF-Token')
    try: assert admin.post(f'/enterprise/api/runs/{rid}/replay').status_code==403
    finally: admin.headers['X-CSRF-Token']=token


def test_legacy_runs_fail_closed(admin):
    rid=make_run(admin)['run_id']
    with db() as c:
        old=c.execute('SELECT result_json FROM runs WHERE id=?',(rid,)).fetchone()['result_json']
        obj=json.loads(old); obj.pop('replay_manifest',None)
        c.execute('UPDATE runs SET result_json=? WHERE id=?',(safe_json(obj),rid))
    try:
        r=admin.post(f'/enterprise/api/runs/{rid}/replay')
        assert r.status_code==409
    finally:
        with db() as c:c.execute('UPDATE runs SET result_json=? WHERE id=?',(old,rid))

def test_agent_benchmark_matrix_runs_without_external_model(admin,monkeypatch):
    import httpx
    monkeypatch.setattr(httpx,'post',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('No external model')))
    r=admin.post('/enterprise/api/agents/1/benchmark',json={'landmark':'正大广场','coverage_only':False})
    assert r.status_code==200,r.text
    j=r.json()
    assert j['total']==15 and len(j['tests'])==15
    assert j['passed']==15
    assert j['model_calls']==0
    assert {(row['industry'],row['budget_wan']) for row in j['tests']}=={
        (sector,v) for sector in ('银行保险','食品饮料','保健品','私立医院','乐园（主题公园）') for v in (100,200,500)}


def test_benchmark_metro_only_reports_missing_media_instead_of_faking(admin):
    r=admin.post('/enterprise/api/agents/1/benchmark',json={'medium':'metro','coverage_only':True})
    assert r.status_code==200
    j=r.json()
    assert j['passed']<=15
    assert all(item['spent_wan']<=item['budget_wan'] for item in j['tests'] if 'spent_wan' in item)


def test_benchmark_denies_unknown_agent(admin):
    r=admin.post('/enterprise/api/agents/999999/benchmark',json={})
    assert r.status_code==404
