#!/usr/bin/env bash
# Local synthetic test only. Never operates on a Coolify server.
set -euo pipefail
cd "$(dirname "$0")/.."
POSTGRES_PASSWORD=synthetic-config-check python3 - <<'PY'
import subprocess,json
configs=[json.loads(subprocess.run(['docker','compose','-p','mwc-config-check','-f',f,'config','--format','json'],capture_output=True,text=True,check=True).stdout) for f in ['docker-compose.yml','maintenance/pretix-hold.yml']]
a,b=configs
assert a['services']['pretix'].get('entrypoint') is None and a['services']['pretix'].get('command') is None
assert b['services']['pretix']['entrypoint']==['sudo','-E','/usr/bin/supervisord','-n','-c','/etc/mwc-maintenance.conf']
assert b['services']['pretix']['command']==[]
for config in configs:
    for key in ['entrypoint','command']:config['services']['pretix'].pop(key,None)
assert a==b
print('PASS: maintenance changes only entrypoint/command, not data/dependencies/environment')
PY
docker build -t mwc-pretix-hold-proof . >/tmp/mwc-hold-build.log 2>&1
NAME="mwc-hold-proof-$$"
trap 'docker rm -fv "$NAME" >/dev/null' EXIT
docker run -d --name "$NAME" --network none --entrypoint sudo mwc-pretix-hold-proof -E /usr/bin/supervisord -n -c /etc/mwc-maintenance.conf >/dev/null
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
echo 'PASS: vendor nginx-only hold serves exports, blocks shop, starts no application writers'
