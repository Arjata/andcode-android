"""Linux CI: exact staged libtinfo initialization must avoid fs-ID calls."""
import ctypes
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import time

lib = Path(sys.argv[1]).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix='andcode-tinfo-') as work:
    root = Path(work)
    # Any accidental call exits immediately, even when already unprivileged.
    fixture = root / 'trap.c'
    fixture.write_text('#include <sys/types.h>\n#include <unistd.h>\nint setfsuid(uid_t u) {(void)u; _exit(91);}\nint setfsgid(gid_t g) {(void)g; _exit(92);}\n')
    trap = root / 'trap.so'
    subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror', str(fixture), '-o', str(trap)], check=True)
    code = r'''
import ctypes,sys,os
lib=ctypes.CDLL(sys.argv[1],use_errno=True)
lib.setupterm.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
err=ctypes.c_int()
assert lib.setupterm(b'xterm-256color',1,ctypes.byref(err))==0 and err.value==1
lib._nc_safe_open3.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.c_uint]
fd=lib._nc_safe_open3(b'/dev/null',os.O_RDONLY,0); assert fd>=0; os.close(fd)
assert lib._nc_safe_open3(b'/root/andcode-forbidden',os.O_RDONLY,0)==-1
assert ctypes.get_errno()==13
print('ANDCODE_TINFO_NATIVE_INIT_OK')
'''
    subprocess.run([sys.executable, '-c', code, str(lib)], env=dict(os.environ, LD_PRELOAD=str(trap)), check=True)
    master, slave = pty.openpty()
    proc = None
    try:
        proc = subprocess.Popen(['/bin/bash', '--noprofile', '--norc', '-i'], stdin=slave, stdout=slave, stderr=slave,
            env=dict(os.environ, LD_LIBRARY_PATH=str(lib.parent), LD_PRELOAD=str(trap), TERM='xterm-256color'), start_new_session=True)
        os.write(master, b"printf 'ANDCODE_TINFO_'; printf 'BASH_OK\\n'; exit\n")
        output = bytearray()
        deadline = time.monotonic()+15
        while time.monotonic()<deadline:
            if select.select([master],[],[],.2)[0]:
                output.extend(os.read(master,65536))
            if b'ANDCODE_TINFO_BASH_OK' in output:break
        assert b'ANDCODE_TINFO_BASH_OK' in output, 'Real interactive Bash failed'
        assert proc.wait(timeout=5)==0
        print('ANDCODE_TINFO_BASH_OK')
    finally:
        if proc and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGKILL); proc.wait(timeout=5)
        os.close(slave); os.close(master)
