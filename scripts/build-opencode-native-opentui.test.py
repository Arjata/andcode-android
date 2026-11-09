import importlib.util
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('opentui_build', Path(__file__).with_name('build-opencode-native-opentui.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    def test_exact_anchor(self):
        self.assertEqual(m.patch_once('before anchor after', 'anchor', 'patched'), 'before patched after')
        for text in ['missing', 'anchor anchor']:
            with self.assertRaises(ValueError):
                m.patch_once(text, 'anchor', 'patched')

    def test_nested_rejects_escape_and_links(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                           ('link', tarfile.SYMTYPE), ('a\\b', tarfile.REGTYPE)]:
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode='w:gz') as t:
                info = tarfile.TarInfo(name)
                info.type = kind
                t.addfile(info)
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    m.unpack_nested(data.getvalue(), Path(tmp))

    def test_nested_regular_file(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as t:
            info = tarfile.TarInfo('yoga/LICENSE')
            info.size = 3
            t.addfile(info, io.BytesIO(b'MIT'))
        with tempfile.TemporaryDirectory() as tmp:
            m.unpack_nested(data.getvalue(), Path(tmp))
            self.assertEqual((Path(tmp) / 'yoga/LICENSE').read_bytes(), b'MIT')

    def test_failure_keeps_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result, target = out / 'new.so', out / 'npm.so'
            result.write_bytes(b'new'); target.write_bytes(b'original')
            with patch.object(m.pty.audit, 'elf', return_value=(None, ['libz.so.1'])):
                with self.assertRaises(ValueError):
                    m.validate(result, target, out, {})
            self.assertEqual(target.read_bytes(), b'original')
            symbols = '\n'.join('1 GLOBAL FUNC ot_' + s for s in [
                'context_abi_version', 'context_create', 'context_destroy', 'video_open'])
            with patch.object(m.pty.audit, 'elf', return_value=(None, ['libc.so.6'])), \
                    patch.object(m.subprocess, 'check_output', return_value=symbols), \
                    patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'failed')):
                with self.assertRaises(subprocess.CalledProcessError):
                    m.validate(result, target, out, {})
            self.assertEqual(target.read_bytes(), b'original')


if __name__ == '__main__':
    unittest.main()
