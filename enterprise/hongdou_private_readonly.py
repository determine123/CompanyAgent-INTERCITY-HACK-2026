"""Company-private Hongdou read-only inventory probe; NOT wired into public API.

This adapter can only run in a separately approved enterprise_pilot process.
The current CompanyAgent server explicitly REJECTS enterprise_pilot at startup.
An external enterprise PDP must independently verify approval evidence, tenant,
network isolation and TTL before every request. There is deliberately NO
"enable=true" environment switch that would bypass the PDP.

Only metadata (field names and list lengths) is returned until a company data
owner approves a redacted response schema and defines real availability
semantics. No raw records, media rows, tokens or tenant IDs are logged.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit
import httpx

from .hongdou_contract import inspect_mock_response,request_spec
from .deployment_policy import deployment_mode

class HongdouPilotDenied(RuntimeError):
    pass

@dataclass(frozen=True)
class EnterpriseGrant:
    data_owner_ticket: str
    security_ticket: str
    tenant_scope: str
    expires_at_utc: str

    def validate_structure(self, tenant:str):
        # Ticket references are just untrusted metadata; an external PDP MUST
        # check the actual approved tickets. This code does not sign or issue grants.
        for item in (self.data_owner_ticket,self.security_ticket,self.tenant_scope):
            if not isinstance(item,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{4,119}",item):
                raise HongdouPilotDenied("Enterprise grant references invalid")
        if self.tenant_scope!=tenant:raise HongdouPilotDenied("Grant tenant scope mismatch")
        try:
            expiry=dt.datetime.fromisoformat(self.expires_at_utc.replace("Z","+00:00"))
        except (ValueError,AttributeError):
            raise HongdouPilotDenied("Grant expiry invalid") from None
        if expiry.tzinfo is None or expiry<=dt.datetime.now(dt.timezone.utc):
            raise HongdouPilotDenied("Enterprise approval expired or lacks timezone")

@dataclass(frozen=True)
class PrivateServiceConfig:
    origin: str
    approved_host: str
    bus_path: str
    metro_path: str
    tenant_id: str
    bearer_token: str

    @staticmethod
    def from_env(env=None):
        e=os.environ if env is None else env
        return PrivateServiceConfig(
            origin=e.get("HONGDOU_PRIVATE_ORIGIN",""),
            approved_host=e.get("HONGDOU_PRIVATE_APPROVED_HOST",""),
            bus_path=e.get("HONGDOU_PRIVATE_BUS_ROUTE",""),
            metro_path=e.get("HONGDOU_PRIVATE_METRO_ROUTE",""),
            tenant_id=e.get("HONGDOU_PRIVATE_TENANT_ID",""),
            bearer_token=e.get("HONGDOU_PRIVATE_BEARER_TOKEN",""),
        )

    def validate(self):
        u=urlsplit(self.origin)
        if (u.scheme!="https" or not u.hostname or u.hostname!=self.approved_host
            or u.username or u.password or u.query or u.fragment or u.path not in ("","/")
            or u.port not in (None,443,881)):
            raise HongdouPilotDenied("Private endpoint must be exact approved HTTPS host/port")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{1,63}",self.tenant_id):
            raise HongdouPilotDenied("Tenant ID invalid")
        if not self.bearer_token or len(self.bearer_token)>4096 or any(ord(ch)<33 for ch in self.bearer_token):
            raise HongdouPilotDenied("Private token invalid")
        for path in (self.bus_path,self.metro_path):
            if not re.fullmatch(r"/[A-Za-z0-9/_-]{1,180}",path) or "//" in path or ".." in path:
                raise HongdouPilotDenied("Private stock routes must be fixed approved paths")

def inspect_private_inventory(kind:str, *, start_date:str,end_date:str,
                              grant:EnterpriseGrant,config:PrivateServiceConfig,
                              verify_enterprise_approval:Callable[[EnterpriseGrant],bool]|None,
                              transport:httpx.BaseTransport|None=None,
                              page_no:int=1,page_size:int=20,
                              line_name:str="",keyword:str="") -> dict:
    """Make exactly one bounded GET only after enterprise PDP authorizes it.

    transport is injectable for mock-only regressions. No retries, redirects,
    arbitrary URLs, write endpoints, raw row results or model export.
    """
    if deployment_mode()!="enterprise_pilot":
        raise HongdouPilotDenied("Real Hongdou access is disabled outside enterprise private pilot")
    if not isinstance(grant,EnterpriseGrant) or not isinstance(config,PrivateServiceConfig):
        raise HongdouPilotDenied("Private config or grant missing")
    config.validate()
    grant.validate_structure(config.tenant_id)
    if verify_enterprise_approval is None or not callable(verify_enterprise_approval):
        raise HongdouPilotDenied("Independent company approval verifier required")
    try:
        authorized=verify_enterprise_approval(grant)
    except Exception:
        authorized=False
    if authorized is not True:
        raise HongdouPilotDenied("Enterprise data-owner/security approval not verified")

    spec=request_spec(kind,start_date=start_date,end_date=end_date,
                      page_no=page_no,page_size=page_size,line_name=line_name,keyword=keyword)
    path=config.bus_path if kind=="bus" else config.metro_path
    url=config.origin.rstrip("/")+path
    headers={"Authorization":"Bearer "+config.bearer_token,
             "tenant-id":config.tenant_id,"Accept":"application/json"}
    try:
        with httpx.Client(transport=transport,verify=True,trust_env=False,
                          follow_redirects=False,timeout=10.0) as client:
            with client.stream("GET",url,params=spec["query"],headers=headers) as response:
                if response.status_code!=200:
                    raise HongdouPilotDenied(f"Private inventory gateway HTTP {response.status_code} (no response body retained)")
                chunks=[];total=0
                for chunk in response.iter_bytes(32768):
                    total+=len(chunk)
                    if total>262144:raise HongdouPilotDenied("Private response exceeds bounded probe size")
                    chunks.append(chunk)
        payload=json.loads(b"".join(chunks).decode("utf-8"))
        evidence=inspect_mock_response(payload)
    except HongdouPilotDenied:
        raise
    except (httpx.HTTPError,UnicodeError,json.JSONDecodeError,ValueError,TypeError):
        raise HongdouPilotDenied("Private inventory response/network invalid; raw data suppressed") from None
    return {
        "kind":kind,"transport":"private_enterprise_gateway_readonly",
        "response_contract_confirmed":False,
        "quantity_semantics_confirmed":False,
        "real_stock_bookability_verified":False,
        "remote_model_called":False,
        "database_written":False,
        "record_values_returned":False,
        "metadata":evidence,
        "next_action":"enterprise owner must confirm redacted response schema, availability semantics and approval evidence",
    }
