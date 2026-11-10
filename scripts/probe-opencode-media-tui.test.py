"""Synthetic replacement TUI staging and rejection tests, no Linux execution."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('media_tui', Path(__file__).with_name('probe-opencode-media-tui.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    def test_isolation_mapping_render_and_rejections(self):
        for mode in ['ok', 'baseline', 'replacement', 'failed', 'timeout', 'marker', 'maps',
                     'render', 'extraction', 'mutate', 'copy-mutate', 'duplicate']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                stage = Path(tmp).resolve()
                exe = stage / 'opencode'; exe.write_bytes(b'executable')
                native = stage / 'native'; native.mkdir()
                rows = []
                for name, data, source in [('opentui.so', b'original', '/@opentui/core-linux-arm64/lib.so'),
                                           ('other.so', b'other', '/other/lib.so')]:
                    path = native / name; path.write_bytes(data)
                    rows.append('\t'.join([name, m.digest(path), str(len(data)), source]))
                (stage / 'oc2-native.tsv').write_text('\n'.join(rows) + '\n')
                output = stage / 'native-opentui-build'
                replacement = output / 'media-object-relink/libopentui.so'
                replacement.parent.mkdir(parents=True); replacement.write_bytes(b'replacement')
                (stage / 'native-opentui-build-review.json').write_text(json.dumps({
                    'mediaObjectRelink': {'files': [{'path': 'media-object-relink/libopentui.so',
                                                   'bytes': replacement.stat().st_size,
                                                   'sha256': m.digest(replacement)}]}}))
                if mode == 'baseline': (native / 'opentui.so').write_bytes(b'changed')
                if mode == 'replacement': replacement.write_bytes(b'changed')
                if mode == 'duplicate': (stage / 'oc2-native.tsv').write_text('\n'.join(rows + rows) + '\n')
                directory = replacement.parent / 'media-tui'

                def run(command, **kwargs):
                    env = kwargs['env']
                    self.assertNotIn('LD_PRELOAD', env)
                    self.assertEqual(env['ANDCODE_EXE_DIR'], str(directory / 'native'))
                    self.assertEqual(env['HOME'], str(directory / 'home'))
                    self.assertEqual(env['BUN_TMPDIR'], str(directory / 'tmp'))
                    self.assertEqual((directory / 'native/opentui.so').read_bytes(), b'replacement')
                    self.assertEqual((native / 'opentui.so').read_bytes(), b'original')
                    self.assertEqual((directory / 'native/other.so').read_bytes(), b'other')
                    if mode == 'timeout': raise subprocess.TimeoutExpired(command, 50, stderr=b'partial')
                    (directory / 'tui-output.bin').write_bytes(b'empty' if mode == 'render' else b'\x1b[0m opencode')
                    (directory / 'tui-maps.txt').write_text('other' if mode == 'maps' else str(directory / 'native/opentui.so'))
                    if mode == 'extraction': (directory / 'tmp/extracted.so').write_bytes(b'\x7fELFbad')
                    if mode == 'mutate': exe.write_bytes(b'changed')
                    if mode == 'copy-mutate': (directory / 'native/other.so').write_bytes(b'changed')
                    return subprocess.CompletedProcess(command, 1 if mode == 'failed' else 0,
                        b'' if mode == 'marker' else b'ANDCODE_SOURCE_TUI_NATIVE_OK (Linux CI only)\n', b'')

                with patch.object(m.subprocess, 'run', side_effect=run):
                    if mode == 'ok':
                        report = m.probe(exe, stage, {'LD_PRELOAD': 'untrusted'})
                        self.assertTrue(report['mappedReplacement'])
                        self.assertFalse(report['lookupManifestIsReleaseManifest'])
                        self.assertFalse(report['runtimeExtractedElf'])
                        self.assertNotEqual(report['replacementSha256'], report['originalSha256'])
                        self.assertTrue(all(not report[k] for k in ['redistributionApproved', 'androidApproved', 'relinkingApproved']))
                        self.assertEqual(json.loads((directory / 'review.json').read_text())['alias'], report['alias'])
                        with self.assertRaises(FileExistsError): m.probe(exe, stage, {})
                    else:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired)):
                            m.probe(exe, stage, {})
                        self.assertFalse((directory / 'review.json').exists())


if __name__ == '__main__': unittest.main()
