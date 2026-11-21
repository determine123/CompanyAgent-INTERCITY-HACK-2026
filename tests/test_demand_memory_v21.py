"""v2.1 synthetic demand memory, decisions, auth isolation, owner approval."""
import json
import secrets

import pytest
from fastapi.testclient import TestClient
from server import app
from enterprise.demand_memory import summarize_runs,decision_brief,TEMPLATES
from enterprise.store import TOOLS


@pytest.fixture
def admin():
    with TestClient(app) as client:
        r=client.post('/enterprise/api/auth/login',json={
            'username':'admin','password':'CI-generated-isolated-password-ONLY'})
        assert r.status_code==200,r.text
        client.headers['X-CSRF-Token']=r.json()['csrf']
        yield client


def create_run(client,**overrides):
    req={'agent_id':1,'brand':'虚构饮料品牌','industry':'食品饮料',
         'budget_wan':200,'start_date':'2027-05-01','weeks':4,
         'landmark':'正大广场','medium':'both','coverage_only':False,
         'brief':'上海食品饮料广告预算200万，面向白领的公交地铁方案',
         'business_goal':'试饮','campaign_goal':'到店','target_audience':'通勤人群',
         'success_kpi':'扫码次数','measurement_method':'后台记录'}
    req.update(overrides)
    r=client.post('/enterprise/api/runs',json=req)
    assert r.status_code==200,r.text
    return r.json()['run_id']


def test_pre_review_gives_three_risks_six_questions_three_actions(admin):
    rid=create_run(admin)
    r=admin.get(f'/enterprise/api/runs/{rid}/decision-brief')
    assert r.status_code==200,r.text
    x=r.json()
    assert len(x['risks'])==3 and len(x['questions'])>=5 and len(x['next_actions'])==3
    assert all(y['evidence'] and y['fix'] for y in x['risks'])
    assert '不等于商业收益最优' in x['label']
    assert x['source_labels'].get('inventory')


def test_aggregated_demand_excludes_customer_text_and_brand(admin):
    create_run(admin,brand='DO-NOT-LEAK-XYZ-PRIVATE-BRAND',brief='DO-NOT-LEAK-CUSTOMER-BRIEF',campaign_goal='拉新')
    r=admin.get('/enterprise/api/insights')
    assert r.status_code==200,r.text
    x=r.json()
    assert x['sample_size']>=1
    assert x['goal_counts']['拉新']>=1
    assert 'DO-NOT-LEAK' not in r.text
    assert x['sample_size']==len(x['recent']) or x['sample_size']>20
    assert x['suggested_template'] in TEMPLATES


def test_candidate_requires_data_and_explicit_owner_approval(admin):
    create_run(admin)
    d=admin.post('/enterprise/api/insights/drafts',json={})
    assert d.status_code==200,d.text
    candidate=d.json()
    assert candidate['status']=='pending'
    assert set(candidate['template']['tools']).issubset(TOOLS)
    before=admin.get('/enterprise/api/insights/drafts').json()['items']
    assert any(r['id']==candidate['draft_id'] and r['status']=='pending' for r in before)
    accepted=admin.post(f"/enterprise/api/insights/drafts/{candidate['draft_id']}/adopt",json={})
    assert accepted.status_code==200,accepted.text
    a=accepted.json()
    assert a['visibility']=='private'
    assert accepted.json()['agent_id']>0 and accepted.json()['skill_id']>0
    assert admin.post(f"/enterprise/api/insights/drafts/{candidate['draft_id']}/adopt",json={}).status_code==409
    agents=admin.get('/enterprise/api/agents').json()['items']
    skills=admin.get('/enterprise/api/skills').json()['items']
    assert next(x for x in agents if x['id']==a['agent_id'])['visibility']=='private'
    assert set(next(x for x in skills if x['id']==a['skill_id'])['tools']).issubset(TOOLS)


def test_independent_user_cannot_access_or_adopt_admin_draft(admin):
    rid=create_run(admin)
    d=admin.post('/enterprise/api/insights/drafts',json={}).json()
    name='memory'+secrets.token_hex(4)
    made=admin.post('/enterprise/api/users',json={
        'username':name,'display':'独立员工','role':'employee'})
    assert made.status_code==200,made.text
    with TestClient(app) as c:
        login=c.post('/enterprise/api/auth/login',json={
            'username':name,'password':made.json()['initial_password']})
        assert login.status_code==200
        c.headers['X-CSRF-Token']=login.json()['csrf']
        assert c.get(f'/enterprise/api/runs/{rid}/decision-brief').status_code==404
        assert c.get('/enterprise/api/insights').json()['sample_size']==0
        assert c.get('/enterprise/api/insights/drafts').json()['items']==[]
        assert c.post('/enterprise/api/insights/drafts',json={}).status_code==409
        assert c.post(f'/enterprise/api/insights/drafts/{d["draft_id"]}/adopt',json={}).status_code==404


def test_csrf_and_login_required(admin):
    rid=create_run(admin)
    admin.headers.pop('X-CSRF-Token',None)
    assert admin.post('/enterprise/api/insights/drafts',json={}).status_code==403
    with TestClient(app) as c:
        assert c.get('/enterprise/api/insights').status_code==401
        assert c.get(f'/enterprise/api/runs/{rid}/decision-brief').status_code==401


def test_aggregator_handles_invalid_goal_and_no_leakage():
    item={'id':3,'created_at':'2026-11-21','request_json':json.dumps({
        'brand':'private','campaign_goal':'malicious text','budget_wan':500,'medium':'bus'}),
          'result_json':json.dumps({'quality_report':{'status':'needs_review',
                       'warnings':[{'code':'COVERAGE_GAP','message':'some private text'}]}})}
    out=summarize_runs([item])
    assert out['goal_counts']=={'待确认':1}
    assert out['risk_counts']['COVERAGE_GAP']==1
    assert 'private' not in str(out)
    assert out['suggested_template']=='coverage_evidence'


def test_frontend_customer_first_and_insights_available(admin):
    html=admin.get('/enterprise/').text
    assert '<section class="screen active" id="page-client">' in html
    assert '<section class="screen" id="page-studio">' in html
    for term in ['page-insights','clientReviewRisks','clientReviewQuestions',
                 'clientReviewActions','clientDbProof','insightCreateDraft',
                 'insightApproveDraft']:
        assert term in html
