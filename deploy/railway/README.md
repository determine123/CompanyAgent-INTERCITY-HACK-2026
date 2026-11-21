# CompanyAgent v1.7 — Railway public synthetic demo

**Scope:** public demonstration of the **Food & Beverage (食品饮料)** industry only.
This is NOT enterprise production. All inventory/coverage data are synthetic,
Hongdou live bus/metro stock APIs are disabled, and visual/coverage API does not exist.

## What is different from the VPS Docker Compose

Railway provisions the externally accessible HTTPS domain and handles TLS.
The GitHub root [Dockerfile](../../Dockerfile) now builds a **single image** with:
- **Caddy** listening on Railway's runtime `PORT` (defaults to 8080), enforcing bcrypt Basic Auth on every application path.
- **FastAPI** listening ONLY on `127.0.0.1:8765` inside the same container; it is never bound to Railway's public port.
- One unauthenticated, minimal `/__railway/health` path for Railway's deployment healthcheck, delegated to FastAPI's safe `/healthz`.
- Fail-closed startup if proxy/app credentials are absent, the mode isn't `cloud_synthetic`, secure cookies are disabled, or model/vendor/corporate tokens are present.
- Non-root image user `10001:10001`, no persistent data volumes; demo application state is ephemeral and may reset after a redeploy.

Do **not** import `deploy/public-demo/compose.yaml` into Railway. That file targets a separate VPS with Caddy-managed public TLS; Railway's edge already manages public HTTPS.

## Create Railway project (requires an account connection and billing authorization)

1. Log in to [Railway dashboard](https://railway.com/dashboard) and create a new project, choosing **Deploy from GitHub repo**.
2. Authorize Railway's GitHub access to `determine123/CompanyAgent-INTERCITY-HACK-2026` and select branch `main` after the GitHub CI checks for v1.7 succeed.
3. Use the repository **root** as the service root. The root `Dockerfile` is intentionally Railway-safe; **do not** override the start command to `python server.py` or publish backend `8765`.
4. Under **Variables**, add the required credentials. For the demo, set only:
   - `PUBLIC_DEMO_USER`: a private reviewer username, e.g. `reviewer`.
   - `PUBLIC_DEMO_BCRYPT_HASH`: the full bcrypt hash generated *locally*, not plaintext.
   - `COMPANYAGENT_ADMIN_PASSWORD`: a **different** randomly generated 20+ character application password.
   Keep `COMPANYAGENT_DEPLOYMENT_MODE=cloud_synthetic`, `COMPANYAGENT_COOKIE_SECURE=true` and `COMPANYAGENT_AUTO_SYNC=false` (image defaults). Do not add `TOKENDANCE_API_KEY`, `B1X_API_KEY`, tenant tokens, Hongdou URL or other corporate secrets.
5. To obtain a bcrypt hash without passing the password as a shell argument, run interactively on a trusted machine:
   ```bash
   docker run --rm -it caddy:2.10.2-alpine caddy hash-password
   ```
   This prompts for the password and prints its hash. Paste ONLY the hash into Railway service Variables. Do not paste the password into GitHub, chat or logs. Generate the separate application password using a local password manager.
6. In Railway service **Settings → Deploy → Healthcheck Path**, enter `/__railway/health`. Railway should use the service's `PORT`, automatically injected by the platform. One replica only.
7. Deploy the service. **Only after it reports healthy**, use **Settings → Networking → Public Networking → Generate Domain**. Railway provides a `*.up.railway.app` HTTPS domain; no purchased DNS name is required. Do not create a separate public endpoint for the internal FastAPI port.
8. First visit `https://YOUR_DOMAIN/enterprise/` to demonstrate customer demand → bounded read-only tools → reference proposal. The browser must first ask for Caddy's reviewer credential, then show the application's separate admin login. Visit `/governance/` only after authorization.

Railway's new services no longer support the old `railway.json` configuration-as-code format, which is being retired on 2026-12-01. Keep the deployment in the service's settings, using the root Dockerfile and the healthcheck path above.

## Post-deploy acceptance, no credentials in reports

| Check | Required result |
|---|---|
| GET `/__railway/health` without auth | HTTP 200; minimal JSON `mode=cloud_synthetic`, `production_ready=false` |
| GET `/enterprise/` without authentication | HTTP 401 |
| GET `/enterprise/` with wrong Basic Auth | HTTP 401 |
| GET `/enterprise/` with valid Basic Auth | HTTP 200; app's own login required |
| GET `/api/demo` after Basic Auth | HTTP 403 |
| POST `/enterprise/api/datasets/upload` after Basic Auth | HTTP 403 |
| POST `/enterprise/api/users` after Basic Auth | HTTP 403 |
| Direct public access to port 8765 | No route / no public binding |
| Non-food industry POST `/enterprise/api/runs` | HTTP 400 once logged into the app |
| Real Hongdou, IMDS or corporate data sent | **None** |

CI simulates these assertions using local Docker and HTTP; it does **not** verify Railway's actual public endpoint. After deployment verify the real Railway domain separately and record a redacted test result.

## Fail closed / rollback

If any endpoint bypasses Basic Auth, if the legacy API is accessible, or if a corporate credential or authentic customer inventory is found in service variables: immediately **remove the Railway public domain or stop the service**, then rotate affected credentials. Do not silently switch the deployment to `local` or `production` mode. Rollback to the last reviewed commit and rerun independent CI.

The Railway demo is disposable and does not have enterprise SSO, tenant isolation, immutable audit or persistence guarantees. The approved corporate Hongdou/IMDS pilot must remain on company-authorized private infrastructure.

## Existing evidence

- GitHub Actions: `.github/workflows/railway-synthetic.yml`.
- Offline public gateway proof: `scripts/railway_synthetic_smoke.sh`.
- Enterprise data pilot plan: `docs/HONGDOU_ENTERPRISE_PILOT.md`.
- Overall migration gates: `docs/V15_CLOUD_DATA_GATES.md`.
