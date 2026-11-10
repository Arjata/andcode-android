"""Synthetic source-rule relink coverage; no linker or target code is executed."""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('source_relink', Path(__file__).with_name('relink-modified-media.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    def test_relink_and_fail_closed(self):
        modes = ['ok', 'discarded-media', 'approval', 'source-drift', 'duplicate', 'set-gap', 'retained-drift',
                 'argument', 'link', 'timeout', 'map', 'extraction', 'needed', 'abi',
                 'crc-shape', 'crc', 'mutation', 'baseline-mutation', 'library-mutation',
                 'probe-mutation', 'unchanged-library']
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve(); output = root / 'build'; output.mkdir()
                (output / 'libopentui.so').write_bytes(b'baseline library')
                directory = output / 'modified-media-source-relink'
                zig = root / 'tools/zig/zig'; zig.parent.mkdir(parents=True); zig.write_bytes(b'zig')
                archive = zig.parent.parent / 'zig.tar.xz'; archive.write_bytes(b'fixed zig archive')
                source_prefix = 'modified-media-source-rebuild/native/.cache/ffmpeg/prefix/aarch64-linux/'
                obj = output / source_prefix / 'objects/libavutil/crc.o'
                obj.parent.mkdir(parents=True); obj.write_bytes(b'fresh CRC')
                source = {'files': [{'path': obj.relative_to(output).as_posix(), 'bytes': obj.stat().st_size,
                                    'sha256': m.digest(obj)}],
                          'compileCommands': {'objects': [{'object': 'objects/libavutil/crc.o', 'objectSha256': m.digest(obj)}]},
                          **{k: False for k in ['redistributionApproved', 'androidApproved', 'relinkingApproved', 'fullCorrespondingSourceApproved']}}
                if mode == 'approval': source['androidApproved'] = True
                if mode == 'duplicate': source['compileCommands']['objects'] *= 2
                if mode == 'source-drift': obj.write_bytes(b'changed')
                source_review = output / 'modified-media-source-rebuild/review.json'
                source_review.write_text(json.dumps(source))
                retained = output / 'link-inputs/0000.o'; retained.parent.mkdir(); retained.write_bytes(b'baseline')
                other = output / 'link-inputs/0001.o'; other.write_bytes(b'nonmedia')
                inputs = [{'path': '/baseline/crc.o', 'retainedPath': retained.relative_to(output).as_posix(),
                           'scope': 'opentui-source-build', 'scopeRelativePath': '.cache/ffmpeg/prefix/aarch64-linux/objects/libavutil/crc.o',
                           'argumentIndex': 1, 'bytes': retained.stat().st_size, 'sha256': m.digest(retained)},
                          {'path': '/baseline/other.o', 'retainedPath': other.relative_to(output).as_posix(),
                           'scope': 'other', 'scopeRelativePath': 'other.o',
                           'argumentIndex': 2, 'bytes': other.stat().st_size, 'sha256': m.digest(other)}]
                if mode == 'set-gap': inputs[0]['scope'] = 'other'
                if mode == 'retained-drift': other.write_bytes(b'changed')
                if mode == 'argument': inputs[0]['path'] = '/wrong'
                if mode == 'discarded-media':
                    unused = obj.parent / 'unused.o'; unused.write_bytes(b'fresh unused media')
                    source['files'].append({'path': unused.relative_to(output).as_posix(),
                        'bytes': unused.stat().st_size, 'sha256': m.digest(unused)})
                    source['compileCommands']['objects'].append({'object': 'objects/libavutil/unused.o',
                        'objectSha256': m.digest(unused)})
                    source_review.write_text(json.dumps(source))
                    inputs[1]['scope'] = 'opentui-source-build'
                    inputs[1]['scopeRelativePath'] = '.cache/ffmpeg/prefix/aarch64-linux/objects/libavutil/unused.o'
                prior = output / 'modified-crc-relink'; prior.mkdir()
                (prior / 'crc-probe.c').write_bytes(b'probe source')
                (output / 'probe.mjs').write_bytes(b'ABI source')
                baseline = {'finalLink': {'command': ['ld.lld', '/baseline/crc.o', '/baseline/other.o', '-o', '/baseline/lib.so'],
                                          'inputs': inputs}, 'needed': ['libc.so.6'],
                            'modifiedCrcRelink': {'probeCommands': [['cc', str(prior / 'crc-probe.c'),
                                str(prior / 'libopentui.so'), '-Wl,-rpath,' + str(prior), '-o', str(prior / 'crc-probe')],
                                [str(prior / 'crc-probe')]]}}
                if mode == 'crc-shape': baseline['modifiedCrcRelink']['probeCommands'][1] = ['unexpected']
                (output.parent / 'native-opentui-build-review.json').write_text(json.dumps(baseline))
                calls = []

                def run(command, **kwargs):
                    calls.append(command); stdout = b''
                    if command[0] == str(zig):
                        self.assertEqual(command[2:4], [str(obj), str(unused if mode == 'discarded-media' else other)])
                        if mode == 'link': raise subprocess.CalledProcessError(1, command)
                        if mode == 'timeout': raise subprocess.TimeoutExpired(command, 120, stderr=b'partial')
                        (directory / 'libopentui.so').write_bytes(b'baseline library' if mode == 'unchanged-library' else b'relinked library')
                        (directory / 'link.map').write_text('missing' if mode == 'map' else str(obj))
                        (directory / 'archive-extraction.tsv').write_bytes(b'bad' if mode == 'extraction' else b'reference\textracted\tsymbol\n')
                    elif command[0] == 'bun':
                        stdout = b'missing' if mode == 'abi' else m.media.MARKER.encode()
                    elif command[0] == 'cc':
                        self.assertIn(str(directory / 'libopentui.so'), command)
                        self.assertNotIn(str(prior / 'libopentui.so'), command)
                        (directory / 'crc-probe').write_bytes(b'CRC executable')
                    else:
                        self.assertEqual(command, [str(directory / 'crc-probe')])
                        stdout = b'bad' if mode == 'crc' else (b'ANDCODE_SOURCE_FFMPEG_CRC_OK 2304 cases (Linux only)\n'
                            b'ANDCODE_MODIFIED_CRC_RELINK_OK 6912 calls (Linux only)\n')
                        if mode == 'mutation': other.write_bytes(b'changed')
                        if mode == 'baseline-mutation': (output / 'libopentui.so').write_bytes(b'changed')
                        if mode == 'library-mutation': (directory / 'libopentui.so').write_bytes(b'changed')
                        if mode == 'probe-mutation': (directory / 'crc-probe').write_bytes(b'changed')
                    return subprocess.CompletedProcess(command, 0, stdout, b'')

                with ExitStack() as stack:
                    stack.enter_context(patch.object(m.shutil, 'which', return_value=str(zig)))
                    stack.enter_context(patch.object(m.media, 'ZIG_SHA256', m.digest(archive)))
                    stack.enter_context(patch.object(m.media.pty.audit, 'elf', return_value=({}, ['unexpected' if mode == 'needed' else 'libc.so.6'])))
                    stack.enter_context(patch.object(m.subprocess, 'run', side_effect=run))
                    if mode in ['ok', 'discarded-media']:
                        result = m.relink(output, {})
                        self.assertEqual(result['replacedObjects'], 2 if mode == 'discarded-media' else 1)
                        self.assertEqual(len(result['commands']), 4)
                        self.assertEqual(result['modifiedCalls'], 6912)
                        for row in result['files']: self.assertEqual(m.digest(output / row['path']), row['sha256'])
                        self.assertFalse(result['relinkingApproved'])
                        with self.assertRaises(FileExistsError): m.relink(output, {})
                    else:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired)):
                            m.relink(output, {})
                        self.assertFalse((directory / 'review.json').exists())
                        if mode == 'timeout': self.assertIn(b'TIMEOUT', (directory / 'link.log').read_bytes())


if __name__ == '__main__': unittest.main()
