import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('pty_build', Path(__file__).with_name('build-opencode-native-pty.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BuildInputTest(unittest.TestCase):
    def test_missing_and_changed_original_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with self.assertRaisesRegex(ValueError, 'Expected one'):
                module.installed_input(root)
            target = root / 'node_modules/.bun/bun-pty@0.4.11/node_modules/bun-pty/rust-pty/target/release/librust_pty_arm64.so'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'original'):
                module.installed_input(root)

    def test_non_arm64_linux_host_rejected_before_writes(self):
        with patch.object(module.platform, 'machine', return_value='x86_64'):
            with self.assertRaisesRegex(ValueError, 'native Linux arm64'):
                module.build('missing', 'missing')


if __name__ == '__main__':
    unittest.main()
