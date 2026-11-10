"""Fresh modified media source-rule diagnostic; never replace baseline inputs."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile

spec = importlib.util.spec_from_file_location('media_build', Path(__file__).with_name('build-opencode-native-opentui.py'))
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_archive_source(archive, source):
    expected, seen = {}, set()
    with tarfile.open(archive) as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or '..' in path.parts or '\\' in member.name
                    or not path.parts or path.parts[0] != source.name
                    or path.as_posix() in seen):
                raise ValueError('Unsafe modified media archive member')
            seen.add(path.as_posix())
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('Non-regular modified media archive member')
            expected[PurePosixPath(*path.parts[1:]).as_posix()] = hashlib.sha256(tar.extractfile(member).read()).hexdigest()
    actual = {}
    for path in source.rglob('*'):
        if path.is_symlink() or (not path.is_dir() and not path.is_file()):
            raise ValueError('Unexpected pristine media source entry')
        if path.is_file():
            actual[path.relative_to(source).as_posix()] = digest(path)
    if not expected or actual != expected:
        raise ValueError('Pristine media source differs from fixed archive')


def copy_source(source, destination, protected):
    destination.mkdir(exist_ok=False)
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('Unexpected media source symlink')
        target = destination / path.relative_to(source)
        if path.is_dir():
            target.mkdir()
            continue
        if not path.is_file() or path.read_bytes().startswith(b'\x7fELF'):
            raise ValueError('Unexpected media source file')
        shutil.copyfile(path, target)
        shutil.copymode(path, target)
        protected[path] = digest(path)
        protected[target] = protected[path]


def evidence_files(directory, output):
    rows = []

    def visit(path, ancestors):
        resolved = path.resolve(strict=True)
        resolved.relative_to(directory)
        if resolved.is_dir():
            if resolved in ancestors:
                raise ValueError('Modified media output link cycle')
            for child in sorted(path.iterdir()):
                visit(child, ancestors | {resolved})
        elif resolved.is_file():
            rows.append({'path': path.relative_to(output).as_posix(),
                         'bytes': path.stat().st_size, 'sha256': digest(path)})
        else:
            raise ValueError('Unexpected modified media output file')

    visit(directory, set())
    return rows


def rebuild(native, output, env):
    native, output = Path(native).resolve(strict=True), Path(output).resolve(strict=True)
    directory = output / 'modified-media-source-rebuild'
    if directory.is_relative_to(native) or native.is_relative_to(directory):
        raise ValueError('Modified media source/output overlap')
    directory.mkdir(exist_ok=False)
    copied = directory / 'native'
    (copied / 'scripts').mkdir(parents=True)
    cache, original_cache = copied / '.cache/ffmpeg', native / '.cache/ffmpeg'
    (cache / 'sources').mkdir(parents=True)
    (cache / 'downloads').mkdir()
    protected = {}
    script = native / 'scripts/build-ffmpeg.ts'
    protected[script] = digest(script)
    copied_script = copied / 'scripts/build-ffmpeg.ts'
    shutil.copyfile(script, copied_script)
    protected[copied_script] = protected[script]
    baseline_prefix = original_cache / 'prefix/aarch64-linux'
    object_list = baseline_prefix / 'objects.txt'
    baseline_objects = object_list.read_text(encoding='utf8').splitlines()
    protected[object_list] = digest(object_list)
    for name in baseline_objects:
        relative = PurePosixPath(name)
        if (not relative.parts or relative.parts[0] != 'objects' or relative.is_absolute()
                or '..' in relative.parts or '\\' in name):
            raise ValueError('Unsafe baseline media object path')
        path = (baseline_prefix / name).resolve(strict=True)
        path.relative_to(baseline_prefix)
        protected[path] = digest(path)
    # Read only fixed archives and pristine sources. Never copy build/prefix,
    # generated headers, sampled preprocessor outputs or existing objects.
    for filename, (_, checksum) in media.pty.rust.sources.MEDIA_SOURCES.items():
        archive = original_cache / 'downloads' / filename
        if digest(archive) != checksum:
            raise ValueError('Modified media archive hash mismatch')
        protected[archive] = checksum
        destination = cache / 'downloads' / filename
        shutil.copyfile(archive, destination)
        protected[destination] = checksum
        name = filename.removesuffix('.tar.xz').removesuffix('.tar.gz')
        require_archive_source(archive, original_cache / 'sources' / name)
    for name in ['ffmpeg-9.0.2', 'zlib-1.3.2']:
        copy_source(original_cache / 'sources' / name, cache / 'sources' / name, protected)
    crc = cache / 'sources/ffmpeg-9.0.2/libavutil/crc.c'
    crc.write_bytes(media.modified_crc_source(crc.read_bytes()))
    protected[crc] = digest(crc)
    child_env = {k: v for k, v in env.items() if k not in
                 ['LD_PRELOAD', 'LD_LIBRARY_PATH', 'NODE_TLS_REJECT_UNAUTHORIZED',
                  'CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH']}
    command = ['bun', 'scripts/build-ffmpeg.ts', '--target=aarch64-linux']
    log = directory / 'build.log'
    with log.open('wb') as stream:
        subprocess.run(command, cwd=copied, env=child_env, stdout=stream,
                       stderr=subprocess.STDOUT, check=True, timeout=1800)
    text = log.read_text(encoding='utf8')
    media.verify_media_command_log(text)
    prefix = cache / 'prefix/aarch64-linux'
    objects = (prefix / 'objects.txt').read_text(encoding='utf8').splitlines()
    if (not objects or len(objects) != len(set(objects))
            or len(baseline_objects) != len(set(baseline_objects)) or set(objects) != set(baseline_objects)):
        raise ValueError('Modified media selected object set differs')
    configuration = media.ffmpeg_configuration((cache / 'build/aarch64-linux/config.h').read_text(encoding='utf8'))
    dependencies = media.ffmpeg_source_inputs(copied, prefix, objects)
    if dependencies['objectsWithoutDependencyFiles']:
        raise ValueError('Modified media missing dependency files')
    compilation = media.media_compile_commands(text, copied, prefix, objects, dependencies)
    crc_key = 'objects/libavutil/crc.o'
    crc_rows = [row for row in compilation['objects'] if row['object'] == crc_key]
    if (len(crc_rows) != 1 or crc_rows[0]['sourceSha256'] != protected[crc]
            or crc_rows[0]['source'] != 'sources/ffmpeg-9.0.2/libavutil/crc.c'):
        raise ValueError('Modified CRC source was not compiled')
    if (prefix / crc_key).read_bytes() == (original_cache / 'prefix/aarch64-linux' / crc_key).read_bytes():
        raise ValueError('Modified source-rule CRC object did not change')
    for row in compilation['objects']:
        raw = (prefix / row['object']).read_bytes()
        if (len(raw) < 64 or raw[:7] != b'\x7fELF\x02\x01\x01'
                or int.from_bytes(raw[16:18], 'little') != 1
                or int.from_bytes(raw[18:20], 'little') != 183
                or int.from_bytes(raw[20:24], 'little') != 1):
            raise ValueError('Modified media object is not AArch64 ELF64 relocatable')
    for path, checksum in protected.items():
        if digest(path) != checksum:
            raise ValueError('Modified media rebuild changed protected source')
    files = evidence_files(directory, output)
    result = {'command': command, 'cwd': str(copied), 'log': log.relative_to(output).as_posix(),
              'files': files, 'configuration': configuration, 'sourceDependencies': dependencies,
              'compileCommands': compilation, 'modifiedCrcSha256': protected[crc],
              'redistributionApproved': False, 'androidApproved': False, 'relinkingApproved': False,
              'fullCorrespondingSourceApproved': False,
              'scope': 'Fresh source-rule configure/make and all selected FFmpeg/zlib objects with modified CRC; no sampled .i reuse, final OpenTUI relink, decoder/TUI execution, original object equivalence, complete toolchain/source or legal approval'}
    (directory / 'review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print('ANDCODE_MODIFIED_MEDIA_SOURCE_RULES_OK', len(objects), 'objects (Linux CI only)')
    return result


if __name__ == '__main__':
    rebuild(sys.argv[1], sys.argv[2], os.environ)
