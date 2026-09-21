#!/usr/bin/env python3
"""Bundle-size report for audit-frontend-best-practices.

Usage:
    python bundle_report.py <repo_root> [--dist <dir>] [--run] [--out bundle.json]
                            [--evidence-dir audit/evidence/audit-frontend-best-practices]

Modes:
  default  : measure an existing build output (auto-detected: angular.json outputPath,
             dist/, build/, .next/static, .output/public) or the --dist directory.
  --run    : run the production build, writing into <evidence-dir>/dist so the audited
             repo tree is not modified:
               Angular : npx ng build --configuration production --output-path <evidence>/dist
               Vite    : npx vite build --outDir <evidence>/dist
               Nuxt    : refuses (NITRO_OUTPUT_DIR is unreliable) - build manually, then --dist
               Next.js : refuses (output dir cannot be redirected) - run `next build` yourself
                         if the working tree may be touched, then re-run with --dist .next/static
             Requires node_modules to be present; nothing is installed.

Output: per-file raw and gzip size, initial vs lazy classification, totals, and a
comparison with angular.json budgets (initial / anyComponentStyle / bundle) or the Vite
chunkSizeWarningLimit when present. Sizes use kB = 1000 bytes like the Angular CLI.
Read-only against the repo; writes only under the evidence dir / --out.
"""
import argparse
import gzip
import importlib.util
import json
import os
import re
import subprocess
import sys

def _audit_core_skills_dir():
    """Resolve the explicit core installation, or the original sibling layout."""
    env = os.environ.get("AUDIT_CORE_ROOT")
    if env:
        skills = os.path.join(env, "skills")
        if os.path.isdir(os.path.join(skills, "audit-code-scan")):
            return skills
        sys.exit("AUDIT_CORE_ROOT does not contain audit-core skills: " + env)
    sibling = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if os.path.isdir(os.path.join(sibling, "audit-code-scan")):
        return sibling
    sys.exit("audit-core is unavailable. Enable audit-core and restart Claude Code, "
             "or set AUDIT_CORE_ROOT to its plugin directory when running manually.")

_SKILLS = _audit_core_skills_dir()
_REPO_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
if not os.path.exists(_REPO_WALK):
    sys.exit("audit-code-scan must be reachable from this skill (audit-core plugin or sibling layout; expected " + _REPO_WALK + ")")
_rw_spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _REPO_WALK)
repo_walk = importlib.util.module_from_spec(_rw_spec)
_rw_spec.loader.exec_module(repo_walk)

# Build output is exactly what this report measures, so these folders are read even though
# the shared walker skips them, and large chunks are never dropped by the size cap.
BUILD_OUTPUT_DIRS = ("dist", "build", ".next", ".output")

INITIAL_PATTERNS = [r"^main[.-]", r"^polyfills[.-]", r"^runtime[.-]", r"^styles[.-]", r"^vendor[.-]",
                    r"^index[.-].*\.(js|css)$", r"^app[.-].*\.(js|css)$", r"^scripts[.-]", r"^chunk-vendors"]


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"(^|[^:\\\"'])//[^\n]*", r"\1", text)
        return json.loads(re.sub(r",(\s*[}\]])", r"\1", text))
    except (OSError, json.JSONDecodeError):
        return None


def parse_size(s):
    m = re.match(r"^\s*([\d.]+)\s*(kb|mb|b)?\s*$", str(s), re.I)
    if not m:
        return None
    return float(m.group(1)) * {"b": 1, "kb": 1000, "mb": 1_000_000}[(m.group(2) or "b").lower()]


def fmt(n):
    return f"{n/1000:.1f} kB" if n < 1_000_000 else f"{n/1_000_000:.2f} MB"


def detect(root):
    info = {"framework": None, "build_cmd": None, "dist": None, "budgets": [], "chunk_limit": None}
    ng = read_json(os.path.join(root, "angular.json"))
    if ng and ng.get("projects"):
        info["framework"] = "angular"
        for name, proj in ng["projects"].items():
            build = (proj.get("architect") or {}).get("build") or {}
            if not build:
                continue
            opts = build.get("options", {}) or {}
            prod = (build.get("configurations") or {}).get("production", {}) or {}
            info["budgets"] = prod.get("budgets") or opts.get("budgets") or []
            op = opts.get("outputPath")
            if isinstance(op, dict):
                op = op.get("base")
            info["dist"] = os.path.join(root, op) if op else os.path.join(root, "dist", name)
            info["project"] = name
            break
        info["build_cmd"] = ["npx", "ng", "build", "--configuration", "production"]
        return info
    for cfg in ("vite.config.ts", "vite.config.js", "vite.config.mjs", "vite.config.mts"):
        p = os.path.join(root, cfg)
        if os.path.exists(p):
            info["framework"] = "vite"
            with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                m = re.search(r"chunkSizeWarningLimit\s*:\s*(\d+)", fh.read())
            info["chunk_limit"] = int(m.group(1)) * 1000 if m else 500_000
            info["dist"] = os.path.join(root, "dist")
            info["build_cmd"] = ["npx", "vite", "build"]
            return info
    if any(os.path.exists(os.path.join(root, c)) for c in ("next.config.js", "next.config.mjs", "next.config.ts")):
        info.update(framework="next", dist=os.path.join(root, ".next", "static"))
        return info
    if any(os.path.exists(os.path.join(root, c)) for c in ("nuxt.config.ts", "nuxt.config.js")):
        info.update(framework="nuxt", dist=os.path.join(root, ".output", "public"))
        return info
    for d in ("dist", "build"):
        if os.path.isdir(os.path.join(root, d)):
            info.update(framework="unknown", dist=os.path.join(root, d))
    return info


def run_build(root, info, evidence_dir):
    if not os.path.isdir(os.path.join(root, "node_modules")):
        return None, "node_modules missing; run the package manager install first (not done by this script)"
    out_dir = os.path.abspath(os.path.join(evidence_dir, "dist"))
    os.makedirs(out_dir, exist_ok=True)
    if info["framework"] == "angular":
        cmd = info["build_cmd"] + ["--output-path", out_dir]
    elif info["framework"] == "vite":
        cmd = info["build_cmd"] + ["--outDir", out_dir, "--emptyOutDir"]
    else:
        return None, f"{info['framework']}: build output cannot be redirected; build manually and pass --dist"
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=1800, shell=(os.name == "nt"))
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"build failed to start: {e}"
    log = os.path.join(evidence_dir, "build.log")
    with open(log, "w", encoding="utf-8") as fh:
        fh.write(proc.stdout + "\n" + proc.stderr)
    if proc.returncode != 0:
        return None, f"build exited {proc.returncode}; see {log}"
    # Angular application builder nests output under browser/
    browser = os.path.join(out_dir, "browser")
    return (browser if os.path.isdir(browser) else out_dir), " ".join(cmd)


def measure(dist):
    files = []
    for p in repo_walk.iter_files(dist, globs=["*.js", "*.css", "*.mjs"], include_dirs=BUILD_OUTPUT_DIRS, max_bytes=None):
        fn = os.path.basename(p)
        raw = os.path.getsize(p)
        with open(p, "rb") as fh:
            gz = len(gzip.compress(fh.read(), compresslevel=6))
        initial = any(re.search(pat, fn) for pat in INITIAL_PATTERNS)
        files.append({"file": repo_walk.rel(dist, p), "raw": raw, "gzip": gz,
                      "type": "initial" if initial else "lazy", "kind": "css" if fn.endswith(".css") else "js"})
    maps = sum(1 for _ in repo_walk.iter_files(dist, globs=["*.map"], include_dirs=BUILD_OUTPUT_DIRS, max_bytes=None))
    return sorted(files, key=lambda f: -f["raw"]), maps


def compare(files, info):
    rows = []
    initial_total = sum(f["raw"] for f in files if f["type"] == "initial")
    for b in info.get("budgets") or []:
        t = b.get("type")
        warn, err = parse_size(b.get("maximumWarning") or 0), parse_size(b.get("maximumError") or 0)
        if t == "initial":
            actual = initial_total
        elif t == "anyComponentStyle":
            continue  # component styles are inlined into the bundle by the CLI; cannot measure post-build
        elif t in ("bundle", "any", "anyScript"):
            actual = max((f["raw"] for f in files if f["kind"] == "js"), default=0)
        else:
            continue
        status = "error" if err and actual > err else "warning" if warn and actual > warn else "ok"
        rows.append({"budget": t, "actual": actual, "warning": warn, "error": err, "status": status})
    if info.get("chunk_limit"):
        for f in files:
            if f["kind"] == "js" and f["raw"] > info["chunk_limit"]:
                rows.append({"budget": "chunkSizeWarningLimit", "actual": f["raw"], "warning": info["chunk_limit"],
                             "error": None, "status": "warning", "file": f["file"]})
    return rows, initial_total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--dist", default=None)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--evidence-dir", default=None)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    evidence = a.evidence_dir or os.path.join(root, "audit", "evidence", "audit-frontend-best-practices")
    info = detect(root)
    built_with, note = None, None
    dist = a.dist
    if a.run:
        dist, note = run_build(root, info, evidence)
        built_with = note if dist else None
    if not dist:
        dist = info.get("dist")
        if dist and os.path.isdir(os.path.join(dist, "browser")):
            dist = os.path.join(dist, "browser")
    result = {"root": root, "framework": info["framework"], "built_with": built_with, "dist": dist,
              "not_run_reason": None if (dist and os.path.isdir(dist)) else (note or "no build output found; run with --run or pass --dist")}
    if dist and os.path.isdir(dist):
        files, maps = measure(dist)
        rows, initial_total = compare(files, info)
        result.update(files=files, source_maps_in_output=maps, budgets=rows,
                      totals={"initial_raw": initial_total,
                              "initial_gzip": sum(f["gzip"] for f in files if f["type"] == "initial"),
                              "lazy_raw": sum(f["raw"] for f in files if f["type"] == "lazy"),
                              "lazy_chunks": sum(1 for f in files if f["type"] == "lazy")})
        print(f"framework={info['framework']} dist={dist}")
        print(f"initial: {fmt(initial_total)} raw / {fmt(result['totals']['initial_gzip'])} gzip; "
              f"lazy chunks: {result['totals']['lazy_chunks']} ({fmt(result['totals']['lazy_raw'])}); .map files: {maps}")
        print("\n| Chunk | Type | Raw | Gzip |\n|---|---|---|---|")
        for f in files[:25]:
            print(f"| {f['file']} | {f['type']} | {fmt(f['raw'])} | {fmt(f['gzip'])} |")
        if rows:
            print("\n| Budget | Actual | Warning | Error | Status |\n|---|---|---|---|---|")
            for r in rows:
                print(f"| {r['budget']}{(' ' + r['file']) if r.get('file') else ''} | {fmt(r['actual'])} | "
                      f"{fmt(r['warning']) if r['warning'] else '-'} | {fmt(r['error']) if r['error'] else '-'} | {r['status']} |")
        else:
            print("\n(no budgets configured to compare against)")
    else:
        print(f"bundle report not produced: {result['not_run_reason']}")
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        print(f"written: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
