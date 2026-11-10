import hashlib
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
                 patch.object(module, 'RUNTIME_DECLARATIONS', {}), \
                 patch.object(module, 'collect_bun_source', return_value={'stub': True}), \
                 patch.object(module.urllib.request, 'urlopen', side_effect=lambda *a, **k: io.BytesIO(data)):
                module.collect(work)
            report = json.loads((Path(work) / 'native-source-review.json').read_text())
            self.assertIs(report['redistributionApproved'], False)
            self.assertTrue(report['sources'][0]['status'].startswith('blocked-'))
            self.assertTrue(report['opentuiStaticMediaSources'][0]['status'].startswith('blocked-'))
            self.assertEqual((Path(work) / 'native-source-evidence/media.tar.gz').read_bytes(), data)

    def test_runtime_declarations_are_pinned_and_never_approved(self):
        content = ('export const WEBKIT_VERSION = "' + module.WEBKIT_COMMIT + '";\n').encode()
        files = {'scripts/build/deps/webkit.ts': module.digest(content)}
        with tempfile.TemporaryDirectory() as work, \
                patch.object(module, 'RUNTIME_DECLARATIONS', {'bun': ('oven-sh/bun', module.BUN_COMMIT, files)}), \
                patch.object(module, 'download_archive', return_value=content) as download:
            root = Path(work)
            report = module.collect_runtime_declarations(root)
            self.assertFalse(report['redistributionApproved'])
            self.assertFalse(report['correspondingSourceComplete'])
            self.assertFalse(report['relinkingApproved'])
            row = report['files'][0]
            self.assertEqual((root / row['retainedPath']).read_bytes(), content)
            self.assertEqual(row['sha256'], module.digest(content))
            self.assertIn(module.BUN_COMMIT, download.call_args.args[0])

    def test_runtime_declaration_drift_paths_and_wrong_pin_rejected(self):
        for mode in ['digest', 'pin', 'large', 'unsafe']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as work:
                content = b'export const WEBKIT_VERSION = "' + b'0' * 40 + b'";\n'
                if mode == 'large': content = b'x' * (1024 * 1024 + 1)
                path = '../escape' if mode == 'unsafe' else 'scripts/build/deps/webkit.ts'
                expected = '0' * 64 if mode == 'digest' else module.digest(content)
                with patch.object(module, 'RUNTIME_DECLARATIONS', {'bun': ('oven-sh/bun', module.BUN_COMMIT, {path: expected})}), \
                        patch.object(module, 'download_archive', return_value=content):
                    with self.assertRaises(ValueError):module.collect_runtime_declarations(Path(work))
                self.assertFalse((Path(work) / 'runtime-declarations/bun/scripts/build/deps/webkit.ts').exists())

    def test_late_runtime_declaration_failure_publishes_no_files(self):
        content = b'valid fixed source text\n'
        for changed in [b'changed', b'x' * (1024 * 1024 + 1)]:
            with self.subTest(bytes=len(changed)), tempfile.TemporaryDirectory() as work:
                files = {'LICENSE.md': module.digest(content), 'Cargo.lock': module.digest(content)}
                with patch.object(module, 'RUNTIME_DECLARATIONS', {'bun': ('oven-sh/bun', module.BUN_COMMIT, files)}), \
                        patch.object(module, 'download_archive', side_effect=[content, changed]):
                    with self.assertRaises(ValueError): module.collect_runtime_declarations(Path(work))
                self.assertFalse(list((Path(work) / 'runtime-declarations').rglob('*')))

    def test_bun_build_declarations_include_material_relink_rules(self):
        files = module.RUNTIME_DECLARATIONS['bun'][2]
        for path in ['scripts/build/rust.ts', 'scripts/build/flags.ts', 'scripts/build/compile.ts',
                     'scripts/build/codegen.ts', 'scripts/build/source.ts', 'scripts/build/deps/mimalloc.ts',
                     'scripts/build/ci-images/spec.ts', 'rust-toolchain.toml', 'src/linker.lds',
                     'Cargo.toml', 'Cargo.lock', 'patches/mimalloc/new-oom-hook.patch']:
            self.assertIn(path, files)
            self.assertRegex(files[path], r'^[0-9a-f]{64}$')

    def bun_archive(self):
        prefix = 'bun-' + module.BUN_COMMIT + '/'
        synthetic = {path: module.digest(path.encode())
                     for path in module.RUNTIME_DECLARATIONS['bun'][2]}
        entries = [(prefix, None)]
        for path in synthetic:
            entries.append((prefix + path, path.encode()))
        entries += [(prefix + 'link', None, 'Cargo.toml')]
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            for name, data, *link in entries:
                item = tarfile.TarInfo(name)
                if link:
                    item.type = tarfile.SYMTYPE; item.linkname = link[0]
                elif data is None:
                    item.type = tarfile.DIRTYPE
                else:
                    item.size = len(data); data_file = io.BytesIO(data)
                tar.addfile(item, None if link or data is None else data_file)
        return buffer.getvalue(), synthetic

    def collect_bun(self, work, archive, synthetic, pinned=None):
        pin = patch.object(module, 'BUN_SOURCE_SHA256', pinned or module.BUN_SOURCE_SHA256)
        with pin, \
                patch.object(module, 'RUNTIME_DECLARATIONS',
                             {'bun': ('oven-sh/bun', module.BUN_COMMIT, synthetic)}), \
                patch.object(module, 'download_archive', return_value=archive):
            return module.collect_bun_source(Path(work))

    def test_bun_source_archive_inventory_and_rejections(self):
        archive, synthetic = self.bun_archive()
        member_count = 1 + len(synthetic) + 1
        for mode, data in [('ok', archive), ('drift', b'x' + archive),
                           ('oversize', b'x' * (module.LIMIT + 1))]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as work:
                if mode == 'ok':
                    result = self.collect_bun(work, data, synthetic,
                                              pinned=hashlib.sha256(archive).hexdigest())
                    self.assertEqual(result['commit'], module.BUN_COMMIT)
                    self.assertEqual(result['memberCount'], member_count)
                    self.assertTrue(all(result[k] is False for k in
                        ['redistributionApproved', 'androidApproved', 'relinkingApproved',
                         'fullCorrespondingSourceApproved']))
                    inventory = json.loads((Path(work) / 'bun-source-inventory.json').read_text())
                    self.assertEqual(len(inventory['members']), member_count)
                    self.assertEqual(result['inventorySha256'],
                                     hashlib.sha256((Path(work) / 'bun-source-inventory.json').read_bytes()).hexdigest())
                    self.assertEqual(inventory['sha256'], hashlib.sha256(archive).hexdigest())
                    self.assertEqual({row['type'] for row in inventory['members']},
                                     {'directory', 'file', 'symlink'})
                else:
                    with self.assertRaises(ValueError): self.collect_bun(work, data, synthetic)
                    self.assertFalse(list(Path(work).glob('*')))

    def test_bun_source_unsafe_members_and_declaration_drift_rejected(self):
        archive, synthetic = self.bun_archive()
        prefix = 'bun-' + module.BUN_COMMIT + '/'
        with self.subTest(mode='path-escape'):
            with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as source:
                members = [m for m in source.getmembers() if m.isfile()]
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
                for member in members:
                    tar.addfile(member, io.BytesIO(b'x' * member.size))
                bad = tarfile.TarInfo(prefix + '../escape'); bad.size = 1
                tar.addfile(bad, io.BytesIO(b'x'))
            with tempfile.TemporaryDirectory() as work:
                with self.assertRaises(ValueError): self.collect_bun(work, buffer.getvalue(), synthetic)
                self.assertFalse(list(Path(work).glob('*')))
        with self.subTest(mode='absolute-symlink'):
            with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as source:
                members = source.getmembers()
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
                for member in members:
                    if member.issym() and member.linkname == 'Cargo.toml':
                        member.linkname = '/etc/passwd'
                    tar.addfile(member, io.BytesIO(b'x' * member.size) if member.isfile() else None)
            with tempfile.TemporaryDirectory() as work:
                with self.assertRaises(ValueError): self.collect_bun(work, buffer.getvalue(), synthetic)
                self.assertFalse(list(Path(work).glob('*')))
        with self.subTest(mode='declaration-drift'):
            first = next(iter(synthetic))
            with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as source:
                members = [m for m in source.getmembers() if m.name != prefix + first]
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
                for member in members:
                    tar.addfile(member, io.BytesIO(b'x' * member.size) if member.isfile() else None)
                changed = tarfile.TarInfo(prefix + first); changed.size = 7
                tar.addfile(changed, io.BytesIO(b'drifted'))
            with tempfile.TemporaryDirectory() as work:
                with self.assertRaises(ValueError): self.collect_bun(work, buffer.getvalue(), synthetic)
                self.assertFalse(list(Path(work).glob('*')))

    def test_bun_source_refuses_overwrite(self):
        archive, synthetic = self.bun_archive()
        pinned = hashlib.sha256(archive).hexdigest()
        with tempfile.TemporaryDirectory() as work:
            self.collect_bun(work, archive, synthetic, pinned=pinned)
            with self.assertRaises(FileExistsError): self.collect_bun(work, archive, synthetic, pinned=pinned)

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
