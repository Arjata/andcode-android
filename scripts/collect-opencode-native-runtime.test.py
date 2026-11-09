import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('native_runtime', Path(__file__).with_name('collect-opencode-native-runtime.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RuntimeClosureTest(unittest.TestCase):
    def test_version_parser(self):
        text = '''Version definition section '.gnu.version_d' contains 2 entries:
  0x001c: Rev: 1 Flags: none Index: 2 Cnt: 1 Name: GLIBCXX_3.4.30
Version needs section '.gnu.version_r' contains 1 entry:
  000000: Version: 1 File: libc.so.6 Cnt: 1
  0x0010: Name: GLIBC_2.39 Flags: none Version: 3
'''
        with patch.object(module.subprocess, 'check_output', return_value=text):
            self.assertEqual(module.versions(Path('fixture')), ({'GLIBCXX_3.4.30'}, {'libc.so.6': {'GLIBC_2.39'}}))

    def test_missing_provider_and_version_rejected(self):
        obj, lib = Path('app'), Path('libc.so.6')
        for provider, need in [('libmissing.so', 'V1'), ('libc.so.6', 'GLIBC_2.40')]:
            with self.subTest(provider=provider), \
                 patch.object(Path, 'read_bytes', return_value=b'fixture'), \
                 patch.object(module.elf_module, 'elf', return_value=({}, [provider])), \
                 patch.object(module, 'versions', side_effect=lambda p: ({'GLIBC_2.39'}, {}) if p == lib else (set(), {provider: {need}})):
                with self.assertRaises(ValueError):
                    module.verify_closure([obj], [lib])

    def test_closed_dependencies(self):
        lib = Path('libc.so.6')
        with patch.object(Path, 'read_bytes', return_value=b'fixture'), \
             patch.object(module.elf_module, 'elf', return_value=({}, ['libc.so.6'])), \
             patch.object(module, 'versions', return_value=({'GLIBC_2.39'}, {'libc.so.6': {'GLIBC_2.39'}})):
            self.assertEqual(module.verify_closure([Path('app')], [lib])[0]['needed'], ['libc.so.6'])


if __name__ == '__main__':
    unittest.main()
