#!/usr/bin/env python3
"""Validate trusted CI rootfs exports before extraction; not an untrusted installer."""
import posixpath
import sys
import tarfile


def clean(name):
    if name.startswith("/") or "\x00" in name or "\\" in name:
        raise ValueError(f"invalid archive path: {name!r}")
    parts = name.split("/")
    if ".." in parts:
        raise ValueError(f"parent traversal: {name!r}")
    return posixpath.normpath(name)


def validate(path):
    with tarfile.open(path, "r:*") as archive:
        entries = {}
        total = 0
        for item in archive:
            name = clean(item.name)
            if name == "." and item.isdir():
                continue
            if name in entries:
                raise ValueError(f"duplicate entry: {name}")
            if not (item.isfile() or item.isdir() or item.issym() or item.islnk()):
                raise ValueError(f"special file: {name}")
            if item.mode & 0o6000:
                raise ValueError(f"setuid/setgid entry: {name}")
            total += item.size
            if len(entries) >= 100000 or total > 3 * 1024**3:
                raise ValueError("rootfs exceeds build limits")
            entries[name] = item
        for name, item in entries.items():
            parent = posixpath.dirname(name)
            while parent:
                ancestor = entries.get(parent)
                if ancestor is not None and not ancestor.isdir():
                    raise ValueError(f"non-directory ancestor: {name}: {parent}")
                parent = posixpath.dirname(parent)
            if item.islnk():
                target = entries.get(clean(item.linkname))
                if target is None or not target.isfile():
                    raise ValueError(f"invalid hardlink: {name}")
            if item.issym():
                # Absolute targets belong to the guest root. Extraction must never
                # write through a symlink (checked above), even for internal links.
                if not item.linkname or "\x00" in item.linkname or "\\" in item.linkname:
                    raise ValueError(f"invalid symlink: {name}")
        required = ("etc/os-release", "etc/passwd", "usr/bin/bash", "usr/bin/apt-get",
                    "usr/bin/gcc", "usr/bin/setpriv", "etc/andcode-image")
        for name in required:
            if name not in entries:
                raise ValueError(f"missing rootfs entry: {name}")
        return len(entries), total


if __name__ == "__main__":
    count, size = validate(sys.argv[1])
    print(f"Ubuntu rootfs: {count} entries, {size} bytes: PASS")
