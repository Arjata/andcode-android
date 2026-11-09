import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('native_manifest', Path(__file__).with_name('manifest-opencode-native.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    def link(self, link, target, directory=False):
        try:
            link.symlink_to(Path(target), target_is_directory=directory)
        except OSError as error:
            self.skipTest('Host cannot create symlinks: ' + str(error))

    def test_hidden_files_and_deterministic_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'z').write_bytes(b'last')
            (root / '.hidden').write_bytes(b'hidden')
            expected = ''.join(f'{hashlib.sha256(data).hexdigest()}  {(root / name).as_posix()}\n'
                               for name, data in [('.hidden', b'hidden'), ('z', b'last')])
            self.assertEqual(m.manifest(root), expected)

    def test_upload_dereferences_internal_directory_and_file_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'sources').mkdir()
            (root / 'sources/config.h').write_bytes(b'config')
            self.link(root / 'src', 'sources', True)
            self.link(root / 'config-link', 'sources/config.h')
            lines = m.manifest(root).splitlines()
            self.assertEqual(len(lines), 3)
            self.assertTrue(all(line.startswith(hashlib.sha256(b'config').hexdigest()) for line in lines))
            self.assertIn((root / 'src/config.h').as_posix(), '\n'.join(lines))

    def test_external_link_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage = root / 'stage'
            stage.mkdir()
            (root / 'outside').write_bytes(b'external')
            self.link(stage / 'link', '../outside')
            with self.assertRaises(ValueError):
                m.manifest(stage)

    def test_cycles_and_broken_links_rejected(self):
        for target in ['.', 'absent']:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.link(root / 'link', target, True)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    m.manifest(root)

    def test_empty_upload_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Empty'):
                m.manifest(tmp)


if __name__ == '__main__':
    unittest.main()
