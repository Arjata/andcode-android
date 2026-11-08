import importlib.util
import io
from pathlib import Path
import tarfile
import unittest

spec = importlib.util.spec_from_file_location('native_sources', Path(__file__).with_name('collect-opencode-native-sources.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def archive(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as out:
        for name, data in entries:
            item = tarfile.TarInfo(name)
            item.size = len(data)
            out.addfile(item, io.BytesIO(data))
    return buffer.getvalue()


class SourceEvidenceTest(unittest.TestCase):
    def test_notices_build_inputs_and_nested_sources(self):
        nested = archive([('yoga/LICENSE', b'MIT example')])
        data = archive([('repo/LICENSE', b'MIT example'), ('repo/Cargo.toml', b'[package]\n'),
                        ('repo/Cargo.lock', b'version = 3\n[[package]]\nname = "test"\nversion = "1.0.0"\n'),
                        ('repo/zig-deps.tar.gz', nested)])
        result = module.inspect_archive(data, module.digest(data))
        self.assertEqual(len(result['noticeFilesByName']), 1)
        self.assertEqual(len(result['buildInputs']), 2)
        self.assertEqual(result['lockfiles'][0]['packages'][0]['name'], 'test')
        self.assertEqual(len(result['nestedArchives'][0]['evidence']['noticeFilesByName']), 1)

    def test_digest_mismatch(self):
        with self.assertRaises(ValueError):
            module.inspect_archive(archive([]), '0' * 64)

    def test_excessive_nesting(self):
        data = archive([('repo/LICENSE', b'MIT')])
        for _ in range(3):
            data = archive([('repo/zig-deps.tar.gz', data)])
        with self.assertRaises(ValueError):
            module.inspect_archive(data, module.digest(data))

    def test_unsafe_and_duplicate_paths(self):
        for entries in [[('../escape', b'bad')], [('/absolute', b'bad')], [('a\\b', b'bad')],
                        [('repo/LICENSE', b'a'), ('repo/LICENSE', b'b')]]:
            with self.subTest(entries=entries):
                data = archive(entries)
                with self.assertRaises(ValueError):
                    module.inspect_archive(data, module.digest(data))


if __name__ == '__main__':
    unittest.main()
