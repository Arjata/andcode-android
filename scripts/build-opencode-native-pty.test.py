import importlib.util
import hashlib
import io
import json
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

    def test_checked_build_records_bytes_without_approving_distribution(self):
        for reject in [False, True]:
            with self.subTest(reject=reject), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                upstream, stage = root / 'upstream', root / 'stage'
                upstream.mkdir()
                stage.mkdir()
                target = upstream / 'original.so'
                target.write_bytes(b'original')
                source = stage / 'native-pty-build/source/repo'

                def unpack(*args):
                    (source / 'rust-pty').mkdir(parents=True)
                    (source / 'rust-pty/Cargo.lock').write_bytes(b'pinned lock')
                    return source

                def command(args, **kwargs):
                    self.assertIn('--locked', args)
                    if args[1] == 'build':
                        self.assertIn('--offline', args)
                        output = Path(kwargs['env']['CARGO_TARGET_DIR']) / module.rust.TARGET / 'release/librust_pty.so'
                        output.parent.mkdir(parents=True)
                        output.write_bytes(b'checked ELF fixture')

                symbols = '\n'.join('0: 0 0 FUNC GLOBAL DEFAULT 1 bun_pty_' + name for name in
                                    ['spawn', 'write', 'read', 'resize', 'kill', 'get_pid', 'get_exit_code', 'close'])
                gate = {'side_effect': ValueError('bad ELF')} if reject else {'return_value': ({}, ['libc.so.6'])}
                with patch.object(module.sys, 'platform', 'linux'), \
                     patch.object(module.platform, 'machine', return_value='aarch64'), \
                     patch.object(module, 'installed_input', return_value=target), \
                     patch.object(module.urllib.request, 'urlopen', return_value=io.BytesIO(b'archive fixture')), \
                     patch.object(module.rust.sources, 'inspect_archive'), \
                     patch.object(module.rust, 'unpack_candidate', side_effect=unpack), \
                     patch.object(module.subprocess, 'run', side_effect=command), \
                     patch.object(module.subprocess, 'check_output', side_effect=[symbols, 'cargo fixture', 'rustc fixture', 'cc fixture']), \
                     patch.object(module.audit, 'elf', **gate):
                    if reject:
                        with self.assertRaisesRegex(ValueError, 'bad ELF'):
                            module.build(upstream, stage)
                        self.assertEqual(target.read_bytes(), b'original')
                        continue
                    module.build(upstream, stage)
                report = json.loads((stage / 'native-pty-build-review.json').read_text())
                self.assertEqual(target.read_bytes(), b'checked ELF fixture')
                self.assertEqual(report['rebuiltSha256'], hashlib.sha256(target.read_bytes()).hexdigest())
                for key in ['redistributionApproved', 'androidApproved', 'originalNpmBinaryCorrespondenceProven']:
                    self.assertIs(report[key], False)


if __name__ == '__main__':
    unittest.main()
