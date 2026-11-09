import importlib.util
import hashlib
import json
import os
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

    def test_synthetic_linker_stubs_are_not_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'libfixture.a').write_bytes(b'archive')
            (root / 'linker stubs').write_bytes(b'unrelated')
            rows = module.link_inputs('LOAD libfixture.a\nLOAD linker stubs\nLOAD linker stubs', root)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['path'], str((root / 'libfixture.a').resolve()))
            self.assertEqual(rows[1]['kind'], 'linker-generated')
            self.assertEqual(rows[1]['name'], 'linker stubs')
            self.assertNotIn('path', rows[1])
            self.assertNotIn('sha256', rows[1])
            with self.assertRaisesRegex(ValueError, 'lacks LOAD'):
                module.link_inputs('LOAD linker stubs', root)

    def test_failure_never_replaces_input(self):
        for failure in [None, 'elf', 'needed', 'runner-zlib', 'exports', 'probe', 'timeout', 'marker']:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result, target = root / 'rebuilt.so', root / 'installed.so'
                result.write_bytes(b'rebuilt'); target.write_bytes(b'original')
                exports = '\n'.join('1: 0 1 FUNC GLOBAL DEFAULT 1 ' + name
                                    for name in re.findall(r'^(fff_\w+):', module.PROBE, re.M))
                if failure == 'exports':
                    exports = ''
                needed = ['libc.so.6']
                if failure == 'needed':
                    needed.append('libunknown.so')
                if failure == 'runner-zlib':
                    needed.append('libz.so.1')
                gate = {'side_effect': ValueError('bad ELF')} if failure == 'elf' else {
                    'return_value': ({}, needed)}
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

    def test_locked_build_records_inputs_and_rejects_lock_mutation(self):
        for failure in [None, 'lock', 'cargo']:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                upstream, stage, source = root / 'upstream', root / 'stage', root / 'source'
                stage.mkdir(); source.mkdir()
                target = upstream / 'node_modules/.bun/@ff-labs+fff-bin-linux-arm64-gnu@0.10.5/node_modules/@ff-labs/fff-bin-linux-arm64-gnu/libfff_c.so'
                target.parent.mkdir(parents=True); target.write_bytes(b'original')
                zig = root / 'zig/tool/zig'
                zig.parent.mkdir(parents=True); zig.write_bytes(b'tool')
                (zig.parent.parent / 'zig.tar.xz').write_bytes(b'tool archive')
                lock = source / 'Cargo.lock'
                lock.write_text('[[package]]\nname="fff-c"\nversion="0.10.5"\n')
                (source / 'Cargo.toml').write_text('manifest fixture')

                def run(command, **kwargs):
                    self.assertEqual(kwargs['env']['LIBZ_SYS_STATIC'], '1')
                    self.assertEqual(kwargs['env']['LIBGIT2_NO_VENDOR'], '0')
                    self.assertIn('--locked', command)
                    if failure == 'cargo':
                        raise subprocess.CalledProcessError(1, command)
                    if failure == 'lock':
                        lock.write_text('changed')
                    if command[1] == 'tree':
                        kwargs['stdout'].write('fff-c v0.10.5|MIT|zlob\n')
                    if command[1] == 'rustc':
                        self.assertIn('--offline', command)
                        self.assertEqual(command[command.index('-p'):command.index('-p')+5], module.FLAGS)
                        result = root / 'native-fff-build/target' / module.pty.rust.TARGET / 'release/libfff_c.so'
                        result.parent.mkdir(parents=True); result.write_bytes(b'rebuilt')
                        (stage / 'native-fff-build/link.map').write_text('LOAD ' + str(result))
                    return subprocess.CompletedProcess(command, 0)

                def validate(result, target, output, env):
                    target.write_bytes(result.read_bytes())
                    return ['libc.so.6']

                with patch.object(module.sys, 'platform', 'linux'), \
                     patch.object(module.platform, 'machine', return_value='aarch64'), \
                     patch.object(module, 'ORIGINAL', hashlib.sha256(b'original').hexdigest()), \
                     patch.object(module, 'ZIG_SHA256', hashlib.sha256(b'tool archive').hexdigest()), \
                     patch.object(module.shutil, 'which', return_value=str(zig)), \
                     patch.object(module.pty.rust.sources, 'download_archive', return_value=b'source archive'), \
                     patch.object(module.pty.rust.sources, 'inspect_archive', return_value={}), \
                     patch.object(module.pty.rust, 'unpack_candidate', return_value=source), \
                     patch.object(module.subprocess, 'run', side_effect=run), \
                     patch.object(module.subprocess, 'check_output', side_effect=['0.16.0', 'rustc fixture', 'cc fixture']), \
                     patch.object(module, 'validate_and_probe', side_effect=validate) as probe:
                    if failure:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                            module.build(upstream, stage)
                        self.assertEqual(target.read_bytes(), b'original')
                        self.assertFalse((stage / 'native-fff-build-review.json').exists())
                        probe.assert_not_called()
                    else:
                        module.build(upstream, stage)
                        report = json.loads((stage / 'native-fff-build-review.json').read_text())
                        self.assertEqual(report['rebuiltSha256'], hashlib.sha256(b'rebuilt').hexdigest())
                        for key in ['redistributionApproved', 'androidApproved', 'originalNpmBinaryCorrespondenceProven']:
                            self.assertIs(report[key], False)
                        self.assertEqual(len(report['linkerLoadInputs']), 1)


if __name__ == '__main__':
    unittest.main()
