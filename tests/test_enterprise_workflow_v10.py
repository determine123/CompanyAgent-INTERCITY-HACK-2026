"""Enterprise-grade proposal gates: no network, no licensed datasets required."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from enterprise.quality import assess_result
from server import app
from enterprise.store import db, safe_json


@pytest.fixture
def admin():
    with TestClient(app) as client:
        r=client.post('/enterprise/api/auth/login',json={'username':'admin','password':'CI-generated-isolated-password-ONLY'})
        assert r.status_code==200,r.text
        client.headers['X-CSRF-Token']=r.json()['csrf']
        yield client


def run(client,**kwargs):
    payload={'agent_id':1,'brand':'公开演示品牌','budget_wan':200,'landmark':'正大广场','coverage_only':False}
    payload.update(kwargs)
    r=client.post('/enterprise/api/runs',json=payload)
    assert r.status_code==200,r.text
    return r.json()


def create_employee(admin,role='employee'):
    import secrets
    user='testuser_'+secrets.token_hex(5)
    r=admin.post('/enterprise/api/users',json={'username':user,'display':'测试员工','role':role})
    assert r.status_code==200,r.text
    with TestClient(app) as client:
        login=client.post('/enterprise/api/auth/login',json={'username':user,'password':r.json()['initial_password']})
        assert login.status_code==200,login.text
        client.headers['X-CSRF-Token']=login.json()['csrf']
        yield client


def test_three_budgets_recomputed_against_same_records(admin):
    result=run(admin)
    assert set(result['budget_variants'])=={'100','200','500'}
    amounts=[]
    for key,v in result['budget_variants'].items():
        assert v['budget_wan']==float(key)
        assert 0 <= v['spent_wan'] <= float(key)
        assert v['remaining_wan']>=0
        assert round(sum(r['line_total_wan'] for r in v['selected']),2)==v['spent_wan']
        assert all(r['quantity']<=r['available_count'] for r in v['selected'])
        amounts.append(v['spent_wan'])
    assert amounts[0]!=amounts[-1]  # Real recomputation, not static slide.
    assert result['quality_report']['status']=='needs_review'


def test_quality_gate_is_pure_and_rejects_fraudulent_totals():
    x={'plan':{'budget_wan':100,'spent_wan':104,'selected':[{'quantity':2,'available_count':1,'line_total_wan':109}]}}
    r=assess_result(x)
    assert r['status']=='blocked' and not r['demo_approvable']
    assert {'OVER_BUDGET','INVALID_QUANTITY','TOTAL_MISMATCH'} <= {a['code'] for a in r['blockers']}


def test_missing_media_blocks_demo_approval(admin):
    result=run(admin)
    # Fault injection into persisted result: a run that lost all media may
    # not be approved, even if a previous cached quality report said otherwise.
    with db() as c:
        stored=json.loads(c.execute('SELECT result_json FROM runs WHERE id=?',(result['run_id'],)).fetchone()['result_json'])
        stored['plan']['selected']=[]
        stored['plan']['item_count']=0
        stored['plan']['spent_wan']=0
        c.execute('UPDATE runs SET result_json=? WHERE id=?',(safe_json(stored),result['run_id']))
    r=admin.post(f"/enterprise/api/runs/{result['run_id']}/review",json={'decision':'approve'})
    assert r.status_code==409


def test_admin_approval_is_demo_only_and_records_audit(admin):
    r=run(admin)
    id=r['run_id']
    before=admin.get(f'/enterprise/api/runs/{id}/quality').json()
    assert before['review']['status']=='pending'
    approved=admin.post(f'/enterprise/api/runs/{id}/review',json={'decision':'approve','comment':'仅用于现场演示'})
    assert approved.status_code==200,approved.text
    assert approved.json()['status']=='approved'
    assert '不构成2027库存锁定' in approved.json()['note']
    after=admin.get(f'/enterprise/api/runs/{id}/quality').json()
    assert after['review']['status']=='approved'
    assert len(after['review']['snapshot_sha256'])==64
    logs=admin.get('/enterprise/api/audit').json()['items']
    assert any(e['action']=='proposal_demo_review' for e in logs)


def test_admin_can_reject_proposal(admin):
    id=run(admin)['run_id']
    r=admin.post(f'/enterprise/api/runs/{id}/review',json={'decision':'reject','comment':'优先核验覆盖'})
    assert r.status_code==200
    assert admin.get(f'/enterprise/api/runs/{id}/quality').json()['review']['status']=='rejected'


def test_managers_employees_cannot_approve_others_runs(admin):
    id=run(admin)['run_id']
    for role in ('employee','manager'):
        for client in create_employee(admin,role):
            assert client.get(f'/enterprise/api/runs/{id}/quality').status_code==404
            assert client.post(f'/enterprise/api/runs/{id}/review',json={'decision':'approve'}).status_code==403
            assert client.get(f'/enterprise/api/runs/{id}/proposal.html').status_code==404


def test_login_and_csrf_required_for_reviews(admin):
    id=run(admin)['run_id']
    with TestClient(app) as visitor:
        assert visitor.get(f'/enterprise/api/runs/{id}/proposal.html').status_code==401
    token=admin.headers.pop('X-CSRF-Token')
    try:
        assert admin.post(f'/enterprise/api/runs/{id}/review',json={'decision':'approve'}).status_code==403
    finally:
        admin.headers['X-CSRF-Token']=token


def test_offline_export_contains_variants_and_sanitizes_script_injection(admin):
    malicious='品牌</script><script>alert(1)</script>'
    result=run(admin,brand=malicious)
    id=result['run_id']
    resp=admin.get(f'/enterprise/api/runs/{id}/proposal.html')
    assert resp.status_code==200
    assert 'attachment;' in resp.headers['content-disposition']
    assert resp.headers['cache-control']=='private, no-store'
    assert 'Content-Security-Policy' in resp.headers
    assert 'https://' not in resp.text and 'http://' not in resp.text
    assert '</script><script>alert(1)' not in resp.text
    assert '\\u003c/script\\u003e' in resp.text
    assert '"100": {' in resp.text and '"500": {' in resp.text
    assert '未获演示审批' in resp.text
    assert 'generated_from_run' in resp.text


def test_export_approved_banner(admin):
    id=run(admin)['run_id']
    admin.post(f'/enterprise/api/runs/{id}/review',json={'decision':'approve'})
    html=admin.get(f'/enterprise/api/runs/{id}/proposal.html').text
    assert '管理员已批准用于演示' in html
    assert '正式报价' in html


def test_approval_stale_after_unauthorized_db_mutation(admin):
    id=run(admin)['run_id']
    admin.post(f'/enterprise/api/runs/{id}/review',json={'decision':'approve'})
    with db() as c:
        row=c.execute('SELECT result_json FROM runs WHERE id=?',(id,)).fetchone()
        result=json.loads(row['result_json'])
        result['rationale']+=' (tampered)'
        c.execute('UPDATE runs SET result_json=? WHERE id=?',(safe_json(result),id))
    assert admin.get(f'/enterprise/api/runs/{id}/quality').json()['review']['status']=='stale'


def test_only_2027_campaign_allowed(admin):
    resp=admin.post('/enterprise/api/runs',json={'agent_id':1,'budget_wan':100,'start_date':'2026-05-01'})
    assert resp.status_code==400


def test_no_enterprise_credentials_in_public_paths():
    root=Path(__file__).resolve().parents[1]
    assert not (root/'data/contest_private').exists()
    assert not (root/'runtime/FIRST_LOGIN.txt').exists()
    assert (root/'enterprise/quality.py').is_file()
    assert (root/'enterprise/proposal.py').is_file()


@pytest.mark.parametrize('industry',['银行保险','食品饮料','保健品','私立医院','乐园（主题公园）'])
@pytest.mark.parametrize('budget',[100,200,500])
def test_judge_input_matrix(industry,budget,admin):
    """All 15 competition industry/budget combinations produce bounded results."""
    result=run(admin,industry=industry,budget_wan=budget,coverage_only=False)
    assert result['plan']['industry']==industry
    assert result['plan']['budget_wan']==budget
    assert 0<=result['plan']['spent_wan']<=budget
    assert result['plan']['end_date'].startswith('2027')
    assert not result['quality_report']['blockers']
    assert result['budget_variants'][str(budget)]['spent_wan']==result['plan']['spent_wan']
