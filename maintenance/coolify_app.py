"""Official Coolify API for fields not exposed by the installed CLI.

Credentials come only from Infisical and are never printed or written to disk.
Callers must project response metadata; application responses may include secrets.
"""
import json
import subprocess
import urllib.request
from functools import lru_cache

BASE = 'https://tools.moorwald.com/api/v1'


@lru_cache(maxsize=1)
def token():
    result = subprocess.run([
        'infisical', 'secrets', 'get', 'COOLIFY_API_TOKEN',
        '--projectId', 'd1e7af13-83f6-479b-b1a9-ad97c2d2826f',
        '--env', 'prod', '--domain', 'https://secrets.moorwald.dev/api',
        '--output', 'json', '--silent',
    ], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Canonical Coolify credential lookup failed; output withheld')
    return json.loads(result.stdout)[0]['secretValue']


def api(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE + path, data=data, method=method,
                                     headers={'Authorization': 'Bearer ' + token(),
                                              'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=90) as response:
        content = response.read()
        return json.loads(content) if content else None
