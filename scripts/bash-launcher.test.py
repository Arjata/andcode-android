"""Linux glibc CI: exec the static-entry logic through a script-free boundary."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class BashLauncherTest(unittest.TestCase):
    def test_actual_loader_argv_and_child_environment(self):
        loader = next((p for p in [Path('/lib/ld-linux-aarch64.so.1'), Path('/lib64/ld-linux-x86-64.so.2')] if p.exists()), None)
        self.assertIsNotNone(loader)
        with tempfile.TemporaryDirectory(prefix='andcode-bash-entry-') as work:
            root = Path(work)
            entry = root / 'libandcode-cmd-bash.so'
            source = Path(__file__).resolve().parents[1] / 'bundle/launcher/bash-launcher.c'
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(entry)], check=True)
            (root / 'libandcode-ld-linux.so').symlink_to(loader)
            (root / 'libandcode-bash.so').symlink_to('/bin/bash')
            shim = root / 'fixture.c'
            shim.write_text('__attribute__((constructor)) static void loaded(void) {}\n')
            subprocess.run(['cc', '-shared', '-fPIC', str(shim), '-o', str(root / 'libandcode-shim.so')], check=True)
            env = dict(os.environ, ANDCODE_ROOT=str(root))
            code = 'test -z "${LD_PRELOAD+x}" && test "$ANDCODE_ETC_DIR" = "$ANDCODE_ROOT/etc" && printf "%s\\n" "$@" && /bin/sh -c \'test -z "${LD_PRELOAD+x}" && echo CHILD_OK\''
            args = ['space value', '', 'literal;$value', '--flag']
            p = subprocess.run([str(entry), '--noprofile', '--norc', '-c', code, 'test', *args], env=env, text=True, capture_output=True, check=True)
            self.assertEqual(p.stdout.splitlines(), args + ['CHILD_OK'])
            for value in ['', 'relative']:
                p = subprocess.run([str(entry), '-c', 'exit 0'], env=dict(env, ANDCODE_ROOT=value), capture_output=True)
                self.assertEqual(p.returncode, 127)


if __name__ == '__main__':
    unittest.main()
