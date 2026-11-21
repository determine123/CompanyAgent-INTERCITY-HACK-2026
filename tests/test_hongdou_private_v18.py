"""RedBean/Hongdou private connector: strictly offline httpx.MockTransport tests."""
from __future__ import annotations
from dataclasses import replace
import httpx
import pytest

from enterprise.hongdou_private_readonly import (
    EnterpriseGrant,PrivateServiceConfig,HongdouPilotDenied,inspect_private_inventory,
)

def config():
    return PrivateServiceConfig(
        origin="https://approved-internal.example.invalid:881",
        approved_host="approved-internal.example.invalid",
        bus_path="/stock/bus/page",
        metro_path="/stock/metro/page",
        tenant_id="TENANT-demo",
        bearer_token="CI-FAKE-TOKEN-DO-NOT-USE",
    )

def grant():
    return EnterpriseGrant(
        "DATA-OWNER-TICKET-123","SECURITY-TICKET-123",
        "TENANT-demo","2099-12-31T23:59:59+00:00",
    )

def fetch(kind,monkeypatch,transport,**kw):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","enterprise_pilot")
    return inspect_private_inventory(
        kind,start_date="2026-11-21",end_date="2026-11-21",
        grant=grant(),config=config(),verify_enterprise_approval=lambda g: True,
        transport=transport,**kw)

def test_mock_transport_checks_exact_bus_route_headers_and_no_raw_response(monkeypatch):
    seen=[]
    def fake(req):
        seen.append(req)
        assert req.method=="GET"
        assert req.url.host=="approved-internal.example.invalid"
        assert req.url.port==881
        assert req.url.path=="/stock/bus/page"
        assert req.url.params["pageNo"]=="1"
        assert req.url.params["lineName"]=="100路"
        assert req.headers["tenant-id"]=="TENANT-demo"
        assert req.headers["Authorization"]=="Bearer CI-FAKE-TOKEN-DO-NOT-USE"
        return httpx.Response(200,json={"code":0,"data":{"list":[{"private_customer":"NEVER_RETURN_THIS"}],"total":1}})
    r=fetch("bus",monkeypatch,httpx.MockTransport(fake),line_name="100路")
    assert len(seen)==1
    assert r["metadata"]["sample_list_length"]==1
    assert r["record_values_returned"] is False
    assert r["remote_model_called"] is False
    assert r["database_written"] is False
    assert r["response_contract_confirmed"] is False
    assert r["quantity_semantics_confirmed"] is False
    assert "NEVER_RETURN_THIS" not in str(r)
    assert "CI-FAKE-TOKEN-DO-NOT-USE" not in str(r)

def test_metro_query_is_separate_and_readonly(monkeypatch):
    def fake(req):
        assert req.url.path=="/stock/metro/page"
        assert req.url.params["keyword"]=="徐家汇"
        assert "lineName" not in req.url.params
        return httpx.Response(200,json={"code":0,"data":{"list":[{"id":1}]}})
    r=fetch("metro",monkeypatch,httpx.MockTransport(fake),keyword="徐家汇")
    assert r["kind"]=="metro"
    assert not r["real_stock_bookability_verified"]

@pytest.mark.parametrize("mode",["cloud_synthetic","local","production"])
def test_public_and_local_runtime_unauthorized_without_any_network(monkeypatch,mode):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE",mode)
    called=[]
    transport=httpx.MockTransport(lambda req:called.append(req) or httpx.Response(200,json={"data":[]}))
    with pytest.raises(HongdouPilotDenied,match="disabled"):
        inspect_private_inventory("bus",start_date="2026-11-21",end_date="2026-11-21",
                                  grant=grant(),config=config(),verify_enterprise_approval=lambda g:True,
                                  transport=transport)
    assert not called

@pytest.mark.parametrize("field,value",[
    ("origin","http://approved-internal.example.invalid:881"),
    ("origin","https://approved-internal.example.invalid:8080"),
    ("origin","https://attacker.example.invalid:881"),
    ("bus_path","//attacker.example.com"),
    ("metro_path","/stock/../../admin"),
    ("tenant_id","no spaces allowed"),
    ("bearer_token","with whitespace"),
])
def test_bad_private_target_tenant_or_secret_fails_before_http(monkeypatch,field,value):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","enterprise_pilot")
    called=[]
    trans=httpx.MockTransport(lambda req:called.append(req) or httpx.Response(200,json={"data":[]}))
    with pytest.raises(HongdouPilotDenied):
        inspect_private_inventory("bus",start_date="2026-11-21",end_date="2026-11-21",
                                  grant=grant(),config=replace(config(),**{field:value}),
                                  verify_enterprise_approval=lambda g:True,transport=trans)
    assert not called

@pytest.mark.parametrize("verifier",[
    None,lambda g:False,lambda g:None,lambda g: (_ for _ in ()).throw(RuntimeError("PDP unavailable"))
])
def test_missing_or_denied_independent_approval_blocks_before_network(monkeypatch,verifier):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","enterprise_pilot")
    called=[]
    trans=httpx.MockTransport(lambda req:called.append(req) or httpx.Response(200,json={"data":[]}))
    with pytest.raises(HongdouPilotDenied):
        inspect_private_inventory("bus",start_date="2026-11-21",end_date="2026-11-21",
                                  grant=grant(),config=config(),
                                  verify_enterprise_approval=verifier,transport=trans)
    assert not called

def test_wrong_tenant_grant_expires_or_scope_mismatch(monkeypatch):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","enterprise_pilot")
    trans=httpx.MockTransport(lambda req:httpx.Response(200,json={"data":[]}))
    for g in (replace(grant(),tenant_scope="OTHER-TENANT"),
              replace(grant(),expires_at_utc="2020-01-01T00:00:00Z"),
              replace(grant(),expires_at_utc="non-date")):
        with pytest.raises(HongdouPilotDenied):
            inspect_private_inventory("bus",start_date="2026-11-21",end_date="2026-11-21",
                                      grant=g,config=config(),
                                      verify_enterprise_approval=lambda _:True,transport=trans)

@pytest.mark.parametrize("status",[301,302,401,403,404,429,500])
def test_http_error_does_not_leak_server_message(monkeypatch,status):
    def fake(req):
        return httpx.Response(status,json={"error":"SECRET-TOKEN-CUSTOMER-NAME"},headers={"Location":"https://evil.example"})
    with pytest.raises(HongdouPilotDenied) as exc:
        fetch("bus",monkeypatch,httpx.MockTransport(fake))
    assert f"HTTP {status}" in str(exc.value)
    assert "SECRET-TOKEN" not in str(exc.value)
    assert "CI-FAKE" not in str(exc.value)

def test_huge_or_invalid_json_rejected_without_leak(monkeypatch):
    for body in (b"x"*280000,b"not json",b'{"data":"not list"}'):
        with pytest.raises(HongdouPilotDenied):
            fetch("metro",monkeypatch,httpx.MockTransport(
                lambda req:httpx.Response(200,content=body)))

def test_disallowed_query_injection_and_cross_endpoint_filters_rejected(monkeypatch):
    calls=[]
    trans=httpx.MockTransport(lambda req:calls.append(req) or httpx.Response(200,json={"data":[]}))
    for kwargs in ({"line_name":"100;drop"}, {"page_size":101},
                   {"start_date":"2026-11-22","end_date":"2026-11-21"}):
        data={"kind":"bus","start_date":"2026-11-21","end_date":"2026-11-21",
              "grant":grant(),"config":config(),"verify_enterprise_approval":lambda g:True,"transport":trans}
        data.update(kwargs)
        monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","enterprise_pilot")
        with pytest.raises((ValueError,HongdouPilotDenied)):
            inspect_private_inventory(**data)
    assert not calls


def test_single_digit_enterprise_tenant_id_is_valid_when_pdp_approves(monkeypatch):
    # Contract documents commonly use numeric tenants, including one digit.
    original=config()
    short_tenant=replace(original,tenant_id="7")
    short_grant=replace(grant(),tenant_scope="7")
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","enterprise_pilot")
    def fake(req):
        assert req.headers["tenant-id"]=="7"
        return httpx.Response(200,json={"data":{"list":[]}})
    result=inspect_private_inventory(
        "bus",start_date="2026-11-21",end_date="2026-11-21",
        grant=short_grant,config=short_tenant,
        verify_enterprise_approval=lambda g:True,
        transport=httpx.MockTransport(fake))
    assert result["metadata"]["sample_list_length"]==0
    assert result["real_stock_bookability_verified"] is False

@pytest.mark.parametrize("path",[
    "/stock/metro/page", "/stock/bus/other", "/stock/bus/page/extra",
    "/stock/bus/../page"
])
def test_bus_route_cannot_point_to_metro_or_other_action(monkeypatch,path):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","enterprise_pilot")
    touched=[]
    with pytest.raises(HongdouPilotDenied):
        inspect_private_inventory(
            "bus",start_date="2026-11-21",end_date="2026-11-21",
            grant=grant(),config=replace(config(),bus_path=path),
            verify_enterprise_approval=lambda _:True,
            transport=httpx.MockTransport(lambda req:touched.append(req) or httpx.Response(200,json={"data":[]})))
    assert not touched


def test_full_f12_authorization_header_works_without_double_bearer(monkeypatch):
    """F12 Network copies the entire 'Bearer <token>' value, not just the token."""
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","enterprise_pilot")
    token="CI-FAKE-ONE-TIME-TOKEN-DONT-USE"
    conf=replace(config(),tenant_id="1",bearer_token="Bearer "+token)
    approval=replace(grant(),tenant_scope="1")
    requests=[]
    def fake(req):
        requests.append(req)
        assert req.method=="GET"
        assert req.headers["Authorization"]=="Bearer "+token
        assert req.headers["tenant-id"]=="1"
        assert req.url.path=="/stock/bus/page"
        return httpx.Response(200,json={"code":0,"data":{"list":[]}})
    result=inspect_private_inventory(
        "bus",start_date="2026-11-21",end_date="2026-11-21",
        grant=approval,config=conf,verify_enterprise_approval=lambda g:True,
        transport=httpx.MockTransport(fake))
    assert len(requests)==1
    assert not result["real_stock_bookability_verified"]
    assert token not in repr(conf)
    assert token not in str(result)


def test_private_config_accepts_token_only_and_complete_header_equivalently():
    raw=replace(config(),bearer_token="CI-SYNTHETIC-TEST")
    full=replace(config(),bearer_token="Bearer CI-SYNTHETIC-TEST")
    assert raw.authorization_header()==full.authorization_header()
    assert full.authorization_header()=="Bearer CI-SYNTHETIC-TEST"


@pytest.mark.parametrize("bad_token",[
    "", "Bearer ", "Bearer Bearer CI-TEST", "<accessToken>",
    "Bearer <accessToken>", "Basic CI-TEST", "Bearer CI-TEST\nX-Injection: yes",
    "Bearer\tCI-TEST", " CI-TEST", "CI-TEST ", "CI TEST",
    "Bearer CI-TEST\r\nAnother: yes",
])
def test_placeholder_injection_and_doubled_bearer_are_denied_without_network(monkeypatch,bad_token):
    monkeypatch.setenv("COMPANYAGENT_DEPLOYMENT_MODE","enterprise_pilot")
    calls=[]
    config_bad=replace(config(),bearer_token=bad_token)
    with pytest.raises(HongdouPilotDenied):
        inspect_private_inventory("bus",start_date="2026-11-21",end_date="2026-11-21",
                                  grant=grant(),config=config_bad,
                                  verify_enterprise_approval=lambda g:True,
                                  transport=httpx.MockTransport(
                                      lambda req:calls.append(req) or httpx.Response(200,json={"data":[]})))
    assert not calls
    assert bad_token not in repr(config_bad) if bad_token else True
