# CompanyAgent cloud_synthetic — ephemeral validation only

**This is NOT production deployment.** The image runs as non-root, container filesystem is read-only, runtime is an ephemeral tmpfs, no data connectors/LLM credentials are allowed, and the host port binds to 127.0.0.1 only. The legacy unauthenticated `/api/*` endpoints and enterprise file/source ingestion are denied in cloud_synthetic mode.

```bash
docker compose -f deploy/cloud-synthetic/compose.yaml up --build -d
curl --fail http://127.0.0.1:18765/healthz
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18765/api/demo  # 403
docker compose -f deploy/cloud-synthetic/compose.yaml down
```

The environment rejects `COMPANYAGENT_DEPLOYMENT_MODE=production` and rejects non-empty model/API secrets or automatic data sync in cloud_synthetic. Never publish or reverse-proxy this single-organization prototype to the Internet: it does not implement enterprise OIDC/SSO, end-to-end tenant isolation, immutable audit logs, backup/restore, or business-owner approval. Cloud CI proves **container boot and isolation controls**, not AWS VPC provisioning or production safety.

For AWS pilot after approved corporate access: choose a private ECS Fargate service (no task public IP), private endpoints/NAT with explicit egress, Secrets Manager + narrowly scoped execution/task roles, audit storage and SSO-protected ingress. These are architecture requirements, **not provisioned by this repo**. Avoid using Lightsail to claim EC2 instance-profile behavior without separate verification.
