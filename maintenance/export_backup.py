"""One-off, encrypted maintenance exports through native Coolify application tasks.

No running-container dependency installation, code patch, SSH, or Docker operation
is used on production. Plaintext stays outside public paths. Only authenticated
OpenSSL CMS ciphertext is briefly served by the existing media route, downloaded,
hash-checked and removed. Receiver private keys live in Infisical, never in task
commands or reports. These are one-off pre-upgrade backups, not a recurring DR plan.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone

from coolify_task import Task

PROJECT = '055347c7-acc6-443e-aab4-e05213098e41'
INFISICAL = ['--projectId', PROJECT, '--env', 'prod', '--domain', 'https://secrets.moorwald.dev/api', '--silent']
ROOT = Path.home() / 'Backups/mautic-maintenance'
APPS = {
    'pretix': ('zwocw8osw4sgk00w48ko8gkk', 'pretix', '/data', 'https://tickets.mautic.org'),
    'kirby': ('s0c0wsc4scs000s0goko4ccg', 'app', '/var/www/html/content', 'https://mauticon.mautic.org'),
}


def process(args, *, allow_failure=False):
    result = subprocess.run(args, capture_output=True, timeout=120)
    if result.returncode and not allow_failure:
        raise RuntimeError(f'{args[0]} failed, exit {result.returncode}; raw output withheld')
    return result


def secret_value(name):
    result = process(['infisical', 'secrets', 'get', name, *INFISICAL, '--output', 'json'])
    value = json.loads(result.stdout)
    return value[0]['secretValue']


def cms_selftest(folder, key, cert):
    plain = folder / 'synthetic.txt'
    plain.write_bytes(b'synthetic CMS interoperability and authentication test\n')
    cipher = folder / 'synthetic.cms'
    decoded = folder / 'synthetic.decoded'
    args = ['docker', 'run', '--rm', '--network', 'none', '--user', f'{os.getuid()}:{os.getgid()}',
            '--entrypoint', 'openssl', '-v', f'{cert}:/in/cert.pem:ro',
            '-v', f'{plain}:/in/plain:ro', '-v', f'{folder}:/out',
            'pretix/standalone:2026.2.0', 'cms', '-encrypt', '-binary', '-aes-256-gcm',
            '-outform', 'DER', '-in', '/in/plain', '-out', '/out/synthetic.cms',
            '-recip', '/in/cert.pem', '-keyopt', 'rsa_padding_mode:oaep',
            '-keyopt', 'rsa_oaep_md:sha256']
    process(args)
    process(['openssl', 'cms', '-decrypt', '-binary', '-inform', 'DER',
             '-in', str(cipher), '-inkey', str(key), '-out', str(decoded)])
    assert decoded.read_bytes() == plain.read_bytes()
    damaged = bytearray(cipher.read_bytes())
    damaged[-1] ^= 1
    cipher.write_bytes(damaged)
    rejected = process(['openssl', 'cms', '-decrypt', '-binary', '-inform', 'DER',
                        '-in', str(cipher), '-inkey', str(key), '-out', str(decoded)], allow_failure=True)
    assert rejected.returncode != 0, 'CMS authentication must reject tampering'
    for p in (plain, cipher, decoded):
        p.unlink()
    print('PASS: production-image CMS encryption, local decryption and tamper rejection')


def init():
    os.umask(0o077)
    session = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(5)
    folder = ROOT / session
    folder.mkdir(parents=True, mode=0o700)
    cert = folder / 'receiver.crt'
    key_name = 'MAUTIC_MAINT_BACKUP_KEY_' + session.replace('-', '_').upper()
    with tempfile.TemporaryDirectory(prefix='mwc-receiver-') as temp:
        private = Path(temp) / 'key.pem'
        process(['openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-nodes',
                 '-keyout', str(private), '-out', str(cert), '-days', '365',
                 '-subj', '/CN=Mautic maintenance backup receiver'])
        cms_selftest(folder, private, cert)
        process(['infisical', 'secrets', 'set', f'{key_name}=@{private}', *INFISICAL, '--output', 'json'])
        assert secret_value(key_name).strip().encode() == private.read_bytes().strip()
    config = {'session': session, 'key_secret': key_name,
              'certificate_sha256': hashlib.sha256(cert.read_bytes()).hexdigest(),
              'cryptography': 'OpenSSL CMS AuthEnvelopedData AES-256-GCM with RSA-OAEP-SHA256'}
    (folder / 'receiver.json').write_text(json.dumps(config, indent=2))
    print('Receiver and public certificate:', folder)
    print('Private receiver key stored and verified in Infisical; no local key retained')
    return folder


def checked(command):
    if len(command) > 255:
        raise ValueError(f'Maintenance command exceeds verified limit: {len(command)}')
    return command


def upload_certificate(task, work, cert):
    encoded = base64.b64encode(cert.read_bytes()).decode()
    for index, start in enumerate(range(0, len(encoded), 160)):
        task.run(checked(f'printf %s {shlex.quote(encoded[start:start + 160])} > {work}/k{index:02d}'))
    output = task.run(checked(f'cat {work}/k[0-9][0-9] | base64 -d > {work}/cert.pem && sha256sum {work}/cert.pem'))
    assert output.split()[0] == hashlib.sha256(cert.read_bytes()).hexdigest()


def decrypt(folder, name):
    config = json.loads((folder / 'receiver.json').read_text())
    with tempfile.TemporaryDirectory(prefix='mwc-decrypt-') as temp:
        key = Path(temp) / 'key.pem'
        key.write_text(secret_value(config['key_secret']))
        key.chmod(0o600)
        partial = folder / f'{name}.tar.partial'
        try:
            process(['openssl', 'cms', '-decrypt', '-binary', '-inform', 'DER',
                     '-in', str(folder / f'{name}.cms'), '-inkey', str(key),
                     '-out', str(partial)])
            partial.chmod(0o600)
            partial.replace(folder / f'{name}.tar')
        finally:
            partial.unlink(missing_ok=True)


def export(folder, name, *, refresh=False):
    os.umask(0o077)
    config = json.loads((folder / 'receiver.json').read_text())
    nonce = config['session'].rsplit('-', 1)[1]
    assert len(nonce) == 10 and all(c in '0123456789abcdef' for c in nonce)
    app, container, base, origin = APPS[name]
    work = f'{base}/.m{nonce}'
    media_root = '/data/media' if name == 'pretix' else '/var/www/html/media'
    public = f'{media_root}/mwc-maint-{secrets.token_hex(16)}.cms'
    remote_dump = f'mwc-pre-{nonce}.dump'
    with Task(app, container) as task:
        if refresh:
            previous = json.loads((folder / f'{name}-backup.json').read_text())
            assert previous['app'] == app and previous['remote_workdir'] == work
            digest = task.run(checked(f'sha256sum {work}/cert.pem')).split()[0]
            assert digest == config['certificate_sha256'], 'Refuse an unverified existing receiver certificate'
        else:
            task.run(checked(f'umask 077; mkdir -m 700 {work}'))
            upload_certificate(task, work, folder / 'receiver.crt')
        if name == 'pretix':
            # Dump in PGDATA so the original consistent dump survives container replacement.
            # The application reads only this explicitly created file via the configured DB role.
            with Task(app, 'db', 'MWC native PostgreSQL backup') as database:
                probe = database.run('psql -U pretix -d pretix -tAc "select rolsuper from pg_roles where rolname=current_user"')
                assert probe.strip() == 't', 'Configured DB role cannot perform this authorized server-file export'
                directory = '/var/lib/postgresql/data/'
                database.run(checked(f'umask 077; pg_dump -U pretix -d pretix -Fc -f {directory}{remote_dump}.part'))
                database.run(checked(f'chown postgres:postgres {directory}{remote_dump}.part && mv -f {directory}{remote_dump}.part {directory}{remote_dump}'))
                info = database.run(checked(f'stat -c %s /var/lib/postgresql/data/{remote_dump}'))
                assert 0 < int(info.strip()) < 256 * 1024 * 1024, 'Dump exceeds bounded in-memory transfer size'
            code = f'from django.db import connection as c;q=c.cursor();q.execute("select pg_read_binary_file(%s)",["{remote_dump}"]);open("{work}/db","wb").write(q.fetchone()[0])'
            task.run(checked('DJANGO_SETTINGS_MODULE=production_settings python -m pretix shell -c ' + shlex.quote(code)))
            command = f'tar --exclude=./logs --exclude="./.m??????????" --exclude="./media/mwc-maint-*.cms" -czf {work}/data.tgz -C /data .'
            task.run(checked(command))
            members = 'db data.tgz'
        else:
            command = f'tar --exclude="content/.m??????????" -czf {work}/data.tgz -C /var/www/html content site/accounts site/config site/sessions'
            task.run(checked(command))
            members = 'data.tgz'
        task.run(checked(f'tar -cf {work}/bundle.tar -C {work} {members}'))
        command = f'cd {work}; umask 077; openssl cms -encrypt -binary -aes-256-gcm -outform DER -in bundle.tar -out export.cms -recip cert.pem -keyopt rsa_padding_mode:oaep -keyopt rsa_oaep_md:sha256'
        task.run(checked(command))
        wanted = task.run(checked(f'sha256sum {work}/export.cms')).split()[0]
        assert len(wanted) == 64
        published = False
        try:
            task.run(checked(f'mv {work}/export.cms {public} && chmod 644 {public}'))
            published = True
            url = origin + '/media/' + public.rsplit('/', 1)[1]
            request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            target = folder / f'{name}.cms'
            partial = folder / f'{name}.cms.partial'
            try:
                with urllib.request.urlopen(request, timeout=120) as response, partial.open('wb') as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                assert hashlib.sha256(partial.read_bytes()).hexdigest() == wanted, 'Encrypted export hash mismatch'
                if refresh:
                    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                    target.rename(folder / f'{name}-preflight-{timestamp}.cms')
                partial.replace(target)
            finally:
                partial.unlink(missing_ok=True)
        finally:
            if published:
                task.run(checked(f'rm -- {public}'))
        # Keep protected server-side plaintext for immediate rollback until release validation.
        report = {'app': app, 'created_at': datetime.now(timezone.utc).isoformat(),
                  'ciphertext_sha256': wanted, 'ciphertext_bytes': target.stat().st_size,
                  'key_secret': config['key_secret'], 'remote_workdir': work,
                  'remote_db_dump': remote_dump if name == 'pretix' else None,
                  'public_ciphertext_removed': True}
        (folder / f'{name}-backup.json').write_text(json.dumps(report, indent=2))
    decrypt(folder, name)
    print(f'{name}: encrypted backup downloaded, hash-checked, decrypted in private local storage; no plaintext was publicly served')
    print('Backup directory:', folder)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['init', 'pretix', 'kirby'])
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--refresh', action='store_true', help='Refresh this verified receiver; keep the previous encrypted snapshot')
    args = parser.parse_args()
    if args.action == 'init':
        init()
    else:
        if args.directory is None:
            parser.error('--directory is required')
        export(args.directory.resolve(), args.action, refresh=args.refresh)
