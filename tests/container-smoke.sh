#!/usr/bin/env bash
# Local, disposable image checks. No production configuration, database or Google requests.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${1:-mwc-pretix-tracking-test}"
BASE="pretix/standalone:2026.2.0"
cd "$ROOT"

docker image inspect "$IMAGE" >/dev/null
docker image inspect "$BASE" >/dev/null
[ "$(docker image inspect "$IMAGE" --format '{{.Config.User}}')" = pretixuser ]

docker run --rm --network none --entrypoint python \
  -v "$ROOT/tests:/work/tests:ro" -v "$ROOT/tracking:/work/tracking:ro" -w /work \
  "$IMAGE" tests/test_confirmation.py

original="$(docker run --rm --network none --entrypoint python "$BASE" -c \
  'import pathlib,hashlib;print(hashlib.sha256(pathlib.Path("/pretix/src/pretix/presale/templates/pretixpresale/event/order.html").read_bytes()).hexdigest())')"
backup="$(docker run --rm --network none --entrypoint python "$IMAGE" -c \
  'import pathlib,hashlib;print(hashlib.sha256(pathlib.Path("/pretix/src/pretix/presale/templates/pretixpresale/event/mwc-order-original.html").read_bytes()).hexdigest())')"
[ "$original" = "$backup" ]
wrapper="$(docker run --rm --network none --entrypoint python "$IMAGE" -c \
  'import pathlib,hashlib,importlib.metadata as m;assert m.version("pretix")=="2026.2.0";assert m.version("Django")=="4.2.28";print(hashlib.sha256(pathlib.Path("/pretix/src/pretix/presale/templates/pretixpresale/event/order.html").read_bytes()).hexdigest())')"
[ "$wrapper" = "$(sha256sum tracking/templates/pretixpresale/event/order.html | cut -d ' ' -f1)" ]
echo 'PASS: exact wrapper/upstream templates; unchanged Pretix/Django and runtime user'

body="$(mktemp)"
container=""
cleanup() {
  if [ -n "$container" ]; then
    # Remove only this disposable container and its anonymous test volumes.
    docker rm -fv "$container" >/dev/null 2>&1 || true
  fi
  rm -f "$body"
}
trap cleanup EXIT
container="$(docker run -d --user root --entrypoint nginx -p 127.0.0.1::80 "$IMAGE")"
if ! address="$(docker port "$container" 80/tcp)"; then
  docker logs "$container" >&2
  exit 1
fi
type="$(curl --fail --silent --show-error --retry 8 --retry-connrefused --retry-delay 1 \
  "http://$address/static/mwc-ads-confirmation-v1.js" -o "$body" -w '%{content_type}')"
case "$type" in application/javascript*|text/javascript*) ;; *) echo "Unexpected JavaScript MIME type: $type" >&2; exit 1;; esac
[ "$(sha256sum "$body" | cut -d ' ' -f1)" = "$(sha256sum tracking/assets/mwc-ads-confirmation-v1.js | cut -d ' ' -f1)" ]
echo 'PASS: real image nginx serves the exact snippet as JavaScript'
