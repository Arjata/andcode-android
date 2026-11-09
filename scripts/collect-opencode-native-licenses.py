"""Collect bounded frozen-package evidence; deliberately never approve redistribution."""
import hashlib
import json
from pathlib import Path
import re
import sys

EXPECTED = {
    '@opentui/core-linux-arm64': ('0.8.1', 'MIT AND LGPL-2.1-or-later'),
    '@parcel/watcher-linux-arm64-glibc': ('2.5.1', 'MIT'),
    '@ff-labs/fff-bin-linux-arm64-gnu': ('0.10.5', 'MIT'),
    'bun-pty': ('0.4.11', 'MIT'),
}


def collect(upstream, stage):
    upstream, stage = Path(upstream).resolve(), Path(stage).resolve()
    rows = []
    for row in (stage / 'oc2-native.tsv').read_text(encoding='utf8').splitlines():
        physical, digest, size, source = row.split('\t')
        payload = (stage / 'native' / physical).read_bytes()
        if hashlib.sha256(payload).hexdigest() != digest or len(payload) != int(size):
            raise ValueError('Native bytes do not match import manifest')
        source = Path(source).resolve(strict=True)
        source.relative_to(upstream)
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError('Installed source bytes changed')
        package = source.parent
        while not (package / 'package.json').is_file():
            if package == upstream:
                raise ValueError('No owning package within upstream')
            package = package.parent
        metadata = json.loads((package / 'package.json').read_text(encoding='utf8'))
        name, version, license_id = metadata['name'], metadata['version'], metadata.get('license')
        if name not in EXPECTED or (version, license_id) != EXPECTED[name]:
            raise ValueError('Unexpected fixed native package: ' + name)
        origin = {'kind': 'frozen-npm-native-input'}
        build_reports = {'bun-pty': 'native-pty-build-review.json',
                         '@parcel/watcher-linux-arm64-glibc': 'native-watcher-build-review.json'}
        build_report = stage / build_reports[name] if name in build_reports else None
        if build_report is not None and build_report.exists():
            build = json.loads(build_report.read_text(encoding='utf8'))
            if build['rebuiltSha256'] != digest or build.get('redistributionApproved') is not False:
                raise ValueError('Rebuilt native provenance does not match imported bytes')
            origin = {'kind': 'fixed-source-ci-rebuild', 'report': build_report.name,
                      'sourceCommit': build['sourceCommit'], 'originalNpmSha256': build['originalNpmSha256']}
        slug = name.lstrip('@').replace('/', '--')
        evidence = stage / 'native-license-evidence' / slug
        evidence.mkdir(parents=True, exist_ok=False)
        (evidence / 'package.json').write_bytes((package / 'package.json').read_bytes())
        notices = []
        # Only package-owned declarations, not an accidental traversal into other
        # dependencies. Static Rust/C/C++ dependency review is explicitly separate.
        for item in sorted(package.iterdir()):
            if re.match(r'^(license|copying|notice)(?:$|[._-])', item.name, re.I):
                if not item.is_file() or item.is_symlink():
                    raise ValueError('Unsafe package notice path')
                data = item.read_bytes()
                (evidence / item.name).write_bytes(data)
                notices.append({'path': item.name, 'sha256': hashlib.sha256(data).hexdigest()})
        rows.append({'physical': physical, 'sha256': digest, 'package': name,
                     'binaryOrigin': origin,
                     'version': version, 'declaredLicense': license_id, 'notices': notices,
                     'status': 'blocked-transitive-review' if notices else 'blocked-missing-package-notice',
                     'obligations': ['Review exact native source and static dependencies',
                                     'Provide corresponding source and relinking materials where required',
                                     'Retain all applicable copyright and license notices']})
    if {r['package'] for r in rows} != set(EXPECTED) or len(rows) != len(EXPECTED):
        raise ValueError('Expected exactly four fixed glibc native packages')
    (stage / 'native-license-review.json').write_text(json.dumps({
        'redistributionApproved': False, 'scope': 'Four imported native extensions only; excludes Bun and other bundled code',
        'packages': rows}, indent=2) + '\n', encoding='utf8')
    print('Collected four frozen native package declarations; redistribution remains BLOCKED')


if __name__ == '__main__':
    collect(*sys.argv[1:])
