"""Fail-closed Railway public demo launcher.

The only Railway-public HTTP port is owned by Caddy. FastAPI binds strictly
to loopback 127.0.0.1:8765. This is synthetic-only, not an enterprise runtime.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.deployment_policy import validate_deployment

CADDY=Path("/usr/local/bin/caddy")
CADDYFILE=ROOT/"deploy"/"railway"/"Caddyfile"
BCRYPT=re.compile(r"^\$2[aby]\$\d\d\$[A-Za-z0-9./]{53}$")
USERNAME=re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,31}$")

def validate_public_config(values=None):
    env=dict(os.environ if values is None else values)
    try:
        validate_deployment(env)
    except RuntimeError:
        raise RuntimeError("Railway public demo requires synthetic-only mode without company/model keys") from None
    if env.get("COMPANYAGENT_DEPLOYMENT_MODE") != "cloud_synthetic":
        raise RuntimeError("Deployment mode must explicitly be cloud_synthetic")
    if env.get("COMPANYAGENT_COOKIE_SECURE") != "true":
        raise RuntimeError("Secure session cookies required")
    try:
        port=int(env.get("PORT","8080"))
    except (ValueError,TypeError):
        raise RuntimeError("Railway PORT invalid") from None
    if not 1024 <= port <= 65535 or port == 8765:
        raise RuntimeError("Railway proxy must bind a dedicated unprivileged port")
    if not USERNAME.fullmatch(env.get("PUBLIC_DEMO_USER","")):
        raise RuntimeError("PUBLIC_DEMO_USER invalid or missing")
    if not BCRYPT.fullmatch(env.get("PUBLIC_DEMO_BCRYPT_HASH","")):
        raise RuntimeError("PUBLIC_DEMO_BCRYPT_HASH must be a valid bcrypt hash")
    password=env.get("COMPANYAGENT_ADMIN_PASSWORD","")
    if not isinstance(password,str) or len(password)<20 or "REPLACE" in password:
        raise RuntimeError("COMPANYAGENT_ADMIN_PASSWORD requires 20+ nonplaceholder characters")
    return {"mode":"cloud_synthetic","port":port,"production_ready":False}

def main():
    os.umask(0o077)
    try:
        cfg=validate_public_config()
    except RuntimeError as exc:
        print("RAILWAY_DEMO_BLOCKED: "+str(exc),file=sys.stderr,flush=True)
        return 2
    if not CADDY.is_file() or not CADDYFILE.is_file():
        print("RAILWAY_DEMO_BLOCKED: authenticated gateway missing",file=sys.stderr,flush=True)
        return 2

    env=os.environ.copy()
    env["PORT"]=str(cfg["port"])
    app_env=env.copy()
    app_env["HOST"]="127.0.0.1"
    app_env["PORT"]="8765"
    processes=[]
    shutdown=False

    def stop(sig=None,frame=None):
        nonlocal shutdown
        shutdown=True
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
    signal.signal(signal.SIGINT,stop)
    signal.signal(signal.SIGTERM,stop)

    try:
        app=subprocess.Popen([sys.executable,"server.py"],cwd=ROOT,env=app_env)
        processes.append(app)
        time.sleep(1)
        if app.poll() is not None:
            print("RAILWAY_DEMO_BLOCKED: internal app failed startup",file=sys.stderr,flush=True)
            return 1
        proxy=subprocess.Popen([str(CADDY),"run","--config",str(CADDYFILE),"--adapter","caddyfile"],
                               cwd=ROOT,env=env)
        processes.append(proxy)
        print("RAILWAY_SYNTHETIC_DEMO_STARTED: authenticated gateway; loopback backend; production=false",flush=True)
        while not shutdown:
            if app.poll() is not None or proxy.poll() is not None:
                print("RAILWAY_DEMO_UNHEALTHY: one service exited",file=sys.stderr,flush=True)
                return 1
            time.sleep(.25)
        return 0
    finally:
        stop()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    return 0

if __name__=="__main__":
    sys.exit(main())
