"""Hongdou pilot request templates are offline only; no token or network."""
from __future__ import annotations
import pytest
from enterprise.hongdou_contract import (
    BUS_PATH, METRO_PATH, HOST, ORIGIN, request_spec,
    check_pilot_mode, inspect_mock_response, PilotApprovalRequired,
)

def test_two_fixed_https_port_881_inventory_paths():
    bus=request_spec("bus",start_date="2026-11-21",end_date="2026-11-21",line_name="100")
    metro=request_spec("metro",start_date="2026-11-21",end_date="2026-11-21",keyword="上海南站")
    assert bus["url"]==ORIGIN+BUS_PATH
    assert metro["url"]==ORIGIN+METRO_PATH
    assert bus["query"]["lineName"]=="100"
    assert metro["query"]["keyword"]=="上海南站"
    assert bus["requires_headers"]==("tenant-id","Authorization")
    assert all(not x["network_permitted"] for x in (bus,metro))
    assert all(not x["bookable"] for x in (bus,metro))
    assert all("sk-" not in x["preview_url"] for x in (bus,metro))


@pytest.mark.parametrize("kind",["coverage","visual","foo",None])
def test_unprovided_visualization_api_is_not_invented(kind):
    with pytest.raises(ValueError):
        request_spec(kind,start_date="2026-11-21",end_date="2026-11-21")


@pytest.mark.parametrize("fields",[
    {"start_date":"2026-11-22","end_date":"2026-11-21"},
    {"start_date":"2026-11-21","end_date":"2027-01-01"},
    {"start_date":"2026-11-21","end_date":"2026-11-21","page_size":101},
    {"start_date":"2026-11-21","end_date":"2026-11-21","page_no":0},
    {"start_date":"2026-11-21","end_date":"2026-11-21","line_name":"100; rm -rf /"},
    {"start_date":"2026-11-21","end_date":"2026-11-21","keyword":"站名"},
])
def test_bus_invalid_or_cross_endpoint_requests_rejected(fields):
    with pytest.raises(ValueError):
        request_spec("bus",**fields)


def test_metro_cannot_take_bus_line_filter():
    with pytest.raises(ValueError):
        request_spec("metro",start_date="2026-11-21",end_date="2026-11-21",line_name="100")


@pytest.mark.parametrize("mode",["local","cloud_synthetic","enterprise_pilot","production"])
def test_real_hongdou_calls_are_never_authorized_by_this_module(mode):
    with pytest.raises(PilotApprovalRequired):
        check_pilot_mode(mode)


def test_mock_response_contract_is_metadata_only():
    fake={"code":0,"msg":"synthetic","data":{"list":[
        {"actual_personal_info":"never print me","amount":999}
    ],"total":1}}
    x=inspect_mock_response(fake)
    assert x["sample_list_length"]==1
    assert x["data_fields"]==["list","total"]
    assert x["response_contract_confirmed"] is False
    assert x["quantity_semantics_confirmed"] is False
    assert x["real_request_sent"] is False
    assert "never print" not in str(x)


@pytest.mark.parametrize("bad",[
    {},[],{"data":123},{"data":None}
])
def test_unknown_payloads_fail_closed(bad):
    with pytest.raises(ValueError):
        inspect_mock_response(bad)
