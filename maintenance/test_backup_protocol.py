"""Synthetic local protocol test. Never touches a Coolify resource or real data."""
import subprocess
import time
import uuid


def run(*args):
    result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f'Local protocol command failed: {args[:2]}: {result.stderr}')
    return result.stdout.strip()


def main():
    suffix = uuid.uuid4().hex[:10]
    network = 'mwc-protocol-' + suffix
    database = network + '-db'
    client = network + '-client'
    run('network', 'create', '--internal', network)
    try:
        run('run', '-d', '--name', database, '--network', network, '--network-alias', 'db',
            '-e', 'POSTGRES_USER=pretix', '-e', 'POSTGRES_DB=pretix',
            '-e', 'POSTGRES_PASSWORD=synthetic-protocol-test', 'postgres:16-alpine')
        for _ in range(30):
            ready = subprocess.run(['docker', 'exec', database, 'pg_isready', '-h', '127.0.0.1', '-U', 'pretix'], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise TimeoutError('Synthetic PostgreSQL did not start')
        run('exec', database, 'psql', '-U', 'pretix', '-d', 'pretix', '-c',
            "CREATE TABLE maintenance_probe (id integer PRIMARY KEY, value text); INSERT INTO maintenance_probe VALUES (1, 'synthetic test only');")
        run('exec', database, 'sh', '-c',
            'umask 077; pg_dump -U pretix -d pretix -Fc -f /var/lib/postgresql/data/mwc-protocol.dump && chown postgres:postgres /var/lib/postgresql/data/mwc-protocol.dump')
        expected = run('exec', database, 'sha256sum', '/var/lib/postgresql/data/mwc-protocol.dump').split()[0]
        code = 'from django.db import connection as c;import hashlib;q=c.cursor();q.execute("select pg_read_binary_file(%s)",["mwc-protocol.dump"]);print(hashlib.sha256(q.fetchone()[0]).hexdigest())'
        actual = run('run', '--rm', '--name', client, '--network', network,
                     '-e', 'PRETIX_PRETIX_URL=http://qa', '-e', 'PRETIX_PRETIX_DATADIR=/data',
                     '-e', 'PRETIX_DATABASE_BACKEND=postgresql', '-e', 'PRETIX_DATABASE_NAME=pretix',
                     '-e', 'PRETIX_DATABASE_USER=pretix', '-e', 'PRETIX_DATABASE_PASSWORD=synthetic-protocol-test',
                     '-e', 'PRETIX_DATABASE_HOST=db', '-e', 'DJANGO_SETTINGS_MODULE=production_settings',
                     '--entrypoint', 'python', 'pretix/standalone:2026.2.0', '-m', 'pretix', 'shell', '-c', code)
        assert expected == actual, 'Native dump and received bytes must be identical'
        run('exec', database, 'createdb', '-U', 'pretix', 'restored_protocol')
        run('exec', database, 'pg_restore', '-U', 'pretix', '-d', 'restored_protocol', '/var/lib/postgresql/data/mwc-protocol.dump')
        assert run('exec', database, 'psql', '-U', 'pretix', '-d', 'restored_protocol', '-tAc',
                   'SELECT COUNT(*) FROM maintenance_probe') == '1'
        print('PASS: exact native pg_dump transfer and successful pg_restore using synthetic data')
        print('PASS: unmodified Pretix image, configured database authentication, isolated internal network')
    finally:
        for name in (client, database):
            result = subprocess.run(['docker', 'rm', '-fv', name], capture_output=True, text=True)
            # --rm normally removed the short-lived client before cleanup.
            if result.returncode and 'No such container' not in result.stderr:
                raise RuntimeError(f'Failed to remove owned local test container {name}')
        run('network', 'rm', network)


if __name__ == '__main__':
    main()
