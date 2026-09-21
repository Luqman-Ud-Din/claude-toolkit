#!/usr/bin/env python3
"""Automated pass: run a stack-specific pattern list over a repository and
emit candidate hits for manual tracing.

Usage:
    python grep_scan.py <repo_root> --patterns <consumer-skill>/scripts/patterns/<stack>.json
                        [--patterns more.json] [--out hits.json] [--md hits.md]
                        [--extra-skip migrations] [--include-dir build]

Pattern file format: see ../references/pattern-file-format.md. In short, a JSON array of
{"id", "pattern", "globs"?, "severity_hint"?, "description"?, "reference"?, "ignore_case"?}.

Every hit is a *candidate*, not a finding. The consumer skill must trace each hit back
to its input source and label it confirmed / likely / false-positive before it
becomes a finding. Folder skipping and text-file selection come from repo_walk.py so
every audit script reads the same files. Read-only: nothing in the audited repo is modified.
"""
import argparse
import fnmatch
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repo_walk  # noqa: E402


def load_patterns(paths):
    patterns = []
    for pf in paths:
        with open(pf, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            data = data.get("patterns", [])
        for p in data:
            flags = re.IGNORECASE if p.get("ignore_case", True) else 0
            p["_re"] = re.compile(p["pattern"], flags)
            patterns.append(p)
    return patterns


def scan(root, patterns, max_hits_per_pattern=500, extra_skip=(), include_dirs=()):
    hits = []
    counts = {p["id"]: 0 for p in patterns}
    for path in repo_walk.iter_files(root, extra_skip=extra_skip, include_dirs=include_dirs):
        base = os.path.basename(path)
        applicable = [p for p in patterns
                      if not p.get("globs") or any(fnmatch.fnmatch(base, g) for g in p["globs"])]
        if not applicable:
            continue
        lines = repo_walk.read_lines(path)
        rel = repo_walk.rel(root, path)
        for n, line in enumerate(lines, 1):
            for p in applicable:
                if counts[p["id"]] >= max_hits_per_pattern:
                    continue
                if p["_re"].search(line):
                    counts[p["id"]] += 1
                    hits.append({
                        "pattern_id": p["id"],
                        "severity_hint": p.get("severity_hint", "Medium"),
                        "description": p.get("description", ""),
                        "reference": p.get("reference", ""),
                        "file": rel,
                        "line": n,
                        "snippet": line.rstrip()[:300],
                        "status": "unreviewed",
                    })
    return hits, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--patterns", required=True, action="append", help="pattern JSON file(s)")
    ap.add_argument("--out", default=None, help="write hits JSON here")
    ap.add_argument("--md", default=None, help="write a Markdown hit table here")
    ap.add_argument("--max-hits-per-pattern", type=int, default=500)
    ap.add_argument("--extra-skip", action="append", default=[], help="additional folder names to skip")
    ap.add_argument("--include-dir", action="append", default=[], help="default-skipped folder names to scan anyway")
    args = ap.parse_args()

    patterns = load_patterns(args.patterns)
    hits, counts = scan(args.root, patterns, args.max_hits_per_pattern, args.extra_skip, args.include_dir)

    result = {"root": os.path.abspath(args.root), "pattern_files": args.patterns,
              "counts": counts, "hits": hits}
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("| Pattern | Sev hint | Location | Snippet |\n|---|---|---|---|\n")
            for h in hits:
                snippet = h["snippet"].replace("|", "\\|")
                fh.write(f"| {h['pattern_id']} | {h['severity_hint']} | `{h['file']}:{h['line']}` | `{snippet[:120]}` |\n")
    print(json.dumps({"total_hits": len(hits), "counts": counts}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
