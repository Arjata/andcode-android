"""Linux-only patcher regression; synthetic bytes are never executed as ELF."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class SeccompPatchTest(unittest.TestCase):
    def run_case(self, legacy=False, corrupt=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'bin').mkdir()
            (root / 'lib').mkdir()
            # Execute standard Linux tools behind the patcher's busybox boundary.
            bb = root / 'bin/busybox'
            bb.write_text('#!/bin/bash\nif [ "$1" = printf ]; then shift; printf "$@"; else exec "$@"; fi\n')
            bb.chmod(0o755)
            ld = bytearray(68000)
            lc = bytearray(966000)
            points = [(ld, 67248, '680c80d2'), (ld, 67324, 'a82480d2'),
                      (lc, 546232, '680c80d2'), (lc, 775112, '680c80d2'),
                      (lc, 546884, 'a82480d2'),
                      (lc, 965408, '883680d2' if legacy else '683680d2'),
                      (lc, 965412, '010000d4'), (lc, 903480, 'e83680d2'),
                      (lc, 903500, '010000d4')]
            for blob, at, value in points:
                blob[at:at + 4] = bytes.fromhex(value)
            if corrupt:
                lc[965408:965412] = bytes(4)
            loader = root / 'lib/ld-linux-aarch64.so.1'
            libc = root / 'lib/libc.so.6'
            loader.write_bytes(ld)
            libc.write_bytes(lc)
            script = Path(__file__).resolve().with_name('patch-seccomp.sh')
            result = subprocess.run(['bash', str(script), str(root)], capture_output=True, text=True)
            if corrupt:
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(libc.read_bytes()[965412:965416], bytes.fromhex('010000d4'))
                return
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            patched = (loader.read_bytes(), libc.read_bytes())
            expected_ld, expected_lc = bytearray(ld), bytearray(lc)
            for blob, at in [(expected_ld, 67248), (expected_ld, 67324),
                             (expected_lc, 546232), (expected_lc, 775112), (expected_lc, 546884)]:
                blob[at:at + 4] = bytes.fromhex('880f80d2')
            for at in [965412, 903500]:
                expected_lc[at:at + 4] = bytes.fromhex('a0048092')
            self.assertEqual(patched, (expected_ld, expected_lc))
            result = subprocess.run(['bash', str(script), str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((loader.read_bytes(), libc.read_bytes()), patched)

    def test_original(self):
        self.run_case()

    def test_legacy(self):
        self.run_case(legacy=True)

    def test_wrong_call_site(self):
        self.run_case(corrupt=True)


if __name__ == '__main__':
    unittest.main()
