#!/usr/bin/env python3
"""Compare a trusted canonical archive with an immutable, read-only CI image tree."""
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tarfile

spec = importlib.util.spec_from_file_location(
    'rootfs_validator', Path(__file__).with_name('validate-ubuntu-rootfs.py'))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def compare(archive_path, root):
    """No extraction or mutation; callers must keep both inputs immutable."""
    validator.validate(archive_path)
    root = Path(root)
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError('Image root must be a real directory')
    entries, digests = {}, {}
    with tarfile.open(archive_path, 'r:*') as archive:
        for item in archive:
            name = validator.clean(item.name)
            if name in entries:
                raise ValueError('Duplicate canonical path')
            entries[name] = item
            if item.isfile():
                with archive.extractfile(item) as stream:
                    digests[name] = hashlib.file_digest(stream, 'sha256').hexdigest()

    actual = {'.': root.lstat()}
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as children:
            for child in children:
                path = Path(child.path)
                name = path.relative_to(root).as_posix()
                info = child.stat(follow_symlinks=False)
                # mkfs.ext4 creates this empty recovery directory independently.
                if name == 'lost+found' and name not in entries:
                    if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700
                            or info.st_uid != 0 or info.st_gid != 0):
                        raise ValueError('Unexpected ext4 recovery directory metadata')
                    with os.scandir(path) as recovery:
                        if next(recovery, None) is not None:
                            raise ValueError('Nonempty ext4 recovery directory')
                    continue
                if len(actual) >= 100001:
                    raise ValueError('Image tree exceeds comparison limits')
                actual[name] = info
                if stat.S_ISDIR(info.st_mode):
                    pending.append(path)
    # Some canonical producers omit the root directory entry.
    if '.' not in entries:
        del actual['.']
    if set(actual) != set(entries):
        raise ValueError('Image/archive path mismatch: missing=' + repr(sorted(set(entries) - set(actual))[:20])
                         + ' extra=' + repr(sorted(set(actual) - set(entries))[:20]))

    files = links = hardlinks = file_bytes = 0
    for name, item in entries.items():
        path = root if name == '.' else root / name
        info = actual[name]
        if item.isdir():
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError('Expected image directory: ' + name)
        elif item.issym():
            if not stat.S_ISLNK(info.st_mode) or os.readlink(path) != item.linkname:
                raise ValueError('Image/archive symbolic link mismatch: ' + name)
            links += 1
        else:
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('Expected image regular file: ' + name)
            target = validator.clean(item.linkname) if item.islnk() else name
            target_item = entries[target]
            if info.st_size != target_item.size:
                raise ValueError('Image/archive file size mismatch: ' + name)
            with path.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != digests[target]:
                    raise ValueError('Image/archive file content mismatch: ' + name)
            if item.islnk():
                target_info = actual[target]
                if (info.st_dev, info.st_ino) != (target_info.st_dev, target_info.st_ino):
                    raise ValueError('Image/archive hardlink identity mismatch: ' + name)
                hardlinks += 1
            files += 1
            file_bytes += info.st_size
        if (stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid) != (item.mode, item.uid, item.gid):
            raise ValueError('Image/archive mode or ownership mismatch: ' + name)
    return {'entries': len(entries), 'regularFilesIncludingHardlinks': files,
            'materializedFileBytes': file_bytes, 'symlinks': links, 'hardlinks': hardlinks,
            'androidApproved': False, 'redistributionApproved': False,
            'scope': 'Read-only path/type/mode/UID/GID/content/link comparison; excludes times, ACLs, xattrs, sparse allocation, runtime and source approval'}


if __name__ == '__main__':
    import json
    if len(sys.argv) != 3:
        raise SystemExit('usage: compare-ubuntu-rootfs.py <canonical-archive> <read-only-image-root>')
    print(json.dumps(compare(*sys.argv[1:]), sort_keys=True))
