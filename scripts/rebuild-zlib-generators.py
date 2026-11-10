"""Isolated host rebuild of two zlib maintenance generators, not source approval."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


SYSTEM_ROOT = Path('/usr')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_aarch64_elf(path, types):
    raw = path.read_bytes()
    if (len(raw) < 64 or raw[:7] != b'\x7fELF\x02\x01\x01'
            or int.from_bytes(raw[16:18], 'little') not in types
            or int.from_bytes(raw[18:20], 'little') != 183
            or int.from_bytes(raw[20:24], 'little') != 1):
        raise ValueError('Zlib generator output is not expected AArch64 ELF64 LE')


def rebuild(source, output, env):
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve(strict=True)
    directory = output / 'zlib-generator-rebuild'
    if source.is_relative_to(directory) or directory.is_relative_to(source):
        raise ValueError('Zlib source and diagnostic output overlap')
    directory.mkdir(exist_ok=False)
    copied = directory / 'source'
    copied.mkdir()
    protected, source_rows = {}, []
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('Unexpected pristine zlib symlink')
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('Unexpected pristine zlib special file')
        raw = path.read_bytes()
        if raw.startswith(b'\x7fELF'):
            raise ValueError('Unexpected ELF in pristine zlib source')
        relative = path.relative_to(source)
        destination = copied / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        checksum = hashlib.sha256(raw).hexdigest()
        protected[path] = checksum
        protected[destination] = checksum
        source_rows.append({'path': relative.as_posix(), 'bytes': len(raw), 'sha256': checksum})
    for name in ['crc32.c', 'inftrees.c', 'zutil.c', 'crc32.h', 'inffixed.h', 'LICENSE']:
        if not (copied / name).is_file():
            raise ValueError('Missing zlib generator source input')
    compiler_name = shutil.which('gcc')
    if not compiler_name:
        raise ValueError('Missing host GCC')
    compiler = Path(compiler_name).resolve(strict=True)
    compiler_digest = digest(compiler)
    child_env = dict(env)
    for key in ['CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'OBJC_INCLUDE_PATH',
                'GCC_EXEC_PREFIX', 'COMPILER_PATH', 'LIBRARY_PATH', 'DEPENDENCIES_OUTPUT',
                'SUNPRO_DEPENDENCIES', 'LD_PRELOAD', 'LD_LIBRARY_PATH']:
        child_env.pop(key, None)
    commands = []

    def run(command, cwd, log):
        commands.append({'command': command, 'cwd': str(cwd), 'log': log.relative_to(output).as_posix()})
        try:
            done = subprocess.run(command, cwd=cwd, env=child_env, capture_output=True, timeout=120)
        except subprocess.TimeoutExpired as error:
            log.write_bytes((shlex.join(command) + '\nTIMEOUT\n').encode()
                            + (error.stdout or b'') + (error.stderr or b''))
            raise
        log.write_bytes((shlex.join(command) + '\n').encode() + done.stdout + done.stderr)
        done.check_returncode()
        return done.stdout

    version = run([str(compiler), '--version'], directory, directory / 'compiler.log')
    headers, rows = {}, []
    for mode, define, sources, filename in [
        ('makecrch', 'MAKECRCH', ['crc32.c'], 'crc32.h'),
        ('makefixed', 'MAKEFIXED', ['inftrees.c', 'zutil.c'], 'inffixed.h')]:
        work = directory / mode
        work.mkdir()
        objects, units = [], []
        for index, name in enumerate(sources):
            preprocessed, dep, obj = [work / f'{index:04d}{suffix}' for suffix in ['.i', '.d', '.o']]
            command = [str(compiler), '-O2', '-std=c17', '-I' + str(copied), '-D' + define,
                       '-MD', '-MF', str(dep), '-MT', obj.name, '-E', '-o', str(preprocessed), str(copied / name)]
            run(command, work, work / f'{index:04d}-preprocess.log')
            target, separator, body = dep.read_text(encoding='utf8').replace('\\\n', ' ').partition(':')
            if not separator or target.strip() != obj.name:
                raise ValueError('Unexpected zlib generator dependency target')
            dependencies = []
            for spelling in sorted(set(shlex.split(body))):
                path = Path(spelling)
                path = (path if path.is_absolute() else work / path).resolve(strict=True)
                checksum = digest(path)
                if path.is_relative_to(copied):
                    if protected.get(path) != checksum:
                        raise ValueError('Changed copied zlib dependency')
                    dependencies.append({'kind': 'source', 'path': path.relative_to(copied).as_posix(), 'sha256': checksum})
                else:
                    if not path.is_relative_to(SYSTEM_ROOT.resolve(strict=True)):
                        raise ValueError('Zlib host header outside approved /usr scope')
                    destination = directory / 'system-headers' / path.relative_to(SYSTEM_ROOT.resolve(strict=True))
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists() and digest(destination) != checksum:
                        raise ValueError('Zlib system-header snapshot drift')
                    destination.write_bytes(path.read_bytes())
                    protected[path] = checksum; protected[destination] = checksum
                    headers[str(path)] = {'path': str(path), 'copy': destination.relative_to(output).as_posix(),
                                          'sha256': checksum, 'bytes': path.stat().st_size}
                    dependencies.append({'kind': 'system', 'path': str(path), 'sha256': checksum})
            if name not in {r['path'] for r in dependencies if r['kind'] == 'source'}:
                raise ValueError('Missing zlib generator main dependency')
            protected[dep] = digest(dep)
            protected[preprocessed] = digest(preprocessed)
            run([str(compiler), '-O2', '-std=c17', '-c', str(preprocessed), '-o', str(obj)],
                work, work / f'{index:04d}-compile.log')
            require_aarch64_elf(obj, {1})
            protected[obj] = digest(obj)
            objects.append(str(obj))
            units.append({'source': name, 'preprocessed': preprocessed.relative_to(output).as_posix(),
                          'preprocessedSha256': protected[preprocessed], 'dependencies': dependencies,
                          'object': obj.relative_to(output).as_posix(), 'objectSha256': protected[obj]})
        executable = work / 'generator'
        run([str(compiler), *objects, '-o', str(executable)], work, work / 'link.log')
        require_aarch64_elf(executable, {2, 3})
        protected[executable] = digest(executable)
        stdout = run([str(executable)], work, work / 'run.log')
        generated = work / filename
        if mode == 'makefixed':
            generated.write_bytes(stdout)
        if not generated.is_file() or generated.read_bytes() != (copied / filename).read_bytes():
            raise ValueError('Regenerated zlib header differs: ' + filename)
        rows.append({'mode': mode, 'define': define, 'units': units,
                     'output': generated.relative_to(output).as_posix(),
                     'bytes': generated.stat().st_size, 'sha256': digest(generated)})
    for path, checksum in {**protected, compiler: compiler_digest}.items():
        if digest(path) != checksum:
            raise ValueError('Zlib generator rebuild changed protected input')
    result = {'compiler': str(compiler), 'compilerSha256': compiler_digest,
              'compilerVersion': version.decode('utf8'), 'sourceFiles': source_rows,
              'systemHeaders': [headers[path] for path in sorted(headers)],
              'outputs': rows, 'commands': commands,
              'files': [{'path': path.relative_to(output).as_posix(), 'bytes': path.stat().st_size,
                         'sha256': digest(path)} for path in sorted(directory.rglob('*')) if path.is_file()],
              'redistributionApproved': False, 'androidApproved': False, 'relinkingApproved': False,
              'fullCorrespondingSourceApproved': False,
              'scope': 'Two host maintenance generators rebuilt from copied pristine zlib inputs via retained actual GCC preprocessed C; output byte comparisons only, not all generators, original toolchain closure or legal/Android approval'}
    (directory / 'review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print('ANDCODE_ZLIB_GENERATORS_REBUILT_OK 2 outputs (Linux CI only)')
    return result


if __name__ == '__main__':
    rebuild(sys.argv[1], sys.argv[2], os.environ)
