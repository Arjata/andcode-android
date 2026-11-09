import importlib.util
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('rust_evidence', Path(__file__).with_name('collect-opencode-native-rust.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CandidateGraphTest(unittest.TestCase):
    def test_dedup_and_build_annotations(self):
        lock = {'package': [{'name': 'a', 'version': '1.0.0'}, {'name': 'b', 'version': '2.0.0'}]}
        tree = 'a v1.0.0 (local)|MIT|zlob\nb v2.0.0 (proc-macro)|MIT|default\nb v2.0.0|MIT|default (*)\n'
        self.assertEqual(module.selected_packages(tree, lock), lock['package'])

    def test_unknown_package_rejected(self):
        with self.assertRaisesRegex(ValueError, 'absent'):
            module.selected_packages('foreign v1.0.0|MIT|', {'package': []})

    def test_empty_and_invalid_graphs_rejected(self):
        for tree in ['', 'unexpected warning', '../escape v1.0.0|MIT|']:
            with self.subTest(tree=tree), self.assertRaises(ValueError):
                module.selected_packages(tree, {'package': []})

    def test_ambiguous_lock_identity_rejected(self):
        lock = {'package': [{'name': 'a', 'version': '1'}, {'name': 'a', 'version': '1', 'source': 'other'}]}
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            module.selected_packages('a v1|MIT|', lock)

    def test_candidate_unpack_skips_links_and_rejects_escape(self):
        for name in ['root/Cargo.toml', '../escape']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                data = io.BytesIO()
                with tarfile.open(fileobj=data, mode='w:gz') as archive:
                    file = tarfile.TarInfo(name)
                    file.size = 1
                    archive.addfile(file, io.BytesIO(b'x'))
                    link = tarfile.TarInfo('root/link')
                    link.type = tarfile.SYMTYPE
                    link.linkname = '/outside'
                    archive.addfile(link)
                src = Path(tmp) / 'candidate.tar.gz'
                src.write_bytes(data.getvalue())
                checksum = hashlib.sha256(data.getvalue()).hexdigest()
                if name.startswith('..'):
                    with self.assertRaises(ValueError):
                        module.unpack_candidate(src, checksum, Path(tmp) / 'out')
                else:
                    root = module.unpack_candidate(src, checksum, Path(tmp) / 'out')
                    self.assertEqual((root / 'Cargo.toml').read_bytes(), b'x')
                    self.assertFalse((root / 'link').exists())


if __name__ == '__main__':
    unittest.main()
