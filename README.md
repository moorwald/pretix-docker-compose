# Mautic Pretix deployment

Pretix Community Edition on Coolify, pinned to `pretix/standalone:2026.2.0`.
Existing shop styling is documented in `branding/README.md`.
There is no Enterprise dependency and no custom Python plugin.

## Temporary MWC 2026 confirmation snippet

Sven chose a small, approximate browser-side solution for the final two weeks
before the conference, rather than a full tracking integration.

- `templates/pretixpresale/event/order.html` extends the original Pretix order
  template. All original order content remains intact.
- It adds an external, self-hosted JavaScript snippet only for `Mautic/mwc2026`,
  paid orders with a positive total, and the `thanks` or `paid` confirmation marker.
  Free, pending, cancelled, test-mode and backend order views do not load it.
- `assets/mwc-ads-confirmation-v1.js` requires the shared Klaro `mwc_consent`
  cookie to contain an explicit Boolean `google-ads: true`. Without it, no Google
  script is loaded and no conversion is queued. There is no extra consent prompt
  in Pretix. Conference consent must have been chosen before confirmation loads.
- The conference repository sets the cookie on `.mautic.org`, covering the
  conference and ticket-shop subdomains. Deploy the conference changes first.
- The event includes the actual order total/currency and a stable transaction ID
  (`Mautic-mwc2026-ORDER_CODE`) for Google's deduplication. No order access secret,
  email or name is included. Standard page URL, title and referrer measurement
  fields are replaced with non-private values before Google loads.
- The script is loaded from `/media/pub/mwc-ads-confirmation-v1.js` to comply with
  Pretix's CSP. `PRETIX_PRETIX_CSP_ADDITIONAL_HEADER` adds the documented Google
  Ads destinations without enabling `unsafe-inline` or `unsafe-eval`.

### Deliberate limitations

This is directional advertising evidence, not financial reporting. Ad blockers,
missing/rejected consent, direct ticket-shop visits without conference consent,
closed confirmation pages, payment/webhook timing and unlisted regional Google
endpoints can cause missing conversions. Refund adjustments, delayed-payment
reconciliation and server-side attribution are intentionally not implemented.
Reconcile against Pretix manually. No artificial click IDs or fake live
conversions should be generated for testing.

## Deployment and rollback

Source branch: `feat/confirmation-tracking`. Sven approved tests and production
release on 2026-10-21. The Coolify app is `zwocw8osw4sgk00w48ko8gkk` and deploys
from `main`. **Preserve repository during deployment** was enabled and verified
through the official Coolify API for these relative file binds. Consult Coolify's
deployment records for the running commit.

1. Deploy the conference consent changes first and check the shared cookie scope.
   Review the conference tracking/privacy notice with the responsible owner.
2. In Coolify, enable **General > Build pipeline > Preserve repository during deployment**.
3. Release this repository's Compose/template/asset changes through the normal
   Git/Coolify path, only after explicit release approval. Do not work around
   Coolify with SSH, manual containers or files copied into running containers.
4. Verify the public shop still loads, the self-hosted script returns HTTP 200
   with a JavaScript content type, and the CSP contains the required destinations.
5. With an authorised test flow, verify the confirmation and consent cases.
   Local tests do not certify the running payment flow or Google's attribution.

Both mounts are read-only. Missing source files fail deployment rather than being
silently created as directories. No file is copied into the persistent data
volume, so rolling back the Compose mounts removes the override and script.
The original order template and data remain untouched.

**Cleanup after the conference (6 November 2026):** remove the two file mounts,
the extra CSP setting, and this temporary template/script through Git and Coolify.
Review whether the conference Google Ads tag is still needed. Do not leave a
second, permanent tracking subsystem behind.

## Checks

```sh
uv run --no-project --with 'Django==4.2.28' python tests/test_confirmation.py
node --test tests/confirmation.test.cjs
POSTGRES_PASSWORD=validation-placeholder docker compose config --quiet
```

These checks render the override with the running Django 4.2.28 version and test
the script in an isolated JavaScript VM without contacting Google or creating
orders. The conference repository additionally provides `npm run test:browser`:
Chromium checks consent, iframe/new-tab flows, rejection, withdrawal and synthetic
confirmation payloads with all measurement intercepted. It does not make a real
Stripe payment. The security inventory/update plan is maintained separately in
`~/Development/mautic-world-conference/docs/security-readiness-2026-10-21.md`.
Pretix remains pinned at 2026.2.0 for this tracking-only release; the documented
security upgrade is a separate, urgent operation.

## Sources

- Pretix 2026.2.0 `settings.py`: Django searches `DATA_DIR/templates` before app templates.
- Django supports extending the same template name from an override directory.
- https://coolify.io/docs/applications/builds/docker-compose (repository-relative binds)
- https://developers.google.com/tag-platform/security/guides/csp (Google Ads sources)
