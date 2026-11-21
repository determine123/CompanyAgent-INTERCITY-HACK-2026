"""Validate the rendered Docker Compose config BEFORE public demo deployment.

No cloud resources are created. This validates syntax + security invariants only.
This cannot replace host firewall review, TLS check, vulnerability scanning, WAF,
private network/secret manager approval, or a formal enterprise signoff.
"""
from __future__ import annotations
import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path

def validate(cfg:dict,*,ci:bool=False)->list[str]:
    errors=[]
    services=cfg.get("services",{})
    app=services.get("companyagent") or {}
    proxy=services.get("caddy") or {}
    env=app.get("environment") or {}
    penv=proxy.get("environment") or {}
    domain=penv.get("PUBLIC_DEMO_DOMAIN","")
    if not isinstance(domain,str):domain=""
    if not ci:
        if domain in {"localhost","127.0.0.1","demo.example.com"} or not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",domain):
            errors.append("A real publicly controlled DNS hostname is required for ACME HTTPS")
        if domain.endswith((".invalid",".test",".example",".local")):
            errors.append("A documentation or private suffix cannot be used for public ACME HTTPS")
        try:
            ipaddress.ip_address(domain)
        except ValueError:
            pass
        else:
            errors.append("Direct IP address cannot be used as the validated production hostname")
    if app.get("ports") or app.get("network_mode")=="host":
        errors.append("Backend MUST NOT publish a host port")
    if env.get("COMPANYAGENT_DEPLOYMENT_MODE")!="cloud_synthetic":
        errors.append("Only cloud_synthetic mode is allowed")
    if str(env.get("COMPANYAGENT_AUTO_SYNC","")).lower() not in ("false","0"):
        errors.append("Automatic enterprise data source sync must remain disabled")
    if str(env.get("COMPANYAGENT_COOKIE_SECURE","")).lower() != "true":
        errors.append("Public HTTPS demo requires Secure session cookies")
    if str(env.get("COMPANYAGENT_REAL_DATA_ENABLED","")).lower() not in ("false","0"):
        errors.append("Real corporate data must be forbidden in the public demo")
    if str(env.get("COMPANYAGENT_ALLOWED_DATA_HOSTS","")):
        errors.append("Corporate API host allowlist must be empty")
    for name in ("TOKENDANCE_API_KEY","B1X_API_KEY","COMPANYAGENT_HONGDOU_TOKEN"):
        if env.get(name):
            errors.append("The public demo must not receive model/vendor API credentials")
    if not app.get("read_only") or "ALL" not in app.get("cap_drop",[]):
        errors.append("Backend requires read-only root filesystem and all Linux capabilities dropped")
    if not app.get("tmpfs") or not any("/app/runtime" in str(v) for v in app["tmpfs"]):
        errors.append("Ephemeral runtime tmpfs is required")
    password=env.get("COMPANYAGENT_ADMIN_PASSWORD","")
    if not isinstance(password,str) or len(password)<20 or "REPLACE" in password:
        errors.append("Distinct strong application demo password required")
    username=penv.get("PUBLIC_DEMO_USER","")
    if not isinstance(username,str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{2,31}",username):
        errors.append("Invalid proxy Basic Auth username")
    h=penv.get("PUBLIC_DEMO_BCRYPT_HASH","")
    # Docker Compose may escape bcrypt dollar signs in rendered output.
    candidate=h.replace("$$","$") if isinstance(h,str) else ""
    if not re.fullmatch(r"\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}",candidate):
        errors.append("Caddy Basic Auth requires bcrypt (length="+str(len(h) if isinstance(h,str) else 0)+", escaped_dollars="+str("$$" in h if isinstance(h,str) else False)+")")
    if not (cfg.get("networks") or {}).get("backend",{}).get("internal",False):
        errors.append("Backend network must be Docker internal")
    if "backend" not in app.get("networks",{}):
        errors.append("Backend service must use private backend network")
    if not all(n in proxy.get("networks",{}) for n in ("edge","backend")):
        errors.append("Proxy must bridge the edge and internal backend networks")
    port_targets={str(p.get("target")) for p in proxy.get("ports",[]) if isinstance(p,dict)}
    if not {"80","443"}<=port_targets:
        errors.append("HTTPS proxy must publish TCP 80/443 for Caddy ACME")
    return errors

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("compose_json",type=Path,help="Rendered compose JSON, not the raw YAML")
    parser.add_argument("--ci",action="store_true",help="Allow test-only http domain in ephemeral GitHub runner")
    args=parser.parse_args()
    try:
        raw=args.compose_json.read_bytes()
        if len(raw)>100_000:raise ValueError()
        cfg=json.loads(raw)
        errors=validate(cfg,ci=args.ci)
    except (OSError,ValueError,UnicodeError):
        errors=["Compose config unavailable or invalid"]
    if errors:
        print(json.dumps({"status":"BLOCKED","checks_failed":errors},ensure_ascii=False))
        return 2
    print(json.dumps({"status":"CONFIG_CHECK_PASS","public_demo_only":True,"production_ready":False},ensure_ascii=False))
    return 0

if __name__=="__main__":sys.exit(main())
