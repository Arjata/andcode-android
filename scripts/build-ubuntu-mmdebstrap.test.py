"""Exercise fail-closed recipe entry guards on Linux, before any privileged work."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == 'linux', 'Native Linux CI only; no local Bash validation')
class RecipeGuards(unittest.TestCase):
    def test_fixed_snapshot_sources_are_explicit_and_no_security_bypass(self):
        recipe = Path(__file__).with_name('build-ubuntu-mmdebstrap.sh').read_text()
        source_config = recipe[recipe.index('SNAPSHOT='):recipe.index('command -v mmdebstrap')]
        sources = recipe[recipe.index('for suite in noble'):recipe.index('# Use root mode')]
        with tempfile.TemporaryDirectory() as tmp:
            key = Path(tmp) / 'ubuntu.gpg'
            script = source_config + '\nKEY="$1"\nOUT="$2"\n' + sources
            result = subprocess.run(['bash', '-euc', script, 'fixture', str(key), tmp],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            mirror = 'https://snapshot.ubuntu.com/ubuntu/20261110T000000Z/'
            expected = ''.join(f'deb [arch=arm64 signed-by={key}] {mirror} {suite} main universe\n'
                               f'deb-src [signed-by={key}] {mirror} {suite} main universe\n'
                               for suite in ['noble', 'noble-updates', 'noble-security'])
            self.assertEqual((Path(tmp) / 'ubuntu-sources.list').read_text(), expected)
        for bypass in ['Check-Valid-Until', 'check-valid-until=no', 'trusted=yes',
                       'AllowUnauthenticated', 'Verify-Peer=false']:
            self.assertNotIn(bypass, recipe)

    def test_cleanup_mount_inspection_fails_closed(self):
        recipe = Path(__file__).with_name('build-ubuntu-mmdebstrap.sh').read_text()
        cleanup = recipe[recipe.index('cleanup() {'):recipe.index('trap cleanup EXIT')]
        # The sudo stand-in records deletion requests; no privileged tool runs.
        for mode, expected, deletes in [('empty', 0, True), ('mount', 1, False),
                                         ('exact', 1, False), ('error', 1, False),
                                         ('prefix', 0, True), ('original-error', 7, True)]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                marker = Path(tmp) / 'deleted'
                script = '''
WORK=/allocated/work
sudo() {
  case "$1" in
    findmnt)
      case "$MODE" in
        mount) printf '/allocated/work/proc\\n' ;;
        exact) printf '/allocated/work\\n' ;;
        error) return 1 ;;
        prefix) printf '/allocated/work-other/proc\\n' ;;
      esac ;;
    rm) printf 'requested' > "$MARKER" ;;
    *) return 99 ;;
  esac
}
''' + cleanup + '\n(exit "$INITIAL"); cleanup\n'
                env = dict(os.environ, MODE=mode, MARKER=str(marker),
                           INITIAL='7' if mode == 'original-error' else '0')
                result = subprocess.run(['bash', '-c', script], env=env,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(marker.exists(), deletes)

    def run_recipe(self, *arguments, architecture='aarch64'):
        with tempfile.TemporaryDirectory() as tmp:
            uname = Path(tmp) / 'uname'
            uname.write_text('#!/bin/sh\nprintf "%s\\n" "' + architecture + '"\n')
            uname.chmod(0o755)
            environment = dict(os.environ, PATH=tmp + os.pathsep + os.environ['PATH'])
            return subprocess.run(['bash', str(Path(__file__).with_name('build-ubuntu-mmdebstrap.sh')),
                                   *map(str, arguments)], env=environment,
                                  capture_output=True, text=True, timeout=10)

    def test_requires_one_argument(self):
        for args in [(), ('one', 'two')]:
            result = self.run_recipe(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('usage:', result.stderr)

    def test_rejects_non_native_architecture_without_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'new'
            result = self.run_recipe(output, architecture='x86_64')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('arm64 runner required', result.stderr)
            self.assertFalse(output.exists())

    def test_preserves_existing_directory_and_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'keep'
            marker.write_bytes(b'preserve')
            for output in [Path(tmp), marker]:
                result = self.run_recipe(output)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('output must be new', result.stderr)
                self.assertEqual(marker.read_bytes(), b'preserve')

    def test_preserves_dangling_output_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'link'
            output.symlink_to(Path(tmp) / 'absent')
            result = self.run_recipe(output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('output must be new', result.stderr)
            self.assertTrue(output.is_symlink())


if __name__ == '__main__':
    unittest.main()
