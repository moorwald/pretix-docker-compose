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
