"""Exercise fail-closed recipe entry guards on Linux, before any privileged work."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == 'linux', 'Native Linux CI only; no local Bash validation')
class RecipeGuards(unittest.TestCase):
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
