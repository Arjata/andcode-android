#!/usr/bin/env python3
"""Development gate input only. Preserve ELF bytes; make symlinks Toybox-safe."""
import hashlib
import copy
import posixpath
from pathlib import Path
import sys
import tarfile

BASE_SHA256 = "04207713ece899c3740823d33690441ad3a7f0ded1101aca744e2b0f37ac7ff2"


def member_name(value):
    if not value or value.startswith("/") or ".." in value.split("/") or "\\" in value:
        raise ValueError("unsafe archive path")
    return posixpath.normpath(value)


def prepare(source, destination):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve() or destination.exists() or destination.is_symlink():
        raise ValueError("output must be new and distinct from source")
    # Keep the same open input for digest verification and archive reading.
    with source.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != BASE_SHA256:
            raise ValueError("official Base SHA-256 mismatch")
        stream.seek(0)
        with tarfile.open(fileobj=stream, mode="r:gz") as archive:
            entries = {}
            for item in archive:
                name = member_name(item.name)
                if name in entries:
                    raise ValueError("duplicate archive entry")
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
                    if not link or "\\" in link:
                        raise ValueError("unsafe symbolic link")
                    resolved = posixpath.normpath(link.lstrip("/") if link.startswith("/")
                                                 else posixpath.join(posixpath.dirname(name), link))
                    if resolved == ".." or resolved.startswith("../"):
                        raise ValueError("symbolic link escapes guest root")
            # Exclusive creation also rejects an output created after the initial check.
            with tarfile.open(destination, "x:gz", format=tarfile.PAX_FORMAT) as result:
                for name, original in entries.items():
                    item = copy.copy(original)
                    item.pax_headers = dict(original.pax_headers)
                    item.mode &= ~0o6000
                    data = archive.extractfile(original) if original.isfile() else None
                    if original.islnk():
                        # Android app_data_file hardlinks can be denied within one tree.
                        target = entries[member_name(original.linkname)]
                        data = archive.extractfile(target)
                        item.type, item.size, item.linkname = tarfile.REGTYPE, target.size, ""
                        item.pax_headers.pop("linkpath", None)
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
    source, destination = sys.argv[1:]
    print("prepared-gate-sha256=" + prepare(source, destination))
    print("ELF contents unchanged; symlinks normalized; setuid/setgid removed; not a release rootfs")
