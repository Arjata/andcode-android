import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import ssl
import urllib.error
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('native_sources', Path(__file__).with_name('collect-opencode-native-sources.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def archive(entries, mode='w:gz'):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=mode) as out:
        for name, data in entries:
            item = tarfile.TarInfo(name)
            item.size = len(data)
            out.addfile(item, io.BytesIO(data))
    return buffer.getvalue()


class SourceEvidenceTest(unittest.TestCase):
    def test_transient_download_retried_without_skipping_digest(self):
        data = archive([('repo/LICENSE', b'fixture')])
        transient = urllib.error.HTTPError('https://example.invalid', 504, 'gateway', {}, None)
        with patch.object(module.urllib.request, 'urlopen', side_effect=[transient, io.BytesIO(data)]) as request, \
             patch.object(module.time, 'sleep'):
            result = module.download_archive('https://example.invalid')
            self.assertEqual(request.call_count, 2)
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                module.inspect_archive(result, '0' * 64)

    def test_download_retries_bounded_and_tls_not_retried(self):
        tls = urllib.error.URLError(ssl.SSLCertVerificationError('untrusted'))
        for error, attempts in [(TimeoutError('timeout'), 3), (tls, 1),
                                (urllib.error.HTTPError('https://example.invalid', 404, 'missing', {}, None), 1)]:
            with self.subTest(error=error), \
                 patch.object(module.urllib.request, 'urlopen', side_effect=error) as request, \
                 patch.object(module.time, 'sleep'):
                with self.assertRaises(type(error)):
                    module.download_archive('https://example.invalid')
                self.assertEqual(request.call_count, attempts)

    def test_collection_keeps_redistribution_blocked(self):
        data = archive([('repo/LICENSE', b'license example')])
        sha = module.digest(data)
        with tempfile.TemporaryDirectory() as work:
            with patch.object(module, 'SOURCES', {'fixture': ('example/repo', 'a' * 40, sha)}), \
                 patch.object(module, 'MEDIA_SOURCES', {'media.tar.gz': ('https://example.invalid/media', sha)}), \
                 patch.object(module.urllib.request, 'urlopen', side_effect=lambda *a, **k: io.BytesIO(data)):
                module.collect(work)
            report = json.loads((Path(work) / 'native-source-review.json').read_text())
            self.assertIs(report['redistributionApproved'], False)
            self.assertTrue(report['sources'][0]['status'].startswith('blocked-'))
            self.assertTrue(report['opentuiStaticMediaSources'][0]['status'].startswith('blocked-'))
            self.assertEqual((Path(work) / 'native-source-evidence/media.tar.gz').read_bytes(), data)

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

    def test_native_build_script_and_crate_vcs_are_indexed(self):
        data = archive([('crate/build.rs', b'fn main() {}'),
                        ('crate/.cargo_vcs_info.json', b'{"git":{"sha1":"example"}}')])
        result = module.inspect_archive(data, module.digest(data))
        self.assertEqual([p['path'] for p in result['buildInputs']],
                         ['crate/build.rs', 'crate/.cargo_vcs_info.json'])

    def test_xz_source(self):
        data = archive([('ffmpeg/COPYING.LGPLv2.1', b'license example')], mode='w:xz')
        result = module.inspect_archive(data, module.digest(data))
        self.assertEqual(len(result['noticeFilesByName']), 1)

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
