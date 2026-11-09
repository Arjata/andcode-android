"""Fixed-source OpenTUI diagnostic rebuild, never license or Android approval."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
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
CRC_MARKER = 'ANDCODE_SOURCE_FFMPEG_CRC_OK'
CRC_PROBE = r'''/* andcode-owned bitwise CRC reference, not copied FFmpeg implementation. */
#include <stdint.h>
#include <stdio.h>
#include <libavutil/crc.h>

static uint32_t swap32(uint32_t value) {
    return ((value & 255) << 24) | ((value & 65280) << 8)
         | ((value >> 8) & 65280) | (value >> 24);
}

static uint32_t reference(const uint8_t *data, size_t size, uint32_t seed,
                          unsigned bits, uint32_t polynomial, int little) {
    uint32_t mask = UINT32_MAX >> (32 - bits);
    uint32_t crc = seed & mask;
    for (size_t i = 0; i < size; ++i) {
        crc ^= (uint32_t)data[i] << (little ? 0 : bits - 8);
        for (unsigned bit = 0; bit < 8; ++bit) {
            if (little) crc = (crc >> 1) ^ ((crc & 1) ? polynomial : 0);
            else crc = ((crc << 1) ^ ((crc & (UINT32_C(1) << (bits - 1))) ? polynomial : 0)) & mask;
        }
    }
    return little ? crc : swap32(crc << (32 - bits));
}

int main(void) {
    static const struct { AVCRCId id; unsigned bits; uint32_t poly; int little; } specs[] = {
        { AV_CRC_8_ATM, 8, 0x07, 0 }, { AV_CRC_8_EBU, 8, 0x1d, 0 },
        { AV_CRC_16_ANSI, 16, 0x8005, 0 }, { AV_CRC_16_ANSI_LE, 16, 0xa001, 1 },
        { AV_CRC_16_CCITT, 16, 0x1021, 0 }, { AV_CRC_24_IEEE, 24, 0x864cfb, 0 },
        { AV_CRC_32_IEEE, 32, 0x04c11db7, 0 }, { AV_CRC_32_IEEE_LE, 32, 0xedb88320, 1 }
    };
    static const size_t lengths[] = { 0, 1, 7, 32, 1999, 4096 };
    uint8_t data[4104];
    for (size_t i = 0; i < sizeof(data); ++i) data[i] = (uint8_t)(i * 73 + i * i);
    unsigned cases = 0;
    for (size_t s = 0; s < sizeof(specs) / sizeof(specs[0]); ++s) {
        AVCRC small[257], large[1024];
        if (av_crc_init(small, specs[s].little, specs[s].bits, specs[s].poly, sizeof(small)) < 0
            || av_crc_init(large, specs[s].little, specs[s].bits, specs[s].poly, sizeof(large)) < 0) return 2;
        const AVCRC *tables[] = { av_crc_get_table(specs[s].id), small, large };
        for (size_t t = 0; t < 3; ++t) {
            if (!tables[t]) return 3;
            for (size_t offset = 0; offset < 8; ++offset) {
                for (size_t l = 0; l < sizeof(lengths) / sizeof(lengths[0]); ++l) {
                    for (unsigned use_seed = 0; use_seed < 2; ++use_seed) {
                        uint32_t seed = use_seed ? UINT32_C(0xa5b6c7d8) >> (32 - specs[s].bits) : 0;
                        uint32_t initial = specs[s].little ? seed : swap32(seed << (32 - specs[s].bits));
                        size_t length = lengths[l], split = length / 2;
                        uint32_t expected = reference(data + offset, length, seed, specs[s].bits, specs[s].poly, specs[s].little);
                        uint32_t whole = av_crc(tables[t], initial, data + offset, length);
                        uint32_t chunk = av_crc(tables[t], initial, data + offset, split);
                        chunk = av_crc(tables[t], chunk, data + offset + split, length - split);
                        if (whole != expected || chunk != expected) {
                            fprintf(stderr, "CRC mismatch spec=%zu table=%zu offset=%zu length=%zu seed=%u\n", s, t, offset, length, use_seed);
                            return 4;
                        }
                        ++cases;
                    }
                }
            }
        }
    }
    if (cases != 2304) return 5;
    puts("ANDCODE_SOURCE_FFMPEG_CRC_OK 2304 cases (Linux only)");
    return 0;
}
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
    for name, value in re.findall(r'^#define[ \t]+(\w+)[ \t]+([^\r\n]+)', text, re.M):
        value = value.strip()
        if name in definitions:
            # Fixed FFmpeg 9.0.2 lists libsmbclient in both GPLV3 and general
            # external libraries, so configure emits this disabled macro twice.
            # Permit that exact upstream duplicate only, never conflicting values.
            if name == 'CONFIG_LIBSMBCLIENT' and definitions[name] == value == '0':
                continue
            raise ValueError('Duplicate FFmpeg configuration macro: ' + name)
        definitions[name] = value
    expected = {'FFMPEG_LICENSE': '"LGPL version 2.1 or later"',
                'CONFIG_GPL': '0', 'CONFIG_VERSION3': '0', 'CONFIG_NONFREE': '0',
                'CONFIG_NETWORK': '0', 'CONFIG_ZLIB': '1',
                'HAVE_ARMV8': '0', 'HAVE_ARMV8_EXTERNAL': '0',
                'HAVE_ARM_CRC': '0', 'HAVE_PMULL': '0'}
    for name, value in expected.items():
        if definitions.get(name) != value:
            raise ValueError('Unexpected FFmpeg configuration: ' + name)
    return expected


def ffmpeg_source_inputs(native, prefix, objects):
    """Bounded make-dependency evidence and GPL-only header guard, not license approval."""
    cache = (native / '.cache/ffmpeg').resolve(strict=True)
    build = cache / 'build/aarch64-linux'
    files, mappings, missing = {}, [], []
    for item in objects:
        parts = PurePosixPath(item).parts
        if len(parts) < 3 or parts[0] != 'objects' or '..' in parts:
            raise ValueError('Unexpected FFmpeg object path')
        library = parts[1]
        relative = PurePosixPath(*parts[2:])
        group = 'zlib' if library == 'libz' else library
        original = build / group / str(relative)
        if original.read_bytes() != (prefix / item).read_bytes():
            raise ValueError('FFmpeg installed object differs from build object')
        dep = original.with_suffix('.d')
        if not dep.exists():
            # Fixed zlib make recipe does not emit dependency files. This gap
            # must remain visible; never infer complete source attribution.
            if library != 'libz':
                raise ValueError('Missing FFmpeg compiler dependency file')
            missing.append(item)
            continue
        target, separator, body = dep.read_text(encoding='utf8').replace('\\\n', ' ').partition(':')
        if not separator or target.strip() != group + '/' + relative.as_posix():
            raise ValueError('Unexpected FFmpeg dependency target')
        dependencies = []
        for name in shlex.split(body):
            path = Path(name)
            if not path.is_absolute():
                path = build / path
            path = path.resolve(strict=True)
            key = path.relative_to(cache).as_posix()
            if not path.is_file():
                raise ValueError('Special FFmpeg source input')
            if key not in files:
                content = path.read_bytes()
                header = '\n'.join(content.decode('utf8', errors='replace').splitlines()[:100])
                normalized = re.sub(r'\s+', ' ', re.sub(r'(?m)^\s*\*\s?', '', header))
                if (('GNU General Public License' in normalized
                     and 'GNU Lesser General Public License' not in normalized)
                        or re.search(r'SPDX-License-Identifier:\s*GPL-', normalized)):
                    raise ValueError('GPL-only declaration in FFmpeg compiler input: ' + key)
                files[key] = {'path': key, 'bytes': len(content),
                              'sha256': hashlib.sha256(content).hexdigest()}
            dependencies.append(key)
        if not dependencies:
            raise ValueError('Empty FFmpeg dependency file')
        mappings.append({'object': item, 'dependencyFile': dep.relative_to(cache).as_posix(),
                         'dependencies': dependencies})
    return {'objects': mappings, 'files': [files[key] for key in sorted(files)],
            'objectsWithoutDependencyFiles': missing,
            'scope': 'Retained make dependencies only; no system-header, zlib-header or complete per-file license approval'}


def probe_ffmpeg_crc(prefix, output, env):
    """Exercise retained libavutil against an independent bitwise reference."""
    source, binary = output / 'crc-probe.c', output / 'crc-probe'
    source.write_text(CRC_PROBE, encoding='utf8', newline='\n')
    commands = [['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                 '-I', str(prefix / 'include'), str(source), str(prefix / 'lib/libavutil.a'),
                 '-lm', '-pthread', '-Wl,-z,max-page-size=16384', '-o', str(binary)], [str(binary)]]
    with (output / 'crc-probe.log').open('w', encoding='utf8') as log:
        for command in commands:
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
            log.write(shlex.join(command) + '\n' + result.stdout + result.stderr)
            result.check_returncode()
        if CRC_MARKER + ' 2304 cases (Linux only)' not in result.stdout:
            raise ValueError('FFmpeg CRC reference probe did not complete')
    return {'commands': commands, 'cases': 2304, 'marker': CRC_MARKER,
            'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'binarySha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
            'scope': 'Runner-linked standalone libavutil probe; not Android, decoder or final library export acceptance'}


def retain_link_inputs(text, native, output, env):
    """Retain fixed Zig's explicit final-link inputs, not archive-member attribution."""
    commands = [line.strip() for line in text.splitlines() if line.strip().startswith('ld.lld ')]
    if len(commands) != 1:
        raise ValueError('Expected one explicit OpenTUI ld.lld command')
    arguments = shlex.split(commands[0])
    roots = [('opentui-source-build', native.resolve(strict=True)),
             ('zig-global-cache', Path(env['ZIG_GLOBAL_CACHE_DIR']).resolve(strict=True)),
             ('zig-local-cache', Path(env['ZIG_LOCAL_CACHE_DIR']).resolve(strict=True))]
    no_value = {'--error-limit=0', '-O3', '--build-id=sha1', '--image-base=0',
                '--gc-sections', '--eh-frame-hdr', '-znow', '-shared',
                '--no-undefined-version', '--as-needed', '-L/'}
    with_value = {'-mllvm': '-float-abi=hard', '-z': 'max-page-size=16384',
                  '-m': 'aarch64linux', '-soname': 'libopentui.so'}
    inputs, linked_output = [], None
    index = 1
    while index < len(arguments):
        argument = arguments[index]
        if argument in no_value:
            index += 1
            continue
        if argument in with_value:
            if index + 1 >= len(arguments) or arguments[index + 1] != with_value[argument]:
                raise ValueError('Unexpected OpenTUI linker option value: ' + argument)
            index += 2
            continue
        if argument == '-o':
            if linked_output is not None or index + 1 >= len(arguments):
                raise ValueError('Unexpected OpenTUI linker output')
            linked_output = Path(arguments[index + 1])
            if not linked_output.is_absolute() or linked_output.name != 'libopentui.so':
                raise ValueError('Unexpected OpenTUI linker output')
            linked_output.resolve(strict=True).relative_to(roots[2][1])
            index += 2
            continue
        path = Path(argument)
        if not path.is_absolute() or not re.fullmatch(r'[A-Za-z0-9_+.-]+', path.name):
            raise ValueError('Unrecognized OpenTUI linker input or option: ' + argument)
        resolved = path.resolve(strict=True)
        scope = next(((name, root) for name, root in roots if resolved.is_relative_to(root)), None)
        if scope is None or not resolved.is_file():
            raise ValueError('OpenTUI linker input escaped allowed build roots')
        if not (path.suffix in ('.o', '.a') or re.fullmatch(r'.+\.so(?:\.\d+)*', path.name)):
            raise ValueError('Unexpected OpenTUI linker input type')
        inputs.append((index, argument, resolved, scope))
        index += 1
    if linked_output is None or not inputs:
        raise ValueError('Missing OpenTUI final-link output or inputs')
    directory = output / 'link-inputs'
    directory.mkdir(exist_ok=False)
    rows = []
    for index, argument, resolved, (scope, root) in inputs:
        retained = directory / f'{index:04d}-{resolved.name}'
        shutil.copyfile(resolved, retained)
        with retained.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        rows.append({'argumentIndex': index, 'path': argument, 'scope': scope,
                     'scopeRelativePath': resolved.relative_to(root).as_posix(),
                     'retainedPath': retained.relative_to(output).as_posix(),
                     'bytes': retained.stat().st_size, 'sha256': digest})
    return {'command': arguments, 'output': str(linked_output), 'inputs': rows}


def retain_zig_resources(archive_path, output):
    """Keep source/notice resources from the verified tool archive, not its binary."""
    with archive_path.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != ZIG_SHA256:
            raise ValueError('Unexpected fixed OpenTUI Zig archive')
    destination = output / 'zig-library-resources.tar.gz'
    rows, seen, roots, expanded = [], set(), set(), 0
    with tarfile.open(archive_path) as src, tarfile.open(destination, 'w:gz') as dest:
        for member in src:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or not path.parts or '..' in path.parts or '\\' in member.name
                    or path.as_posix() in seen):
                raise ValueError('Unsafe Zig resource archive path')
            seen.add(path.as_posix())
            roots.add(path.parts[0])
            if len(roots) != 1 or len(seen) > 50000:
                raise ValueError('Unexpected Zig resource archive roots or entry count')
            relative = PurePosixPath(*path.parts[1:])
            if str(relative) not in ('LICENSE', 'README.md') and relative.parts[:1] != ('lib',):
                continue
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('Zig source resource link or special entry')
            expanded += member.size
            if expanded > 512 * 1024 * 1024 or member.size > 128 * 1024 * 1024:
                raise ValueError('Zig source resource expansion exceeds bounds')
            content = src.extractfile(member).read()
            if content.startswith(b'\x7fELF'):
                raise ValueError('Executable ELF in Zig source resources')
            entry = tarfile.TarInfo(relative.as_posix())
            entry.size = len(content)
            entry.mode = 0o644
            dest.addfile(entry, io.BytesIO(content))
            rows.append({'path': relative.as_posix(), 'bytes': len(content),
                         'sha256': hashlib.sha256(content).hexdigest()})
    required = {'LICENSE', 'lib/libcxx/LICENSE.TXT', 'lib/libcxxabi/LICENSE.TXT',
                'lib/libunwind/LICENSE.TXT', 'lib/libc/glibc/LICENSES', 'lib/compiler_rt.zig'}
    if required - {row['path'] for row in rows}:
        raise ValueError('Missing Zig runtime source or notice resource')
    with destination.open('rb') as source:
        checksum = hashlib.file_digest(source, 'sha256').hexdigest()
    return {'archive': destination.name, 'sha256': checksum, 'files': rows,
            'scope': 'Pinned tool archive lib/ resources and root notices, not complete toolchain corresponding source'}


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
    zig_resources = retain_zig_resources(zig.parent.parent / 'zig.tar.xz', output)
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
    patched_script = patch_once(original_script,
        '  await download(NASM_URL, nasmArchive, NASM_SHA256, "NASM")',
        '  // andcode aarch64-only experiment: no x86 NASM download')
    # Fixed FFmpeg crc.S declares GPL-2.0-or-later despite --disable-gpl.
    # Disable its ARMV8-OBJS group and the independently tested CRC header
    # dispatch features; otherwise crc.c still references the excluded symbols.
    # The independently selected NEON group remains enabled.
    patched_script = patch_once(patched_script, '    "--disable-gpl",',
                                '    "--disable-gpl",\n    "--disable-armv8",\n'
                                '    "--disable-arm-crc",\n    "--disable-pmull",')
    ffmpeg_script.write_text(patched_script, encoding='utf8')
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
        if item == 'objects/libavutil/aarch64/crc.o':
            raise ValueError('GPL-declared FFmpeg CRC object must not be linked')
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
    source_inputs = ffmpeg_source_inputs(native, prefix, objects)
    crc_probe = probe_ffmpeg_crc(prefix, output, env)
    link = retain_link_inputs((output / 'command-1.log').read_text(encoding='utf8'), native, output, env)
    result = native / 'lib/aarch64-linux/libopentui.so'
    if Path(link['output']).read_bytes() != result.read_bytes():
        raise ValueError('Installed OpenTUI differs from final-link output')
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
        'zigLibraryResources': zig_resources,
        'nestedZigArchiveSha256': hashlib.sha256(nested.read_bytes()).hexdigest(),
        'ffmpegObjects': object_rows, 'ffmpegConfiguration': configuration, 'abiGate': MARKER,
        'ffmpegSourceInputs': source_inputs,
        'ffmpegCrcProbe': crc_probe,
        'finalLink': link,
        'limitations': ['FFmpeg objects and build tree retained, not complete LGPL relinking approval',
                        'Explicit linker input copies do not prove selected archive members, per-file source attribution or toolchain corresponding source',
                        'Per-file notices, Bun/JSC obligations and Android remain under review']
    }, indent=2) + '\n', encoding='utf8')
    print('Fixed-source OpenTUI ABI passed; redistribution remains BLOCKED')


if __name__ == '__main__':
    build(*sys.argv[1:])
