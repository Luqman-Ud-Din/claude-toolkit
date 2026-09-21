#!/usr/bin/env python3
"""Shared repository walker for audit-* skill scripts.

One place that decides which folders are skipped and which files count as text,
so every audit script reads the same slice of the repository.

Import from another skill's script (the skills live side by side). Load it by file path
under a unique module name; do not put this folder on sys.path (see references/repo-walk-api.md):

    import importlib.util, os
    _SKILLS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    _WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
    _spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _WALK)
    repo_walk = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(repo_walk)

    for path in repo_walk.iter_files(root, exts={".cs", ".ts"}):
        text = repo_walk.read_text(path)
        print(repo_walk.rel(root, path))

Run directly to list what an audit would read:

    python repo_walk.py <repo_root> [--ext .cs --ext .ts] [--extra-skip migrations] [--count]
                        [--skip-hidden] [--show-skipped]

Read-only: nothing in the audited repository is modified.
"""
import argparse
import fnmatch
import os
import sys

# Folders no audit script should descend into: VCS metadata, dependency caches,
# build output, IDE state, and the audit workspace itself.
SKIP_DIRS = frozenset({
    ".git", "node_modules", "bin", "obj", "dist", "build", "target", ".venv", "venv",
    "__pycache__", ".idea", ".vs", "coverage", ".angular", ".next", ".nuxt", ".output",
    ".gradle", ".tox", ".terraform", "audit",
})

# Extensions treated as readable source, config, or docs.
TEXT_EXT = frozenset({
    ".cs", ".cshtml", ".razor", ".java", ".kt", ".xml", ".properties", ".yml", ".yaml", ".json",
    ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue", ".html", ".htm", ".py", ".sql", ".md",
    ".env", ".config", ".toml", ".ini", ".txt", ".sh", ".ps1", ".dockerfile", ".gradle", ".csproj",
    ".props", ".tf", ".bicep", ".prisma", ".scss", ".css",
})

# Extension-less file names treated as text.
TEXT_NAMES = frozenset({"dockerfile", "makefile", "web.config", "jenkinsfile", "procfile"})

MAX_BYTES = 2_000_000


def is_text_file(name, exts=None, names=None):
    """True when a file name matches the given (or default) text extensions or names."""
    low = name.lower()
    ext = os.path.splitext(low)[1]
    return ext in (exts if exts is not None else TEXT_EXT) or low in (names if names is not None else TEXT_NAMES)


def iter_files(root, exts=None, names=None, globs=None, skip_dirs=None, extra_skip=(),
               include_dirs=(), max_bytes=MAX_BYTES, max_depth=None, skip_hidden=False, skipped=None):
    """Yield absolute paths of text files under root.

    exts         set of lowercase extensions to accept (default TEXT_EXT)
    names        set of lowercase extension-less names to accept (default TEXT_NAMES); passing
                 exts alone still accepts TEXT_NAMES, so pass names=frozenset() to accept only exts
    globs        optional filename globs; when given, a file must match one of them
    skip_dirs    replaces SKIP_DIRS entirely
    extra_skip   folder names skipped in addition to the defaults (e.g. "migrations")
    include_dirs folder names that must NOT be skipped even if in the defaults (e.g. "build")
    max_bytes    files larger than this are ignored; None disables the limit
    max_depth    maximum folder depth below root; None means unlimited
    skip_hidden  when true, also skip folders whose name starts with "." unless listed in include_dirs
    skipped      optional list; (abs_path, reason) is appended for every file left out because of
                 max_bytes or an OSError while reading its size
    """
    skip = set(skip_dirs if skip_dirs is not None else SKIP_DIRS)
    skip.update(extra_skip)
    skip.difference_update(include_dirs)
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip
                             and not (skip_hidden and d.startswith(".") and d not in include_dirs))
        if max_depth is not None:
            depth = os.path.relpath(dirpath, root).count(os.sep) if dirpath != root else 0
            if depth >= max_depth:
                dirnames[:] = []
        for fn in sorted(filenames):
            if globs:
                if not any(fnmatch.fnmatch(fn, g) for g in globs):
                    continue
            elif not is_text_file(fn, exts, names):
                continue
            path = os.path.join(dirpath, fn)
            if max_bytes is not None:
                try:
                    size = os.path.getsize(path)
                except OSError as exc:
                    if skipped is not None:
                        skipped.append((path, "unreadable: %s" % exc))
                    continue
                if size > max_bytes:
                    if skipped is not None:
                        skipped.append((path, "too large: %d bytes > max_bytes %d" % (size, max_bytes)))
                    continue
            yield path


def read_text(path, limit=None):
    """Read a file as UTF-8, ignoring undecodable bytes. Returns '' on error."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit) if limit else fh.read()
    except OSError:
        return ""


def read_lines(path):
    """Read a file into a list of lines (newline kept). Returns [] on error."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.readlines()
    except OSError:
        return []


def rel(root, path):
    """Repo-relative path with forward slashes, as used in findings locations."""
    return os.path.relpath(path, root).replace(os.sep, "/")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--ext", action="append", help="accept only these extensions (repeatable)")
    ap.add_argument("--extra-skip", action="append", default=[], help="additional folder names to skip")
    ap.add_argument("--include-dir", action="append", default=[], help="default-skipped folder names to read anyway")
    ap.add_argument("--count", action="store_true", help="print only the number of files")
    ap.add_argument("--skip-hidden", action="store_true",
                    help="also skip folders whose name starts with '.' (except --include-dir names)")
    ap.add_argument("--show-skipped", action="store_true",
                    help="after the list or count, print 'skipped: <path> (<reason>)' for files left out by size or read errors")
    a = ap.parse_args()
    exts = {e.lower() if e.startswith(".") else "." + e.lower() for e in a.ext} if a.ext else None
    skipped = [] if a.show_skipped else None
    files = [rel(a.root, p) for p in iter_files(a.root, exts=exts, extra_skip=a.extra_skip, include_dirs=a.include_dir,
                                                skip_hidden=a.skip_hidden, skipped=skipped)]
    if a.count:
        print(len(files))
    else:
        print("\n".join(files))
    for path, reason in skipped or []:
        print("skipped: %s (%s)" % (rel(a.root, path), reason))
    return 0


if __name__ == "__main__":
    sys.exit(main())
