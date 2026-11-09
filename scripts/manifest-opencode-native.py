"""Hash the diagnostic upload's dereferenced file tree, never external links."""
import hashlib
from pathlib import Path
import sys


def manifest(stage):
    stage = Path(stage)
    root = stage.resolve(strict=True)
    rows = []

    def visit(path, ancestors):
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
        if resolved.is_dir():
            if resolved in ancestors:
                raise ValueError('Diagnostic directory link cycle')
            for child in sorted(path.iterdir()):
                visit(child, ancestors | {resolved})
        elif resolved.is_file():
            name = path.as_posix()
            if any(c in name for c in '\\\r\n'):
                raise ValueError('Unsupported diagnostic manifest filename')
            with path.open('rb') as source:
                digest = hashlib.file_digest(source, 'sha256').hexdigest()
            rows.append(f'{digest}  {name}\n')
        else:
            raise ValueError('Diagnostic special file')

    visit(stage, set())
    if not rows:
        raise ValueError('Empty diagnostic upload')
    return ''.join(rows)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8', newline='\n')
    sys.stdout.write(manifest(sys.argv[1]))
