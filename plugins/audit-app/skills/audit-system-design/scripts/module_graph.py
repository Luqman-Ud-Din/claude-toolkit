#!/usr/bin/env python3
"""Build the module dependency graph of a repository, detect circular references,
and report fan-in / fan-out / instability and layer-direction violations.

Usage:
    python module_graph.py <repo_root> [--stack auto|dotnet|java-spring|node-express|python-django|angular|react|vue]
                           [--ts-root src] [--ts-depth 1] [--out modules.json] [--md modules.md] [--mermaid modules.mmd]

Sources per stack (all read-only, regex based):
  dotnet         *.csproj <ProjectReference Include="..."> (nodes = project names)
  java-spring    Maven <modules>/<module> + per-module <dependency> on sibling artifactIds;
                 Gradle settings.gradle include(':x') + project(':y') dependencies
  node-express / package.json workspaces (npm/yarn/pnpm-workspace.yaml) + dependencies between them,
  angular/react/vue   PLUS a TypeScript/JavaScript import graph between top-level folders under --ts-root
                 (auto-detected: src/app/features, src/features, src/modules, src) at --ts-depth
  python-django  INSTALLED_APPS from settings*.py + `from <app>` / `import <app>` between app packages

Layer inference (from module names): presentation/host (api, web, host, worker, jobs, controllers, ui, pages, views),
application (application, managers, services, usecases, handlers), domain (domain, core, entity,
entities, model, models), infrastructure (infrastructure, infra, data, persistence, repository,
repositories, jpa, adapters, integrations, external), contracts (dto, contracts, iservices,
interfaces, types), shared (shared, common, utils, lib, kernel). Allowed direction:
presentation -> application -> domain; infrastructure -> domain/application/contracts; anything -> contracts/shared.

Output JSON: nodes[{id, layer, fan_in, fan_out, instability, path}], edges[{from,to,evidence}],
cycles[[...]], layer_violations[{from,to,rule}], summary. Mermaid output colours cycle edges red.
"""
import argparse
import json
import os
import re
import sys

import importlib.util

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


def _load_atomic(skill, module, alias):
    """Load an atomic skill's script by path under a unique module name."""
    path = os.path.join(_SKILLS, skill, "scripts", module + ".py")
    if not os.path.exists(path):
        sys.exit(f"{skill} must be reachable from this skill (audit-core plugin or sibling layout; expected {path})")
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


repo_walk = _load_atomic("audit-code-scan", "repo_walk", "audit_code_scan_repo_walk")
LAYER_WORDS = [
    ("presentation", r"(microapi|webhost|\bapi\b|\bweb\b|\bhost\b|controllers?|\bui\b|pages|views|rest|frontend|gateway|worker|\bjobs?\b|consumer|\bcli\b)"),
    ("application", r"(application|managers?|services?|usecases?|use_cases|handlers|workflows?|\bapp\b)"),
    ("domain", r"(domain|\bcore\b|entit(y|ies)|models?|aggregates?)"),
    ("infrastructure", r"(infrastructure|infra|\bdata\b|persistence|repositor(y|ies)|jpa|adapters?|integrations?|external|clients?|storage|messaging)"),
    ("contracts", r"(\bdto\b|dtos|contracts?|iservices|interfaces|types|abstractions|proto)"),
    ("shared", r"(shared|common|utils?|\blib\b|kernel|helpers?|toolkit)"),
]
ALLOWED = {
    "presentation": {"application", "domain", "contracts", "shared", "infrastructure", "presentation"},
    "application": {"domain", "contracts", "shared", "application"},
    "domain": {"domain", "contracts", "shared"},
    "infrastructure": {"domain", "application", "contracts", "shared", "infrastructure"},
    "contracts": {"contracts", "shared"},
    "shared": {"shared", "contracts"},
    "unknown": {"presentation", "application", "domain", "infrastructure", "contracts", "shared", "unknown"},
}


def _read(p):
    return repo_walk.read_text(p)


def rel(root, p):
    return repo_walk.rel(root, p)


def walk(root, exts=None, names=None):
    return repo_walk.iter_files(root, exts=set(exts or ()), names=set(names or ()))


def layer_of(name):
    n = name.lower().replace("-", " ").replace("_", " ").replace(".", " ")
    n = re.sub(r"([a-z])([A-Z])", r"\1 \2", name).lower().replace("-", " ").replace("_", " ").replace(".", " ")
    for layer, rx in LAYER_WORDS:
        if re.search(rx, n):
            return layer
    return "unknown"


class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}

    def node(self, nid, path=""):
        self.nodes.setdefault(nid, {"id": nid, "path": path, "layer": layer_of(nid)})
        if path and not self.nodes[nid]["path"]:
            self.nodes[nid]["path"] = path

    def edge(self, a, b, evidence):
        if a == b:
            return
        self.node(a); self.node(b)
        self.edges.setdefault((a, b), evidence)


# ----------------------------------------------------------------------------- dotnet
def dotnet(root, g):
    projects = {}
    for p in walk(root, exts={".csproj", ".fsproj", ".vbproj"}):
        projects[os.path.splitext(os.path.basename(p))[0]] = p
    for name, p in projects.items():
        g.node(name, rel(root, p))
        text = _read(p)
        for i, line in enumerate(text.splitlines(), 1):
            m = re.search(r'<ProjectReference\s+Include="([^"]+)"', line)
            if m:
                target = os.path.splitext(os.path.basename(m.group(1).replace("\\", "/")))[0]
                g.edge(name, target, f"{rel(root, p)}:{i}")


# ----------------------------------------------------------------------------- java
def java(root, g):
    for pom in walk(root, names={"pom.xml"}):
        text = _read(pom)
        art = re.search(r"<artifactId>([^<]+)</artifactId>", re.sub(r"<parent>.*?</parent>", "", text, flags=re.S))
        if not art:
            continue
        name = art.group(1).strip()
        mods = re.findall(r"<module>([^<]+)</module>", text)
        if mods:
            for mname in mods:
                g.node(os.path.basename(mname.strip()), rel(root, os.path.join(os.path.dirname(pom), mname)))
            continue
        g.node(name, rel(root, pom))
        for i, line in enumerate(text.splitlines(), 1):
            m = re.search(r"<artifactId>([^<]+)</artifactId>", line)
            if m and m.group(1).strip() != name and m.group(1).strip() in g.nodes:
                g.edge(name, m.group(1).strip(), f"{rel(root, pom)}:{i}")
    for settings in walk(root, names={"settings.gradle", "settings.gradle.kts"}):
        text = _read(settings)
        for m in re.finditer(r"include\s*\(?\s*((?:['\"]:?[\w:-]+['\"]\s*,?\s*)+)\)?", text):
            for mod in re.findall(r"['\"]:?([\w:-]+)['\"]", m.group(1)):
                g.node(mod.split(":")[-1], rel(root, os.path.join(os.path.dirname(settings), mod.replace(":", "/"))))
        base = os.path.dirname(settings)
        for build in walk(base, names={"build.gradle", "build.gradle.kts"}):
            if os.path.dirname(build) == base:
                continue
            name = os.path.basename(os.path.dirname(build))
            if name not in g.nodes:
                continue
            for i, line in enumerate(_read(build).splitlines(), 1):
                for dep in re.findall(r"project\(\s*['\"]:?([\w:-]+)['\"]\s*\)", line):
                    g.edge(name, dep.split(":")[-1], f"{rel(root, build)}:{i}")


# ----------------------------------------------------------------------------- node workspaces + TS imports
def node_workspaces(root, g):
    pkgs = {}
    for pj in walk(root, names={"package.json"}):
        try:
            data = json.loads(_read(pj))
        except json.JSONDecodeError:
            continue
        name = data.get("name")
        if name:
            pkgs[name] = (pj, data)
    if len(pkgs) < 2:
        return
    ws_names = set(pkgs)
    for name, (pj, data) in pkgs.items():
        g.node(name, rel(root, pj))
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            for dep in (data.get(key) or {}):
                if dep in ws_names and dep != name:
                    g.edge(name, dep, f"{rel(root, pj)} ({key})")


def detect_ts_root(root):
    for cand in ("src/app/features", "src/features", "src/modules", "src/app", "src", "app", "lib"):
        p = os.path.join(root, cand)
        if os.path.isdir(p):
            subs = [d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d)) and d not in repo_walk.SKIP_DIRS]
            if len(subs) >= 2:
                return cand
    return None


def ts_imports(root, g, ts_root, depth):
    base = os.path.join(root, ts_root)
    if not os.path.isdir(base):
        return
    alias = {}
    for tsconfig in walk(root, names={"tsconfig.json", "tsconfig.base.json", "tsconfig.app.json"}):
        txt = re.sub(r"//[^\n]*|/\*.*?\*/", "", _read(tsconfig), flags=re.S)
        for m in re.finditer(r'"(@?[\w./-]+?)/?\*?"\s*:\s*\[\s*"([^"]+?)/?\*?"', txt):
            alias[m.group(1).rstrip("/")] = os.path.normpath(os.path.join(os.path.dirname(tsconfig), m.group(2)))

    def module_of(path):
        r = os.path.relpath(path, base).replace(os.sep, "/")
        if r.startswith(".."):
            return None
        parts = r.split("/")
        if len(parts) <= depth:
            return None
        return "/".join(parts[:depth])

    for p in walk(base, exts={".ts", ".tsx", ".js", ".jsx", ".vue", ".mjs"}):
        if p.endswith((".spec.ts", ".test.ts", ".d.ts", ".spec.tsx", ".test.tsx")):
            continue
        src_mod = module_of(p)
        if not src_mod:
            continue
        g.node(ts_root + "/" + src_mod, ts_root + "/" + src_mod)
        for i, line in enumerate(_read(p).splitlines(), 1):
            m = re.search(r"""(?:import|export)\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)|import\(\s*['"]([^'"]+)['"]\s*\)""", line)
            if not m:
                continue
            spec = m.group(1) or m.group(2) or m.group(3)
            target = None
            if spec.startswith("."):
                target = os.path.normpath(os.path.join(os.path.dirname(p), spec))
            else:
                for a, real in sorted(alias.items(), key=lambda kv: -len(kv[0])):
                    if spec == a or spec.startswith(a + "/"):
                        target = os.path.normpath(os.path.join(real, spec[len(a):].lstrip("/")))
                        break
                if target is None and spec.startswith(("src/", "app/")):
                    target = os.path.normpath(os.path.join(root, spec))
            if target is None:
                continue
            dst_mod = module_of(target)
            if dst_mod and dst_mod != src_mod:
                g.edge(ts_root + "/" + src_mod, ts_root + "/" + dst_mod, f"{rel(root, p)}:{i}")


# ----------------------------------------------------------------------------- django
def django(root, g):
    apps = {}
    for settings in walk(root, exts={".py"}):
        if "settings" not in os.path.basename(settings).lower() and "settings" not in settings.replace(os.sep, "/").split("/")[-2:-1]:
            continue
        text = _read(settings)
        m = re.search(r"INSTALLED_APPS\s*(?:\+?=|:)\s*\[(.*?)\]", text, re.S)
        if not m:
            continue
        for app in re.findall(r"['\"]([\w.]+)['\"]", m.group(1)):
            if app.startswith(("django.", "rest_framework", "corsheaders", "drf_", "debug_toolbar", "django_", "channels", "storages", "allauth", "crispy")):
                continue
            leaf = app.split(".")[-1].replace("Config", "")
            apps[leaf.lower()] = app
    if not apps:
        return
    app_dirs = {}
    for marker in walk(root, names={"apps.py", "models.py", "views.py"}):
        dirpath = os.path.dirname(marker)
        if os.path.basename(dirpath).lower() in apps:
            app_dirs[os.path.basename(dirpath).lower()] = dirpath
    for name, d in app_dirs.items():
        g.node(name, rel(root, d))
        for p in walk(d, exts={".py"}):
            if "migrations" in p.replace(os.sep, "/").split("/"):
                continue
            for i, line in enumerate(_read(p).splitlines(), 1):
                m = re.match(r"\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", line)
                if not m:
                    continue
                mod = (m.group(1) or m.group(2)).split(".")
                for seg in mod[:2]:
                    if seg.lower() in app_dirs and seg.lower() != name:
                        g.edge(name, seg.lower(), f"{rel(root, p)}:{i}")
                        break


# ----------------------------------------------------------------------------- analysis
def find_cycles(nodes, adj):
    """Tarjan SCC; returns SCCs with more than one node (or self loops)."""
    index, low, on, stack, out = {}, {}, set(), [], []
    counter = [0]

    def strong(v):
        index[v] = low[v] = counter[0]; counter[0] += 1
        stack.append(v); on.add(v)
        for w in adj.get(v, ()):
            if w not in index:
                strong(w); low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop(); on.discard(w); comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                out.append(sorted(comp))

    sys.setrecursionlimit(max(10000, len(nodes) * 4))
    for v in nodes:
        if v not in index:
            strong(v)
    return out


def analyse(g):
    adj = {}
    for (a, b) in g.edges:
        adj.setdefault(a, set()).add(b)
    fan_out = {n: len(adj.get(n, ())) for n in g.nodes}
    fan_in = {n: 0 for n in g.nodes}
    for (a, b) in g.edges:
        fan_in[b] = fan_in.get(b, 0) + 1
    for n, d in g.nodes.items():
        d["fan_in"] = fan_in.get(n, 0)
        d["fan_out"] = fan_out.get(n, 0)
        tot = d["fan_in"] + d["fan_out"]
        d["instability"] = round(d["fan_out"] / tot, 2) if tot else None
        d["depends_on"] = sorted(adj.get(n, ()))
    cycles = find_cycles(list(g.nodes), adj)
    cycle_edges = set()
    for comp in cycles:
        s = set(comp)
        for (a, b) in g.edges:
            if a in s and b in s:
                cycle_edges.add((a, b))
    violations = []
    for (a, b), ev in g.edges.items():
        la, lb = g.nodes[a]["layer"], g.nodes[b]["layer"]
        if lb not in ALLOWED.get(la, ALLOWED["unknown"]):
            violations.append({"from": a, "to": b, "from_layer": la, "to_layer": lb, "evidence": ev, "rule": f"{la} must not depend on {lb}"})
    edges = [{"from": a, "to": b, "evidence": ev, "in_cycle": (a, b) in cycle_edges} for (a, b), ev in sorted(g.edges.items())]
    god = [n for n, d in g.nodes.items() if d["fan_in"] >= 3 and d["fan_out"] >= 3]
    return {"nodes": sorted(g.nodes.values(), key=lambda d: (-d["fan_in"], d["id"])), "edges": edges, "cycles": cycles,
            "layer_violations": violations, "god_module_candidates": god,
            "summary": {"modules": len(g.nodes), "edges": len(edges), "cycles": len(cycles), "layer_violations": len(violations)}}


def to_mermaid(doc):
    out = ["flowchart LR"]
    ids = {n["id"]: f"n{i}" for i, n in enumerate(doc["nodes"])}
    for n in doc["nodes"]:
        out.append(f'  {ids[n["id"]]}["{n["id"]}<br/>({n["layer"]}, in {n["fan_in"]} / out {n["fan_out"]})"]')
    red = []
    for i, e in enumerate(doc["edges"]):
        out.append(f'  {ids[e["from"]]} --> {ids[e["to"]]}')
        if e["in_cycle"]:
            red.append(str(i))
    if red:
        out.append(f"  linkStyle {','.join(red)} stroke:#c00,stroke-width:2px;")
    return "\n".join(out) + "\n"


def to_md(doc):
    out = ["# Module dependency graph", "", f"Modules: {doc['summary']['modules']}  Edges: {doc['summary']['edges']}  Cycles: {doc['summary']['cycles']}  Layer violations: {doc['summary']['layer_violations']}", "",
           "| Module | Layer | Fan-in | Fan-out | Instability | Depends on | In cycle |", "|---|---|---|---|---|---|---|"]
    incycle = {n for c in doc["cycles"] for n in c}
    for n in doc["nodes"]:
        out.append(f"| {n['id']} | {n['layer']} | {n['fan_in']} | {n['fan_out']} | {n['instability'] if n['instability'] is not None else '-'} | {', '.join(n['depends_on']) or '-'} | {'yes' if n['id'] in incycle else ''} |")
    out += ["", "## Cycles", ""]
    out += [f"- {' -> '.join(c)} -> {c[0]}" for c in doc["cycles"]] or ["- none"]
    out += ["", "## Layer violations", ""]
    out += [f"- {v['from']} ({v['from_layer']}) -> {v['to']} ({v['to_layer']}): {v['rule']} - `{v['evidence']}`" for v in doc["layer_violations"]] or ["- none"]
    out += ["", "## God-module candidates (fan-in >= 3 and fan-out >= 3)", ""]
    out += [f"- {n}" for n in doc["god_module_candidates"]] or ["- none"]
    out += ["", "Layer inference is name-based; confirm before writing a finding."]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--stack", default="auto")
    ap.add_argument("--ts-root", default=None)
    ap.add_argument("--ts-depth", type=int, default=1)
    ap.add_argument("--out"); ap.add_argument("--md"); ap.add_argument("--mermaid")
    a = ap.parse_args()
    g = Graph()
    stacks = {a.stack} if a.stack != "auto" else {"dotnet", "java-spring", "node-express", "python-django", "angular", "react", "vue"}
    if "dotnet" in stacks:
        dotnet(a.root, g)
    if "java-spring" in stacks:
        java(a.root, g)
    if stacks & {"node-express", "angular", "react", "vue"}:
        node_workspaces(a.root, g)
        ts_root = a.ts_root or detect_ts_root(a.root)
        if ts_root:
            ts_imports(a.root, g, ts_root, a.ts_depth)
    if "python-django" in stacks:
        django(a.root, g)
    doc = analyse(g)
    doc["root"] = os.path.abspath(a.root)
    for path, text in ((a.out, json.dumps(doc, indent=2)), (a.md, to_md(doc)), (a.mermaid, to_mermaid(doc))):
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
    print(to_md(doc) if not (a.out or a.md or a.mermaid) else json.dumps(doc["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
