#!/usr/bin/env python3
"""Compare the architecture described in README / docs / ADRs / diagrams with
the architecture discovered by module_graph.py and topology_scan.py.

Usage:
    python doc_drift.py <repo_root> [--modules modules.json] [--topology topology.json]
                        [--out drift.json] [--md drift.md]

Documentation sources scanned: README*.md, docs/**/*.md, doc/, adr/, docs/adr, docs/decisions,
architecture/, *.puml, *.plantuml, *.drawio, *.dsl (C4), CLAUDE.md, CONTRIBUTING.md.
Extracted: component names from Mermaid nodes/edges, PlantUML components/databases/queues,
drawio labels, and backticked/bold identifiers that look like module or service names;
ADR inventory (title, status, date, decision sentence).

Output: documented_not_found (stale), found_not_documented, relationship claims, ADR list.
Name matching is normalised (lowercase, alphanumerics only, common suffixes dropped), so
"Payments Service" matches "payments-service" and "Payments.Service". Read-only.
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

DOC_DIR_HINTS = ("docs", "doc", "adr", "adrs", "decisions", "architecture", "design", "wiki")
STOP = {"the", "and", "for", "with", "from", "into", "via", "http", "https", "api", "app", "service", "services", "client", "server", "user", "users",
        "browser", "mobile", "internet", "note", "todo", "yes", "no", "true", "false", "null", "json", "xml", "get", "post", "put", "delete",
        "db", "database", "queue", "cache", "gateway", "frontend", "backend", "web", "ui", "spa", "system", "external", "internal", "flowchart", "graph",
        "subgraph", "end", "lr", "tb", "rl", "bt", "td", "class", "classdef", "style", "linkstyle", "sequencediagram", "participant", "actor"}
SUFFIXES = ("microapi", "service", "svc", "api", "worker", "host", "server", "app", "module", "core", "queue", "broker", "cache", "cluster")


def _read(p):
    return repo_walk.read_text(p)


def norm(name):
    n = re.sub(r"[^a-z0-9]", "", name.lower())
    for s in SUFFIXES:
        if n.endswith(s) and len(n) - len(s) >= 3:
            n = n[: -len(s)]
    return n


def is_doc(path, root):
    rp = os.path.relpath(path, root).replace(os.sep, "/").lower()
    fn = os.path.basename(rp)
    if fn.startswith("readme") or fn in ("claude.md", "contributing.md", "architecture.md", "design.md"):
        return True
    if fn.endswith((".puml", ".plantuml", ".drawio", ".dsl")):
        return True
    return fn.endswith(".md") and any(seg in DOC_DIR_HINTS for seg in rp.split("/")[:-1])


def extract(text, rp):
    names, rels, alias = {}, [], {}

    def add(n, ctx):
        n = n.strip().strip("\"'`*[]()")
        if not n or len(n) < 3 or n.lower() in STOP or not re.search(r"[a-zA-Z]", n):
            return
        names.setdefault(n, ctx)

    # mermaid blocks
    for m in re.finditer(r"```mermaid\s*\n(.*?)```", text, re.S):
        block, start = m.group(1), text.count("\n", 0, m.start()) + 1
        for i, line in enumerate(block.splitlines(), start + 1):
            l = line.strip()
            if not l or l.startswith(("%%", "classDef", "class ", "style", "linkStyle", "subgraph", "end")):
                if l.startswith("subgraph"):
                    sm = re.match(r"subgraph\s+\w+\s*\[([^\]]+)\]", l)
                    if sm:
                        add(sm.group(1), f"{rp}:{i} subgraph")
                continue
            for nm in re.finditer(r"(\w[\w.-]*)\s*(?:\[\(?/?\{?\{?\"?([^\]\)\}\"]+)|\(\(?([^\)]+)\)|\{\{([^\}]+)\}\})", l):
                label = nm.group(2) or nm.group(3) or nm.group(4)
                add(nm.group(1), f"{rp}:{i} node id")
                if label:
                    clean = re.sub(r"<br\s*/?>.*", "", label).split(":")[0].strip()
                    add(clean, f"{rp}:{i} node label")
                    alias[nm.group(1)] = clean
            for em in re.finditer(r"(\w[\w.-]*)(?:\[[^\]]*\]|\([^)]*\)|\{[^}]*\})?\s*(?:-->|-\.->|==>|---|-\.-|->>|-->>|<-->)\s*(?:\|[^|]*\|\s*)?(\w[\w.-]*)", l):
                rels.append({"from": alias.get(em.group(1), em.group(1)), "to": alias.get(em.group(2), em.group(2)), "where": f"{rp}:{i}"})
                add(em.group(1), f"{rp}:{i} edge"); add(em.group(2), f"{rp}:{i} edge")
    # plantuml
    for i, line in enumerate(text.splitlines(), 1):
        for pm in re.finditer(r"(?:component|database|queue|node|rectangle|package|actor|interface|cloud)\s+\"([^\"]+)\"|\[([^\]]+)\]\s*(?:as\s+\w+)?", line):
            if line.strip().startswith(("!", "'", "skinparam")):
                continue
            if re.search(r"^\s*(component|database|queue|node|rectangle|package|actor|cloud)\b", line) or rp.endswith((".puml", ".plantuml")):
                add(pm.group(1) or pm.group(2), f"{rp}:{i} plantuml")
        if rp.endswith((".puml", ".plantuml")):
            em = re.search(r"^\s*\[?([\w .-]+?)\]?\s*(?:-+>|\.+>|<-+)\s*\[?([\w .-]+?)\]?\s*(?::|$)", line)
            if em:
                rels.append({"from": em.group(1).strip(), "to": em.group(2).strip(), "where": f"{rp}:{i}"})
    # drawio / dsl labels
    if rp.endswith(".drawio"):
        for i, line in enumerate(text.splitlines(), 1):
            for vm in re.finditer(r'value="([^"<]{3,60})"', line):
                add(vm.group(1), f"{rp}:{i} drawio")
    if rp.endswith(".dsl"):
        for i, line in enumerate(text.splitlines(), 1):
            for vm in re.finditer(r'=\s*(?:softwareSystem|container|component|person)\s+"([^"]+)"', line):
                add(vm.group(1), f"{rp}:{i} c4")
    # prose identifiers: backticked or bold tokens that look like modules/services
    if rp.endswith(".md"):
        for i, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith("```"):
                continue
            for tm in re.finditer(r"`([A-Za-z][\w.-]{2,40})`|\*\*([A-Za-z][\w .-]{2,40})\*\*", line):
                tok = tm.group(1) or tm.group(2)
                if re.search(r"(\.|-|_)?(api|service|svc|worker|host|gateway|db|queue|broker|cache|core|module|microapi|redis|rabbit|kafka|postgres|sql)", tok, re.I) or "." in tok:
                    if not tok.lower().endswith((".json", ".yml", ".yaml", ".md", ".cs", ".ts", ".js", ".py", ".java", ".sql", ".csproj", ".sln", ".txt", ".config", ".env")) and "/" not in tok:
                        add(tok, f"{rp}:{i} prose")
    return names, rels


def adr_info(text, rp):
    title = re.search(r"^#\s+(.+)$", text, re.M)
    status = re.search(r"(?i)^\s*(?:##\s*)?status\s*:?\s*\n?\s*\**([A-Za-z][\w -]*)", text, re.M)
    date = re.search(r"(?i)date\s*:?\s*(\d{4}-\d{2}-\d{2})", text)
    decision = re.search(r"(?is)##\s*decision(?:\s+outcome)?\s*\n+(.+?)(?:\n\s*\n|\n##)", text)
    return {"file": rp, "title": title.group(1).strip() if title else os.path.basename(rp),
            "status": status.group(1).strip() if status else "unknown",
            "date": date.group(1) if date else None,
            "decision": re.sub(r"\s+", " ", decision.group(1)).strip()[:300] if decision else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root"); ap.add_argument("--modules"); ap.add_argument("--topology"); ap.add_argument("--out"); ap.add_argument("--md")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    discovered = {}
    if a.modules and os.path.exists(a.modules):
        for n in json.load(open(a.modules, encoding="utf-8")).get("nodes", []):
            discovered.setdefault(norm(n["id"].split("/")[-1]), n["id"])
    if a.topology and os.path.exists(a.topology):
        for c in json.load(open(a.topology, encoding="utf-8")).get("components", []):
            discovered.setdefault(norm(c["name"]), c["name"])
            if c.get("image"):
                discovered.setdefault(norm(str(c["image"]).split(":")[0].split("/")[-1]), c["name"])
    # fallback discovery from manifests when no modules.json is given
    if not discovered:
        for path in repo_walk.iter_files(root, exts={".csproj"}, names=frozenset()):
            fn = os.path.basename(path)
            discovered.setdefault(norm(fn[:-7]), fn[:-7])
    documented, rels, adrs, docs_seen = {}, [], [], []
    # globs=("*",): diagram formats (.puml, .drawio, .dsl) are outside the walker's text extensions.
    for p in repo_walk.iter_files(root, globs=("*",)):
        if not is_doc(p, root):
            continue
        rp = repo_walk.rel(root, p)
        docs_seen.append(rp)
        text = _read(p)
        names, r = extract(text, rp)
        rels += r
        for n, ctx in names.items():
            documented.setdefault(norm(n), {"name": n, "where": ctx})
        low = rp.lower()
        if re.search(r"(^|/)(adr|adrs|decisions)/", low) or re.search(r"(^|/)(adr|\d{3,4})-[\w-]+\.md$", low):
            adrs.append(adr_info(text, rp))
    stale = [v | {"key": k} for k, v in documented.items() if k and k not in discovered and not any(k in d or d in k for d in discovered if len(k) >= 5 and len(d) >= 5)]
    undocumented, seen_names = [], set()
    for k, v in discovered.items():
        if not k or k in documented or any(k in d or d in k for d in documented if len(k) >= 5 and len(d) >= 5):
            seen_names.add(v)
    for k, v in discovered.items():
        if k and v not in seen_names and k not in documented and not any(k in d or d in k for d in documented if len(k) >= 5 and len(d) >= 5):
            undocumented.append({"key": k, "name": v}); seen_names.add(v)
    def found(name):
        k = norm(name)
        return bool(k) and (k in discovered or any((k in d or d in k) for d in discovered if len(k) >= 5 and len(d) >= 5))

    rel_checks = [{**r, "from_found": found(r["from"]), "to_found": found(r["to"])} for r in rels]
    doc = {"root": root, "docs_scanned": docs_seen, "discovered": sorted(discovered.values()),
           "documented": sorted(v["name"] for v in documented.values()),
           "documented_not_found": stale, "found_not_documented": undocumented, "relationship_claims": rel_checks, "adrs": adrs,
           "summary": {"docs": len(docs_seen), "documented_components": len(documented), "discovered_components": len(discovered),
                       "stale": len(stale), "undocumented": len(undocumented), "adrs": len(adrs)}}
    md = ["# Documentation drift", "", f"Docs scanned: {len(docs_seen)}  Documented components: {len(documented)}  Discovered: {len(discovered)}  Stale: {len(stale)}  Undocumented: {len(undocumented)}  ADRs: {len(adrs)}", ""]
    if not docs_seen:
        md.append("No README/docs/ADR files found: record an Info finding 'no recorded design'.")
    md += ["## Documented but not found in code/topology (stale?)", "", "| Name | Where documented |", "|---|---|"]
    md += [f"| {s['name']} | {s['where']} |" for s in stale] or ["| none | |"]
    md += ["", "## Found in code/topology but not documented", "", "| Component |", "|---|"]
    md += [f"| {u['name']} |" for u in undocumented] or ["| none |"]
    md += ["", "## Relationship claims in diagrams", "", "| From | To | Where | Both exist? |", "|---|---|---|---|"]
    md += [f"| {r['from']} | {r['to']} | {r['where']} | {'yes' if r['from_found'] and r['to_found'] else 'NO'} |" for r in rel_checks] or ["| none | | | |"]
    md += ["", "## ADR inventory (verify each decision against the code)", "", "| File | Title | Status | Date | Decision |", "|---|---|---|---|---|"]
    md += [f"| {x['file']} | {x['title']} | {x['status']} | {x['date'] or '-'} | {(x['decision'] or '-').replace('|', '/')} |" for x in adrs] or ["| none | | | | |"]
    md += ["", "Name matching is heuristic: a 'stale' row may be a renamed component; confirm before writing a finding."]
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(md) + "\n")
    print("\n".join(md) if not (a.out or a.md) else json.dumps(doc["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
