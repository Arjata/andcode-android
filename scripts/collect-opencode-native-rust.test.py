import importlib.util
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

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

    def test_supplement_commit_must_match_crate(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as archive:
            content = json.dumps({'git': {'sha1': 'a' * 40}}).encode()
            member = tarfile.TarInfo('crate/.cargo_vcs_info.json')
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        module.validate_vcs(data.getvalue(), 'a' * 40)
        with self.assertRaisesRegex(ValueError, 'does not match'):
            module.validate_vcs(data.getvalue(), 'b' * 40)

    def test_serial_supplement_requires_every_crate_file(self):
        def archive(entries):
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode='w:gz') as out:
                for name, content in entries:
                    member = tarfile.TarInfo(name)
                    member.size = len(content)
                    out.addfile(member, io.BytesIO(content))
            return data.getvalue()
        repository = archive([('repo/LICENSE', b'MIT fixture'), ('repo/serial/src/lib.rs', b'code')])
        expected = ('commit', hashlib.sha256(repository).hexdigest(), hashlib.sha256(b'MIT fixture').hexdigest())
        with patch.object(module, 'SERIAL_SOURCE', expected):
            crate = archive([('serial/src/lib.rs', b'code')])
            self.assertEqual(module.match_serial_source(crate, repository), (b'MIT fixture', ['src/lib.rs']))
            for entries in [[('serial/src/lib.rs', b'changed')], [('serial/missing', b'code')], []]:
                with self.subTest(entries=entries), self.assertRaisesRegex(ValueError, 'differ'):
                    module.match_serial_source(archive(entries), repository)

    def test_collection_stays_blocked_with_pinned_registry_sources(self):
        def archive(entries):
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode='w:gz') as out:
                for name, content in entries:
                    member = tarfile.TarInfo(name)
                    member.size = len(content)
                    out.addfile(member, io.BytesIO(content))
            return data.getvalue()

        crate = archive([('dep-1/LICENSE', b'example notice'),
                         ('dep-1/.cargo_vcs_info.json', json.dumps({'git': {'sha1': 'a' * 40}}).encode())])
        notice = b'supplemental notice fixture'
        sha = hashlib.sha256(crate).hexdigest()
        lock = ('[[package]]\nname="root"\nversion="1"\n'
                '[[package]]\nname="dep"\nversion="1"\n'
                'source="registry+https://github.com/rust-lang/crates.io-index"\n'
                f'checksum="{sha}"\n').encode()
        candidate = archive([('root/Cargo.toml', b'[package]'), ('root/Cargo.lock', lock)])
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            (stage / 'native-source-evidence').mkdir()
            (stage / 'native-source-evidence/fixture-commit.tar.gz').write_bytes(candidate)
            with patch.object(module, 'CANDIDATES', {'fixture': ('Cargo.toml', 'Cargo.lock', [])}), \
                 patch.object(module.sources, 'SOURCES', {'fixture': ('repo', 'commit', hashlib.sha256(candidate).hexdigest())}), \
                 patch.object(module, 'SUPPLEMENTAL_NOTICES', {('dep', '1'): ('repo', 'a' * 40, hashlib.sha256(notice).hexdigest())}), \
                 patch.object(module.subprocess, 'check_output', side_effect=['root v1|MIT|\ndep v1|MIT|\n', 'cargo fixture', 'rustc fixture']), \
                 patch.object(module.urllib.request, 'urlopen', side_effect=[io.BytesIO(crate), io.BytesIO(notice)]):
                module.collect(stage)
            report = json.loads((stage / 'native-rust-review.json').read_text())
            self.assertEqual(report['candidates'][0]['sourceCommit'], 'commit')
            self.assertIs(report['redistributionApproved'], False)
            self.assertIs(report['binaryCorrespondenceProven'], False)
            dependency = report['candidates'][0]['packages'][0]
            self.assertEqual(dependency['checksum'], sha)
            self.assertEqual(dependency['supplementalNotice']['commit'], 'a' * 40)
            self.assertTrue(dependency['status'].startswith('blocked-'))
            self.assertEqual((stage / 'native-rust-evidence/dep-1.crate').read_bytes(), crate)


if __name__ == '__main__':
    unittest.main()
