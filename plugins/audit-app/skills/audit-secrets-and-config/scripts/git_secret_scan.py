#!/usr/bin/env python3
"""Scan a repository's FULL git history for hard-coded secrets.

A secret removed from the current tree is still exploitable if it remains in
history. This reads the lines every commit added on every ref (audit-git-history's
added_lines) and matches them against the secret value rules of
audit-sensitive-data-catalog: API keys, connection strings with passwords, JWT
signing keys, private-key blocks and credential assignments. For each hit it
reports commit + file + line + which rule matched, so you can build the "commits
to purge" list. Read-only: it never writes to the repo.

Usage:
    python git_secret_scan.py <repo_root> [--max-commits 2000] [--out hits.json]
                                          [--md hits.md] [--include-tree]

  --include-tree  also scan the current working tree files (useful when the path
                  is not a git repo, e.g. an extracted sample). Without it, a
                  non-git path prints a clear message and exits 0.

Notes:
  * History comes from one `git log -p --cc --all` stream capped at --max-commits, so
    every branch is covered; a merge commit contributes only lines new to every parent.
    Binary diffs are skipped. A shallow clone is reported under not_checked.
  * Working-tree files are read with audit-code-scan's repo_walk (shared skip list).
  * Placeholders are judged per value; well-known default credentials (admin, sa,
    postgres) are still reported as committed weak secrets.
  * This is a regex pre-filter; treat every hit as a candidate and confirm it is
    a real, still-valid secret before writing a finding (see references/*.md).
  * To PURGE confirmed secrets, use git filter-repo / BFG and ROTATE the secret;
    this script only finds them.
"""
import argparse
import importlib.util
import json
import os
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
_SDC_PATH = os.path.join(_SKILLS, "audit-sensitive-data-catalog", "scripts", "catalog.py")
if not os.path.exists(_SDC_PATH):
    sys.exit("audit-sensitive-data-catalog must be reachable from this skill (audit-core plugin or sibling layout; expected " + _SDC_PATH + ")")
_spec = importlib.util.spec_from_file_location("sensitive_data_catalog", _SDC_PATH)
sdc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sdc)
_GH_PATH = os.path.join(_SKILLS, "audit-git-history", "scripts", "githist.py")
if not os.path.exists(_GH_PATH):
    sys.exit("audit-git-history must be reachable from this skill (audit-core plugin or sibling layout; expected " + _GH_PATH + ")")
_spec = importlib.util.spec_from_file_location("audit_git_history_githist", _GH_PATH)
githist = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = githist
_spec.loader.exec_module(githist)

SECRETISH = ("credential", "secret")
# catalog rule id -> (rule name reported by this script, severity_hint, reference)
LEGACY = {
    "V-AWS-SECRET-KEY": ("aws-secret-key", "Critical", "CWE-798"),
    "V-AWS-SECRET-KEY-NEAR": ("aws-secret-key", "Critical", "CWE-798"),
    "V-AWS-ACCESS-KEY-ID": ("aws-access-key-id", "High", "CWE-798"),
    "V-STRIPE-SECRET": ("stripe-secret", "Critical", "CWE-798"),
    "V-SENDGRID": ("sendgrid", "Critical", "CWE-798"),
    "V-GOOGLE-API-KEY": ("google-api-key", "High", "CWE-798"),
    "V-SLACK-TOKEN": ("slack-token", "High", "CWE-798"),
    "V-GITHUB-TOKEN": ("github-token", "High", "CWE-798"),
    "V-PEM-PRIVATE-KEY": ("private-key", "Critical", "CWE-321"),
    "V-CONN-STRING-PASSWORD": ("conn-str-password", "High", "CWE-798"),
}
MIN_LEN = {"jwt-signing-key": 12, "generic-api-key": 16, "password-assign": 6}


def _assignment_name(m):
    sub = m["subcategory"]
    if sub == "key-material" or (sub == "application-secret" and "jwt" in m["attributes"]["key"].lower()):
        return "jwt-signing-key", "Critical"
    if sub in ("api-key", "token", "application-secret", "service-credential"):
        return "generic-api-key", "High"
    return "password-assign", "High"


def match_line(line):
    """Return (rule, severity_hint, reference) for the highest-priority secret on the line, else None."""
    best = None
    for m in sdc.find_values(line):
        if m["category"] not in SECRETISH or m["exposure"] == "public":
            continue
        if m["placeholder"] and m["placeholder"]["kind"] != "default-credential":
            continue
        if m["kind"] == "assignment":
            name, sev = _assignment_name(m)
            if not m["attributes"]["quoted"] or len(m["value"]) < MIN_LEN[name]:
                continue
            cand = (name, sev, m["cwe"] or "CWE-798")
        else:
            cand = LEGACY.get(m["rule_id"], (m["rule_id"].lower(), "High", m["cwe"] or "CWE-798"))
        if best is None or m["priority"] > best[0]:
            best = (m["priority"], cand)
    return best[1] if best else None


def scan_history(hist, max_commits):
    hits = []
    for row in hist.added_lines(all_refs=True, max_commits=max_commits):
        m = match_line(row["text"])
        if m:
            name, sev, ref = m
            hits.append({"rule": name, "severity_hint": sev, "reference": ref,
                         "commit": row["hash_full"][:12], "author": row["author"],
                         "date": githist.iso(row["date"]), "file": row["file"], "line": row["line"],
                         "snippet": row["text"].strip()[:200]})
    return hits


def scan_tree(hist):
    hits = []
    for row in hist.tree_lines():
        m = match_line(row["text"])
        if m:
            name, sev, ref = m
            hits.append({"rule": name, "severity_hint": sev, "reference": ref,
                         "commit": "(working tree)", "author": "", "date": "",
                         "file": row["file"], "line": row["line"], "snippet": row["text"].strip()[:200]})
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--max-commits", type=int, default=2000)
    ap.add_argument("--out")
    ap.add_argument("--md")
    ap.add_argument("--include-tree", action="store_true")
    args = ap.parse_args()

    hist = githist.History(args.root)
    hits = []
    if hist.mode == "git":
        hits.extend(scan_history(hist, args.max_commits))
    elif not args.include_tree:
        print(f"{args.root} is not a git repository; pass --include-tree to scan the files as-is.")
        return 0
    if args.include_tree:
        hits.extend(scan_tree(hist))

    result = {"root": os.path.abspath(args.root), "total_hits": len(hits),
              "commits_with_secrets": sorted({h["commit"] for h in hits if h["commit"] != "(working tree)"}),
              "hits": hits,
              # shallow clone or no history: older commits were not scanned
              "not_checked": hist.not_checked()}
    text = json.dumps(result, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(args.out)
    else:
        print(text)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("| Rule | Sev | Commit | File | Snippet |\n|---|---|---|---|---|\n")
            for h in hits:
                snip = h["snippet"].replace("|", "\\|")
                loc = h["file"] + (f":{h['line']}" if h.get("line") else "")
                fh.write(f"| {h['rule']} | {h['severity_hint']} | `{h['commit']}` | `{loc}` | `{snip[:90]}` |\n")
            for n in result["not_checked"]:
                fh.write(f"\nNot checked: {n['item']} - {n['reason']}\n")
        print(args.md)
    print(f"# {len(hits)} candidate secrets in {len(result['commits_with_secrets'])} commits", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
