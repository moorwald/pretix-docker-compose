"""Short, audited maintenance commands through Coolify's disabled one-off tasks.

Never put credentials or customer data in commands or print unfiltered task output.
"""
import json
import subprocess
import time

CLI = '/home/sdoering/.local/share/coolify-cli/1.8.0/coolify'


def cli(*args, json_output=False):
    result = subprocess.run(
        [CLI, '--context', 'moorwald', '--format', 'json', *args],
        capture_output=True, text=True, timeout=40,
    )
    if result.returncode:
        raise RuntimeError(f'Coolify {args[:3]} failed, exit {result.returncode}; raw output withheld')
    return json.loads(result.stdout) if json_output else result.stdout


class Task:
    def __init__(self, app, container, name='MWC isolated upgrade maintenance'):
        self.app = app
        result = cli('app', 'task', 'create', app, '--name', name,
                     '--command', 'true', '--container', container,
                     '--frequency', '0 0 1 1 *', '--enabled=false', '--timeout', '1800',
                     json_output=True)
        self.uuid = result['uuid']
        print(f'Temporary disabled task: {self.uuid}', flush=True)

    def run(self, command, *, timeout=1800):
        if len(command) > 255:
            raise ValueError(f'Command exceeds verified Coolify limit: {len(command)}')
        cli('app', 'task', 'update', self.app, self.uuid, '--command', command)
        prior = cli('app', 'task', 'executions', self.app, self.uuid, json_output=True)
        old = {item['uuid'] for item in prior}
        # Never automatically retry this mutation: a timeout may mean it was queued.
        cli('app', 'task', 'execute', self.app, self.uuid)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            executions = cli('app', 'task', 'executions', self.app, self.uuid, json_output=True)
            current = [item for item in executions if item['uuid'] not in old]
            if current:
                item = current[0]
                if item['status'] == 'success':
                    return item.get('message', '')
                if item['status'] in ('failed', 'cancelled'):
                    raise RuntimeError(f'Maintenance task failed: {self.uuid}, execution {item["uuid"]}; raw output withheld')
            time.sleep(1)
        raise TimeoutError(f'Maintenance task still pending: {self.uuid}; do not blindly repeat it')

    def close(self):
        cli('app', 'task', 'delete', self.app, self.uuid)
        print(f'Temporary task removed: {self.uuid}', flush=True)

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.close()
