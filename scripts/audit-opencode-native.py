"""Bounded static gate for the source-built glibc native prototype, not license approval."""
import hashlib
from pathlib import Path
import re
import struct
import sys


def elf(data):
    def unpack(fmt, offset):
        size = struct.calcsize(fmt)
        if offset < 0 or offset + size > len(data):
            raise ValueError('Truncated ELF table')
        return struct.unpack_from(fmt, data, offset)

    if data[:7] != b'\x7fELF\x02\x01\x01' or unpack('<H', 18)[0] != 183:
        raise ValueError('Expected ELF64 LE AArch64')
    phoff, shoff = unpack('<QQ', 32)
    phsize, phnum, shsize, shnum, stridx = unpack('<HHHHH', 54)
    if phsize != 56 or shsize != 64 or not phnum or not shnum or stridx >= shnum:
        raise ValueError('Unsupported ELF layout')
    programs = [unpack('<IIQQQQQQ', phoff + i * phsize) for i in range(phnum)]
    sections = [unpack('<IIQQQQIIQQ', shoff + i * shsize) for i in range(shnum)]

    def region(offset, size):
        if offset < 0 or size < 0 or offset + size > len(data):
            raise ValueError('Truncated ELF region')
        return data[offset:offset + size]

    strings = region(sections[stridx][4], sections[stridx][5])

    def string(table, offset):
        if offset >= len(table) or b'\0' not in table[offset:]:
            raise ValueError('Invalid ELF string')
        return table[offset:table.index(b'\0', offset)].decode('ascii')

    named = {string(strings, s[0]): s for s in sections}
    loads = [p for p in programs if p[0] == 1]
    if not loads or any(p[7] < 16384 or p[7] & (p[7] - 1) or (p[2] - p[3]) % p[7] for p in loads):
        raise ValueError('Invalid or sub-16K PT_LOAD alignment')
    for p in programs:
        region(p[2], p[5])
    for s in sections:
        if s[1] != 8:
            region(s[4], s[5])
    needed = []
    dynamic, dynstr = named.get('.dynamic'), named.get('.dynstr')
    if dynamic:
        if not dynstr or dynamic[5] % 16:
            raise ValueError('Invalid ELF dynamic table')
        table = region(dynstr[4], dynstr[5])
        for off in range(dynamic[4], dynamic[4] + dynamic[5], 16):
            tag, value = unpack('<qQ', off)
            if tag == 0:
                break
            if tag == 1:
                needed.append(string(table, value))
    for ver in re.findall(rb'GLIBC_([0-9]+(?:\.[0-9]+)+)', data):
        if tuple(map(int, ver.split(b'.'))) > (2, 39):
            raise ValueError('glibc symbol exceeds 2.39: ' + ver.decode())
    return named, needed


def audit(root):
    root = Path(root)
    exe = (root / 'opencode').read_bytes()
    sections, _ = elf(exe)
    bun = sections.get('.bun')
    if not bun:
        raise ValueError('Missing compiled Bun graph')
    # No imported executable bytes may remain in the standalone graph. This also
    # catches the extensionless persistent PTY missed by a .so/.node-only hook.
    if b'\x7fELF\x02\x01\x01' in exe[bun[4]:bun[4] + bun[5]]:
        raise ValueError('ELF remains embedded in Bun graph')
    allowed = {'libc.so.6', 'libm.so.6', 'libpthread.so.0', 'libdl.so.2',
               'librt.so.1', 'libutil.so.1', 'libstdc++.so.6', 'libgcc_s.so.1',
               'ld-linux-aarch64.so.1'}
    expected = set()
    for row in (root / 'oc2-native.tsv').read_text(encoding='utf8').splitlines():
        physical, digest, size, source = row.split('\t')
        if not re.fullmatch(r'libandcode-oc2-native-[a-f0-9]{16}\.so', physical):
            raise ValueError('Invalid physical native filename')
        payload = (root / 'native' / physical).read_bytes()
        if hashlib.sha256(payload).hexdigest() != digest or int(size) != len(payload) or physical != f'libandcode-oc2-native-{digest[:16]}.so':
            raise ValueError('Native provenance mismatch: ' + physical)
        _, needed = elf(payload)
        if not needed or set(needed) - allowed:
            raise ValueError('Unexpected native dependencies: ' + physical + ': ' + repr(needed))
        if 'musl' in source:
            raise ValueError('musl native input in glibc-only output')
        expected.add(physical)
        print(physical, 'NEEDED=' + ','.join(needed))
    actual = {p.name for p in (root / 'native').iterdir()}
    if not expected or actual != expected:
        raise ValueError('Untracked or missing native output')
    print('Static prototype gate passed; no embedded ELF; license/runtime closure still requires review')


if __name__ == '__main__':
    audit(sys.argv[1])
