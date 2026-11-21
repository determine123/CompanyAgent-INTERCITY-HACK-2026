#!/usr/bin/env python3
"""Single-use REAL HTTPS Railway public acceptance probe. Synthetic data only.

Run only in an approved short-lived private Railway tester service.
Credentials are read exclusively from environment variables; none are logged,
copied to GitHub/CI, stored in artifacts, or inserted in the URL.
"""
from __future__ import annotations
import base64
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PREFIX="https://"
ALLOWED_HOST_SUFFIX=".up.railway.app"

class AcceptanceFailed(RuntimeError):
    pass

def check_env(env):
    raw=env.get("RAILWAY_LIVE_BASE","").rstrip("/")
    u=urllib.parse.urlsplit(raw)
    if u.scheme!="https" or not u.hostname or not u.hostname.endswith(ALLOWED_HOST_SUFFIX) or u.port or u.username or u.password or u.query or u.fragment or u.path:
        raise AcceptanceFailed("URL must be a plain Railway-managed HTTPS hostname")
    for name in ("RAILWAY_LIVE_GATEWAY_USER","RAILWAY_LIVE_GATEWAY_PASSWORD","RAILWAY_LIVE_APP_PASSWORD"):
        if not env.get(name):raise AcceptanceFailed("Missing private test credentials")
    if env.get("RAILWAY_LIVE_EXPLICIT_CONSENT")!="synthetic-only":
        raise AcceptanceFailed("Missing explicit synthetic-only permission")
    return raw

def run():
    base=check_env(os.environ)
    jar=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    user=os.environ["RAILWAY_LIVE_GATEWAY_USER"]
    password=os.environ["RAILWAY_LIVE_GATEWAY_PASSWORD"]
    basic="Basic "+base64.b64encode((user+":"+password).encode()).decode("ascii")

    def request(method,path,body=None,*,auth=False,csrf=None):
        if not path.startswith("/") or path.startswith("//"):raise AcceptanceFailed("Invalid local probe path")
        headers={"Accept":"application/json"}
        if auth:headers["Authorization"]=basic
        if body is not None:headers["Content-Type"]="application/json"
        if csrf:headers["X-CSRF-Token"]=csrf
        data=json.dumps(body,ensure_ascii=False).encode("utf-8") if body is not None else None
        req=urllib.request.Request(base+path,data=data,headers=headers,method=method)
        try:
            with opener.open(req,timeout=18) as res:
                status=res.status
                raw=res.read(1000000)
                return status,raw,dict(res.headers)
        except urllib.error.HTTPError as e:
            e.read(4096) # intentionally discard response, never log details
            return e.code,b"",dict(e.headers)
        except (OSError,ValueError,TimeoutError):
            raise AcceptanceFailed("Railway HTTPS request failed; consult provider network logs") from None

    checks={}
    def expect(name,status,want):
        checks[name]=status
        if status!=want:raise AcceptanceFailed(f"{name}: expected HTTP {want}, got {status}")

    # Outer proxy authentication and prohibited network paths.
    for name,path in (("anonymous_workbench","/enterprise/"),("anonymous_api","/enterprise/api/status"),("anonymous_health","/healthz")):
        status,_,_=request("GET",path)
        expect(name,status,401)
    # The correct realm user and wrong password must not bypass authentication.
    wrong="Basic "+base64.b64encode((user+":wrong-password-for-security-check").encode()).decode()
    req=urllib.request.Request(base+"/enterprise/",headers={"Authorization":wrong},method="GET")
    try:
        with opener.open(req,timeout=18) as r:status=r.status
    except urllib.error.HTTPError as e:
        status=e.code
    expect("wrong_gateway_password",status,401)

    status,html,_=request("GET","/enterprise/",auth=True)
    expect("authenticated_workbench_html",status,200)
    if b"CompanyAgent" not in html:raise AcceptanceFailed("Workbench HTML identity missing")
    status,js,_=request("GET","/enterprise/app.js",auth=True)
    expect("authenticated_workbench_javascript",status,200)

    status,_,_=request("GET","/enterprise/api/me",auth=True)
    expect("application_second_login_required",status,401)
    status,raw,headers=request("POST","/enterprise/api/auth/login",
                               {"username":"admin","password":os.environ["RAILWAY_LIVE_APP_PASSWORD"]},
                               auth=True)
    expect("application_login",status,200)
    try:
        payload=json.loads(raw)
        csrf=payload["csrf"]
        if payload["user"]["role"]!="admin" or not csrf:
            raise KeyError()
    except (ValueError,KeyError,TypeError):
        raise AcceptanceFailed("App login response contract invalid") from None
    if not any(cookie.secure for cookie in jar):
        raise AcceptanceFailed("Secure login cookie absent")

    status,raw,_=request("GET","/enterprise/api/me",auth=True)
    expect("session_cookie_auth",status,200)
    status,raw,_=request("GET","/enterprise/api/status",auth=True)
    expect("deployment_status",status,200)
    info=json.loads(raw)
    if info.get("deployment_mode")!="cloud_synthetic" or info.get("fixed_industry")!="食品饮料":
        raise AcceptanceFailed("Cloud synthetic single-industry policy invalid")
    if info.get("hongdou_real_api_connected") is not False or info.get("visual_coverage_api_available") is not False:
        raise AcceptanceFailed("Public demo must not claim real stock/visual APIs")
    status,raw,_=request("GET","/enterprise/api/datasets",auth=True)
    expect("synthetic_datasets",status,200)
    inv=[x for x in json.loads(raw).get("items",[]) if x.get("kind")=="inventory" and x.get("origin")=="demo_synthetic_repo_seed"]
    if not inv:raise AcceptanceFailed("Public demo lacks seeded fictional inventory")
    status,raw,_=request("GET","/enterprise/api/agents",auth=True)
    expect("default_agent",status,200)
    agents=json.loads(raw).get("items",[])
    if not agents:raise AcceptanceFailed("No allowed Agent available for demo")

    # Every dangerous route must be denied, even with a valid application CSRF token.
    for name,method,path in (
        ("legacy_api_blocked","GET","/api/demo"),
        ("upload_blocked","POST","/enterprise/api/datasets/upload"),
        ("sources_blocked","POST","/enterprise/api/sources"),
        ("user_creation_blocked","POST","/enterprise/api/users"),
        ("cross_industry_benchmark_blocked","POST","/enterprise/api/agents/1/benchmark"),
    ):
        status,_,_=request(method,path,body={} if method=="POST" else None,auth=True,csrf=csrf)
        expect(name,status,403)

    payload={
        "agent_id":agents[0]["id"],
        "industry":"食品饮料","brand":"CI-虚构饮料品牌",
        "brief":"合成演示：食品饮料 2027 年 5 月，200 万元预算，公交/地铁投放参考情景。",
        "budget_wan":200,"start_date":"2027-05-01","weeks":4,
        "landmark":"正大广场","medium":"both","coverage_only":False,
    }
    status,_,_=request("POST","/enterprise/api/runs",
                       {**payload,"industry":"银行保险"},auth=True,csrf=csrf)
    expect("cross_industry_submit_denied",status,400)

    status,raw,_=request("POST","/enterprise/api/runs",payload,auth=True,csrf=csrf)
    expect("synthetic_proposal_generated",status,200)
    try:
        result=json.loads(raw)
        run_id=int(result["run_id"])
        plan=result["plan"]
        if result.get("industry","食品饮料")!="食品饮料":raise ValueError()
        if not isinstance(plan,dict) or "spent_wan" not in plan:
            raise ValueError()
    except (ValueError,KeyError,TypeError):
        raise AcceptanceFailed("Generated proposal schema invalid") from None
    status,detail,_=request("GET",f"/enterprise/api/runs/{run_id}",auth=True)
    expect("proposal_saved_and_readable",status,200)
    if json.loads(detail).get("id")!=run_id:
        raise AcceptanceFailed("Frozen run ID mismatch")
    status,proposal_html,_=request("GET",f"/enterprise/api/runs/{run_id}/proposal.html",auth=True)
    expect("proposal_html_export",status,200)
    if len(proposal_html)<100:raise AcceptanceFailed("Exported proposal HTML empty")

    print(json.dumps({
        "verification":"PASS",
        "transport":"real_railway_https",
        "scenario":"synthetic_food_and_beverage_only",
        "checks":checks,
        "run_id":run_id,
        "example_budget_wan":200,
        "real_hongdou_data_accessed":False,
        "external_model_called":False,
        "production_migration_authorized":False,
    },ensure_ascii=False,sort_keys=True))
    return 0

if __name__=="__main__":
    try:sys.exit(run())
    except AcceptanceFailed as e:
        print("RAILWAY_E2E=FAIL; "+str(e),file=sys.stderr)
        sys.exit(2)
