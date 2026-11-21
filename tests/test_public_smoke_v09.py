"""Public package smoke test using ONLY synthetic demo dataset."""
import os
from fastapi.testclient import TestClient
from server import app


def test_public_demo_and_problem_bootstrap():
    with TestClient(app) as c:
        a=c.post('/enterprise/api/auth/login',json={'username':'admin','password':os.environ['COMPANYAGENT_ADMIN_PASSWORD']})
        assert a.status_code==200
        c.headers['X-CSRF-Token']=a.json()['csrf']
        ds=c.get('/enterprise/api/datasets').json()['items']
        assert any(d['kind']=='inventory' and d['count']>0 for d in ds)
        problem='给食品饮料客户分析上海公交广告媒体，约束预算100万元，需要能够自动核对库存并输出方案'
        r=c.post('/enterprise/api/agents/from-problem',json={'problem':problem})
        assert r.status_code==200,r.text
        run=c.post('/enterprise/api/runs',json={'agent_id':r.json()['agent_id'],'brand':'某演示饮料品牌',
                         'budget_wan':100,'landmark':'正大广场','coverage_only':False})
        assert run.status_code==200,run.text
        assert run.json()['plan']['spent_wan']<=100
        fb=c.post('/enterprise/api/feedback',json={'run_id':run.json()['run_id'],'score':3,'category':'pricing_accuracy','comment':'仍需正式核价'})
        assert fb.status_code==200
        assert fb.json()['improvement_id'] is None
