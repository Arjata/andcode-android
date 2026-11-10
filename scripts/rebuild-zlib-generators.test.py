"""Host-generator isolation/failure regressions; no compiler is executed."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('zlib_rebuild', Path(__file__).with_name('rebuild-zlib-generators.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    def test_generators_and_fail_closed(self):
        for mode in ['ok', 'missing', 'source-elf', 'compiler', 'preprocess', 'compile', 'link',
                     'timeout', 'dependency-target', 'external-header', 'missing-main', 'object-elf',
                     'generator-elf', 'run', 'drift', 'mutate', 'compiler-mutate']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve(); source = root / 'upstream'; source.mkdir()
                output = root / 'output'; output.mkdir()
                files = {'crc32.c': b'crc source', 'inftrees.c': b'tree source', 'zutil.c': b'utility',
                         'crc32.h': b'generated crc header', 'inffixed.h': b'generated fixed header',
                         'LICENSE': b'zlib license', 'zlib.h': b'zlib header'}
                for name, raw in files.items(): (source / name).write_bytes(raw)
                compiler = root / 'gcc'; compiler.write_bytes(b'compiler')
                system = root / 'usr'; system.mkdir()
                system_header = system / 'stdio.h'; system_header.write_bytes(b'system header')
                outside = root / 'outside.h'; outside.write_bytes(b'outside')
                if mode == 'missing': (source / 'crc32.c').unlink()
                if mode == 'source-elf': (source / 'extra.c').write_bytes(b'\x7fELFbad')
                directory = output / 'zlib-generator-rebuild'
                calls = []

                def run(command, **kwargs):
                    calls.append(command)
                    self.assertNotIn('CPATH', kwargs['env'])
                    work = Path(kwargs['cwd']); stdout = b''
                    if command[-1] == '--version': stdout = b'GCC fixture\n'
                    elif '-E' in command:
                        if mode == 'timeout': raise subprocess.TimeoutExpired(command, 120, stderr=b'partial')
                        if mode == 'preprocess': return subprocess.CompletedProcess(command, 2, b'', b'failed')
                        preprocessed = Path(command[command.index('-o') + 1]); preprocessed.write_bytes(b'actual preprocessed C')
                        dep = Path(command[command.index('-MF') + 1])
                        target = command[command.index('-MT') + 1]
                        if mode == 'dependency-target': target = 'other.o'
                        dependencies = [command[-1], str(directory / 'source/zlib.h'),
                                        str(outside if mode == 'external-header' else system_header)]
                        if mode == 'missing-main': dependencies.pop(0)
                        import shlex
                        dep.write_text(target + ': ' + shlex.join(dependencies) + '\n')
                    elif '-c' in command:
                        self.assertTrue(command[command.index('-c') + 1].endswith('.i'))
                        if mode == 'compile': return subprocess.CompletedProcess(command, 2, b'', b'failed')
                        Path(command[-1]).write_bytes(b'invalid' if mode == 'object-elf' else b'\x7fELF\x02\x01object')
                    elif '-o' in command:
                        if mode == 'link': return subprocess.CompletedProcess(command, 2, b'', b'failed')
                        Path(command[-1]).write_bytes(b'invalid' if mode == 'generator-elf' else b'\x7fELF\x02\x01generator')
                    else:
                        self.assertEqual(command, [str(work / 'generator')])
                        if mode == 'run': return subprocess.CompletedProcess(command, 2, b'', b'failed')
                        if work.name == 'makecrch':
                            (work / 'crc32.h').write_bytes(b'changed' if mode == 'drift' else files['crc32.h'])
                        else:
                            stdout = files['inffixed.h']
                            if mode == 'mutate': (directory / 'source/zlib.h').write_bytes(b'changed')
                            if mode == 'compiler-mutate': compiler.write_bytes(b'changed')
                    return subprocess.CompletedProcess(command, 0, stdout, b'')

                with patch.object(m.shutil, 'which', return_value=None if mode == 'compiler' else str(compiler)), \
                     patch.object(m, 'SYSTEM_ROOT', system), patch.object(m.subprocess, 'run', side_effect=run):
                    if mode == 'ok':
                        result = m.rebuild(source, output, {'CPATH': 'untrusted'})
                        self.assertEqual(len(result['outputs']), 2)
                        self.assertEqual(len(result['systemHeaders']), 1)
                        self.assertEqual(len(result['commands']), 11)
                        self.assertEqual(sum(len(row['units']) for row in result['outputs']), 3)
                        self.assertTrue(all(not result[key] for key in ['redistributionApproved', 'androidApproved',
                                        'relinkingApproved', 'fullCorrespondingSourceApproved']))
                        for name, raw in files.items(): self.assertEqual((source / name).read_bytes(), raw)
                        for row in result['files']:
                            path = output / row['path']
                            self.assertEqual(m.digest(path), row['sha256'])
                            self.assertEqual(path.stat().st_size, row['bytes'])
                        self.assertEqual(json.loads((directory / 'review.json').read_text())['outputs'], result['outputs'])
                        with self.assertRaises(FileExistsError): m.rebuild(source, output, {})
                    else:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired)):
                            m.rebuild(source, output, {})
                        self.assertFalse((directory / 'review.json').exists())
                        if mode == 'timeout':
                            self.assertIn(b'TIMEOUT', (directory / 'makecrch/0000-preprocess.log').read_bytes())


if __name__ == '__main__': unittest.main()
