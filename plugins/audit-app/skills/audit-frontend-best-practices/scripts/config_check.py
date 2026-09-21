#!/usr/bin/env python3
"""Config checker for audit-frontend-best-practices.

Reads frontend build/type/lint configuration and prints a preliminary scorecard.

Usage:
    python config_check.py <repo_root> [--out audit/evidence/audit-frontend-best-practices/config.json]

What it reads (all read-only):
  * tsconfig*.json (root, src/, apps/*, projects/*): resolves the `extends` chain and
    reports the effective strict flags (strict, noImplicitAny, strictNullChecks,
    strictTemplates for Angular, checkJs for JS projects).
  * angular.json / project.json: per-project budgets, and the production configuration's
    sourceMap / optimization / outputHashing / namedChunks / builder.
  * vite.config.*, next.config.*, nuxt.config.*, vue.config.js, .env.production (CRA):
    sourcemap / minify / chunkSizeWarningLimit / productionBrowserSourceMaps / compress.
  * package.json: lint script + framework ESLint plugin, size-limit/bundlesize tools,
    build script (does it pass a production configuration), dev server used as start.
  * Backend hints when a backend is present in the same repo: static-file serving
    without compression (Program.cs, express app). Only the frontend-serving slice.

Output: JSON with `checks` (raw facts, each with file/line) and `scorecard`
(category -> pass|partial|fail|unknown with a reason). Everything is a
candidate for the manual pass, not a final verdict.
"""
import argparse
import glob
import importlib.util
import json
import os
import re
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
STRICT_FLAGS = ["strict", "noImplicitAny", "strictNullChecks", "strictFunctionTypes",
                "strictPropertyInitialization", "noImplicitReturns", "checkJs"]


def read(path):
    return repo_walk.read_text(path)


def load_jsonc(path):
    """Parse JSON with comments and trailing commas (tsconfig style)."""
    text = read(path)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|[^:\\\"'])//[^\n]*", r"\1", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def line_of(path, needle):
    for n, line in enumerate(read(path).splitlines(), 1):
        if needle in line:
            return n
    return None


def find_files(root, names, max_depth=3):
    # Shared skip list and size cap from audit-code-scan; `names` are full-match regexes on
    # the file name (globs=["*"] so .env.production and .eslintrc are offered too).
    out = [p for p in repo_walk.iter_files(root, globs=["*"], max_depth=max_depth)
           if any(re.fullmatch(pat, os.path.basename(p)) for pat in names)]
    return sorted(set(out))


def rel(root, path):
    return repo_walk.rel(root, path)


# ---------- tsconfig ----------
def resolve_tsconfig(path, seen=None):
    seen = seen or set()
    if path in seen or not os.path.exists(path):
        return {}, {}
    seen.add(path)
    doc = load_jsonc(path) or {}
    co, aco = {}, {}
    ext = doc.get("extends")
    if isinstance(ext, str) and not ext.startswith("@") and not ext.startswith("."):
        ext = None  # package extends (e.g. @tsconfig/node18) - cannot resolve offline
    if isinstance(ext, str):
        base = os.path.normpath(os.path.join(os.path.dirname(path), ext))
        if not base.endswith(".json"):
            base += ".json"
        co, aco = resolve_tsconfig(base, seen)
    co.update(doc.get("compilerOptions", {}) or {})
    aco.update(doc.get("angularCompilerOptions", {}) or {})
    return co, aco


def check_tsconfigs(root, checks):
    files = find_files(root, [r"tsconfig\.json", r"tsconfig\.app\.json", r"tsconfig\.base\.json"])
    result = []
    for f in files:
        co, aco = resolve_tsconfig(f)
        flags = {k: co.get(k) for k in STRICT_FLAGS}
        flags["strictTemplates"] = aco.get("strictTemplates")
        effective_strict = bool(co.get("strict")) and co.get("strictNullChecks") is not False \
            and co.get("noImplicitAny") is not False
        entry = {"file": rel(root, f), "line": line_of(f, "strict") or line_of(f, "compilerOptions"),
                 "flags": flags, "effective_strict": effective_strict}
        result.append(entry)
        checks.append({"check": "tsconfig-strict", "file": entry["file"], "line": entry["line"],
                       "value": effective_strict, "detail": flags})
    return result


# ---------- angular.json / project.json ----------
def parse_size(s):
    m = re.match(r"^\s*([\d.]+)\s*(kb|mb|b)?\s*$", str(s), re.I)
    if not m:
        return None
    n = float(m.group(1)); u = (m.group(2) or "b").lower()
    return n * {"b": 1, "kb": 1000, "mb": 1_000_000}[u]


def check_angular(root, checks):
    out = []
    for f in find_files(root, [r"angular\.json", r"project\.json"]):
        doc = load_jsonc(f)
        if not doc:
            continue
        projects = doc.get("projects") or ({doc.get("name", os.path.basename(os.path.dirname(f))): doc} if "targets" in doc or "architect" in doc else {})
        for name, proj in projects.items():
            build = ((proj.get("architect") or proj.get("targets") or {}).get("build") or {})
            if not build:
                continue
            opts = build.get("options", {}) or {}
            confs = build.get("configurations", {}) or {}
            prod = confs.get("production", {}) or {}
            budgets = prod.get("budgets") or opts.get("budgets") or []
            has_error_budget = any(b.get("maximumError") for b in budgets)
            entry = {
                "file": rel(root, f), "project": name, "builder": build.get("builder"),
                "budgets": budgets, "budget_error_threshold": has_error_budget,
                "production": {
                    "sourceMap": prod.get("sourceMap", opts.get("sourceMap")),
                    "optimization": prod.get("optimization", opts.get("optimization")),
                    "outputHashing": prod.get("outputHashing", opts.get("outputHashing")),
                    "namedChunks": prod.get("namedChunks", opts.get("namedChunks")),
                    "extractLicenses": prod.get("extractLicenses", opts.get("extractLicenses")),
                },
                "configurations": sorted(confs.keys()),
                "outputPath": opts.get("outputPath"),
            }
            out.append(entry)
            sm = entry["production"]["sourceMap"]
            sm_bad = sm is True or (isinstance(sm, dict) and (sm.get("scripts") is True) and not sm.get("hidden"))
            checks.append({"check": "prod-sourcemap", "file": entry["file"], "line": line_of(f, "sourceMap"),
                           "value": sm, "bad": sm_bad, "project": name})
            opt = entry["production"]["optimization"]
            checks.append({"check": "prod-optimization", "file": entry["file"], "line": line_of(f, "optimization"),
                           "value": opt, "bad": opt is False, "project": name})
            checks.append({"check": "budgets", "file": entry["file"], "line": line_of(f, "budgets"),
                           "value": len(budgets), "bad": not budgets, "error_threshold": has_error_budget, "project": name})
            b = build.get("builder") or ""
            checks.append({"check": "builder", "file": entry["file"], "line": line_of(f, "builder"),
                           "value": b, "bad": b.endswith(":browser")})
    return out


# ---------- bundler configs ----------
def check_bundlers(root, checks):
    out = []
    for f in find_files(root, [r"vite\.config\.(ts|js|mjs|cjs|mts)", r"next\.config\.(js|mjs|ts|cjs)",
                               r"nuxt\.config\.(ts|js|mjs)", r"vue\.config\.(js|cjs|ts)", r"\.env\.production"]):
        text = read(f); base = os.path.basename(f); r = rel(root, f)
        entry = {"file": r, "kind": base}
        def grab(pattern, key):
            m = re.search(pattern, text)
            if m:
                entry[key] = m.group(1)
                line = text[:m.start()].count("\n") + 1
                return m.group(1), line
            return None, None
        if base.startswith("vite.config") or base.startswith("vue.config") or base.startswith("nuxt.config"):
            v, ln = grab(r"sourcemap\s*:\s*(true|false|['\"]hidden['\"]|\{[^}]*\})", "sourcemap")
            if v is not None:
                bad = v == "true" or ("client" in v and re.search(r"client\s*:\s*true", v) is not None)
                checks.append({"check": "prod-sourcemap", "file": r, "line": ln, "value": v, "bad": bad})
            v, ln = grab(r"productionSourceMap\s*:\s*(true|false)", "productionSourceMap")
            if v is not None:
                checks.append({"check": "prod-sourcemap", "file": r, "line": ln, "value": v, "bad": v == "true"})
            v, ln = grab(r"minify\s*:\s*(false|true|['\"]\w+['\"])", "minify")
            if v is not None:
                checks.append({"check": "prod-optimization", "file": r, "line": ln, "value": v, "bad": v == "false"})
            v, ln = grab(r"chunkSizeWarningLimit\s*:\s*(\d+)", "chunkSizeWarningLimit")
            checks.append({"check": "budgets", "file": r, "line": ln, "value": v, "bad": v is None, "error_threshold": False})
        if base.startswith("next.config"):
            v, ln = grab(r"productionBrowserSourceMaps\s*:\s*(true|false)", "productionBrowserSourceMaps")
            checks.append({"check": "prod-sourcemap", "file": r, "line": ln, "value": v, "bad": v == "true"})
            v, ln = grab(r"swcMinify\s*:\s*(true|false)", "swcMinify")
            if v is not None:
                checks.append({"check": "prod-optimization", "file": r, "line": ln, "value": v, "bad": v == "false"})
            v, ln = grab(r"compress\s*:\s*(true|false)", "compress")
            if v == "false":
                checks.append({"check": "compression", "file": r, "line": ln, "value": v, "bad": True})
        if base == ".env.production":
            v, ln = grab(r"GENERATE_SOURCEMAP\s*=\s*(true|false)", "GENERATE_SOURCEMAP")
            if v is not None:
                checks.append({"check": "prod-sourcemap", "file": r, "line": ln, "value": v, "bad": v == "true"})
        out.append(entry)
    return out


# ---------- package.json ----------
def check_packages(root, checks):
    out = []
    for f in find_files(root, [r"package\.json"], max_depth=2):
        doc = load_jsonc(f) or {}
        deps = {}
        for k in ("dependencies", "devDependencies"):
            deps.update(doc.get(k, {}) or {})
        scripts = doc.get("scripts", {}) or {}
        r = rel(root, f)
        fw = "angular" if "@angular/core" in deps else "react" if "react" in deps or "next" in deps else "vue" if "vue" in deps or "nuxt" in deps else None
        if not fw:
            continue
        plugin = {"angular": "@angular-eslint/eslint-plugin", "react": "eslint-plugin-react-hooks", "vue": "eslint-plugin-vue"}[fw]
        has_plugin = plugin in deps or (fw == "angular" and "angular-eslint" in deps)
        eslint_cfg = bool(find_files(os.path.dirname(f), [r"\.eslintrc(\.\w+)?", r"eslint\.config\.(js|mjs|cjs|ts)"], max_depth=1)) or "eslintConfig" in doc
        lint_script = scripts.get("lint")
        lint_runnable = bool(lint_script) and (("ng lint" not in lint_script) or "@angular-eslint/builder" in deps)
        size_tool = next((t for t in ("size-limit", "bundlesize", "bundlewatch") if t in deps), None)
        build = " ".join(v for k, v in scripts.items() if k.startswith("build"))
        prod_build = bool(re.search(r"--configuration[= ]production|--prod\b|--mode[= ]production|next build|nuxt build|vite build|vue-cli-service build|react-scripts build", build))
        start = scripts.get("start", "")
        dev_start = bool(re.search(r"^(ng serve|vite\b|react-scripts start|next dev|nuxt dev|vue-cli-service serve)", start.strip()))
        entry = {"file": r, "framework": fw, "framework_version": deps.get({"angular": "@angular/core", "react": "react", "vue": "vue"}[fw]),
                 "eslint_config": eslint_cfg, "eslint_plugin": has_plugin, "lint_script": lint_script,
                 "lint_runnable": lint_runnable, "size_tool": size_tool, "prod_build_script": prod_build,
                 "dev_server_start": dev_start, "typescript": "typescript" in deps}
        out.append(entry)
        checks.append({"check": "lint", "file": r, "line": line_of(f, '"lint"'), "value": entry["lint_script"],
                       "bad": not (eslint_cfg and has_plugin and lint_runnable),
                       "detail": {"config": eslint_cfg, "plugin": has_plugin, "runnable": lint_runnable}})
        checks.append({"check": "size-tool", "file": r, "line": None, "value": size_tool, "bad": size_tool is None})
        checks.append({"check": "build-script", "file": r, "line": line_of(f, '"build'), "value": build, "bad": not prod_build})
        if dev_start:
            checks.append({"check": "dev-server-start", "file": r, "line": line_of(f, '"start"'), "value": start, "bad": False,
                           "note": "start runs a dev server; confirm the deploy does not use it"})
    return out


# ---------- backend slice ----------
def check_backend(root, checks):
    out = []
    for f in find_files(root, [r"Program\.cs", r"Startup\.cs"], max_depth=3):
        t = read(f)
        if "UseStaticFiles" in t or "UseSpa" in t or "MapFallbackToFile" in t:
            entry = {"file": rel(root, f), "serves_frontend": True,
                     "compression": "UseResponseCompression" in t,
                     "spa_fallback": "MapFallbackToFile" in t or "UseSpa" in t,
                     "cache_headers": "OnPrepareResponse" in t,
                     "dev_server_reference": bool(re.search(r"UseAngularCliServer|UseProxyToSpaDevelopmentServer|UseReactDevelopmentServer", t))}
            out.append(entry)
            checks.append({"check": "backend-static", "file": entry["file"], "line": line_of(f, "UseStaticFiles") or line_of(f, "UseSpa"),
                           "value": entry, "bad": not entry["compression"] or not entry["cache_headers"],
                           "note": "compression may be at the proxy; confirm before rating"})
    for f in find_files(root, [r"(server|app|index|main)\.(js|ts|mjs)"], max_depth=3):
        t = read(f)
        if "express.static" in t or "ServeStaticModule" in t or "fastifyStatic" in t or "@fastify/static" in t:
            entry = {"file": rel(root, f), "serves_frontend": True, "compression": "compression(" in t or "@fastify/compress" in t,
                     "spa_fallback": bool(re.search(r"get\(\s*['\"]\*['\"]|sendFile\([^)]*index\.html", t)),
                     "cache_headers": "maxAge" in t or "immutable" in t}
            out.append(entry)
            checks.append({"check": "backend-static", "file": entry["file"], "line": line_of(f, "express.static") or line_of(f, "ServeStaticModule"),
                           "value": entry, "bad": not entry["compression"] or not entry["cache_headers"],
                           "note": "compression may be at the proxy; confirm before rating"})
    return out


# ---------- scorecard ----------
def scorecard(checks, ts, ng, pk):
    sc = {}
    def grade(cat, status, reason):
        sc[cat] = {"result": status, "reason": reason}
    strict = [c for c in checks if c["check"] == "tsconfig-strict"]
    if not strict:
        grade("strict_type_checking", "fail" if any(p["typescript"] for p in pk) else "unknown", "no tsconfig found")
    elif all(c["value"] for c in strict):
        st = [c for c in strict if c["detail"].get("strictTemplates") is False]
        grade("strict_type_checking", "partial" if st else "pass", "strictTemplates false" if st else "strict true in all tsconfigs")
    elif any(c["value"] for c in strict):
        grade("strict_type_checking", "partial", "strict differs between tsconfigs: " + ", ".join(f"{c['file']}={c['value']}" for c in strict))
    else:
        grade("strict_type_checking", "fail", "strict false/absent: " + ", ".join(c["file"] for c in strict))
    sm = [c for c in checks if c["check"] == "prod-sourcemap"]
    opt = [c for c in checks if c["check"] == "prod-optimization"]
    if any(c.get("bad") for c in sm) or any(c.get("bad") for c in opt):
        grade("production_build", "fail", "; ".join(f"{c['check']}={c['value']} in {c['file']}" for c in sm + opt if c.get("bad")))
    elif sm or opt:
        grade("production_build", "pass", "sourceMap off and optimization on in the inspected production config")
    else:
        grade("production_build", "unknown", "no production build config found")
    bud = [c for c in checks if c["check"] == "budgets"]
    st = [c for c in checks if c["check"] == "size-tool" and not c["bad"]]
    if any(not c["bad"] and c.get("error_threshold") for c in bud):
        grade("bundle_budgets", "pass", "budgets with error thresholds configured")
    elif any(not c["bad"] for c in bud) or st:
        grade("bundle_budgets", "partial", "budgets or size tool present but warning-only / not verified in CI")
    else:
        grade("bundle_budgets", "fail", "no budgets or size tool configured")
    lint = [c for c in checks if c["check"] == "lint"]
    if lint and not any(c["bad"] for c in lint):
        grade("lint_config", "pass", "eslint config, framework plugin and runnable lint script present")
    elif lint and any(c["detail"]["config"] for c in lint):
        grade("lint_config", "partial", "; ".join(f"{c['file']}: {c['detail']}" for c in lint))
    else:
        grade("lint_config", "fail", "no eslint config found")
    for cat in ("component_model", "control_flow_and_state", "change_detection", "legacy_modern_mixing"):
        grade(cat, "unknown", "decided by grep_scan.py hits + manual pass")
    grade("lazy_routes", "unknown", "decided by route_scan.py")
    return sc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    checks = []
    ts = check_tsconfigs(root, checks)
    ng = check_angular(root, checks)
    bl = check_bundlers(root, checks)
    pk = check_packages(root, checks)
    be = check_backend(root, checks)
    result = {"root": root, "tsconfigs": ts, "angular": ng, "bundlers": bl, "packages": pk,
              "backend_static_serving": be, "checks": checks, "scorecard": scorecard(checks, ts, ng, pk)}
    text = json.dumps(result, indent=2, default=str)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    print("Preliminary scorecard:")
    for cat, v in result["scorecard"].items():
        print(f"  {cat:28s} {v['result']:8s} {v['reason']}")
    bad = [c for c in checks if c.get("bad")]
    print(f"\n{len(bad)} config issue(s) flagged:")
    for c in bad:
        print(f"  - {c['check']}: {c['file']}:{c.get('line')} value={c.get('value')!s:.60}")
    if a.out:
        print(f"\nwritten: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
