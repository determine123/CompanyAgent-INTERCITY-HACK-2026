"""Synthetic-only regression: customer brief -> plan -> cross-form impact."""
from __future__ import annotations
import secrets
import pytest
from fastapi.testclient import TestClient
from server import app
from enterprise.change_workflow import analyze_change,CHANGE_TYPES

@pytest.fixture
def admin():
    with TestClient(app) as c:
        r=c.post('/enterprise/api/auth/login',json={'username':'admin','password':'CI-generated-isolated-password-ONLY'})
        assert r.status_code==200,r.text
        c.headers['X-CSRF-Token']=r.json()['csrf']
        yield c


def run(admin,**attrs):
    request={'agent_id':1,'brand':'合成客户品牌','industry':'食品饮料','budget_wan':200,
             'start_date':'2027-05-01','weeks':4,'landmark':'正大广场','medium':'both',
             'brief':'在上海核心商圈使用有证据的广告媒体','coverage_only':False}
    request.update(attrs)
    r=admin.post('/enterprise/api/runs',json=request)
    assert r.status_code==200,r.text
    return r.json()


@pytest.mark.parametrize('kind',list(CHANGE_TYPES))
def test_all_six_change_causes_generate_ordered_reviewable_actions(admin,kind):
    result=run(admin)
    data={'change_type':kind,'effective_date':'2027-05-12','note':'现场变更影响上刊时间与客户确认'}
    response=admin.post(f'/enterprise/api/runs/{result["run_id"]}/change-impact',json=data)
    assert response.status_code==200,response.text
    report=response.json()
    steps=report['dependency_steps']
    assert steps[0]['id']=='source_check' and steps[-1]['id']=='customer'
    assert [s['order'] for s in steps]==list(range(1,len(steps)+1))
    assert all(s['status']=='requires_human_confirmation' for s in steps)
    assert report['status']=='needs_human_review'
    assert not report['inventory_reserved'] and not report['real_system_mutated'] and not report['customer_notified']
    assert '2027' in ''.join(report['evidence_gaps'])
    assert report['original_plan']['brand']=='合成客户品牌'
    assert all(not step['depends_on'] or step['depends_on'][0]==steps[i-1]['id'] for i,step in enumerate(steps) if i)
    # Planning a change must not mutate the frozen original run.
    frozen=admin.get(f'/enterprise/api/runs/{result["run_id"]}').json()
    assert frozen['result']['plan']==result['plan']

@pytest.mark.parametrize('payload',[
 {'change_type':'shell_exec','effective_date':'2027-05-12','note':'恶意工具调用执行危险操作'},
 {'change_type':'vehicle_reassignment','effective_date':'not-a-date','note':'准备变更媒体车辆'},
 {'change_type':'vehicle_reassignment','effective_date':'2026-05-12','note':'准备变更媒体车辆'},
 {'change_type':'creative_revision','effective_date':'2027-05-12','note':'短'},
])
def test_invalid_changes_are_rejected(admin,payload):
    rid=run(admin)['run_id']
    r=admin.post(f'/enterprise/api/runs/{rid}/change-impact',json=payload)
    assert r.status_code in (400,422)


def test_other_employee_cannot_access_private_run(admin):
    rid=run(admin)['run_id']
    name='v13user'+secrets.token_hex(4)
    r=admin.post('/enterprise/api/users',json={'username':name,'display':'员工','role':'employee'})
    assert r.status_code==200
    with TestClient(app) as c:
        l=c.post('/enterprise/api/auth/login',json={'username':name,'password':r.json()['initial_password']})
        assert l.status_code==200
        c.headers['X-CSRF-Token']=l.json()['csrf']
        denied=c.post(f'/enterprise/api/runs/{rid}/change-impact',json={
            'change_type':'creative_revision','effective_date':'2027-05-12','note':'修改另一员工的方案'})
        assert denied.status_code in (403,404)


def test_csrf_blocks_unauthenticated_mutation():
    with TestClient(app) as c:
        r=c.post('/enterprise/api/runs/1/change-impact',json={'change_type':'creative_revision','effective_date':'2027-05-12','note':'不授权也操作'})
        assert r.status_code in (401,403)


def test_client_ui_is_present_and_data_model_confidential(admin):
    html=admin.get('/enterprise/').text
    for token in ('page-client','clientGenerate','clientModel','changeType','changeAnalyze','clientExport'):
        assert token in html
    status=admin.get('/enterprise/api/status')
    assert status.status_code==200
    assert status.json()['model_configured'] is False
    assert 'B1X_API_KEY' not in status.text
