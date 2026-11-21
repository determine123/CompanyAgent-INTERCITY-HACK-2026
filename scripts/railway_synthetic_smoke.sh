#!/usr/bin/env bash
# Ephemeral Railway-shape Docker check. NO Railway account or live company API.
set -euo pipefail
id="railway-ci-${GITHUB_RUN_ID:-$$}"
edge="${id}-edge"
private="${id}-private"
app="${id}-app"
gateway="${id}-gateway"
tmp="$(mktemp -d)"
cleanup(){
  docker logs --tail 15 "$gateway" 2>/dev/null || true
  docker rm -f "$gateway" "$app" >/dev/null 2>&1 || true
  docker network rm "$private" "$edge" >/dev/null 2>&1 || true
  rm -rf "$tmp"
}
trap cleanup EXIT
docker build -f deploy/railway/backend.Dockerfile -t companyagent:railway-private-ci .
docker build -f deploy/railway/gateway.Dockerfile -t companyagent:railway-gateway-ci .
# Fail-safe default: selecting the repo-root Dockerfile must build ONLY the
# authenticated gateway, never the unauthenticated FastAPI service.
docker build -f Dockerfile -t companyagent:railway-default-ci .
docker run --rm --entrypoint /bin/sh companyagent:railway-default-ci \
  -c 'test -f /etc/caddy/Caddyfile && test ! -f /app/server.py'
docker image inspect -f '{{json .Config.ExposedPorts}}' companyagent:railway-default-ci | \
  grep -q '8080/tcp'
echo "RAILWAY_DEFAULT_ROOT_IMAGE=GATEWAY_ONLY_PASS"
docker network create --internal "$private" >/dev/null
docker network create "$edge" >/dev/null
fake_pass="synthetic-railway-demo-secret-for-ci"
hash="$(docker run --rm caddy:2.10.2-alpine caddy hash-password --plaintext "$fake_pass")"
docker run -d --rm --name "$app" --network "$private" \
 --network-alias companyagent.railway.internal \
 --cap-drop ALL --security-opt no-new-privileges --read-only \
 --tmpfs /app/runtime:rw,noexec,nosuid,size=32m,uid=10001,gid=10001 \
 --tmpfs /tmp:rw,noexec,nosuid,size=16m,uid=10001,gid=10001 \
 -e COMPANYAGENT_ADMIN_PASSWORD=synthetic-railway-app-password-ci-only \
 companyagent:railway-private-ci >/dev/null
docker run -d --name "$gateway" --network "$edge" \
 --cap-drop ALL --cap-add NET_BIND_SERVICE \
 -p 127.0.0.1:18082:8080 \
 -e RAILWAY_DEMO_USER=reviewer -e RAILWAY_DEMO_BCRYPT_HASH="$hash" \
 companyagent:railway-gateway-ci >/dev/null
docker network connect "$private" "$gateway"

base="http://127.0.0.1:18082"
ready=false
for _ in $(seq 1 40); do
  if curl -fsS --max-time 3 --user reviewer:"$fake_pass" "$base/healthz" > "$tmp/health.json" 2>/dev/null; then
     ready=true; break
  fi
  sleep 1
done
test "$ready" = true || { echo "Railway gateway/backend failed to start"; exit 1; }
python - "$tmp/health.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
assert x=={"ok":True,"mode":"cloud_synthetic","production_ready":False},x
PY
anon="$(curl -s -o /dev/null -w '%{http_code}' "$base/healthz")"
wrong="$(curl -s -o /dev/null -w '%{http_code}' --user reviewer:bad "$base/healthz")"
unsafe="$(curl -s -o /dev/null -w '%{http_code}' --user reviewer:"$fake_pass" "$base/api/demo")"
ingest="$(curl -s -o /dev/null -w '%{http_code}' -X POST --user reviewer:"$fake_pass" "$base/enterprise/api/datasets/upload")"
users="$(curl -s -o /dev/null -w '%{http_code}' -X POST --user reviewer:"$fake_pass" "$base/enterprise/api/users")"
benchmark="$(curl -s -o /dev/null -w '%{http_code}' -X POST --user reviewer:"$fake_pass" "$base/enterprise/api/agents/1/benchmark")"
# The anonymous judge surface must work, but never create a backend bypass.
guest_page="$(curl -s -o "$tmp/judge-page.html" -w '%{http_code}' "$base/judge/")"
guest_api="$(curl -s -o "$tmp/judge-plan.json" -w '%{http_code}' "$base/judge/api/plan?budget_wan=200&medium=both")"
guest_private="$(curl -s -o /dev/null -w '%{http_code}' "$base/enterprise/api/status")"
guest_old="$(curl -s -o /dev/null -w '%{http_code}' "$base/api/demo")"
guest_post="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$base/judge/api/plan")"
test "$guest_page" = 200 && test "$guest_api" = 200
test "$guest_private" = 401 && test "$guest_old" = 401 && test "$guest_post" = 405
grep -q '无需登录' "$tmp/judge-page.html"
python - "$tmp/judge-plan.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
assert d["synthetic_only"] and not d["real_hongdou_connected"]
assert d["budget_wan"]==200 and d["spent_wan"]<=200
assert d["sample_size"]==80
assert not d["evidence"]["future_inventory_available"] and not d["evidence"]["booked"]
PY
test "$anon" = 401 && test "$wrong" = 401
test "$unsafe" = 403 && test "$ingest" = 403 && test "$users" = 403 && test "$benchmark" = 403
test -z "$(docker port "$app")"
curl -sS --user reviewer:"$fake_pass" \
  -D "$tmp/login-headers" -o "$tmp/login-body" \
  -H 'Content-Type: application/json' \
  --data '{"username":"admin","password":"synthetic-railway-app-password-ci-only"}' \
  "$base/enterprise/api/auth/login"
grep -qi '^set-cookie: .*secure' "$tmp/login-headers"
grep -qi '^set-cookie: .*httponly' "$tmp/login-headers"
echo "RAILWAY_GATEWAY_SMOKE=PASS; anonymous=$anon; wrong_password=$wrong; legacy=$unsafe; upload=$ingest; users=$users; benchmark=$benchmark; backend_host_port=none; session_secure=true"
