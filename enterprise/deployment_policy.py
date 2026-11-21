"""Fail-closed deployment boundary for CompanyAgent single-organization prototype.

Only 'local' and 'cloud_synthetic' modes are supported. This is intentionally
NOT a production deployment switch: no environment variable can bypass
missing SSO, tenant authorization, audited secret storage, and enterprise
approval requirements by simply claiming approval.
"""
from __future__ import annotations
import os

SUPPORTED = frozenset({"local", "cloud_synthetic"})
BLOCKED_EXACT = frozenset({
    "B1X_API_KEY", "TOKENDANCE_API_KEY",
    "COMPANYAGENT_ALLOWED_DATA_HOSTS",
})
BLOCKED_MUTATIONS = frozenset({
    "/enterprise/api/datasets/upload",
    "/enterprise/api/sources",
    "/enterprise/api/sources/poll-folder",
    "/enterprise/api/data/bridge/reconcile",
    "/enterprise/api/users",
})

def deployment_mode(env=None):
    values = os.environ if env is None else env
    return values.get("COMPANYAGENT_DEPLOYMENT_MODE", "local").strip().lower()

def validate_deployment(env=None):
    values = dict(os.environ if env is None else env)
    mode = deployment_mode(values)
    if mode not in SUPPORTED:
        raise RuntimeError("PRODUCTION_DEPLOYMENT_BLOCKED: only local/cloud_synthetic are implemented; SSO, audit, tenant isolation and sign-off are missing")
    if mode == "cloud_synthetic":
        if values.get("COMPANYAGENT_AUTO_SYNC", "false").lower() not in ("", "false", "0"):
            raise RuntimeError("CLOUD_SYNTHETIC_BLOCKED: unattended source syncing is forbidden")
        if any(values.get(key, "").strip() for key in BLOCKED_EXACT):
            raise RuntimeError("CLOUD_SYNTHETIC_BLOCKED: external model keys or data allowlists are forbidden")
        if any(key.startswith("COMPANYAGENT_SOURCE_") and key.endswith("_TOKEN") and values.get(key)
               for key in values):
            raise RuntimeError("CLOUD_SYNTHETIC_BLOCKED: enterprise connector credentials are forbidden")
        if values.get("COMPANYAGENT_REAL_DATA_ENABLED", "false").lower() not in ("", "false", "0"):
            raise RuntimeError("CLOUD_SYNTHETIC_BLOCKED: real-data flag is forbidden")
        if any(key.startswith("HONGDOU_PILOT_") and str(val).strip()
               for key, val in values.items()):
            raise RuntimeError("CLOUD_SYNTHETIC_BLOCKED: Hongdou enterprise pilot configuration is forbidden")
    # Railway demo is an additional *synthetic-only* hardening profile.
    # It cannot be used to enable real data or production deployment.
    if values.get("COMPANYAGENT_RAILWAY_PRIVATE_BACKEND", "").lower() in ("1", "true"):
        if mode != "cloud_synthetic":
            raise RuntimeError("RAILWAY_DEMO_BLOCKED: private backend must be cloud_synthetic")
        if values.get("COMPANYAGENT_COOKIE_SECURE", "").lower() != "true":
            raise RuntimeError("RAILWAY_DEMO_BLOCKED: Secure cookies are mandatory behind Railway HTTPS")
        pwd = values.get("COMPANYAGENT_ADMIN_PASSWORD", "")
        if len(pwd) < 20 or pwd.lower().startswith("replace") or pwd.startswith("CI-"):
            raise RuntimeError("RAILWAY_DEMO_BLOCKED: configure an independent strong application password")
        if values.get("HOST", "") not in ("0.0.0.0", "::"):
            raise RuntimeError("RAILWAY_DEMO_BLOCKED: backend must bind the internal service network")
        if values.get("PORT", "") != "8765":
            raise RuntimeError("RAILWAY_DEMO_BLOCKED: internal service port must remain 8765")
    return {"mode": mode, "real_data_permitted": False, "production_ready": False}

def forbidden_cloud_request(path, method="GET", env=None):
    """Restrict legacy unprotected and enterprise ingestion endpoints in cloud demo."""
    if deployment_mode(env) != "cloud_synthetic":
        return False
    if path == "/api" or path.startswith("/api/"):
        return True
    if path in BLOCKED_MUTATIONS and method.upper() != "GET":
        return True
    if path.startswith("/enterprise/api/sources/") and path.endswith("/sync"):
        return True
    if path.startswith("/enterprise/api/agents/") and path.endswith("/benchmark"):
        return True
    # Cloud-synthetic is not a public enterprise API for arbitrary source uploads.
    return False
