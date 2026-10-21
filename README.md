# Mautic Pretix deployment

Coolify app `zwocw8osw4sgk00w48ko8gkk`, Git-based Compose, automatic deployment
from `main`. Runtime remains `pretix/standalone:2026.2.0`. Branding is documented
in `branding/README.md`.

## Purchase tracking withdrawn, 21 October 2026

Purchase measurement is **not enabled**. No custom order template, tracking asset,
Google CSP extension or host bind is deployed. The conference site's Klaro consent
and optional landing-page Google Ads tag remain separate from this shop.
Use Pretix's financial totals for manual reconciliation.

The temporary confirmation snippet passed unit and stubbed-browser checks, but a
subsequent isolated test with the **real Google tag** demonstrated that overriding
`page_location` and `page_referrer` does not protect the private order URL: Google
constructs additional `top` and `dl` parameters containing that URL. All measurement
requests in that test were intercepted; no fabricated conversions were sent.
The live hook was immediately disabled in `0b10e37`, completed at
2026-10-21 11:19:05 UTC. This withdrawal then removes its unused image additions.

Do **not** reactivate the old snippet. A future implementation needs a public,
cross-origin measurement document, no-referrer embedding and a narrowly validated
message containing only non-secret transaction ID, amount and currency. Google
must never execute in the private order-page context. That replacement is not
implemented or approved by this rollback.

Actual customer exposure during the brief rollout is not established by the
synthetic test. Check retained access logs for confirmation views in the broader
2026-10-21 10:55–11:20 UTC window. Even a matching response would not prove that
advertising consent was present or that Google received a conversion. Do not print
order access secrets, names, emails or complete private URLs during that check.

## Deployment incidents

- The first file-bind deployment failed because Coolify created the file sources
  as directories. GitHub connection timeouts then delayed recovery. Git revert
  `7bbc528` restored the pre-tracking source and HTTP 200.
- The image-bundled retry exposed a second issue: a trailing semicolon crashes
  Pretix 2026.2.0's CSP parser. `de2c83b` corrected it and restored HTTP 200 before
  the real-tag privacy test prompted withdrawal.
- No application-version update or deliberate database/data migration was made.
  Repository preservation was restored to its original `false` value.

## Maintenance readiness

Pretix, Django, Stripe and the conference's Kirby/PHP stack have separate urgent
security findings. No backup/restore rehearsal was verified, so this deployment
must not be described as update-ready or patched. See
`~/Development/mautic-world-conference/docs/security-readiness-2026-10-21.md`.

Use Git/Coolify for releases. Do not use manual SSH/Docker deployment workarounds.
A Compose rollback must restore the Git branch's definition as well as selecting
a previous revision in Coolify. Do not create chargeable test orders or fake live
advertising conversions.
