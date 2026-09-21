#!/usr/bin/env python3
"""Parse dependency-injection registrations per stack, cross-reference constructor
parameters, and flag captive dependencies.

Usage:
    python di_lifetimes.py <repo_root> --stack dotnet|java-spring|node-express|python-django
           [--out di.json] [--md di.md]

Per stack:
  dotnet        services.AddSingleton/AddScoped/AddTransient<I, Impl>() / <Impl>() / (typeof)
                AddDbContext<T> (Scoped), AddHostedService<T> (Singleton), AddHttpClient<T>
                (Transient typed client), AddMemoryCache/AddHttpContextAccessor (Singleton).
                Constructor parameters of each registered implementation are resolved
                through the registration map; a consumer whose lifetime is longer than a
                dependency's is flagged CAPTIVE-SCOPED / CAPTIVE-TRANSIENT.
  java-spring   @Component/@Service/@Repository/@Controller/@RestController/@Configuration
                (Singleton unless @Scope/@RequestScope/@SessionScope), @Bean methods (with
                optional @Scope). Constructor and @Autowired field types resolved by simple
                class name; singleton -> request/session/prototype without proxyMode or
                ObjectProvider/Provider is flagged CAPTIVE-<SCOPE>.
  node-express  NestJS @Injectable({ scope: Scope.REQUEST|TRANSIENT }) (default Singleton),
                @Inject(REQUEST). A singleton injecting a REQUEST/TRANSIENT provider is
                flagged SCOPE-BUBBLING (Nest silently re-scopes the consumer). Also lists
                inversify/awilix/tsyringe lifetime calls when present.
  python-django N/A - prints why (no container; module scope = process lifetime) and lists
                the shapes that play the same role: module globals assigned inside functions,
                app.state assignments, lru_cache'd dependency providers, FastAPI Depends.

Output rows: {service, implementation, lifetime, dependencies: [{name, type, lifetime}],
              mismatch: "-" | "CAPTIVE-SCOPED" | "CAPTIVE-TRANSIENT" | "SCOPE-BUBBLING" | "UNRESOLVED",
              file, line}
Every row is a candidate for the reviewer to confirm. Read-only. Python 3 stdlib only.
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
RANK = {"Singleton": 3, "Scoped": 2, "Transient": 1}
KNOWN_SINGLETONS_DOTNET = {"ILogger", "ILoggerFactory", "IConfiguration", "IOptions", "IOptionsMonitor", "IOptionsSnapshot",
                           "IHttpClientFactory", "IMemoryCache", "IDistributedCache", "IHttpContextAccessor", "IServiceScopeFactory",
                           "IServiceProvider", "IHostApplicationLifetime", "IWebHostEnvironment", "IHostEnvironment", "IMapper",
                           "TimeProvider", "IBackgroundJobClient", "IRecurringJobManager", "HybridCache", "DbContextOptions",
                           "IServiceScope", "ILoggerProvider", "IHostedService", "IDataProtectionProvider", "IAuthorizationService"}
KNOWN_SINGLETONS_DOTNET_SCOPED = {"IOptionsSnapshot"}


def iter_files(root, exts):
    # Shared skip list and size cap from audit-code-scan.
    for full in repo_walk.iter_files(root, exts=set(exts), names=frozenset()):
        yield full, repo_walk.rel(root, full)


def read(path):
    return repo_walk.read_text(path)


def strip_generics(t):
    t = t.strip()
    return re.sub(r"<.*>$", "", t).split(".")[-1]


# ---------------------------------------------------------------- dotnet
def dotnet(root):
    regs = {}   # service name -> {impl, lifetime, file, line}
    ctors = {}  # class name -> [(param_type, param_name)], file, line
    reg_re = re.compile(r"\.Add(?P<life>Singleton|Scoped|Transient|DbContext|DbContextPool|HostedService|HttpClient|MemoryCache|HttpContextAccessor)\s*(<(?P<gen>[^>()]*(<[^>]*>)?[^>()]*)>)?\s*\((?P<args>[^;)]*)\)?")
    for path, rel in iter_files(root, (".cs",)):
        text = read(path)
        for i, line in enumerate(text.splitlines(), 1):
            for m in reg_re.finditer(line):
                life = m.group("life")
                gen = m.group("gen") or ""
                args = m.group("args") or ""
                parts = [strip_generics(p) for p in re.split(r",(?![^<]*>)", gen)] if gen else []
                if life in ("DbContext", "DbContextPool"):
                    lifetime, svc, impl = "Scoped", parts[0] if parts else "?", parts[0] if parts else "?"
                elif life == "HostedService":
                    lifetime, svc, impl = "Singleton", parts[0] if parts else "?", parts[0] if parts else "?"
                elif life == "HttpClient":
                    lifetime = "Transient"
                    svc = parts[0] if parts else "?"
                    impl = parts[1] if len(parts) > 1 else svc
                elif life in ("MemoryCache", "HttpContextAccessor"):
                    lifetime, svc, impl = "Singleton", "I" + life, "I" + life
                else:
                    lifetime = life
                    if parts:
                        svc = parts[0]
                        impl = parts[1] if len(parts) > 1 else parts[0]
                    else:
                        tm = re.findall(r"typeof\s*\(\s*([\w.<>]+)\s*\)", args)
                        svc = strip_generics(tm[0]) if tm else "?"
                        impl = strip_generics(tm[1]) if len(tm) > 1 else svc
                    if "=>" in args and impl == svc:
                        impl = svc + " (factory)"
                regs[svc] = {"impl": impl, "lifetime": lifetime, "file": rel, "line": i}
                if impl != svc and not impl.endswith("(factory)"):
                    regs.setdefault(impl, {"impl": impl, "lifetime": lifetime, "file": rel, "line": i})
        # constructors (also primary constructors)
        for cm in re.finditer(r"(?:class|record)\s+(?P<cls>\w+)(?:<[^>]*>)?\s*(?:\((?P<pc>[^)]*)\))?", text):
            cls = cm.group("cls")
            params = cm.group("pc")
            if params is None:
                ctor = re.search(r"(?:public|internal|protected)\s+" + re.escape(cls) + r"\s*\((?P<p>[^)]*)\)", text)
                params = ctor.group("p") if ctor else ""
            line_no = text[:cm.start()].count("\n") + 1
            plist = []
            for p in re.split(r",(?![^<]*>)", params or ""):
                p = p.strip()
                if not p:
                    continue
                p = re.sub(r"^\[[^\]]*\]\s*", "", p)
                bits = p.replace("=", " = ").split()
                if len(bits) >= 2:
                    plist.append((bits[0], bits[1]))
            if plist or cls in regs:
                ctors.setdefault(cls, {"params": plist, "file": rel, "line": line_no})

    def resolve(ptype):
        base = strip_generics(ptype)
        if base in regs:
            return regs[base]["lifetime"], "registered"
        if base in KNOWN_SINGLETONS_DOTNET_SCOPED:
            return "Scoped", "framework"
        if base == "HttpClient":
            return "Transient", "framework"   # typed client handed in by IHttpClientFactory
        if base in KNOWN_SINGLETONS_DOTNET or base.startswith("ILogger") or base.startswith("IOptions"):
            return "Singleton", "framework"
        if base.endswith("DbContext"):
            return "Scoped", "convention"
        return None, "unresolved"

    rows = []
    for svc, r in sorted(regs.items()):
        impl = r["impl"].replace(" (factory)", "")
        c = ctors.get(impl) or ctors.get(svc)
        deps, flags = [], []
        if c:
            for ptype, pname in c["params"]:
                life, how = resolve(ptype)
                deps.append({"name": pname, "type": ptype, "lifetime": life or "?", "source": how})
                if life == "Scoped" and RANK.get(r["lifetime"], 0) > RANK["Scoped"]:
                    flags.append("CAPTIVE-SCOPED")
                elif life == "Transient" and r["lifetime"] == "Singleton" and how != "framework":
                    flags.append("CAPTIVE-TRANSIENT")   # scoped-holding-transient is per request anyway; only singletons capture
                elif life is None and how == "unresolved" and not ptype.startswith(("string", "int", "bool", "IEnumerable<", "Func<")):
                    flags.append("UNRESOLVED")
        mismatch = "-"
        if "CAPTIVE-SCOPED" in flags:
            mismatch = "CAPTIVE-SCOPED"
        elif "CAPTIVE-TRANSIENT" in flags:
            mismatch = "CAPTIVE-TRANSIENT"
        elif "UNRESOLVED" in flags:
            mismatch = "UNRESOLVED"
        rows.append({"service": svc, "implementation": r["impl"], "lifetime": r["lifetime"], "dependencies": deps,
                     "mismatch": mismatch, "file": r["file"], "line": r["line"],
                     "ctor_file": c["file"] if c else None, "ctor_line": c["line"] if c else None})
    return rows, None


# ---------------------------------------------------------------- java-spring
def java_spring(root):
    comp_re = re.compile(r"@(Component|Service|Repository|Controller|RestController|Configuration)\b")
    scope_re = re.compile(r"@RequestScope|@SessionScope|@Scope\s*\(\s*(?:value\s*=\s*)?\"(\w+)\"(?P<rest>[^)]*)\)|@Scope\s*\(\s*(?:scopeName\s*=\s*)?\"(\w+)\"(?P<rest2>[^)]*)\)")
    beans = {}  # class name -> {lifetime, proxied, file, line}
    ctors = {}
    for path, rel in iter_files(root, (".java", ".kt")):
        text = read(path)
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if comp_re.search(line) or re.search(r"@Bean\b", line):
                window = "\n".join(lines[max(0, i - 4): i + 4])
                sm = scope_re.search(window)
                lifetime, proxied = "Singleton", False
                if sm:
                    if "@RequestScope" in window:
                        lifetime, proxied = "Request", True
                    elif "@SessionScope" in window:
                        lifetime, proxied = "Session", True
                    else:
                        lifetime = (sm.group(1) or sm.group(3) or "singleton").capitalize()
                        proxied = "proxyMode" in (sm.group("rest") or sm.group("rest2") or "")
                if "@Bean" in line:
                    nm = re.search(r"\b(\w+)\s*\(", "\n".join(lines[i: i + 3]))
                    decl = re.search(r"(?:public|protected|private)?\s*(?:static\s+)?([\w<>]+)\s+(\w+)\s*\(", "\n".join(lines[i: i + 3]))
                    name = strip_generics(decl.group(1)) if decl else (nm.group(1) if nm else "?")
                else:
                    cm = re.search(r"class\s+(\w+)", "\n".join(lines[i: i + 6]))
                    name = cm.group(1) if cm else "?"
                beans.setdefault(name, {"lifetime": lifetime, "proxied": proxied, "file": rel, "line": i + 1})
        for cm in re.finditer(r"class\s+(?P<cls>\w+)", text):
            cls = cm.group("cls")
            ctor = re.search(r"(?:public|protected)?\s+" + re.escape(cls) + r"\s*\((?P<p>[^)]*)\)", text)
            plist = []
            if ctor:
                for p in re.split(r",(?![^<]*>)", ctor.group("p")):
                    bits = re.sub(r"@\w+(\([^)]*\))?\s*", "", p.strip()).split()
                    if len(bits) >= 2:
                        plist.append((bits[-2], bits[-1]))
            for fm in re.finditer(r"@Autowired[^\n]*\n\s*(?:private|protected|public)?\s*(?:final\s+)?([\w<>]+)\s+(\w+)\s*;", text):
                plist.append((fm.group(1), fm.group(2)))
            if plist:
                ctors.setdefault(cls, {"params": plist, "file": rel, "line": text[:cm.start()].count("\n") + 1})
    rows = []
    for name, b in sorted(beans.items()):
        c = ctors.get(name)
        deps, flags = [], []
        if c:
            for ptype, pname in c["params"]:
                base = strip_generics(ptype)
                wrapped = ptype.startswith(("ObjectProvider", "Provider", "ObjectFactory", "Supplier", "Lazy"))
                inner = re.sub(r"^\w+<(.*)>$", r"\1", ptype) if wrapped else None
                target = beans.get(strip_generics(inner) if inner else base)
                life = target["lifetime"] if target else None
                deps.append({"name": pname, "type": ptype, "lifetime": life or "?", "source": "registered" if target else "unresolved"})
                if target and b["lifetime"] == "Singleton" and life not in ("Singleton", None) and not wrapped and not target["proxied"]:
                    flags.append("CAPTIVE-" + life.upper())
        rows.append({"service": name, "implementation": name, "lifetime": b["lifetime"] + (" (proxied)" if b["proxied"] else ""),
                     "dependencies": deps, "mismatch": flags[0] if flags else "-", "file": b["file"], "line": b["line"],
                     "ctor_file": c["file"] if c else None, "ctor_line": c["line"] if c else None})
    return rows, None


# ---------------------------------------------------------------- node (NestJS)
def node(root):
    provs = {}
    ctors = {}
    other = []
    for path, rel in iter_files(root, (".ts", ".js")):
        text = read(path)
        for m in re.finditer(r"@Injectable\s*\((?P<opts>[^)]*)\)\s*(?:export\s+)?(?:abstract\s+)?class\s+(?P<cls>\w+)", text, re.S):
            opts = m.group("opts") or ""
            sm = re.search(r"Scope\.(REQUEST|TRANSIENT|DEFAULT)", opts)
            life = {"REQUEST": "Request", "TRANSIENT": "Transient", "DEFAULT": "Singleton"}.get(sm.group(1), "Singleton") if sm else "Singleton"
            provs[m.group("cls")] = {"lifetime": life, "file": rel, "line": text[:m.start()].count("\n") + 1}
            body_start = m.end()
            ctor = re.search(r"constructor\s*\((?P<p>[^)]*)\)", text[body_start:], re.S)
            plist = []
            if ctor:
                for p in re.split(r",(?![^<(]*[>)])", ctor.group("p")):
                    p = p.strip()
                    if not p:
                        continue
                    inj = re.search(r"@Inject\s*\(\s*(\w+)\s*\)", p)
                    tm = re.search(r"(\w+)\s*:\s*([\w<>\[\]| ]+)", p)
                    if tm:
                        plist.append((("REQUEST" if inj and inj.group(1) == "REQUEST" else strip_generics(tm.group(2))), tm.group(1)))
            ctors[m.group("cls")] = {"params": plist, "file": rel, "line": text[:body_start].count("\n") + 1}
        for m in re.finditer(r"(inRequestScope|inSingletonScope|inTransientScope|\.scoped\(\)|\.singleton\(\)|\.transient\(\)|Lifecycle\.\w+)", text):
            other.append({"file": rel, "line": text[:m.start()].count("\n") + 1, "call": m.group(1)})
    rows = []
    for name, p in sorted(provs.items()):
        c = ctors.get(name)
        deps, flags = [], []
        if c:
            for ptype, pname in c["params"]:
                if ptype == "REQUEST":
                    life = "Request"
                else:
                    t = provs.get(ptype)
                    life = t["lifetime"] if t else None
                deps.append({"name": pname, "type": ptype, "lifetime": life or "?", "source": "registered" if life else "unresolved"})
                if p["lifetime"] == "Singleton" and life in ("Request", "Transient"):
                    flags.append("SCOPE-BUBBLING")
        rows.append({"service": name, "implementation": name, "lifetime": p["lifetime"], "dependencies": deps,
                     "mismatch": flags[0] if flags else "-", "file": p["file"], "line": p["line"],
                     "ctor_file": c["file"] if c else None, "ctor_line": c["line"] if c else None})
    note = None
    if not provs:
        note = ("No NestJS providers found. Plain Express/Fastify has no container: module scope is the singleton and "
                "closures are the request scope. Review DI-MODULE-MUTABLE-STATE and HTTP-CLIENT-IN-FUNCTION grep hits instead.")
    if other:
        note = (note or "") + f" Found {len(other)} inversify/awilix/tsyringe lifetime calls (listed in JSON 'other'); cross-check consumers by hand."
    return rows, {"note": note, "other": other}


# ---------------------------------------------------------------- python
def python_django(root):
    shapes = []
    pats = {
        "module-global-written-in-function": re.compile(r"^\s{4,}global\s+(\w+)"),
        "app.state-assignment": re.compile(r"app\.state\.(\w+)\s*="),
        "lru_cache-dependency": re.compile(r"@(?:functools\.)?lru_cache"),
        "fastapi-Depends": re.compile(r"Depends\s*\(\s*(\w+)"),
        "class-attr-request-state": re.compile(r"^\s{4,}(?:cls|self\.__class__|[A-Z]\w+)\.(\w*(?:user|tenant|request|current)\w*)\s*="),
        "dependency_injector": re.compile(r"providers\.(Singleton|Factory|Resource|Configuration)\s*\("),
    }
    for path, rel in iter_files(root, (".py",)):
        for i, line in enumerate(read(path).splitlines(), 1):
            for kind, rx in pats.items():
                m = rx.search(line)
                if m:
                    shapes.append({"kind": kind, "file": rel, "line": i, "snippet": line.strip()[:160]})
    note = ("N/A: Django/Flask have no DI container, so there are no registered lifetimes to mismatch. "
            "What plays the same role: module-level objects live for the worker process (singleton), request objects "
            "and FastAPI Depends live per request (scoped), and thread/context locals persist across pooled threads unless "
            "reset. The captive-dependency bug here is per-request data written to module globals, class attributes, "
            "app.state, or an lru_cache'd provider. The rows below list those shapes for manual review.")
    rows = [{"service": s["kind"], "implementation": s["snippet"], "lifetime": "process" if s["kind"] != "fastapi-Depends" else "request",
             "dependencies": [], "mismatch": "REVIEW" if s["kind"] in ("module-global-written-in-function", "app.state-assignment", "class-attr-request-state", "lru_cache-dependency") else "-",
             "file": s["file"], "line": s["line"], "ctor_file": None, "ctor_line": None} for s in shapes]
    return rows, {"note": note}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--stack", required=True, choices=["dotnet", "java-spring", "node-express", "python-django"])
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args()
    fn = {"dotnet": dotnet, "java-spring": java_spring, "node-express": node, "python-django": python_django}[a.stack]
    rows, extra = fn(a.root)
    result = {"root": os.path.abspath(a.root), "stack": a.stack, "count": len(rows),
              "mismatches": sum(1 for r in rows if r["mismatch"] not in ("-", "UNRESOLVED")), "rows": rows}
    if extra:
        result.update({k: v for k, v in extra.items() if v})
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    md = ["| Service (registered as) | Implementation | Lifetime | Dependencies (lifetime) | Mismatch | Location |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        deps = ", ".join(f"{d['type']} ({d['lifetime']})" for d in r["dependencies"]) or "-"
        loc = f"`{r['file']}:{r['line']}`" + (f" ctor `{r['ctor_file']}:{r['ctor_line']}`" if r.get("ctor_file") else "")
        md.append(f"| {r['service']} | {r['implementation']} | {r['lifetime']} | {deps} | {r['mismatch']} | {loc} |")
    if extra and extra.get("note"):
        md.insert(0, extra["note"] + "\n")
    text = "\n".join(md) + "\n"
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(json.dumps({"count": result["count"], "mismatches": result["mismatches"],
                      "flagged": [f"{r['service']} ({r['lifetime']}) -> {r['mismatch']}" for r in rows if r["mismatch"] not in ("-",)]}, indent=2))
    if extra and extra.get("note"):
        print(extra["note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
