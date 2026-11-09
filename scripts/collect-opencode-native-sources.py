"""Pinned candidate-source evidence; NOT binary reproducibility or license approval."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import time
import tomllib
import urllib.error
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
BUN_COMMIT = '38afee6c84fcf48c0edb2466aa4b27d287a59c30'
WEBKIT_COMMIT = 'd6375c72affe0f70222cdcb45012b10f0bf3a9d5'
RUNTIME_DECLARATIONS = {
    'bun': ('oven-sh/bun', BUN_COMMIT, {
        'LICENSE.md': '362fe32c954ec829240bd7429c53d705eef08c6bfa45ffc2d02005f857cba4dd',
        'scripts/build/deps/webkit.ts': 'e801ac2b2c0b83767a10e4bf673addda60ff1c4e64d1246c0e442ce22b3c5059',
        'package.json': '68f7347c90102f4d394f9188fde96afc882cdb8871321d3ed13678002eaa3b35',
    }),
    'webkit': ('oven-sh/WebKit', WEBKIT_COMMIT, {
        'Source/JavaScriptCore/COPYING.LIB': '5094ecb9c9dcd0eadc34f3c11511d9b5535063032bc150164ecd1a5d5a445547',
        'Source/JavaScriptCore/CMakeLists.txt': 'f9899a7939def67e3cde4e500e96ea13cfc877737e85ee792ee760a5253beb19',
        'CMakeLists.txt': '95f5a87e9572f7efca4dc4b456c8180b5a03dd13295b1ca8440af4feeddc237e',
    }),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def download_archive(url):
    """Bounded transport retry only; archive trust checks always run afterwards."""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=90) as response:
                return response.read(LIMIT + 1)
        except urllib.error.HTTPError as error:
            if error.code not in {408, 429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (TimeoutError, ConnectionError):
            if attempt == 2:
                raise
        except urllib.error.URLError as error:
            if not isinstance(error.reason, (TimeoutError, ConnectionError)) or attempt == 2:
                raise
        time.sleep(2 * (attempt + 1))


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
            build = (name in {'Cargo.toml', 'Cargo.lock', 'build.rs', '.cargo_vcs_info.json',
                              'build.zig', 'build.zig.zon', 'binding.gyp', 'package.json'}
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
        data = download_archive(url)
        review = inspect_archive(data, expected)
        filename = f'{name}-{commit}.tar.gz'
        (evidence / filename).write_bytes(data)
        rows.append({'name': name, 'repository': repo, 'commit': commit, 'url': url,
                     'archive': filename, 'sha256': expected, 'evidence': review,
                     'status': 'blocked-build-correspondence-and-transitive-review'})
    media = []
    for filename, (url, expected) in MEDIA_SOURCES.items():
        data = download_archive(url)
        review = inspect_archive(data, expected)
        (evidence / filename).write_bytes(data)
        media.append({'archive': filename, 'url': url, 'sha256': expected, 'evidence': review,
                      'status': 'blocked-actual-binary-correspondence-and-relinking'})
    runtime = collect_runtime_declarations(evidence)
    (stage / 'native-source-review.json').write_text(json.dumps({
        'redistributionApproved': False,
        'scope': 'Four candidate source repositories plus selected Bun/WebKit declarations; excludes complete Bun/JS/Web closure',
        'limitations': ['Archive digest is pinned, not proof of binary correspondence',
                        'Notice filename search is not exhaustive per-source copyright review',
                        'Lockfiles include inactive targets/features; no target closure claim',
                        'LGPL corresponding-source, relinking and replacement obligations remain open'],
        'sources': rows, 'opentuiStaticMediaSources': media,
        'runtimeDeclarations': runtime}, indent=2) + '\n', encoding='utf8')
    print('Four pinned candidate source archives and FFmpeg/zlib collected; redistribution remains BLOCKED')


def collect_runtime_declarations(evidence):
    """Selected fixed-source bytes only, deliberately not full corresponding source."""
    directory = evidence / 'runtime-declarations'
    directory.mkdir(exist_ok=False)
    rows = []
    for name, (repo, commit, files) in RUNTIME_DECLARATIONS.items():
        for relative, expected in files.items():
            path = PurePosixPath(relative)
            if path.is_absolute() or '..' in path.parts or '\\' in relative:
                raise ValueError('Unsafe runtime declaration path')
            url = f'https://raw.githubusercontent.com/{repo}/{commit}/{relative}'
            data = download_archive(url)
            if len(data) > 1024 * 1024 or digest(data) != expected:
                raise ValueError('Runtime declaration size or digest mismatch')
            if name == 'bun' and relative == 'scripts/build/deps/webkit.ts':
                pins = re.findall(rb'^export const WEBKIT_VERSION = "([0-9a-f]{40})";', data, re.M)
                if pins != [WEBKIT_COMMIT.encode()]:
                    raise ValueError('Fixed Bun WebKit source pin changed')
            dest = directory / name / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            rows.append({'component': name, 'repository': repo, 'commit': commit,
                         'path': relative, 'url': url, 'bytes': len(data), 'sha256': expected,
                         'retainedPath': dest.relative_to(evidence).as_posix()})
    return {'files': rows, 'redistributionApproved': False, 'correspondingSourceComplete': False,
            'relinkingApproved': False,
            'scope': 'Selected pinned declarations and build files, not complete source or binary correspondence'}


if __name__ == '__main__':
    collect(sys.argv[1])
