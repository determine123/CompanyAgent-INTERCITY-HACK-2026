"""Opt-in private-network, read-only Hongdou contract probe.

NOT IMPORTED by the public FastAPI app. No raw inventory, data counts tied to
actual stock availability, auth token, response body or company URL is logged.
This module cannot establish enterprise approval by itself.
"""
from __future__ import annotations

import json
import os
import re
from typing import Mapping

import httpx

from .deployment_policy import deployment_mode
from .hongdou_contract import inspect_mock_response, request_spec

_HOST = re.compile(r"^(?=.{4,160}$)[a-z0-9][a-z0-9.-]*[a-z0-9]$")
_TICKET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{4,119}$")
_SEGMENT = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]{0,50}$")
_MAX_RESPONSE_BYTES = 512 * 1024


class PrivatePilotBlocked(ValueError):
    """A fail-closed and credential-free error message."""


def _route(value: object, kind: str) -> str:
    if not isinstance(value, str) or len(value) > 180 or any(c in value for c in ("?", "#", "%", "\\", "@")):
        raise PrivatePilotBlocked("Unapproved or malformed inventory route")
    parts = value.split("/")
    if len(parts) not in range(5, 10) or parts[0] != "" or not all(_SEGMENT.fullmatch(v) for v in parts[1:]):
        raise PrivatePilotBlocked("Inventory route does not match bounded path shape")
    if parts[-2:] != [kind, "page"]:
        raise PrivatePilotBlocked("Only read-only bus/metro inventory page routes are permitted")
    return value


def _config(env: Mapping[str, str], kind: str, owner_approved: bool,
            network_approved: bool) -> dict:
    if not owner_approved or not network_approved:
        raise PrivatePilotBlocked("Data owner and private network authorizations are required")
    if deployment_mode(env) != "local" or env.get("COMPANYAGENT_RAILWAY_PRIVATE_BACKEND") == "true":
        raise PrivatePilotBlocked("Hongdou live probe cannot run in any Railway or cloud_synthetic profile")
    host = env.get("HONGDOU_PILOT_HOST", "").strip().lower()
    allow = env.get("HONGDOU_PILOT_APPROVED_EGRESS_HOST", "").strip().lower()
    if not host or host != allow or not _HOST.fullmatch(host) or ".." in host:
        raise PrivatePilotBlocked("Inventory host must match the enterprise egress allowlist")
    if host.endswith((".invalid", ".localhost", ".local", ".example", ".test")) or host in {"localhost"}:
        raise PrivatePilotBlocked("Nonroutable placeholder and loopback hosts are forbidden")
    if any(label.isdigit() for label in host.split(".")) and all(label.isdigit() for label in host.split(".")):
        raise PrivatePilotBlocked("Raw IP addresses are forbidden")
    if "." not in host or ":" in host or "/" in host or host.startswith("-"):
        raise PrivatePilotBlocked("Inventory host must be a DNS hostname")
    tenant = env.get("HONGDOU_PILOT_TENANT_ID", "")
    if not re.fullmatch(r"[1-9][0-9]{0,9}", tenant):
        raise PrivatePilotBlocked("Approved tenant ID missing or invalid")
    token = env.get("HONGDOU_PILOT_ACCESS_TOKEN", "")
    if not isinstance(token, str) or not re.fullmatch(r"[!-~]{16,4096}", token):
        raise PrivatePilotBlocked("Approved short-lived access token is required")
    ticket = env.get("HONGDOU_PILOT_APPROVAL_REF", "")
    if not _TICKET.fullmatch(ticket):
        raise PrivatePilotBlocked("Approval reference missing or invalid; a reference does not prove sign-off")
    key = "HONGDOU_PILOT_BUS_PATH" if kind == "bus" else "HONGDOU_PILOT_METRO_PATH"
    return {"host": host, "tenant": tenant, "token": token,
            "route": _route(env.get(key), kind), "ticket": ticket}


def probe_hongdou_inventory(kind: str, *, start_date: str, end_date: str,
                            page_no: int = 1, page_size: int = 1,
                            line_name: str = "", keyword: str = "",
                            owner_approved: bool = False,
                            network_approved: bool = False,
                            env: Mapping[str, str] | None = None,
                            transport: httpx.BaseTransport | None = None) -> dict:
    """One real GET *only when explicitly invoked* in an approved private context.

    Normalizes no quantities until the enterprise provides a reviewed response
    schema. Even a HTTP 200 here does not establish bookable stock.
    """
    if kind not in ("bus", "metro"):
        raise PrivatePilotBlocked("Only bus and metro inventory page queries are supported")
    values = dict(os.environ if env is None else env)
    config = _config(values, kind, owner_approved, network_approved)
    spec = request_spec(kind, start_date=start_date, end_date=end_date,
                        page_no=page_no, page_size=page_size,
                        line_name=line_name, keyword=keyword)
    url = "https://" + config["host"] + ":881" + config["route"]
    headers = {
        "tenant-id": config["tenant"],
        "Authorization": "Bearer " + config["token"],
        "Accept": "application/json",
    }
    try:
        # No proxy inherited from ambient env, no redirects to third-party
        # hosts, strict TLS and no retries. Corporate firewall must pin egress.
        with httpx.Client(transport=transport, timeout=httpx.Timeout(8.0),
                          follow_redirects=False, trust_env=False,
                          verify=True) as client:
            with client.stream("GET", url, headers=headers, params=spec["query"]) as response:
                code = response.status_code
                if code != 200:
                    # Never include provider body, request headers, hostname, or token.
                    raise PrivatePilotBlocked(f"Private inventory API returned HTTP {code}; check enterprise-owned logs")
                content_type = response.headers.get("content-type", "").lower()
                if "application/json" not in content_type and "+json" not in content_type:
                    raise PrivatePilotBlocked("Inventory response is not JSON")
                received = bytearray()
                for chunk in response.iter_bytes():
                    if len(received) + len(chunk) > _MAX_RESPONSE_BYTES:
                        raise PrivatePilotBlocked("Inventory response exceeds bounded inspection size")
                    received.extend(chunk)
            try:
                payload = json.loads(received.decode("utf-8"))
                schema = inspect_mock_response(payload)
            except (ValueError, TypeError, UnicodeError):
                raise PrivatePilotBlocked("Inventory JSON envelope not compatible with provisional schema") from None
    except PrivatePilotBlocked:
        raise
    except httpx.TimeoutException:
        raise PrivatePilotBlocked("Private inventory API timeout") from None
    except httpx.RequestError:
        raise PrivatePilotBlocked("Private inventory API network or TLS failure") from None
    except httpx.HTTPError:
        raise PrivatePilotBlocked("Private inventory API transport failed") from None
    return {
        "source": "hongdou_private_pilot", "media": kind,
        "probe_http_status": 200, "query_window": [start_date, end_date],
        "requested_page_size": page_size, "data_fields": schema["data_fields"],
        "envelope_fields": schema["envelope_fields"],
        "sample_list_length": schema["sample_list_length"],
        "response_contract_confirmed": False, "quantity_semantics_confirmed": False,
        "real_stock_verified": False, "bookable": False, "model_exported": False,
        "database_written": False,
        "approval_independently_verified": False,
        "next_gate": "verify data-owner sign-off, field dictionary, and availability semantics inside enterprise network",
    }
