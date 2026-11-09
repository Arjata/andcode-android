"""Fixed-source fff/zlob diagnostic build; never original npm or license approval."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tomllib

spec = importlib.util.spec_from_file_location('pty_build', Path(__file__).with_name('build-opencode-native-pty.py'))
pty = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pty)
ORIGINAL = '3e037ac8584fa49eaeedc8eacbb116682854d4a623efcf7feb68f25656e7bfcd'
ZIG_SHA256 = 'ea4b09bfb22ec6f6c6ceac57ab63efb6b46e17ab08d21f69f3a48b38e1534f17'
FLAGS = ['-p', 'fff-c', '--no-default-features', '--features', 'zlob']
MARKER = 'ANDCODE_SOURCE_FFF_SEARCH_GLOB_OK'
SORT_INPUTS = {
    'Cargo.toml': '57ce8f9edcb94bbdd28bc930f834882a89c970851ebe3b5203a7632f10f02b1c',
    'Cargo.lock': '5f862723546a9819de97aab3d6bd25e4326e3c6390d6b1c8a2063589ffa829bd',
    'crates/fff-core/Cargo.toml': 'aa7653a643fa18ee7f989dab4e6d465f25963ffabba63f6760eaba6eea5a06e6',
    'crates/fff-core/src/sort_buffer.rs': '73af6547e3ba6645d8aecbbbaf0da9e49f0a15d267c27b02714b548dc4ae937c',
}
SORT_ADAPTER = r'''// andcode-owned adapter: use Rust's stable sort, not glidesort source.
// Modified for the andcode source experiment; shared scratch-buffer optimization removed.
pub fn sort_with_buffer<T, F>(slice: &mut [T], compare: F)
where F: FnMut(&T, &T) -> std::cmp::Ordering {
    slice.sort_by(compare);
}

pub fn sort_by_key_with_buffer<T, K, F>(slice: &mut [T], key_fn: F)
where K: Ord, F: FnMut(&T) -> K {
    slice.sort_by_key(key_fn);
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn order_empty_single_and_duplicates() {
        let mut data = [3, 1, 4, 1, 5, 9, 2, 6];
        sort_with_buffer(&mut data, |a, b| a.cmp(b));
        assert_eq!(data, [1, 1, 2, 3, 4, 5, 6, 9]);
        sort_with_buffer(&mut data, |a, b| b.cmp(a));
        assert_eq!(data, [9, 6, 5, 4, 3, 2, 1, 1]);
        let mut empty: [i32; 0] = [];
        sort_with_buffer(&mut empty, |a, b| a.cmp(b));
        sort_by_key_with_buffer(&mut empty, |a| *a);
        let mut single = [42];
        sort_by_key_with_buffer(&mut single, |a| *a);
        assert_eq!(single, [42]);
    }
    #[test]
    fn both_entries_preserve_stable_ties_and_non_copy_values() {
        let original = vec![(2, String::from("a")), (1, String::from("b")),
                            (2, String::from("c")), (1, String::from("d"))];
        let mut by = original.clone();
        let mut calls = 0;
        sort_with_buffer(&mut by, |a, b| { calls += 1; a.0.cmp(&b.0) });
        assert!(calls > 0);
        let mut key = original;
        sort_by_key_with_buffer(&mut key, |a| a.0);
        assert_eq!(by, key);
        assert_eq!(by.iter().map(|a| a.1.as_str()).collect::<Vec<_>>(), ["b", "d", "a", "c"]);
    }
    #[test]
    fn comparator_panic_keeps_owned_elements() {
        let mut values: Vec<_> = (0..100).rev().map(|i| i.to_string()).collect();
        let mut calls = 0;
        assert!(std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            sort_with_buffer(&mut values, |a, b| {
                calls += 1;
                if calls == 5 { panic!("fixture comparator"); }
                a.cmp(b)
            });
        })).is_err());
        values.sort();
        let mut expected: Vec<_> = (0..100).map(|i| i.to_string()).collect();
        expected.sort();
        assert_eq!(values, expected);
    }
}
'''
PROBE = '''import {dlopen,FFIType as T,CString} from "bun:ffi";
import {mkdtemp,writeFile,readFile,realpath,rm} from "node:fs/promises";
import path from "node:path";
const signatures={
fff_create_instance:{args:[T.ptr,T.ptr,T.ptr,T.bool,T.bool,T.bool,T.bool,T.bool],returns:T.ptr},
fff_result_get_success:{args:[T.ptr],returns:T.bool},
fff_result_get_error:{args:[T.ptr],returns:T.ptr},
fff_result_get_handle:{args:[T.ptr],returns:T.ptr},
fff_result_get_int_value:{args:[T.ptr],returns:T.i64},
fff_free_result:{args:[T.ptr],returns:T.void},
fff_destroy:{args:[T.ptr],returns:T.void},
fff_wait_for_scan:{args:[T.ptr,T.u64],returns:T.ptr},
fff_search:{args:[T.ptr,T.ptr,T.ptr,T.u32,T.u32,T.u32,T.i32,T.u32],returns:T.ptr},
fff_glob:{args:[T.ptr,T.ptr,T.ptr,T.u32,T.u32,T.u32],returns:T.ptr},
fff_search_result_get_count:{args:[T.ptr],returns:T.u32},
fff_search_result_get_item:{args:[T.ptr,T.u32],returns:T.ptr},
fff_file_item_get_relative_path:{args:[T.ptr],returns:T.ptr},
fff_free_search_result:{args:[T.ptr],returns:T.void},
};
const lib=dlopen(process.argv[2],signatures),f=lib.symbols;
function checked(result,field){
 if(!result)throw new Error("Null fff envelope");
 try{if(!f.fff_result_get_success(result))throw new Error(String(new CString(f.fff_result_get_error(result))));
 return f[field](result)}finally{f.fff_free_result(result)}
}
const dir=await mkdtemp(path.join(process.argv[3],"search-"));let handle;
const c=s=>Buffer.from(s+"\\0");
try{
 await writeFile(path.join(dir,"andcode-source-needle.txt"),"andcode source gate\\n");
 await writeFile(path.join(dir,"unrelated.bin"),"other\\n");
 handle=checked(f.fff_create_instance(c(dir),null,null,false,false,false,false,false),"fff_result_get_handle");
 if(!handle)throw new Error("No fff instance");
 if(Number(checked(f.fff_wait_for_scan(handle,10000),"fff_result_get_int_value"))!==1)throw new Error("fff scan timeout");
 for(const result of [()=>f.fff_search(handle,c("andcode-source-needle"),null,1,0,20,1,1),
                      ()=>f.fff_glob(handle,c("*.txt"),null,1,0,20)]){
  const found=checked(result(),"fff_result_get_handle");
  if(!found)throw new Error("No fff search result");
  try{const names=[];for(let i=0;i<f.fff_search_result_get_count(found);i++){
   const item=f.fff_search_result_get_item(found,i);
   names.push(String(new CString(f.fff_file_item_get_relative_path(item))));
  }if(!names.includes("andcode-source-needle.txt"))throw new Error("fff search/glob missed fixture: "+JSON.stringify(names));
  }finally{f.fff_free_search_result(found)}
 }
 const maps=await readFile("/proc/self/maps","utf8");
 if(!maps.includes(await realpath(process.argv[2])))throw new Error("Wrong fff ELF mapping");
 if(process.env.ANDCODE_LOADER){for(const name of ["ld-linux-aarch64.so.1","libc.so.6","libgcc_s.so.1"]){
  if(!maps.includes(await realpath(path.join(path.dirname(process.env.ANDCODE_LOADER),name))))throw new Error("Wrong fff runtime mapping: "+name);
 }}
 console.log("ANDCODE_SOURCE_FFF_SEARCH_GLOB_OK");
}finally{try{if(handle)f.fff_destroy(handle)}finally{lib.close();await rm(dir,{recursive:true,force:true})}}
'''


def replace_glidesort(root):
    """Only transform exact fixed source bytes; preserve the original archive separately."""
    data = {name: (root / name).read_bytes() for name in SORT_INPUTS}
    for name, expected in SORT_INPUTS.items():
        if hashlib.sha256(data[name]).hexdigest() != expected:
            raise ValueError('Unexpected fff sort adapter source: ' + name)
    changes = {
        'Cargo.toml': ('glidesort = "0.1"\n', ''),
        'crates/fff-core/Cargo.toml': ('glidesort = { workspace = true }\n', ''),
        'Cargo.lock': (' "glidesort",\n', ''),
    }
    updated = {name: value.decode('utf8') for name, value in data.items()}
    for name, (old, new) in changes.items():
        if updated[name].count(old) != 1:
            raise ValueError('Unexpected glidesort dependency occurrence')
        updated[name] = updated[name].replace(old, new)
    block = ('[[package]]\nname = "glidesort"\nversion = "0.1.2"\n'
             'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
             'checksum = "f2e102e6eb644d3e0b186fc161e4460417880a0a0b87d235f2e5b8fb30f2e9e0"\n\n')
    if updated['Cargo.lock'].count(block) != 1:
        raise ValueError('Unexpected glidesort lock entry')
    updated['Cargo.lock'] = updated['Cargo.lock'].replace(block, '')
    updated['crates/fff-core/src/sort_buffer.rs'] = SORT_ADAPTER
    lock = tomllib.loads(updated['Cargo.lock'])
    for package in lock['package']:
        if package['name'] == 'glidesort' or any(d.split()[0] == 'glidesort' for d in package.get('dependencies', [])):
            raise ValueError('glidesort remains in modified lockfile')
    rows = []
    for name, text in updated.items():
        payload = text.encode('utf8')
        (root / name).write_bytes(payload)
        rows.append({'path': name, 'originalSha256': SORT_INPUTS[name],
                     'modifiedSha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)})
    return {'files': rows, 'implementation': 'Rust standard-library stable slice sorting',
            'scope': 'Removes glidesort from modified build only; no performance or redistribution approval'}


def probe_sort_adapter(root, output, env):
    binary = output / 'sort-test'
    commands = [['rustc', '--edition=2021', '--test', str(root / 'crates/fff-core/src/sort_buffer.rs'),
                 '-C', 'link-arg=-Wl,-z,max-page-size=16384', '-o', str(binary)],
                [str(binary), '--test-threads=1']]
    log = output / 'sort-test.log'
    log.write_text('', encoding='utf8')
    for command in commands:
        done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
        with log.open('a', encoding='utf8') as stream:
            stream.write(' '.join(command) + '\n' + done.stdout + done.stderr)
        done.check_returncode()
    if '3 passed; 0 failed' not in done.stdout:
        raise ValueError('Stable sorting adapter tests did not complete')
    return {'commands': commands, 'tests': 3, 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}


def link_inputs(text, cwd=None):
    """GNU map LOAD records, not proof of which sections survived GC/LTO."""
    names = {line[5:].strip() for line in text.splitlines() if line.startswith('LOAD ')}
    # GNU bfd emits this synthetic entry; it is not a missing disk input,
    # even if an unrelated file with the same name happens to exist in cwd.
    synthetic = 'linker stubs' in names
    names.discard('linker stubs')
    paths = sorted({((Path(cwd) if cwd else Path.cwd()) / name).resolve() for name in names})
    if not paths:
        raise ValueError('GNU linker map lacks LOAD inputs')
    rows = [({'path': str(path), 'kind': 'file', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'bytes': path.stat().st_size, 'availableAfterLink': True} if path.is_file() else
             {'path': str(path), 'kind': 'file', 'availableAfterLink': False,
               'limitation': 'Input unavailable after link; no hash or exact removal cause claimed'})
            for path in paths]
    if synthetic:
        rows.append({'kind': 'linker-generated', 'name': 'linker stubs',
                     'availableAfterLink': False,
                     'limitation': 'GNU linker synthetic entry, not a filesystem input; no hash claimed'})
    return rows


def validate_and_probe(result, target, output, env):
    payload = result.read_bytes()
    _, needed = pty.audit.elf(payload)
    if not needed or set(needed) - {'libc.so.6', 'libm.so.6', 'libdl.so.2', 'libpthread.so.0',
                                    'librt.so.1', 'libgcc_s.so.1', 'ld-linux-aarch64.so.1'}:
        raise ValueError('Unexpected rebuilt fff dependency closure: ' + repr(needed))
    symbols = subprocess.check_output(['readelf', '--dyn-syms', '--wide', str(result)], text=True)
    exports = {line.split()[-1] for line in symbols.splitlines() if line.split() and ' UND ' not in line}
    # Require every function used by this Bun probe, not merely a successful dlopen.
    import re
    required = set(re.findall(r'^(fff_\w+):', PROBE, re.M))
    if required - exports:
        raise ValueError('Missing rebuilt fff exports: ' + repr(sorted(required - exports)))
    probe = output / 'probe.mjs'
    probe.write_text(PROBE, encoding='utf8')
    try:
        completed = subprocess.run(['bun', str(probe), str(result), str(output)], env=env,
                                   capture_output=True, text=True, check=True, timeout=40)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        text = '\n'.join(p.decode(errors='replace') if isinstance(p, bytes) else (p or '')
                         for p in [error.stdout, error.stderr])
        (output / 'search.log').write_text(text, encoding='utf8')
        print(text[-12000:], file=sys.stderr)
        raise
    (output / 'search.log').write_text(completed.stdout + completed.stderr, encoding='utf8')
    if MARKER not in completed.stdout:
        raise ValueError('fff search/glob probe did not complete')
    shutil.copyfile(result, target)
    return needed


def build(upstream, stage):
    if sys.platform != 'linux' or platform.machine() not in ('aarch64', 'arm64'):
        raise ValueError('fff rebuild requires native Linux arm64 CI')
    upstream, stage = Path(upstream).resolve(strict=True), Path(stage).resolve(strict=True)
    matches = list((upstream / 'node_modules/.bun').glob(
        '@ff-labs+fff-bin-linux-arm64-gnu@0.10.5*/node_modules/@ff-labs/fff-bin-linux-arm64-gnu/libfff_c.so'))
    if len(matches) != 1:
        raise ValueError('Expected one fixed fff glibc input')
    target = matches[0].resolve(strict=True)
    target.relative_to(upstream)
    if hashlib.sha256(target.read_bytes()).hexdigest() != ORIGINAL:
        raise ValueError('Unexpected original fff input')
    output, work = stage / 'native-fff-build', stage.parent / 'native-fff-build'
    output.mkdir(exist_ok=False)
    work.mkdir(exist_ok=False)
    zig = Path(shutil.which('zig') or '').resolve(strict=True)
    if hashlib.sha256((zig.parent.parent / 'zig.tar.xz').read_bytes()).hexdigest() != ZIG_SHA256:
        raise ValueError('Unexpected fixed Zig tool archive')
    if subprocess.check_output([str(zig), 'version'], text=True).strip() != '0.16.0':
        raise ValueError('Expected Zig 0.16.0')
    repo, commit, expected = pty.rust.sources.SOURCES['fff']
    data = pty.rust.sources.download_archive(f'https://codeload.github.com/{repo}/tar.gz/{commit}')
    pty.rust.sources.inspect_archive(data, expected)
    archive = output / f'fff-{commit}.tar.gz'
    archive.write_bytes(data)
    root = pty.rust.unpack_candidate(archive, expected, output / 'source')
    sort_adapter = replace_glidesort(root)
    lock = root / 'Cargo.lock'
    original_lock = lock.read_bytes()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('CARGO_', 'RUST', 'ZIG', 'ZLOB_', 'LIBZ_', 'LIBGIT2_'))
           and k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH')}
    env.update(CARGO_HOME=str(work / 'cargo-home'), CARGO_TARGET_DIR=str(work / 'target'),
               CARGO_TERM_COLOR='never', ZIG=str(zig), ZLOB_ZIG_CPU='baseline',
               LIBZ_SYS_STATIC='1', LIBGIT2_NO_VENDOR='0',
                RUSTFLAGS='-C linker=cc -C link-arg=-fuse-ld=bfd -C link-arg=-Wl,-z,max-page-size=16384')
    sort_probe = probe_sort_adapter(root, output, env)
    base = ['--locked', '--manifest-path', str(root / 'Cargo.toml')]
    commands = [
        ['cargo', 'fetch', *base, '--target', pty.rust.TARGET],
        ['cargo', 'tree', *base, '--offline', '--target', pty.rust.TARGET,
         '--edges', 'normal,build', '--prefix', 'none', '--format', '{p}|{l}|{f}', *FLAGS],
        ['cargo', 'rustc', *base, '--offline', '--release', '--target', pty.rust.TARGET, *FLAGS,
         '--message-format=json-render-diagnostics', '--', '-C', 'link-arg=-Wl,-Map=' + str(output / 'link.map')],
    ]
    for index, command in enumerate(commands):
        logpath = output / f'command-{index}.log'
        with logpath.open('w', encoding='utf8') as log, (output / f'command-{index}.stderr.log').open('w', encoding='utf8') as err:
            try:
                subprocess.run(command, cwd=root, env=env, stdout=log, stderr=err,
                               check=True, timeout=1200)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                print(logpath.read_text(encoding='utf8')[-12000:], file=sys.stderr)
                print((output / f'command-{index}.stderr.log').read_text(encoding='utf8')[-12000:], file=sys.stderr)
                raise
        if lock.read_bytes() != original_lock:
            raise ValueError('Cargo changed pinned fff lockfile')
    # Persist the target/feature-selected registry archives actually fetched for
    # this build. This does not turn build scripts or compiler inputs into a sandbox.
    packages = pty.rust.selected_packages((output / 'command-1.log').read_text(), tomllib.loads(original_lock.decode()))
    if any(package['name'] == 'glidesort' for package in packages):
        raise ValueError('glidesort remains in selected fff build graph')
    crates = output / 'crates'
    crates.mkdir()
    for package in packages:
        if not package.get('source'):
            continue
        if package['source'] != 'registry+https://github.com/rust-lang/crates.io-index':
            raise ValueError('Unexpected fff dependency source')
        filename = f"{package['name']}-{package['version']}.crate"
        cached = list((work / 'cargo-home/registry/cache').glob('*/' + filename))
        if len(cached) != 1:
            raise ValueError('Missing/ambiguous fetched crate: ' + filename)
        content = cached[0].read_bytes()
        pty.rust.sources.inspect_archive(content, package['checksum'])
        (crates / filename).write_bytes(content)
    inputs = link_inputs((output / 'link.map').read_text(), root)
    result = work / 'target' / pty.rust.TARGET / 'release/libfff_c.so'
    shutil.copyfile(result, output / 'libfff_c.so')
    needed = validate_and_probe(result, target, output, env)
    (stage / 'native-fff-build-review.json').write_text(json.dumps({
        'redistributionApproved': False, 'androidApproved': False,
        'originalNpmBinaryCorrespondenceProven': False,
        'scope': 'This fixed-source diagnostic build only; GNU LOAD is not section-level attribution',
        'sourceCommit': commit, 'archiveSha256': expected,
        'lockSha256': hashlib.sha256(original_lock).hexdigest(), 'features': FLAGS,
        'originalNpmSha256': ORIGINAL, 'rebuiltSha256': hashlib.sha256(result.read_bytes()).hexdigest(),
        'installedInput': str(target.relative_to(upstream)), 'needed': needed, 'commands': commands,
        'selectedPackages': packages, 'linkerLoadInputs': inputs,
        'sortAdapter': sort_adapter, 'sortProbe': sort_probe,
        'zigVersion': '0.16.0', 'zigArchiveSha256': ZIG_SHA256,
        'nativeDependencyEnvironment': {key: env[key] for key in ['LIBZ_SYS_STATIC', 'LIBGIT2_NO_VENDOR', 'ZLOB_ZIG_CPU']},
        'rustcVersion': subprocess.check_output(['rustc', '-vV'], text=True).strip(),
        'ccVersion': subprocess.check_output(['cc', '--version'], text=True).splitlines()[0],
        'searchGate': MARKER,
        'limitations': ['Cargo offline is not a build.rs sandbox',
                        'GNU LOAD input hashes do not supply host/toolchain corresponding source',
                        'libgit2/LMDB/MPL/Zig/Rust per-file notices and static linking remain under review',
                        'No Android physicalization, seccomp or application-domain acceptance']
    }, indent=2) + '\n', encoding='utf8')
    print('Fixed-source fff search/glob passed; redistribution remains BLOCKED')


if __name__ == '__main__':
    build(*sys.argv[1:])
