# Mautic Pretix deployment

Pretix Community Edition on Coolify, pinned to `pretix/standalone:2026.2.0`.
Shop styling is documented in `branding/README.md`. No Enterprise dependency or
custom Python plugin is installed for tracking.

## Temporary MWC 2026 confirmation snippet

Sven chose approximate browser-side measurement for the final two weeks before
the conference, with manual reconciliation rather than a full tracking platform.

- `Dockerfile` preserves the base image's original order template as
  `pretixpresale/event/mwc-order-original.html`, then installs a thin wrapper.
  The wrapper extends that exact original, preserving all order-page content.
- `tracking/templates/pretixpresale/event/order.html` adds a self-hosted external
  script only for `Mautic/mwc2026`, paid orders with a positive total, and a
  `thanks` or `paid` confirmation marker. Free, pending, cancelled, test-mode,
  backend and ordinary later order views do not load it.
- `tracking/assets/mwc-ads-confirmation-v1.js` is bundled in the image's existing
  static directory and served as `/static/mwc-ads-confirmation-v1.js`.
- The script requires the Klaro `mwc_consent` cookie to contain the Boolean
  `google-ads: true` before loading Google. The conference site sets this cookie
  on `.mautic.org`. There is no extra Pretix consent prompt: absent or rejected
  consent means no tracking. Deploy conference consent first.
- The event contains the real total/currency and stable transaction ID
  `Mautic-mwc2026-ORDER_CODE` for Google's deduplication. No order access secret,
  name or email is included. Standard measurement URL/title/referrer fields are
  replaced with non-private values. Personalisation and analytics storage remain off.
- `PRETIX_PRETIX_CSP_ADDITIONAL_HEADER` adds the documented Google Ads destinations
  without `unsafe-inline` or `unsafe-eval`. The confirmation hook itself is external
  same-origin JavaScript, not an inline script.

No tracking code is copied into `/data`; no host-file bind mounts or repository
preservation setting are required. Runtime remains `pretixuser`. The Python core
is unmodified; the small template wrapper and static asset are part of the image.

### Deliberate limitations

Ad blockers, absent/rejected consent, direct-shop visits without prior conference
consent, closed confirmation pages, payment/webhook timing and unlisted regional
Google endpoints can cause missing conversions. Refund adjustment, delayed-payment
reconciliation and server-side attribution are intentionally not implemented.
Pretix remains the source of truth. Never generate artificial click IDs or fake
live conversions for testing.

## Deployment and rollback

Coolify app: `zwocw8osw4sgk00w48ko8gkk`, Git-based Compose, automatic deployments
from `main`. Sven approved testing and release on 21 October 2026.

1. Deploy the conference consent change and verify its shared cookie scope.
2. Build and run the local image checks below. They must preserve the exact
   upstream template and serve the JavaScript through the real image's nginx.
3. Release through Git/Coolify. Do not run manual Docker/SSH deployment workarounds.
4. Check the deployment result **and** the public shop, script MIME type/content
   hash, CSP and synthetic-browser consent cases. A failed Compose deployment can
   leave the shop unavailable; success must not be inferred from a queued request.
5. To roll back this tracking-only release, revert its Git changes and verify the
   corresponding Coolify deployment. Git branch HEAD and the intended Compose
   restore definition must agree. No database or `/data` migration is introduced
   by the snippet; application-version upgrades have separate backup requirements.

### Incident note

The initial file-bind implementation was withdrawn. On 21 October, Coolify created
file-bind sources as directories and failed during repository preservation. The
shop returned HTTP 503. Several rollback attempts were additionally blocked by
GitHub connection timeouts from the deployment server. Reverting Git `main` to
its pre-tracking tree (`7bbc528`) restored HTTP 200 before this image-bundled
replacement was prepared. Repository preservation was returned to its original
`false` value. No database contents or schema were deliberately modified.
Do not reintroduce those host file binds as an emergency fix.

**Cleanup after the conference (6 November 2026):** remove the Dockerfile template/
asset additions, extra CSP setting and temporary tracking sources via Git/Coolify.
The next base-image deployment then supplies the original template automatically;
there are no tracking files to remove from the persistent data volume.

## Checks

```sh
uv run --no-project --with 'Django==4.2.28' python tests/test_confirmation.py
node --test tests/confirmation.test.cjs
POSTGRES_PASSWORD=validation-placeholder docker compose config --quiet
docker build -t mwc-pretix-tracking-test .
./tests/container-smoke.sh
```

The container checks use the exact bundled Django version, compare the original
and backed-up upstream template hashes, verify the unchanged runtime user, and
start only nginx on a loopback test port to verify JavaScript delivery. No real
Pretix database, outgoing email or Google endpoint is used.

The conference repository's `npm run test:browser` covers desktop/tablet/mobile
consent, separate choices, rejection, withdrawal and synthetic iframe/new-tab
confirmations, intercepting all measurement. It does not make a real Stripe
payment. The separate urgent update plan is in
`~/Development/mautic-world-conference/docs/security-readiness-2026-10-21.md`.

## Sources

- Pretix 2026.2.0 order template, nginx config and `deployment/docker/pretix.bash`.
- https://developers.google.com/tag-platform/security/guides/csp (Google Ads sources).
