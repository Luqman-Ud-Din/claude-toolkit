#!/usr/bin/env python3
"""Enumerate every HTTP endpoint, websocket, client route and background job in a
repository and record facts about each one. Judges nothing: whether a fact is a
finding is decided by the consuming audit skill.

Usage:
    python inventory_endpoints.py <repo_root> [--stack ID ...] [--out-dir DIR]
                                  [--out FILE] [--md FILE] [--probe FILE] [--print]

    <repo_root>  repository to read (never modified)
    --stack      override stack ids (repeatable): dotnet, java-spring, node-express,
                 python-django, angular, react, vue. Default: audit/stack.json, else
                 ../audit-stack-detection/scripts/detect_stack.py (not written).
    --out-dir    default <repo_root>/audit/evidence/audit-endpoint-inventory
    --out/--md/--probe  override individual output paths
                 (endpoints.json, endpoints.md, endpoints.probe.json)
    --print      also print the full endpoints.json document to stdout

Meta-framework server handlers (Next.js route handlers, API routes, server actions and
middleware; Remix/React Router loaders and actions; Nuxt server routes and middleware) are
read under the react and vue stack roots.

Module use:
    import inventory_endpoints as inv
    doc = inv.build_inventory("/path/to/repo")          # dict, contract in references/
    probe = inv.probe_projection(doc)                     # authz/tenant/loadtest input
    md = inv.render_markdown(doc)

Contract: references/endpoint-inventory-contract.md. Python 3 stdlib only.
Read-only against the audited repository; writes only the three output files.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
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
sys.path.insert(0, _HERE)
_REPO_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
try:
    _rw_spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _REPO_WALK)
    repo_walk = importlib.util.module_from_spec(_rw_spec)
    _rw_spec.loader.exec_module(repo_walk)
except (FileNotFoundError, AttributeError, ImportError):
    sys.exit("audit-code-scan must be reachable from this skill (audit-core plugin or sibling layout; expected " + _REPO_WALK + ")")

import ep_common as c  # noqa: E402
import ep_backends  # noqa: E402
import ep_clients_jobs  # noqa: E402
import ep_metaframeworks  # noqa: E402

SCHEMA_VERSION = "1.0"
BACKENDS = ("dotnet", "java-spring", "node-express", "python-django")
FRONTENDS = ("angular", "react", "vue")
SOURCE_EXT = {".cs", ".java", ".kt", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".py", ".yaml", ".yml"}
KINDS = ("http", "websocket", "job", "client-route", "server-action", "middleware")
KIND_ORDER = {"http": 0, "websocket": 1, "server-action": 2, "middleware": 3, "job": 4, "client-route": 5}


# ============================================================================ stack resolution
def resolve_stacks(root, override=None):
    """Return (stacks [{id, roots}], source)."""
    if override:
        return [{"id": s, "roots": ["."]} for s in override], "--stack"
    cached = os.path.join(root, "audit", "stack.json")
    if os.path.exists(cached):
        try:
            with open(cached, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
            return [{"id": s["id"], "roots": s.get("roots") or ["."]} for s in doc.get("stacks", [])], "audit/stack.json"
        except (OSError, ValueError):
            pass
    try:
        _ds_path = os.path.join(_SKILLS, "audit-stack-detection", "scripts", "detect_stack.py")
        _ds_spec = importlib.util.spec_from_file_location("audit_stack_detection_detect_stack", _ds_path)
        detect_stack = importlib.util.module_from_spec(_ds_spec)
        _ds_spec.loader.exec_module(detect_stack)
        doc = detect_stack.detect(root)
        return [{"id": s["id"], "roots": s.get("roots") or ["."]} for s in doc["stacks"]], "detect_stack.py"
    except Exception as exc:  # pragma: no cover
        print(f"WARNING: stack detection unavailable ({exc}); scanning all backends", file=sys.stderr)
        return [{"id": s, "roots": ["."]} for s in BACKENDS], "fallback-all"


# ============================================================================ context
class Ctx:
    def __init__(self, root, stacks):
        self.root = root
        self.roots = {s["id"]: s["roots"] for s in stacks}
        self.text_by_rel = {}
        for path in repo_walk.iter_files(root, exts=SOURCE_EXT):
            self.text_by_rel[repo_walk.rel(root, path)] = repo_walk.read_text(path)
        self._lines = {}
        backend_text = {r: t for r, t in self.text_by_rel.items() if not r.endswith((".yaml", ".yml"))}
        self.types = c.index_types(backend_text)
        self.methods = build_method_index(self, backend_text)
        self.py_mounts, self.py_mount_auth = python_mounts(self)

    def lines(self, rel):
        if rel not in self._lines:
            self._lines[rel] = self.text_by_rel.get(rel, "").splitlines()
        return self._lines[rel]

    def all_files(self, exts):
        return [(r, t) for r, t in sorted(self.text_by_rel.items()) if r.lower().endswith(exts)]

    def files(self, stack, exts):
        """Files of one stack: under that stack's detected roots, test-named files excluded."""
        roots = [rt.replace("\\", "/").strip("/") for rt in self.roots.get(stack, ["."])]
        out = []
        for r, t in self.all_files(exts):
            if TEST_FILE.search(r):
                continue
            if any(rt in (".", "") or r == rt or r.startswith(rt + "/") for rt in roots):
                out.append((r, t))
        return out


TEST_FILE = re.compile(r"\.(spec|test|stories)\.[cm]?[jt]sx?$|(^|/)test_\w+\.py$|_tests?\.py$|Tests?\.(cs|java|kt)$")


METHOD_DEF = {
    "brace": re.compile(r"^\s*(?:(?:public|private|protected|internal|static|async|virtual|override|final|synchronized|export|default|"
                        r"suspend|open)\s+)+[\w<>\[\],.?\s]*?\b(\w+)\s*(?:<[^>]*>)?\s*\("),
    "js": re.compile(r"^\s*(?:(?:public|private|protected|static|async|export|default)\s+)*(?:function\s*\*?\s*)?(\w+)\s*\([^;]*$|"
                     r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*(?::\s*[^=]+)?=>|"
                     r"^\s*(?:module\.)?exports\.(\w+)\s*=|^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*[^{]+)?\{\s*$"),
    "python": re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\("),
}


def build_method_index(ctx, files_text):
    idx = {}
    for rel, text in files_text.items():
        ext = os.path.splitext(rel)[1].lower()
        lines = ctx.lines(rel)
        lang = "python" if ext == ".py" else ("js" if ext in (".js", ".ts", ".mjs", ".cjs", ".tsx", ".jsx") else "brace")
        rx = METHOD_DEF[lang]
        cls, cls_indent = None, -1
        for i, line in enumerate(lines):
            cm = re.match(r"^(\s*)(?:export\s+)?(?:(?:public|internal|private|protected|abstract|sealed|partial|static|default|data|open)\s+)*"
                          r"class\s+(\w+)", line)
            if cm:
                cls, cls_indent = cm.group(2), len(cm.group(1))
                continue
            if lang == "python" and cls and line.strip() and (len(line) - len(line.lstrip())) <= cls_indent and not line.lstrip().startswith(("@", "#")):
                cls = None
            m = rx.match(line)
            if not m:
                continue
            name = next((g for g in m.groups() if g), None)
            if not name or name in ep_backends.KEYWORDS or name == "constructor":
                continue
            end = c.indent_body_end(lines, i) if lang == "python" else c.brace_body_end(lines, i)
            if lang == "python" and cls and (len(line) - len(line.lstrip())) == 0:
                owner = None
            else:
                owner = cls
            idx.setdefault(name, []).append({"file": rel, "class": owner, "start": i, "end": end})
    return idx


def python_mounts(ctx):
    """FastAPI include_router / Flask register_blueprint prefixes: {module_file: prefix}, {module_file: auth evidence}."""
    mounts, auth = {}, {}
    for rel, text in ctx.all_files((".py",)):
        if "include_router" not in text and "register_blueprint" not in text:
            continue
        imports = {}
        for m in re.finditer(r"^\s*from\s+([\w.]+)\s+import\s+([^\n(]+|\([^)]*\))", text, re.M):
            for part in m.group(2).strip("()").split(","):
                part = part.strip()
                if not part:
                    continue
                name, _, alias = part.partition(" as ")
                imports[(alias or name).strip()] = (m.group(1), name.strip())
        for m in re.finditer(r"\b\w+\.(include_router|register_blueprint)\(\s*([\w.]+)\s*(?:,([^)]*))?\)", text):
            var = m.group(2).split(".")[0]
            opts = m.group(3) or ""
            pm = re.search(r"(?:url_)?prefix\s*=\s*['\"]([^'\"]+)['\"]", opts)
            if var not in imports:
                continue
            module, name = imports[var]
            target = ep_backends._py_module_file(ctx, module + "." + name, rel) or ep_backends._py_module_file(ctx, module, rel)
            if not target:
                continue
            mounts[target] = pm.group(1) if pm else ""
            if re.search(r"dependencies\s*=\s*\[[^\]]*Depends\(", opts):
                auth[target] = {"line": c.line_of(text, m.start()), "text": f"{rel}: {m.group(0)[:120]}"}
    return mounts, auth


# ============================================================================ build
def build_inventory(root, stacks_override=None):
    root = os.path.abspath(root)
    stacks, source = resolve_stacks(root, stacks_override)
    ids = [s["id"] for s in stacks]
    ctx = Ctx(root, stacks)
    out = []
    backend_ids = [s for s in ids if s in BACKENDS]
    warnings = []
    if not backend_ids and not [s for s in ids if s in FRONTENDS]:
        warnings.append("no supported backend or frontend stack detected; scanned all backend extractors over the whole repo")
        for s in BACKENDS:
            ctx.roots[s] = ["."]
        backend_ids = list(BACKENDS)
    for s in backend_ids:
        ep_backends.SCANNERS[s](ctx, out)
    for s in ids:
        if s in FRONTENDS:
            ep_clients_jobs.scan_client_routes(ctx, s, out)
    ep_metaframeworks.scan_metaframeworks(ctx, [s for s in ids if s in ("react", "vue")], out)
    ep_clients_jobs.scan_jobs(ctx, backend_ids, out)

    seen, recs = set(), []
    for r in out:
        k = (r["kind"], r["method"], r["path"], r["file"], r["line"], r["symbol"])
        if k not in seen:
            seen.add(k)
            recs.append(r)

    # error shapes (per file holding http endpoints)
    shapes_by_file = {}
    for f in sorted({r["file"] for r in recs if r["kind"] == "http"}):
        text = ctx.text_by_rel.get(f, "")
        shapes_by_file[f] = sorted({name for name, rx in c.ERROR_SHAPES if rx.search(text)})
    counts = Counter(s for v in shapes_by_file.values() for s in v if s != "exception message/stack")
    majority = counts.most_common(1)[0][0] if counts else None
    for r in recs:
        if r["kind"] not in ("http", "server-action"):
            continue
        shapes = shapes_by_file.get(r["file"], []) if r["kind"] == "http" else             sorted({name for name, rx in c.ERROR_SHAPES if rx.search(ctx.text_by_rel.get(r["file"], ""))})
        r["errors"]["shapes_in_file"] = shapes
        if not shapes:
            r["errors"]["consistent_with_majority"] = "unknown"
        elif majority and set(shapes) == {majority}:
            r["errors"]["consistent_with_majority"] = "yes"
        else:
            r["errors"]["consistent_with_majority"] = "no"
        r["operation"] = operation(r)
    for r in recs:
        if r["kind"] == "websocket":
            r["operation"] = "stream"
        if not r.get("route_location"):
            r["route_location"] = {"file": r["file"], "line": r["line"]}

    recs.sort(key=lambda r: (KIND_ORDER.get(r["kind"], 9), r["path"] or "", r["method"] or "", r["file"] or "", r["line"] or 0))
    c.assign_ids(recs)
    kinds = Counter(r["kind"] for r in recs)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": root,
        "stacks": ids,
        "stack_source": source,
        "counts": {"total": len(recs), **{k: kinds.get(k, 0) for k in KINDS}},
        "error_shapes": {"by_file": shapes_by_file, "distinct": sorted({s for v in shapes_by_file.values() for s in v}),
                         "majority": majority},
        "sensitive_fields_source": c.SENSITIVE_FIELDS_SOURCE,
        "warnings": warnings,
        "endpoints": recs,
    }


def operation(r):
    p = (r["path"] or "").lower()
    if "download" in p:
        return "download"
    if "export" in p:
        return "export"
    if r["method"] in c.WRITE_METHODS:
        return "write"
    if "search" in p or any(x["in"] == "query" and x["name"].lower() in ("q", "query", "term", "search", "keyword", "keywords", "searchterm")
                            and (x["type"] is None or x["type"].rstrip("?").lower() in c.SIMPLE_TYPES) for x in r["params"]):
        return "search"
    if r["response"]["returns_collection"] == "yes":
        return "list"
    if c.route_placeholders(r["path"] or "") or r["response"]["returns_collection"] == "no":
        return "read"
    return "list"


# ============================================================================ projections and rendering
def probe_projection(doc):
    """Input shape shared by authz_probe.py, tenant_probe.py and loadtest_plan.py (http records only)."""
    rows = []
    for r in doc["endpoints"]:
        if r["kind"] != "http":
            continue
        path = r["path"]
        id_params = dict(r["id_params"])
        vev = r["versioned"]["evidence"] or ""
        vm = re.search(r"ApiVersion\(\s*\"(\d+)", vev)
        if c.VERSION_PLACEHOLDER.search(path):
            if vm:
                path = c.VERSION_PLACEHOLDER.sub(vm.group(1), path)
            else:
                for name in re.findall(r"\{(\w+)\}", path):
                    if c.VERSION_PLACEHOLDER.fullmatch("{" + name + "}"):
                        id_params[name] = "version"
        method = r["method"]
        assumed = method == "ANY"
        req = r["auth"]["required"]
        own = {"yes": "Y", "no": "N", "n/a": "-", "unknown": "?"}[r["ownership"]["check"]]
        row = {"id": r["id"], "method": "GET" if assumed else method, "path": path, "route": path,
               "auth_required": {"yes": True, "no": False}.get(req), "auth_source": r["auth"]["source"],
               "roles": r["auth"]["roles"] + ["policy:" + p for p in r["auth"]["policies"]],
               "ownership_check": own, "id_params": id_params, "operation": r["operation"],
               "kind": "write" if method in c.WRITE_METHODS else "read", "weight": 1,
               "tenant_params": [f"{p['in']}:{p['name']}" for p in r["params"] if p["identifier"] == "tenant"],
               "user_params": [f"{p['in']}:{p['name']}" for p in r["params"] if p["identifier"] == "user"],
               "body_fields": [p["name"] for p in r["params"] if p["in"] in ("body", "form") and p["source_type"]]}
        if assumed:
            row["method_assumed"] = True
        rows.append(row)
    return {"schema_version": SCHEMA_VERSION, "base_path": "", "generated_from": "endpoints.json",
            "note": "static extraction; add body/query tamper values and real ids before probing", "endpoints": rows}


def _md(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_markdown(doc):
    out = [f"# Endpoint inventory", "",
           f"Root: `{doc['root']}`  ", f"Stacks: {', '.join(doc['stacks']) or '-'} (source: {doc['stack_source']})  ",
           f"Counts: {json.dumps(doc['counts'])}", ""]
    http = [r for r in doc["endpoints"] if r["kind"] in ("http", "websocket")]
    out += ["## HTTP and websocket endpoints", "",
            "| ID | Method | Path | Handler | Auth | Roles / policies | Ownership | Tenant/user params | Validation | Collection | Pagination | Sensitive response fields | Outbound (seq) | Location |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in http:
        a = r["auth"]
        auth = a["required"] + (f" ({a['source']})" if a["source"] else "")
        ids = ", ".join(f"{p['in']}:{p['name']}" for p in r["params"] if p["identifier"] in ("tenant", "user")) or "-"
        ob = r["outbound"]
        out.append(f"| {r['id']} | {r['method']} | `{_md(r['path'])}` | {_md(r['symbol'])} | {_md(auth)} | "
                   f"{_md(', '.join(a['roles'] + ['policy:' + p for p in a['policies']]) or '-')} | {r['ownership']['check']} | {_md(ids)} | "
                   f"{r['validation']['status']} | {r['response']['returns_collection']} | {r['response']['pagination']['status']} | "
                   f"{_md(', '.join(r['response']['sensitive_fields']) or '-')} | {len(ob['calls'])} ({'seq' if ob['sequential'] else '-'}) | "
                   f"`{r['file']}:{r['line']}` |")
    actions = [r for r in doc["endpoints"] if r["kind"] == "server-action"]
    if actions:
        out += ["", "## Server actions", "", "No URL: invoked by POST to the page that renders them, so they are not in endpoints.probe.json.", "",
                "| ID | Action | Auth | Roles | Ownership | Tenant/user params | Validation | Collection | Outbound (seq) | Location |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for r in actions:
            a = r["auth"]
            ids = ", ".join(f"{p['in']}:{p['name']}" for p in r["params"] if p["identifier"] in ("tenant", "user")) or "-"
            out.append(f"| {r['id']} | `{_md(r['path'])}` | {_md(a['required'] + ' (' + a['source'] + ')')} | {_md(', '.join(a['roles']) or '-')} | "
                       f"{r['ownership']['check']} | {_md(ids)} | {r['validation']['status']} | {r['response']['returns_collection']} | "
                       f"{len(r['outbound']['calls'])} ({'seq' if r['outbound']['sequential'] else '-'}) | `{r['file']}:{r['line']}` |")
    mws = [r for r in doc["endpoints"] if r["kind"] == "middleware"]
    if mws:
        out += ["", "## Middleware", "", "| ID | Framework | Scope | Auth | Location |", "|---|---|---|---|---|"]
        for r in mws:
            out.append(f"| {r['id']} | {r['framework']} | `{_md(r['path'])}` | {_md(r['auth']['required'] + ' (' + r['auth']['source'] + ')')} | "
                       f"`{r['file']}:{r['line']}` |")
    jobs = [r for r in doc["endpoints"] if r["kind"] == "job"]
    out += ["", "## Background jobs", "", "| ID | Framework | Name | Schedule | Target | Identity context | Location |", "|---|---|---|---|---|---|---|"]
    for r in jobs:
        j = r["job"]
        out.append(f"| {r['id']} | {r['framework']} | {_md(j['name'] or '-')} | {_md(j['schedule'] or '-')} | {_md(j['target'] or '-')} | "
                   f"{j['identity_context']} | `{r['file']}:{r['line']}` |")
    routes = [r for r in doc["endpoints"] if r["kind"] == "client-route"]
    out += ["", "## Client routes", "", "| ID | Framework | Path | Target | Client guards | Location |", "|---|---|---|---|---|---|"]
    for r in routes:
        out.append(f"| {r['id']} | {r['framework']} | `{_md(r['path'])}` | {_md(r['symbol'] or '-')} | "
                   f"{_md(', '.join(r['auth']['client_guards']) or 'none')} | `{r['file']}:{r['line']}` |")
    es = doc["error_shapes"]
    out += ["", f"Error shapes seen across endpoint files: {', '.join(es['distinct']) or 'none detected'}; most common: {es['majority'] or '-'}",
            "", f"Sensitive field names: {doc['sensitive_fields_source']}"]
    for w in doc.get("warnings", []):
        out.append(f"\nWARNING: {w}")
    return "\n".join(out) + "\n"


def write_outputs(doc, out_json, out_md, out_probe):
    for path, content in ((out_json, json.dumps(doc, indent=2)), (out_md, render_markdown(doc)),
                          (out_probe, json.dumps(probe_projection(doc), indent=2))):
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)


def summary(doc):
    http = [r for r in doc["endpoints"] if r["kind"] == "http"]
    return {"stacks": doc["stacks"], "stack_source": doc["stack_source"], "counts": doc["counts"],
            "http_auth_required": dict(Counter(r["auth"]["required"] for r in http)),
            "http_explicit_anonymous": sum(1 for r in http if r["auth"]["source"] == "explicit-anonymous"),
            "http_ownership_check": dict(Counter(r["ownership"]["check"] for r in http)),
            "http_pagination": dict(Counter(r["response"]["pagination"]["status"] for r in http)),
            "http_with_sensitive_response_fields": sum(1 for r in http if r["response"]["sensitive_fields"]),
            "http_with_sequential_outbound": sum(1 for r in http if r["outbound"]["sequential"]),
            "jobs_identity_context": dict(Counter(r["job"]["identity_context"] for r in doc["endpoints"] if r["kind"] == "job")),
            "warnings": doc["warnings"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--stack", action="append", choices=list(BACKENDS) + list(FRONTENDS))
    ap.add_argument("--out-dir")
    ap.add_argument("--out")
    ap.add_argument("--md")
    ap.add_argument("--probe")
    ap.add_argument("--print", dest="print_doc", action="store_true")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    if not os.path.isdir(root):
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    out_dir = a.out_dir or os.path.join(root, "audit", "evidence", "audit-endpoint-inventory")
    doc = build_inventory(root, a.stack)
    paths = (a.out or os.path.join(out_dir, "endpoints.json"), a.md or os.path.join(out_dir, "endpoints.md"),
             a.probe or os.path.join(out_dir, "endpoints.probe.json"))
    write_outputs(doc, *paths)
    if a.print_doc:
        print(json.dumps(doc, indent=2))
    else:
        print(json.dumps(summary(doc), indent=2))
        print("\n".join(paths), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
