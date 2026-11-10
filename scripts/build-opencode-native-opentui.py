"""Fixed-source OpenTUI diagnostic rebuild, never license or Android approval."""
import difflib
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
HOST_SYSTEM_ROOT = Path('/usr')
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
CRC_SOURCE_SHA256 = 'fbcab458ebddda14d121333622525cb0547c1d428645e9286534690c48366ad5'
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


def patch_zlib_dependencies(text):
    """Record non-system prerequisites during the actual fixed zlib compilation."""
    text = patch_once(text, '      `-I${zlibSource}`,\n      "-c",',
        '      `-I${zlibSource}`,\n'
        '      "-MMD", "-MF", join(build, `${file}.d`),\n'
        '      "-MT", `zlib/${file}.o`,\n'
        '      "-c",')
    text = patch_once(text,
        '  const result = spawnSync(command, args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] })',
        '  console.log("ANDCODE_MEDIA_COMMAND " + JSON.stringify({ command, args, cwd }))\n'
        '  const result = spawnSync(command, args, { cwd, encoding: "utf8", maxBuffer: 16 * 1024 * 1024, stdio: ["ignore", "pipe", "inherit"] })\n'
        '  if (result.stdout) process.stdout.write(result.stdout)')
    return patch_once(text, '  run("make", [`-j${Math.max(1, availableParallelism())}`], build)',
        '  run("make", ["V=1", `-j${Math.max(1, availableParallelism())}`], build)')


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


def verify_media_command_log(text):
    """Require actual captured compiler output, not merely verbose-mode arguments."""
    commands = [json.loads(line.removeprefix('ANDCODE_MEDIA_COMMAND '))
                for line in text.splitlines() if line.startswith('ANDCODE_MEDIA_COMMAND ')]
    if (not any(row['command'] == 'make' and 'V=1' in row['args'] for row in commands)
            or not any(re.search(r'(?:^|\s)-c(?:\s|$)', line)
                       and re.search(r'(?:^|\s)-o\s+libavutil/crc\.o(?:\s|$)', line)
                       for line in text.splitlines())):
        raise ValueError('Actual verbose FFmpeg compiler output was not retained')


def media_compile_commands(text, native, prefix, objects, dependency):
    """Bind retained media objects to observed commands; never execute log content."""
    cache = (native / '.cache/ffmpeg').resolve(strict=True)
    build = cache / 'build/aarch64-linux'
    expected = {}
    for item in objects:
        parts = PurePosixPath(item).parts
        if len(parts) < 3 or parts[0] != 'objects' or '..' in parts or '\\' in item:
            raise ValueError('Unsafe media compile object')
        group = 'zlib' if parts[1] == 'libz' else parts[1]
        path = (build / group / str(PurePosixPath(*parts[2:]))).resolve(strict=True)
        path.relative_to(build)
        if path in expected:
            raise ValueError('Duplicate media compile object')
        if path.read_bytes() != (prefix / item).read_bytes():
            raise ValueError('Media compile object bytes changed')
        expected[path] = item
    dependencies = {row['object']: set(row['dependencies']) for row in dependency['objects']}
    if set(dependencies) != set(objects) or dependency['objectsWithoutDependencyFiles']:
        raise ValueError('Incomplete media compile dependency coverage')
    commands, make_dirs = [], set()
    for number, line in enumerate(text.splitlines(), 1):
        if not line.startswith('ANDCODE_MEDIA_COMMAND '):
            continue
        row = json.loads(line.removeprefix('ANDCODE_MEDIA_COMMAND '))
        if row['command'] == 'make' and 'V=1' in row['args']:
            make_dirs.add(Path(row['cwd']).resolve(strict=True))
        elif '-c' in row['args']:
            commands.append((number, row['command'], row['args'], Path(row['cwd'])))
    if make_dirs != {build.resolve(strict=True)}:
        raise ValueError('Unexpected verbose media make directory')
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith('ANDCODE_MEDIA_COMMAND ') or not re.search(r'(?:^|\s)-c(?:\s|$)', line):
            continue
        args = shlex.split(line)
        if '-c' in args and '-o' in args:
            commands.append((number, args[0], args[1:], build))
    mapped = {}
    for number, command, args, cwd in commands:
        if args.count('-c') != 1 or args.count('-o') != 1 or args.index('-o') + 1 >= len(args):
            raise ValueError('Ambiguous media compiler invocation')
        output = Path(args[args.index('-o') + 1])
        output = (output if output.is_absolute() else cwd / output).resolve()
        if output not in expected:
            continue
        item = expected[output]
        if item in mapped:
            raise ValueError('Duplicate media compiler invocation: ' + item)
        compiler = Path(command).resolve(strict=True)
        if compiler != (cache / 'toolchains/aarch64-linux/cc').resolve(strict=True):
            raise ValueError('Unexpected media compiler wrapper')
        source_args = [arg for arg in args if arg.endswith(('.c', '.S', '.s'))]
        if len(source_args) != 1:
            raise ValueError('Ambiguous media compiler source')
        source = Path(source_args[0])
        source = (source if source.is_absolute() else cwd / source).resolve(strict=True)
        relative = source.relative_to(cache).as_posix()
        if relative not in dependencies[item]:
            raise ValueError('Compiler source absent from recorded dependencies')
        mapped[item] = {'object': item, 'logLine': number, 'command': command,
                        'args': args, 'cwd': str(cwd), 'source': relative,
                        'objectSha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                        'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                        'compilerWrapperSha256': hashlib.sha256(compiler.read_bytes()).hexdigest()}
    if set(mapped) != set(objects):
        raise ValueError('Missing actual media compiler invocations: ' + repr(sorted(set(objects) - set(mapped))))
    return {'objects': [mapped[item] for item in objects], 'redistributionApproved': False,
            'scope': 'Observed compiler argv/cwd/source matched to retained objects and non-system dependencies; not system-header, preprocessing, provenance or complete source approval'}


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


def notice_candidates(content):
    """Preserve exact candidate comment bytes, not infer a license from keywords."""
    keywords = re.compile(rb'copyright|spdx-license-identifier|permission|redistribution|'
                          rb'general public license|independent jpeg group|public domain', re.I)
    comments = list(re.finditer(rb'/\*.*?\*/', content, re.S))
    rows = []
    for comment in comments:
        raw = comment.group()
        if keywords.search(raw):
            rows.append({'offset': comment.start(), 'bytes': len(raw),
                         'line': content.count(b'\n', 0, comment.start()) + 1,
                         'sha256': hashlib.sha256(raw).hexdigest(),
                         'text': raw.decode('utf8')})
    outside, offset, cursor = [], 0, 0
    for number, line in enumerate(content.splitlines(keepends=True), 1):
        for match in keywords.finditer(line):
            position = offset + match.start()
            while cursor < len(comments) and comments[cursor].end() <= position:
                cursor += 1
            if cursor >= len(comments) or position < comments[cursor].start():
                outside.append({'line': number, 'offset': offset, 'text': line.decode('utf8')})
                break
        offset += len(line)
    return {'comments': rows, 'outsideCommentLines': outside}


def retain_ffmpeg_notices(native, dependency, output):
    cache = (native / '.cache/ffmpeg').resolve(strict=True)
    files = []
    for row in dependency['files']:
        path = (cache / row['path']).resolve(strict=True)
        path.relative_to(cache)
        content = path.read_bytes()
        if len(content) != row['bytes'] or hashlib.sha256(content).hexdigest() != row['sha256']:
            raise ValueError('FFmpeg notice source changed')
        files.append(dict(row, **notice_candidates(content)))
    report = {'redistributionApproved': False, 'files': files,
              'scope': 'Keyword-selected block comments and outside lines from recorded dependencies only; not complete notices, system headers, generators or license approval'}
    destination = output / 'ffmpeg-notice-candidates.json'
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    return {'path': destination.name, 'bytes': destination.stat().st_size,
            'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'files': len(files),
            'redistributionApproved': False, 'scope': report['scope']}


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
            # Historical zlib builds did not emit dependency files. Preserve the
            # gap in this reader; new build integration requires them below.
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
            'scope': 'Recorded non-system compiler dependencies only; missing objects explicit, no complete compiler-input or per-file license approval'}


def replay_media_generators(native, output, env):
    """Replay two fixed host-generator modes without modifying build inputs."""
    cache = (native / '.cache/ffmpeg').resolve(strict=True)
    build = cache / 'build/aarch64-linux'
    generator = (build / 'libswscale/aarch64/ops_asmgen').resolve(strict=True)
    generator.relative_to(build)
    source = (cache / 'sources/ffmpeg-9.0.2/libswscale/aarch64/ops_asmgen.c').resolve(strict=True)
    rule = (cache / 'sources/ffmpeg-9.0.2/libswscale/aarch64/Makefile').resolve(strict=True)
    inputs = [generator, source, rule]
    for path in inputs:
        path.relative_to(cache)
    baseline = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    directory = output / 'media-generator-replay'
    directory.mkdir(exist_ok=False)
    rows = []
    modes = [('-lookup', 'ops_lookup.gen.c', 'lookup.log'),
             ('-ops', 'ops_neon.gen.S', 'neon.log')]
    expected_inputs, originals = {}, {}
    for _, filename, _ in modes:
        expected = (build / 'libswscale/aarch64' / filename).resolve(strict=True)
        expected.relative_to(build)
        original = expected.read_bytes()
        expected_inputs[expected] = hashlib.sha256(original).hexdigest()
        originals[filename] = (expected, original)
    for mode, filename, logname in modes:
        expected, original = originals[filename]
        command = [str(generator), mode]
        log = directory / logname
        try:
            done = subprocess.run(command, cwd=directory, env=env, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired as error:
            log.write_bytes((shlex.join(command) + '\nTIMEOUT\n').encode() + (error.stderr or b''))
            raise
        log.write_bytes((shlex.join(command) + '\n').encode() + done.stderr)
        done.check_returncode()
        reproduced = directory / filename
        reproduced.write_bytes(done.stdout)
        if not original or done.stdout != original or expected.read_bytes() != original:
            raise ValueError('Media generator replay differs from retained input: ' + filename)
        rows.append({'command': command, 'cwd': str(directory),
                     'input': expected.relative_to(cache).as_posix(),
                     'output': reproduced.relative_to(output).as_posix(),
                     'bytes': len(original), 'sha256': hashlib.sha256(original).hexdigest(),
                     'log': log.relative_to(output).as_posix(),
                     'logSha256': hashlib.sha256(log.read_bytes()).hexdigest()})
    for path, digest in {**baseline, **expected_inputs}.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Media generator replay changed its baseline inputs')
    return {'inputs': [{'path': path.relative_to(cache).as_posix(), 'sha256': digest,
                        'bytes': path.stat().st_size} for path, digest in baseline.items()],
            'outputs': rows, 'redistributionApproved': False, 'androidApproved': False,
            'scope': 'Two modes of retained FFmpeg host generator reproduced configured inputs byte-for-byte; not a rebuilt generator, all generators, source closure or license approval'}


def rebuild_media_generator(native, output, env):
    """Recompile the standalone host tool in isolation; never execute log argv."""
    cache = (native / '.cache/ffmpeg').resolve(strict=True)
    source = (cache / 'sources/ffmpeg-9.0.2').resolve(strict=True)
    build = cache / 'build/aarch64-linux'
    dependency = build / 'libswscale/aarch64/ops_asmgen.d'
    original_generator = build / 'libswscale/aarch64/ops_asmgen'
    rule = source / 'libswscale/aarch64/Makefile'
    baseline = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [dependency, original_generator, rule]}
    modes = [('-lookup', 'ops_lookup.gen.c', 'lookup.log'),
             ('-ops', 'ops_neon.gen.S', 'neon.log')]
    expected = {}
    for _, filename, _ in modes:
        path = build / 'libswscale/aarch64' / filename
        expected[filename] = path.read_bytes()
        baseline[path] = hashlib.sha256(expected[filename]).hexdigest()
    target, separator, body = dependency.read_text(encoding='utf8').replace('\\\n', ' ').partition(':')
    if not separator or target.strip() != 'libswscale/aarch64/ops_asmgen.o':
        raise ValueError('Unexpected host generator dependency target')
    directory = output / 'media-generator-rebuild'
    directory.mkdir(exist_ok=False)
    copied = directory / 'source'
    copied.mkdir()
    inputs = []
    seen = set()
    for name in shlex.split(body):
        parts = PurePosixPath(name).parts
        if (not parts or parts[0] != 'src' or '..' in parts or '\\' in name
                or PurePosixPath(name).is_absolute()):
            raise ValueError('Unexpected host generator source dependency')
        relative = PurePosixPath(*parts[1:]).as_posix()
        if relative in seen:
            continue
        seen.add(relative)
        path = (source / relative).resolve(strict=True)
        path.relative_to(source)
        content = path.read_bytes()
        baseline[path] = hashlib.sha256(content).hexdigest()
        destination = copied / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        inputs.append({'path': path.relative_to(cache).as_posix(),
                       'copy': destination.relative_to(output).as_posix(),
                       'bytes': len(content), 'sha256': baseline[path]})
    main = copied / 'libswscale/aarch64/ops_asmgen.c'
    if not main.is_file():
        raise ValueError('Missing host generator main source')
    compiler_name = shutil.which('gcc')
    if not compiler_name:
        raise ValueError('Missing host GCC')
    compiler = Path(compiler_name).resolve(strict=True)
    if not compiler.is_file():
        raise ValueError('Missing host GCC')
    compiler_digest = hashlib.sha256(compiler.read_bytes()).hexdigest()
    clean_env = dict(env)
    for key in ['CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'OBJC_INCLUDE_PATH',
                'GCC_EXEC_PREFIX', 'COMPILER_PATH', 'LIBRARY_PATH', 'DEPENDENCIES_OUTPUT',
                'SUNPRO_DEPENDENCIES', 'LD_PRELOAD', 'LD_LIBRARY_PATH']:
        clean_env.pop(key, None)
    commands = []

    def run(command, logname):
        log = directory / logname
        commands.append({'command': command, 'cwd': str(directory),
                         'log': log.relative_to(output).as_posix()})
        try:
            done = subprocess.run(command, cwd=directory, env=clean_env,
                                  capture_output=True, timeout=120)
        except subprocess.TimeoutExpired as error:
            log.write_bytes((shlex.join(command) + '\nTIMEOUT\n').encode()
                            + (error.stdout or b'') + (error.stderr or b''))
            raise
        log.write_bytes((shlex.join(command) + '\n').encode() + done.stdout + done.stderr)
        done.check_returncode()
        return done.stdout

    version = run([str(compiler), '--version'], 'compiler.log')
    flags = ['-I.', '-Isource', '-D_ISOC11_SOURCE', '-D_POSIX_C_SOURCE=200112',
             '-D_XOPEN_SOURCE=600', '-D_POSIX_C_SOURCE=200112', '-D_XOPEN_SOURCE=600',
             '-std=c17', '-Wall', '-O3']
    run([str(compiler), *flags, '-MD', '-MF', 'ops_asmgen.d', '-MT', 'ops_asmgen.o',
         '-E', '-o', 'ops_asmgen.i', 'source/libswscale/aarch64/ops_asmgen.c'], 'preprocess.log')
    preprocessed = directory / 'ops_asmgen.i'
    preprocessed_digest = hashlib.sha256(preprocessed.read_bytes()).hexdigest()
    target, separator, body = (directory / 'ops_asmgen.d').read_text(encoding='utf8').replace('\\\n', ' ').partition(':')
    if not separator or target.strip() != 'ops_asmgen.o':
        raise ValueError('Invalid rebuilt generator dependency target')
    headers = []
    copied_inputs = set()
    header_baseline = {}
    for name in sorted(set(shlex.split(body))):
        path = Path(name)
        if not path.is_absolute():
            path = directory / path
        path = path.resolve(strict=True)
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        header_baseline[path] = digest
        if path.is_relative_to(copied):
            copied_inputs.add(path.relative_to(copied).as_posix())
            continue
        if not path.is_relative_to(HOST_SYSTEM_ROOT.resolve(strict=True)):
            raise ValueError('Host generator header outside approved /usr tree')
        destination = directory / 'system-headers' / path.relative_to(Path(path.anchor))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        headers.append({'original': str(path), 'copy': destination.relative_to(output).as_posix(),
                        'bytes': len(content), 'sha256': digest})
    if copied_inputs != seen or not headers:
        raise ValueError('Rebuilt generator source/header dependency set differs')
    run([str(compiler), '-std=c17', '-Wall', '-O3', '-c', '-o', 'ops_asmgen.o',
         'ops_asmgen.i'], 'compile.log')
    run([str(compiler), '-o', 'ops_asmgen', 'ops_asmgen.o', '-lm'], 'link.log')
    if (not (directory / 'ops_asmgen.i').stat().st_size
            or not (directory / 'ops_asmgen').read_bytes().startswith(b'\x7fELF')):
        raise ValueError('Missing preprocessing or ELF host generator output')
    for mode, filename, logname in modes:
        raw = run([str(directory / 'ops_asmgen'), mode], logname)
        (directory / filename).write_bytes(raw)
        if not raw or raw != expected[filename]:
            raise ValueError('Rebuilt host generator output differs: ' + filename)
    protected = {**baseline, **header_baseline, compiler: compiler_digest,
                 preprocessed: preprocessed_digest}
    protected.update({output / row['copy']: row['sha256'] for row in inputs + headers})
    for path, digest in protected.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Host generator rebuild changed a retained input')
    files = []
    for path in sorted(directory.rglob('*')):
        if path.is_file():
            files.append({'path': path.relative_to(output).as_posix(), 'bytes': path.stat().st_size,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'compiler': {'path': str(compiler), 'sha256': compiler_digest,
                         'version': version.decode('utf8')},
            'commands': commands, 'sourceInputs': inputs, 'systemHeaders': headers,
            'files': files, 'outputMatches': 2, 'redistributionApproved': False,
            'androidApproved': False, 'relinkingApproved': False,
            'scope': 'Isolated standalone host generator rebuild with observed full dependency snapshots and preprocessed TU; two output byte matches, not toolchain closure, reproducible generator ELF, other generators, complete source or legal approval'}


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


def retain_zig_generated_sources(output, env):
    """Snapshot generated builtin inputs, not a claim about complete compiler inputs."""
    pending, expanded = [], 0
    for label, key in [('global', 'ZIG_GLOBAL_CACHE_DIR'), ('local', 'ZIG_LOCAL_CACHE_DIR')]:
        root = Path(env[key])
        if root.is_symlink():
            raise ValueError('Zig generated source cache link')
        root = root.resolve(strict=True)
        directory = root / 'b'
        if directory.is_symlink():
            raise ValueError('Zig generated source directory link')
        if not directory.exists():
            continue
        children = sorted(directory.iterdir())
        if len(children) > 10000:
            raise ValueError('Zig generated source cache entry bound exceeded')
        for child in children:
            if child.is_symlink():
                raise ValueError('Zig generated source entry link')
            if not child.is_dir():
                continue
            path = child / 'builtin.zig'
            if path.is_symlink():
                raise ValueError('Zig generated source file link')
            if not path.exists():
                continue
            if not re.fullmatch(r'[a-f0-9]{32}', child.name) or not path.is_file():
                raise ValueError('Unexpected Zig generated source path')
            path.resolve(strict=True).relative_to(root)
            if path.stat().st_size > 4 * 1024 * 1024:
                raise ValueError('Zig generated source file exceeds bound')
            content = path.read_bytes()
            expanded += len(content)
            if (not content or len(content) > 4 * 1024 * 1024
                    or expanded > 32 * 1024 * 1024 or len(pending) >= 256):
                raise ValueError('Zig generated source snapshot exceeds bounds')
            if content.startswith(b'\x7fELF'):
                raise ValueError('ELF in Zig generated sources')
            content.decode('utf8')
            relative = Path('zig-generated-sources') / label / 'b' / child.name / 'builtin.zig'
            pending.append((path, relative, content, label))
    if not pending:
        raise ValueError('No Zig generated builtin sources found')
    destination = output / 'zig-generated-sources'
    destination.mkdir(exist_ok=False)
    rows = []
    for path, relative, content, label in pending:
        retained = output / relative
        retained.parent.mkdir(parents=True, exist_ok=True)
        retained.write_bytes(content)
        rows.append({'path': str(path), 'scope': label, 'retainedPath': relative.as_posix(),
                     'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
    return {'files': rows, 'sourceAttributionApproved': False, 'redistributionApproved': False,
            'scope': 'Post-build generated builtin snapshots only; no complete compiler-input or source-to-object proof'}


def replay_link_inputs(link, zig, result, output, env):
    """Replay with the same fixed linker; byte equality binds map to original output."""
    directory = output / 'link-replay'
    directory.mkdir(exist_ok=False)
    arguments = list(link['command'])
    if arguments[0] != 'ld.lld' or arguments.count('-o') != 1:
        raise ValueError('Unexpected linker replay command')
    for item in link['inputs']:
        path = (output / item['retainedPath']).resolve(strict=True)
        path.relative_to((output / 'link-inputs').resolve(strict=True))
        if (arguments[item['argumentIndex']] != item['path']
                or path.stat().st_size != item['bytes']
                or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']):
            raise ValueError('Retained linker replay input changed')
        arguments[item['argumentIndex']] = str(path)
    binary = directory / 'libopentui.so'
    arguments[arguments.index('-o') + 1] = str(binary)
    command = [str(zig), *arguments,
               '--Map=' + str(directory / 'link.map'),
               '--why-extract=' + str(directory / 'archive-extraction.tsv')]
    done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=120)
    (directory / 'link.log').write_text(done.stdout + done.stderr, encoding='utf8')
    done.check_returncode()
    payload = binary.read_bytes()
    if payload != result.read_bytes():
        raise ValueError('Same-linker replay differs from original OpenTUI bytes')
    _, needed = pty.audit.elf(payload)
    for name in ['link.map', 'archive-extraction.tsv']:
        if not (directory / name).is_file() or not (directory / name).stat().st_size:
            raise ValueError('Missing linker replay map or extraction report')
    if not (directory / 'archive-extraction.tsv').read_text(encoding='utf8').startswith('reference\textracted\tsymbol\n'):
        raise ValueError('Unexpected linker archive extraction report')
    probe = output / 'probe.mjs'
    probe.write_text(PROBE, encoding='utf8', newline='\n')
    done = subprocess.run(['bun', str(probe), str(binary)], env=env, capture_output=True,
                          text=True, timeout=30)
    (directory / 'abi.log').write_text(done.stdout + done.stderr, encoding='utf8')
    done.check_returncode()
    if MARKER not in done.stdout:
        raise ValueError('Linker replay ABI probe did not complete')
    files = []
    for path in sorted(directory.iterdir()):
        files.append({'path': path.relative_to(output).as_posix(), 'bytes': path.stat().st_size,
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'command': command, 'files': files, 'inputCount': len(link['inputs']),
            'byteIdentical': True, 'needed': needed, 'abiGate': MARKER,
            'scope': 'Same fixed Zig linker retained-input replay only; not modified-library rebuild or LGPL/Android approval'}


def modified_crc_source(content):
    """Instrument one pinned upstream translation unit without changing its grant."""
    if hashlib.sha256(content).hexdigest() != CRC_SOURCE_SHA256:
        raise ValueError('Unexpected original FFmpeg CRC source')
    text = content.decode('utf8')
    text = patch_once(text, '#include "config.h"',
        '/* Modified by andcode on 2026-11-10 for a single-threaded Linux-only\n'
        ' * relink diagnostic: count calls and expose CRC entry points.\n'
        ' * Disable the pure declaration locally because counting is a side effect.\n'
        ' */\n#include "config.h"')
    text = patch_once(text, '#include "crc.h"',
        '#include "attributes.h"\n#undef av_pure\n#define av_pure\n#include "crc.h"')
    text = patch_once(text, 'uint32_t av_crc(const AVCRC *ctx, uint32_t crc,',
        'static unsigned andcode_crc_calls;\n'
        'unsigned andcode_crc_relink_calls(void);\n'
        '__attribute__((visibility("default"))) unsigned andcode_crc_relink_calls(void)\n'
        '{ return andcode_crc_calls; }\n\n'
        'uint32_t av_crc(const AVCRC *ctx, uint32_t crc,')
    text = patch_once(text, 'const uint8_t *buffer, size_t length)\n{\n',
        'const uint8_t *buffer, size_t length)\n{\n    ++andcode_crc_calls;\n')
    for symbol in ('int av_crc_init(', 'const AVCRC *av_crc_get_table(', 'uint32_t av_crc('):
        text = patch_once(text, '\n' + symbol,
                          '\n__attribute__((visibility("default"))) ' + symbol)
    return text.encode('utf8')


def probe_modified_crc_relink(native, link, zig, result, output, env):
    """Replace one CRC object; never install the modified diagnostic library."""
    candidates = [row for row in link['inputs'] if Path(row['path']).as_posix().endswith(
        '/prefix/aarch64-linux/objects/libavutil/crc.o')]
    if len(candidates) != 1:
        raise ValueError('Expected one retained generic FFmpeg CRC object')
    selected = candidates[0]
    source = native / '.cache/ffmpeg/sources/ffmpeg-9.0.2/libavutil/crc.c'
    original = source.read_bytes()
    modified = modified_crc_source(original)
    directory = output / 'modified-crc-relink'
    directory.mkdir(exist_ok=False)
    (directory / 'original-crc.c').write_bytes(original)
    changed = directory / 'modified-crc.c'
    changed.write_bytes(modified)
    (directory / 'crc.patch').write_text(''.join(difflib.unified_diff(
        original.decode('utf8').splitlines(keepends=True),
        modified.decode('utf8').splitlines(keepends=True),
        fromfile='original/libavutil/crc.c', tofile='modified/libavutil/crc.c')),
        encoding='utf8', newline='\n')
    build = native / '.cache/ffmpeg/build/aarch64-linux'
    replacement = directory / 'crc.o'
    # Reuse the configured rule in separate trees. SRC_LINK must not resolve to
    # the original build's src symlink, or make would compile the unmodified file.
    isolated = directory / 'source'
    shutil.copytree(source.parent.parent, isolated)
    (isolated / 'libavutil/crc.c').write_bytes(modified)
    isolated_build = directory / 'build'
    shutil.copytree(build, isolated_build,
                    ignore=shutil.ignore_patterns('src', '*.o', '*.a', '*.d', 'zlib'))
    compile_command = ['make', '-C', str(isolated_build), 'V=1', 'libavutil/crc.o',
                       'SRC_PATH=' + str(isolated), 'SRC_LINK=' + str(isolated)]
    object_path = isolated_build / 'libavutil/crc.o'
    done = subprocess.run(compile_command, env=env, capture_output=True, text=True, timeout=120)
    (directory / 'compile.log').write_text(done.stdout + done.stderr, encoding='utf8')
    done.check_returncode()
    if str(isolated / 'libavutil/crc.c') not in done.stdout:
        raise ValueError('Modified CRC compilation source not recorded')
    shutil.copyfile(object_path, replacement)
    shutil.copyfile(isolated_build / 'libavutil/crc.d', directory / 'crc.d')
    if replacement.read_bytes() == (output / selected['retainedPath']).read_bytes():
        raise ValueError('Modified CRC object did not change')
    command = [str(zig), *link['command']]
    for row in link['inputs']:
        retained = output / row['retainedPath']
        if (retained.stat().st_size != row['bytes']
                or hashlib.sha256(retained.read_bytes()).hexdigest() != row['sha256']):
            raise ValueError('Retained modified-relink input changed')
        command[row['argumentIndex'] + 1] = str(replacement if row == selected else retained)
    binary = directory / 'libopentui.so'
    command[link['command'].index('-o') + 2] = str(binary)
    command.extend(['--Map=' + str(directory / 'link.map'),
                    '--why-extract=' + str(directory / 'archive-extraction.tsv')])
    done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=120)
    (directory / 'link.log').write_text(done.stdout + done.stderr, encoding='utf8')
    done.check_returncode()
    if binary.read_bytes() == result.read_bytes():
        raise ValueError('Modified CRC library did not change')
    for name in ['link.map', 'archive-extraction.tsv']:
        if not (directory / name).is_file() or not (directory / name).stat().st_size:
            raise ValueError('Missing modified linker map or extraction report')
    if not (directory / 'archive-extraction.tsv').read_text(encoding='utf8').startswith('reference\textracted\tsymbol\n'):
        raise ValueError('Unexpected modified linker archive extraction report')
    if str(replacement) not in (directory / 'link.map').read_text(encoding='utf8'):
        raise ValueError('Replacement object missing from modified linker map')
    _, needed = pty.audit.elf(binary.read_bytes())
    if sorted(needed) != sorted(pty.audit.elf(result.read_bytes())[1]):
        raise ValueError('Modified CRC dependencies changed')
    abi_source = directory / 'probe.mjs'
    abi_source.write_text(PROBE, encoding='utf8')
    abi_command = ['bun', str(abi_source), str(binary)]
    done = subprocess.run(abi_command, env=env, capture_output=True, text=True, timeout=30)
    (directory / 'abi.log').write_text(done.stdout + done.stderr, encoding='utf8')
    done.check_returncode()
    if MARKER not in done.stdout:
        raise ValueError('Modified CRC ABI probe did not complete')
    probe = directory / 'crc-probe.c'
    text = patch_once(CRC_PROBE, 'int main(void) {',
                      'extern unsigned andcode_crc_relink_calls(void);\n'
                      'static uint32_t (*volatile modified_crc)(const AVCRC *, uint32_t,\n'
                      '                                          const uint8_t *, size_t) = av_crc;\n'
                      '#define av_crc modified_crc\nint main(void) {')
    text = patch_once(text, '    if (cases != 2304) return 5;',
                      '    if (cases != 2304) return 5;\n'
                      '    if (andcode_crc_relink_calls() != cases * 3) return 6;\n'
                      '    puts("ANDCODE_MODIFIED_CRC_RELINK_OK 6912 calls (Linux only)");')
    probe.write_text(text, encoding='utf8', newline='\n')
    probe_binary = directory / 'crc-probe'
    probe_commands = [['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                       '-I', str(native / '.cache/ffmpeg/prefix/aarch64-linux/include'),
                       str(probe), str(binary), '-Wl,-rpath,' + str(directory),
                       '-Wl,-z,max-page-size=16384', '-o', str(probe_binary)], [str(probe_binary)]]
    with (directory / 'crc-probe.log').open('w', encoding='utf8') as log:
        for probe_command in probe_commands:
            done = subprocess.run(probe_command, env=env, capture_output=True, text=True, timeout=60)
            log.write(shlex.join(probe_command) + '\n' + done.stdout + done.stderr)
            done.check_returncode()
        if (CRC_MARKER + ' 2304 cases (Linux only)' not in done.stdout
                or 'ANDCODE_MODIFIED_CRC_RELINK_OK 6912 calls (Linux only)' not in done.stdout):
            raise ValueError('Modified-library CRC probe did not complete')
    if source.read_bytes() != original:
        raise ValueError('Baseline CRC source changed')
    for row in link['inputs']:
        retained = output / row['retainedPath']
        if (retained.stat().st_size != row['bytes']
                or hashlib.sha256(retained.read_bytes()).hexdigest() != row['sha256']):
            raise ValueError('Retained input changed during modified relink')
    files = []
    for path in sorted(directory.rglob('*')):
        if path.is_file():
            files.append({'path': path.relative_to(output).as_posix(), 'bytes': path.stat().st_size,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    print('ANDCODE_MODIFIED_CRC_RELINK_OK 6912 calls (Linux only)')
    return {'compileCommand': compile_command, 'command': command, 'abiCommand': abi_command,
            'probeCommands': probe_commands, 'files': files, 'replacement': selected,
            'inputCount': len(link['inputs']), 'crcCases': 2304, 'modifiedCalls': 6912,
            'redistributionApproved': False, 'androidApproved': False, 'relinkingApproved': False,
            'scope': 'One instrumented CRC object and final shared-library execution only; not complete source, general replacement, decoder/TUI or LGPL approval'}


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
    patched_script = patch_zlib_dependencies(patched_script)
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
    verify_media_command_log((output / 'command-0.log').read_text(encoding='utf8'))
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
    if source_inputs['objectsWithoutDependencyFiles']:
        raise ValueError('New media build must retain every compiler dependency file')
    compile_commands = media_compile_commands((output / 'command-0.log').read_text(encoding='utf8'),
                                              native, prefix, objects, source_inputs)
    notices = retain_ffmpeg_notices(native, source_inputs, output)
    generator_replay = replay_media_generators(native, output, env)
    generator_rebuild = rebuild_media_generator(native, output, env)
    crc_probe = probe_ffmpeg_crc(prefix, output, env)
    link = retain_link_inputs((output / 'command-1.log').read_text(encoding='utf8'), native, output, env)
    result = native / 'lib/aarch64-linux/libopentui.so'
    if Path(link['output']).read_bytes() != result.read_bytes():
        raise ValueError('Installed OpenTUI differs from final-link output')
    replay = replay_link_inputs(link, zig, result, output, env)
    modified_relink = probe_modified_crc_relink(native, link, zig, result, output, env)
    generated_sources = retain_zig_generated_sources(output, env)
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
        'zigGeneratedSources': generated_sources,
        'nestedZigArchiveSha256': hashlib.sha256(nested.read_bytes()).hexdigest(),
        'ffmpegObjects': object_rows, 'ffmpegConfiguration': configuration, 'abiGate': MARKER,
        'ffmpegSourceInputs': source_inputs,
        'ffmpegCompileCommands': compile_commands,
        'ffmpegNoticeCandidates': notices,
        'ffmpegGeneratorReplay': generator_replay,
        'ffmpegGeneratorRebuild': generator_rebuild,
        'ffmpegCrcProbe': crc_probe,
        'finalLink': link,
        'finalLinkReplay': replay,
        'modifiedCrcRelink': modified_relink,
        'limitations': ['FFmpeg objects and build tree retained, not complete LGPL relinking approval',
                        'Explicit linker input copies do not prove selected archive members, per-file source attribution or toolchain corresponding source',
                        'Per-file notices, Bun/JSC obligations and Android remain under review']
    }, indent=2) + '\n', encoding='utf8')
    print('Fixed-source OpenTUI ABI passed; redistribution remains BLOCKED')


if __name__ == '__main__':
    build(*sys.argv[1:])
