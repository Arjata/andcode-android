#!/usr/bin/env python3
"""Synthetic tree comparisons; no mount, third-party input or device required."""
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'comparison', Path(__file__).with_name('compare-ubuntu-rootfs.py'))
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


@unittest.skipUnless(sys.platform == 'linux', 'POSIX inode/mode/owner tests run on Linux CI')
class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'root'
        self.root.mkdir()
        self.archive = self.base / 'rootfs.tar'
        for name in ['etc/os-release', 'etc/passwd', 'usr/bin/bash', 'usr/bin/apt-get',
                     'usr/bin/gcc', 'usr/bin/setpriv', 'etc/andcode-image']:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic content')
        (self.root / 'bin').symlink_to('usr/bin')
        os.link(self.root / 'usr/bin/bash', self.root / 'usr/bin/bash-alias')
        with tarfile.open(self.archive, 'w') as archive:
            archive.add(self.root, arcname='.')

    def compare(self):
        return comparison.compare(self.archive, self.root)

    def test_equal(self):
        report = self.compare()
        self.assertEqual(report['hardlinks'], 1)
        self.assertEqual(report['symlinks'], 1)
        self.assertIs(report['androidApproved'], False)

    def test_content(self):
        (self.root / 'etc/passwd').write_bytes(b'x' * len(b'synthetic content'))
        with self.assertRaisesRegex(ValueError, 'content mismatch'):
            self.compare()

    def test_size(self):
        (self.root / 'etc/passwd').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError, 'size mismatch'):
            self.compare()

    def test_missing(self):
        (self.root / 'etc/passwd').unlink()
        with self.assertRaisesRegex(ValueError, 'path mismatch'):
            self.compare()

    def test_extra(self):
        (self.root / 'extra').write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'path mismatch'):
            self.compare()

    def test_mode(self):
        (self.root / 'etc/passwd').chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'mode or ownership'):
            self.compare()

    def test_symlink(self):
        (self.root / 'bin').unlink()
        (self.root / 'bin').symlink_to('/usr/bin')
        with self.assertRaisesRegex(ValueError, 'symbolic link mismatch'):
            self.compare()

    def test_link_not_followed(self):
        (self.root / 'bin').unlink()
        (self.root / 'bin').symlink_to(self.base)
        with self.assertRaisesRegex(ValueError, 'symbolic link mismatch'):
            self.compare()

    def test_hardlink_identity(self):
        path = self.root / 'usr/bin/bash-alias'
        path.unlink()
        shutil.copyfile(self.root / 'usr/bin/bash', path)
        with self.assertRaisesRegex(ValueError, 'hardlink identity'):
            self.compare()

    def test_file_type(self):
        path = self.root / 'etc/passwd'
        path.unlink()
        path.mkdir()
        with self.assertRaisesRegex(ValueError, 'Expected image regular file'):
            self.compare()

    def test_root_must_not_be_symlink(self):
        link = self.base / 'link'
        link.symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, 'real directory'):
            comparison.compare(self.archive, link)

    def test_recovery_directory_exception_is_exact(self):
        path = self.root / 'lost+found'
        path.mkdir(mode=0o700)
        if os.getuid() == 0:
            self.compare()
        else:
            with self.assertRaisesRegex(ValueError, 'recovery directory metadata'):
                self.compare()
        path.chmod(0o755)
        with self.assertRaisesRegex(ValueError, 'recovery directory metadata'):
            self.compare()

    @unittest.skipUnless(hasattr(os, 'getuid') and os.getuid() == 0, 'Root-only recovery directory fixture')
    def test_nonempty_recovery_directory(self):
        path = self.root / 'lost+found'
        path.mkdir(mode=0o700)
        (path / 'unexpected').write_bytes(b'not ignored')
        with self.assertRaisesRegex(ValueError, 'Nonempty ext4 recovery'):
            self.compare()

    def test_archive_ownership_drift(self):
        changed = self.base / 'changed.tar'
        with tarfile.open(self.archive) as source, tarfile.open(changed, 'w') as dest:
            for item in source:
                if item.name == './etc/passwd':
                    item.uid += 1
                stream = source.extractfile(item) if item.isfile() else None
                try:
                    dest.addfile(item, stream)
                finally:
                    if stream is not None:
                        stream.close()
        with self.assertRaisesRegex(ValueError, 'mode or ownership'):
            comparison.compare(changed, self.root)


if __name__ == '__main__':
    unittest.main()
