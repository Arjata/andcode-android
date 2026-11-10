#!/usr/bin/env python3
"""Dependency-free synthetic source acquisition tests; no apt or network calls."""
import importlib.util
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'source_collection', Path(__file__).with_name('collect-ubuntu-sources.py'))
collection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collection)
INSTALLED = 'liba:arm64\t1.0\ta\t1:1.0-1\nliba-dev\t1.0\ta\t1:1.0-1\n'


class SourceCollectionTests(unittest.TestCase):
    def runner(self, command, **kwargs):
        self.assertEqual(command[-1], 'a=1:1.0-1')
        self.assertIn('--download-only', command)
        self.assertIn('--only-source', command)
        self.assertNotIn('--allow-unauthenticated', command)
        self.assertEqual(kwargs['env']['LC_ALL'], 'C')
        directory = kwargs['cwd']
        data = b'synthetic archive; not extracted'
        (directory / 'a_1.0-1.dsc').write_text(
            'Format: 3.0 (quilt)\nSource: a\nVersion: 1:1.0-1\nChecksums-Sha256:\n '
            + hashlib.sha256(data).hexdigest() + ' ' + str(len(data)) + ' a_1.0.orig.tar.xz\n', encoding='utf-8', newline='\n')
        (directory / 'a_1.0.orig.tar.xz').write_bytes(data)
        return subprocess.CompletedProcess(command, 0, b'apt synthetic output')

    def test_exact_source_versions_deduplicated(self):
        rows = collection.installed_sources(INSTALLED)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][:2], ('a', '1:1.0-1'))
        self.assertEqual(len(rows[0][2]), 2)

    def test_invalid_package_records(self):
        for text in ['', INSTALLED + INSTALLED, 'bad\t1\t../../bad\t1\n',
                     'bad\t1\t-ok\t1\n', 'bad\t1\tok\t1;exec\n',
                     'bad\t1\tok\t--option\n']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                collection.installed_sources(text)

    def test_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'new'
            report = collection.collect(output, INSTALLED, self.runner)
            self.assertEqual(len(report['sources']), 1)
            self.assertEqual(len(report['sources'][0]['files']), 2)
            self.assertEqual(report['downloadedBytes'], sum(
                row['bytes'] for row in report['sources'][0]['files']))
            self.assertIs(report['redistributionApproved'], False)
            self.assertTrue((output / 'andcode-ubuntu-source-inputs.json').is_file())

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'keep'
            marker.write_bytes(b'preserve')
            with self.assertRaises(FileExistsError):
                collection.collect(tmp, INSTALLED, self.runner)
            self.assertEqual(marker.read_bytes(), b'preserve')

    def test_apt_failure_preserves_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'new'
            def failed(command, **kwargs):
                return subprocess.CompletedProcess(command, 100, b'failed')
            with self.assertRaises(RuntimeError):
                collection.collect(output, INSTALLED, failed)
            self.assertEqual((output / '0000-a/apt-source.log').read_bytes(), b'failed')
            self.assertFalse((output / 'andcode-ubuntu-source-inputs.json').exists())

    def test_apt_timeout_preserves_partial_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'new'
            def timeout(command, **kwargs):
                raise subprocess.TimeoutExpired(command, 600, output=b'partial download output')
            with self.assertRaisesRegex(RuntimeError, 'timed out: a=1:1.0-1'):
                collection.collect(output, INSTALLED, timeout)
            self.assertEqual((output / '0000-a/apt-source.log').read_bytes(), b'partial download output')
            self.assertFalse((output / 'andcode-ubuntu-source-inputs.json').exists())

    def test_missing_dsc_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            def incomplete(command, **kwargs):
                (kwargs['cwd'] / 'archive.tar.xz').write_bytes(b'content')
                return subprocess.CompletedProcess(command, 0, b'')
            with self.assertRaisesRegex(ValueError, 'exactly one .dsc'):
                collection.collect(Path(tmp) / 'new', INSTALLED, incomplete)

    def test_log_collision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            def collision(command, **kwargs):
                (kwargs['cwd'] / 'apt-source.log').write_bytes(b'keep')
                return subprocess.CompletedProcess(command, 0, b'')
            with self.assertRaisesRegex(ValueError, 'log collision'):
                collection.collect(Path(tmp) / 'new', INSTALLED, collision)

    def test_dsc_identity_and_hash_rejection(self):
        for mode in ['source', 'version', 'hash', 'extra', 'missing', 'duplicate', 'negative', 'zero', 'unsafe']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                def corrupt(command, **kwargs):
                    result = self.runner(command, **kwargs)
                    path = kwargs['cwd'] / 'a_1.0-1.dsc'
                    text = path.read_text()
                    if mode == 'source':
                        path.write_text(text.replace('Source: a', 'Source: wrong'))
                    elif mode == 'version':
                        path.write_text(text.replace('Version: 1:1.0-1', 'Version: 1.0-2'))
                    elif mode == 'hash':
                        (kwargs['cwd'] / 'a_1.0.orig.tar.xz').write_bytes(b'corrupt')
                    elif mode == 'extra':
                        (kwargs['cwd'] / 'extra.tar.xz').write_bytes(b'extra')
                    elif mode == 'duplicate':
                        path.write_bytes((text + 'Source: a\n').encode())
                    elif mode in ('negative', 'zero'):
                        path.write_bytes(text.replace(' ' + str(len(b'synthetic archive; not extracted')) + ' ',
                                                      ' -1 ' if mode == 'negative' else ' 0 ').encode())
                    elif mode == 'unsafe':
                        path.write_bytes(text.replace('a_1.0.orig.tar.xz', '../archive.tar.xz').encode())
                    else:
                        path.write_text(text.split('Checksums-Sha256:')[0])
                    return result
                with self.assertRaises(ValueError):
                    collection.collect(Path(tmp) / 'new', INSTALLED, corrupt)

    def test_clearsigned_dsc(self):
        with tempfile.TemporaryDirectory() as tmp:
            def signed(command, **kwargs):
                result = self.runner(command, **kwargs)
                path = kwargs['cwd'] / 'a_1.0-1.dsc'
                text = path.read_text()
                path.write_text('-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA512\n\n'
                                + text + '\n-----BEGIN PGP SIGNATURE-----\nsynthetic signature\n'
                                '-----END PGP SIGNATURE-----\n', encoding='utf-8', newline='\n')
                return result
            report = collection.collect(Path(tmp) / 'new', INSTALLED, signed)
            self.assertEqual(len(report['sources']), 1)

    def test_malformed_clearsigned_dsc_rejected(self):
        for mode in ['headers', 'missing-begin', 'missing-end', 'extra-trailer', 'crlf', 'nul']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                def malformed(command, **kwargs):
                    result = self.runner(command, **kwargs)
                    path = kwargs['cwd'] / 'a_1.0-1.dsc'
                    body = path.read_bytes()
                    text = (b'-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA512\n\n' + body
                            + b'\n-----BEGIN PGP SIGNATURE-----\nsynthetic signature\n'
                            b'-----END PGP SIGNATURE-----\n')
                    if mode == 'headers': text = text.replace(b'\nHash: SHA512', b'')
                    elif mode == 'missing-begin': text = text.replace(b'-----BEGIN PGP SIGNATURE-----\n', b'')
                    elif mode == 'missing-end': text = text.replace(b'-----END PGP SIGNATURE-----\n', b'')
                    elif mode == 'extra-trailer': text += b'unexpected\n'
                    elif mode == 'crlf': text = text.replace(b'\n', b'\r\n')
                    else: text += b'\x00'
                    path.write_bytes(text)
                    return result
                with self.assertRaisesRegex(ValueError, 'source control'):
                    collection.collect(Path(tmp) / 'new', INSTALLED, malformed)

    def test_unexpected_directory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            def extra_directory(command, **kwargs):
                result = self.runner(command, **kwargs)
                (kwargs['cwd'] / 'unpacked').mkdir()
                return result
            with self.assertRaisesRegex(ValueError, 'Unexpected downloaded source path'):
                collection.collect(Path(tmp) / 'new', INSTALLED, extra_directory)


if __name__ == '__main__':
    unittest.main()
