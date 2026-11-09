import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('license_evidence', Path(__file__).with_name('collect-opencode-native-licenses.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LicenseEvidenceTest(unittest.TestCase):
    def fixture(self, root):
        upstream, stage = root / 'upstream', root / 'stage'
        (stage / 'native').mkdir(parents=True)
        rows = []
        for index, (name, (version, license_id)) in enumerate(module.EXPECTED.items()):
            package = upstream / name
            package.mkdir(parents=True)
            (package / 'package.json').write_text(json.dumps({'name': name, 'version': version, 'license': license_id}))
            if 'fff' not in name:
                (package / 'LICENSE').write_text('test notice only')
            payload = str(index).encode()
            digest = hashlib.sha256(payload).hexdigest()
            physical = f'libandcode-oc2-native-{digest[:16]}.so'
            source = package / 'lib.so'
            source.write_bytes(payload)
            (stage / 'native' / physical).write_bytes(payload)
            rows.append(f'{physical}\t{digest}\t{len(payload)}\t{source}')
        (stage / 'oc2-native.tsv').write_text('\n'.join(rows))
        return upstream, stage

    def test_missing_notices_remain_blocked_and_mixed_license_preserved(self):
        with tempfile.TemporaryDirectory() as work:
            upstream, stage = self.fixture(Path(work))
            module.collect(upstream, stage)
            result = json.loads((stage / 'native-license-review.json').read_text())
            self.assertFalse(result['redistributionApproved'])
            self.assertEqual(len(result['packages']), 4)
            self.assertEqual(result['packages'][0]['declaredLicense'], 'MIT AND LGPL-2.1-or-later')
            self.assertEqual(result['packages'][2]['status'], 'blocked-missing-package-notice')

    def test_changed_source_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            upstream, stage = self.fixture(Path(work))
            (upstream / '@opentui/core-linux-arm64/lib.so').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                module.collect(upstream, stage)

    def test_changed_package_version_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            upstream, stage = self.fixture(Path(work))
            package = upstream / '@opentui/core-linux-arm64/package.json'
            metadata = json.loads(package.read_text())
            metadata['version'] = '0.8.2'
            package.write_text(json.dumps(metadata))
            with self.assertRaises(ValueError):
                module.collect(upstream, stage)

    def test_rebuilt_origin_must_match_imported_elf(self):
        for index, report_name in [(3, 'native-pty-build-review.json'), (1, 'native-watcher-build-review.json'),
                                   (2, 'native-fff-build-review.json')]:
            for digest in [hashlib.sha256(str(index).encode()).hexdigest(), '0' * 64]:
                with self.subTest(index=index, digest=digest), tempfile.TemporaryDirectory() as work:
                    upstream, stage = self.fixture(Path(work))
                    (stage / report_name).write_text(json.dumps({
                        'rebuiltSha256': digest, 'redistributionApproved': False,
                        'sourceCommit': 'fixed-source', 'originalNpmSha256': 'original-npm'}))
                    if digest == '0' * 64:
                        with self.assertRaisesRegex(ValueError, 'provenance'):
                            module.collect(upstream, stage)
                    else:
                        module.collect(upstream, stage)
                        result = json.loads((stage / 'native-license-review.json').read_text())
                        self.assertEqual(result['packages'][index]['binaryOrigin']['kind'], 'fixed-source-ci-rebuild')
                        self.assertIs(result['redistributionApproved'], False)


if __name__ == '__main__':
    unittest.main()
