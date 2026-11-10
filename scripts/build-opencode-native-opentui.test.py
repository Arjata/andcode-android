import importlib.util
import hashlib
import io
import json
import shlex
from contextlib import ExitStack
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('opentui_build', Path(__file__).with_name('build-opencode-native-opentui.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    CONFIG = ('#define FFMPEG_LICENSE "LGPL version 2.1 or later"\n'
              '#define CONFIG_GPL 0\n#define CONFIG_VERSION3 0\n#define CONFIG_NONFREE 0\n'
              '#define CONFIG_NETWORK 0\n#define CONFIG_ZLIB 1\n'
              '#define HAVE_ARMV8 0\n#define HAVE_ARMV8_EXTERNAL 0\n'
              '#define HAVE_ARM_CRC 0\n#define HAVE_PMULL 0\n')

    def test_ffmpeg_configuration_drift_rejected(self):
        self.assertEqual(m.ffmpeg_configuration(self.CONFIG)['CONFIG_GPL'], '0')
        for changed in [self.CONFIG.replace('CONFIG_GPL 0', 'CONFIG_GPL 1'),
                        self.CONFIG.replace('CONFIG_NONFREE 0', 'CONFIG_NONFREE 1'),
                        self.CONFIG.replace('CONFIG_NETWORK 0', 'CONFIG_NETWORK 1'),
                         self.CONFIG.replace('CONFIG_ZLIB 1', 'CONFIG_ZLIB 0'),
                         self.CONFIG.replace('HAVE_ARMV8 0', 'HAVE_ARMV8 1'),
                         self.CONFIG.replace('HAVE_ARMV8_EXTERNAL 0', 'HAVE_ARMV8_EXTERNAL 1'),
                         self.CONFIG.replace('HAVE_ARM_CRC 0', 'HAVE_ARM_CRC 1'),
                         self.CONFIG.replace('HAVE_PMULL 0', 'HAVE_PMULL 1'),
                        self.CONFIG.replace('LGPL version 2.1', 'GPL version 3'),
                        self.CONFIG.replace('#define CONFIG_VERSION3 0\n', ''),
                        self.CONFIG + '#define CONFIG_GPL 0\n']:
            with self.subTest(configuration=changed), self.assertRaises(ValueError):
                m.ffmpeg_configuration(changed)

    def test_fixed_ffmpeg_disabled_smb_duplicate(self):
        generated = ('#ifndef FFMPEG_CONFIG_H\n#define FFMPEG_CONFIG_H\n' + self.CONFIG
                     + '#define CONFIG_LIBSMBCLIENT 0\n#define CONFIG_LIBSMBCLIENT 0\n#endif\n')
        self.assertEqual(m.ffmpeg_configuration(generated)['FFMPEG_LICENSE'],
                         '"LGPL version 2.1 or later"')
        for duplicate in ['#define CONFIG_LIBSMBCLIENT 1\n', '#define CONFIG_NETWORK 0\n']:
            with self.subTest(duplicate=duplicate), self.assertRaises(ValueError):
                m.ffmpeg_configuration(generated + duplicate)
        # A valueless header guard must not consume the next macro's line.
        with self.assertRaisesRegex(ValueError, 'FFMPEG_LICENSE'):
            m.ffmpeg_configuration('#define FFMPEG_CONFIG_H\n'
                                   + self.CONFIG.replace('LGPL version 2.1', 'GPL version 3'))

    def test_exact_anchor(self):
        self.assertEqual(m.patch_once('before anchor after', 'anchor', 'patched'), 'before patched after')
        for text in ['missing', 'anchor anchor']:
            with self.assertRaises(ValueError):
                m.patch_once(text, 'anchor', 'patched')

    def test_library_only_patch_preserves_video_requirement(self):
        fixture = ('    if (target.result.os.tag == .linux and optimize != .debug) shared.build_id = .sha1;\n'
                   '    require_video = b.option(bool, "require-video", "required") orelse false;\n'
                   '    buildSingleTarget();\n    // Test step (native only)\n    addMuslTests();')
        result = m.patch_build(fixture)
        self.assertIn('shared.link_z_max_page_size = 16384;', result)
        self.assertIn('require_video = b.option', result)
        self.assertLess(result.index('buildSingleTarget();'), result.index('andcode-library-only'))
        self.assertLess(result.index('return;'), result.index('addMuslTests();'))
        self.assertIn('if (target_option == null) @panic', result)
        with self.assertRaises(ValueError):
            m.patch_build(result)

    def test_nested_rejects_escape_and_links(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                           ('link', tarfile.SYMTYPE), ('hardlink', tarfile.LNKTYPE),
                           ('fifo', tarfile.FIFOTYPE), ('a\\b', tarfile.REGTYPE)]:
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode='w:gz') as t:
                info = tarfile.TarInfo(name)
                info.type = kind
                t.addfile(info)
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    m.unpack_nested(data.getvalue(), Path(tmp))

    def test_nested_duplicate_normalized_path(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as t:
            for name in ['yoga/LICENSE', 'yoga/./LICENSE']:
                info = tarfile.TarInfo(name)
                t.addfile(info)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                m.unpack_nested(data.getvalue(), Path(tmp))

    def test_nested_expansion_bound(self):
        entry = tarfile.TarInfo('huge')
        entry.size = 128 * 1024 * 1024 + 1
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(m.tarfile, 'open') as archive:
            archive.return_value.__enter__.return_value = [entry]
            with self.assertRaisesRegex(ValueError, 'bounds'):
                m.unpack_nested(b'', Path(tmp))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_nested_regular_file(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as t:
            info = tarfile.TarInfo('yoga/LICENSE')
            info.size = 3
            t.addfile(info, io.BytesIO(b'MIT'))
        with tempfile.TemporaryDirectory() as tmp:
            m.unpack_nested(data.getvalue(), Path(tmp))
            self.assertEqual((Path(tmp) / 'yoga/LICENSE').read_bytes(), b'MIT')

    def test_ffmpeg_dependency_inputs_and_gpl_guard(self):
        for mode in ['ok', 'gpl', 'gpl-wrapped', 'spdx', 'missing', 'escape', 'drift', 'target', 'empty']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                native = Path(tmp)
                cache = native / '.cache/ffmpeg'
                build = cache / 'build/aarch64-linux'
                (build / 'libavutil').mkdir(parents=True)
                (build / 'src').mkdir()
                prefix = cache / 'prefix/aarch64-linux'
                (prefix / 'objects/libavutil').mkdir(parents=True)
                item = 'objects/libavutil/fixture.o'
                (prefix / item).write_bytes(b'object')
                (build / 'libavutil/fixture.o').write_bytes(b'drift' if mode == 'drift' else b'object')
                text = 'GNU Lesser General Public License'
                if mode == 'gpl': text = 'GNU General Public License'
                if mode == 'gpl-wrapped': text = '/* GNU General Public\n * License */'
                if mode == 'spdx': text = '// SPDX-License-Identifier: GPL-2.0-or-later'
                (build / 'src/fixture.c').write_text(text)
                outside = native / 'outside.h'
                outside.write_bytes(b'outside')
                dependency = outside.as_posix() if mode == 'escape' else 'src/fixture.c'
                if mode != 'missing':
                    target = 'wrong.o' if mode == 'target' else 'libavutil/fixture.o'
                    (build / 'libavutil/fixture.d').write_text(target + ': ' + ('' if mode == 'empty' else dependency))
                if mode == 'ok':
                    report = m.ffmpeg_source_inputs(native, prefix, [item])
                    self.assertEqual(report['objectsWithoutDependencyFiles'], [])
                    self.assertEqual(report['files'][0]['sha256'], hashlib.sha256(text.encode()).hexdigest())
                else:
                    with self.assertRaises(ValueError):
                        m.ffmpeg_source_inputs(native, prefix, [item])

    def test_zlib_missing_depfiles_stay_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            native = Path(tmp)
            cache = native / '.cache/ffmpeg'
            build = cache / 'build/aarch64-linux/zlib'
            build.mkdir(parents=True)
            prefix = cache / 'prefix/aarch64-linux'
            (prefix / 'objects/libz').mkdir(parents=True)
            (build / 'fixture.o').write_bytes(b'zlib-object')
            item = 'objects/libz/fixture.o'
            (prefix / item).write_bytes(b'zlib-object')
            report = m.ffmpeg_source_inputs(native, prefix, [item])
            self.assertEqual(report['objectsWithoutDependencyFiles'], [item])
            self.assertEqual(report['files'], [])

    def test_media_generator_replay_exact_fail_closed_and_baseline_preserved(self):
        for mode in ['ok', 'drift', 'failed', 'timeout', 'input-mutation', 'baseline-mutation', 'next-input-mutation']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                cache = root / 'native/.cache/ffmpeg'
                build = cache / 'build/aarch64-linux/libswscale/aarch64'
                source = cache / 'sources/ffmpeg-9.0.2/libswscale/aarch64'
                build.mkdir(parents=True)
                source.mkdir(parents=True)
                (build / 'ops_asmgen').write_bytes(b'generator')
                (source / 'ops_asmgen.c').write_bytes(b'source')
                (source / 'Makefile').write_bytes(b'rules')
                for name, data in [('ops_lookup.gen.c', b'lookup'), ('ops_neon.gen.S', b'neon')]:
                    (build / name).write_bytes(data)
                output = root / 'output'
                output.mkdir()
                def run(command, **kwargs):
                    self.assertEqual(kwargs['cwd'], output / 'media-generator-replay')
                    self.assertEqual(kwargs['timeout'], 60)
                    if mode == 'input-mutation':
                        (source / 'ops_asmgen.c').write_bytes(b'changed')
                    if mode == 'baseline-mutation' and command[-1] == '-ops':
                        (build / 'ops_lookup.gen.c').write_bytes(b'changed')
                    if mode == 'next-input-mutation' and command[-1] == '-lookup':
                        (build / 'ops_neon.gen.S').write_bytes(b'changed')
                    if mode == 'timeout':
                        raise subprocess.TimeoutExpired(command, 60, stderr=b'partial diagnostic')
                    payload = b'lookup' if command[-1] == '-lookup' else b'neon'
                    return subprocess.CompletedProcess(command, 7 if mode == 'failed' else 0,
                                                       b'different' if mode == 'drift' else payload, b'diagnostic')
                with patch.object(m.subprocess, 'run', side_effect=run):
                    if mode == 'ok':
                        report = m.replay_media_generators(root / 'native', output, {})
                        self.assertEqual(len(report['outputs']), 2)
                        self.assertFalse(report['redistributionApproved'])
                        self.assertEqual((build / 'ops_lookup.gen.c').read_bytes(), b'lookup')
                        with self.assertRaises(FileExistsError):
                            m.replay_media_generators(root / 'native', output, {})
                    elif mode == 'failed':
                        with self.assertRaises(subprocess.CalledProcessError):
                            m.replay_media_generators(root / 'native', output, {})
                        self.assertTrue((output / 'media-generator-replay/lookup.log').exists())
                    elif mode == 'timeout':
                        with self.assertRaises(subprocess.TimeoutExpired):
                            m.replay_media_generators(root / 'native', output, {})
                        self.assertIn(b'partial diagnostic', (output / 'media-generator-replay/lookup.log').read_bytes())
                    else:
                        with self.assertRaises(ValueError):
                            m.replay_media_generators(root / 'native', output, {})

    def test_zlib_dependency_patch_is_exact_and_rejects_repeat(self):
        source = ('run(cc, [\n      `-I${zlibSource}`,\n      "-c",\n]);\n'
                  '  const result = spawnSync(command, args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] })\n'
                  '  if (result.status !== 0) throw new Error("failed")\n'
                  '  run("make", [`-j${Math.max(1, availableParallelism())}`], build)')
        modified = m.patch_zlib_dependencies(source)
        self.assertIn('"-MMD", "-MF", join(build, `${file}.d`)', modified)
        self.assertIn('"-MT", `zlib/${file}.o`', modified)
        self.assertIn('run("make", ["V=1",', modified)
        self.assertIn('JSON.stringify({ command, args, cwd })', modified)
        self.assertIn('maxBuffer: 16 * 1024 * 1024', modified)
        self.assertLess(modified.index('process.stdout.write(result.stdout)'),
                        modified.index('if (result.status !== 0)'))
        self.assertLess(modified.index('"-MMD"'), modified.index('"-c"'))
        for invalid in [modified, source + source, source.replace('"-c"', '"-S"')]:
            with self.assertRaises(ValueError): m.patch_zlib_dependencies(invalid)

    def test_zlib_emitted_dependencies_are_recorded_and_bound_to_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            native = Path(tmp)
            cache = native / '.cache/ffmpeg'
            build = cache / 'build/aarch64-linux/zlib'
            build.mkdir(parents=True)
            prefix = cache / 'prefix/aarch64-linux'
            (prefix / 'objects/libz').mkdir(parents=True)
            source = cache / 'sources/zlib-1.3.2'
            source.mkdir(parents=True)
            for name in ['fixture.c', 'zlib.h']:
                (source / name).write_text('/* zlib fixture */\n')
            (build / 'fixture.o').write_bytes(b'zlib-object')
            (prefix / 'objects/libz/fixture.o').write_bytes(b'zlib-object')
            dependencies = [(source / name).as_posix() for name in ['fixture.c', 'zlib.h']]
            (build / 'fixture.d').write_text('zlib/fixture.o: ' + ' \\\n '.join(dependencies))
            report = m.ffmpeg_source_inputs(native, prefix, ['objects/libz/fixture.o'])
            self.assertEqual(report['objectsWithoutDependencyFiles'], [])
            self.assertEqual(report['objects'][0]['dependencies'],
                             ['sources/zlib-1.3.2/' + name for name in ['fixture.c', 'zlib.h']])
            self.assertEqual(len(report['files']), 2)

    def test_media_log_requires_actual_compiler_stdout(self):
        command = 'ANDCODE_MEDIA_COMMAND ' + json.dumps(
            {'command': 'make', 'args': ['V=1', '-j2'], 'cwd': '/fixture/build'}) + '\n'
        output = 'cc -I. -c -o libavutil/crc.o src/libavutil/crc.c\n'
        m.verify_media_command_log(command + output)
        m.verify_media_command_log(command + 'cc -c src/libavutil/crc.c -o libavutil/crc.o\n')
        for invalid in [command, output, command + 'CC libavutil/crc.o\n',
                        command + output.replace('libavutil/crc.o', 'libavutil/crc.o.fake'),
                        command.replace('V=1', 'V=0') + output,
                        command + output.replace(' -c ', ' -S ')]:
            with self.subTest(log=invalid), self.assertRaises(ValueError):
                m.verify_media_command_log(invalid)

    def test_media_compile_commands_match_objects_sources_and_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            native = Path(tmp)
            cache = native / '.cache/ffmpeg'
            build = cache / 'build/aarch64-linux'
            prefix = cache / 'prefix/aarch64-linux'
            compiler = cache / 'toolchains/aarch64-linux/cc'
            compiler.parent.mkdir(parents=True)
            compiler.write_bytes(b'wrapper')
            objects = ['objects/libavutil/crc.o', 'objects/libz/adler32.o']
            deps = []
            for item, group, filename in [(objects[0], 'libavutil', 'crc'),
                                           (objects[1], 'zlib', 'adler32')]:
                (build / group).mkdir(parents=True, exist_ok=True)
                (build / group / (filename + '.o')).write_bytes(b'object')
                (build / group / (filename + '.c')).write_bytes(b'source')
                dest = prefix / item
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b'object')
                deps.append({'object': item, 'dependencies': [f'build/aarch64-linux/{group}/{filename}.c']})
            dependency = {'objects': deps, 'objectsWithoutDependencyFiles': []}
            make = 'ANDCODE_MEDIA_COMMAND ' + json.dumps(
                {'command': 'make', 'args': ['V=1'], 'cwd': str(build)}) + '\n'
            ffmpeg = shlex.join([str(compiler), '-c', '-o', 'libavutil/crc.o', 'libavutil/crc.c']) + '\n'
            zlib = 'ANDCODE_MEDIA_COMMAND ' + json.dumps({'command': str(compiler),
                'args': ['-c', str(build / 'zlib/adler32.c'), '-o', str(build / 'zlib/adler32.o')],
                'cwd': str(native)}) + '\n'
            log = make + ffmpeg + zlib
            report = m.media_compile_commands(log, native, prefix, objects, dependency)
            self.assertEqual(len(report['objects']), 2)
            self.assertEqual(report['objects'][0]['logLine'], 2)
            self.assertIs(report['redistributionApproved'], False)
            for invalid in [make + ffmpeg, log + ffmpeg, log.replace('V=1', 'V=0'),
                            log.replace('-c -o', '-c -c -o'),
                            log.replace(str(compiler), str(build / 'libavutil/crc.c'))]:
                with self.subTest(log=invalid), self.assertRaises(ValueError):
                    m.media_compile_commands(invalid, native, prefix, objects, dependency)
            with self.assertRaises(ValueError):
                m.media_compile_commands(log, native, prefix, objects + objects[:1], dependency)
            with self.assertRaises(ValueError):
                m.media_compile_commands(log, native, prefix, objects,
                    {'objects': [], 'objectsWithoutDependencyFiles': objects})
            deps[0]['dependencies'] = []
            with self.assertRaises(ValueError):
                m.media_compile_commands(log, native, prefix, objects, dependency)

    def test_crc_probe_requires_compilation_execution_and_marker(self):
        for mode in ['ok', 'compile-failed', 'run-failed', 'no-marker']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                calls = []

                def run(command, **kwargs):
                    calls.append(command)
                    self.assertEqual(kwargs['env'], {'fixture': 'clean'})
                    self.assertEqual(kwargs['timeout'], 60)
                    if len(calls) == 1:
                        self.assertIn('-Werror', command)
                        self.assertIn('-Wl,-z,max-page-size=16384', command)
                        self.assertIn(str(root / 'prefix/lib/libavutil.a'), command)
                        (root / 'crc-probe').write_bytes(b'probe')
                    failed = ((mode == 'compile-failed' and len(calls) == 1)
                              or (mode == 'run-failed' and len(calls) == 2))
                    stdout = '' if mode == 'no-marker' else m.CRC_MARKER + ' 2304 cases (Linux only)'
                    return subprocess.CompletedProcess(command, 1 if failed else 0, stdout, '')

                with patch.object(m.subprocess, 'run', side_effect=run):
                    if mode == 'ok':
                        report = m.probe_ffmpeg_crc(root / 'prefix', root, {'fixture': 'clean'})
                        self.assertEqual(report['cases'], 2304)
                        self.assertEqual(report['sourceSha256'], hashlib.sha256(m.CRC_PROBE.encode()).hexdigest())
                        self.assertEqual(report['binarySha256'], hashlib.sha256(b'probe').hexdigest())
                    else:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                            m.probe_ffmpeg_crc(root / 'prefix', root, {'fixture': 'clean'})
                self.assertEqual(len(calls), 1 if mode == 'compile-failed' else 2)

    def test_failure_keeps_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result, target = out / 'new.so', out / 'npm.so'
            result.write_bytes(b'new'); target.write_bytes(b'original')
            with patch.object(m.pty.audit, 'elf', return_value=(None, ['libz.so.1'])):
                with self.assertRaises(ValueError):
                    m.validate(result, target, out, {})
            self.assertEqual(target.read_bytes(), b'original')
            symbols = '\n'.join('1 GLOBAL FUNC ot_' + s for s in [
                'context_abi_version', 'context_create', 'context_destroy', 'video_open'])
            with patch.object(m.pty.audit, 'elf', return_value=(None, ['libc.so.6'])), \
                    patch.object(m.subprocess, 'check_output', return_value=symbols), \
                    patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'failed')):
                with self.assertRaises(subprocess.CalledProcessError):
                    m.validate(result, target, out, {})
            self.assertEqual(target.read_bytes(), b'original')

    def link_fixture(self, root):
        native, output = root / 'source', root / 'output'
        native.mkdir(); output.mkdir()
        global_cache, local_cache = root / 'global', root / 'local'
        global_cache.mkdir(); local_cache.mkdir()
        env = {'ZIG_GLOBAL_CACHE_DIR': str(global_cache), 'ZIG_LOCAL_CACHE_DIR': str(local_cache)}
        paths = [native / 'fixture.o', global_cache / 'libc++.a', local_cache / 'libc.so.6']
        for index, path in enumerate(paths):
            path.write_bytes(f'input-{index}'.encode())
        result = local_cache / 'libopentui.so'
        result.write_bytes(b'linked')
        arguments = ['ld.lld', '-shared', '-z', 'max-page-size=16384', '-o', str(result),
                     '-soname', 'libopentui.so', *map(str, paths)]
        return native, output, env, arguments, paths

    def test_retains_ordered_link_inputs_and_toolchain_libraries(self):
        with tempfile.TemporaryDirectory() as tmp:
            native, output, env, args, paths = self.link_fixture(Path(tmp))
            report = m.retain_link_inputs('diagnostics\n  ' + shlex.join(args) + '\n', native, output, env)
            self.assertEqual(report['command'], args)
            self.assertEqual([r['path'] for r in report['inputs']], list(map(str, paths)))
            self.assertEqual([r['scope'] for r in report['inputs']],
                             ['opentui-source-build', 'zig-global-cache', 'zig-local-cache'])
            for row, path in zip(report['inputs'], paths):
                retained = output / row['retainedPath']
                self.assertEqual(retained.read_bytes(), path.read_bytes())
                self.assertEqual(row['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(row['bytes'], path.stat().st_size)

    def test_link_command_drift_and_unsafe_inputs_fail_closed(self):
        for mode in ['missing', 'multiple', 'response', 'relative', 'option', 'escape',
                     'bad-output', 'no-output', 'missing-file', 'bad-value']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                native, output, env, args, paths = self.link_fixture(root)
                if mode == 'response': args.append('@hidden.rsp')
                if mode == 'relative': args.append('relative.o')
                if mode == 'option': args.append('--whole-archive')
                if mode == 'escape':
                    outside = root / 'outside.a'
                    outside.write_bytes(b'outside')
                    args.append(str(outside))
                if mode == 'bad-output': args[5] = str(paths[0])
                if mode == 'no-output': del args[4:6]
                if mode == 'missing-file': args.append(str(native / 'missing.a'))
                if mode == 'bad-value': args[3] = 'max-page-size=4096'
                text = shlex.join(args)
                if mode == 'missing': text = ''
                if mode == 'multiple': text += '\n' + text
                with self.assertRaises((ValueError, FileNotFoundError)):
                    m.retain_link_inputs(text, native, output, env)
                self.assertFalse((output / 'link-inputs').exists())

    def test_generated_builtin_snapshots_keep_separate_cache_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / 'output'
            output.mkdir()
            env = {}
            for label, key in [('global', 'ZIG_GLOBAL_CACHE_DIR'), ('local', 'ZIG_LOCAL_CACHE_DIR')]:
                cache = root / label
                path = cache / 'b' / ('a' * 32) / 'builtin.zig'
                path.parent.mkdir(parents=True)
                path.write_bytes(('// generated fixture ' + label + '\n').encode())
                env[key] = str(cache)
            report = m.retain_zig_generated_sources(output, env)
            self.assertEqual(len(report['files']), 2)
            for row in report['files']:
                payload = (output / row['retainedPath']).read_bytes()
                self.assertEqual(payload, Path(row['path']).read_bytes())
                self.assertEqual(len(payload), row['bytes'])
                self.assertEqual(hashlib.sha256(payload).hexdigest(), row['sha256'])
                self.assertIn('/' + row['scope'] + '/b/', row['retainedPath'])
            self.assertIs(report['sourceAttributionApproved'], False)
            self.assertIs(report['redistributionApproved'], False)
            with self.assertRaises(FileExistsError):
                m.retain_zig_generated_sources(output, env)

    def test_generated_builtin_snapshots_reject_unsafe_or_missing_inputs(self):
        for mode in ['empty', 'path', 'elf', 'utf8', 'large', 'cache-link',
                     'directory-link', 'entry-link', 'file-link', 'count']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                output = root / 'output'
                output.mkdir()
                cache = root / 'cache'
                entry = cache / 'b' / ('unexpected' if mode == 'path' else 'a' * 32)
                entry.mkdir(parents=True)
                path = entry / 'builtin.zig'
                payload = b'// fixture builtin\n'
                if mode == 'elf':payload = b'\x7fELFfake'
                if mode == 'utf8':payload = b'\xff'
                if mode == 'large':payload = b' ' * (4 * 1024 * 1024 + 1)
                if mode != 'empty':path.write_bytes(payload)
                env = {'ZIG_GLOBAL_CACHE_DIR': str(cache), 'ZIG_LOCAL_CACHE_DIR': str(cache)}
                links = {'cache-link': cache, 'directory-link': cache / 'b',
                         'entry-link': entry, 'file-link': path}
                original_is_symlink = Path.is_symlink
                original_iterdir = Path.iterdir
                def linked(p):
                    return p == links.get(mode) or original_is_symlink(p)
                def entries(p):
                    return iter([entry] * 10001) if mode == 'count' and p == cache / 'b' else original_iterdir(p)
                with patch.object(Path, 'is_symlink', linked), patch.object(Path, 'iterdir', entries):
                    with self.assertRaises((ValueError, UnicodeDecodeError)):
                        m.retain_zig_generated_sources(output, env)
                self.assertFalse((output / 'zig-generated-sources').exists())

    def test_notice_candidates_keep_late_exact_comments_and_outside_lines(self):
        content = (b'/* ordinary comment */\n' + b'\n' * 110
                   + '/* Copyright \u00a9 Fixture\n Permission granted\n */\n'.encode()
                   + b'// SPDX-License-Identifier: MIT\n'
                   + b'const char *s = "copyright metadata";\n')
        candidates = m.notice_candidates(content)
        self.assertEqual(len(candidates['comments']), 1)
        item = candidates['comments'][0]
        raw = content[item['offset']:item['offset'] + item['bytes']]
        self.assertEqual(raw.decode(), item['text'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])
        self.assertEqual(item['line'], 112)
        self.assertEqual(len(candidates['outsideCommentLines']), 2)
        self.assertEqual(m.notice_candidates(b'no declaration'), {'comments': [], 'outsideCommentLines': []})

    def test_notice_report_is_bound_to_dependency_bytes_without_approval(self):
        for mode in ['ok', 'changed', 'escape']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                cache = root / 'native/.cache/ffmpeg'
                cache.mkdir(parents=True)
                output = root / 'output'
                output.mkdir()
                content = b'/* Copyright Fixture; permission granted. */\n'
                (cache / 'fixture.c').write_bytes(content)
                (root / 'outside.c').write_bytes(content)
                row = {'path': '../../../../outside.c' if mode == 'escape' else 'fixture.c',
                       'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
                if mode == 'changed':(cache / 'fixture.c').write_bytes(b'changed')
                if mode != 'ok':
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        m.retain_ffmpeg_notices(root / 'native', {'files': [row]}, output)
                    self.assertFalse((output / 'ffmpeg-notice-candidates.json').exists())
                else:
                    report = m.retain_ffmpeg_notices(root / 'native', {'files': [row]}, output)
                    payload = (output / report['path']).read_bytes()
                    self.assertEqual(hashlib.sha256(payload).hexdigest(), report['sha256'])
                    document = json.loads(payload)
                    self.assertIs(document['redistributionApproved'], False)
                    self.assertIs(report['redistributionApproved'], False)
                    self.assertEqual(document['files'][0]['comments'][0]['text'].encode(), content.rstrip())

    def test_same_linker_replay_requires_exact_bytes_reports_and_abi(self):
        for mode in ['ok', 'changed-input', 'compile-failed', 'different-output',
                     'missing-map', 'bad-extraction', 'abi-failed', 'abi-marker']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                native, output, env, args, paths = self.link_fixture(root)
                link = m.retain_link_inputs(shlex.join(args), native, output, env)
                result = Path(link['output'])
                if mode == 'changed-input':
                    (output / link['inputs'][0]['retainedPath']).write_bytes(b'tampered')
                calls = []

                def run(command, **kwargs):
                    calls.append(command)
                    self.assertEqual(kwargs['env'], env)
                    directory = output / 'link-replay'
                    if len(calls) == 1:
                        self.assertEqual(command[:2], ['fixed-zig', 'ld.lld'])
                        for item in link['inputs']:
                            self.assertEqual(command[item['argumentIndex'] + 1],
                                             str((output / item['retainedPath']).resolve()))
                        self.assertIn('--Map=' + str(directory / 'link.map'), command)
                        self.assertIn('--why-extract=' + str(directory / 'archive-extraction.tsv'), command)
                        self.assertEqual(kwargs['timeout'], 120)
                        (directory / 'libopentui.so').write_bytes(b'different' if mode == 'different-output' else b'linked')
                        if mode != 'missing-map': (directory / 'link.map').write_text('fixture map')
                        (directory / 'archive-extraction.tsv').write_text(
                            'bad' if mode == 'bad-extraction' else 'reference\textracted\tsymbol\n')
                    else:
                        self.assertEqual(command, ['bun', str(output / 'probe.mjs'), str(directory / 'libopentui.so')])
                        self.assertEqual(kwargs['timeout'], 30)
                    failure = ((mode == 'compile-failed' and len(calls) == 1)
                               or (mode == 'abi-failed' and len(calls) == 2))
                    return subprocess.CompletedProcess(command, 1 if failure else 0,
                                                       '' if mode == 'abi-marker' else m.MARKER, '')

                with patch.object(m.subprocess, 'run', side_effect=run), \
                        patch.object(m.pty.audit, 'elf', return_value=(None, ['libc.so.6'])):
                    if mode == 'ok':
                        report = m.replay_link_inputs(link, Path('fixed-zig'), result, output, env)
                        self.assertTrue(report['byteIdentical'])
                        self.assertEqual(report['inputCount'], 3)
                        self.assertEqual(len(report['files']), 5)
                        for row in report['files']:
                            payload = (output / row['path']).read_bytes()
                            self.assertEqual(row['bytes'], len(payload))
                            self.assertEqual(row['sha256'], hashlib.sha256(payload).hexdigest())
                    else:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                            m.replay_link_inputs(link, Path('fixed-zig'), result, output, env)
                self.assertEqual(result.read_bytes(), b'linked')
                self.assertEqual(len(calls), 0 if mode == 'changed-input' else 2 if mode in (
                    'ok', 'abi-failed', 'abi-marker') else 1)

    def test_link_input_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native, output, env, args, paths = self.link_fixture(root)
            outside = root / 'outside.a'
            outside.write_bytes(b'outside')
            link = native / 'link.a'
            try:
                link.symlink_to(outside)
            except OSError as error:
                self.skipTest('Host cannot create symlinks: ' + str(error))
            args.append(str(link))
            with self.assertRaises(ValueError):
                m.retain_link_inputs(shlex.join(args), native, output, env)

    CRC_FIXTURE = (b'/* upstream license fixture */\n#include "config.h"\n#include "crc.h"\n'
                   b'int av_crc_init(void) { return 0; }\n'
                   b'const AVCRC *av_crc_get_table(void) { return 0; }\n'
                   b'uint32_t av_crc(const AVCRC *ctx, uint32_t crc,\n'
                   b'                const uint8_t *buffer, size_t length)\n{\n return crc;\n}\n')

    def test_modified_crc_transform_pins_bytes_preserves_header_and_changes_calls(self):
        with patch.object(m, 'CRC_SOURCE_SHA256', hashlib.sha256(self.CRC_FIXTURE).hexdigest()):
            modified = m.modified_crc_source(self.CRC_FIXTURE)
            self.assertTrue(modified.startswith(b'/* upstream license fixture */\n'))
            self.assertIn(b'Modified by andcode on 2026-11-10', modified)
            self.assertIn(b'#undef av_pure\n#define av_pure', modified)
            self.assertEqual(modified.count(b'++andcode_crc_calls;'), 1)
            self.assertEqual(modified.count(b'__attribute__((visibility("default")))'), 4)
            for invalid in [modified, self.CRC_FIXTURE + b'drift']:
                with self.assertRaises(ValueError):
                    m.modified_crc_source(invalid)

    def test_modified_crc_relink_requires_single_substitution_and_final_library_execution(self):
        modes = ['ok', 'missing-object', 'duplicate-object', 'changed-input', 'compile-failed',
                 'wrong-source', 'unchanged-object', 'link-failed', 'unchanged-library',
                 'missing-map', 'bad-extraction', 'wrong-map', 'dependencies',
                 'abi-failed', 'abi-marker', 'probe-compile', 'probe-run', 'probe-marker']
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                native, output, env, args, paths = self.link_fixture(Path(tmp))
                cache = native / '.cache/ffmpeg'
                source = cache / 'sources/ffmpeg-9.0.2/libavutil/crc.c'
                source.parent.mkdir(parents=True)
                source.write_bytes(self.CRC_FIXTURE)
                build = cache / 'build/aarch64-linux'
                (build / 'libavutil').mkdir(parents=True)
                (build / 'libavutil/crc.o').write_bytes(b'original-object')
                crc = cache / 'prefix/aarch64-linux/objects/libavutil/crc.o'
                crc.parent.mkdir(parents=True)
                crc.write_bytes(b'original-object')
                args.append(str(crc))
                link = m.retain_link_inputs(shlex.join(args), native, output, env)
                result = Path(link['output'])
                if mode == 'missing-object': link['inputs'].pop()
                if mode == 'duplicate-object': link['inputs'].append(dict(link['inputs'][-1]))
                if mode == 'changed-input': (output / link['inputs'][0]['retainedPath']).write_bytes(b'drift')
                directory = output / 'modified-crc-relink'
                calls = []

                def run(command, **kwargs):
                    calls.append(command)
                    index = len(calls)
                    self.assertEqual(kwargs['env'], env)
                    stdout = ''
                    if index == 1:
                        self.assertEqual(command[:3], ['make', '-C', str(directory / 'build')])
                        self.assertIn('SRC_LINK=' + str(directory / 'source'), command)
                        self.assertFalse((directory / 'build/libavutil/crc.o').exists())
                        self.assertEqual((directory / 'source/libavutil/crc.c').read_bytes(),
                                         m.modified_crc_source(self.CRC_FIXTURE))
                        (directory / 'build/libavutil/crc.o').write_bytes(
                            b'original-object' if mode == 'unchanged-object' else b'modified-object')
                        (directory / 'build/libavutil/crc.d').write_bytes(b'fixture dependency')
                        stdout = '' if mode == 'wrong-source' else str(directory / 'source/libavutil/crc.c')
                    elif index == 2:
                        self.assertEqual(command[:2], ['fixed-zig', 'ld.lld'])
                        for row in link['inputs']:
                            expected = directory / 'crc.o' if row['path'] == str(crc) else output / row['retainedPath']
                            self.assertEqual(command[row['argumentIndex'] + 1], str(expected))
                        (directory / 'libopentui.so').write_bytes(b'linked' if mode == 'unchanged-library' else b'modified-library')
                        if mode != 'missing-map':
                            (directory / 'link.map').write_text('wrong' if mode == 'wrong-map' else str(directory / 'crc.o'))
                        (directory / 'archive-extraction.tsv').write_text(
                            'wrong' if mode == 'bad-extraction' else 'reference\textracted\tsymbol\n')
                    elif index == 3:
                        self.assertEqual(command, ['bun', str(directory / 'probe.mjs'), str(directory / 'libopentui.so')])
                        stdout = '' if mode == 'abi-marker' else m.MARKER
                    elif index == 4:
                        self.assertIn(str(directory / 'libopentui.so'), command)
                        self.assertNotIn(str(cache / 'prefix/aarch64-linux/lib/libavutil.a'), command)
                        probe = (directory / 'crc-probe.c').read_text()
                        self.assertIn('(*volatile modified_crc)', probe)
                        self.assertIn('andcode_crc_relink_calls() != cases * 3', probe)
                        (directory / 'crc-probe').write_bytes(b'probe')
                    else:
                        self.assertEqual(command, [str(directory / 'crc-probe')])
                        stdout = m.CRC_MARKER + ' 2304 cases (Linux only)\n'
                        if mode != 'probe-marker': stdout += 'ANDCODE_MODIFIED_CRC_RELINK_OK 6912 calls (Linux only)\n'
                    failed = {1: 'compile-failed', 2: 'link-failed', 3: 'abi-failed',
                              4: 'probe-compile', 5: 'probe-run'}.get(index) == mode
                    return subprocess.CompletedProcess(command, int(failed), stdout, '')

                def elf(payload):
                    return None, ['wrong.so' if mode == 'dependencies' and payload == b'modified-library' else 'libc.so.6']

                with patch.object(m, 'CRC_SOURCE_SHA256', hashlib.sha256(self.CRC_FIXTURE).hexdigest()), \
                        patch.object(m.subprocess, 'run', side_effect=run), patch.object(m.pty.audit, 'elf', side_effect=elf):
                    if mode == 'ok':
                        report = m.probe_modified_crc_relink(native, link, Path('fixed-zig'), result, output, env)
                        self.assertEqual(len(calls), 5)
                        self.assertEqual(report['inputCount'], 4)
                        self.assertEqual(report['modifiedCalls'], 6912)
                        for flag in ['redistributionApproved', 'androidApproved', 'relinkingApproved']:
                            self.assertIs(report[flag], False)
                        for row in report['files']:
                            payload = (output / row['path']).read_bytes()
                            self.assertEqual(hashlib.sha256(payload).hexdigest(), row['sha256'])
                    else:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                            m.probe_modified_crc_relink(native, link, Path('fixed-zig'), result, output, env)
                self.assertEqual(result.read_bytes(), b'linked')
                self.assertEqual(source.read_bytes(), self.CRC_FIXTURE)
                self.assertEqual((build / 'libavutil/crc.o').read_bytes(), b'original-object')

    def resource_archive(self, entries):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:xz') as archive:
            for name, content in entries:
                item = tarfile.TarInfo(name)
                item.size = len(content)
                archive.addfile(item, io.BytesIO(content))
        return data.getvalue()

    def resource_entries(self):
        return [('zig/' + name, ('fixture-' + name).encode()) for name in [
            'LICENSE', 'lib/libcxx/LICENSE.TXT', 'lib/libcxxabi/LICENSE.TXT',
            'lib/libunwind/LICENSE.TXT', 'lib/libc/glibc/LICENSES', 'lib/compiler_rt.zig']]

    def test_zig_resources_keep_source_bytes_but_not_tool_binary(self):
        entries = self.resource_entries()
        data = self.resource_archive(entries + [('zig/zig', b'\x7fELFtool')])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'tool.tar.xz'
            path.write_bytes(data)
            with patch.object(m, 'ZIG_SHA256', hashlib.sha256(data).hexdigest()):
                result = m.retain_zig_resources(path, root)
            self.assertEqual(len(result['files']), len(entries))
            with tarfile.open(root / result['archive']) as archive:
                self.assertEqual(set(archive.getnames()), {n.partition('/')[2] for n, _ in entries})
                for row in result['files']:
                    content = archive.extractfile(row['path']).read()
                    self.assertEqual(hashlib.sha256(content).hexdigest(), row['sha256'])

    def test_zig_resources_reject_digest_paths_duplicates_elf_and_missing_notices(self):
        for mode in ['digest', 'path', 'duplicate', 'elf', 'missing']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                entries = self.resource_entries()
                if mode == 'path': entries.append(('zig/lib/../escape', b'bad'))
                if mode == 'duplicate': entries.append(entries[0])
                if mode == 'elf': entries.append(('zig/lib/binary', b'\x7fELFbad'))
                if mode == 'missing': entries.pop()
                data = self.resource_archive(entries)
                root = Path(tmp)
                path = root / 'tool.tar.xz'
                path.write_bytes(data)
                with patch.object(m, 'ZIG_SHA256', '0' * 64 if mode == 'digest' else hashlib.sha256(data).hexdigest()):
                    with self.assertRaises(ValueError):
                        m.retain_zig_resources(path, root)

    def test_zig_resources_reject_links(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:xz') as archive:
            item = tarfile.TarInfo('zig/lib/link')
            item.type = tarfile.SYMTYPE
            item.linkname = '/outside'
            archive.addfile(item)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'tool.tar.xz'
            path.write_bytes(data.getvalue())
            with patch.object(m, 'ZIG_SHA256', hashlib.sha256(data.getvalue()).hexdigest()):
                with self.assertRaisesRegex(ValueError, 'link or special'):
                    m.retain_zig_resources(path, root)

    def test_exports_probe_and_success_gate(self):
        symbols = '\n'.join('1 GLOBAL FUNC ot_' + s for s in [
            'context_abi_version', 'context_create', 'context_destroy', 'video_open'])
        for exported, output, succeeds in [('', m.MARKER, False),
                                           (symbols, '', False), (symbols, m.MARKER, True)]:
            with self.subTest(exports=bool(exported), marker=bool(output)), \
                    tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result, target = root / 'new.so', root / 'npm.so'
                result.write_bytes(b'new'); target.write_bytes(b'original')
                with patch.object(m.pty.audit, 'elf', return_value=(None, ['libc.so.6'])), \
                        patch.object(m.subprocess, 'check_output', return_value=exported), \
                        patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, output, '')):
                    if succeeds:
                        self.assertEqual(m.validate(result, target, root, {}), ['libc.so.6'])
                    else:
                        with self.assertRaises(ValueError):
                            m.validate(result, target, root, {})
                self.assertEqual(target.read_bytes(), b'new' if succeeds else b'original')

    def test_build_retains_inputs_and_does_not_approve_distribution(self):
        for failure in [None, 'build', 'media-log', 'compile-command', 'objects', 'configuration', 'source-license', 'crc-object', 'missing-zlib-dependencies', 'generator-replay', 'crc-probe', 'link', 'link-output', 'replay', 'modified-relink', 'generated']:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                upstream, stage, source = root / 'upstream', root / 'stage', root / 'source'
                stage.mkdir()
                native = source / 'packages/native'
                (native / 'src/vendor').mkdir(parents=True)
                (native / 'scripts').mkdir()
                (native / 'src/vendor/zig-deps.tar.gz').write_bytes(b'nested')
                (native / 'build.zig').write_text(
                    '    if (target.result.os.tag == .linux and optimize != .debug) shared.build_id = .sha1;\n'
                    '    // Test step (native only)')
                (native / 'scripts/build-ffmpeg.ts').write_text(
                     '  await download(NASM_URL, nasmArchive, NASM_SHA256, "NASM")\n'
                     '    "--disable-gpl",\n      `-I${zlibSource}`,\n      "-c",\n'
                     '  const result = spawnSync(command, args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] })\n'
                    '  run("make", [`-j${Math.max(1, availableParallelism())}`], build)')
                target = upstream / 'node_modules/.bun/@opentui+core-linux-arm64@0.8.1/node_modules/@opentui/core-linux-arm64/libopentui.so'
                target.parent.mkdir(parents=True)
                target.write_bytes(b'original')
                zig = root / 'zig/tool/zig'
                zig.parent.mkdir(parents=True)
                zig.write_bytes(b'tool')
                (zig.parent.parent / 'zig.tar.xz').write_bytes(b'tool archive')

                def run(command, **kwargs):
                    env = kwargs['env']
                    self.assertNotIn('NODE_TLS_REJECT_UNAUTHORIZED', env)
                    self.assertTrue(env['ZIG_GLOBAL_CACHE_DIR'].endswith('opentui-zig-cache'))
                    self.assertTrue(env['ZIG_LOCAL_CACHE_DIR'].endswith('opentui-zig-local-cache'))
                    self.assertEqual(kwargs['cwd'], native)
                    if command[0] == 'bun':
                        prefix = native / '.cache/ffmpeg/prefix/aarch64-linux'
                        (prefix / 'objects/libavutil').mkdir(parents=True)
                        (prefix / 'objects/libavutil/fixture.o').write_bytes(b'object')
                        (prefix / 'objects.txt').write_text(
                            '../escape.o\n' if failure == 'objects' else 'objects/libavutil/fixture.o\n')
                        if failure == 'crc-object':
                            (prefix / 'objects.txt').write_text('objects/libavutil/aarch64/crc.o\n')
                        (prefix.parent / 'escape.o').write_bytes(b'outside')
                        build = native / '.cache/ffmpeg/build/aarch64-linux'
                        (build / 'ffbuild').mkdir(parents=True)
                        (build / 'libavutil').mkdir()
                        (build / 'libavutil/fixture.o').write_bytes(b'object')
                        (build / 'libavutil/fixture.c').write_text('GNU Lesser General Public License')
                        if failure == 'source-license':
                            (build / 'libavutil/fixture.c').write_text('GNU General Public License')
                        (build / 'libavutil/fixture.d').write_text('libavutil/fixture.o: libavutil/fixture.c')
                        compiler = native / '.cache/ffmpeg/toolchains/aarch64-linux/cc'
                        compiler.parent.mkdir(parents=True)
                        compiler.write_bytes(b'wrapper')
                        if failure != 'media-log':
                            kwargs['stdout'].write('ANDCODE_MEDIA_COMMAND ' + json.dumps(
                                {'command': 'make', 'args': ['V=1', '-j2'], 'cwd': str(build)})
                                + '\ncc -c -o libavutil/crc.o src/libavutil/crc.c\n'
                                + ('' if failure == 'compile-command' else
                                   shlex.join([str(compiler), '-c', '-o', 'libavutil/fixture.o',
                                               'libavutil/fixture.c']) + '\n'))
                        if failure == 'missing-zlib-dependencies':
                            (prefix / 'objects/libz').mkdir()
                            (prefix / 'objects/libz/fixture.o').write_bytes(b'zlib-object')
                            (build / 'zlib').mkdir()
                            (build / 'zlib/fixture.o').write_bytes(b'zlib-object')
                            with (prefix / 'objects.txt').open('a') as listing:
                                listing.write('objects/libz/fixture.o\n')
                        self.assertIn('"--disable-armv8",', (native / 'scripts/build-ffmpeg.ts').read_text())
                        self.assertIn('"--disable-arm-crc",', (native / 'scripts/build-ffmpeg.ts').read_text())
                        self.assertIn('"--disable-pmull",', (native / 'scripts/build-ffmpeg.ts').read_text())
                        self.assertIn('"-MT", `zlib/${file}.o`', (native / 'scripts/build-ffmpeg.ts').read_text())
                        for name in ['config.h', 'ffbuild/config.mak', 'ffbuild/config.log']:
                            (build / name).write_text(self.CONFIG if name == 'config.h' else 'config fixture')
                        if failure == 'configuration':
                            (build / 'config.h').write_text(self.CONFIG.replace('CONFIG_GPL 0', 'CONFIG_GPL 1'))
                    else:
                        self.assertIn('-Drequire-video=true', command)
                        self.assertIn('-Dandcode-library-only=true', command)
                        self.assertIn('-Dlibrary-target=aarch64-linux-gnu.2.17', command)
                        if failure == 'build':
                            raise subprocess.CalledProcessError(1, command)
                        result = native / 'lib/aarch64-linux/libopentui.so'
                        result.parent.mkdir(parents=True)
                        result.write_bytes(b'rebuilt')
                        cache = Path(env['ZIG_LOCAL_CACHE_DIR'])
                        cache.mkdir()
                        Path(env['ZIG_GLOBAL_CACHE_DIR']).mkdir()
                        builtin = cache / 'b' / ('a' * 32) / 'builtin.zig'
                        builtin.parent.mkdir(parents=True)
                        if failure != 'generated':builtin.write_bytes(b'// fixture builtin\n')
                        linked = cache / 'libopentui.so'
                        linked.write_bytes(b'drift' if failure == 'link-output' else b'rebuilt')
                        obj = cache / 'fixture.o'
                        obj.write_bytes(b'linked object')
                        args = ['ld.lld', '-shared', '-o', str(linked), str(obj)]
                        kwargs['stdout'].write('unexpected linker' if failure == 'link' else shlex.join(args))
                    return subprocess.CompletedProcess(command, 0)

                def validate(result, target, output, env):
                    self.assertEqual(result, native / 'lib/aarch64-linux/libopentui.so')
                    target.write_bytes(result.read_bytes())
                    return ['libc.so.6']

                with ExitStack() as stack:
                    # Register mocks dynamically to stay below Python 3.12's
                    # static block limit while retaining LIFO cleanup on failure.
                    mocks = [
                        patch.object(m.sys, 'platform', 'linux'),
                        patch.object(m.platform, 'machine', return_value='aarch64'),
                        patch.object(m, 'ORIGINAL', hashlib.sha256(b'original').hexdigest()),
                        patch.object(m, 'ZIG_SHA256', hashlib.sha256(b'tool archive').hexdigest()),
                        patch.object(m, 'retain_zig_resources', return_value={'archive': 'fixture'}),
                        patch.object(m.shutil, 'which', return_value=str(zig)),
                        patch.object(m.pty.rust.sources, 'download_archive', return_value=b'archive'),
                        patch.object(m.pty.rust.sources, 'inspect_archive', return_value={}),
                        patch.object(m.pty.rust, 'unpack_candidate', return_value=source),
                        patch.object(m, 'unpack_nested'),
                        patch.object(m, 'replay_media_generators', return_value={'outputs': ['lookup', 'neon']},
                                     side_effect=ValueError('Generator replay failed') if failure == 'generator-replay' else None),
                        patch.object(m, 'probe_ffmpeg_crc', return_value={'cases': 2304},
                                     side_effect=ValueError('CRC probe failed') if failure == 'crc-probe' else None),
                        patch.object(m, 'replay_link_inputs', return_value={'byteIdentical': True},
                                     side_effect=ValueError('Replay failed') if failure == 'replay' else None),
                        patch.object(m, 'probe_modified_crc_relink', return_value={'modifiedCalls': 6912},
                                     side_effect=ValueError('Modified relink failed') if failure == 'modified-relink' else None),
                        patch.object(m.subprocess, 'check_output', return_value='0.17.0'),
                        patch.object(m.subprocess, 'run', side_effect=run),
                    ]
                    for mock in mocks:
                        stack.enter_context(mock)
                    probe = stack.enter_context(patch.object(m, 'validate', side_effect=validate))
                    if failure:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                            m.build(upstream, stage)
                        probe.assert_not_called()
                        self.assertEqual(target.read_bytes(), b'original')
                        self.assertFalse((stage / 'native-opentui-build-review.json').exists())
                    else:
                        m.build(upstream, stage)
                        report = json.loads((stage / 'native-opentui-build-review.json').read_text())
                        for key in ['redistributionApproved', 'androidApproved', 'originalNpmBinaryCorrespondenceProven']:
                            self.assertIs(report[key], False)
                        self.assertEqual(report['ffmpegObjects'][0]['sha256'], hashlib.sha256(b'object').hexdigest())
                        self.assertEqual(report['rebuiltSha256'], hashlib.sha256(b'rebuilt').hexdigest())
                        self.assertEqual(report['finalLink']['inputs'][0]['sha256'],
                                         hashlib.sha256(b'linked object').hexdigest())
                        self.assertEqual(len(report['zigGeneratedSources']['files']), 1)
                        self.assertEqual(report['modifiedCrcRelink']['modifiedCalls'], 6912)
                        self.assertEqual(len(report['ffmpegGeneratorReplay']['outputs']), 2)
                        self.assertEqual(len(report['ffmpegCompileCommands']['objects']), 1)
                        self.assertIs(report['zigGeneratedSources']['sourceAttributionApproved'], False)
                        self.assertEqual(target.read_bytes(), b'rebuilt')


if __name__ == '__main__':
    unittest.main()
