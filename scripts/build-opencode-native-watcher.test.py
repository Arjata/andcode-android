import importlib.util
import io
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('watcher_build', Path(__file__).with_name('build-opencode-native-watcher.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WatcherBuildTest(unittest.TestCase):
    def test_non_arm64_linux_host_rejected(self):
        with patch.object(module.platform, 'machine', return_value='x86_64'):
            with self.assertRaisesRegex(ValueError, 'native Linux arm64'):
                module.build('missing', 'missing')

    def test_source_list_and_fixed_headers(self):
        self.assertEqual(len(module.SOURCES), 11)
        self.assertEqual(len(set(module.SOURCES)), len(module.SOURCES))
        self.assertTrue(all(p.startswith('src/') and '..' not in p for p in module.SOURCES))
        self.assertEqual(len(module.HEADERS), 2)
        for url, checksum in module.HEADERS.values():
            self.assertTrue(url.startswith('https://'))
            self.assertRegex(checksum, '^[0-9a-f]{64}$')

    def test_only_checked_elf_and_successful_event_replace_input(self):
        for failure in [None, 'elf', 'event']:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                upstream, stage = root / 'upstream', root / 'stage'
                stage.mkdir()
                target = upstream / 'node_modules/.bun/@parcel+watcher-linux-arm64-glibc@2.5.1/node_modules/@parcel/watcher-linux-arm64-glibc/watcher.node'
                target.parent.mkdir(parents=True)
                target.write_bytes(b'original')
                roots = [root / name for name in ['watcher', 'addon', 'node']]
                for folder in roots:
                    folder.mkdir()
                (roots[0] / 'binding.gyp').write_text('\n'.join('"' + name + '"' for name in module.SOURCES))
                for name in module.SOURCES:
                    path = roots[0] / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b'source fixture')
                header = roots[1] / 'napi.h'
                header.write_bytes(b'// Copyright fixture\n// MIT License fixture')

                def run(command, **kwargs):
                    if command[0] == 'c++':
                        self.assertIn('-DNAPI_VERSION=4', command)
                        self.assertIn('-H', command)
                        kwargs['stdout'].write('. ' + str(header) + '\n')
                        kwargs['stdout'].flush()
                        Path(command[-1]).write_bytes(b'checked watcher fixture')
                        return subprocess.CompletedProcess(command, 0)
                    if failure == 'event':
                        raise subprocess.CalledProcessError(1, command, output='', stderr='event failed')
                    probe = Path(command[1]).read_text()
                    self.assertIn('watcher.unsubscribe(dir,callback,options)', probe)
                    return subprocess.CompletedProcess(command, 0, stdout='ANDCODE_SOURCE_WATCHER_EVENT_OK', stderr='')

                gate = {'side_effect': ValueError('bad ELF')} if failure == 'elf' else {'return_value': ({}, ['libc.so.6'])}
                with patch.object(module.sys, 'platform', 'linux'), \
                     patch.object(module.platform, 'machine', return_value='aarch64'), \
                     patch.object(module, 'ORIGINAL', hashlib.sha256(b'original').hexdigest()), \
                     patch.object(module.urllib.request, 'urlopen', side_effect=[io.BytesIO(b'archive') for _ in range(3)]), \
                     patch.object(module.pty.rust.sources, 'inspect_archive', return_value={}), \
                     patch.object(module.pty.rust, 'unpack_candidate', side_effect=roots), \
                     patch.object(module.subprocess, 'run', side_effect=run), \
                     patch.object(module.subprocess, 'check_output', side_effect=['0: 0 0 FUNC GLOBAL DEFAULT 1 napi_register_module_v1', 'c++ fixture']), \
                     patch.object(module.pty.audit, 'elf', **gate):
                    if failure:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                            module.build(upstream, stage)
                        self.assertEqual(target.read_bytes(), b'original')
                        self.assertFalse((stage / 'native-watcher-build-review.json').exists())
                    else:
                        module.build(upstream, stage)
                        report = json.loads((stage / 'native-watcher-build-review.json').read_text())
                        self.assertEqual(report['rebuiltSha256'], hashlib.sha256(target.read_bytes()).hexdigest())
                        for key in ['redistributionApproved', 'androidApproved', 'originalNpmBinaryCorrespondenceProven']:
                            self.assertIs(report[key], False)

    def test_compiler_include_index_requires_real_inputs_and_preserves_clues(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source, header = root / 'source.cc', root / 'header.h'
            source.write_bytes(b'#include "header.h"')
            header.write_bytes(b'// Copyright holder\n// SPDX-License-Identifier: MIT\n')
            with self.assertRaisesRegex(ValueError, 'included headers'):
                module.compiler_inputs('', [source], {})
            with self.assertRaises(FileNotFoundError):
                module.compiler_inputs('. ' + str(root / 'missing.h'), [source], {})
            result = module.compiler_inputs('. ' + str(header) + '\n.. ' + str(header), [source], {'fixed': root})
            self.assertIs(result['redistributionApproved'], False)
            self.assertEqual(len(result['files']), 2)
            item = next(row for row in result['files'] if row['path'] == 'header.h')
            self.assertEqual(item['origin'], 'fixed')
            self.assertEqual(len(item['declarationClues']), 2)


if __name__ == '__main__':
    unittest.main()
