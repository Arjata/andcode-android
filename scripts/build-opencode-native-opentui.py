"""Fixed-source OpenTUI diagnostic rebuild, never license or Android approval."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile

spec = importlib.util.spec_from_file_location('pty_build', Path(__file__).with_name('build-opencode-native-pty.py'))
pty = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pty)
ORIGINAL = '3d733490879955965a67a16364e50fe724d9fec63731e97fa6855285c3db70f2'
ZIG_SHA256 = '9e8d11661d4ae3bd57702a3832781e23ad151dde5798e16a5ccd503f65234ff8'
MARKER = 'ANDCODE_SOURCE_OPENTUI_ABI_OK'
PROBE = '''import {dlopen,FFIType as T} from "bun:ffi";
import {readFile,realpath} from "node:fs/promises";
const lib=dlopen(process.argv[2],{ot_context_abi_version:{args:[],returns:T.u32}});
try{
 if(lib.symbols.ot_context_abi_version()!==2)throw new Error("Wrong OpenTUI ABI");
 const maps=await readFile("/proc/self/maps","utf8");
 if(!maps.includes(await realpath(process.argv[2])))throw new Error("Wrong OpenTUI mapping");
 console.log("ANDCODE_SOURCE_OPENTUI_ABI_OK");
}finally{lib.close()}
'''


def patch_once(text, anchor, replacement):
    if text.count(anchor) != 1:
        raise ValueError('Fixed OpenTUI source anchor changed')
    return text.replace(anchor, replacement)


def patch_build(text):
    if 'andcode-library-only' in text or 'shared.link_z_max_page_size = 16384;' in text:
        raise ValueError('OpenTUI source is already patched')
    text = patch_once(text,
        '    if (target.result.os.tag == .linux and optimize != .debug) shared.build_id = .sha1;',
        '    shared.link_z_max_page_size = 16384;\n'
        '    shared.verbose_link = true;\n'
        '    if (target.result.os.tag == .linux and optimize != .debug) shared.build_id = .sha1;')
    return patch_once(text, '    // Test step (native only)',
        '    // andcode: do not configure unrelated musl test/bench artifacts.\n'
        '    if (b.option(bool, "andcode-library-only", "Configure explicit library target only") orelse false) {\n'
        '        if (target_option == null) @panic("andcode-library-only requires library-target");\n'
        '        return;\n'
        '    }\n\n'
        '    // Test step (native only)')


def unpack_nested(data, destination):
    """Fixed nested sources only: reject links, traversal, duplicates and huge input."""
    seen, expanded = set(), 0
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            normalized = path.as_posix()
            if (path.is_absolute() or '..' in path.parts or '\\' in member.name
                    or not path.parts or normalized in seen):
                raise ValueError('Unsafe nested Zig source path')
            seen.add(normalized)
            expanded += member.size
            if len(seen) > 10000 or expanded > 128 * 1024 * 1024:
                raise ValueError('Nested Zig sources exceed bounds')
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('Nested Zig source link or special entry')
            output = destination.joinpath(*path.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.extractfile(member).read())


def ffmpeg_configuration(text):
    """Reject license/configuration drift, not a replacement for per-file review."""
    definitions = {}
    for name, value in re.findall(r'^#define\s+(\w+)\s+([^\r\n]+)', text, re.M):
        if name in definitions:
            raise ValueError('Duplicate FFmpeg configuration macro: ' + name)
        definitions[name] = value.strip()
    expected = {'FFMPEG_LICENSE': '"LGPL version 2.1 or later"',
                'CONFIG_GPL': '0', 'CONFIG_VERSION3': '0', 'CONFIG_NONFREE': '0',
                'CONFIG_NETWORK': '0', 'CONFIG_ZLIB': '1'}
    for name, value in expected.items():
        if definitions.get(name) != value:
            raise ValueError('Unexpected FFmpeg configuration: ' + name)
    return expected


def validate(result, target, output, env):
    payload = result.read_bytes()
    _, needed = pty.audit.elf(payload)
    allowed = {'libc.so.6', 'libm.so.6', 'libdl.so.2', 'libpthread.so.0', 'librt.so.1',
               'libgcc_s.so.1', 'ld-linux-aarch64.so.1'}
    if not needed or set(needed) - allowed:
        raise ValueError('Unexpected rebuilt OpenTUI dependency closure: ' + repr(needed))
    symbols = subprocess.check_output(['readelf', '--dyn-syms', '--wide', str(result)], text=True)
    exports = {line.split()[-1] for line in symbols.splitlines() if line.split() and ' UND ' not in line}
    if {'ot_context_abi_version', 'ot_context_create', 'ot_context_destroy', 'ot_video_open'} - exports:
        raise ValueError('Missing rebuilt OpenTUI exports')
    probe = output / 'probe.mjs'
    probe.write_text(PROBE, encoding='utf8')
    done = subprocess.run(['bun', str(probe), str(result)], env=env, capture_output=True,
                          text=True, timeout=30)
    (output / 'abi.log').write_text(done.stdout + done.stderr, encoding='utf8')
    done.check_returncode()
    if MARKER not in done.stdout:
        raise ValueError('OpenTUI ABI probe did not complete')
    # Later full experiment requires actual staged-library TUI rendering too.
    shutil.copyfile(result, target)
    return needed


def build(upstream, stage):
    if sys.platform != 'linux' or platform.machine() not in ('aarch64', 'arm64'):
        raise ValueError('OpenTUI rebuild requires native Linux arm64 CI')
    upstream, stage = Path(upstream).resolve(strict=True), Path(stage).resolve(strict=True)
    matches = list((upstream / 'node_modules/.bun').glob(
        '@opentui+core-linux-arm64@0.8.1*/node_modules/@opentui/core-linux-arm64/libopentui.so'))
    if len(matches) != 1:
        raise ValueError('Expected one fixed OpenTUI glibc input')
    target = matches[0].resolve(strict=True)
    target.relative_to(upstream)
    if hashlib.sha256(target.read_bytes()).hexdigest() != ORIGINAL:
        raise ValueError('Unexpected original OpenTUI input')
    output = stage / 'native-opentui-build'
    output.mkdir(exist_ok=False)
    zig = Path(shutil.which('zig') or '').resolve(strict=True)
    if hashlib.sha256((zig.parent.parent / 'zig.tar.xz').read_bytes()).hexdigest() != ZIG_SHA256:
        raise ValueError('Unexpected fixed OpenTUI Zig archive')
    if subprocess.check_output([str(zig), 'version'], text=True).strip() != '0.17.0':
        raise ValueError('Expected Zig 0.17.0')
    repo, commit, expected = pty.rust.sources.SOURCES['opentui']
    data = pty.rust.sources.download_archive(f'https://codeload.github.com/{repo}/tar.gz/{commit}')
    pty.rust.sources.inspect_archive(data, expected)
    archive = output / f'opentui-{commit}.tar.gz'
    archive.write_bytes(data)
    root = pty.rust.unpack_candidate(archive, expected, output / 'source')
    native = root / 'packages/native'
    nested = native / 'src/vendor/zig-deps.tar.gz'
    unpack_nested(nested.read_bytes(), native / 'zig-deps')
    build_file = native / 'build.zig'
    original_build = build_file.read_text(encoding='utf8')
    build_file.write_text(patch_build(original_build), encoding='utf8')
    (output / 'original-build.zig').write_text(original_build, encoding='utf8')
    ffmpeg_script = native / 'scripts/build-ffmpeg.ts'
    original_script = ffmpeg_script.read_text(encoding='utf8')
    # aarch64 does not use NASM. Avoid downloading an unused x86 build tool.
    ffmpeg_script.write_text(patch_once(original_script,
        '  await download(NASM_URL, nasmArchive, NASM_SHA256, "NASM")',
        '  // andcode aarch64-only experiment: no x86 NASM download'), encoding='utf8')
    (output / 'original-build-ffmpeg.ts').write_text(original_script, encoding='utf8')
    downloads = native / '.cache/ffmpeg/downloads'
    downloads.mkdir(parents=True)
    for filename, (url, checksum) in pty.rust.sources.MEDIA_SOURCES.items():
        content = pty.rust.sources.download_archive(url)
        pty.rust.sources.inspect_archive(content, checksum)
        (downloads / filename).write_bytes(content)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('ZIG_', 'CARGO_', 'RUST'))
           and k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'NODE_TLS_REJECT_UNAUTHORIZED')}
    env['ZIG_GLOBAL_CACHE_DIR'] = str(stage.parent / 'opentui-zig-cache')
    env['ZIG_LOCAL_CACHE_DIR'] = str(stage.parent / 'opentui-zig-local-cache')
    commands = [['bun', 'scripts/build-ffmpeg.ts', '--target=aarch64-linux'],
                [str(zig), 'build', '-Doptimize=ReleaseFast', '-Dlibrary-target=aarch64-linux-gnu.2.17',
                 '-Drequire-video=true', '-Dandcode-library-only=true', '-j2', '--summary', 'all']]
    for index, command in enumerate(commands):
        logpath = output / f'command-{index}.log'
        try:
            with logpath.open('w', encoding='utf8') as log:
                subprocess.run(command, cwd=native, env=env, stdout=log, stderr=subprocess.STDOUT,
                               check=True, timeout=1800)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print(logpath.read_text(encoding='utf8')[-14000:], file=sys.stderr)
            raise
    prefix = native / '.cache/ffmpeg/prefix/aarch64-linux'
    objects = (prefix / 'objects.txt').read_text().splitlines()
    object_rows = []
    for item in objects:
        path = (prefix / item).resolve(strict=True)
        path.relative_to(prefix)
        object_rows.append({'path': item, 'bytes': path.stat().st_size,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    if not object_rows:
        raise ValueError('Empty FFmpeg object list')
    for name in ['config.h', 'ffbuild/config.mak', 'ffbuild/config.log']:
        source = native / '.cache/ffmpeg/build/aarch64-linux' / name
        dest = output / 'ffmpeg-config' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    configuration = ffmpeg_configuration((output / 'ffmpeg-config/config.h').read_text(encoding='utf8'))
    result = native / 'lib/aarch64-linux/libopentui.so'
    shutil.copyfile(result, output / 'libopentui.so')
    needed = validate(result, target, output, env)
    (stage / 'native-opentui-build-review.json').write_text(json.dumps({
        'redistributionApproved': False, 'androidApproved': False,
        'originalNpmBinaryCorrespondenceProven': False,
        'scope': 'Fixed-source diagnostic rebuild; later full staged TUI gate required',
        'sourceCommit': commit, 'archiveSha256': expected,
        'originalNpmSha256': ORIGINAL, 'rebuiltSha256': hashlib.sha256(result.read_bytes()).hexdigest(),
        'installedInput': str(target.relative_to(upstream)), 'needed': needed, 'commands': commands,
        'zigVersion': '0.17.0', 'zigArchiveSha256': ZIG_SHA256,
        'nestedZigArchiveSha256': hashlib.sha256(nested.read_bytes()).hexdigest(),
        'ffmpegObjects': object_rows, 'ffmpegConfiguration': configuration, 'abiGate': MARKER,
        'limitations': ['FFmpeg objects and build tree retained, not complete LGPL relinking approval',
                        'No complete linker input attribution or toolchain corresponding source',
                        'Per-file notices, Bun/JSC obligations and Android remain under review']
    }, indent=2) + '\n', encoding='utf8')
    print('Fixed-source OpenTUI ABI passed; redistribution remains BLOCKED')


if __name__ == '__main__':
    build(*sys.argv[1:])
