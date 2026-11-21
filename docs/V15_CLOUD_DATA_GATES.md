# CompanyAgent v1.5 — Staged verification, enterprise ingress and migration gates

**2026-11-21 · Status: cloud-synthetic implementation and offline enterprise review, NOT a production deployment.**

## Evidence-led status

| Deliverable | Verified state | Evidence |
|---|---|---|
| TokenDance restricted live Tool Calling | PASS, synthetic-only: glm-5.2, three read-only tools | [2026-11-21 actual run](TOKENDANCE_LIVE_VERIFIED_2026-11-21.md) |
| Existing regression and governance workbench | Previously 91 pytest tests + governance logic | `.github/workflows/ci.yml`, `.github/workflows/governance.yml` |
| cloud_synthetic FastAPI protection | Implemented; verify in new CI | `enterprise/deployment_policy.py`, new tests |
| GitHub-hosted non-root sandbox | Implemented; verify in cloud container workflow | `deploy/cloud-synthetic/`, `scripts/cloud_synthetic_smoke.sh` |
| Enterprise data ingress | **No real data acquired or imported.** Offline, metadata-only inspection implemented | `enterprise/ingress_review.py` |
| Live AWS instance, VPC, production SSO, deployment, rollback | **Not performed; remains blocked.** | Requires cloud account + enterprise approval |
| OpenClaw production replacement | **Not performed; remains blocked.** | Requires inventory, side-by-side measurements, SRE sign-off |

The internal-data boundary remains: public/non-sensitive read-only Cron jobs may be considered for cloud pilots; corporate API, private business data and company credentials stay inside approved private enterprise environments until the data owner, security and network owners authorize them. No CI passing score is an authorization.

## Source-control deliverables

- `enterprise/deployment_policy.py`: explicit `local` vs `cloud_synthetic` modes; `production` and unknown values fail startup. cloud_synthetic refuses model keys, source-connector tokens, outbound approved-data hosts, auto-sync and real-data enable flags. It blocks legacy `/api/*` and the authenticated enterprise import/sync/bridge routes.
- `enterprise/ingress_review.py`: offline dry-run inspection of a locally supplied CSV/XLSX with mandatory SHA-256 checksum, classification, tenant, purpose, provenance, owner/security ticket references, 1–30 day retention and a hard `model_export_allowed=false`. Never persists the raw rows, uploads them or calls LLMs. Internal data still requires out-of-band ticket verification; restricted data is rejected.
- `enterprise/migration_gates.py`: explicit evidence requirements for `cloud_synthetic`, `enterprise_pilot`, and `production_migration`. Even fully populated metadata manifests return `deployment_permitted=false` and `production_cutover_permitted=false` until real human-led enterprise change management occurs.
- `deploy/cloud-synthetic/`: ephemeral, loopback-only Docker sandbox running non-root, read-only root filesystem and in-memory data runtime. Does not expose corporate data sources.
- `.github/workflows/cloud-synthetic.yml`: cloud hosted Docker build/start + negative HTTP checks. Treat this as **GitHub Actions cloud container testing**, *not AWS EC2/Lightsail or enterprise production*.
- `governance_site/core.js`: seed evidence now distinguishes verified glm-5.2 tool calls and GitHub Docker smoke from missing real-data approvals. Existing browser localStorage might retain older user edits; export backup before using “restore examples.”

## Commands for independent review

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/review_migration_gates.py deploy/approval-manifest.example.json
# expected: blocked; exit 2, not a production change
docker compose -f deploy/cloud-synthetic/compose.yaml up --build -d
curl -fsS http://127.0.0.1:18765/healthz
# expected: cloud_synthetic, production_ready=false
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18765/api/demo
# expected: HTTP 403
docker compose -f deploy/cloud-synthetic/compose.yaml down
```

Offline enterprise-data review, **only on an approved company workstation and only after written authorization**:

```bash
python scripts/review_enterprise_export.py /approved/path/inventory.csv /approved/path/source-manifest.json
```

Input data and manifest must remain outside public GitHub, chat, or consumer model services; output includes only checksum, row counts and classification, and never grants production permission.

## Target AWS deployment (architecture only — not provisioned)

For sensitive/internal tasks, prefer pre-approved enterprise AWS/VPC rather than a new personal cloud account. An enterprise-approved design could use ECS Fargate **private subnets, disabled public IP assignment**, narrowly scoped task and execution IAM roles, Secrets Manager/KMS, private application ingress with enterprise SSO/OIDC, auditable Tool Gateway/MCP PDP+PEP, controlled egress/NAT/PrivateLink and centralized immutable audit logging. AWS documents private subnet networking and Secrets Manager with ECS task execution roles:
- https://docs.aws.amazon.com/securityhub/latest/userguide/exposure-ecs-service.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security-iam-roles.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html
- https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-options.html

For an EC2 pilot, require IMDSv2 only, security groups limited to private ingress, auditable IAM instance profile and network egress restrictions. **Do not assume** an IAM instance role can be attached to a Lightsail instance in the same manner as EC2. API keys are not placed in source, instance user data, environment files committed to Git, or unscoped build logs.

No AWS account/region billing data, corporate network routes, IAM permissions or company credentials were supplied or accessed in this implementation. Therefore there is no credible basis to claim an AWS deployment is live or that an enterprise API has been connected.

## Exact go/no-go before real data or production

1. **Governance:** approved data purpose, classification, retention, data owner and security owner references. Confirm actual approval outside this repo; a ticket string is only an untrusted assertion.
2. **Identity and tenancy:** corporate OIDC/SSO + per-tenant resource separation; local SQLite/cookie login does not satisfy this gate. Test cross-tenant leakage, CSRF, session expiry and audit completeness.
3. **Network and secrets:** enterprise-owned VPC/PrivateLink/VPN, egress DNS and IP allowlists, time-limited credentials from corporate Secret Manager/KMS, key rotation and failure-closed behavior.
4. **MCP and skill security:** parameter-level authorization for every tool, principal and tenant; immutable audit and independent negative tests for prompt injection, SSRF, DNS rebinding, metadata access, skill supply-chain tampering and KMS failure.
5. **IMDS project:** authorized field mapping/handbooks, multiple-candidate ambiguity `needs_review`, real end-to-end datasets, 10k-row performance + p95/p99, no autonomous Approve/Reject.
6. **Shadow Mode:** freeze OpenClaw Cron and API dependencies, run parallel comparisons with **writes disabled**; verify idempotency and prevent duplicate notifications; require explicit rollback trigger owners and a tested rollback drill.
7. **Go-live:** SRE, security, data owner and business mentor sign-off in enterprise change control. Production cutover may only follow those approvals; this repository deliberately has no automatic production deployment workflow.

## Migration / rollback matrix

| Phase | Permit | Abort / rollback condition | Evidence required |
|---|---|---|---|
| Static source and offline tests | Synthetic inputs only | Unit, security or schema test fails | Commit SHA + CI test run |
| GitHub cloud sandbox | Synthetic localhost container only | Any open legacy API, real-data path, external token, unexpected network exposure | Container smoke run and negative tests |
| North America public task pilot | Public read-only Cron under approved cost account | Missed/duplicate jobs; unexpected egress or cost | Timestamped job logs, comparison and cost statement |
| Authorized enterprise ingress pilot | Only sanctioned export in internal test tenancy | Owner consent missing, checksum drift, scope/tenant mismatch, sensitive-data egress | Signed ticket, manifest, import ledger, deletion proof |
| Hermes/OpenClaw shadow mode | No writes, no notifications from shadow agent | Output drift, unauthorized tool invocation, KMS/network faults | Signed run manifests, traces, failure and recovery drill |
| Production cutover | **Not permitted by v1.5** | Any critical approval missing | OIDC/SSO, Security/SRE/Owner signoffs and rollback acceptance |

**Next enterprise input needed (not to be posted in chat):** authorized account/VPC owner; data catalog references; SSO/tenant scope; approved MCP tools; data-classification and retention policy; deployment change ticket; rollback and monitoring owners.
