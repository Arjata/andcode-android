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
        for failure in [None, 'lock', 'cargo', 'sort-patch', 'sort-test']:
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
                      patch.object(module, 'replace_glidesort', return_value={'files': []},
                                   side_effect=ValueError('sort patch failed') if failure == 'sort-patch' else None), \
                      patch.object(module, 'probe_sort_adapter', return_value={'tests': 3},
                                   side_effect=ValueError('sort tests failed') if failure == 'sort-test' else None), \
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

    def test_sort_replacement_rejects_source_drift_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in module.SORT_INPUTS:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'changed source')
            with self.assertRaisesRegex(ValueError, 'Unexpected fff sort adapter source'):
                module.replace_glidesort(root)
            self.assertTrue(all((root / name).read_bytes() == b'changed source' for name in module.SORT_INPUTS))

    def test_sort_replacement_removes_only_fixed_dependency_and_records_bytes(self):
        fixture = {
            'Cargo.toml': b'[workspace.dependencies]\nglidesort = "0.1"\nother = "1"\n',
            'crates/fff-core/Cargo.toml': b'[dependencies]\nglidesort = { workspace = true }\n',
            'crates/fff-core/src/sort_buffer.rs': b'fixture upstream adapter',
            'Cargo.lock': (b'[[package]]\nname = "fff-core"\nversion = "1"\ndependencies = [\n "glidesort",\n]\n\n'
                           b'[[package]]\nname = "glidesort"\nversion = "0.1.2"\n'
                           b'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
                           b'checksum = "f2e102e6eb644d3e0b186fc161e4460417880a0a0b87d235f2e5b8fb30f2e9e0"\n\n'),
        }
        for mode in ['ok', 'manifest-shape', 'lock-shape', 'remaining-edge']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                data = dict(fixture)
                if mode == 'manifest-shape':data['Cargo.toml'] += b'glidesort = "0.1"\n'
                if mode == 'lock-shape':data['Cargo.lock'] = data['Cargo.lock'].replace(b'0.1.2', b'0.1.3')
                if mode == 'remaining-edge':data['Cargo.lock'] += b'[[package]]\nname = "other"\nversion = "1"\ndependencies = ["glidesort 0.1.2"]\n'
                for name, payload in data.items():
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(payload)
                pins = {name: hashlib.sha256(payload).hexdigest() for name, payload in data.items()}
                with patch.object(module, 'SORT_INPUTS', pins):
                    if mode != 'ok':
                        with self.assertRaises(ValueError):module.replace_glidesort(root)
                        self.assertTrue(all((root / name).read_bytes() == payload for name, payload in data.items()))
                    else:
                        report = module.replace_glidesort(root)
                        self.assertEqual(len(report['files']), 4)
                        self.assertNotIn('glidesort', (root / 'Cargo.lock').read_text())
                        self.assertEqual((root / 'crates/fff-core/src/sort_buffer.rs').read_bytes(), module.SORT_ADAPTER.encode())
                        for row in report['files']:
                            self.assertEqual(row['originalSha256'], pins[row['path']])
                            self.assertEqual(row['modifiedSha256'], hashlib.sha256((root / row['path']).read_bytes()).hexdigest())

    def test_sort_probe_fails_closed(self):
        for mode in ['ok', 'compile', 'run', 'marker']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                calls = []
                def run(command, **kwargs):
                    calls.append(command)
                    self.assertEqual(kwargs['env'], {'fixture': 'clean'})
                    self.assertEqual(kwargs['timeout'], 60)
                    if len(calls) == 1:
                        self.assertEqual(command[:3], ['rustc', '--edition=2021', '--test'])
                        (root / 'sort-test').write_bytes(b'tests')
                    failed = (mode == 'compile' and len(calls) == 1) or (mode == 'run' and len(calls) == 2)
                    return subprocess.CompletedProcess(command, 1 if failed else 0,
                                                       '' if mode == 'marker' else '3 passed; 0 failed', '')
                with patch.object(module.subprocess, 'run', side_effect=run):
                    if mode == 'ok':
                        report = module.probe_sort_adapter(root, root, {'fixture': 'clean'})
                        self.assertEqual(report['tests'], 3)
                    else:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                            module.probe_sort_adapter(root, root, {'fixture': 'clean'})


if __name__ == '__main__':
    unittest.main()
