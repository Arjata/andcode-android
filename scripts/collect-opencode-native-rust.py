"""Candidate target/feature Rust sources, never npm ELF or redistribution approval."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tomllib
import urllib.request

spec = importlib.util.spec_from_file_location('source_evidence', Path(__file__).with_name('collect-opencode-native-sources.py'))
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)
TARGET = 'aarch64-unknown-linux-gnu'
CANDIDATES = {
    'bun-pty': ('rust-pty/Cargo.toml', 'rust-pty/Cargo.lock', []),
    'fff': ('Cargo.toml', 'Cargo.lock', ['-p', 'fff-c', '--no-default-features', '--features', 'zlob']),
}
REVIEW_TOPICS = {
    'libgit2-sys': 'Embedded libgit2 COPYING is GPL-2.0 with linking exception; audit actual static inputs and source obligations',
    'lmdb-master-sys': 'Embedded LMDB LICENSE is OpenLDAP Public License 2.8, not wrapper crate Apache-2.0',
    'option-ext': 'MPL-2.0 per-file obligations require review',
    'zlob': 'Embedded Zig sources/build and missing separate notice filename require review',
}
SUPPLEMENTAL_NOTICES = {
    ('heed', '0.22.0'): ('Kerollmops/heed', 'bc9cf18f6c3543fd492920c9c84bdebb4cdfb057',
                         '6d4e3db586416994db32596f0a256eaeee6c3f79e783bf6ac0fab3cc2e36759b'),
    ('heed-traits', '0.20.0'): ('Kerollmops/heed', '9de8469341cafcd5f239317fff85db955103fcd9',
                                'c4ea684839984235efcebff570a4d253dcc456789edbd4fdf3e96ca15004e730'),
    ('heed-types', '0.21.0'): ('Kerollmops/heed', '178c53261595880bb89554bc7f1b55dcda45ae50',
                               'c4ea684839984235efcebff570a4d253dcc456789edbd4fdf3e96ca15004e730'),
    ('zlob', '1.6.3'): ('dmtrKovalenko/zlob', '4bc4da2cbc823d3911b4a1436448687c398977dd',
                        'b58a537ce812184628abbf3283377f7d2447ef8c9940699f72a73d4edd9633b3'),
}
SERIAL_SOURCE = ('7ed6540c2789b7c7365cd7a89fcb7bac7c567de8',
                 'c8ff1c33d84c0b8a6ee461bcf00d60ec14639856dcd21a14ce29ec5d215b1797',
                 '871afd9d691846de71e0b83812ba9c7ff00bc7b3ad102dedcaa109f2246d52ad')


def selected_packages(tree, lock):
    packages = {(p['name'], p['version']): p for p in lock['package']}
    if len(packages) != len(lock['package']):
        raise ValueError('Ambiguous package identity in pinned lockfile')
    selected = set()
    for line in tree.splitlines():
        match = re.match(r'^([A-Za-z0-9_-]+) v([^\s|]+)(?:[\s|]|$)', line)
        if not match:
            raise ValueError('Unrecognized cargo tree package line')
        key = match.groups()
        if key not in packages:
            raise ValueError('Cargo tree package absent from pinned lockfile')
        selected.add(key)
    if not selected:
        raise ValueError('Empty candidate Cargo graph')
    return [packages[key] for key in sorted(selected)]


def unpack_candidate(archive, expected, destination):
    data = archive.read_bytes()
    sources.inspect_archive(data, expected)
    roots = set()
    with tarfile.open(fileobj=io.BytesIO(data)) as src:
        for member in src:
            path = PurePosixPath(member.name)
            roots.add(path.parts[0])
            # Do not materialize symlinks, hardlinks or special files.
            if member.isfile():
                output = destination.joinpath(*path.parts)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(src.extractfile(member).read())
    if len(roots) != 1:
        raise ValueError('Candidate archive must have one root')
    return destination / roots.pop()


def validate_vcs(data, commit):
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        matches = [m for m in archive if m.isfile() and m.name.endswith('/.cargo_vcs_info.json')]
        if len(matches) != 1 or matches[0].size > 65536:
            raise ValueError('Missing or ambiguous crate VCS evidence')
        info = json.loads(archive.extractfile(matches[0]).read())
        if info.get('git', {}).get('sha1') != commit:
            raise ValueError('Supplemental notice commit does not match crate VCS evidence')


def match_serial_source(crate, upstream):
    """serial predates Cargo VCS metadata; require all crate file bytes to match."""
    commit, checksum, license_checksum = SERIAL_SOURCE
    sources.inspect_archive(upstream, checksum)
    def files(data, allow_repository_links=False):
        result = {}
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for member in archive:
                if member.isfile():
                    name = member.name.partition('/')[2]
                    if not name or name in result:
                        raise ValueError('Ambiguous serial source path')
                    result[name] = archive.extractfile(member).read()
                elif member.issym() and allow_repository_links:
                    # Only root regular LICENSE is consumed; do not resolve the
                    # other serial-* crates' ../LICENSE links or materialize them.
                    continue
                elif not member.isdir():
                    raise ValueError('Unexpected serial source link or special entry')
        return result
    packaged, repository = files(crate), files(upstream, allow_repository_links=True)
    if not packaged or any(repository.get('serial/' + path) != content for path, content in packaged.items()):
        raise ValueError('serial crate files differ from fixed upstream source')
    notice = repository.get('LICENSE', b'')
    if sources.digest(notice) != license_checksum:
        raise ValueError('serial supplemental license checksum mismatch')
    return notice, sorted(packaged)


def collect(stage):
    stage = Path(stage).resolve(strict=True)
    evidence = stage / 'native-rust-evidence'
    evidence.mkdir(exist_ok=False)
    rows = []
    env = dict(os.environ, CARGO_TERM_COLOR='never')
    for name, (manifest, lockfile, flags) in CANDIDATES.items():
        _, source_commit, expected = sources.SOURCES[name]
        root = unpack_candidate(stage / 'native-source-evidence' / f'{name}-{source_commit}.tar.gz',
                                expected, evidence / 'candidates')
        lockpath = root / lockfile
        original = lockpath.read_bytes()
        command = ['cargo', 'tree', '--locked', '--manifest-path', str(root / manifest),
                   '--target', TARGET, '--edges', 'normal,build', '--prefix', 'none',
                   '--format', '{p}|{l}|{f}', *flags]
        tree = subprocess.check_output(command, text=True, env=env, timeout=300)
        if lockpath.read_bytes() != original:
            raise ValueError('Cargo mutated pinned lockfile')
        (evidence / f'{name}-tree.txt').write_text(tree, encoding='utf8')
        packages = []
        for package in selected_packages(tree, tomllib.loads(original.decode())):
            row = dict(package)
            row['status'] = 'blocked-binary-correspondence-and-per-file-review'
            if package['name'] in REVIEW_TOPICS:
                row['reviewTopic'] = REVIEW_TOPICS[package['name']]
            if package.get('source'):
                if package['source'] != 'registry+https://github.com/rust-lang/crates.io-index':
                    raise ValueError('Unsupported non-crates.io dependency source')
                checksum = package.get('checksum', '')
                if not re.fullmatch('[0-9a-f]{64}', checksum):
                    raise ValueError('Registry dependency lacks pinned checksum')
                filename = f"{package['name']}-{package['version']}.crate"
                archive = evidence / filename
                if archive.exists():
                    data = archive.read_bytes()
                else:
                    url = f"https://static.crates.io/crates/{package['name']}/{filename}"
                    with urllib.request.urlopen(url, timeout=90) as response:
                        data = response.read(sources.LIMIT + 1)
                row['evidence'] = sources.inspect_archive(data, checksum)
                if not row['evidence']['noticeFilesByName']:
                    row['status'] = 'blocked-no-notice-filename-found'
                supplement = SUPPLEMENTAL_NOTICES.get((package['name'], package['version']))
                if supplement:
                    repo, commit, expected_notice = supplement
                    validate_vcs(data, commit)
                    url = f'https://raw.githubusercontent.com/{repo}/{commit}/LICENSE'
                    with urllib.request.urlopen(url, timeout=90) as response:
                        notice = response.read(1024 * 1024 + 1)
                    if len(notice) > 1024 * 1024 or sources.digest(notice) != expected_notice:
                        raise ValueError('Supplemental notice size or checksum mismatch')
                    notice_name = filename + '.upstream-LICENSE'
                    (evidence / notice_name).write_bytes(notice)
                    row['supplementalNotice'] = {'url': url, 'commit': commit,
                                                 'sha256': expected_notice, 'file': notice_name,
                                                 'status': 'candidate-not-binary-or-per-file-approval'}
                if (package['name'], package['version']) == ('serial', '0.4.0'):
                    commit, source_sha, notice_sha = SERIAL_SOURCE
                    url = f'https://codeload.github.com/dcuddeback/serial-rs/tar.gz/{commit}'
                    with urllib.request.urlopen(url, timeout=90) as response:
                        repository = response.read(sources.LIMIT + 1)
                    notice, matched = match_serial_source(data, repository)
                    source_name = f'serial-rs-{commit}.tar.gz'
                    (evidence / source_name).write_bytes(repository)
                    notice_name = filename + '.upstream-LICENSE'
                    (evidence / notice_name).write_bytes(notice)
                    row['supplementalNotice'] = {'url': url, 'commit': commit, 'sha256': notice_sha,
                                                 'file': notice_name, 'sourceArchive': source_name,
                                                 'sourceArchiveSha256': source_sha, 'matchedCrateFiles': matched,
                                                 'status': 'crate-files-match-not-binary-approval'}
                archive.write_bytes(data)
                row['archive'] = filename
            packages.append(row)
        rows.append({'name': name, 'sourceCommit': source_commit, 'target': TARGET,
                     'cargoFlags': flags, 'lockSha256': hashlib.sha256(original).hexdigest(),
                     'tree': f'{name}-tree.txt', 'packages': packages})
    (stage / 'native-rust-review.json').write_text(json.dumps({
        'redistributionApproved': False, 'binaryCorrespondenceProven': False,
        'cargoVersion': subprocess.check_output(['cargo', '--version'], text=True).strip(),
        'rustcVersion': subprocess.check_output(['rustc', '-vV'], text=True).strip(),
        'scope': 'Candidate release target/feature normal+build graph; no compilation or build.rs execution',
        'limitations': ['Not proof of npm ELF build inputs, linked code or enabled binary features',
                        'Host build/proc-macro graph depends on Cargo execution host',
                        'Crate notice filename scan is not a per-file or nested C/Zig license audit',
                        'Rust standard library and native build tool/source closure not included'],
        'candidates': rows}, indent=2) + '\n', encoding='utf8')
    print('Candidate Rust target/feature evidence collected; redistribution remains BLOCKED')


if __name__ == '__main__':
    collect(sys.argv[1])
