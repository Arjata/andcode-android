import importlib.util
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('fff_build', Path(__file__).with_name('build-opencode-native-fff.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FffBuildTest(unittest.TestCase):
    def test_wrong_host_rejected(self):
        with patch.object(module.platform, 'machine', return_value='x86_64'):
            with self.assertRaisesRegex(ValueError, 'native Linux arm64'):
                module.build('missing', 'missing')

    def test_pinned_features_and_probe_cleanup(self):
        self.assertEqual(module.FLAGS, ['-p', 'fff-c', '--no-default-features', '--features', 'zlob'])
        self.assertIn('fff_free_search_result(found)', module.PROBE)
        self.assertIn('fff_destroy(handle)', module.PROBE)
        self.assertIn('lib.close()', module.PROBE)
        self.assertIn('libgcc_s.so.1', module.PROBE)

    def test_map_hashes_available_inputs_and_discloses_temporaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'libfixture.a'
            p.write_bytes(b'archive')
            text = 'LOAD ' + str(p) + '\nLOAD ' + str(p) + '\nLOAD ' + str(Path(tmp) / 'removed.o')
            rows = module.link_inputs(text)
            self.assertEqual(len(rows), 2)
            self.assertEqual(sum(r['availableAfterLink'] for r in rows), 1)
            self.assertEqual(sum('sha256' in r for r in rows), 1)
            with self.assertRaisesRegex(ValueError, 'lacks LOAD'):
                module.link_inputs('not a GNU map')

    def test_failure_never_replaces_input(self):
        for failure in [None, 'elf', 'needed', 'exports', 'probe', 'timeout', 'marker']:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result, target = root / 'rebuilt.so', root / 'installed.so'
                result.write_bytes(b'rebuilt'); target.write_bytes(b'original')
                exports = '\n'.join('1: 0 1 FUNC GLOBAL DEFAULT 1 ' + name
                                    for name in re.findall(r'^(fff_\w+):', module.PROBE, re.M))
                if failure == 'exports':
                    exports = ''
                gate = {'side_effect': ValueError('bad ELF')} if failure == 'elf' else {
                    'return_value': ({}, ['libunknown.so'] if failure == 'needed' else ['libc.so.6'])}
                probe = {'return_value': subprocess.CompletedProcess([], 0,
                         stdout='' if failure == 'marker' else module.MARKER, stderr='')}
                if failure == 'probe':
                    probe = {'side_effect': subprocess.CalledProcessError(1, [], output='failed', stderr='')}
                if failure == 'timeout':
                    probe = {'side_effect': subprocess.TimeoutExpired([], 40)}
                with patch.object(module.pty.audit, 'elf', **gate), \
                     patch.object(module.subprocess, 'check_output', return_value=exports), \
                     patch.object(module.subprocess, 'run', **probe):
                    if failure:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired)):
                            module.validate_and_probe(result, target, root, {})
                        self.assertEqual(target.read_bytes(), b'original')
                    else:
                        module.validate_and_probe(result, target, root, {})
                        self.assertEqual(target.read_bytes(), b'rebuilt')


if __name__ == '__main__':
    unittest.main()
