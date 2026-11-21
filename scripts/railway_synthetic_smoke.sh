#!/usr/bin/env bash
# GitHub-hosted Railway IMAGE smoke. No Railway account, credits, or corporate data.
set -euo pipefail
image="companyagent:railway-synthetic-ci"
docker build -f Dockerfile -t "$image" .
user="$(docker image inspect -f '{{.Config.User}}' "$image")"
test "$user" = '10001:10001'

hash="$(docker run --rm caddy:2.10.2-alpine caddy hash-password --plaintext 'synthetic-ci-basic-only')"
test -n "$hash"
name="railway-synthetic-ci-${GITHUB_RUN_ID:-$$}"
cleanup(){
  docker logs --tail 15 "$name" 2>/dev/null || true
  docker rm -f "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Deliberately missing both auth variables. Must stop BEFORE listening.
set +e
timeout 12 docker run --rm -e PORT=18080 "$image" >/tmp/railway-fail-closed.log 2>&1
fail_status=$?
set -e
test "$fail_status" -ne 0
test "$fail_status" -ne 124
grep -q 'RAILWAY_DEMO_BLOCKED' /tmp/railway-fail-closed.log

docker run -d --name "$name" \
  -p 127.0.0.1:18766:18080 \
  -e PORT=18080 \
  -e PUBLIC_DEMO_USER=ci-reviewer \
  -e PUBLIC_DEMO_BCRYPT_HASH="$hash" \
  -e COMPANYAGENT_ADMIN_PASSWORD='synthetic-ci-independent-long-password' \
  "$image" >/dev/null

base='http://127.0.0.1:18766'
ready=false
for i in $(seq 1 40); do
  if curl -fsS --max-time 2 "$base/__railway/health" >/tmp/railway-health.json; then
    ready=true
    break
  fi
  if ! docker inspect -f '{{.State.Running}}' "$name" | grep -qx true; then
    docker logs "$name"
    exit 1
  fi
  sleep 1
done
test "$ready" = true
python - <<'PY'
import json
x=json.load(open("/tmp/railway-health.json",encoding="utf8"))
assert x=={"ok":True,"mode":"cloud_synthetic","production_ready":False},x
PY

getcode(){
  curl -sS -o /dev/null -w '%{http_code}' "$@"
}
anonymous="$(getcode "$base/enterprise/")"
incorrect="$(getcode -u ci-reviewer:wrong "$base/enterprise/")"
authorized="$(getcode -u ci-reviewer:synthetic-ci-basic-only "$base/enterprise/")"
legacy="$(getcode -u ci-reviewer:synthetic-ci-basic-only "$base/api/demo")"
upload="$(getcode -X POST -u ci-reviewer:synthetic-ci-basic-only "$base/enterprise/api/datasets/upload")"
users="$(getcode -X POST -u ci-reviewer:synthetic-ci-basic-only "$base/enterprise/api/users")"
health_private="$(getcode "$base/healthz")"
test "$anonymous" = 401
test "$incorrect" = 401
test "$authorized" = 200
test "$legacy" = 403
test "$upload" = 403
test "$users" = 403
test "$health_private" = 401
host_ports="$(docker port "$name")"
! echo "$host_ports" | grep -q '8765'
echo "$host_ports" | grep -q '18080'
echo "RAILWAY_SINGLE_SERVICE=PASS; anonymous=401; wrong_password=401; authorized=200; legacy=403; upload=403; user_create=403; app_port_not_published=true; health=200; fail_closed=true"
