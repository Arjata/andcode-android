"""Link fresh source-rule media objects into isolated OpenTUI diagnostics only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

spec = importlib.util.spec_from_file_location('media_build', Path(__file__).with_name('build-opencode-native-opentui.py'))
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def relink(output, env):
    output = Path(output).resolve(strict=True)
    source_review = output / 'modified-media-source-rebuild/review.json'
    source = json.loads(source_review.read_text(encoding='utf8'))
    baseline_review = output.parent / 'native-opentui-build-review.json'
    baseline = json.loads(baseline_review.read_text(encoding='utf8'))
    if any(source[k] is not False for k in ['redistributionApproved', 'androidApproved',
            'relinkingApproved', 'fullCorrespondingSourceApproved']):
        raise ValueError('Unexpected source-rule approval')
    protected = {source_review: digest(source_review), baseline_review: digest(baseline_review)}
    directory = output / 'modified-media-source-relink'
    directory.mkdir(exist_ok=False)
    zig = Path(shutil.which('zig') or '').resolve(strict=True)
    if digest(zig.parent.parent / 'zig.tar.xz') != media.ZIG_SHA256:
        raise ValueError('Unexpected source-relink Zig archive')
    protected[zig] = digest(zig)
    copied_prefix = output / 'modified-media-source-rebuild/native/.cache/ffmpeg/prefix/aarch64-linux'
    replacements = {}
    for row in source['files']:
        path = (output / row['path']).resolve(strict=True)
        path.relative_to(output / 'modified-media-source-rebuild')
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Fresh source-rule input changed')
        protected[path] = row['sha256']
    for row in source['compileCommands']['objects']:
        key = row['object']
        path = (copied_prefix / key).resolve(strict=True)
        path.relative_to(copied_prefix)
        if key in replacements or protected.get(path) != row['objectSha256']:
            raise ValueError('Unbound or duplicate source-rule object')
        replacements[key] = path
    link = baseline['finalLink']
    media_prefix = '.cache/ffmpeg/prefix/aarch64-linux/'
    selected = {row['scopeRelativePath'].removeprefix(media_prefix) for row in link['inputs']
        if row['scope'] == 'opentui-source-build' and row['scopeRelativePath'].startswith(media_prefix + 'objects/')}
    if not replacements or set(replacements) != selected:
        raise ValueError('Fresh source-rule final-link media set differs')
    command = [str(zig), *link['command']]
    for row in link['inputs']:
        retained = (output / row['retainedPath']).resolve(strict=True)
        retained.relative_to(output)
        if retained.stat().st_size != row['bytes'] or digest(retained) != row['sha256']:
            raise ValueError('Retained non-media baseline input changed')
        protected[retained] = row['sha256']
        index = row['argumentIndex'] + 1
        if command[index] != row['path']:
            raise ValueError('Unexpected final-link argument binding')
        key = row['scopeRelativePath'].removeprefix(media_prefix)
        use_fresh = row['scope'] == 'opentui-source-build' and key in replacements
        command[index] = str(replacements[key] if use_fresh else retained)
    binary = directory / 'libopentui.so'
    command[link['command'].index('-o') + 2] = str(binary)
    command.extend(['--Map=' + str(directory / 'link.map'),
                    '--why-extract=' + str(directory / 'archive-extraction.tsv')])
    commands = []

    def run(args, name, timeout):
        commands.append({'command': args, 'log': name})
        log = directory / name
        try:
            done = subprocess.run(args, env=env, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            log.write_bytes((shlex.join(args) + '\nTIMEOUT\n').encode()
                            + (error.stdout or b'') + (error.stderr or b''))
            raise
        log.write_bytes((shlex.join(args) + '\n').encode() + done.stdout + done.stderr)
        done.check_returncode()
        return done.stdout

    run(command, 'link.log', 120)
    for name in ['link.map', 'archive-extraction.tsv']:
        if not (directory / name).is_file() or not (directory / name).stat().st_size:
            raise ValueError('Missing fresh source-relink map/extraction evidence')
    mapping = (directory / 'link.map').read_text(encoding='utf8')
    if any(str(path) not in mapping for path in replacements.values()):
        raise ValueError('Fresh source-rule object absent from linker map')
    if not (directory / 'archive-extraction.tsv').read_bytes().startswith(b'reference\textracted\tsymbol\n'):
        raise ValueError('Unexpected fresh source-relink archive extraction report')
    _, needed = media.pty.audit.elf(binary.read_bytes())
    if sorted(needed) != sorted(baseline['needed']):
        raise ValueError('Fresh source-relink dependency closure changed')
    probe = output / 'probe.mjs'
    protected[probe] = digest(probe)
    if media.MARKER.encode() not in run(['bun', str(probe), str(binary)], 'abi.log', 30):
        raise ValueError('Fresh source-relink ABI marker missing')
    prior = output / 'modified-crc-relink'
    probe_source = prior / 'crc-probe.c'
    protected[probe_source] = digest(probe_source)
    probe_commands = baseline['modifiedCrcRelink']['probeCommands']
    if len(probe_commands) != 2 or probe_commands[1] != [str(prior / 'crc-probe')]:
        raise ValueError('Unexpected baseline CRC probe command shape')
    compile_command = list(probe_commands[0])
    for i, arg in enumerate(compile_command):
        if arg == str(prior / 'libopentui.so'): compile_command[i] = str(binary)
        elif arg == '-Wl,-rpath,' + str(prior): compile_command[i] = '-Wl,-rpath,' + str(directory)
        elif arg == str(prior / 'crc-probe'): compile_command[i] = str(directory / 'crc-probe')
    run(compile_command, 'crc-compile.log', 60)
    media.pty.audit.elf((directory / 'crc-probe').read_bytes())
    stdout = run([str(directory / 'crc-probe')], 'crc-run.log', 60)
    if (b'ANDCODE_SOURCE_FFMPEG_CRC_OK 2304 cases (Linux only)' not in stdout
            or b'ANDCODE_MODIFIED_CRC_RELINK_OK 6912 calls (Linux only)' not in stdout):
        raise ValueError('Fresh source-relink CRC execution failed')
    for path, expected in protected.items():
        if digest(path) != expected:
            raise ValueError('Fresh source-relink changed protected inputs')
    result = {'sourceReviewSha256': protected[source_review], 'baselineReviewSha256': protected[baseline_review],
              'replacedObjects': len(replacements), 'inputCount': len(link['inputs']), 'needed': needed,
              'commands': commands, 'crcCases': 2304, 'modifiedCalls': 6912,
              'files': [{'path': path.relative_to(output).as_posix(), 'bytes': path.stat().st_size,
                         'sha256': digest(path)} for path in sorted(directory.iterdir()) if path.is_file()],
              'redistributionApproved': False, 'androidApproved': False, 'relinkingApproved': False,
              'fullCorrespondingSourceApproved': False,
              'scope': 'Retained non-media objects plus all fresh modified media source-rule objects; Linux ABI/CRC execution only, not original object equivalence, decoder/TUI, full source/toolchain or legal/Android approval'}
    (directory / 'review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print('ANDCODE_MODIFIED_MEDIA_SOURCE_RELINK_OK', len(replacements), 'objects (Linux CI only)')
    return result


if __name__ == '__main__': relink(sys.argv[1], os.environ)
