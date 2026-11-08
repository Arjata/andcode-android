"""Linux-only wrapper argv/environment regression; no Android device needed."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class WrapperTest(unittest.TestCase):
    def test_actual_glibc_bash_child(self):
        loaders = [Path('/lib/ld-linux-aarch64.so.1'), Path('/lib64/ld-linux-x86-64.so.2')]
        loader = next((p for p in loaders if p.exists()), None)
        self.assertIsNotNone(loader, 'Linux glibc runner is required')
        with tempfile.TemporaryDirectory(prefix='andcode-wrapper-') as work:
            root = Path(work)
            (root / 'shim').mkdir()
            source = root / 'fixture.c'
            source.write_text('__attribute__((constructor)) static void loaded(void) {}\n')
            subprocess.run(['cc', '-shared', '-fPIC', str(source), '-o', str(root / 'shim/libandcode-shim.so')], check=True)
            template = (Path(__file__).resolve().parents[1] / 'bundle/wrapper.sh.tpl').read_text()
            values = {'@ROOT@': 'ROOT="' + str(root) + '"', '@EXEDIR@': '/bin', '@LOADER@': str(loader),
                      '@LIBPATH@': '/lib', '@TARGET@': 'bash', '@TIER@': 'p'}
            for key, value in values.items():
                template = template.replace(key, value)
            wrapper = root / 'wrapper'
            wrapper.write_text(template)
            proc = subprocess.run(['/bin/sh', str(wrapper), '--noprofile', '--norc', '-c',
                'test -z "${LD_PRELOAD+x}" && /bin/sh -c \'test -z "${LD_PRELOAD+x}" && echo CHILD_ENV_OK\''],
                env=dict(os.environ, ANDCODE_IN_PROOT='1'), capture_output=True, text=True, check=True, timeout=10)
            self.assertIn('CHILD_ENV_OK', proc.stdout)

    def test_direct_loader_preload_does_not_export_to_children(self):
        template = (Path(__file__).resolve().parents[1] / 'bundle/wrapper.sh.tpl').read_text()
        with tempfile.TemporaryDirectory(prefix='andcode-wrapper-') as work:
            root = Path(work)
            (root / 'shim').mkdir()
            shim = root / 'shim/libandcode-shim.so'
            shim.write_text('fixture only, not ELF')
            loader = root / 'loader'
            loader.write_text('#!/bin/sh\n[ -z "${LD_PRELOAD+x}" ] || exit 90\nprintf "%s\\n" "$@"\n')
            loader.chmod(0o755)
            values = {'@ROOT@': 'ROOT="' + root.as_posix() + '"', '@EXEDIR@': root.as_posix(),
                      '@LOADER@': loader.as_posix(), '@LIBPATH@': root.as_posix(), '@TARGET@': 'target', '@TIER@': 'p'}
            for key, value in values.items():
                template = template.replace(key, value)
            wrapper = root / 'wrapper'
            wrapper.write_text(template)
            args = ['space value', '', 'semi;dollar$']
            for present in [True, False]:
                if not present:
                    shim.unlink()
                env = dict(os.environ, ANDCODE_IN_PROOT='1')
                # The non-existent inherited value is intentionally harmless to
                # /bin/sh, but must not be visible to the loader or its children.
                env['LD_PRELOAD'] = '/andcode-nonexistent-test-preload'
                proc = subprocess.run(['/bin/sh', str(wrapper), *args], env=env,
                                      text=True, capture_output=True, check=True, timeout=10)
                expected = ['--library-path', str(root), '--inhibit-cache']
                if present:
                    expected += ['--preload', str(shim)]
                expected += [str(root / 'target'), *args]
                self.assertEqual(proc.stdout.splitlines(), expected)


if __name__ == '__main__':
    unittest.main()
