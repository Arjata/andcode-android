"""Collect an explicit Ubuntu runtime closure for the Linux-only prototype."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

spec = importlib.util.spec_from_file_location('native_elf', Path(__file__).with_name('audit-opencode-native.py'))
elf_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(elf_module)

LIBRARIES = {
    'ld-linux-aarch64.so.1': 'libc6', 'libc.so.6': 'libc6', 'libm.so.6': 'libc6',
    'libdl.so.2': 'libc6', 'libpthread.so.0': 'libc6', 'librt.so.1': 'libc6',
    'libutil.so.1': 'libc6', 'libstdc++.so.6': 'libstdc++6', 'libgcc_s.so.1': 'libgcc-s1',
}


def versions(path):
    # Parsing binutils output requires a deterministic language even on a runner
    # configured with a non-English locale.
    text = subprocess.check_output(['readelf', '--version-info', '--wide', str(path)],
                                   text=True, env=dict(os.environ, LC_ALL='C'))
    definitions, requirements = set(), {}
    mode, provider = None, None
    for line in text.splitlines():
        if line.startswith('Version definition section'):
            mode = 'definition'
        elif line.startswith('Version needs section'):
            mode = 'need'
        elif line.startswith('Version symbols section'):
            mode = None
        if mode == 'need':
            match = re.search(r'File:\s+(\S+)', line)
            if match:
                provider = match[1]
                requirements.setdefault(provider, set())
        match = re.search(r'Name:\s+(\S+)', line)
        if match and mode == 'definition':
            definitions.add(match[1])
        elif match and mode == 'need':
            if provider is None:
                raise ValueError('Version requirement has no provider')
            requirements[provider].add(match[1])
    return definitions, requirements


def verify_closure(objects, runtime):
    """Require each dependency and version in the staged closure, never host fallback."""
    providers = {}
    for path in runtime:
        if path.name in providers:
            raise ValueError('Duplicate runtime provider')
        providers[path.name] = versions(path)[0]
    rows = []
    for path in objects:
        _, needed = elf_module.elf(path.read_bytes())
        _, required = versions(path)
        for name in set(needed) | set(required):
            if name not in providers:
                raise ValueError(f'Missing runtime provider: {path.name}: {name}')
            missing = required.get(name, set()) - providers[name]
            if missing:
                raise ValueError(f'Missing symbol versions: {path.name}: {name}: {sorted(missing)}')
        rows.append({'file': path.name, 'needed': needed,
                     'requiredVersions': {k: sorted(v) for k, v in required.items()}})
    return rows


def collect(sysroot, stage, image):
    sysroot, stage = Path(sysroot).resolve(strict=True), Path(stage).resolve(strict=True)
    output = stage / 'runtime'
    output.mkdir(exist_ok=False)
    notices = output / 'copyright'
    notices.mkdir()
    packages = {}
    for package in sorted(set(LIBRARIES.values())):
        fmt = '${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n'
        fields = subprocess.check_output(['dpkg-query', '--admindir=' + str(sysroot / 'var/lib/dpkg'),
                                          '-W', '-f=' + fmt, package], text=True).strip().split('\t')
        if len(fields) != 4:
            raise ValueError('Invalid dpkg package provenance')
        # Ubuntu runtime copyright paths may be relative symlinks; resolve only
        # inside the exported tree and refuse escapes instead of reading host files.
        copyright_path = (sysroot / 'usr/share/doc' / package / 'copyright').resolve(strict=True)
        copyright_path.relative_to(sysroot)
        shutil.copyfile(copyright_path, notices / package)
        packages[package] = dict(zip(('binaryPackage', 'version', 'sourcePackage', 'sourceVersion'), fields))
    rows = []
    for name, package in LIBRARIES.items():
        source = (sysroot / 'usr/lib/aarch64-linux-gnu' / name).resolve(strict=True)
        source.relative_to(sysroot)
        payload = source.read_bytes()
        elf_module.elf(payload)
        shutil.copyfile(source, output / name)
        (output / name).chmod(0o755)
        rows.append({'name': name, 'source': source.relative_to(sysroot).as_posix(),
                     'sha256': hashlib.sha256(payload).hexdigest(), 'package': package})
    libraries = [output / name for name in LIBRARIES]
    objects = [stage / 'opencode', *sorted((stage / 'native').glob('*.so')), *libraries]
    closure = verify_closure(objects, libraries)
    (stage / 'native-runtime-review.json').write_text(json.dumps({
        'redistributionApproved': False, 'androidApproved': False,
        'scope': 'Explicit Linux prototype ELF DT_NEEDED/version closure; not all dlopen names or static dependencies',
        'imageID': image, 'packages': packages, 'libraries': rows, 'closure': closure,
        'limitations': ['No corresponding-source or license approval',
                        'No Android physicalization, seccomp or application-domain acceptance']}, indent=2) + '\n', encoding='utf8')
    print('Explicit Ubuntu runtime dependency/version closure verified; redistribution remains BLOCKED')


if __name__ == '__main__':
    collect(*sys.argv[1:])
