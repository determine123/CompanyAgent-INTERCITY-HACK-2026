"""Enterprise value accounting: no invented savings, per-run access and evidence gates."""
import math
import secrets
import pytest
from fastapi.testclient import TestClient
from server import app
from enterprise.impact_metrics import evaluate_pair

SAMPLE={
    "manual_minutes":120.0,"generation_minutes":0.5,
    "review_minutes":15.0,"rework_minutes":4.0,
    "manual_errors":3,"assistant_errors":1,
    "comparable_scope":True,"evidence_attested":True,
}

@pytest.fixture
def admin():
    with TestClient(app) as c:
        r=c.post('/enterprise/api/auth/login',json={
            'username':'admin','password':'CI-generated-isolated-password-ONLY'})
        assert r.status_code==200,r.text
        c.headers['X-CSRF-Token']=r.json()['csrf']
        yield c

def demo_run(admin):
    r=admin.post('/enterprise/api/runs',json={
        'agent_id':1,'brand':'虚构品牌','industry':'食品饮料','budget_wan':100,
        'start_date':'2027-05-01','weeks':4,'landmark':'正大广场',
        'medium':'bus','brief':'食品饮料模拟客户需要商圈广告方案',
        'coverage_only':False,
    })
    assert r.status_code==200,r.text
    return r.json()['run_id']

def test_time_includes_review_and_rework_and_never_claims_roi():
    r=evaluate_pair(SAMPLE,synthetic_mode=False)
    assert r['ai_total_minutes']==19.5
    assert r['delta_minutes']==100.5
    assert r['time_change_pct']==83.75
    assert r['error_delta']==2
    assert r['status']=='single_case_self_reported'
    assert not r['roi_verified'] and not r['enterprise_savings_verified']
    assert evaluate_pair(SAMPLE,synthetic_mode=True)['status']=='synthetic_illustration'

def test_missing_comparability_remains_unverified():
    x=dict(SAMPLE,comparable_scope=False)
    assert evaluate_pair(x,synthetic_mode=False)['status']=='not_comparable'
    x=dict(SAMPLE,evidence_attested=False)
    assert evaluate_pair(x,synthetic_mode=False)['status']=='not_comparable'

@pytest.mark.parametrize('field,bad',[
    ('manual_minutes',0),('manual_minutes',float('nan')),
    ('review_minutes',-1),('generation_minutes',float('inf')),
    ('rework_minutes',2000),('manual_errors',-1),
    ('assistant_errors',101),('manual_errors',1.2),
])
def test_bad_numeric_metrics_fail_closed(field,bad):
    data=dict(SAMPLE)
    data[field]=bad
    with pytest.raises(ValueError):
        evaluate_pair(data,synthetic_mode=False)

def test_error_counts_must_be_paired():
    x=dict(SAMPLE,manual_errors=None)
    with pytest.raises(ValueError,match='Both error'):
        evaluate_pair(x,synthetic_mode=False)

def test_run_scoped_record_persists_and_is_user_attested_not_proven(admin):
    run_id=demo_run(admin)
    endpoint=f'/enterprise/api/runs/{run_id}/impact-measurement'
    assert admin.get(endpoint).json()['status']=='not_measured'
    r=admin.post(endpoint,json=SAMPLE)
    assert r.status_code==200,r.text
    assert r.json()['report']['roi_verified'] is False
    loaded=admin.get(endpoint)
    assert loaded.status_code==200
    assert loaded.json()['report']['delta_minutes']==100.5
    assert loaded.json()['inputs']['manual_minutes']==120.0
    assert '虚构品牌' not in loaded.text
    assert 'impact_self_report_saved' in admin.get('/enterprise/api/audit').text

def test_cross_user_cannot_read_or_submit_someone_elses_metrics(admin):
    run_id=demo_run(admin)
    name='impact'+secrets.token_hex(4)
    u=admin.post('/enterprise/api/users',json={
        'username':name,'display':'测试员工','role':'employee'})
    assert u.status_code==200
    with TestClient(app) as c:
        logged=c.post('/enterprise/api/auth/login',json={
            'username':name,'password':u.json()['initial_password']})
        assert logged.status_code==200
        c.headers['X-CSRF-Token']=logged.json()['csrf']
        url=f'/enterprise/api/runs/{run_id}/impact-measurement'
        assert c.get(url).status_code==404
        assert c.post(url,json=SAMPLE).status_code==404

def test_csrf_required_for_metric_mutation(admin):
    run_id=demo_run(admin)
    admin.headers.pop('X-CSRF-Token',None)
    assert admin.post(f'/enterprise/api/runs/{run_id}/impact-measurement',json=SAMPLE).status_code==403

def test_client_can_measure_run_and_review_effort_in_ui(admin):
    page=admin.get('/enterprise/').text
    for k in ('clientImpactSave','clientReworkMinutes','clientComparable',
              'clientEvidenceAttested','clientManualErrors','clientAiErrors'):
        assert k in page
