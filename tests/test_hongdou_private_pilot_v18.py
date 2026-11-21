"""Private Hongdou bus/metro contract proof using MockTransport only, no real network."""
from __future__ import annotations

import json
import httpx
import pytest

from enterprise.hongdou_private_pilot import (
    PrivatePilotBlocked, probe_hongdou_inventory,
)

TOKEN="synthetic-testing-token-not-a-secret"
HOST="approved-inventory.example.org"
def approved_env():
    return {
        "COMPANYAGENT_DEPLOYMENT_MODE":"local",
        "HONGDOU_PILOT_HOST":HOST,
        "HONGDOU_PILOT_APPROVED_EGRESS_HOST":HOST,
        "HONGDOU_PILOT_BUS_PATH":"/admin/api/media/bus/page",
        "HONGDOU_PILOT_METRO_PATH":"/admin/api/media/metro/page",
        "HONGDOU_PILOT_TENANT_ID":"1",
        "HONGDOU_PILOT_ACCESS_TOKEN":TOKEN,
        "HONGDOU_PILOT_APPROVAL_REF":"DO-TICKET-12345",
    }

def probe(kind="bus",env=None,transport=None,owner=True,network=True,**kw):
    return probe_hongdou_inventory(
        kind,start_date="2026-11-21",end_date="2026-11-21",
        env=approved_env() if env is None else env,transport=transport,
        owner_approved=owner,network_approved=network,**kw)

@pytest.mark.parametrize("kind,filter_key,filter_value",[
    ("bus","line_name","100"),
    ("metro","keyword","Shanghai South"),
])
def test_authorized_private_contract_inspection_not_stock_availability(kind,filter_key,filter_value):
    requests=[]
    def fake(req):
        requests.append(req)
        return httpx.Response(200,json={
            "code":0,"data":{"list":[{"personal_info":"NEVER_EMIT_ROW_DATA"}],"total":99}
        })
    x=probe(kind,transport=httpx.MockTransport(fake),**{filter_key:filter_value})
    assert len(requests)==1
    req=requests[0]
    assert req.method=="GET"
    assert req.url.scheme=="https" and req.url.host==HOST and req.url.port==881
    assert req.url.path==f"/admin/api/media/{kind}/page"
    assert req.headers["tenant-id"]=="1"
    assert req.headers["Authorization"]=="Bearer "+TOKEN
    assert req.url.params["pageSize"]=="1"
    assert req.url.params["startDate"]=="2026-11-21"
    assert req.url.params["endDate"]=="2026-11-21"
    assert req.url.params["lineName" if kind=="bus" else "keyword"]==filter_value
    assert x["probe_http_status"]==200
    assert x["response_contract_confirmed"] is False
    assert x["quantity_semantics_confirmed"] is False
    assert x["real_stock_verified"] is False
    assert x["bookable"] is False
    assert x["model_exported"] is False
    assert x["database_written"] is False
    assert "NEVER_EMIT_ROW_DATA" not in json.dumps(x)
    assert TOKEN not in json.dumps(x)
    assert HOST not in json.dumps(x)

@pytest.mark.parametrize("owner,network",[(False,False),(False,True),(True,False)])
def test_no_request_when_real_data_or_network_approval_missing(owner,network):
    called=[]
    def fake(req):
        called.append(1);return httpx.Response(200,json={"data":[]})
    with pytest.raises(PrivatePilotBlocked,match="authorizations"):
        probe(owner=owner,network=network,transport=httpx.MockTransport(fake))
    assert not called

@pytest.mark.parametrize("invalid",[
    {"COMPANYAGENT_DEPLOYMENT_MODE":"cloud_synthetic"},
    {"COMPANYAGENT_RAILWAY_PRIVATE_BACKEND":"true"},
    {"HONGDOU_PILOT_HOST":"127.0.0.1","HONGDOU_PILOT_APPROVED_EGRESS_HOST":"127.0.0.1"},
    {"HONGDOU_PILOT_HOST":"localhost","HONGDOU_PILOT_APPROVED_EGRESS_HOST":"localhost"},
    {"HONGDOU_PILOT_HOST":"evil.example.org"},
    {"HONGDOU_PILOT_HOST":"example.invalid","HONGDOU_PILOT_APPROVED_EGRESS_HOST":"example.invalid"},
    {"HONGDOU_PILOT_BUS_PATH":"/admin/api/media/metro/page"},
    {"HONGDOU_PILOT_METRO_PATH":"/admin/api/media/bus/page"},
    {"HONGDOU_PILOT_BUS_PATH":"/admin/api/media/bus/page?other=true"},
    {"HONGDOU_PILOT_BUS_PATH":"/admin/api/media/bus/../page"},
    {"HONGDOU_PILOT_ACCESS_TOKEN":""},
    {"HONGDOU_PILOT_APPROVAL_REF":""},
    {"HONGDOU_PILOT_TENANT_ID":"0"},
])
def test_invalid_private_config_fails_without_any_request(invalid):
    env=approved_env();env.update(invalid)
    called=[]
    def fake(req):
        called.append(1);return httpx.Response(200,json={"data":[]})
    with pytest.raises(PrivatePilotBlocked):
        probe(kind="metro" if "METRO_PATH" in " ".join(invalid) else "bus",
              env=env,transport=httpx.MockTransport(fake))
    assert not called

@pytest.mark.parametrize("code",[301,302,307,400,401,403,404,429,500,503])
def test_gateway_refusal_never_leaks_provider_response_or_headers(code):
    def fake(req):
        return httpx.Response(code,json={"error":{"message":TOKEN+" sensitive raw response"}})
    with pytest.raises(PrivatePilotBlocked,match=f"HTTP {code}") as err:
        probe(transport=httpx.MockTransport(fake))
    assert TOKEN not in str(err.value)
    assert "sensitive" not in str(err.value)

def test_unrecognized_json_envelope_is_blocked():
    with pytest.raises(PrivatePilotBlocked,match="not compatible"):
        probe(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={"unexpected":123})))

def test_non_json_content_type_is_blocked():
    with pytest.raises(PrivatePilotBlocked,match="not JSON"):
        probe(transport=httpx.MockTransport(lambda req:httpx.Response(200,content=b"sample",headers={"content-type":"text/plain"})))

def test_oversize_response_is_blocked():
    big="A"*(513*1024)
    with pytest.raises(PrivatePilotBlocked,match="exceeds"):
        probe(transport=httpx.MockTransport(lambda req:httpx.Response(200,content=big,headers={"content-type":"application/json"})))

def test_transport_errors_are_redacted():
    def fake(req):
        raise httpx.ConnectError("synthetic-testing-token-not-a-secret could not connect")
    with pytest.raises(PrivatePilotBlocked,match="network or TLS") as err:
        probe(transport=httpx.MockTransport(fake))
    assert TOKEN not in str(err.value)

@pytest.mark.parametrize("kwargs",[
    {"page_size":101},
    {"line_name":"a;curl -X POST"},
    {"start_date":"wrong"},
    {"page_no":0},
])
def test_unbounded_requests_fail_before_network(kwargs):
    opts={"start_date":"2026-11-21","end_date":"2026-11-21",**kwargs}
    with pytest.raises(ValueError):
        probe_hongdou_inventory("bus",env=approved_env(),transport=httpx.MockTransport(
          lambda req: (_ for _ in ()).throw(AssertionError("no calls"))),
          owner_approved=True,network_approved=True,**opts)

def test_unknown_media_is_refused():
    with pytest.raises(PrivatePilotBlocked,match="Only bus and metro"):
        probe(kind="visual",transport=httpx.MockTransport(lambda req: httpx.Response(200,json={})))
