"""Linux CI: exercise the real OpenTUI dlopen path, not just serve/version."""
import fcntl
import errno
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
    # Use the ELF's staged interpreter. Explicit `ld.so opencode` changes
    # /proc/self/exe and can break the CLI's self-spawn path in --standalone.
    process = subprocess.Popen([str(exe), '--standalone'], stdin=slave, stdout=slave,
                               stderr=slave, env=env, preexec_fn=controlling_terminal)
    os.close(slave)
    slave = None
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        assert process.poll() is None, f'TUI exited before native rendering ({process.returncode}): {bytes(output[-4096:])!r}'
        maps = Path(f'/proc/{process.pid}/maps').read_text()
        mapped = str(stage / opentui[0]) in maps
        if select.select([master], [], [], .2)[0]:
            try:
                output.extend(os.read(master, 65536))
            except OSError as error:
                if error.errno != errno.EIO:
                    raise
                raise AssertionError(f'TUI PTY closed ({process.poll()}): {bytes(output[-4096:])!r}') from error
        if len(output) > 2 * 1024 * 1024:
            raise AssertionError('Unexpectedly large TUI output')
        # dlopen alone is not enough: require terminal rendering with visible
        # application content, without waiting for a model/provider connection.
        if mapped and b'\x1b[' in output and b'opencode' in output.lower():
            break
    assert mapped, 'Preinstalled OpenTUI was not actually mapped'
    if env.get('ANDCODE_LOADER'):
        runtime = Path(env['ANDCODE_LOADER']).resolve().parent
        assert str(runtime / 'ld-linux-aarch64.so.1') in maps, 'TUI used host ELF interpreter'
        assert str(runtime / 'libc.so.6') in maps, 'TUI used host libc instead of staged runtime'
        for line in maps.splitlines():
            if any(name in line for name in ('libstdc++.so.', 'libgcc_s.so.')):
                assert str(runtime) + '/' in line, 'TUI used unstaged C++ runtime'
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
