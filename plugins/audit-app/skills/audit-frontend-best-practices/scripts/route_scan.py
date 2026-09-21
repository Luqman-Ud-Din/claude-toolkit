#!/usr/bin/env python3
"""Route scanner for audit-frontend-best-practices: lists every route and
whether it is lazy-loaded, per framework.

Usage:
    python route_scan.py <repo_root> [--out routes.json] [--framework angular|react|vue|auto]

Detection rules (candidates; confirm the eager ones by opening the file):
  Angular : route objects in *.routes.ts / *-routing.module.ts / files with `Routes = [`.
            lazy  = loadChildren / loadComponent
            eager = component: SomeComponent
  React   : <Route path=".." element={<X/>}> or object routes {path, element|Component}.
            lazy  = X declared via lazy(() => import()) / React.lazy in the same file,
                    or `lazy:` loader in object routes
            eager = X imported statically
            Next.js app/ and pages/ file routes are reported as lazy by convention.
  Vue     : route records {path, component}.
            lazy  = component: () => import(...) or defineAsyncComponent
            eager = component: Identifier
            Nuxt pages/ file routes are reported as lazy by convention.
Redirects (redirectTo / <Navigate>), wildcards and pure container routes are listed with
kind=redirect|container and excluded from the eager/lazy totals.
Read-only.
"""
import argparse
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


def read(path):
    return repo_walk.read_text(path)


def walk(root, exts):
    # Shared skip list and size cap from audit-code-scan.
    return repo_walk.iter_files(root, exts=set(exts), names=frozenset())


def rel(root, p):
    return repo_walk.rel(root, p)


def objects(text):
    """Yield (start, end, body) for every balanced {...} in text (skips strings/comments roughly)."""
    stack = []
    i, n = 0, len(text)
    in_str = None
    while i < n:
        ch = text[i]
        if in_str:
            if ch == "\\":
                i += 2; continue
            if ch == in_str:
                in_str = None
        elif ch in "'\"`":
            in_str = ch
        elif text.startswith("//", i):
            j = text.find("\n", i); i = n if j < 0 else j; continue
        elif text.startswith("/*", i):
            j = text.find("*/", i); i = n if j < 0 else j + 2; continue
        elif ch == "{":
            stack.append(i)
        elif ch == "}" and stack:
            s = stack.pop()
            yield s, i + 1, text[s + 1:i]
        i += 1


def top_level(body):
    """Return body with nested {...} and [...] blanked out so regexes see depth-0 keys only."""
    out, depth = [], 0
    for ch in body:
        if ch in "{[":
            depth += 1; out.append(" ")
        elif ch in "}]":
            depth -= 1; out.append(" ")
        else:
            out.append(ch if depth == 0 else " ")
    return "".join(out)


PATH_RE = re.compile(r"(?:^|[\s,{])path\s*:\s*(['\"`])([^'\"`]*)\1")


def scan_angular(root, files):
    routes = []
    for f in files:
        text = read(f)
        if not re.search(r"\bRoutes\b|RouterModule\.for(Root|Child)|provideRouter\(", text) and not re.search(r"\.routes\.ts$|routing\.module\.ts$", f):
            continue
        for s, e, body in objects(text):
            tl = top_level(body)
            m = PATH_RE.search(tl)
            if not m:
                continue
            line = text[:s].count("\n") + 1
            path = m.group(2)
            if re.search(r"\bredirectTo\s*:", tl):
                kind, lazy, target = "redirect", None, re.search(r"redirectTo\s*:\s*['\"]([^'\"]*)", tl).group(1)
            elif re.search(r"\bloadChildren\s*:|\bloadComponent\s*:", tl):
                kind, lazy = "route", True
                tm = re.search(r"import\(\s*['\"]([^'\"]+)['\"]", body)
                target = tm.group(1) if tm else "(loader)"
                if re.search(r"loadChildren\s*:\s*['\"]", tl):
                    kind = "route-legacy-string-loader"
            elif re.search(r"\bcomponent\s*:\s*([A-Za-z_$][\w$]*)", tl):
                kind, lazy = "route", False
                target = re.search(r"\bcomponent\s*:\s*([A-Za-z_$][\w$]*)", tl).group(1)
            elif re.search(r"\bchildren\s*:", tl):
                kind, lazy, target = "container", None, "(children)"
            else:
                continue
            if path == "**":
                kind = "wildcard"
            routes.append({"framework": "angular", "file": rel(root, f), "line": line, "path": path,
                           "kind": kind, "lazy": lazy, "target": target})
    return routes


def scan_react(root, files):
    routes = []
    for f in files:
        text = read(f)
        if "<Route" not in text and "createBrowserRouter" not in text and "createRoutesFromElements" not in text and not re.search(r"\bpath\s*:\s*['\"]", text):
            continue
        lazy_names = set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:React\.)?lazy\(", text))
        # JSX <Route ... path=".." element={<X .../>} />
        for m in re.finditer(r"<Route\b([^>]*)/?>", text):
            attrs = m.group(1)
            pm = re.search(r"\bpath=(?:\"([^\"]*)\"|'([^']*)'|\{['\"`]([^'\"`]*)['\"`]\})", attrs)
            if not pm:
                if re.search(r"\bindex\b", attrs):
                    path = "(index)"
                else:
                    continue
            else:
                path = next(g for g in pm.groups() if g is not None)
            line = text[:m.start()].count("\n") + 1
            em = re.search(r"\b(?:element|Component)=\{\s*<?\s*([A-Za-z_$][\w$.]*)", attrs)
            if em is None:
                kind, lazy, target = "container", None, "(children)"
            else:
                target = em.group(1)
                if target == "Navigate":
                    kind, lazy = "redirect", None
                else:
                    kind, lazy = "route", target in lazy_names
            if path == "*":
                kind = "wildcard"
            routes.append({"framework": "react", "file": rel(root, f), "line": line, "path": path,
                           "kind": kind, "lazy": lazy, "target": target})
        # object routes: { path: '/x', element: <X/> | Component: X | lazy: () => import() }
        if "createBrowserRouter" in text or "createHashRouter" in text or "useRoutes" in text or "RouteObject" in text:
            for s, e, body in objects(text):
                tl = top_level(body)
                pm = PATH_RE.search(tl)
                if not pm:
                    continue
                path = pm.group(2)
                line = text[:s].count("\n") + 1
                if re.search(r"\blazy\s*:", tl):
                    kind, lazy, target = "route", True, "(lazy loader)"
                elif re.search(r"\b(?:element|Component)\s*:\s*<?\s*([A-Za-z_$][\w$.]*)", tl):
                    target = re.search(r"\b(?:element|Component)\s*:\s*<?\s*([A-Za-z_$][\w$.]*)", tl).group(1)
                    if target == "Navigate":
                        kind, lazy = "redirect", None
                    else:
                        kind, lazy = "route", target in lazy_names
                elif re.search(r"\bchildren\s*:", tl):
                    kind, lazy, target = "container", None, "(children)"
                else:
                    continue
                if path == "*":
                    kind = "wildcard"
                routes.append({"framework": "react", "file": rel(root, f), "line": line, "path": path,
                               "kind": kind, "lazy": lazy, "target": target})
    # Next.js file routes
    for base in ("app", "src/app", "pages", "src/pages"):
        d = os.path.join(root, base)
        if os.path.isdir(d):
            for p in walk(d, (".tsx", ".jsx", ".js", ".ts")):
                name = os.path.basename(p)
                if base.endswith("app") and name.startswith("page.") or base.endswith("pages") and not name.startswith("_") and "api" not in rel(d, p).split("/"):
                    routes.append({"framework": "react", "file": rel(root, p), "line": 1,
                                   "path": "/" + os.path.dirname(rel(d, p)) if base.endswith("app") else "/" + os.path.splitext(rel(d, p))[0],
                                   "kind": "file-route", "lazy": True, "target": "(Next.js file route, code-split by framework)"})
    return routes


def scan_vue(root, files):
    routes = []
    for f in files:
        text = read(f)
        if not re.search(r"createRouter\(|new VueRouter\(|RouteRecordRaw|\broutes\s*[:=]\s*\[", text):
            continue
        for s, e, body in objects(text):
            tl = top_level(body)
            pm = PATH_RE.search(tl)
            if not pm:
                continue
            path = pm.group(2)
            line = text[:s].count("\n") + 1
            if re.search(r"\bredirect\s*:", tl):
                kind, lazy, target = "redirect", None, "(redirect)"
            elif re.search(r"\bcomponents?\s*:\s*(\(\s*\)\s*=>|defineAsyncComponent\()", tl) or re.search(r"\bcomponents?\s*:\s*\(\s*\)\s*=>\s*import\(", body):
                kind, lazy = "route", True
                tm = re.search(r"import\(\s*['\"]([^'\"]+)['\"]", body)
                target = tm.group(1) if tm else "(loader)"
            elif re.search(r"\bcomponent\s*:\s*([A-Za-z_$][\w$]*)", tl):
                kind, lazy = "route", False
                target = re.search(r"\bcomponent\s*:\s*([A-Za-z_$][\w$]*)", tl).group(1)
            elif re.search(r"\bchildren\s*:", tl):
                kind, lazy, target = "container", None, "(children)"
            else:
                continue
            if path.startswith("/:pathMatch") or path == "*":
                kind = "wildcard"
            routes.append({"framework": "vue", "file": rel(root, f), "line": line, "path": path,
                           "kind": kind, "lazy": lazy, "target": target})
    for base in ("pages", "src/pages"):
        d = os.path.join(root, base)
        if os.path.isdir(d) and os.path.exists(os.path.join(root, "nuxt.config.ts")) or os.path.isdir(d) and os.path.exists(os.path.join(root, "nuxt.config.js")):
            for p in walk(d, (".vue",)):
                routes.append({"framework": "vue", "file": rel(root, p), "line": 1, "path": "/" + os.path.splitext(rel(d, p))[0],
                               "kind": "file-route", "lazy": True, "target": "(Nuxt file route, code-split by framework)"})
    return routes


def detect(root):
    fws = set()
    for pkg_path in repo_walk.iter_files(root, exts=frozenset(), names={"package.json"}, max_depth=3):
        if os.path.basename(pkg_path) != "package.json":
            continue
        try:
            pkg = json.loads(read(pkg_path))
        except json.JSONDecodeError:
            continue
        deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
        if "@angular/core" in deps: fws.add("angular")
        if "react" in deps or "next" in deps: fws.add("react")
        if "vue" in deps or "nuxt" in deps: fws.add("vue")
    return fws


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--out", default=None)
    ap.add_argument("--framework", default="auto", choices=["auto", "angular", "react", "vue"])
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    fws = detect(root) if a.framework == "auto" else {a.framework}
    ts_files = list(walk(root, (".ts", ".tsx", ".js", ".jsx", ".mjs")))
    routes = []
    if "angular" in fws: routes += scan_angular(root, [f for f in ts_files if f.endswith(".ts") and not f.endswith(".spec.ts")])
    if "react" in fws: routes += scan_react(root, [f for f in ts_files if not re.search(r"\.(spec|test)\.", f)])
    if "vue" in fws: routes += scan_vue(root, [f for f in ts_files if f.endswith((".ts", ".js"))])
    real = [r for r in routes if r["kind"] in ("route", "route-legacy-string-loader", "file-route")]
    eager = [r for r in real if r["lazy"] is False]
    summary = {"frameworks": sorted(fws), "total_routes": len(real), "lazy": len(real) - len(eager),
               "eager": len(eager), "eager_ratio": round(len(eager) / len(real), 2) if real else None,
               "legacy_string_loaders": sum(1 for r in routes if r["kind"] == "route-legacy-string-loader")}
    result = {"root": root, "summary": summary, "routes": routes}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    print(json.dumps(summary, indent=2))
    for r in routes:
        flag = "EAGER " if r["lazy"] is False else "lazy  " if r["lazy"] else r["kind"][:6].ljust(6)
        print(f"  {flag} {r['file']}:{r['line']}  path={r['path']!r}  -> {r['target']}")
    if a.out:
        print(f"written: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
