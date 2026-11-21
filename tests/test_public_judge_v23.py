"""Anonymous judge path is ONLY for fixed fictional input + the real deterministic optimizer."""
from __future__ import annotations
from fastapi.testclient import TestClient
from enterprise.judge_preview import preview
from server import app
import pytest

def test_preview_real_planner_has_fictional_source_and_valid_budget():
    for budget in (100,200,500):
        for medium in ('both','bus','metro'):
            x=preview(budget,medium)
            assert x['synthetic_only'] is True
            assert x['real_hongdou_connected'] is False
            assert x['runtime']=='same_deterministic_optimizer_as_enterprise'
            assert 0<=x['spent_wan']<=budget
            assert x['sample_size']==80
            assert x['item_count']==len(x['selected']) or x['selection_truncated']
            assert x['evidence']=={
                'budget_checked':True,'coverage_confirmed':False,
                'future_inventory_available':False,
                'commercial_quote_approved':False,'booked':False,
                'roi_verified':False,
            }
            assert all(y['media_type'] in (('bus','metro') if medium=='both' else (medium,)) for y in x['selected'])

@pytest.mark.parametrize('bad',[(0,'both'),(200,'helium'),(200.0,'both'),(501,'bus')])
def test_preview_strict_allowlists(bad):
    with pytest.raises(ValueError):preview(*bad)

def test_public_judge_api_unauthenticated_but_no_real_backend_access(monkeypatch):
    monkeypatch.setenv('COMPANYAGENT_DEPLOYMENT_MODE','cloud_synthetic')
    with TestClient(app) as c:
        page=c.get('/judge/')
        assert page.status_code==200
        assert '无需登录' in page.text and '合成数据' in page.text
        assert 'ENTERPRISE_BEARER' not in page.text
        script=c.get('/judge/app.js')
        assert script.status_code==200 and 'credentials' in script.text
        r=c.get('/judge/api/plan?budget_wan=200&medium=both')
        assert r.status_code==200,r.text
        result=r.json()
        assert result['spent_wan']<=200
        assert result['real_hongdou_connected'] is False
        assert c.post('/judge/api/plan').status_code==405
        assert c.get('/enterprise/api/insights').status_code==401
        assert c.get('/enterprise/api/runs').status_code==401
        assert c.get('/api/demo').status_code==403

@pytest.mark.parametrize('query',[
    'budget_wan=999&medium=both','budget_wan=200&medium=thirdparty',
    'budget_wan=0&medium=bus','budget_wan=200&medium=bus&customer_secret=abc'
])
def test_judge_endpoint_rejects_invalid_params_or_ignores_unknown(query,monkeypatch):
    monkeypatch.setenv('COMPANYAGENT_DEPLOYMENT_MODE','cloud_synthetic')
    with TestClient(app) as c:
        r=c.get('/judge/api/plan?'+query)
        if 'customer_secret' in query:
            assert r.status_code==200 and 'abc' not in r.text
        else:
            assert r.status_code==422

def test_judge_page_not_available_to_unapproved_runtime(monkeypatch):
    monkeypatch.setenv('COMPANYAGENT_DEPLOYMENT_MODE','local')
    with TestClient(app) as c:
        assert c.get('/judge/api/plan').status_code==404
