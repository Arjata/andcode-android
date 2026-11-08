"""Repair a stale DT_VERDEF after patchelf moves SHT_GNU_verdef.

Only ELF64 little-endian AArch64 is accepted. Never guess offsets: require a
unique allocated verdef section, matching count and a file-backed LOAD mapping.
All writes are limited to the DT_VERDEF value in the dynamic segment.
"""
import struct
import sys
from pathlib import Path


def repair(path):
    path = Path(path)
    blob = bytearray(path.read_bytes())
    if blob[:4] != b'\x7fELF':
        return False  # Tier P also contains interpreted wrappers.
    if len(blob) < 64 or blob[4:7] != b'\x02\x01\x01' or struct.unpack_from('<H', blob, 18)[0] != 183:
        raise ValueError('expected ELF64 LE AArch64')
    phoff, shoff = struct.unpack_from('<QQ', blob, 32)
    phsize, phnum, shsize, shnum = struct.unpack_from('<HHHH', blob, 54)
    if phsize != 56 or shsize != 64 or not shnum or phoff + phnum * 56 > len(blob) or shoff + shnum * 64 > len(blob):
        raise ValueError('unsupported or truncated ELF tables')
    programs = [struct.unpack_from('<IIQQQQQQ', blob, phoff + i * 56) for i in range(phnum)]
    dynamic = [p for p in programs if p[0] == 2]
    if not dynamic:
        return False
    if len(dynamic) != 1:
        raise ValueError('ambiguous dynamic segment')
    d = dynamic[0]
    if d[2] + d[5] > len(blob) or d[5] % 16:
        raise ValueError('invalid dynamic segment')
    entries = {}
    for offset in range(d[2], d[2] + d[5], 16):
        tag, value = struct.unpack_from('<QQ', blob, offset)
        if tag == 0:
            if value:
                raise ValueError('invalid DT_NULL value')
            break
        if tag in (0x6ffffffc, 0x6ffffffd):
            if tag in entries:
                raise ValueError('duplicate version definition tag')
            entries[tag] = (offset + 8, value)
    else:
        raise ValueError('missing DT_NULL')
    if not entries:
        return False
    if set(entries) != {0x6ffffffc, 0x6ffffffd}:
        raise ValueError('incomplete version definition tags')
    sections = [struct.unpack_from('<IIQQQQIIQQ', blob, shoff + i * 64) for i in range(shnum)]
    definitions = [s for s in sections if s[1] == 0x6ffffffd]
    if len(definitions) != 1:
        raise ValueError('missing or ambiguous verdef section')
    s = definitions[0]
    if not s[2] & 2 or not s[5] or s[4] + s[5] > len(blob) or s[7] != entries[0x6ffffffd][1]:
        raise ValueError('invalid verdef section/count')
    mappings = [p for p in programs if p[0] == 1 and p[3] <= s[3]
                and s[3] + s[5] <= p[3] + p[5] and p[2] + s[3] - p[3] == s[4]]
    if len(mappings) != 1:
        raise ValueError('verdef not uniquely file-backed')
    # Walk every definition, validating its version and exact bounded chain.
    at = s[4]
    for index in range(s[7]):
        if at + 20 > s[4] + s[5]:
            raise ValueError('truncated version definition')
        version, _, _, count, _, aux, nxt = struct.unpack_from('<HHHHIII', blob, at)
        if version != 1 or not count or aux < 20 or at + aux + 8 > s[4] + s[5]:
            raise ValueError('invalid version definition')
        if index + 1 == s[7]:
            if nxt:
                raise ValueError('unexpected version definition tail')
        elif nxt < 20 or at + nxt <= at:
            raise ValueError('invalid version definition chain')
        at += nxt
    offset, value = entries[0x6ffffffc]
    if value == s[3]:
        return False
    struct.pack_into('<Q', blob, offset, s[3])
    path.write_bytes(blob)
    print(f'{path.name}: DT_VERDEF {value:#x} -> {s[3]:#x} (section-derived)')
    return True


if __name__ == '__main__':
    for filename in sys.argv[1:]:
        repair(filename)
