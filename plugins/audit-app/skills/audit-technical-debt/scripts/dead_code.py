#!/usr/bin/env python3
"""Heuristic dead-code finder: unreferenced files/modules, unreferenced exported
or public symbols, obviously unreachable statements, and projects missing from
the solution.

Usage:
    python dead_code.py <repo_root> [--exclude GLOB ...] [--out dead_code.json] [--md dead_code.md]

FALSE-POSITIVE CAVEAT (printed into the output as "caveat"): this is a name-based
search, not a compiler. It cannot see reflection, DI assembly scanning, string-based
routing, template or XAML bindings, serializer-only types, public APIs consumed by
other repositories, dynamic imports built from variables, or code reached only from
tests. Treat every row as a candidate; confirm with the stack's tool (Roslyn IDE0051/
IDE0052 + "Find all references", knip/ts-prune, vulture, PMD UnusedPrivateMethod) and a
search across sibling repositories before calling it dead.

Rules:
  C#/Java   a type (class/record/interface/enum/struct) is unreferenced when its name
            appears in no other file and not again in its own file. Types discovered by
            the framework are skipped: names ending Controller, Hub, Middleware, Filter,
            Attribute, Profile, Validator, Handler, Consumer, Job, Worker, Tests, Migration,
            ModelSnapshot; types deriving from ControllerBase, BackgroundService,
            IHostedService, Profile, AbstractValidator, DbContext, IRequestHandler,
            IEntityTypeConfiguration, JsonConverter, ComponentBase, PageModel; Java types
            annotated @RestController/@Controller/@Service/@Component/@Repository/
            @Configuration/@SpringBootApplication/@Entity/@ControllerAdvice/@Aspect;
            Program/Startup. A file whose declared types are all unreferenced is
            reported once as an unreferenced module.
  TS/JS/Vue a module no import/require/import()/loadChildren/loadComponent resolves to
            (relative specifiers resolved with .ts/.tsx/.js/.jsx/.vue/index.*; alias
            specifiers matched by trailing path) and that is not an entry point (main.*,
            index.*, server.*, app.*, *.config.*, environment*, polyfills, *.spec/test/
            stories, files named in package.json main/bin or angular.json). Vue
            components also count as used when their tag (<order-list> / <OrderList>)
            appears. Exported names used by no other file are "unused exports".
  Python    a module never imported (import x / from x import) and not a framework file
            (manage.py, settings, urls, wsgi, asgi, apps, admin, models, views, tasks,
            signals, conftest, __init__, migrations, tests).
  Unreachable  a statement after return/throw/raise/break/continue at the same
            indentation inside the same block; if (false) / #if false / if False:.
Read-only against the audited repo.
"""
import argparse
import fnmatch
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import complexity  # noqa: E402

CAVEAT = ("Heuristic, name-based: reflection, DI scanning, string routing, templates, serializers, other "
          "repositories and dynamic imports are invisible to it. Every row is a candidate to confirm, not proof.")
repo_walk = complexity.repo_walk  # audit-code-scan's shared walker, imported by complexity.py
REF_EXT = {".cs", ".java", ".kt", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".py", ".html", ".cshtml",
           ".razor", ".xaml", ".json", ".xml", ".csproj", ".config", ".yml", ".yaml", ".gradle", ".properties", ".sln"}
IDENT = re.compile(r"[A-Za-z_]\w*")
CS_TYPE = re.compile(r"^\s*(?:\[[^\]]*\]\s*)*(?:(?:public|internal|private|protected|static|sealed|abstract|partial|"
                     r"readonly|file|unsafe)\s+)*(class|record|interface|enum|struct)\s+(\w+)(?:<[^>]*>)?([^{\n]*)")
JAVA_TYPE = re.compile(r"^\s*(?:(?:public|private|protected|static|final|abstract|sealed)\s+)*"
                       r"(class|interface|enum|record|@interface)\s+(\w+)([^{\n]*)")
TS_EXPORT = re.compile(r"^\s*export\s+(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?(?:async\s+)?"
                       r"(class|function\*?|const|let|var|interface|type|enum)\s+(\w+)")
PY_TOP = re.compile(r"^(class|def)\s+(\w+)")
FRAMEWORK_SUFFIX = re.compile(r"(Controller|Hub|Middleware|Filter|Attribute|Profile|Validator|Handler|Consumer|Job|"
                              r"Worker|Tests?|Fixture|Migration|ModelSnapshot|DbContextFactory|Application|Config|"
                              r"Configuration|Module|Startup|Program)$")
FRAMEWORK_BASE = re.compile(r"\b(ControllerBase|Controller|Hub|BackgroundService|IHostedService|Profile|AbstractValidator|"
                            r"DbContext|IRequestHandler|INotificationHandler|IConsumer|Migration|ComponentBase|PageModel|"
                            r"IEntityTypeConfiguration|JsonConverter|ActionFilterAttribute|IMiddleware|IStartupFilter|"
                            r"TestCase|AppConfig|APIView|ViewSet|ModelViewSet|BaseCommand|ModelAdmin|Model)\b")
JAVA_ANN = re.compile(r"@(RestController|Controller|Service|Component|Repository|Configuration|SpringBootApplication|"
                      r"Entity|ControllerAdvice|RestControllerAdvice|Aspect|WebFilter|Mapper|Embeddable|"
                      r"MappedSuperclass|SpringBootTest|WebMvcTest|DataJpaTest)\b")
TS_ENTRY = re.compile(r"(^|/)(main|index|server|app|polyfills|test-setup|setup-jest|environment[\w.-]*|"
                      r"[\w.-]+\.(config|spec|test|stories|e2e|d))\.(ts|tsx|js|jsx|mjs|cjs|vue)$"
                      r"|(^|/)(page|layout|route|loading|error|not-found|template|default|middleware)\.(tsx|ts|jsx|js)$"
                      r"|(^|/)(pages|layouts|plugins|middleware|server/api|components|composables)/.*\.(vue|ts|tsx|js|jsx)$")
PY_ENTRY = re.compile(r"(^|/)(manage|settings|urls|wsgi|asgi|apps|admin|models|views|tasks|signals|conftest|"
                      r"__init__|__main__|setup|serializers|forms|celery|routers|schema|test_\w+|\w+_test|tests)\.py$"
                      r"|(^|/)(migrations|tests|management)/")
IMPORT_RE = re.compile(r"""(?:from\s+|require\(\s*|import\(\s*|import\s+)['"]([^'"]+)['"]""")
PY_IMPORT = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import\s+([\w, ()*]+)|import\s+([\w., ]+))", re.M)
UNREACH_C = re.compile(r"^(\s*)(?:return\b[^;{]*;|throw\b[^;{]*;|break;|continue;)\s*$")
UNREACH_PY = re.compile(r"^(\s*)(?:return\b.*|raise\b.*|break|continue)\s*$")
FALSE_BRANCH = re.compile(r"\bif\s*\(\s*false\s*\)|^\s*#if\s+false\b|^\s*if\s+False\s*:|\bwhile\s*\(\s*false\s*\)")


def walk(root, excludes):
    for full in repo_walk.iter_files(root, exts=REF_EXT, names={"dockerfile"}, extra_skip=complexity.EXTRA_SKIP):
        rel = repo_walk.rel(root, full)
        if complexity.in_hidden_dir(rel) or any(fnmatch.fnmatch(rel, g) for g in excludes):
            continue
        yield full, rel


def read(p):
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    texts, tokens = {}, {}
    for full, rel in walk(root, a.exclude):
        t = read(full)
        texts[rel] = t
        counts = {}
        for m in IDENT.finditer(t):
            counts[m.group(0)] = counts.get(m.group(0), 0) + 1
        tokens[rel] = counts

    def used_elsewhere(name, own):
        return any(name in toks for rel, toks in tokens.items() if rel != own)

    entry_files = set()
    pj = texts.get("package.json", "")
    for m in re.finditer(r'"(?:main|module|bin)"\s*:\s*"([^"]+)"', pj):
        entry_files.add(os.path.normpath(m.group(1)).replace(os.sep, "/"))
    for rel, t in texts.items():
        if rel.endswith("angular.json"):
            for m in re.finditer(r'"(?:main|browser|server|polyfills)"\s*:\s*"([^"]+)"', t):
                entry_files.add(m.group(1).lstrip("./"))

    unref_files, unref_symbols, unreachable = [], [], []
    code_files = [r for r in texts if os.path.splitext(r)[1].lower() in (".cs", ".java", ".kt", ".ts", ".tsx", ".js",
                                                                         ".jsx", ".mjs", ".cjs", ".vue", ".py")]
    # ---- import resolution for TS/JS/Vue and Python
    imported = set()
    py_imported = set()
    for rel in code_files:
        t = texts[rel]
        base = os.path.dirname(rel)
        for m in IMPORT_RE.finditer(t):
            spec = m.group(1)
            if spec.startswith("."):
                target = os.path.normpath(os.path.join(base, spec)).replace(os.sep, "/")
                imported.add(target)
            else:
                imported.add("*alias*/" + spec.lstrip("@~/"))
        if rel.endswith(".py"):
            for m in PY_IMPORT.finditer(t):
                if m.group(1):
                    py_imported.add(m.group(1))
                    for n in re.split(r"[,\s()]+", m.group(2)):
                        if n and n != "*":
                            py_imported.add(m.group(1) + "." + n)
                if m.group(3):
                    for n in m.group(3).split(","):
                        py_imported.add(n.strip().split(" as ")[0])

    def ts_module_used(rel):
        stem = re.sub(r"\.(ts|tsx|js|jsx|mjs|cjs|vue)$", "", rel)
        cands = {stem}
        if stem.endswith("/index"):
            cands.add(stem[:-6])
        for c in cands:
            if c in imported:
                return True
            for imp in imported:
                if imp.startswith("*alias*/"):
                    tail = imp[8:]
                    if c.endswith("/" + tail) or c == tail or (tail and c.endswith(tail)):
                        return True
        if rel.endswith(".vue"):
            name = os.path.basename(stem)
            kebab = re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()
            for other, t in texts.items():
                if other != rel and (("<" + name) in t or ("<" + kebab) in t):
                    return True
        return False

    for rel in code_files:
        t = texts[rel]
        ext = os.path.splitext(rel)[1].lower()
        lines = t.splitlines()
        if ext in (".cs", ".java", ".kt"):
            decls = []
            for n, line in enumerate(lines, 1):
                m = (CS_TYPE if ext == ".cs" else JAVA_TYPE).match(line)
                if not m:
                    continue
                name, rest = m.group(2), m.group(3) or ""
                window = "\n".join(lines[max(0, n - 6):n])
                framework = bool(FRAMEWORK_SUFFIX.search(name) or FRAMEWORK_BASE.search(rest)
                                 or (ext != ".cs" and JAVA_ANN.search(window))
                                 or re.search(r"static\s+(?:async\s+)?(?:void|int|Task)\s+Main\s*\(|public\s+static\s+void\s+main\s*\(", t))
                decl_count = len(re.findall(r"\b(?:class|record|interface|enum|struct)\s+" + re.escape(name) + r"\b", t))
                internal = tokens[rel].get(name, 0) > decl_count
                decls.append({"symbol": name, "kind": m.group(1), "line": n, "framework": framework,
                              "used": framework or internal or used_elsewhere(name, rel)})
            top = [d for d in decls if not d["framework"]]
            if top and all(not d["used"] for d in top) and len(top) == len(decls):
                unref_files.append({"file": rel, "symbols": [d["symbol"] for d in top], "line": top[0]["line"],
                                    "reason": "no declared type is referenced from any other file"})
            else:
                for d in top:
                    if not d["used"]:
                        unref_symbols.append({"file": rel, "line": d["line"], "symbol": d["symbol"], "kind": d["kind"]})
        elif ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue"):
            is_entry = bool(TS_ENTRY.search(rel)) or any(rel.endswith(e) for e in entry_files)
            exports = [(n, m.group(2), m.group(1)) for n, line in enumerate(lines, 1) for m in [TS_EXPORT.match(line)] if m]
            if not is_entry and not ts_module_used(rel) and (exports or ext == ".vue"):
                unref_files.append({"file": rel, "symbols": [e[1] for e in exports], "line": exports[0][0] if exports else 1,
                                    "reason": "no import, require, lazy route or component tag resolves to this module"})
                continue
            for n, name, kind in exports:
                if not used_elsewhere(name, rel):
                    unref_symbols.append({"file": rel, "line": n, "symbol": name, "kind": "export " + kind})
        elif ext == ".py":
            if PY_ENTRY.search(rel):
                continue
            mod = re.sub(r"\.py$", "", rel).replace("/", ".")
            stem = mod.split(".")[-1]
            used = any(i == mod or i.endswith("." + stem) or i == stem or i.startswith(mod + ".") or mod.endswith("." + i)
                       for i in py_imported)
            defs = [(n, m.group(2), m.group(1)) for n, line in enumerate(lines, 1) for m in [PY_TOP.match(line)] if m]
            if not used and defs:
                unref_files.append({"file": rel, "symbols": [d[1] for d in defs], "line": defs[0][0],
                                    "reason": "module is never imported"})

        # ---- unreachable statements
        stripped = complexity.strip_python(t) if ext == ".py" else complexity.strip_c_like(t)
        sl = stripped.split("\n")
        rx = UNREACH_PY if ext == ".py" else UNREACH_C
        for i, line in enumerate(sl):
            if FALSE_BRANCH.search(line):
                unreachable.append({"file": rel, "line": i + 1, "after": "constant false condition", "snippet": lines[i].strip()[:160]})
                continue
            m = rx.match(line)
            if not m:
                continue
            indent = len(m.group(1).expandtabs())
            for j in range(i + 1, min(i + 6, len(sl))):
                nxt = sl[j]
                if not nxt.strip():
                    continue
                ni = len(nxt) - len(nxt.lstrip())
                s = nxt.strip()
                if ni == indent and not re.match(r"^(\}|\)|case\b|default\b|else\b|elif\b|except\b|finally\b|#|\w+:\s*$|@|"
                                                 r"catch\b|\]|end\b)", s):
                    unreachable.append({"file": rel, "line": j + 1, "after": line.strip()[:60], "snippet": lines[j].strip()[:160]})
                break

    orphan_projects = []
    slns = [r for r in texts if r.endswith(".sln")]
    if slns:
        sln_text = "\n".join(texts[s] for s in slns).replace("\\", "/")
        for rel in texts:
            if rel.endswith(".csproj") and os.path.basename(rel) not in sln_text:
                orphan_projects.append({"file": rel, "reason": "project not listed in any .sln"})

    result = {"root": root, "caveat": CAVEAT,
              "summary": {"unreferenced_files": len(unref_files), "unreferenced_symbols": len(unref_symbols),
                          "unreachable": len(unreachable), "orphan_projects": len(orphan_projects)},
              "unreferenced_files": unref_files, "unreferenced_symbols": unref_symbols,
              "unreachable": unreachable, "orphan_projects": orphan_projects}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("> " + CAVEAT + "\n\n| Kind | Location | Symbols / snippet | Reason |\n|---|---|---|---|\n")
            for u in unref_files:
                fh.write("| unreferenced module | `%s:%d` | %s | %s |\n" % (u["file"], u["line"], ", ".join(u["symbols"]), u["reason"]))
            for u in unref_symbols:
                fh.write("| unreferenced symbol | `%s:%d` | %s | %s |\n" % (u["file"], u["line"], u["symbol"], u["kind"]))
            for u in unreachable:
                fh.write("| unreachable | `%s:%d` | `%s` | after %s |\n" % (u["file"], u["line"], u["snippet"].replace("|", "/"), u["after"]))
            for u in orphan_projects:
                fh.write("| orphan project | `%s` | | %s |\n" % (u["file"], u["reason"]))
    print(json.dumps(dict(result["summary"], modules=[u["file"] for u in unref_files[:10]]), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
