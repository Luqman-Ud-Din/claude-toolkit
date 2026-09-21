#!/usr/bin/env python3
"""Detect the technology stack(s) of a repository so an audit skill can load
only the matching references/<stack>.md file.

Usage:
    python detect_stack.py [repo_root] [--force] [--write]

Behaviour:
  * If <repo_root>/audit/stack.json exists (written by audit-application) it is
    returned as-is unless --force is given, so every child skill sees the same
    answer.
  * Otherwise the repo is scanned for package manifests / project files and a
    stack.json-shaped document is printed (and written to audit/stack.json when
    --write is passed).

Output shape:
{
  "detected_at": "...",
  "root": "...",
  "stacks": [
     {"id": "dotnet", "reference": "dotnet.md", "evidence": ["Foo.csproj"], "roots": ["InventoryBackend"]}
  ],
  "primary_backend": "dotnet" | null,
  "primary_frontend": "angular" | null,
  "multi_tenant": null          # filled in by audit-application after asking the user
}
Read-only: never modifies the audited code.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

SKIP_DIRS = {".git", "node_modules", "bin", "obj", "dist", "build", "target", ".venv", "venv",
             "__pycache__", ".idea", ".vs", "packages", "coverage", ".angular", ".next", "audit"}

BACKEND_IDS = {"dotnet", "java-spring", "node-express", "python-django"}
FRONTEND_IDS = {"angular", "react", "vue"}


def _read(path, limit=200_000):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def detect(root):
    stacks = {}

    def add(sid, evidence, sub_root, reference=None):
        entry = stacks.setdefault(sid, {"id": sid, "reference": reference if reference is not None else f"{sid}.md",
                                        "evidence": [], "roots": []})
        if evidence not in entry["evidence"]:
            entry["evidence"].append(evidence)
        rel = os.path.relpath(sub_root, root) or "."
        if rel not in entry["roots"]:
            entry["roots"].append(rel)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        depth = os.path.relpath(dirpath, root).count(os.sep)
        if depth > 4:
            dirnames[:] = []
            continue
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            low = fn.lower()
            if low.endswith((".csproj", ".sln", ".fsproj")):
                add("dotnet", rel, dirpath)
            elif low in ("pom.xml", "build.gradle", "build.gradle.kts"):
                content = _read(full)
                if "spring" in content.lower():
                    add("java-spring", rel, dirpath)
                else:
                    add("java-spring", rel + " (no spring marker; treat as generic Java)", dirpath)
            elif low == "package.json":
                content = _read(full)
                try:
                    pkg = json.loads(content)
                except json.JSONDecodeError:
                    pkg = {}
                deps = {}
                for key in ("dependencies", "devDependencies", "peerDependencies"):
                    deps.update(pkg.get(key, {}) or {})
                if "@angular/core" in deps:
                    add("angular", rel, dirpath)
                if "react" in deps or "next" in deps:
                    add("react", rel, dirpath)
                if "vue" in deps or "nuxt" in deps:
                    add("vue", rel, dirpath)
                if any(d in deps for d in ("express", "fastify", "koa", "@nestjs/core", "hapi", "@hapi/hapi")):
                    add("node-express", rel, dirpath)
            elif low in ("requirements.txt", "pyproject.toml", "pipfile", "setup.py", "manage.py"):
                content = _read(full).lower()
                if "django" in content or low == "manage.py":
                    add("python-django", rel, dirpath)
                elif low in ("requirements.txt", "pyproject.toml") and re.search(r"\b(flask|fastapi)\b", content):
                    add("python-django", rel + " (flask/fastapi; use python-django.md generic sections)", dirpath)
            elif low in ("dockerfile", "docker-compose.yml", "docker-compose.yaml") or low.endswith(".dockerfile"):
                add("containers", rel, dirpath, reference=None)

    ordered = sorted(stacks.values(), key=lambda s: s["id"])
    backend = next((s["id"] for s in ordered if s["id"] in BACKEND_IDS), None)
    frontend = next((s["id"] for s in ordered if s["id"] in FRONTEND_IDS), None)
    return {
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "root": os.path.abspath(root),
        "stacks": ordered,
        "primary_backend": backend,
        "primary_frontend": frontend,
        "multi_tenant": None,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--force", action="store_true", help="ignore an existing audit/stack.json")
    ap.add_argument("--write", action="store_true", help="write audit/stack.json (creates audit/ only)")
    args = ap.parse_args()

    cached = os.path.join(args.root, "audit", "stack.json")
    if os.path.exists(cached) and not args.force:
        print(_read(cached))
        return 0

    result = detect(args.root)
    text = json.dumps(result, indent=2)
    if args.write:
        os.makedirs(os.path.dirname(cached), exist_ok=True)
        with open(cached, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    if not result["stacks"]:
        print("WARNING: no known stack markers found; use references/stack-reference-template.md", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
