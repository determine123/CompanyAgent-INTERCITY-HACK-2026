"""v1.2 tool calls, data bridge and error-driven Skill patch fault injection."""
from __future__ import annotations
import json, secrets, os
import pytest
import httpx
from fastapi.testclient import TestClient
from server import app
from enterprise.store import db,safe_json
from enterprise.bridge import reconcile
from enterprise.model_tools import run_model_tools,ModelError

@pytest.fixture
def admin():
    with TestClient(app) as client:
        r=client.post('/enterprise/api/auth/login',json={'username':'admin','password':'CI-generated-isolated-password-ONLY'})
        assert r.status_code==200,r.text
        client.headers['X-CSRF-Token']=r.json()['csrf']
        yield client


def _run(client,**kw):
    r=client.post('/enterprise/api/runs',json={'agent_id':1,'brand':'合成品牌','landmark':'正大广场',
                                               'budget_wan':200,'coverage_only':False,**kw})
    assert r.status_code==200,r.text
    return r.json()


def _coverage_csv(name='模拟公交媒体001',place='正大广场'):
    return ('media_name,media_type,landmark,radius_m,distance_m\n'+
            f'{name},公交线路,{place},500,63\n').encode('utf-8')


def _import(client,kind,data,name):
    res=client.post(f'/enterprise/api/datasets/upload?kind={kind}&visibility=private',
                  files={'file':(name,data,'text/csv')})
    assert res.status_code==200,res.text
    return res.json()['dataset_id']


def test_strict_bridge_not_fuzzy_or_booking(admin):
    cv=_import(admin,'coverage',_coverage_csv(),'coverage_v12.csv')
    with db() as c:
        i=c.execute("SELECT id FROM datasets WHERE kind='inventory' AND origin='synthetic_demo' LIMIT 1").fetchone()['id']
    r=admin.post('/enterprise/api/data/bridge/reconcile',json={'inventory_dataset_id':i,'coverage_dataset_id':cv,'landmark':'正大广场'})
    assert r.status_code==200,r.text
    x=r.json()
    assert x['summary']['filtered_matched_items']==1
    assert x['summary']['metro_matched']==0
    assert x['summary']['bus_matched']==1
    assert x['matched_media'][0]['media_name']=='模拟公交媒体001'
    assert x['verified_for_2027'] is False and x['booking_state']=='NOT_RESERVED'
    assert len(x['provenance']['coverage']['sha256'])==64


def test_same_name_duplicate_evidence_is_not_distinct_inventory():
    inv=[{'id':'1','media_type':'bus','media_name':'100路','available_count':2},
         {'id':'2','media_type':'bus','media_name':'1001路','available_count':1}]
    cov=[{'media_type':'bus','media_name':'100路','landmark':'正大广场','source':'s'},
         {'media_type':'bus','media_name':'100路','landmark':'正大广场','source':'s'}]
    x=reconcile(inv,cov,landmark='正大广场')
    assert x['summary']['filtered_matched_items']==1
    assert x['summary']['matched_coverage_rows']==2
    assert x['summary']['repeated_evidence_rows']==1
    assert x['matched_media'][0]['media_name']=='100路'


def test_bridge_denies_private_data_to_other_employee(admin):
    cv=_import(admin,'coverage',_coverage_csv(),'private_coverage12.csv')
    with db() as c:i=c.execute("SELECT id FROM datasets WHERE kind='inventory' LIMIT 1").fetchone()['id']
    username='bridge_'+secrets.token_hex(5)
    r=admin.post('/enterprise/api/users',json={'username':username,'display':'员工','role':'employee'})
    with TestClient(app) as user:
        login=user.post('/enterprise/api/auth/login',json={'username':username,'password':r.json()['initial_password']})
        user.headers['X-CSRF-Token']=login.json()['csrf']
        denied=user.post('/enterprise/api/data/bridge/reconcile',json={'inventory_dataset_id':i,'coverage_dataset_id':cv})
        assert denied.status_code==403


def test_model_requires_consent_and_server_key(admin,monkeypatch):
    run=_run(admin)
    rid=run['run_id']
    assert admin.post(f'/enterprise/api/runs/{rid}/model-tools',json={'external_consent':False}).status_code==412
    monkeypatch.delenv('B1X_API_KEY',raising=False)
    r=admin.post(f'/enterprise/api/runs/{rid}/model-tools',json={'external_consent':True})
    assert r.status_code==503
    assert 'B1X_API_KEY' in r.json()['detail']
    failures=admin.get('/enterprise/api/failures').json()['items']
    assert any(x['code']=='MODEL_NOT_CONFIGURED' and x['run_id']==rid for x in failures)


def _fake_transport(result_calls):
    payloads=[]
    responses=iter(result_calls)
    def handler(req):
        assert req.url==httpx.URL('https://token.b1x.work/v1/chat/completions')
        assert req.headers['Authorization']=='Bearer test-only'
        obj=json.loads(req.content)
        payloads.append(obj)
        return httpx.Response(200,json={'choices':[{'message':next(responses)}]})
    return httpx.MockTransport(handler),payloads


def test_model_three_step_tool_calls_frozen_aggregate_only(admin):
    run=_run(admin)
    replies=[
        {'role':'assistant','content':None,'tool_calls':[{'id':'call1','type':'function','function':{'name':'inspect_coverage','arguments':'{}'}}]},
        {'role':'assistant','content':None,'tool_calls':[{'id':'call2','type':'function','function':{'name':'select_budget_scenario','arguments':'{"budget_wan":100}'}}]},
        {'role':'assistant','content':'选100万情景，并保留未锁位提醒。'}]
    transport,payloads=_fake_transport(replies)
    r=run_model_tools(run,{'inspect_coverage','select_budget_scenario'},api_key='test-only',transport=transport)
    assert len(r['executed_tools'])==2
    assert r['selected_scenario']['budget_wan']==100
    assert '锁位' in r['summary']
    assert all('模拟公交媒体' not in json.dumps(payload,ensure_ascii=False) for payload in payloads)
    assert all('合成品牌' not in json.dumps(payload,ensure_ascii=False) for payload in payloads)
    assert all('正大广场' not in json.dumps(payload,ensure_ascii=False) for payload in payloads)
    assert r['selected_scenario']['spent_wan'] <=100

@pytest.mark.parametrize('bad_call',[
    {'name':'execute_shell','arguments':'{}'},
    {'name':'select_budget_scenario','arguments':'{"budget_wan":999}'},
    {'name':'select_budget_scenario','arguments':'{"budget_wan":100,"override_admin":true}'},
    {'name':'inspect_coverage','arguments':'{"url":"http://localhost:1234"}'},
    {'name':'inspect_inventory','arguments':'not-json'},
])
def test_malicious_model_calls_fail_closed(admin,bad_call):
    run=_run(admin)
    t,_=_fake_transport([{'role':'assistant','tool_calls':[{'id':'x','type':'function','function':bad_call}]}])
    with pytest.raises(ModelError):
        run_model_tools(run,{'inspect_coverage','inspect_inventory','select_budget_scenario'},api_key='test-only',transport=t)


def test_unapproved_model_tool_rejected_before_http(admin):
    run=_run(admin)
    t,_=_fake_transport([])
    with pytest.raises(ModelError):run_model_tools(run,set(),api_key='test-only',transport=t)


def test_non_owner_cannot_access_model_trace(admin):
    rid=_run(admin)['run_id']
    name='hidden_'+secrets.token_hex(5)
    res=admin.post('/enterprise/api/users',json={'username':name,'display':'员工','role':'employee'})
    with TestClient(app) as user:
        l=user.post('/enterprise/api/auth/login',json={'username':name,'password':res.json()['initial_password']})
        user.headers['X-CSRF-Token']=l.json()['csrf']
        assert user.get(f'/enterprise/api/runs/{rid}/model-tools').status_code==404
        assert user.post(f'/enterprise/api/runs/{rid}/model-tools',json={'external_consent':True}).status_code==404


def test_failed_coverage_skill_auto_proposes_then_tests_publishes_rolls_back(admin):
    # Use synthetic dataset and deliberately restrict one private skill.
    cvid=_import(admin,'coverage',_coverage_csv(),'improvement_coverage12.csv')
    skill=admin.post('/enterprise/api/skills',json={'name':'有缺陷的覆盖工具配置',
        'instructions':'合成测试Skill','tools':['load_inventory','optimize_budget','brief_parse'], 'visibility':'private'}).json()
    aid=admin.post('/enterprise/api/agents',json={'name':'缺工具的合成业务Agent',
        'description':'单元测试','skill_ids':[skill['id']], 'visibility':'private'}).json()['id']
    r=admin.post('/enterprise/api/runs',json={'agent_id':aid,'budget_wan':100,
                   'landmark':'正大广场','coverage_only':True,'coverage_dataset_id':cvid})
    assert r.status_code==200,r.text
    run=r.json()
    fid=run.get('failure_improvement_id')
    assert fid,run
    out=admin.post(f'/enterprise/api/failures/{fid}/evaluate')
    assert out.status_code==200,out.text
    report=out.json()
    assert report['passed'],report
    assert report['before']['unsupported']>report['after']['unsupported']
    release=admin.post(f'/enterprise/api/failures/{fid}/publish')
    assert release.status_code==200,release.text
    with db() as c:
        s=c.execute('SELECT tools_json FROM skills WHERE id=?',(skill['id'],)).fetchone()
    assert 'match_coverage' in json.loads(s['tools_json'])
    undo=admin.post(f'/enterprise/api/failures/{fid}/rollback')
    assert undo.status_code==200
    assert 'match_coverage' not in undo.json()['restored_tools']


def test_failure_experiment_without_original_run_cannot_publish(admin):
    from enterprise.failure_learning import record_failure
    id=record_failure(1,1,None,None,'DATA_NOT_FOUND','没有数据')
    assert admin.post(f'/enterprise/api/failures/{id}/evaluate').status_code==409
    assert admin.post(f'/enterprise/api/failures/{id}/publish').status_code==409


def test_model_rejects_result_tampering_even_when_key_set(admin,monkeypatch):
    rid=_run(admin)['run_id']
    with db() as c:
        orig=c.execute('SELECT result_json FROM runs WHERE id=?',(rid,)).fetchone()['result_json']
        x=json.loads(orig);x['plan']['spent_wan']=1
        c.execute('UPDATE runs SET result_json=? WHERE id=?',(safe_json(x),rid))
    monkeypatch.setenv('B1X_API_KEY','dummy-should-never-call')
    try:
        bad=admin.post(f'/enterprise/api/runs/{rid}/model-tools',json={'external_consent':True})
        assert bad.status_code==409
    finally:
        with db() as c:c.execute('UPDATE runs SET result_json=? WHERE id=?',(orig,rid))


def test_invalid_model_multi_call_is_blocked(admin):
    run=_run(admin)
    call={'id':'x','type':'function','function':{'name':'inspect_inventory','arguments':'{}'}}
    t,_=_fake_transport([{'role':'assistant','tool_calls':[call,call]}])
    with pytest.raises(ModelError,match='最多一次'):
        run_model_tools(run,{'inspect_inventory'},api_key='test-only',transport=t)


def test_insufficient_model_calls_never_auto_modify_plan(admin):
    run=_run(admin)
    t,_=_fake_transport([{'role':'assistant','content':'需要先核验库存，不能承诺效果'}])
    old=run['plan']['spent_wan']
    output=run_model_tools(run,{'inspect_inventory'},api_key='test-only',transport=t,max_steps=1)
    assert output['selected_scenario'] is None
    assert run['plan']['spent_wan']==old


def test_data_bridge_requires_csrf(admin):
    with db() as c:
        inventory=c.execute("SELECT id FROM datasets WHERE kind='inventory' LIMIT 1").fetchone()['id']
        coverage=c.execute("SELECT id FROM datasets WHERE kind='coverage' LIMIT 1").fetchone()['id']
    token=admin.headers.pop('X-CSRF-Token')
    try:
        assert admin.post('/enterprise/api/data/bridge/reconcile',json={
            'inventory_dataset_id':inventory,'coverage_dataset_id':coverage}).status_code==403
    finally:
        admin.headers['X-CSRF-Token']=token


def test_staff_ui_serves_all_three_v12_entrypoints():
    with TestClient(app) as c:
        html=c.get('/enterprise/')
        js=c.get('/enterprise/app.js')
    assert html.status_code==200 and js.status_code==200
    for element in ('id="modelToolCall"','id="bridgeInventory"','id="bridgeCoverage"',
                    'id="bridgeCheck"','id="failureCases"'):
        assert element in html.text
    for path in ('/data/bridge/reconcile','/model-tools','/failures/'):
        assert path in js.text
    assert 'eval(' not in js.text
