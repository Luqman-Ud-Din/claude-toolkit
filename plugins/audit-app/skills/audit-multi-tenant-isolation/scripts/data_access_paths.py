#!/usr/bin/env python3
"""Data-access-path inventory for a multi-tenant application.

Statically enumerates every place tenant-owned data is read or written and
records, per path, its tenant-scoping mechanism (global query filter, explicit
predicate, row-level security, or NONE) so the reviewer can see at a glance which
paths are unscoped. It also flags the classic isolation break points: raw SQL,
filter-disabling calls, tenant id read from request input, cache/blob keys with
no tenant segment, and background jobs.

This is a best-effort static extractor; every "?" must be confirmed by reading
the code. Files are walked with audit-code-scan's repo_walk.py, so the slice of the
repository matches every other audit script. tenant_probe.py takes its endpoint
list from audit-endpoint-inventory (endpoints.probe.json); join these rows to it by
file and line when you mark which endpoints are unscoped.

Usage:
    python data_access_paths.py <repo_root> --stack <id> [--out paths.json] [--md paths.md]

<id>: dotnet, java-spring, node-express, python-django (backends carry the data
paths; frontend stacks are out of scope for this inventory - audit their URL/query
building in audit-authz / the frontend skills). Omit --stack to try all.

Row shape:
{"category","file","line","snippet","scoping","risk"}
  category: query | raw-sql | filter-bypass | tenant-from-input | cache-key
            | blob-path | background-job
  scoping:  global-filter | explicit-predicate | NONE | ?     (best guess)
  risk:     high | medium | info
Read-only: never modifies the audited repo.
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
_spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _REPO_WALK)
repo_walk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repo_walk)

TENANT_TOKENS = r"(TenantId|CompanyId|OrgId|OrganizationId|AccountId|tenant_id|tenant)"

# category -> (regex, default scoping, risk, applicable extensions)
RULES = {
    "raw-sql": (re.compile(r"FromSqlRaw|FromSqlInterpolated|ExecuteSqlRaw|createNativeQuery|\.raw\(|cursor\.execute|db\.query\(|entityManager\.createQuery", re.I),
                "?", "high"),
    "filter-bypass": (re.compile(r"IgnoreQueryFilters|withoutGlobalScope|unscoped\(|filter_backends\s*=\s*\[\]|HasQueryFilter\s*\(\s*\)", re.I),
                      "NONE", "high"),
    "tenant-from-input": (re.compile(r"(req(uest)?\.(body|query|params|headers)\.[A-Za-z_]*" + TENANT_TOKENS + r"|dto\.\w*" + TENANT_TOKENS + r"|\[FromBody\][^\n]*" + TENANT_TOKENS + r"|data\.get\(['\"]?" + TENANT_TOKENS + r")", re.I),
                         "NONE", "high"),
    "cache-key": (re.compile(r"(GetStringAsync|SetStringAsync|SetString|_cache\.|cache\.(get|set)|redis\.(get|set)|MemoryCache|IDistributedCache)", re.I),
                  "?", "medium"),
    "blob-path": (re.compile(r"(blobstore|/uploads/|/documents/|PhysicalFile|BlobClient|GetBlobClient|S3|PutObject|GetObject|FileStream|new FileInfo|storage\.(bucket|blob))", re.I),
                  "?", "medium"),
}
QUERY_RE = re.compile(r"\.(Find|FindAsync|SingleOrDefault|FirstOrDefault|Where|ToList|findById|findOne|objects\.(get|filter)|createQuery)\b", re.I)
JOB_HINT = re.compile(r"(Hangfire|IJob\b|BackgroundService|@Scheduled|celery|@shared_task|RecurringJob|IHostedService|class\s+\w*Job\b|class\s+\w*Worker\b)", re.I)
TENANT_NEARBY = re.compile(TENANT_TOKENS, re.I)

EXT_BY_STACK = {"dotnet": {".cs"}, "java-spring": {".java", ".kt"},
                "node-express": {".js", ".ts"}, "python-django": {".py"}}


def scan(root, exts):
    rows = []
    # names=frozenset(): only the stack's source extensions, not Dockerfile/Makefile.
    for path in repo_walk.iter_files(root, exts=exts, names=frozenset()):
        rel = repo_walk.rel(root, path)
        lines = repo_walk.read_lines(path)
        text = "".join(lines)
        # Judge job tenant-context from CODE only; comments often mention "tenant".
        code_lines = []
        for ln in lines:
            s = ln.lstrip()
            if s.startswith(("//", "*", "/*", "#")):
                continue
            code_lines.append(ln.split("//", 1)[0])   # drop trailing line comments
        code_text = "".join(code_lines)
        is_job = bool(JOB_HINT.search(text))
        job_has_tenant = bool(TENANT_NEARBY.search(code_text))
        job_recorded = False
        for i, raw in enumerate(lines):
            line = raw.rstrip("\n")
            window = "".join(lines[max(0, i - 2):i + 3])
            for cat, (rx, scoping, risk) in RULES.items():
                if rx.search(line):
                    sc = scoping
                    if cat in ("cache-key", "blob-path"):
                        sc = "explicit-predicate" if TENANT_NEARBY.search(window) else "NONE"
                        risk = "info" if sc != "NONE" else risk
                    rows.append({"category": cat, "file": rel, "line": i + 1,
                                 "snippet": line.strip()[:200], "scoping": sc, "risk": risk})
            if QUERY_RE.search(line):
                sc = "explicit-predicate" if TENANT_NEARBY.search(window) else "?"
                rows.append({"category": "query", "file": rel, "line": i + 1,
                             "snippet": line.strip()[:200], "scoping": sc,
                             "risk": "medium" if sc == "?" else "info"})
            if is_job and not job_recorded and JOB_HINT.search(line):
                rows.append({"category": "background-job", "file": rel, "line": i + 1,
                             "snippet": line.strip()[:200],
                             "scoping": "explicit-predicate" if job_has_tenant else "NONE",
                             "risk": "info" if job_has_tenant else "high"})
                job_recorded = True
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--stack", choices=sorted(EXT_BY_STACK))
    ap.add_argument("--out")
    ap.add_argument("--md")
    args = ap.parse_args()

    exts = EXT_BY_STACK[args.stack] if args.stack else set().union(*EXT_BY_STACK.values())
    rows = scan(args.root, exts)
    unscoped = [r for r in rows if r["scoping"] == "NONE"]
    doc = {"root": os.path.abspath(args.root), "count": len(rows),
           "unscoped_count": len(unscoped),
           "note": "static best-effort; confirm every '?' and 'NONE' by reading the code",
           "paths": rows}
    text = json.dumps(doc, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(args.out)
    else:
        print(text)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("| Category | Scoping | Risk | Location | Snippet |\n|---|---|---|---|---|\n")
            for r in rows:
                snip = r["snippet"].replace("|", "\\|")
                fh.write(f"| {r['category']} | {r['scoping']} | {r['risk']} | "
                         f"`{r['file']}:{r['line']}` | `{snip[:100]}` |\n")
        print(args.md)
    print(f"# {len(rows)} data-access paths, {len(unscoped)} unscoped (NONE)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
