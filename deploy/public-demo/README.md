# CompanyAgent public synthetic demo · HTTPS + Basic Auth

This is a **restricted public demo** for synthetic Food & Beverage scenario only, not an enterprise production release. Do not put corporate secrets, business files, 2027 real inventory, RedBean/Hongdou API tokens, or IMDS data into this VM.

## Requirements
- A VPS with Docker Engine and Docker Compose V2 and an assigned public IPv4 address.
- An owned hostname (e.g. demo.example.com) with DNS A record pointed to the VPS, and inbound TCP 80/443; optionally UDP 443 for HTTP/3. Caddy manages TLS certificates.
- Two **different** strong secrets: a Caddy Basic Auth password (stored as a bcrypt hash) and an app account password (provided through local untracked env file). No keys committed to Git.
- Keep the underlying CompanyAgent container on a Docker **internal** network without host-published ports; Caddy is the only public entry point.

## One-time preparation

```bash
git clone https://github.com/determine123/CompanyAgent-INTERCITY-HACK-2026.git
cd CompanyAgent-INTERCITY-HACK-2026
cp deploy/public-demo/.env.example deploy/public-demo/.env
docker run --rm -it caddy:2.10.2-alpine caddy hash-password
```

Edit the local `deploy/public-demo/.env` with your hostname, unique username, the **single-quoted bcrypt hash**, and a distinct >=20 character app password. Keep file permissions at `chmod 600`. For example, generate app password with `python -c 'import secrets;print(secrets.token_urlsafe(30))'` (execute on your own trusted host).

```bash
# Preflight consumes Compose JSON through a pipe and does not save secrets to a file
docker compose --env-file deploy/public-demo/.env -f deploy/public-demo/compose.yaml config --format json | python scripts/public_demo_config_preflight.py /dev/stdin
docker compose --env-file deploy/public-demo/.env -f deploy/public-demo/compose.yaml up --build -d
docker compose --env-file deploy/public-demo/.env -f deploy/public-demo/compose.yaml ps
```

Visit `https://YOUR_DOMAIN/enterprise/` (customer demand / Agent proposal) or `https://YOUR_DOMAIN/governance/` (governance site). Browser first asks for the Caddy Basic Auth credentials; inside the app, log in as `admin` with the separate `PUBLIC_DEMO_APP_PASSWORD`. Both layers must be used only for a narrow demo audience. Do not configure this shared demo with actual enterprise users/SSO assertions.

## Acceptance (do not log credentials)
- `curl -I https://YOUR_DOMAIN/` without credentials must return 401.
- With Basic Auth (enter in a private terminal) `GET /healthz` must return `{"ok":true,"mode":"cloud_synthetic","production_ready":false}`.
- With Basic Auth: `GET /api/demo` and `POST /enterprise/api/datasets/upload` return 403; no corporate API credentials allowed.
- Only Caddy binds host ports 80/443. `docker compose ... ps` must show **no published 8765** port. Verify with an external port scan; no access to /healthz or application on 8765.
- Restarting the container wipes all app data and sessions because runtime resides in tmpfs. Changes in governance site's localStorage remain only in the browser that made them; do not enter customer information.

## Stop and rollback

```bash
docker compose --env-file deploy/public-demo/.env -f deploy/public-demo/compose.yaml down
```

Immediately tear down if unprotected requests succeed, `/api/*` returns anything other than 403 after authentication, corporate tokens/real data are present, HTTPS cannot provision, or ingress exposes 8765. Rotate exposed credentials, remove the VM if compromised, and preserve sanitized event evidence only.

## Constraints
- There is no enterprise SSO/OIDC, tenant isolation, production-grade audit, rate limiting/WAF, formal backup/restore, commercial inventory confirmation or approved live Hongdou integration.
- **Food & Beverage / 食品饮料** is the sole public demo industry. The private enterprise pilot will require separate company-owned infrastructure and explicit data-owner/security/network sign-off.
- Visual coverage platform offers **no API**: do not fabricate a connector or scrape a website.
- Hongdou endpoints are *specified*, but live access is not performed here. See `docs/HONGDOU_ENTERPRISE_PILOT.md`.
- This repository does not create a VPS, DNS entry or cloud account. An operator must deploy using an approved account/domain.
