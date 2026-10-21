#!/usr/bin/env bash
# Local synthetic test only. Match Coolify's explicit root project directory.
set -euo pipefail
cd "$(dirname "$0")/.."
export POSTGRES_PASSWORD=synthetic-config-check
python3 - <<'PY'
import subprocess,json,os
configs=[json.loads(subprocess.run(['docker','compose','--project-directory',os.getcwd(),'-p','mwc-config-check','-f',f,'config','--format','json'],capture_output=True,text=True,check=True).stdout) for f in ['docker-compose.yml','maintenance/pretix-hold.yml']]
a,b=configs
assert a['services']['pretix'].get('entrypoint') is None
assert b['services']['pretix']['entrypoint']==['sudo','-E','/usr/bin/supervisord','-n','-c','/etc/mwc-maintenance.conf']
assert a['services']['pretix'].get('command') is None and b['services']['pretix'].get('command') is None
for config in configs:config['services']['pretix'].pop('entrypoint',None)
assert a==b
print('PASS: root-project-directory maintenance changes only entrypoint')
PY
PROJECT="mwc-hold-proof-$$"
OVERRIDE=$(mktemp /tmp/mwc-hold-network.XXXXXX.yml)
printf 'networks:\n  default:\n    internal: true\n' > "$OVERRIDE"
COMPOSE=(docker compose --project-directory "$PWD" -p "$PROJECT" -f maintenance/pretix-hold.yml -f "$OVERRIDE")
cleanup() { "${COMPOSE[@]}" down --volumes >/dev/null; rm -f "$OVERRIDE"; }
trap cleanup EXIT
"${COMPOSE[@]}" up -d --no-deps --build pretix >/tmp/mwc-hold-build.log 2>&1
NAME=$("${COMPOSE[@]}" ps -q pretix)
[ "$(docker network inspect "${PROJECT}_default" --format '{{.Internal}}')" = true ]
# This bounded retry covers nginx's startup race, not application failures.
for n in $(seq 1 15); do
  status="$(docker exec "$NAME" curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/ || true)"
  if [ "$status" = 502 ]; then break; fi
  sleep 1
done
docker exec "$NAME" sh -c 'mkdir -p /data/media; printf "synthetic placeholder" > /data/media/mwc-probe.cms'
[ "$(docker exec "$NAME" curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/media/mwc-probe.cms)" = 200 ]
[ "$(docker exec "$NAME" curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/)" = 502 ]
docker exec "$NAME" python -c 'from pathlib import Path;names=[p.read_text().strip() for p in Path("/proc").glob("[0-9]*/comm")];assert not any(n.startswith(("gunicorn","celery","cron")) for n in names)'
echo 'PASS: real Compose hold serves exports, blocks shop, starts no application writers'
