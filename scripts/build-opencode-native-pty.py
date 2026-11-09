"""CI-only fixed-source bun-pty rebuild; not original npm binary correspondence."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import urllib.request


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rust = load('rust_sources', 'collect-opencode-native-rust.py')
audit = load('native_audit', 'audit-opencode-native.py')
ORIGINAL = '9449de4b2dbb4dcdf1e19aa3f26624b57a799b9a0a00465850139c8bc75a56e8'


def installed_input(upstream):
    matches = list((upstream / 'node_modules/.bun').glob(
        'bun-pty@0.4.11*/node_modules/bun-pty/rust-pty/target/release/librust_pty_arm64.so'))
    if len(matches) != 1:
        raise ValueError('Expected one fixed bun-pty glibc input')
    target = matches[0].resolve(strict=True)
    target.relative_to(upstream)
    if hashlib.sha256(target.read_bytes()).hexdigest() != ORIGINAL:
        raise ValueError('Unexpected original bun-pty input bytes')
    return target


def build(upstream, stage):
    if sys.platform != 'linux' or platform.machine() not in ('aarch64', 'arm64'):
        raise ValueError('Source PTY rebuild requires native Linux arm64 CI')
    upstream, stage = Path(upstream).resolve(strict=True), Path(stage).resolve(strict=True)
    target = installed_input(upstream)
    output = stage / 'native-pty-build'
    output.mkdir(exist_ok=False)
    # Do not upload Cargo caches, intermediate object files or credentials.
    work = stage.parent / 'native-pty-build'
    work.mkdir(exist_ok=False)
    repo, commit, expected = rust.sources.SOURCES['bun-pty']
    url = f'https://codeload.github.com/{repo}/tar.gz/{commit}'
    with urllib.request.urlopen(url, timeout=90) as response:
        data = response.read(rust.sources.LIMIT + 1)
    archive = output / f'bun-pty-{commit}.tar.gz'
    # Validate before persisting/extracting or running third-party build inputs.
    rust.sources.inspect_archive(data, expected)
    archive.write_bytes(data)
    root = rust.unpack_candidate(archive, expected, output / 'source')
    manifest = root / 'rust-pty/Cargo.toml'
    lock = root / 'rust-pty/Cargo.lock'
    original_lock = lock.read_bytes()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('CARGO_', 'RUST'))}
    env.update(CARGO_HOME=str(work / 'cargo-home'), CARGO_TARGET_DIR=str(work / 'target'),
               CARGO_TERM_COLOR='never', RUSTFLAGS='-C link-arg=-Wl,-z,max-page-size=16384')
    base = ['cargo', '--locked', '--manifest-path', str(manifest)]
    commands = [
        [base[0], 'fetch', *base[1:], '--target', rust.TARGET],
        [base[0], 'build', *base[1:], '--offline', '--release', '--target', rust.TARGET],
    ]
    for index, command in enumerate(commands):
        logpath = output / f'command-{index}.log'
        try:
            with logpath.open('w', encoding='utf8') as log:
                subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
                               check=True, timeout=900)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print(logpath.read_text(encoding='utf8')[-12000:], file=sys.stderr)
            raise
        if lock.read_bytes() != original_lock:
            raise ValueError('Cargo changed pinned bun-pty lockfile')
    result = work / 'target' / rust.TARGET / 'release/librust_pty.so'
    payload = result.read_bytes()
    _, needed = audit.elf(payload)
    if not needed or set(needed) - {'libc.so.6', 'libm.so.6', 'libdl.so.2', 'libpthread.so.0',
                                    'libutil.so.1', 'librt.so.1', 'libgcc_s.so.1', 'ld-linux-aarch64.so.1'}:
        raise ValueError('Unexpected rebuilt PTY dependency closure')
    symbols = subprocess.check_output(['readelf', '--dyn-syms', '--wide', str(result)], text=True)
    for symbol in ['spawn', 'write', 'read', 'resize', 'kill', 'get_pid', 'get_exit_code', 'close']:
        if not any(line.split()[-1:] == ['bun_pty_' + symbol] and ' UND ' not in line for line in symbols.splitlines()):
            raise ValueError('Missing rebuilt PTY export: ' + symbol)
    # Keep the exact tested ELF and corresponding fixed input separate from npm's
    # original bytes. The build plugin later records the new content physical name.
    shutil.copyfile(result, target)
    shutil.copyfile(result, output / 'librust_pty.so')
    (stage / 'native-pty-build-review.json').write_text(json.dumps({
        'redistributionApproved': False, 'androidApproved': False,
        'originalNpmBinaryCorrespondenceProven': False,
        'scope': 'This CI source build only, not reproducibility of original npm ELF',
        'sourceCommit': commit, 'archiveSha256': expected,
        'lockSha256': hashlib.sha256(original_lock).hexdigest(),
        'originalNpmSha256': ORIGINAL, 'rebuiltSha256': hashlib.sha256(payload).hexdigest(),
        'installedInput': str(target.relative_to(upstream)), 'needed': needed,
        'commands': commands, 'rustflags': env['RUSTFLAGS'],
        'cargoVersion': subprocess.check_output(['cargo', '--version'], text=True).strip(),
        'rustcVersion': subprocess.check_output(['rustc', '-vV'], text=True).strip(),
        'ccVersion': subprocess.check_output(['cc', '--version'], text=True).splitlines()[0],
        'limitations': ['Build scripts execute on isolated CI runner; Cargo offline is not a sandbox',
                        'Rust sysroot and transitive per-file notices still require review',
                        'No Android physicalization, seccomp or application-domain acceptance']
    }, indent=2) + '\n', encoding='utf8')
    print('Fixed-source PTY rebuilt and staged for Linux experiment; redistribution remains BLOCKED')


if __name__ == '__main__':
    build(*sys.argv[1:])
