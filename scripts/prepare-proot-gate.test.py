#!/usr/bin/env python3
"""Synthetic archive tests; no download and no device/root required."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("prepare_gate", Path(__file__).with_name("prepare-proot-gate.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def entry(name, kind=tarfile.REGTYPE, link="", mode=0o755, data=b"\x7fELF\x00test"):
    item = tarfile.TarInfo(name)
    item.type, item.linkname, item.mode = kind, link, mode
    item.size = len(data) if item.isfile() else 0
    return item, data


class PrepareGateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "input.tar.gz"
        self.output = Path(self.temp.name) / "output.tar.gz"

    def archive(self, *items):
        with tarfile.open(self.source, "w:gz", format=tarfile.PAX_FORMAT) as archive:
            for item, data in items:
                archive.addfile(item, io.BytesIO(data) if item.isfile() else None)
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        mock = patch.object(gate, "BASE_SHA256", digest)
        mock.start()
        self.addCleanup(mock.stop)

    def reject(self, *items):
        self.archive(*items)
        with self.assertRaises(ValueError):
            gate.prepare(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_preserves_bytes_and_strips_privilege_bits(self):
        self.archive(entry("usr/bin/bash", mode=0o6755))
        digest = gate.prepare(self.source, self.output)
        self.assertEqual(digest, hashlib.sha256(self.output.read_bytes()).hexdigest())
        with tarfile.open(self.output) as archive:
            self.assertEqual(archive.extractfile("usr/bin/bash").read(), b"\x7fELF\x00test")
            self.assertEqual(archive.getmember("usr/bin/bash").mode, 0o755)

    def test_absolute_symlink_becomes_guest_relative(self):
        self.archive(entry("usr/bin/sh", tarfile.SYMTYPE, "/usr/bin/bash"))
        gate.prepare(self.source, self.output)
        with tarfile.open(self.output) as archive:
            self.assertEqual(archive.getmember("usr/bin/sh").linkname, "bash")

    def test_relative_link_remains_relative(self):
        self.archive(entry("usr/bin/tool", tarfile.SYMTYPE, "../../bin/tool"))
        gate.prepare(self.source, self.output)
        with tarfile.open(self.output) as archive:
            self.assertEqual(archive.getmember("usr/bin/tool").linkname, "../../bin/tool")

    def test_hardlink_copies_content(self):
        self.archive(entry("bin/tool", tarfile.LNKTYPE, "usr/bin/tool"), entry("usr/bin/tool"))
        gate.prepare(self.source, self.output)
        with tarfile.open(self.output) as archive:
            self.assertTrue(archive.getmember("bin/tool").isfile())
            self.assertEqual(archive.extractfile("bin/tool").read(), b"\x7fELF\x00test")

    def test_pax_absolute_link_is_rewritten(self):
        item, data = entry("bin/sh", tarfile.SYMTYPE, "/usr/bin/bash")
        item.pax_headers = {"linkpath": "/usr/bin/bash"}
        self.archive((item, data))
        gate.prepare(self.source, self.output)
        with tarfile.open(self.output) as archive:
            self.assertEqual(archive.getmember("bin/sh").linkname, "../usr/bin/bash")

    def test_pax_hardlink_size_does_not_override_materialized_content(self):
        item, data = entry('./bin/tool', tarfile.LNKTYPE, './usr/bin/tool')
        item.pax_headers = {'path': './bin/tool', 'linkpath': './usr/bin/tool', 'size': '0'}
        self.archive((item, data), entry('./usr/bin/tool'))
        gate.prepare(self.source, self.output)
        with tarfile.open(self.output) as archive:
            self.assertEqual(archive.getnames(), ['bin/tool', 'usr/bin/tool'])
            self.assertEqual(archive.extractfile('bin/tool').read(), b'\x7fELF\x00test')
            self.assertEqual(archive.extractfile('usr/bin/tool').read(), b'\x7fELF\x00test')

    def test_wrong_digest(self):
        self.archive(entry("file"))
        with patch.object(gate, "BASE_SHA256", "0" * 64):
            with self.assertRaises(ValueError):
                gate.prepare(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_explicit_trusted_ci_digest_and_dot_root(self):
        self.archive(entry('.', tarfile.DIRTYPE), entry('./usr/bin/bash'))
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with patch.object(gate, 'BASE_SHA256', '0' * 64):
            gate.prepare(self.source, self.output, digest)
        with tarfile.open(self.output) as archive:
            self.assertEqual(archive.getnames(), ['usr/bin/bash'])
            self.assertEqual(archive.extractfile('usr/bin/bash').read(), b'\x7fELF\x00test')

    def test_explicit_digest_malformed_or_wrong_rejected(self):
        self.archive(entry('file'))
        for digest in ['0' * 64, '', 'A' * 64, '../file']:
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                gate.prepare(self.source, self.output, digest)
            self.assertFalse(self.output.exists())

    def test_conversion_entry_and_expansion_limits(self):
        huge, _ = entry('huge')
        huge.size = 3 * 1024**3 + 1
        with patch.object(gate.tarfile, 'open') as mocked:
            self.source.write_bytes(b'fixture')
            mocked.return_value.__enter__.return_value = [huge]
            with self.assertRaisesRegex(ValueError, 'limits'):
                gate.prepare(self.source, self.output, hashlib.sha256(b'fixture').hexdigest())
        self.assertFalse(self.output.exists())

    def test_hardlink_expansion_limit(self):
        large, _ = entry('large')
        large.size = 2 * 1024**3
        link, _ = entry('copy', tarfile.LNKTYPE, 'large')
        with patch.object(gate.tarfile, 'open') as mocked:
            self.source.write_bytes(b'fixture')
            mocked.return_value.__enter__.return_value = [large, link]
            with self.assertRaisesRegex(ValueError, 'materialized'):
                gate.prepare(self.source, self.output, hashlib.sha256(b'fixture').hexdigest())
        self.assertFalse(self.output.exists())

    def test_refuses_overwrite(self):
        self.archive(entry("file"))
        self.output.write_bytes(b"keep")
        with self.assertRaises(ValueError):
            gate.prepare(self.source, self.output)
        self.assertEqual(self.output.read_bytes(), b"keep")

    def test_refuses_input_as_output(self):
        self.archive(entry("file"))
        original = self.source.read_bytes()
        with self.assertRaises(ValueError):
            gate.prepare(self.source, self.source)
        self.assertEqual(self.source.read_bytes(), original)

    def test_path_traversal(self):
        for name in ("../bad", "/bad", "a/../bad", "a\\bad"):
            with self.subTest(name=name):
                self.reject(entry(name))

    def test_invalid_root_and_nul_paths_rejected(self):
        self.reject(entry('.'))
        for name in ['file\x00suffix', '']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                gate.member_name(name)

    def test_duplicate_normalized_path(self):
        self.reject(entry("./file"), entry("file"))

    def test_symlink_ancestor(self):
        self.reject(entry("dir", tarfile.SYMTYPE, "target"), entry("dir/file"))

    def test_special_file(self):
        self.reject(entry("device", tarfile.CHRTYPE))

    def test_bad_hardlink_targets(self):
        for target in ("missing", "../escape", "/absolute", "sym"):
            with self.subTest(target=target):
                self.reject(entry("hard", tarfile.LNKTYPE, target), entry("sym", tarfile.SYMTYPE, "file"))

    def test_symlink_escape(self):
        self.reject(entry("dir/link", tarfile.SYMTYPE, "../../escape"))


if __name__ == "__main__":
    unittest.main()
