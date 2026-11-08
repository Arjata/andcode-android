import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('repair', Path(__file__).with_name('repair-elf-verdef.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RepairTest(unittest.TestCase):
    def fixture(self):
        b = bytearray(1024)
        b[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<H', b, 18, 183)
        struct.pack_into('<QQ', b, 32, 64, 768)
        struct.pack_into('<HHHH', b, 54, 56, 2, 64, 2)
        struct.pack_into('<IIQQQQQQ', b, 64, 1, 4, 0, 0x10000, 0, 1024, 1024, 0x10000)
        struct.pack_into('<IIQQQQQQ', b, 120, 2, 6, 256, 0x10100, 0, 48, 48, 8)
        struct.pack_into('<QQQQQQ', b, 256, 0x6ffffffc, 0x10280, 0x6ffffffd, 1, 0, 0)
        struct.pack_into('<IIQQQQIIQQ', b, 832, 0, 0x6ffffffd, 2, 0x10200, 512, 28, 0, 1, 4, 0)
        struct.pack_into('<HHHHIII', b, 512, 1, 0, 1, 1, 0, 20, 0)
        return b

    def test_repair_is_limited_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'fixture.so'
            before = self.fixture()
            p.write_bytes(before)
            self.assertTrue(module.repair(p))
            expected = bytearray(before)
            struct.pack_into('<Q', expected, 264, 0x10200)
            self.assertEqual(p.read_bytes(), expected)
            self.assertFalse(module.repair(p))

    def test_reject_without_writing(self):
        mutations = [
            (18, '<H', 62), (58, '<H', 55), (60, '<H', 0),
            (280, '<Q', 2),  # count mismatch
            (848, '<Q', 0x99999),  # unmapped section address
            (864, '<Q', 10000),  # truncated section
            (512, '<H', 2), (524, '<I', 20000), (528, '<I', 28),
            (288, '<Q', 1), (296, '<Q', 1),  # no DT_NULL
        ]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'fixture.so'
            for offset, fmt, value in mutations:
                with self.subTest(offset=offset):
                    b = self.fixture()
                    struct.pack_into(fmt, b, offset, value)
                    p.write_bytes(b)
                    with self.assertRaises(ValueError):
                        module.repair(p)
                    self.assertEqual(p.read_bytes(), b)

    def test_wrapper_and_static(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'fixture.so'
            p.write_text('#!/system/bin/sh\n')
            self.assertFalse(module.repair(p))
            b = self.fixture()
            struct.pack_into('<I', b, 120, 0)
            p.write_bytes(b)
            self.assertFalse(module.repair(p))


if __name__ == '__main__':
    unittest.main()
