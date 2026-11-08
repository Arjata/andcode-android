import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('audit_native', Path(__file__).with_name('audit-opencode-native.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    b = bytearray(1024)
    b[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<H', b, 18, 183)
    struct.pack_into('<QQ', b, 32, 64, 256)
    struct.pack_into('<HHHHH', b, 54, 56, 1, 64, 2, 1)
    struct.pack_into('<IIQQQQQQ', b, 64, 1, 5, 0, 0, 0, len(b), len(b), 16384)
    struct.pack_into('<IIQQQQIIQQ', b, 320, 1, 3, 0, 0, 512, 16, 0, 0, 1, 0)
    b[512:528] = b'\0.shstrtab\0\0\0\0\0\0'
    return b


class ElfGateTest(unittest.TestCase):
    def test_valid_minimal(self):
        self.assertEqual(module.elf(fixture())[1], [])

    def test_alignment_arch_and_bounds_rejected(self):
        for offset, fmt, value in [(18, '<H', 62), (112, '<Q', 4096), (96, '<Q', 2000), (40, '<Q', 2000), (62, '<H', 2)]:
            with self.subTest(offset=offset):
                b = fixture()
                struct.pack_into(fmt, b, offset, value)
                with self.assertRaises(ValueError):
                    module.elf(b)

    def test_too_new_glibc_rejected(self):
        b = fixture()
        b[700:711] = b'GLIBC_2.40\0'
        with self.assertRaises(ValueError):
            module.elf(b)


if __name__ == '__main__':
    unittest.main()
