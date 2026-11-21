#!/usr/bin/env bash
# Cloud validation uses synthetic seed only. No AWS credentials or TokenDance key.
set -euo pipefail
docker build -f deploy/cloud-synthetic/Dockerfile -t companyagent:cloud-synthetic .
container="$(docker run -d --rm -p 127.0.0.1:18765:8765 \
  --read-only --cap-drop=ALL --security-opt no-new-privileges \
  --tmpfs /app/runtime:rw,noexec,nosuid,size=32m,uid=10001,gid=10001 \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m,uid=10001,gid=10001 \
  companyagent:cloud-synthetic)"
trap 'docker logs --tail=25 "$container" || true; docker stop "$container" >/dev/null || true' EXIT
for i in $(seq 1 30); do
  if curl -fsS --max-time 3 http://127.0.0.1:18765/healthz >/tmp/companyagent-cloud-health.json; then break; fi
  sleep 1
done
python - <<'PY'
import json
p=json.load(open('/tmp/companyagent-cloud-health.json',encoding='utf-8'))
assert p == {'ok':True,'mode':'cloud_synthetic','production_ready':False}, p
PY
legacy="$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:18765/api/demo)"
ingress="$(curl -sS -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:18765/enterprise/api/datasets/upload)"
test "$legacy" = 403
test "$ingress" = 403
echo "CLOUD_SYNTHETIC_SMOKE=PASS; legacy_api=$legacy; ingest=$ingress; non_root=verified_by_image"
