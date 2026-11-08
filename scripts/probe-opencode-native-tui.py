"""Linux CI: exercise the real OpenTUI dlopen path, not just serve/version."""
import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
import time


exe = Path(sys.argv[1]).resolve(strict=True)
stage = Path(os.environ['ANDCODE_EXE_DIR']).resolve(strict=True)
manifest = (stage.parent / 'oc2-native.tsv').read_text().splitlines()
opentui = [row.split('\t')[0] for row in manifest if '/@opentui/core-linux-arm64/' in row]
assert len(opentui) == 1, 'Expected exactly one staged OpenTUI'
master, slave = pty.openpty()
fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 35, 100, 0, 0))
env = dict(os.environ, TERM='xterm-256color', COLORTERM='truecolor')
env.pop('CI', None)
process = None
output = bytearray()
mapped = False


def controlling_terminal():
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


try:
    process = subprocess.Popen([str(exe), '--standalone'], stdin=slave, stdout=slave,
                               stderr=slave, env=env, preexec_fn=controlling_terminal)
    os.close(slave)
    slave = None
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        assert process.poll() is None, 'TUI exited before native rendering'
        maps = Path(f'/proc/{process.pid}/maps').read_text()
        mapped = str(stage / opentui[0]) in maps
        if select.select([master], [], [], .2)[0]:
            output.extend(os.read(master, 65536))
        if len(output) > 2 * 1024 * 1024:
            raise AssertionError('Unexpectedly large TUI output')
        # dlopen alone is not enough: require terminal rendering with visible
        # application content, without waiting for a model/provider connection.
        if mapped and b'\x1b[' in output and b'opencode' in output.lower():
            break
    assert mapped, 'Preinstalled OpenTUI was not actually mapped'
    assert b'\x1b[' in output and b'opencode' in output.lower(), 'No rendered OpenCode TUI'
    print('ANDCODE_SOURCE_TUI_NATIVE_OK (Linux CI only)')
finally:
    if process:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    if slave is not None:
        os.close(slave)
    os.close(master)
