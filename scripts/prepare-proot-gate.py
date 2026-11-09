#!/usr/bin/env python3
"""Development gate input only. Preserve ELF bytes; make symlinks Toybox-safe."""
import hashlib
import copy
import posixpath
import re
from pathlib import Path
import sys
import tarfile

BASE_SHA256 = "04207713ece899c3740823d33690441ad3a7f0ded1101aca744e2b0f37ac7ff2"


def member_name(value):
    if not value or value.startswith("/") or ".." in value.split("/") or "\\" in value or "\x00" in value:
        raise ValueError("unsafe archive path")
    return posixpath.normpath(value)


def prepare(source, destination, expected_sha256=None):
    """Build-time conversion only; an explicit digest must come from trusted CI."""
    expected_sha256 = BASE_SHA256 if expected_sha256 is None else expected_sha256
    if not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('invalid trusted rootfs SHA-256')
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve() or destination.exists() or destination.is_symlink():
        raise ValueError("output must be new and distinct from source")
    # Keep the same open input for digest verification and archive reading.
    with source.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != expected_sha256:
            raise ValueError("trusted rootfs SHA-256 mismatch")
        stream.seek(0)
        with tarfile.open(fileobj=stream, mode="r:gz") as archive:
            entries = {}
            expanded = 0
            for item in archive:
                name = member_name(item.name)
                if name == '.' and item.isdir():
                    continue
                if name == '.':
                    raise ValueError('non-directory archive root')
                if name in entries:
                    raise ValueError("duplicate archive entry")
                expanded += item.size
                if len(entries) >= 100000 or expanded > 3 * 1024**3:
                    raise ValueError('rootfs exceeds conversion limits')
                entries[name] = item
            for name, item in entries.items():
                parent = posixpath.dirname(name)
                while parent:
                    if parent in entries and not entries[parent].isdir():
                        raise ValueError("non-directory ancestor")
                    parent = posixpath.dirname(parent)
                if not (item.isfile() or item.isdir() or item.issym() or item.islnk()):
                    raise ValueError("special archive member")
                if item.islnk():
                    target = entries.get(member_name(item.linkname))
                    if target is None or not target.isfile():
                        raise ValueError("non-regular hardlink target")
                if item.issym():
                    link = item.linkname
                    if not link or "\\" in link or "\x00" in link:
                        raise ValueError("unsafe symbolic link")
                    resolved = posixpath.normpath(link.lstrip("/") if link.startswith("/")
                                                 else posixpath.join(posixpath.dirname(name), link))
                    if resolved == ".." or resolved.startswith("../"):
                        raise ValueError("symbolic link escapes guest root")
            output_size = sum(entries[member_name(i.linkname)].size if i.islnk() else i.size
                              for i in entries.values())
            if output_size > 3 * 1024**3:
                raise ValueError('materialized rootfs exceeds conversion limits')
            # Exclusive creation also rejects an output created after the initial check.
            with tarfile.open(destination, "x:gz", format=tarfile.PAX_FORMAT) as result:
                for name, original in entries.items():
                    item = copy.copy(original)
                    item.name = name
                    item.pax_headers = dict(original.pax_headers)
                    item.pax_headers.pop('path', None)
                    item.mode &= ~0o6000
                    data = archive.extractfile(original) if original.isfile() else None
                    if original.islnk():
                        # Android app_data_file hardlinks can be denied within one tree.
                        target = entries[member_name(original.linkname)]
                        data = archive.extractfile(target)
                        item.type, item.size, item.linkname = tarfile.REGTYPE, target.size, ""
                        item.pax_headers.pop("linkpath", None)
                        item.pax_headers.pop("size", None)
                    if original.issym() and original.linkname.startswith("/"):
                        item.linkname = posixpath.relpath(original.linkname.lstrip("/"), posixpath.dirname(name) or ".")
                        item.pax_headers.pop("linkpath", None)
                    try:
                        result.addfile(item, data)
                    finally:
                        if data is not None:
                            data.close()
    with destination.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if len(arguments) not in (2, 3):
        raise SystemExit('usage: prepare-proot-gate.py <input> <new-output> [trusted-ci-sha256]')
    print("prepared-gate-sha256=" + prepare(*arguments))
    print("ELF contents unchanged; symlinks normalized; setuid/setgid removed; not a release rootfs")
