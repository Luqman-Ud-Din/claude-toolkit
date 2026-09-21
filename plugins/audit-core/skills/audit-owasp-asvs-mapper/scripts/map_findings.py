#!/usr/bin/env python3
"""Map every audit finding onto OWASP Top 10 (2021), ASVS 4.0 controls and CWE ids,
write the references back into each findings.json, and build the coverage matrix.

Usage:
    python map_findings.py [repo_root] [--mapping scripts/mapping.json]
                           [--findings-dir audit/findings] [--status-dir audit/status]
                           [--out audit/reports/audit-owasp-asvs-mapper.md]
                           [--json audit/findings/audit-owasp-asvs-mapper.json]
                           [--dry-run] [--min-level 1|2|3]

What it does:
  1. Loads mapping.json (rules, ASVS section catalogue, control names/levels, skill coverage).
  2. Reads every audit/findings/*.json through audit-findings-rollup's load_findings (its own
     output, by skill name, and underscore-prefixed files are skipped). For each finding it scores
     every rule: +3 if one of the finding's existing CWE references is in the rule, +2 for a
     tag match, +1 per matched keyword (capped at 2) in title/impact/evidence/tags. The best
     scoring rule wins; ties go to the earlier rule in mapping.json.
  3. Adds the rule's OWASP-A0n:2021, ASVS-x.y.z and canonical CWE-nnn to `references`
     (union - existing references are never removed) and records the rule id under
     `extra.mapping`. Existing references are honoured: a finding that already carries
     ASVS-x.y.z ids keeps them and they count in the matrix.
  4. Computes status per ASVS section and per referenced control:
        Failed        - at least one non-false-positive finding maps to it
        Verified      - a skill whose coverage (mapping.json skill_coverage) includes the section
                        completed (status file `completed`, or a findings.json exists) and no
                        finding failed it; also any section/control named in scope.checked as
                        "ASVS-x.y" or "ASVS-x.y.z"
        Not assessed  - neither of the above
  5. Writes the Markdown coverage matrix (--out) and its own findings.json (--json) with an
     Info finding listing the not-assessed sections, plus audit/status/<skill>.json.

--dry-run prints what would change and writes nothing. Read-only against the audited
code: only files under audit/ are written.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone

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

SKILL = "audit-owasp-asvs-mapper"
PREFIX = "MAP"
SEVERITIES = ["Critical", "High", "Medium", "Low", "Info"]
ASVS_RE = re.compile(r"ASVS-?\s*(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)
CWE_RE = re.compile(r"CWE-?\s*(\d+)", re.IGNORECASE)
OWASP_RE = re.compile(r"OWASP-?\s*(A\d{2})", re.IGNORECASE)


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save(path, doc):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)


def norm_refs(refs):
    """Normalise reference spellings so 'cwe 79' and 'CWE-79' compare equal."""
    out = []
    for r in refs or []:
        r = str(r).strip()
        m = CWE_RE.fullmatch(r)
        if m:
            r = f"CWE-{m.group(1)}"
        m = ASVS_RE.fullmatch(r)
        if m:
            r = f"ASVS-{m.group(1)}"
        m = OWASP_RE.match(r)
        if m and ":" not in r:
            r = f"OWASP-{m.group(1).upper()}:2021"
        if r not in out:
            out.append(r)
    return out


def section_of(control_id):
    parts = control_id.split(".")
    return f"V{parts[0]}.{parts[1]}" if len(parts) >= 2 else None


def score_rule(rule, finding):
    refs = norm_refs(finding.get("references", []))
    cwes = {r for r in refs if r.startswith("CWE-")}
    tags = {str(t).lower() for t in finding.get("tags", []) or []}
    text = " ".join(str(finding.get(k, "")) for k in ("title", "impact", "evidence", "remediation")).lower()
    text += " " + " ".join(tags)
    score, why = 0, []
    hit_cwe = [c for c in rule.get("cwe", []) if c in cwes]
    if hit_cwe:
        score += 3
        why.append("cwe:" + ",".join(hit_cwe))
    hit_tag = [t for t in rule.get("tags", []) if t.lower() in tags]
    if hit_tag:
        score += 2
        why.append("tag:" + ",".join(hit_tag))
    hit_kw = [k for k in rule.get("keywords", []) if k.lower() in text]
    if hit_kw:
        score += min(2, len(hit_kw))
        why.append("kw:" + ",".join(hit_kw[:3]))
    return score, ";".join(why)


def best_rule(rules, finding):
    best, best_score, best_why = None, 0, ""
    for rule in rules:
        s, why = score_rule(rule, finding)
        if s > best_score:
            best, best_score, best_why = rule, s, why
    return best, best_why


def apply_rule(finding, rule, why):
    """Union the rule's references into the finding. Never removes anything."""
    refs = norm_refs(finding.get("references", []))
    added = []
    if rule.get("top10") and not any(r.startswith("OWASP-") for r in refs):
        added.append(f"OWASP-{rule['top10']}:2021")
    for c in rule.get("asvs", []):
        r = f"ASVS-{c}"
        if r not in refs:
            added.append(r)
    if rule.get("canonical_cwe") and not any(r.startswith("CWE-") for r in refs):
        added.append(rule["canonical_cwe"])
    finding["references"] = refs + [a for a in added if a not in refs]
    extra = finding.setdefault("extra", {})
    extra["mapping"] = {"rule": rule["id"], "matched_by": why, "added": added,
                        "top10": rule.get("top10"), "asvs": rule.get("asvs", []),
                        "cwe": rule.get("canonical_cwe")}
    return added


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--mapping", default=os.path.join(here, "mapping.json"))
    ap.add_argument("--findings-dir", default=None)
    ap.add_argument("--status-dir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-level", type=int, default=1, help="only list controls at this ASVS level or below")
    a = ap.parse_args()
    started = datetime.now(timezone.utc).isoformat()

    root = a.root
    fdir = a.findings_dir or os.path.join(root, "audit", "findings")
    sdir = a.status_dir or os.path.join(root, "audit", "status")
    out_md = a.out or os.path.join(root, "audit", "reports", f"{SKILL}.md")
    out_json = a.json_out or os.path.join(root, "audit", "findings", f"{SKILL}.json")
    m = load(a.mapping)
    rules, controls, sections = m["rules"], m["controls"], m["asvs_sections"]
    top10 = m["top10"]
    statuses = {k: s["status"] for k, s in fr.load_status(sdir)["skills"].items()}

    fl = fr.load_findings(fdir, exclude_skills={SKILL})
    for e in fl["parse_errors"]:
        print(f"skip {e['file']}: {e['error']}", file=sys.stderr)
    files = [d["path"] for d in fl["documents"]] + [e["file"] for e in fl["parse_errors"]]
    if not files:
        print(f"no findings files under {fdir}", file=sys.stderr)

    mapped, unmapped, rows = [], [], []
    control_hits = {}       # control id -> [finding ids]
    section_hits = {}       # V4.2 -> [finding ids]
    top10_hits = {}         # A01 -> [finding ids]
    verified_by_scope = set()
    completed_skills = set()
    changed_files = 0

    for d in fl["documents"]:
        path, doc, skill = d["path"], d["doc"], d["skill"]
        if statuses.get(skill, "completed") == "completed":
            completed_skills.add(skill)
        for item in doc.get("scope", {}).get("checked", []) or []:
            for mm in ASVS_RE.finditer(str(item)):
                verified_by_scope.add(mm.group(1))
        changed = False
        for f in doc.get("findings", []):
            if f.get("confidence") == "false-positive":
                continue
            rule, why = best_rule(rules, f)
            before = list(f.get("references", []))
            if rule:
                added = apply_rule(f, rule, why)
                if f["references"] != before:
                    changed = True
                mapped.append((skill, f, rule["id"], why))
            else:
                f["references"] = norm_refs(before)
                if not any(r.startswith(("ASVS-", "CWE-", "OWASP-")) for r in f["references"]):
                    unmapped.append((skill, f))
                else:
                    mapped.append((skill, f, "(existing references)", "refs"))
            refs = f["references"]
            for r in refs:
                mm = ASVS_RE.fullmatch(r)
                if mm:
                    cid = mm.group(1)
                    control_hits.setdefault(cid, []).append(f["id"])
                    sec = section_of(cid)
                    if sec:
                        section_hits.setdefault(sec, []).append(f["id"])
                mm = OWASP_RE.match(r)
                if mm:
                    top10_hits.setdefault(mm.group(1).upper(), []).append(f["id"])
            rows.append({
                "id": f["id"], "skill": skill, "severity": f.get("severity"),
                "top10": next((r for r in refs if r.startswith("OWASP-")), "-"),
                "asvs": ", ".join(r for r in refs if r.startswith("ASVS-")) or "-",
                "cwe": ", ".join(r for r in refs if r.startswith("CWE-")) or "-",
                "rule": (f.get("extra", {}).get("mapping", {}) or {}).get("rule", "-"),
                "why": (f.get("extra", {}).get("mapping", {}) or {}).get("matched_by", ""),
            })
        if changed and not a.dry_run:
            save(path, doc)
            changed_files += 1
        elif changed:
            print(f"[dry-run] would update {path}")

    # Section coverage
    coverage_by_skill = m.get("skill_coverage", {})
    section_rows = []
    not_assessed = []
    section_assessed = {}
    for sec, name in sections.items():
        assessed_by = sorted(s for s in completed_skills if sec in coverage_by_skill.get(s, []))
        scope_hit = any(v == sec[1:] or v.startswith(sec[1:] + ".") for v in verified_by_scope)
        section_assessed[sec] = bool(assessed_by or scope_hit)
        if sec in section_hits:
            status = "Failed"
        elif assessed_by or scope_hit:
            status = "Verified"
        else:
            status = "Not assessed"
            not_assessed.append(f"{sec} {name}")
        section_rows.append((sec, name, status, sorted(set(section_hits.get(sec, []))),
                             assessed_by + (["scope.checked"] if scope_hit and not assessed_by else [])))

    # Control coverage (only controls named in the catalogue or seen in findings)
    control_rows = []
    all_controls = dict(controls)
    for cid in control_hits:
        all_controls.setdefault(cid, {"level": "?", "name": "(not in catalogue; see ASVS 4.0.3)"})
    for cid in sorted(all_controls, key=lambda c: [int(x) if x.isdigit() else 0 for x in c.split(".")]):
        meta = all_controls[cid]
        lvl = meta.get("level", "?")
        if isinstance(lvl, int) and lvl > a.min_level and cid not in control_hits:
            continue
        sec = section_of(cid)
        if cid in control_hits:
            status = "Failed"
        elif cid in verified_by_scope or section_assessed.get(sec):
            status = "Verified"
        else:
            status = "Not assessed"
        control_rows.append((cid, lvl, meta["name"], status, sorted(set(control_hits.get(cid, [])))))

    # Markdown
    now = datetime.now(timezone.utc).isoformat()
    L = [f"## {SKILL} findings", "",
         f"Generated {now}. Findings files: {len(files)}. Mapped findings: {len(mapped)}. "
         f"Unmapped: {len(unmapped)}. Findings files updated: {changed_files}"
         + (" (dry-run)" if a.dry_run else "") + ".", ""]
    L += ["### OWASP Top 10 (2021) coverage", "", "| Category | Status | Linked findings |", "|---|---|---|"]
    top10_sections = m.get("top10_sections", {})
    for k, name in top10.items():
        ids = sorted(set(top10_hits.get(k, [])))
        assessed = any(section_assessed.get(sec) for sec in top10_sections.get(k, []))
        status = "Failed" if ids else ("Verified" if assessed else "Not assessed")
        L.append(f"| {k}:2021 {name} | {status} | {', '.join(ids) or '-'} |")
    L += ["", "### ASVS 4.0 coverage matrix (by section)", "",
          "| Section | Name | Status | Linked findings | Assessed by |", "|---|---|---|---|---|"]
    for sec, name, status, ids, by in section_rows:
        L.append(f"| {sec} | {name} | {status} | {', '.join(ids) or '-'} | {', '.join(by) or '-'} |")
    L += ["", f"### ASVS controls (level <= {a.min_level}, plus any control a finding names)", "",
          "| Control | Level | Name | Status | Linked findings |", "|---|---|---|---|---|"]
    for cid, lvl, name, status, ids in control_rows:
        L.append(f"| ASVS-{cid} | L{lvl} | {name} | {status} | {', '.join(ids) or '-'} |")
    L += ["", "### Per-finding mapping", "",
          "| Finding | Skill | Severity | OWASP Top 10 | ASVS | CWE | Rule | Matched by |",
          "|---|---|---|---|---|---|---|---|"]
    order = {k: i for i, k in enumerate(SEVERITIES)}
    for r in sorted(rows, key=lambda r: (order.get(r["severity"], 99), r["id"])):
        L.append(f"| {r['id']} | {r['skill']} | {r['severity']} | {r['top10']} | {r['asvs']} | {r['cwe']} | {r['rule']} | {r['why']} |")
    L += ["", "### Unmapped findings (no security standard applies, or the rule table needs a new entry)", ""]
    if unmapped:
        for skill, f in unmapped:
            L.append(f"- {f['id']} ({skill}) - {f.get('title')}")
    else:
        L.append("- none")
    L += ["", "### ASVS sections not assessed", ""]
    if not_assessed:
        L += [f"- {s}" for s in not_assessed]
    else:
        L.append("- none; every section has a completed skill or a scope.checked entry")
    L += ["", "### Not checked", "",
          "- Statuses come from audit/status/*.json and the presence of findings files; a skill that ran but did not write a status file is treated as completed.",
          "- 'Verified' means a covering skill completed without a failing finding; it is not a claim that every control in the section was individually tested. Check the skill's own scope.checked list.",
          "- ASVS levels 2 and 3 controls are listed only when a finding names them (raise --min-level to list more).", ""]
    text = "\n".join(L)

    # Own findings.json
    findings = []
    if not_assessed:
        findings.append({
            "id": f"{PREFIX}-001",
            "title": f"{len(not_assessed)} ASVS 4.0 sections were not assessed by any audit skill",
            "severity": "Info", "confidence": "confirmed",
            "location": {"file": "audit/findings", "symbol": "coverage matrix"},
            "evidence": "\n".join(not_assessed),
            "impact": "The audit cannot claim ASVS coverage for these areas; a reader could mistake silence for a pass. Rated Info because it is a gap in the audit, not in the product.",
            "remediation": "Run the skill that owns each section (see skill_coverage in scripts/mapping.json), or record a manual check in that skill's scope.checked as 'ASVS-x.y verified: <how>'.",
            "references": ["ASVS-1.1.2"], "tags": ["audit-coverage"],
        })
    if unmapped:
        findings.append({
            "id": f"{PREFIX}-002",
            "title": f"{len(unmapped)} findings carry no OWASP/ASVS/CWE reference",
            "severity": "Info", "confidence": "confirmed",
            "location": {"file": "audit/findings", "symbol": "unmapped"},
            "evidence": "\n".join(f"{f['id']} ({s}): {f.get('title')}" for s, f in unmapped),
            "impact": "These findings will appear in the report without industry-standard ids; if any is a security defect it is invisible in the coverage matrix.",
            "remediation": "Add a tag or a CWE to each finding (audit-finding-writer), or extend scripts/mapping.json rules with the missing pattern; non-security findings can stay unmapped but should carry a 'non-security' tag.",
            "references": [], "tags": ["non-security", "audit-coverage"],
        })
    summary = {k: 0 for k in SEVERITIES}
    for f in findings:
        summary[f["severity"]] += 1
    doc = {"skill": SKILL, "generated_at": now, "target": {"root": os.path.abspath(root), "commit": None},
           "stack": {}, "scope": {
               "checked": [f"{len(files)} findings files under {os.path.relpath(fdir, root)}",
                           f"{len(completed_skills)} completed skills counted toward Verified"],
               "not_checked": [{"item": "ASVS level 2/3 controls without findings",
                                "reason": f"listed only when named; run with --min-level 3 to see all"}]},
           "findings": findings, "summary": summary,
           "extra": {"sections_verified": sum(1 for r in section_rows if r[2] == "Verified"),
                     "sections_failed": sum(1 for r in section_rows if r[2] == "Failed"),
                     "sections_not_assessed": len(not_assessed),
                     "mapped": len(mapped), "unmapped": len(unmapped)}}

    if a.dry_run:
        print(text)
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(out_md)) or ".", exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(text)
    save(out_json, doc)
    save(os.path.join(root, "audit", "status", f"{SKILL}.json"),
         {"skill": SKILL, "status": "completed" if files else "skipped",
          "reason": None if files else "no findings files to map",
          "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat()})
    print(json.dumps({"findings_files": len(files), "mapped": len(mapped), "unmapped": len(unmapped),
                      "updated_files": changed_files, "sections_not_assessed": len(not_assessed),
                      "report": out_md, "findings": out_json}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
