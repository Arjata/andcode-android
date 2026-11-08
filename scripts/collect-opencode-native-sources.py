"""Pinned candidate-source evidence; NOT binary reproducibility or license approval."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import tomllib
import urllib.request

SOURCES = {
    'opentui': ('anomalyco/opentui', '9a09079c0c7ad0fb2d55404f66a5c453204328dd',
                '215969a66f7ca090405ef47d6ea350c2c11987084c688111d7a78fa9132b22fd'),
    'fff': ('dmtrKovalenko/fff', '459ebcdbdba094843fe5339a1a7f7dae4ced2d82',
            '605d997abc090b337b2c78e20a85bad910a0bf0f53d5e452ca2805eb5bf8620b'),
    'bun-pty': ('sursaone/bun-pty', 'a582ae17cc6c41cb890b142c48669936541339c7',
                '1d17634471f83b3988c1509c3679dcd33186568d625ea273590d26ecad961378'),
    'watcher': ('parcel-bundler/watcher', '119f1ff04bb41c2369929e37274900c61b0a9f49',
                '62b13513f5c020ebccd6a5deb14d93301f69ce36dca3b9a4c1ee0acaa6a7bb6a'),
}
LIMIT = 128 * 1024 * 1024
MEDIA_SOURCES = {
    'ffmpeg-9.0.2.tar.xz': ('https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz',
                          '8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e'),
    'zlib-1.3.2.tar.gz': ('https://zlib.net/fossils/zlib-1.3.2.tar.gz',
                        'bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect_archive(data, expected, depth=0):
    if depth > 2:
        raise ValueError('Candidate source nesting exceeds bound')
    if len(data) > LIMIT or digest(data) != expected:
        raise ValueError('Candidate source archive size or digest mismatch')
    notices, inputs, locks, nested = [], [], [], []
    seen, expanded = set(), 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or '\\' in member.name or member.name in seen:
                raise ValueError('Unsafe or duplicate candidate source path')
            seen.add(member.name)
            if len(seen) > 50000:
                raise ValueError('Candidate source entry count exceeds bound')
            if member.isdir():
                continue
            # No extraction is performed, including links and special objects.
            if not member.isfile():
                continue
            expanded += member.size
            if expanded > 512 * 1024 * 1024 or member.size > LIMIT:
                raise ValueError('Candidate source archive expansion exceeds bound')
            name = path.name
            notice = re.match(r'^(license|copying|notice|copyright|authors|patents)(?:$|[._-])', name, re.I)
            build = (name in {'Cargo.toml', 'Cargo.lock', 'build.zig', 'build.zig.zon', 'binding.gyp', 'package.json'}
                     or str(path).endswith('/scripts/build-ffmpeg.ts'))
            if notice or build or name == 'zig-deps.tar.gz':
                content = archive.extractfile(member).read()
                item = {'path': member.name, 'sha256': digest(content), 'bytes': len(content)}
                if notice:
                    notices.append(item)
                if build:
                    inputs.append(item)
                if name == 'Cargo.lock':
                    packages = tomllib.loads(content.decode('utf8'))['package']
                    locks.append({'path': member.name, 'scope': 'Whole lockfile, NOT enabled target/feature closure',
                                  'packages': [{k: p[k] for k in ('name', 'version', 'source', 'checksum') if k in p}
                                               for p in packages]})
                if name == 'zig-deps.tar.gz':
                    nested.append({'path': member.name, 'sha256': digest(content),
                                   'evidence': inspect_archive(content, digest(content), depth + 1)})
    return {'noticeFilesByName': notices, 'buildInputs': inputs, 'lockfiles': locks, 'nestedArchives': nested}


def collect(stage):
    stage = Path(stage)
    evidence = stage / 'native-source-evidence'
    evidence.mkdir(exist_ok=False)
    rows = []
    for name, (repo, commit, expected) in SOURCES.items():
        url = f'https://codeload.github.com/{repo}/tar.gz/{commit}'
        with urllib.request.urlopen(url, timeout=90) as response:
            data = response.read(LIMIT + 1)
        review = inspect_archive(data, expected)
        filename = f'{name}-{commit}.tar.gz'
        (evidence / filename).write_bytes(data)
        rows.append({'name': name, 'repository': repo, 'commit': commit, 'url': url,
                     'archive': filename, 'sha256': expected, 'evidence': review,
                     'status': 'blocked-build-correspondence-and-transitive-review'})
    media = []
    for filename, (url, expected) in MEDIA_SOURCES.items():
        with urllib.request.urlopen(url, timeout=90) as response:
            data = response.read(LIMIT + 1)
        review = inspect_archive(data, expected)
        (evidence / filename).write_bytes(data)
        media.append({'archive': filename, 'url': url, 'sha256': expected, 'evidence': review,
                      'status': 'blocked-actual-binary-correspondence-and-relinking'})
    (stage / 'native-source-review.json').write_text(json.dumps({
        'redistributionApproved': False,
        'scope': 'Four candidate source repositories linked by exact npm version gitHead; excludes Bun/JS/Web closure',
        'limitations': ['Archive digest is pinned, not proof of binary correspondence',
                        'Notice filename search is not exhaustive per-source copyright review',
                        'Lockfiles include inactive targets/features; no target closure claim',
                        'LGPL corresponding-source, relinking and replacement obligations remain open'],
        'sources': rows, 'opentuiStaticMediaSources': media}, indent=2) + '\n', encoding='utf8')
    print('Four pinned candidate source archives and FFmpeg/zlib collected; redistribution remains BLOCKED')


if __name__ == '__main__':
    collect(sys.argv[1])
