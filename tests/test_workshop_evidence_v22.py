"""New workshop contract: frozen source selection, no invented availability and RBAC."""
from __future__ import annotations
import secrets
import pytest
from fastapi.testclient import TestClient
from server import app
from enterprise.workshop_contract import source_snapshot,workshop_readiness

@pytest.fixture
def admin():
    with TestClient(app) as client:
        r=client.post('/enterprise/api/auth/login',json={
            'username':'admin','password':'CI-generated-isolated-password-ONLY'})
        assert r.status_code==200,r.text
        client.headers['X-CSRF-Token']=r.json()['csrf']
        yield client

def request_data(**kwargs):
    p={'agent_id':1,'industry':'食品饮料','brand':'虚构饮品甲',
       'brief':'为虚构品牌安排2027年上海饮料广告','budget_wan':200,
       'start_date':'2027-05-01','weeks':4,'landmark':'正大广场',
       'medium':'both','coverage_only':False,
       'business_goal':'新品试饮转化','campaign_goal':'到店',
       'target_audience':'上海通勤白领','success_kpi':'扫码次数',
       'measurement_method':'客户后台的匿名扫码记录'}
    p.update(kwargs)
    return p

def test_workshop_internal_rubric_is_not_official_and_never_books(admin):
    ds=admin.get('/enterprise/api/workshop/data-readiness')
    assert ds.status_code==200,ds.text
    report=ds.json()
    assert report['industry']=='食品饮料'
    assert report['real_inventory_connected'] is False
    assert report['hongdou_bus_metro_status']=='private_approval_pending'
    assert report['visualization_status']=='approved_offline_export_only'
    inventory=next(d for d in report['available_snapshots'] if d['kind']=='inventory')
    assert 'checksum_short' in inventory and 'dataset_id' in inventory
    assert 'Bearer' not in ds.text and 'Authorization' not in ds.text
    run=admin.post('/enterprise/api/runs',json=request_data(inventory_dataset_id=inventory['dataset_id']))
    assert run.status_code==200,run.text
    assert run.json()['source_evidence']['inventory']['dataset_id']==inventory['dataset_id']
    rid=run.json()['run_id']
    review=admin.get(f'/enterprise/api/runs/{rid}/workshop-readiness')
    assert review.status_code==200,review.text
    r=review.json()
    assert r['rubric_official'] is False
    assert r['official_proposal_standard_available'] is False
    assert r['status']=='draft_needs_human_review'
    assert len(r['checks'])==9
    checks={x['id']:x for x in r['checks']}
    assert checks['single_industry']['status']=='evidence_present'
    assert checks['seven_campaign_elements']['status']=='evidence_present'
    assert checks['frozen_inventory_source']['status']=='evidence_present'
    assert checks['target_date_stock']['status']=='needs_review'
    assert checks['formal_pricing']['status']=='needs_review'
    assert checks['human_approval']['status']=='needs_review'
    assert not r['booking_permitted'] and not r['customer_roi_verified']

@pytest.mark.parametrize('badfield', ['coverage_dataset_id','pricing_dataset_id'])
def test_explicit_missing_source_fails_closed(admin,badfield):
    p=request_data(**{badfield:987654321})
    r=admin.post('/enterprise/api/runs',json=p)
    assert r.status_code==403,r.text
    assert '禁止静默' in r.text

def test_invalid_inventory_source_never_uses_another(admin):
    r=admin.post('/enterprise/api/runs',json=request_data(inventory_dataset_id=987654321))
    assert r.status_code==400

def test_user_cannot_access_other_staff_run_or_private_source(admin):
    r=admin.post('/enterprise/api/runs',json=request_data())
    assert r.status_code==200,r.text
    run_id=r.json()['run_id']
    name='ws'+secrets.token_hex(4)
    new=admin.post('/enterprise/api/users',json={'username':name,'display':'隔离测试员工','role':'employee'})
    assert new.status_code==200,new.text
    with TestClient(app) as client:
        login=client.post('/enterprise/api/auth/login',json={
            'username':name,'password':new.json()['initial_password']})
        assert login.status_code==200
        client.headers['X-CSRF-Token']=login.json()['csrf']
        assert client.get(f'/enterprise/api/runs/{run_id}/workshop-readiness').status_code==404
        assert client.get('/enterprise/api/workshop/data-readiness').status_code==200

def test_public_html_contains_source_choice_and_workshop_review(admin):
    page=admin.get('/enterprise/').text
    for text in ('clientInventorySource','clientCoverageSource','clientPricingSource',
                 'clientWorkshopStatus','clientWorkshopChecks','clientSourceState'):
        assert text in page

def test_unknown_origin_is_not_marked_verified():
    row={'id':99,'origin':'unknown_company_feed','checksum':'abc123012345',
         'count':3,'imported_at':'2026-11-21T10:00:00Z'}
    x=source_snapshot(row,kind='inventory')
    assert x['class']=='other_unverified'
    assert x['commercially_verified'] is False
