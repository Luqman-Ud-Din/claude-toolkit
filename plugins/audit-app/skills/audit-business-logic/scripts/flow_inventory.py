#!/usr/bin/env python3
"""List candidate business flows in a repository so the reviewer knows what to
trace by hand.

Usage:
    python flow_inventory.py <repo_root> [--out audit/evidence/audit-business-logic/flows.json] [--md flows.md]

What it collects (all stacks, heuristics on names):
  * status/state enums (C# enum, Java enum, TS enum/union, Python TextChoices)
    with their member names -> the states of each flow
  * every line that assigns a status/state field -> the transitions to map
  * files whose name matches a domain entity (order, payment, invoice,
    subscription, stock, inventory, approval, coupon, discount, refund, role,
    permission, impersonat, wallet, credit, voucher, ledger)
  * handlers (controller/route/job/task) in those files

Output is JSON: {"enums": [...], "status_writes": [...], "domain_files": [...]}
grouped under a guessed flow name. Every entry is a pointer for the manual
trace, not a finding. Read-only.
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

# Generated schema migrations carry no business rules; skipped on top of the shared walker defaults.
MIGRATION_DIRS = ("migrations", "Migrations")
EXTS = {".cs", ".java", ".kt", ".ts", ".tsx", ".js", ".jsx", ".py", ".vue"}

FLOW_WORDS = {
    "payments": ["payment", "pay", "charge", "refund", "checkout", "gateway", "webhook", "transaction"],
    "orders": ["order", "sale", "cart", "shipment", "fulfil"],
    "subscriptions": ["subscription", "plan", "billing", "invoice", "renewal", "trial"],
    "inventory": ["stock", "inventory", "warehouse", "batch", "transfer", "purchase", "ledger"],
    "discounts": ["discount", "coupon", "promo", "voucher", "credit", "wallet", "loyalty"],
    "approvals": ["approval", "approve", "workflow", "review", "reject"],
    "permissions": ["role", "permission", "impersonat", "admin", "tenant", "company"],
}

ENUM_RE = re.compile(r"\b(enum|class)\s+(\w*(Status|State|Stage)\w*)\b")
TS_UNION_RE = re.compile(r"type\s+(\w*(Status|State)\w*)\s*=\s*(['\"]\w+['\"]\s*\|?\s*)+")
STATUS_WRITE_RE = re.compile(r"\.(Status|State|status|state|Stage|stage)\s*=\s*[^=]|\.set(Status|State)\(|status\s*:\s*['\"]\w+['\"]")
HANDLER_RE = re.compile(
    r"\[(Http(Post|Put|Patch|Delete|Get))\b|@(Post|Put|Patch|Delete|Get)Mapping|@(Post|Put|Patch|Delete)\(|"
    r"router\.(post|put|patch|delete)\(|app\.(post|put|patch|delete)\(|def\s+(post|put|patch|delete|perform_\w+)\(|"
    r"@api_view|@shared_task|@Scheduled|RecurringJob|node-cron|cron\.schedule|@Cron\(")


def guess_flow(name):
    low = name.lower()
    for flow, words in FLOW_WORDS.items():
        if any(w in low for w in words):
            return flow
    return "other"


def iter_files(root):
    return repo_walk.iter_files(root, exts=EXTS, names=frozenset(), extra_skip=MIGRATION_DIRS)


def enum_members(lines, start):
    members = []
    depth = 0
    for line in lines[start:start + 60]:
        depth += line.count("{") - line.count("}")
        for m in re.finditer(r"^\s*([A-Z][A-Za-z0-9_]*)\s*(=\s*[^,]+)?,?\s*(//.*)?$", line):
            members.append(m.group(1))
        if depth <= 0 and "{" in "".join(lines[start:start + 2]) and line.strip().endswith("}"):
            break
    return members[:40]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out", default=None)
    ap.add_argument("--md", default=None)
    args = ap.parse_args()

    enums, writes, domain = [], [], []
    for path in iter_files(args.root):
        rel = repo_walk.rel(args.root, path)
        lines = repo_walk.read_lines(path)
        base = os.path.basename(path)
        flow = guess_flow(rel)
        handlers = []
        for n, line in enumerate(lines, 1):
            m = ENUM_RE.search(line)
            if m and ("enum" in m.group(1) or "TextChoices" in line):
                enums.append({"name": m.group(2), "file": rel, "line": n, "flow": guess_flow(m.group(2) + rel),
                              "members": enum_members(lines, n - 1)})
            m2 = TS_UNION_RE.search(line)
            if m2:
                enums.append({"name": m2.group(1), "file": rel, "line": n, "flow": guess_flow(m2.group(1) + rel),
                              "members": re.findall(r"['\"](\w+)['\"]", line)})
            if STATUS_WRITE_RE.search(line):
                writes.append({"file": rel, "line": n, "flow": flow, "snippet": line.strip()[:200]})
            if HANDLER_RE.search(line):
                handlers.append({"line": n, "snippet": line.strip()[:160]})
        if flow != "other" or handlers:
            domain.append({"file": rel, "flow": flow, "handlers": handlers[:50]})

    by_flow = {}
    for e in enums:
        by_flow.setdefault(e["flow"], {"enums": [], "status_writes": [], "files": []})["enums"].append(e)
    for w in writes:
        by_flow.setdefault(w["flow"], {"enums": [], "status_writes": [], "files": []})["status_writes"].append(w)
    for d in domain:
        by_flow.setdefault(d["flow"], {"enums": [], "status_writes": [], "files": []})["files"].append(d)

    result = {"root": os.path.abspath(args.root), "flows": by_flow,
              "totals": {"enums": len(enums), "status_writes": len(writes), "domain_files": len(domain)}}
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("| Flow | Enums | Status writes | Files with handlers |\n|---|---|---|---|\n")
            for flow, d in sorted(by_flow.items()):
                fh.write(f"| {flow} | {len(d['enums'])} | {len(d['status_writes'])} | {len(d['files'])} |\n")
            fh.write("\n## Status writes\n\n| Flow | Location | Snippet |\n|---|---|---|\n")
            for w in writes:
                fh.write(f"| {w['flow']} | `{w['file']}:{w['line']}` | `{w['snippet'].replace('|', '/')[:100]}` |\n")
    print(json.dumps(result["totals"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
