#!/usr/bin/env python3
"""Aggregate every audit/findings/*.json (and audit/status/*.json) into a severity summary,
a Critical/High list, a blocker list and the Go / No-Go recommendation.

Usage:
    python aggregate_findings.py <repo_root> [--findings-dir audit/findings] [--status-dir audit/status]
                                 [--readiness readiness.json] [--accepted accepted.json] [--as-of YYYY-MM-DD]
                                 [--out summary.json] [--md summary.md]

Loading, de-duplication, acceptance checks and the verdict come from audit-findings-rollup
($AUDIT_CORE_ROOT/skills/audit-findings-rollup/scripts/findings_rollup.py). The rule (references/go-no-go-rules.md):
  NO-GO           any open Critical or High finding, from any skill
  CONDITIONAL GO  only Medium or Low findings are open
  GO              nothing above Info is open
"Open" excludes confidence "false-positive" and findings covered by a valid risk acceptance.
Skills that failed, were skipped, did not run or ran with limited access are listed as caveats;
they never change the verdict word.

--accepted points at a JSON list of {"id": "SEC-004", "accepted_by": "...", "date": "...", "reason": "...",
"expires": "YYYY-MM-DD"}; a record needs all four of id/accepted_by/date/reason, and an "expires" before --as-of
(default today, UTC) no longer lifts the finding. Other keys are kept verbatim.

--readiness (readiness_probe.py output) is listed as a checklist section only. Failed checklist items reach
the verdict as READY- findings written in SKILL.md step 4, never directly.
Read-only against the audited repo; writes only where --out/--md point.
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
_ROLLUP = os.path.join(_SKILLS, "audit-findings-rollup", "scripts", "findings_rollup.py")
try:
    _spec = importlib.util.spec_from_file_location("audit_findings_rollup", _ROLLUP)
    fr = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(fr)
except (FileNotFoundError, AttributeError, ImportError):
    sys.exit("audit-findings-rollup must be reachable from this skill (audit-core plugin or sibling layout; expected " + _ROLLUP + ")")

EXPECTED_SKILLS = [
    "audit-authz-and-access-control", "audit-injection-vulnerabilities", "audit-secrets-and-config",
    "audit-security-headers-and-middleware", "audit-frontend-xss-and-dom-safety", "audit-client-auth-and-storage",
    "audit-dependency-vulnerabilities", "audit-multi-tenant-isolation", "audit-async-and-dependency-injection",
    "audit-orm-query-and-data-access", "audit-backend-resource-leak", "audit-frontend-best-practices",
    "audit-frontend-memory-leak", "audit-accessibility-and-i18n", "audit-db-schema", "audit-concurrency-and-race-condition",
    "audit-api-contract", "audit-business-logic", "audit-datetime-and-timezone", "audit-performance-and-scalability",
    "audit-system-design", "audit-technical-debt", "audit-logging-and-observability", "audit-test-coverage-and-ci",
    "audit-infra-and-deployment", "audit-licensing-and-compliance", "audit-owasp-asvs-mapper", "audit-gdpr-data-protection",
    "audit-soc2-controls-evidence", "audit-privacy-data-flow-mapper",
]
SEVERITIES = fr.SEVERITIES


def _cell(v):
    return str(v if v not in (None, "") else "-").replace("|", "/").replace("\n", " ")


def build(a):
    fdir = a.findings_dir or os.path.join(a.root, "audit", "findings")
    sdir = a.status_dir or os.path.join(a.root, "audit", "status")
    fl, sl = fr.load_findings(fdir), fr.load_status(sdir)
    acc = fr.load_acceptances(a.accepted, a.as_of)
    live = [f for f in fl["findings"] if f.get("confidence") != "false-positive"]
    merged = fr.merge_by_root_cause(live)
    skills = fr.skill_summary(fl, sl, EXPECTED_SKILLS)
    for e in skills["by_skill"]:
        e["counts_rollup"] = fr.severity_counts([f for f in merged if f.get("skill") == e["skill"]])
    v = fr.verdict(merged, acc, skills)
    raw_rows = fr.critical_high(fl["findings"], acc)
    missing = {x["skill"] for k in ("not_run", "failed", "skipped") for x in skills[k]}
    readiness = None
    if a.readiness and os.path.exists(a.readiness):
        with open(a.readiness, "r", encoding="utf-8") as fh:
            readiness = json.load(fh)
    return {
        "root": os.path.abspath(a.root),
        "as_of": acc["as_of"].isoformat() if hasattr(acc.get("as_of"), "isoformat") else acc.get("as_of"),
        "recommendation": v["verdict"],
        "reason": v["reason"],
        "caveats": v["caveats"],
        "totals": fr.severity_counts(live),
        "open": v["open"],
        "skills": [{"skill": e["skill"], "findings_file": e["findings_file"], "status": e["status"] or "completed",
                    "status_file": e["status_file"], "counts": e["counts_raw"], "critical_high_ids": e["critical_high_ids"],
                    "reason": e["reason"]} for e in skills["by_skill"]],
        "unreadable": skills["unreadable"],
        "no_status_file": skills["no_status_file"],
        "not_run": [s for s in EXPECTED_SKILLS if s in missing],
        "critical_high": [dict(r, accepted=not r["open"], acceptance=(r["acceptance"]["records"] or [None])[0])
                          for r in raw_rows],
        "blockers": v["blockers"],
        "accepted": acc["valid"],
        "acceptances": {"expired": acc["expired"], "invalid": acc["invalid"],
                        "parse_error": acc.get("parse_error")},
        "readiness_items_not_passing": [i for i in (readiness or {}).get("items", []) if i.get("status") in ("fail", "unknown")],
    }


def to_md(doc):
    md = ["# Aggregated audit findings", "", f"## Recommendation: {doc['recommendation']}", "", doc["reason"], ""]
    if doc["caveats"]:
        md += ["Caveats (the recommendation covers only what was assessed):", ""] + [f"- {c}" for c in doc["caveats"]] + [""]
    md += ["Totals (false positives excluded, before de-duplication): " + ", ".join(f"{s} {doc['totals'][s]}" for s in SEVERITIES), ""]
    md += ["## Blockers (open Critical and High)", "", "| # | Id | Skill | Severity | Title | Location | Merged ids | Acceptance |",
           "|---|---|---|---|---|---|---|---|"]
    for n, b in enumerate(doc["blockers"], 1):
        md.append(f"| {n} | {b['id']} | {b['skill']} | {b['severity']} | {_cell(b['title'])} | `{b['location']}` | "
                  f"{_cell(', '.join(b['merged_ids']))} | {b['acceptance']} |")
    if not doc["blockers"]:
        md.append("| - | none | | | | | | |")
    md += ["", "## Critical / High findings by skill", "", "| Skill | Status | Critical | High | Medium | Low | Info | Critical/High ids |",
           "|---|---|---|---|---|---|---|---|"]
    rows = {r["skill"]: r for r in doc["skills"]}
    for name in sorted(rows):
        r = rows[name]
        if r["findings_file"] is None and r["status_file"] is None:
            md.append(f"| {name} | not run | - | - | - | - | - | |")
            continue
        c = r["counts"]
        md.append(f"| {name} | {r['status']} | {c['Critical']} | {c['High']} | {c['Medium']} | {c['Low']} | {c['Info']} | "
                  f"{', '.join(i for i in r['critical_high_ids'] if i)} |")
    if doc["readiness_items_not_passing"]:
        md += ["", "## Readiness checklist items not passing (each failed item must also be a READY- finding)", ""]
        md += [f"- {i['id']}: {i['status']} - {i.get('what_would_make_it_pass') or '-'}" for i in doc["readiness_items_not_passing"]]
    if doc["accepted"]:
        md += ["", "## Accepted risks", ""] + [
            f"- {v['id']}: accepted by {v['accepted_by']} on {v['date']}" + (f", expires {v['expires']}" if v.get("expires") else "")
            + f" - {v['reason']}" for v in doc["accepted"]]
    if doc["acceptances"]["expired"] or doc["acceptances"]["invalid"]:
        md += ["", "## Acceptances not applied", ""] + [
            f"- {e['record'].get('id') if isinstance(e['record'], dict) else e['record']}: {e['why']}"
            for e in doc["acceptances"]["expired"] + doc["acceptances"]["invalid"]]
    md.append("")
    return "\n".join(md)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--findings-dir", default=None)
    ap.add_argument("--status-dir", default=None)
    ap.add_argument("--readiness")
    ap.add_argument("--accepted")
    ap.add_argument("--as-of", dest="as_of", default=None)
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args()
    doc = build(a)
    md = to_md(doc)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, default=str)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(md)
    print(md if not (a.out or a.md) else json.dumps({"recommendation": doc["recommendation"], "caveats": len(doc["caveats"]),
                                                     "totals": doc["totals"], "blockers": len(doc["blockers"]),
                                                     "not_run": len(doc["not_run"])}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
