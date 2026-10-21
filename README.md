# Mautic Pretix deployment

Coolify app `zwocw8osw4sgk00w48ko8gkk`, Git-based Compose, automatic deployment
from `main` outside a controlled maintenance window. Runtime pin is
`pretix/standalone:2026.8.0`. Branding is documented
in `branding/README.md`.

## Isolated purchase bridge, 21 October 2026

Sven approved the new cross-origin implementation and deployment. It deliberately
replaces, rather than reactivates, the withdrawn direct-page Google design.
The source implementation is accepted only after both releases and real-SDK
live-asset checks succeed; see the protected off-server purchase release record.

- Only `Mautic/mwc2026`, genuinely paid positive-value non-test confirmations with
  `paid`/`thanks` query flags and no backend-user preview load the bridge.
- The exact 2026.8.0 upstream order template is preserved as a parent. Only the
  header is extended. Its SHA-256 is a build gate for future upstream upgrades.
- The private page runs ONLY our versioned `/static/mwc-ads-bridge-v1.js`.
  It embeds `https://mauticon.mautic.org/ads-conversion/` without a referrer.
- Exact origin/source checks and schema validation allow only the non-secret
  `Mautic-mwc2026-<order.code>`, actual gross total and currency after Ads consent.
- Google runs only in that public document, never the private order context.
  Both sides check the shared Klaro cookie. The parent CSP adds only the public
  frame origin, not Google script/connect permissions. No host-file bind is used.
- Destination: `AW-960227364/zd9jCL3G3KQdEKTQ78kD`. Browser suppression plus Google's
  stable transaction ID handle duplicates; queuing is not proof of attribution.
  Free Sprint registrations, ordinary receipt visits and refunds are not emitted.

The complete protocol, limits and real-SDK tests live in the conference repo:
`~/Development/mautic-world-conference-tracking-release/docs/google-ads-tracking.md`.
Run `python3 tracking/test_confirmation.py <protected-backup-directory>` after
building `mwc-pretix-relay-qa` to test the real restored order/PDF/API views and
nine negative template contexts offline. The bundled server-only
`/pretix/src/mwc_confirmation_probe.py` can verify production rendering through a
controlled Coolify task without executing any browser or advertising JavaScript.

The previous direct snippet was disabled at 2026-10-21 11:19:05 UTC in `0b10e37`
and removed in `65a9f0e`. Its real-SDK test revealed private URLs in `top`/`dl`
despite page-location overrides. Do **not** restore it. All measurements in the
privacy tests were intercepted; no synthetic production conversion was sent.

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
- Those earlier tracking rollouts did not update application/database versions.
  The later security upgrade is separate. Repository preservation remains `false`.

## Controlled upgrade preparation, 21 October 2026

The target `2026.8.0` has passed an isolated rehearsal using the real encrypted
backup. Native PostgreSQL restore, all intervening migrations, existing paid-order
views, public shop/widget, ticket PDF generation, stored invoice PDF, login and
authenticated event API passed. Stable financial/access fields in orders,
positions and payments remained identical. A full database AND file rollback to
`2026.2.0` passed the same checks. No workers, outgoing mail, real payments or
Google measurement ran in the test network; no ports were published.

Operator tooling is under `maintenance/`. It is not application/tracking code.

- `export_backup.py`: native `pg_dump`, data archive and OpenSSL CMS encryption
  (AES-256-GCM, RSA-OAEP-SHA256). Only ciphertext briefly uses an existing media
  download path; it is removed after transfer. Private receiver keys stay in
  Infisical. Local decrypted test data stays outside Git in a mode-0700 directory.
- `qa_pretix.py`: baseline restore, upgrade and rollback with separate local data
  copies in an internal Docker network. Reports contain only hashes/statuses.
- `pretix-hold.yml` and `pretix-hold.conf`: deliberate nginx-only maintenance,
  without app workers or automatic migration. The same volumes, environment and
  dependencies are retained. Ordinary shop/API requests intentionally return 502
  while encrypted backup downloads and controlled Coolify tasks remain available.
- `test_backup_protocol.py` and `test_hold.sh`: synthetic protocol and maintenance
  tests. Do not use native `clone --clone-volumes` casually: that implementation
  stops the source and queues source deployments per volume.

Release gates: enter hold on the old image, refresh the off-server encrypted
backup, switch hold to the target image, run/verify migrations and financial
fingerprints, then return the resource to `main` and `/docker-compose.yml`.
Prefetch the target image through a temporary, data-free Coolify resource before
pausing sales. Remove that resource after release.

Recovery: keep writers stopped in hold. The matching native SQL dump remains
protected in the database volume (`mwc-pre-<nonce>.dump`); the corresponding data
archive remains in `/data/.m<nonce>/data.tgz`. With no app connections, recreate
the database, restore it with `pg_restore --exit-on-error`, restore the matching
data archive, then select the old image. Do not run old application code against
the migrated schema. This procedure was rehearsed in the disposable copy.

These are one-off pre-upgrade backups, not an automatic recurring backup service
or proof of complete host-disaster recovery. Follow-up: agree retention and
recurring offsite backup policy. The receiver key's Infisical reference is in the
private local backup manifest, never in a public download or a task command.

The conference's Kirby/PHP stack has separate security findings and release gates.
See `~/Development/mautic-world-conference-tracking-release/docs/security-readiness-2026-10-21.md`.

Use Git/Coolify for releases. Do not use manual SSH/Docker deployment workarounds.
A Compose rollback must restore the Git branch's definition as well as selecting
a previous revision in Coolify. Do not create chargeable test orders or fake live
advertising conversions.
