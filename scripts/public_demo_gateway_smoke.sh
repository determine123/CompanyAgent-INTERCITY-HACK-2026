#!/usr/bin/env bash
# GitHub-hosted ephemeral HTTP test of the Caddy authentication boundary.
# This intentionally uses an HTTP-only loopback address for CI, not a public host.
set -euo pipefail
edge="ca-public-edge-ci-${GITHUB_RUN_ID:-$$}"
network="ca-public-demo-ci-${GITHUB_RUN_ID:-$$}"
app="ca-synthetic-app-${GITHUB_RUN_ID:-$$}"
proxy="ca-synthetic-proxy-${GITHUB_RUN_ID:-$$}"
cleanup(){
  docker logs --tail 20 "$proxy" 2>/dev/null || true
  docker rm -f "$proxy" "$app" >/dev/null 2>&1 || true
  docker network rm "$network" "$edge" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker build -f deploy/cloud-synthetic/Dockerfile -t companyagent:public-demo-ci .
docker network create --internal "$network" >/dev/null
docker network create "$edge" >/dev/null
hash="$(docker run --rm caddy:2.10.2-alpine caddy hash-password --plaintext 'ci-synthetic-password-only')"
test -n "$hash"
export PUBLIC_DEMO_DOMAIN='http://:80'
export PUBLIC_DEMO_USER='ci-reviewer'
export PUBLIC_DEMO_BCRYPT_HASH="$hash"
export PUBLIC_DEMO_APP_PASSWORD='synthetic-app-password-only-ci'
docker compose -f deploy/public-demo/compose.yaml config --format json | python scripts/public_demo_config_preflight.py /dev/stdin --ci
docker run -d --rm --name "$app" --network "$network" \
  --network-alias companyagent --read-only --cap-drop ALL \
  --security-opt no-new-privileges \
  --tmpfs /app/runtime:rw,noexec,nosuid,size=32m,uid=10001,gid=10001 \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m,uid=10001,gid=10001 \
  -e COMPANYAGENT_DEPLOYMENT_MODE=cloud_synthetic \
  -e COMPANYAGENT_AUTO_SYNC=false -e COMPANYAGENT_ALLOWED_DATA_HOSTS= \
  -e COMPANYAGENT_ADMIN_PASSWORD=synthetic-app-password-only-ci \
  companyagent:public-demo-ci >/dev/null

docker run -d --name "$proxy" --network "$edge" \
  --cap-drop ALL --cap-add NET_BIND_SERVICE \
  -p 127.0.0.1:18081:80 \
  -e PUBLIC_DEMO_DOMAIN=http://:80 \
  -e PUBLIC_DEMO_USER=ci-reviewer \
  -e PUBLIC_DEMO_BCRYPT_HASH="$hash" \
  -v "$PWD/deploy/public-demo/Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2.10.2-alpine >/dev/null
# Caddy has edge networking for port mapping and separate internal app connectivity.
docker network connect "$network" "$proxy"

base="http://127.0.0.1:18081"
ready=false
for i in $(seq 1 45); do
  if ! docker inspect -f '{{.State.Running}}' "$proxy" | grep -qx true; then
    echo "Caddy process exited before health check; printing startup diagnostics"
    docker logs --tail 30 "$proxy" || true
    exit 1
  fi
  if curl -fsS --max-time 2 --user ci-reviewer:ci-synthetic-password-only "$base/healthz" > /tmp/public-demo-health.json; then
    ready=true
    break
  fi
  sleep 1
done
test "$ready" = true
python - <<'PY'
import json
obj=json.load(open('/tmp/public-demo-health.json',encoding='utf8'))
assert obj=={"ok":True,"mode":"cloud_synthetic","production_ready":False},obj
PY
anonymous="$(curl -sS -o /dev/null -w '%{http_code}' "$base/healthz")"
incorrect="$(curl -sS -o /dev/null -w '%{http_code}' --user ci-reviewer:invalid "$base/healthz")"
legacy="$(curl -sS -o /dev/null -w '%{http_code}' --user ci-reviewer:ci-synthetic-password-only "$base/api/demo")"
ingress="$(curl -sS -o /dev/null -w '%{http_code}' -X POST --user ci-reviewer:ci-synthetic-password-only "$base/enterprise/api/datasets/upload")"
users="$(curl -sS -o /dev/null -w '%{http_code}' -X POST --user ci-reviewer:ci-synthetic-password-only "$base/enterprise/api/users")"
test "$anonymous" = 401
test "$incorrect" = 401
test "$legacy" = 403
test "$ingress" = 403
test "$users" = 403
test -z "$(docker port "$app")"
echo "PUBLIC_DEMO_GATEWAY=PASS; anonymous=$anonymous; wrong_password=$incorrect; legacy=$legacy; ingress=$ingress; user_create=$users; backend_host_port=none"
