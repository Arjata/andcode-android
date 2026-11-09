"""Fixed-source Linux arm64 watcher build and real Bun N-API event gate."""
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

spec = importlib.util.spec_from_file_location('pty_build', Path(__file__).with_name('build-opencode-native-pty.py'))
pty = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pty)
ORIGINAL = 'a0bc8fc5f3e68e95218c2541b812dc07ba5fb8afd765b6252ab9e68ba5edb2aa'
SOURCES = ['src/binding.cc', 'src/Watcher.cc', 'src/Backend.cc', 'src/DirTree.cc',
           'src/Glob.cc', 'src/Debounce.cc', 'src/watchman/BSER.cc',
           'src/watchman/WatchmanBackend.cc', 'src/shared/BruteForceBackend.cc',
           'src/linux/InotifyBackend.cc', 'src/unix/legacy.cc']
HEADERS = {
    'node-addon-api-7.1.1.tgz': ('https://registry.npmjs.org/node-addon-api/-/node-addon-api-7.1.1.tgz',
                               'b10455d15a977c0cd17a1cb0eb679e03d939f8ef8d4302eb33e1f78dacc71f82'),
    'node-v24.6.0-headers.tar.gz': ('https://nodejs.org/dist/v24.6.0/node-v24.6.0-headers.tar.gz',
                                  '6b891cced2a8ee08fef06b8cb36a890bd6d1dd8aca575e2a392bb78f0970b819'),
}


def build(upstream, stage):
    if sys.platform != 'linux' or platform.machine() not in ('aarch64', 'arm64'):
        raise ValueError('Watcher rebuild requires native Linux arm64 CI')
    upstream, stage = Path(upstream).resolve(strict=True), Path(stage).resolve(strict=True)
    matches = list((upstream / 'node_modules/.bun').glob(
        '@parcel+watcher-linux-arm64-glibc@2.5.1*/node_modules/@parcel/watcher-linux-arm64-glibc/watcher.node'))
    if len(matches) != 1:
        raise ValueError('Expected one fixed watcher glibc input')
    target = matches[0].resolve(strict=True)
    target.relative_to(upstream)
    if hashlib.sha256(target.read_bytes()).hexdigest() != ORIGINAL:
        raise ValueError('Unexpected original watcher input')
    output = stage / 'native-watcher-build'
    output.mkdir(exist_ok=False)
    repo, commit, expected = pty.rust.sources.SOURCES['watcher']
    archives = {f'watcher-{commit}.tar.gz': (f'https://codeload.github.com/{repo}/tar.gz/{commit}', expected), **HEADERS}
    roots, records = [], []
    for filename, (url, checksum) in archives.items():
        with urllib.request.urlopen(url, timeout=90) as response:
            data = response.read(pty.rust.sources.LIMIT + 1)
        review = pty.rust.sources.inspect_archive(data, checksum)
        archive = output / filename
        archive.write_bytes(data)
        roots.append(pty.rust.unpack_candidate(archive, checksum, output / 'source'))
        records.append({'archive': filename, 'url': url, 'sha256': checksum, 'evidence': review})
    source, addon, node = roots
    # Refuse a different binding.gyp instead of silently compiling an obsolete
    # manually selected source list when the fixed archive changes.
    binding = (source / 'binding.gyp').read_text()
    for item in SOURCES:
        if '"' + item + '"' not in binding:
            raise ValueError('Fixed binding.gyp source mismatch: ' + item)
    result = output / 'watcher.node'
    command = ['c++', '-shared', '-fPIC', '-O2', '-std=c++17', '-pthread',
               '-DNAPI_VERSION=3', '-DNAPI_DISABLE_CPP_EXCEPTIONS',
               '-DWATCHMAN', '-DINOTIFY', '-DBRUTE_FORCE',
               '-I' + str(addon), '-I' + str(node / 'include/node'),
               '-Wl,-z,max-page-size=16384', *[str(source / item) for item in SOURCES], '-o', str(result)]
    with (output / 'compile.log').open('w', encoding='utf8') as log:
        try:
            subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print((output / 'compile.log').read_text()[-12000:], file=sys.stderr)
            raise
    payload = result.read_bytes()
    _, needed = pty.audit.elf(payload)
    if not needed or set(needed) - {'libstdc++.so.6', 'libm.so.6', 'libgcc_s.so.1', 'libc.so.6',
                                    'libpthread.so.0', 'libdl.so.2'}:
        raise ValueError('Unexpected rebuilt watcher dependencies')
    symbols = subprocess.check_output(['readelf', '--dyn-syms', '--wide', str(result)], text=True)
    if not any(line.split()[-1:] == ['napi_register_module_v1'] and ' UND ' not in line for line in symbols.splitlines()):
        raise ValueError('Missing N-API registration export')
    # This test uses only a fresh directory owned by this build and waits for a
    # real inotify event, not just a successful dlopen or exported function list.
    probe = output / 'probe.mjs'
    probe.write_text('''import {mkdtemp, writeFile, rm} from "node:fs/promises";
import path from "node:path";
const m={exports:{}};process.dlopen(m,process.argv[2]);const watcher=m.exports;
const dir=await mkdtemp(path.join(process.argv[3],"event-"));let subscribed=false,callback;
const options={backend:"inotify"};
try {
  let resolveEvent,rejectEvent;const received=new Promise((resolve,reject)=>{resolveEvent=resolve;rejectEvent=reject});
  const file=path.join(dir,"created.txt");
  const timer=setTimeout(()=>rejectEvent(new Error("No watcher create event")),10000);
  try {
    callback=(error,events)=>{if(error)rejectEvent(error);else if(events.some(e=>e.path===file&&e.type==="create"))resolveEvent()};
    await watcher.subscribe(dir,callback,options);subscribed=true;
    await writeFile(file,"andcode watcher source gate");await received;
    console.log("ANDCODE_SOURCE_WATCHER_EVENT_OK");
  } finally {clearTimeout(timer)}
} finally {try {if(subscribed)await watcher.unsubscribe(dir,callback,options)} finally {await rm(dir,{recursive:true,force:true})}}
''', encoding='utf8')
    env = {k: v for k, v in os.environ.items() if k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH')}
    try:
        probe_result = subprocess.run(['bun', str(probe), str(result), str(output)], env=env,
                                      capture_output=True, text=True, check=True, timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        diagnostic = '\n'.join(part.decode(errors='replace') if isinstance(part, bytes) else (part or '')
                               for part in [error.stdout, error.stderr])
        (output / 'event.log').write_text(diagnostic, encoding='utf8')
        print(diagnostic[-12000:], file=sys.stderr)
        raise
    (output / 'event.log').write_text(probe_result.stdout + probe_result.stderr, encoding='utf8')
    if 'ANDCODE_SOURCE_WATCHER_EVENT_OK' not in probe_result.stdout:
        raise ValueError('Watcher event probe did not complete')
    shutil.copyfile(result, target)
    (stage / 'native-watcher-build-review.json').write_text(json.dumps({
        'redistributionApproved': False, 'androidApproved': False,
        'originalNpmBinaryCorrespondenceProven': False, 'sourceCommit': commit,
        'archives': records, 'commands': [command], 'sourceFiles': SOURCES,
        'originalNpmSha256': ORIGINAL, 'rebuiltSha256': hashlib.sha256(payload).hexdigest(),
        'installedInput': str(target.relative_to(upstream)), 'needed': needed,
        'cxxVersion': subprocess.check_output(['c++', '--version'], text=True).splitlines()[0],
        'eventGate': 'ANDCODE_SOURCE_WATCHER_EVENT_OK',
        'limitations': ['Explicit Linux binding.gyp branch, not original npm build reproducibility',
                        'Per-file native source notices and compiler/runtime source closure require review',
                        'No Android physicalization, seccomp or application-domain acceptance']
    }, indent=2) + '\n', encoding='utf8')
    print('Fixed-source watcher rebuilt and real event passed; redistribution remains BLOCKED')


if __name__ == '__main__':
    build(*sys.argv[1:])
