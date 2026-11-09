import importlib.util
import hashlib
import io
import json
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
              '#define CONFIG_NETWORK 0\n#define CONFIG_ZLIB 1\n')

    def test_ffmpeg_configuration_drift_rejected(self):
        self.assertEqual(m.ffmpeg_configuration(self.CONFIG)['CONFIG_GPL'], '0')
        for changed in [self.CONFIG.replace('CONFIG_GPL 0', 'CONFIG_GPL 1'),
                        self.CONFIG.replace('CONFIG_NONFREE 0', 'CONFIG_NONFREE 1'),
                        self.CONFIG.replace('CONFIG_NETWORK 0', 'CONFIG_NETWORK 1'),
                        self.CONFIG.replace('CONFIG_ZLIB 1', 'CONFIG_ZLIB 0'),
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
        for failure in [None, 'build', 'objects', 'configuration']:
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
                    '  await download(NASM_URL, nasmArchive, NASM_SHA256, "NASM")')
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
                        (prefix / 'objects').mkdir(parents=True)
                        (prefix / 'objects/fixture.o').write_bytes(b'object')
                        (prefix / 'objects.txt').write_text(
                            '../escape.o\n' if failure == 'objects' else 'objects/fixture.o\n')
                        (prefix.parent / 'escape.o').write_bytes(b'outside')
                        build = native / '.cache/ffmpeg/build/aarch64-linux'
                        (build / 'ffbuild').mkdir(parents=True)
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
                    return subprocess.CompletedProcess(command, 0)

                def validate(result, target, output, env):
                    self.assertEqual(result, native / 'lib/aarch64-linux/libopentui.so')
                    target.write_bytes(result.read_bytes())
                    return ['libc.so.6']

                with patch.object(m.sys, 'platform', 'linux'), \
                        patch.object(m.platform, 'machine', return_value='aarch64'), \
                        patch.object(m, 'ORIGINAL', hashlib.sha256(b'original').hexdigest()), \
                        patch.object(m, 'ZIG_SHA256', hashlib.sha256(b'tool archive').hexdigest()), \
                        patch.object(m.shutil, 'which', return_value=str(zig)), \
                        patch.object(m.pty.rust.sources, 'download_archive', return_value=b'archive'), \
                        patch.object(m.pty.rust.sources, 'inspect_archive', return_value={}), \
                        patch.object(m.pty.rust, 'unpack_candidate', return_value=source), \
                        patch.object(m, 'unpack_nested'), \
                        patch.object(m.subprocess, 'check_output', return_value='0.17.0'), \
                        patch.object(m.subprocess, 'run', side_effect=run), \
                        patch.object(m, 'validate', side_effect=validate) as probe:
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
                        self.assertEqual(target.read_bytes(), b'rebuilt')


if __name__ == '__main__':
    unittest.main()
