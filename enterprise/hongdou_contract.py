"""Hongdou stock endpoint contract. ZERO live calls without approved private pilot.

The only available source note provides two GET paths and required headers;
it does NOT provide confirmed JSON schema, data contracts, scopes, or approval.
This module builds fixed, bounded request specs and parses mock responses
for offline validation; it cannot send real requests.
"""
from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urlencode
from typing import Any
from .deployment_policy import deployment_mode

BUS_PATH="/REPLACE_WITH_APPROVED_BUS_STOCK_ROUTE"
METRO_PATH="/REPLACE_WITH_APPROVED_METRO_STOCK_ROUTE"
HOST="approved-internal-inventory.example.invalid"
ORIGIN="https://approved-internal-inventory.example.invalid:881"
KINDS={"bus":BUS_PATH,"metro":METRO_PATH}
_SAFE_QUERY=re.compile(r"^[\w\u4e00-\u9fff\s()（）·/-]{0,70}$",re.UNICODE)

class PilotApprovalRequired(ValueError):
    pass

def _date(value:str)->dt.date:
    if not isinstance(value,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",value):
        raise ValueError("date must be ISO YYYY-MM-DD")
    return dt.date.fromisoformat(value)

def request_spec(kind:str, *, start_date:str, end_date:str,
                 page_no:int=1,page_size:int=20,
                 line_name:str="",keyword:str="")->dict[str,Any]:
    """Produce a NONFUNCTIONAL PLACEHOLDER URL (no auth or tenant headers). Never fetch it.

    The actual company host, route and tenant configuration must stay in a
    separately approved private deployment, NEVER in public GitHub source.
    """
    if kind not in KINDS: raise ValueError("only bus/metro stock permitted")
    start,end=_date(start_date),_date(end_date)
    if end<start or (end-start).days>31:
        raise ValueError("inventory query dates must be ordered within 31 days")
    if type(page_no) is not int or type(page_size) is not int or not 1<=page_no<=100 or not 1<=page_size<=100:
        raise ValueError("pagination must be bounded")
    for term in (line_name,keyword):
        if not isinstance(term,str) or not _SAFE_QUERY.fullmatch(term):
            raise ValueError("invalid filter characters or size")
    if kind=="bus" and keyword: raise ValueError("metro keyword is forbidden for bus")
    if kind=="metro" and line_name: raise ValueError("bus lineName is forbidden for metro")
    params={"pageNo":page_no,"pageSize":page_size,"startDate":start.isoformat(),"endDate":end.isoformat()}
    if kind=="bus" and line_name:params["lineName"]=line_name
    if kind=="metro" and keyword:params["keyword"]=keyword
    return {
       "method":"GET",
       "url":ORIGIN+KINDS[kind],
       "query":params,
       "requires_headers":("tenant-id","Authorization"),
       "network_permitted":False,
       "preview_url":ORIGIN+KINDS[kind]+"?"+urlencode(params),
       "verified_inventory":False,
       "bookable":False,
    }

def check_pilot_mode(mode:str|None=None)->None:
    """Hard fail closed until enterprise_pilot is implemented with external approvals."""
    current=deployment_mode() if mode is None else mode
    if current not in ("local", "cloud_synthetic"):
        raise PilotApprovalRequired("enterprise pilot runtime not approved for real API requests")
    raise PilotApprovalRequired("Hongdou live API access is not enabled; data owner, tenant, SSO and private network approval required")

def inspect_mock_response(payload:object)->dict[str,Any]:
    """Inspect only structural metadata, not customer/item values or stock semantics."""
    if not isinstance(payload,dict) or len(payload)>40:
        raise ValueError("unexpected Hongdou JSON response envelope")
    if "data" not in payload:
        raise ValueError("data field absent; request an authorized redacted response schema")
    data=payload["data"]
    if not isinstance(data,(dict,list)):
        raise ValueError("unrecognized data payload type")
    if isinstance(data,list):
        count=len(data)
        keys=[]
    else:
        keys=sorted(k for k in data if isinstance(k,str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,40}",k))
        values=[value for value in data.values() if isinstance(value,list)]
        count=max((len(v) for v in values),default=0)
    return {
        "envelope_fields":sorted(k for k in payload if isinstance(k,str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,40}",k)),
        "data_fields":keys,
        "sample_list_length":count,
        "response_contract_confirmed":False,
        "quantity_semantics_confirmed":False,
        "official_bookable_or_reserved":False,
        "real_request_sent":False,
    }
