"""Linux CI API gate for the isolated prototype, never reads user credentials."""
import base64
import json
import os
from pathlib import Path
import re
import time
import urllib.request

log = Path('work/prototype-serve.log').read_text()
password = re.findall(r'^server password (.+)$', log, re.M)[-1].strip()
authorization = 'Basic ' + base64.b64encode(('opencode:' + password).encode()).decode()


def request(method, path, body=None):
    req = urllib.request.Request('http://127.0.0.1:4096' + path, method=method,
        headers={'Authorization': authorization, 'Content-Type': 'application/json'},
        data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()
        return json.loads(data) if data else None


created = []
session = None
try:
    shell = request('POST', '/api/shell', {'command': 'printf ANDCODE_SOURCE_SHELL_OK', 'timeout': 10000})['data']
    for _ in range(100):
        state = request('GET', '/api/shell/' + shell['id'])['data']
        if state['status'] != 'running':
            break
        time.sleep(.1)
    assert state.get('exit') == 0, state
    assert 'ANDCODE_SOURCE_SHELL_OK' in request('GET', '/api/shell/' + shell['id'] + '/output')['data']['output']
    # Ordinary Web PTY must really allocate a tty, resize, and execute a child.
    marker = Path(os.environ['HOME']) / 'ordinary-pty-ok'
    assert not marker.exists()
    pty = request('POST', '/api/pty', {'command': '/bin/sh', 'args': ['-c', 'test -t 0 && printf ANDCODE_SOURCE_PTY_OK > "$HOME/ordinary-pty-ok"; exec /bin/sh'], 'title': 'andcode source CI'})['data']
    created.append(('/api/pty/', pty['id']))
    request('PUT', '/api/pty/' + pty['id'], {'size': {'cols': 91, 'rows': 31}})
    for _ in range(100):
        if marker.exists():
            break
        time.sleep(.1)
    assert marker.read_text() == 'ANDCODE_SOURCE_PTY_OK'
    session = request('POST', '/api/session', {'title': 'andcode source native CI'})['data']['id']
    pty = request('POST', '/api/experimental/session/' + session + '/terminal', {'command': '/bin/sh', 'args': ['-c', 'test -t 0 && printf ANDCODE_SOURCE_PERSISTENT_PTY_OK; exec /bin/sh'], 'title': 'andcode source CI', 'env': {}, 'size': {'cols': 80, 'rows': 24}})['data']
    created.append(('/api/experimental/persistent-pty/', pty['id']))
    for _ in range(100):
        snapshot = request('GET', '/api/experimental/persistent-pty/' + pty['id'] + '/snapshot')['data']
        if 'ANDCODE_SOURCE_PERSISTENT_PTY_OK' in json.dumps(snapshot):
            break
        time.sleep(.1)
    assert 'ANDCODE_SOURCE_PERSISTENT_PTY_OK' in json.dumps(snapshot)
    print('ANDCODE_SOURCE_SHELL_PTY_OK (Linux CI; not Android acceptance)')
finally:
    for prefix, identifier in reversed(created):
        request('DELETE', prefix + identifier)
    if session:
        request('DELETE', '/api/session/' + session)
