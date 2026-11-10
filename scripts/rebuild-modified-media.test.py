"""Fresh modified-source staging and fail-closed regressions; no tools execute."""
from contextlib import ExitStack
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('modified_media', Path(__file__).with_name('rebuild-modified-media.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    def test_fresh_source_rules_and_rejections(self):
        modes = ['ok', 'archive', 'source-drift', 'duplicate-archive', 'source-link',
                 'build-fail', 'timeout', 'object-set', 'duplicate-object', 'empty-objects',
                 'dependency-gap', 'crc-source', 'crc-unchanged', 'object-elf',
                 'object-machine', 'object-type', 'object-version', 'source-mutation', 'baseline-mutation',
                 'escape-output']
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve(); native = root / 'original'; output = root / 'output'
                output.mkdir(); cache = native / '.cache/ffmpeg'
                (native / 'scripts').mkdir(parents=True)
                (native / 'scripts/build-ffmpeg.ts').write_bytes(b'fixed script')
                (cache / 'downloads').mkdir(parents=True)
                archives = {}
                for name, files in [('ffmpeg-9.0.2', {'libavutil/crc.c': b'original CRC', 'configure': b'configure script'}),
                                    ('zlib-1.3.2', {'LICENSE': b'zlib grant'})]:
                    data = io.BytesIO()
                    with tarfile.open(fileobj=data, mode='w:gz') as tar:
                        for relative, raw in files.items():
                            info = tarfile.TarInfo(name + '/' + relative); info.size = len(raw)
                            tar.addfile(info, io.BytesIO(raw))
                            if mode == 'duplicate-archive' and name.startswith('ffmpeg'):
                                tar.addfile(info, io.BytesIO(raw))
                            path = cache / 'sources' / name / relative
                            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
                            if relative == 'configure': path.chmod(0o755)
                    filename = name + '.tar.gz'; raw = data.getvalue()
                    (cache / 'downloads' / filename).write_bytes(raw)
                    archives[filename] = ('unused', hashlib.sha256(raw).hexdigest())
                if mode == 'archive': (cache / 'downloads/ffmpeg-9.0.2.tar.gz').write_bytes(b'drift')
                crc_source = cache / 'sources/ffmpeg-9.0.2/libavutil/crc.c'
                if mode == 'source-drift': crc_source.write_bytes(b'drift')
                if mode == 'source-link':
                    try: (cache / 'sources/zlib-1.3.2/link').symlink_to(crc_source)
                    except OSError: continue
                keys = ['objects/libavutil/crc.o', 'objects/libz/zutil.o']
                prefix = cache / 'prefix/aarch64-linux'
                prefix.mkdir(parents=True); (prefix / 'objects.txt').write_text('\n'.join(keys) + '\n')
                for key in keys:
                    p = prefix / key; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'baseline object')
                # Existing outputs must never be copied into the new build tree.
                (cache / 'build').mkdir(); (cache / 'build/baseline-marker').write_bytes(b'not input')
                directory = output / 'modified-media-source-rebuild'
                copied = directory / 'native'; copied_cache = copied / '.cache/ffmpeg'
                dependency = {'objectsWithoutDependencyFiles': ['missing'] if mode == 'dependency-gap' else [],
                              'objects': [], 'files': []}

                def run(command, **kwargs):
                    self.assertEqual(command, ['bun', 'scripts/build-ffmpeg.ts', '--target=aarch64-linux'])
                    self.assertEqual(kwargs['cwd'], copied)
                    self.assertNotIn('NODE_TLS_REJECT_UNAUTHORIZED', kwargs['env'])
                    self.assertFalse((copied_cache / 'build').exists())
                    self.assertFalse((copied_cache / 'prefix').exists())
                    original_configure = cache / 'sources/ffmpeg-9.0.2/configure'
                    copied_configure = copied_cache / 'sources/ffmpeg-9.0.2/configure'
                    self.assertEqual(original_configure.stat().st_mode, copied_configure.stat().st_mode)
                    self.assertEqual((copied_cache / 'sources/ffmpeg-9.0.2/libavutil/crc.c').read_bytes(), b'modified CRC')
                    kwargs['stdout'].write(b'actual compiler output\n')
                    if mode == 'build-fail': raise subprocess.CalledProcessError(1, command)
                    if mode == 'timeout': raise subprocess.TimeoutExpired(command, 1800)
                    target = copied_cache / 'prefix/aarch64-linux'; target.mkdir(parents=True)
                    names = keys if mode != 'object-set' else keys[:1]
                    if mode == 'duplicate-object': names = keys + keys[:1]
                    if mode == 'empty-objects': names = []
                    (target / 'objects.txt').write_text('\n'.join(names))
                    for key in keys:
                        raw = bytearray(64); raw[:7] = b'\x7fELF\x02\x01\x01'
                        raw[16:18] = (3 if mode == 'object-type' else 1).to_bytes(2, 'little')
                        raw[18:20] = (62 if mode == 'object-machine' else 183).to_bytes(2, 'little')
                        raw[20:24] = (0 if mode == 'object-version' else 1).to_bytes(4, 'little')
                        if mode == 'object-elf': raw = b'bad'
                        if mode == 'crc-unchanged' and key == keys[0]: raw = b'baseline object'
                        p = target / key; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
                        group = 'zlib' if key.startswith('objects/libz/') else 'libavutil'
                        built = copied_cache / 'build/aarch64-linux' / group / Path(key).name
                        built.parent.mkdir(parents=True, exist_ok=True); built.write_bytes(raw)
                    config = copied_cache / 'build/aarch64-linux/config.h'
                    config.parent.mkdir(parents=True, exist_ok=True); config.write_bytes(b'configuration')
                    if mode == 'source-mutation': crc_source.write_bytes(b'changed')
                    if mode == 'baseline-mutation': (prefix / keys[1]).write_bytes(b'changed')
                    if mode == 'escape-output':
                        try: (directory / 'escape').symlink_to(root / 'original/scripts/build-ffmpeg.ts')
                        except OSError: raise ValueError('Symlink fixture unavailable')
                    return subprocess.CompletedProcess(command, 0)

                def compile_commands(text, selected, target, objects, dependencies):
                    self.assertEqual(text, 'actual compiler output\n')
                    return {'objects': [{'object': keys[0],
                        'source': 'sources/ffmpeg-9.0.2/libavutil/crc.c',
                        'sourceSha256': hashlib.sha256(b'wrong' if mode == 'crc-source' else b'modified CRC').hexdigest()},
                        {'object': keys[1]}]}

                with ExitStack() as stack:
                    stack.enter_context(patch.dict(m.media.pty.rust.sources.MEDIA_SOURCES, archives, clear=True))
                    stack.enter_context(patch.object(m.media, 'modified_crc_source', return_value=b'modified CRC'))
                    stack.enter_context(patch.object(m.media, 'verify_media_command_log'))
                    stack.enter_context(patch.object(m.media, 'ffmpeg_configuration', return_value={'CONFIG_GPL': '0'}))
                    stack.enter_context(patch.object(m.media, 'ffmpeg_source_inputs', return_value=dependency))
                    stack.enter_context(patch.object(m.media, 'media_compile_commands', side_effect=compile_commands))
                    stack.enter_context(patch.object(m, 'rebuild_swscale_macros', return_value={'mockOnly': True}))
                    stack.enter_context(patch.object(m.subprocess, 'run', side_effect=run))
                    if mode == 'ok':
                        result = m.rebuild(native, output, {'NODE_TLS_REJECT_UNAUTHORIZED': '0'})
                        self.assertEqual(len(result['compileCommands']['objects']), 2)
                        self.assertTrue(all(result[k] is False for k in ['redistributionApproved', 'androidApproved',
                            'relinkingApproved', 'fullCorrespondingSourceApproved']))
                        self.assertEqual(json.loads((directory / 'review.json').read_text())['files'], result['files'])
                        for row in result['files']: self.assertEqual(m.digest(output / row['path']), row['sha256'])
                        self.assertEqual(crc_source.read_bytes(), b'original CRC')
                        with self.assertRaises(FileExistsError): m.rebuild(native, output, {})
                    else:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired)):
                            m.rebuild(native, output, {})
                        self.assertFalse((directory / 'review.json').exists())

    def test_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            native = Path(tmp).resolve(); output = native / 'nested'; output.mkdir()
            with self.assertRaisesRegex(ValueError, 'overlap'): m.rebuild(native, output, {})

    def test_swscale_macro_source_rule_and_rejections(self):
        for mode in ['ok', 'preexisting', 'build', 'timeout', 'bad-elf', 'run', 'drift', 'mutation']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp).resolve(); cache = directory / 'cache'
                build = cache / 'build/aarch64-linux'; build.mkdir(parents=True)
                header = cache / 'sources/ffmpeg-9.0.2/libswscale/uops_macros.h'
                header.parent.mkdir(parents=True); header.write_bytes(b'macro bytes\n')
                generator = build / 'libswscale/tests/sws_ops'
                generator.parent.mkdir(parents=True)
                if mode == 'preexisting': generator.write_bytes(b'old ELF')

                def run(command, **kwargs):
                    if command[0] == 'make':
                        self.assertEqual(kwargs['cwd'], build)
                        self.assertEqual(command, ['make', 'V=1', 'libswscale/tests/sws_ops', 'ELIBS=-Wl,-z,max-page-size=16384'])
                        if mode == 'timeout': raise subprocess.TimeoutExpired(command, 300, stderr=b'partial')
                        generator.write_bytes(b'new ELF')
                        return subprocess.CompletedProcess(command, 1 if mode == 'build' else 0, b'compile argv', b'')
                    self.assertEqual(command, [str(generator), '-macros'])
                    self.assertEqual(kwargs['cwd'], directory / 'swscale-generator-rebuild')
                    if mode == 'mutation': generator.write_bytes(b'changed ELF')
                    return subprocess.CompletedProcess(command, 1 if mode == 'run' else 0,
                        b'different' if mode == 'drift' else header.read_bytes(), b'')

                with patch.object(m.subprocess, 'run', side_effect=run), \
                     patch.object(m.media.pty.audit, 'elf', side_effect=ValueError('bad ELF') if mode == 'bad-elf' else None,
                                  return_value=({}, ['libc.so.6'])):
                    if mode == 'ok':
                        result = m.rebuild_swscale_macros(cache, directory, {})
                        self.assertEqual(result['sha256'], m.digest(header))
                        self.assertEqual(result['generatorSha256'], m.digest(generator))
                        self.assertEqual(len(result['commands']), 2)
                        self.assertFalse(result['redistributionApproved'])
                    else:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired)):
                            m.rebuild_swscale_macros(cache, directory, {})

    def test_evidence_directory_alias_and_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp).resolve(); directory = output / 'evidence'; directory.mkdir()
            source = directory / 'source'; source.mkdir(); (source / 'input.h').write_bytes(b'header')
            alias = directory / 'src'
            try: alias.symlink_to(source, target_is_directory=True)
            except OSError: self.skipTest('Directory symlink fixture unavailable')
            rows = m.evidence_files(directory, output)
            self.assertEqual({r['path'] for r in rows}, {'evidence/source/input.h', 'evidence/src/input.h'})
            self.assertEqual(rows[0]['sha256'], rows[1]['sha256'])
            (source / 'cycle').symlink_to(directory, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'cycle'): m.evidence_files(directory, output)


if __name__ == '__main__': unittest.main()
