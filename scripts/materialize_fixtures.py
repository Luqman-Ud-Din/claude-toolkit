#!/usr/bin/env python3
"""Copy eval templates to a temporary directory, substituting local fixture values.

Never modifies tracked files. Delete the printed directory after testing.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VARIABLE = re.compile(r"\$\{(TOOLKIT_[A-Z_]+)\}")


def materialize(source, values):
    files = [p for p in source.rglob('*') if p.is_file()]
    replacements = {}
    for path in files:
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeError:
            continue
        names = VARIABLE.findall(text)
        missing = [name for name in names if not values.get(name)]
        if missing:
            raise ValueError('Missing local values: ' + ', '.join(sorted(set(missing))))
        if names:
            def replace(match):
                value = values[match[1]]
                return json.dumps(value)[1:-1] if path.suffix == '.json' else value
            replacements[path.relative_to(source)] = VARIABLE.sub(replace, text)
    destination = Path(tempfile.mkdtemp(prefix='claude-toolkit-private-fixtures-'))
    try:
        shutil.copytree(source, destination, dirs_exist_ok=True)
        for relative, text in replacements.items():
            (destination / relative).write_text(text, encoding='utf-8')
    except BaseException:
        shutil.rmtree(destination)
        raise
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Eval directory to copy')
    parser.add_argument('--local-settings', type=Path, help='Explicit ignored settings file; otherwise uses environment')
    args = parser.parse_args()
    source = args.source.resolve()
    if not source.is_dir():
        parser.error('source must be an existing eval directory')
    values = dict(os.environ)
    if args.local_settings:
        settings = json.loads(args.local_settings.read_text(encoding='utf-8'))
        values.update({k: v for k, v in settings.get('env', {}).items() if k.startswith('TOOLKIT_')})
    try:
        print(materialize(source, values))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
