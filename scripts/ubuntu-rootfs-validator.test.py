#!/usr/bin/env python3
"""Synthetic, dependency-free tests; no actual ELF or third-party binaries."""
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "validator", Path(__file__).with_name("validate-ubuntu-rootfs.py"))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def entry(name, kind=tarfile.REGTYPE, target="", mode=0o644):
    item = tarfile.TarInfo(name)
    item.type, item.linkname, item.mode = kind, target, mode
    return item


class ValidatorTests(unittest.TestCase):
    def check(self, extra, good=False):
        required = [entry(name) for name in (
            "etc/os-release", "etc/passwd", "usr/bin/bash", "usr/bin/apt-get",
            "usr/bin/gcc", "usr/bin/setpriv", "etc/andcode-image")]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rootfs.tar"
            with tarfile.open(path, "w") as archive:
                for item in required + extra:
                    archive.addfile(item, io.BytesIO(b"") if item.size == 0 else None)
            if good:
                validator.validate(path)
            else:
                with self.assertRaises(ValueError):
                    validator.validate(path)

    def test_merged_usr(self):
        self.check([entry("bin", tarfile.SYMTYPE, "usr/bin")], good=True)

    def test_guest_absolute_symlink(self):
        self.check([entry("dev/fd", tarfile.SYMTYPE, "/proc/self/fd")], good=True)

    def test_parent_path(self):
        self.check([entry("etc/../../outside")])

    def test_absolute_path(self):
        self.check([entry("/outside")])

    def test_duplicate(self):
        self.check([entry("etc/passwd")])

    def test_symlink_write_through(self):
        self.check([entry("escape", tarfile.SYMTYPE, "/tmp"), entry("escape/payload")])

    def test_regular_ancestor(self):
        self.check([entry("etc/passwd/child")])

    def test_device(self):
        self.check([entry("dev/raw", tarfile.CHRTYPE)])

    def test_fifo(self):
        self.check([entry("fifo", tarfile.FIFOTYPE)])

    def test_setuid(self):
        self.check([entry("usr/bin/unsafe", mode=0o4755)])

    def test_bad_hardlink(self):
        self.check([entry("hard", tarfile.LNKTYPE, "../outside")])

    def test_valid_hardlink(self):
        self.check([entry("hard", tarfile.LNKTYPE, "usr/bin/bash")], good=True)

    def test_backslash(self):
        self.check([entry("etc\\outside")])

    def test_size_limit(self):
        item = entry("large", tarfile.DIRTYPE)
        item.size = 4 * 1024**3
        self.check([item])


if __name__ == "__main__":
    unittest.main()
