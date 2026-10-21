"""Restore the encrypted export into disposable, offline local PostgreSQL databases.

The baseline and upgrade use independent database/data copies. No ports are
published, no workers are started, and no outgoing mail/payment request can leave
the internal Docker network. Reports contain only counts, hashes and status codes.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import tarfile
import time
import uuid

from export_backup import secret_value


def docker(*args, timeout=180, env=None):
    result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout, env=env)
    if result.returncode:
        # pg_restore or Django errors can contain private row values/URLs.
        stages = re.findall(r'^MWC_QA_STAGE ([a-z_]+)$', result.stdout, re.M)
        classes = re.findall(r'^([A-Za-z_.]*(?:Error|Exception)):', result.stderr, re.M)
        statuses = re.findall(r'^AssertionError: ((?:health|shop|widget) status [0-9]+)$', result.stderr, re.M)
        raise RuntimeError(f'Local QA failed in {args[:2]}; stage={stages[-1:]}, class={classes[-1:]}, status={statuses}; raw output withheld')
    return result.stdout


CHECK = r'''
import hashlib, json, logging, os
logging.disable(logging.CRITICAL)
from django.db import connection
from django.test import Client
from pretix.base.models import Order, OrderPosition, Invoice, Organizer, Event
from django_scopes import scope
checks = {}
for path, key in [("/healthcheck/", "health"), ("/Mautic/mwc2026/", "shop"), ("/widget/v1.en.js", "widget")]:
    print("MWC_QA_STAGE " + key, flush=True)
    r = Client(raise_request_exception=False, HTTP_HOST="tickets.mautic.org").get(path, secure=True)
    checks[key] = r.status_code
    assert r.status_code == 200, key + " status " + str(r.status_code)
print("MWC_QA_STAGE existing_paid_order", flush=True)
organizer = Organizer.objects.get(slug="Mautic")
with scope(organizer=organizer):
    event = Event.objects.get(organizer=organizer, slug="mwc2026")
with scope(organizer=organizer, event=event):
    order = Order.objects.filter(event=event, status="p", testmode=False).first()
assert order is not None, "No paid order available for existing-order regression test"
private_path = "/Mautic/mwc2026/order/" + order.code + "/" + order.secret + "/"
r = Client(raise_request_exception=False, HTTP_HOST="tickets.mautic.org").get(private_path, secure=True)
checks["existing_paid_order"] = r.status_code
assert r.status_code == 200, "Existing order view did not render"
checks["order_page_contains_google_tag"] = b"googletagmanager.com/gtag/js" in r.content
assert checks["order_page_contains_google_tag"] is False
print("MWC_QA_STAGE pdf", flush=True)
with scope(organizer=organizer, event=event):
    from pretix.plugins.ticketoutputpdf.ticketoutput import PdfTicketOutput
    position = OrderPosition.objects.filter(order__event=event, order__status="p", order__testmode=False, item__admission=True, canceled=False).first()
    assert position is not None, "No admission position for copied ticket PDF test"
    filename, mime, pdf = PdfTicketOutput(event).generate(position)
    checks["ticket_pdf"] = mime == "application/pdf" and pdf.startswith(b"%PDF")
    assert checks["ticket_pdf"], "Copied ticket PDF generation failed"
    invoice = Invoice.objects.filter(order__event=event).exclude(file="").first()
    assert invoice is not None, "No stored invoice PDF for backup verification"
    with invoice.file.open("rb") as stream:
        checks["invoice_pdf_preserved"] = stream.read(5) == b"%PDF-"
    assert checks["invoice_pdf_preserved"], "Copied invoice PDF missing or invalid"
print("MWC_QA_STAGE backend", flush=True)
c = Client(raise_request_exception=False, HTTP_HOST="tickets.mautic.org")
r = c.get("/control/login", secure=True)
checks["backend_login"] = r.status_code
assert r.status_code == 200, "Backend login did not render"
r = c.get("/api/v1/organizers/Mautic/events/mwc2026/", secure=True,
          HTTP_AUTHORIZATION="Token " + os.environ["MWC_QA_TOKEN"])
checks["authenticated_event_api"] = r.status_code
assert r.status_code == 200, "Copied event API authentication failed"
# Only stable financial/access fields are hashed, never printed.
tables = {
 "pretixbase_order": ["id", "code", "status", "total", "secret"],
 "pretixbase_orderposition": ["id", "order_id", "item_id", "price", "secret"],
 "pretixbase_orderpayment": ["id", "order_id", "amount", "state", "provider"],
}
financial = {}
print("MWC_QA_STAGE financial", flush=True)
with connection.cursor() as q:
    for table, columns in tables.items():
        q.execute("SELECT " + ",".join(columns) + " FROM " + table + " ORDER BY id")
        rows = q.fetchall()
        payload = json.dumps(rows, default=str, separators=(",", ":")).encode()
        financial[table] = {"count": len(rows), "sha256": hashlib.sha256(payload).hexdigest()}
print("MWC_QA_RESULT " + json.dumps({"checks": checks, "financial": financial}))
'''


def unpack(folder):
    clear = folder / 'pretix-clear'
    clear.mkdir(mode=0o700, exist_ok=True)
    with tarfile.open(folder / 'pretix.tar') as archive:
        assert set(archive.getnames()) == {'db', 'data.tgz'}
        assert all(member.isfile() for member in archive.getmembers())
        archive.extractall(clear, filter='data')
    for mode in ('baseline', 'upgrade'):
        data = folder / f'pretix-{mode}-data'
        data.mkdir(mode=0o700, exist_ok=True)
        with tarfile.open(clear / 'data.tgz') as archive:
            archive.extractall(data, filter='data')
        assert (data / '.secret').is_file(), 'Application encryption secret must be preserved'
    return clear


def main(folder, target_image='pretix/standalone:2026.8.0', extra_check='', target_environment=None):
    os.umask(0o077)
    clear = unpack(folder)
    suffix = uuid.uuid4().hex[:10]
    network = 'mwc-upgrade-qa-' + suffix
    pg = network + '-db'
    redis = network + '-redis'
    clients = []
    docker('network', 'create', '--internal', network)
    assert docker('network', 'inspect', network, '--format', '{{.Internal}}').strip() == 'true'
    report = {'network_internal': True, 'ports_published': False, 'workers_started': False}
    stage_env = {**os.environ, 'MWC_QA_TOKEN': secret_value('MAUTIC_PRETIX_ADMIN_TOKEN')}
    try:
        docker('run', '-d', '--name', pg, '--network', network, '--network-alias', 'db',
               '-e', 'POSTGRES_USER=pretix', '-e', 'POSTGRES_PASSWORD=isolated-restore-only',
               '-v', f'{clear / "db"}:/restore/db:ro', 'postgres:16-alpine')
        for _ in range(30):
            ready = subprocess.run(['docker', 'exec', pg, 'pg_isready', '-h', '127.0.0.1', '-U', 'pretix'], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise TimeoutError('Local PostgreSQL did not start')
        docker('run', '-d', '--name', redis, '--network', network, '--network-alias', 'redis', 'redis:7-alpine')
        for mode, image in [('baseline', 'pretix/standalone:2026.2.0'), ('upgrade', target_image)]:
            database = 'pretix_' + mode
            docker('exec', pg, 'createdb', '-U', 'pretix', database)
            docker('exec', pg, 'pg_restore', '--exit-on-error', '-U', 'pretix', '-d', database, '/restore/db')
            client = network + '-' + mode
            clients.append(client)
            custom_env = []
            if mode == 'upgrade':
                for key, value in (target_environment or {}).items():
                    custom_env.extend(['-e', key + '=' + value])
            common = ['run', '--rm', '--name', client, '--network', network,
                      '--user', f'{os.getuid()}:{os.getgid()}',
                      '-v', f'{folder / ("pretix-" + mode + "-data")}:/data',
                      '-e', 'MWC_QA_TOKEN', '-e', 'PRETIX_PRETIX_URL=https://tickets.mautic.org',
                      '-e', 'PRETIX_PRETIX_DATADIR=/data', '-e', 'PRETIX_DATABASE_BACKEND=postgresql',
                      '-e', 'PRETIX_DATABASE_NAME=' + database, '-e', 'PRETIX_DATABASE_USER=pretix',
                      '-e', 'PRETIX_DATABASE_PASSWORD=isolated-restore-only', '-e', 'PRETIX_DATABASE_HOST=db',
                      '-e', 'PRETIX_MAIL_HOST=127.0.0.1',
                      '-e', 'PRETIX_REDIS_LOCATION=redis://redis:6379/' + ('0' if mode == 'baseline' else '3'),
                      '-e', 'PRETIX_REDIS_SESSIONS=true',
                      '-e', 'PRETIX_CELERY_BACKEND=redis://redis:6379/' + ('1' if mode == 'baseline' else '4'),
                      '-e', 'PRETIX_CELERY_BROKER=redis://redis:6379/' + ('2' if mode == 'baseline' else '5'),
                      '-e', 'DJANGO_SETTINGS_MODULE=production_settings',
                      *custom_env, '--entrypoint', 'python', image, '-m', 'pretix']
            if mode == 'upgrade':
                output = docker(*common, 'migrate', '--noinput', timeout=600, env=stage_env)
                applied = [line.strip() for line in output.splitlines() if line.strip().startswith('Applying ')]
                report['applied_migrations'] = applied
            output = docker(*common, 'shell', '-c', CHECK + (extra_check if mode == 'upgrade' else ''), env=stage_env)
            lines = [line for line in output.splitlines() if line.startswith('MWC_QA_RESULT ')]
            assert len(lines) == 1, 'Expected one sanitized QA result'
            report[mode] = json.loads(lines[0].removeprefix('MWC_QA_RESULT '))
            extra = [line for line in output.splitlines() if line.startswith('MWC_QA_EXTRA ')]
            if extra:
                report[mode]['extra_checks'] = [json.loads(line.removeprefix('MWC_QA_EXTRA ')) for line in extra]
            print(mode, 'restored and passed HTTP/financial checks', flush=True)
        assert report['baseline']['financial'] == report['upgrade']['financial'], 'Financial/access fields changed during migration'
        report['financial_and_access_fields_preserved'] = True
        # Prove a complete database AND file rollback after the real migrations.
        docker('exec', pg, 'dropdb', '-U', 'pretix', '--force', 'pretix_upgrade')
        docker('exec', pg, 'createdb', '-U', 'pretix', 'pretix_upgrade')
        docker('exec', pg, 'pg_restore', '--exit-on-error', '-U', 'pretix', '-d', 'pretix_upgrade', '/restore/db')
        rollback_data = folder / 'pretix-upgrade-data'
        shutil.rmtree(rollback_data)
        rollback_data.mkdir(mode=0o700)
        with tarfile.open(clear / 'data.tgz') as archive:
            archive.extractall(rollback_data, filter='data')
        rollback_command = common.copy()
        rollback_command[rollback_command.index(target_image)] = 'pretix/standalone:2026.2.0'
        output = docker(*rollback_command, 'shell', '-c', CHECK, env=stage_env)
        lines = [line for line in output.splitlines() if line.startswith('MWC_QA_RESULT ')]
        assert len(lines) == 1
        report['rollback'] = json.loads(lines[0].removeprefix('MWC_QA_RESULT '))
        assert report['rollback']['financial'] == report['baseline']['financial']
        report['database_and_file_rollback_proven'] = True
        print('rollback restored and passed HTTP/PDF/financial checks', flush=True)
        (folder / 'pretix-restore-upgrade-qa.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    finally:
        for name in [*clients, redis, pg]:
            result = subprocess.run(['docker', 'rm', '-fv', name], capture_output=True, text=True)
            if result.returncode and 'No such container' not in result.stderr:
                raise RuntimeError(f'Failed to remove local QA container {name}')
        docker('network', 'rm', network)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    main(parser.parse_args().directory.resolve())
