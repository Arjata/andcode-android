"""Linux-only isolated TUI experiments for explicitly selected media replacements."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(exe, stage, env, variant='sampled'):
    if variant not in ['sampled', 'source-rules']:
        raise ValueError('Unexpected media TUI diagnostic selector')
    stage = Path(stage).resolve(strict=True)
    exe = Path(exe).resolve(strict=True)
    native = (stage / 'native').resolve(strict=True)
    manifest = stage / 'oc2-native.tsv'
    output = stage / 'native-opentui-build'
    parent = 'modified-media-source-relink' if variant == 'source-rules' else 'media-object-relink'
    review_path = output / parent / 'review.json' if variant == 'source-rules' else stage / 'native-opentui-build-review.json'
    review = json.loads(review_path.read_text(encoding='utf8'))
    evidence = review if variant == 'source-rules' else review['mediaObjectRelink']
    if variant == 'source-rules' and any(evidence[k] is not False for k in
            ['redistributionApproved', 'androidApproved', 'relinkingApproved', 'fullCorrespondingSourceApproved']):
        raise ValueError('Unexpected source-rule TUI approval')
    replacement = output / parent / 'libopentui.so'
    rows = [line.split('\t') for line in manifest.read_text(encoding='utf8').splitlines()]
    if not rows or any(len(row) != 4 for row in rows):
        raise ValueError('Invalid native manifest')
    selected = [row for row in rows if '/@opentui/core-linux-arm64/' in row[3]]
    if len(selected) != 1 or len({row[0] for row in rows}) != len(rows):
        raise ValueError('Expected one unique OpenTUI input')
    protected = {exe: digest(exe), manifest: digest(manifest), review_path: digest(review_path)}
    for name, checksum, size, _ in rows:
        if Path(name).name != name or '\\' in name or name in ('.', '..'):
            raise ValueError('Invalid native filename')
        path = (native / name).resolve(strict=True)
        path.relative_to(native)
        if digest(path) != checksum or path.stat().st_size != int(size):
            raise ValueError('Changed baseline native input')
        protected[path] = checksum
    library_rows = [row for row in evidence['files'] if row['path'] == parent + '/libopentui.so']
    if (len(library_rows) != 1 or digest(replacement) != library_rows[0]['sha256']
            or replacement.stat().st_size != library_rows[0]['bytes']):
        raise ValueError('Changed replacement library')
    protected[replacement] = digest(replacement)
    if protected[replacement] == selected[0][1]:
        raise ValueError('Expected a changed replacement library')
    directory = output / parent / 'media-tui'
    directory.mkdir(exist_ok=False)
    copied = directory / 'native'
    copied.mkdir()
    for name, _, _, _ in rows:
        shutil.copyfile(replacement if name == selected[0][0] else native / name, copied / name)
    # This manifest is a byte-preserved lookup index for the existing probe,
    # not an asserted digest manifest for the deliberately aliased replacement.
    shutil.copyfile(manifest, directory / 'oc2-native.tsv')
    copies = {p: digest(p) for p in copied.iterdir()}
    for name in ['home', 'tmp']:
        (directory / name).mkdir()
    child_env = dict(env, ANDCODE_EXE_DIR=str(copied), HOME=str(directory / 'home'),
                     BUN_TMPDIR=str(directory / 'tmp'), TMPDIR=str(directory / 'tmp'))
    child_env.pop('LD_PRELOAD', None)
    command = [sys.executable, str(Path(__file__).with_name('probe-opencode-native-tui.py')),
               str(exe), str(directory)]
    log = directory / 'tui.log'
    try:
        done = subprocess.run(command, env=child_env, capture_output=True, timeout=50)
    except subprocess.TimeoutExpired as error:
        log.write_bytes(b'TIMEOUT\n' + (error.stdout or b'') + (error.stderr or b''))
        raise
    log.write_bytes(done.stdout + done.stderr)
    done.check_returncode()
    if b'ANDCODE_SOURCE_TUI_NATIVE_OK (Linux CI only)' not in done.stdout:
        raise ValueError('Replacement TUI gate did not complete')
    maps = (directory / 'tui-maps.txt').read_text(encoding='utf8')
    rendered = (directory / 'tui-output.bin').read_bytes()
    alias = copied / selected[0][0]
    if (str(alias) not in maps or str(native / selected[0][0]) in maps
            or b'\x1b[' not in rendered or b'opencode' not in rendered.lower()):
        raise ValueError('Replacement mapping or rendered TUI missing')
    for root in [directory / 'home', directory / 'tmp']:
        for path in root.rglob('*'):
            if path.is_symlink():
                raise ValueError('Unexpected TUI extraction symlink')
            if path.is_file():
                with path.open('rb') as stream:
                    if stream.read(4) == b'\x7fELF':
                        raise ValueError('Replacement TUI extracted ELF')
    for path, checksum in {**protected, **copies}.items():
        if digest(path) != checksum:
            raise ValueError('Replacement TUI changed a protected input')
    result = {'command': command, 'alias': alias.relative_to(output).as_posix(),
              'variant': variant, 'inputReviewSha256': protected[review_path],
              'originalSha256': selected[0][1], 'replacementSha256': protected[replacement],
              'lookupManifestIsReleaseManifest': False, 'mappedReplacement': True,
              'renderedTui': True, 'runtimeExtractedElf': False,
              'redistributionApproved': False, 'androidApproved': False, 'relinkingApproved': False,
              'files': [{'path': p.relative_to(output).as_posix(), 'bytes': p.stat().st_size,
                         'sha256': digest(p)} for p in sorted(directory.rglob('*')) if p.is_file()],
              'scope': 'Isolated replacement-library lookup alias mapped and terminal-rendered on Linux only; not decoder coverage, complete source, valid content-addressed release payload or Android/legal approval'}
    (directory / 'review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print('ANDCODE_MEDIA_REPLACEMENT_TUI_OK (Linux CI only)')
    return result


if __name__ == '__main__':
    probe(sys.argv[1], sys.argv[2], os.environ, sys.argv[3] if len(sys.argv) > 3 else 'sampled')
