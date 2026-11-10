#!/usr/bin/env python3
"""Run inside a disposable CI guest with authenticated deb-src lists already loaded."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def installed_sources(text):
    sources = {}
    binaries = set()
    for line in text.splitlines():
        binary, binary_version, source, version = line.split('\t')
        if (not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9-]+)?', binary)
                or not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*', source)
                or not re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]*', version)
                or not binary_version or (binary, binary_version) in binaries):
            raise ValueError('Invalid or duplicate installed package record')
        binaries.add((binary, binary_version))
        sources.setdefault((source, version), []).append(
            {'package': binary, 'version': binary_version})
    if not sources or len(sources) > 1000:
        raise ValueError('Installed source set is empty or exceeds the limit')
    return [(name, version, sorted(rows, key=lambda row: row['package']))
            for (name, version), rows in sorted(sources.items())]


def verify_dsc(directory, files, name, version):
    """Bind downloaded inputs to the .dsc; apt authenticates its Sources record."""
    dsc = next(row for row in files if row['path'].endswith('.dsc'))
    path = directory / Path(dsc['path']).name
    if path.stat().st_size > 1024**2:
        raise ValueError('Source control file exceeds limit')
    text = path.read_bytes().decode('utf-8')
    if '\r' in text or '\x00' in text:
        raise ValueError('Invalid source control framing')
    if text.startswith('-----BEGIN PGP SIGNED MESSAGE-----\n'):
        headers, separator, body = text.partition('\n\n')
        if (not separator or not re.fullmatch(
                r'-----BEGIN PGP SIGNED MESSAGE-----\nHash: [A-Za-z0-9, -]+', headers)):
            raise ValueError('Invalid source control signed headers')
        text, separator, signature = body.partition('\n-----BEGIN PGP SIGNATURE-----\n')
        if (not separator or signature.count('-----END PGP SIGNATURE-----') != 1
                or not signature.rstrip().endswith('-----END PGP SIGNATURE-----')):
            raise ValueError('Invalid source control signature framing')
        # Framing only: authenticated apt, not this parser, verifies repository data.
        text = '\n'.join(line[2:] if line.startswith('- ') else line for line in text.splitlines())
    elif '-----BEGIN PGP' in text or '-----END PGP' in text:
        raise ValueError('Invalid source control framing')
    fields, last = {}, None
    for line in text.splitlines():
        if not line:
            continue
        if line[0].isspace():
            if last is None:
                raise ValueError('Invalid source control continuation')
            fields[last] += '\n' + line.strip()
        else:
            key, separator, value = line.partition(':')
            if not separator or key in fields:
                raise ValueError('Invalid source control field')
            fields[key] = value.strip()
            last = key
    if fields.get('Source') != name or fields.get('Version') != version:
        raise ValueError('Downloaded source identity/version mismatch')
    expected = {}
    for line in fields.get('Checksums-Sha256', '').splitlines():
        if not line.strip():
            continue
        sha, size, filename = line.split()
        if (not re.fullmatch('[0-9a-f]{64}', sha)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+:~_\-]*', filename)
                or filename in expected or not size.isdecimal() or int(size) <= 0):
            raise ValueError('Invalid source control checksum')
        expected[filename] = (sha, int(size))
    actual = {Path(row['path']).name: (row['sha256'], row['bytes'])
              for row in files if row is not dsc}
    if not expected or expected != actual:
        raise ValueError('Source control archive set/hash mismatch')


def collect(output, installed, runner=subprocess.run):
    sources = installed_sources(installed)
    output = Path(output)
    # Refuse existing paths, including dangling links; never clean up on failure.
    output.mkdir(mode=0o755, exist_ok=False)
    result = {'format': 1, 'sources': [], 'androidApproved': False,
              'redistributionApproved': False,
              'scope': 'Exact installed source-version downloads through guest apt authenticated deb-src indexes; hash inventory only, no extraction/build/notices or complete-source approval'}
    total = 0
    for index, (name, version, binaries) in enumerate(sources):
        directory = output / f'{index:04d}-{name}'
        directory.mkdir(mode=0o755)
        command = ['apt-get', '-o', 'APT::Get::AllowUnauthenticated=false',
                   '--yes', '--download-only', '--only-source', 'source', '--', name + '=' + version]
        # apt may drop to _apt; a fresh root-owned directory remains non-writable
        # to _apt and apt reports its root download fallback. No sandbox override.
        log = directory / 'apt-source.log'
        try:
            completed = runner(command, cwd=directory, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=600, check=False,
                               env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C',
                                    'DEBIAN_FRONTEND': 'noninteractive'})
        except subprocess.TimeoutExpired as error:
            partial = error.stdout or b''
            with log.open('xb') as stream:
                stream.write(partial)
            print(partial.decode('utf-8', errors='replace')[-16384:], flush=True)
            raise RuntimeError('Exact source acquisition timed out: ' + name + '=' + version) from error
        if log.exists() or log.is_symlink():
            raise ValueError('Unexpected source log collision')
        log.write_bytes(completed.stdout)
        if completed.returncode:
            print(completed.stdout.decode('utf-8', errors='replace')[-16384:], flush=True)
            raise RuntimeError('Exact source acquisition failed: ' + name + '=' + version)
        files = []
        for path in sorted(directory.iterdir()):
            if path == log:
                continue
            if (path.is_symlink() or not path.is_file()
                    or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+:~_\-]*', path.name)):
                raise ValueError('Unexpected downloaded source path')
            size = path.stat().st_size
            total += size
            if not size or total > 8 * 1024**3:
                raise ValueError('Empty source input or source-byte limit exceeded')
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            files.append({'path': path.relative_to(output).as_posix(),
                          'bytes': size, 'sha256': digest})
        if len(files) < 2 or sum(row['path'].endswith('.dsc') for row in files) != 1:
            raise ValueError('Expected exactly one .dsc and source archive inputs')
        verify_dsc(directory, files, name, version)
        result['sources'].append({'package': name, 'version': version, 'binaries': binaries,
                                  'command': command, 'files': files,
                                  'log': {'path': log.relative_to(output).as_posix(),
                                          'bytes': log.stat().st_size,
                                          'sha256': hashlib.sha256(completed.stdout).hexdigest()}})
        print('UBUNTU_EXACT_SOURCE_DOWNLOADED', index + 1, len(sources), name, version, flush=True)
    result['downloadedBytes'] = total
    (output / 'andcode-ubuntu-source-inputs.json').write_text(
        json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.platform != 'linux' or os.geteuid() != 0:
        raise SystemExit('usage (disposable Linux guest, root): collect-ubuntu-sources.py <new-output>')
    installed = subprocess.check_output(
        ['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n'],
        text=True, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
    collect(sys.argv[1], installed)
