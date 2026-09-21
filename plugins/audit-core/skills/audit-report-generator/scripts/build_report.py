#!/usr/bin/env python3
"""Assemble every audit/findings/*.json (plus status files, the OWASP/ASVS coverage
report and the GDPR / SOC 2 sections when present) into audit/audit-report.md.

Usage:
    python build_report.py [repo_root] [--out audit/audit-report.md] [--title "..."]
                           [--product "Name"] [--evidence-lines 4] [--docx] [--pdf]
                           [--accepted accepted.json] [--as-of YYYY-MM-DD]

Sections produced (in this order):
  1. Executive summary - GO / CONDITIONAL GO / NO-GO verdict and the top three risks in
     plain language (impact text, not CWE ids).
  2. Scope and methodology - per audit area: status, what was checked, what was not and why.
  3. Findings - sorted Critical -> High -> Medium -> Low -> Info, de-duplicated by
     root_cause_key (the highest-severity entry survives; merged ids and locations kept).
     Evidence is cut to --evidence-lines in the body; the full text goes to Appendix A.
  4. Pass/fail matrix by audit area.
  5. OWASP / ASVS coverage - embedded from audit/reports/audit-owasp-asvs-mapper.md.
  6. Compliance status - GDPR and SOC 2 sections embedded if those skills ran.
  7. Remediation plan - "Must fix before launch" (Critical + High) vs "Ticket for post-launch".
  8. Appendices - A: full evidence; B: scripts and tools used; C: excluded false positives;
     D: ASVS control detail (from the mapper); E: source files.
The section layout mirrors references/report-template.md; edit the template and this
script together.

Gathering, de-duplication, counts and the verdict come from audit-findings-rollup
(../audit-findings-rollup/scripts/findings_rollup.py). Verdict rule: NO-GO if any open Critical
or High finding (confidence != false-positive, not covered by a valid --accepted record);
CONDITIONAL GO if only Medium/Low are open; GO if nothing above Info. Failed, skipped, not-run
and limited-access areas, unreadable files and expired acceptances are printed as caveats after
the recommendation line; they never change the verdict.

Export: --docx / --pdf call pandoc if it is on PATH; if not, the script says so and
prints the command to run once pandoc is installed. Read-only against the audited
code: writes only audit/audit-report.md (+ .docx/.pdf) and audit/status/<skill>.json.
"""
import argparse
import glob
import importlib.util
import json
import os
import re
import shutil
import subprocess
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

SKILL = "audit-report-generator"
SEVERITIES = ["Critical", "High", "Medium", "Low", "Info"]
ORDER = {s: i for i, s in enumerate(SEVERITIES)}
WORDS_PER_PAGE = 450
MAPPER = "audit-owasp-asvs-mapper"
GDPR = "audit-gdpr-data-protection"
SOC2 = "audit-soc2-controls-evidence"


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


def area_name(skill):
    return skill.replace("audit-", "").replace("-", " ")


def location_str(f):
    loc = f.get("location") or {}
    s = loc.get("file", ".")
    if loc.get("line"):
        s += f":{loc['line']}"
    if loc.get("symbol"):
        s += f" ({loc['symbol']})"
    return s


def demote(md, levels=1):
    """Push every Markdown heading down so an embedded report nests under our section."""
    out = []
    for line in md.splitlines():
        m = re.match(r"^(#{1,6})\s", line)
        if m:
            line = "#" * min(6, len(m.group(1)) + levels) + line[len(m.group(1)):]
        out.append(line)
    return "\n".join(out)


# Plain-language sentence added after the rollup's reason, per verdict word.
PLAIN = {
    "NO-GO": ("Each is a launch blocker: an attacker or an ordinary user can cause data exposure, "
              "data loss or account takeover without special skill."),
    "CONDITIONAL GO": ("They should be ticketed with owners and dates before launch and fixed in the "
                       "first release cycle."),
    "GO": "Nothing above Info was recorded in the areas audited.",
}


def other_ids(f):
    """Ids merged into this finding, primary id excluded."""
    return [i for i in (f.get("extra") or {}).get("merged_ids", []) if i != f["id"]]


def all_locations(f):
    locs = (f.get("extra") or {}).get("locations")
    return [location_str({"location": loc}) for loc in locs] if locs else [location_str(f)]


def body_evidence(text, n):
    lines = str(text or "").strip().splitlines()
    cut = lines[:n]
    more = len(lines) - len(cut)
    return "\n".join(cut) + (f"\n... ({more} more lines in Appendix A)" if more > 0 else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--out", default=None)
    ap.add_argument("--title", default="Pre-production audit report")
    ap.add_argument("--product", default=None)
    ap.add_argument("--evidence-lines", type=int, default=4)
    ap.add_argument("--docx", action="store_true")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--accepted", default=None,
                    help="JSON list of risk-acceptance records (id, accepted_by, date, reason, optional expires)")
    ap.add_argument("--as-of", dest="as_of", default=None,
                    help="date acceptance expiry is checked against (default: today, UTC)")
    a = ap.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    root = a.root
    audit = os.path.join(root, "audit")
    out = a.out or os.path.join(audit, "audit-report.md")
    product = a.product or os.path.basename(os.path.abspath(root))

    # ---- gather ----------------------------------------------------------------
    rdoc = fr.rollup(root, acceptances=a.accepted, as_of=a.as_of)
    fl, sl = fr.load_findings(audit), fr.load_status(audit)
    docs = {os.path.splitext(os.path.basename(d["path"]))[0]: d["doc"] for d in fl["documents"]}  # by file stem
    docs_by_skill = {d["skill"]: d["doc"] for d in fl["documents"]}
    statuses = {k: s["raw"] for k, s in sl["skills"].items()}
    parse_errors = [f"{e['file']}: {e['error']}" for e in rdoc["parse_errors"]]
    stack = {}
    sp = os.path.join(audit, "stack.json")
    if os.path.exists(sp):
        try:
            stack = load(sp)
        except ValueError:
            pass
    if not stack:  # fall back to whatever the first findings file recorded
        stack = next((d.get("stack") for d in docs.values() if d.get("stack")), {})

    findings = rdoc["findings"]  # merged by root_cause_key and sorted; each carries skill, open, acceptance
    counts = rdoc["summary"]["deduplicated"]
    raw_total = sum(rdoc["summary"]["raw"].values())
    false_positives = rdoc["false_positives"]
    by_skill = {x["skill"]: x for x in rdoc["skills"]["by_skill"]}
    skills = sorted(set(by_skill) - {SKILL})
    failed_skills = [x["skill"] for x in rdoc["skills"]["failed"] if x["skill"] != SKILL]
    v, caveats = rdoc["verdict"]["verdict"], rdoc["verdict"]["caveats"]
    why = f"{rdoc['verdict']['reason']} {PLAIN[v]}"
    open_findings = [f for f in findings if f["open"]]
    now = datetime.now(timezone.utc)

    # ---- body ------------------------------------------------------------------
    L = [f"# {a.title}: {product}", "",
         f"Generated {now.strftime('%Y-%m-%d %H:%M UTC')}. Commit: "
         f"{next((d.get('target', {}).get('commit') for d in docs.values() if d.get('target', {}).get('commit')), 'n/a')}. "
         f"Stack: {stack.get('primary_backend') or 'n/a'} / {stack.get('primary_frontend') or 'n/a'}.", ""]

    L += ["## 1. Executive summary", "", f"**Recommendation: {v}.** {why}", "",
          "| Critical | High | Medium | Low | Info |", "|---|---|---|---|---|",
          "| " + " | ".join(str(counts[s]) for s in SEVERITIES) + " |", ""]
    if caveats:
        L += ["Caveats (the verdict covers only what was assessed):", ""] + [f"- {c}" for c in caveats] + [""]
    L += ["### Top three risks", ""]
    top = open_findings[:3]
    if top:
        for i, f in enumerate(top, 1):
            L.append(f"{i}. **{f['title']}** ({f['severity']}, {f['id']}). {f['impact']}")
    else:
        L.append("No risks above Info were found in the areas assessed.")
    L += ["", f"Audit areas run: {len(skills)}; completed: "
          f"{sum(1 for s in skills if statuses.get(s, {}).get('status', 'completed') == 'completed')}; "
          f"skipped: {sum(1 for s in skills if statuses.get(s, {}).get('status') == 'skipped')}; "
          f"failed: {len(failed_skills)}. Findings after de-duplication: {len(findings)} "
          f"(from {raw_total}; {len(false_positives)} false positives excluded, see Appendix C).", ""]

    L += ["## 2. Scope and methodology", "",
          "Each area was reviewed in two passes: an automated grep/script pass over the repository "
          "(scripts listed in Appendix B) followed by a manual trace of the highest-risk flows. "
          "The audited code was never modified; all artefacts live under `audit/`.", "",
          "| Audit area | Status | Checked | Not checked (reason) |", "|---|---|---|---|"]
    for s in skills:
        st = statuses.get(s, {})
        status = st.get("status") or ("completed" if s in docs_by_skill else "unknown")
        if st.get("reason"):
            status += f" - {st['reason']}"
        scope = docs_by_skill.get(s, {}).get("scope", {})
        checked = "; ".join(str(c) for c in scope.get("checked", [])) or "-"
        nc = "; ".join(f"{i.get('item')} ({i.get('reason')})" if isinstance(i, dict) else str(i)
                       for i in scope.get("not_checked", [])) or "-"
        L.append(f"| {area_name(s)} | {status} | {checked.replace('|', '/')} | {nc.replace('|', '/')} |")
    if parse_errors:
        L += ["", "Findings files that could not be parsed: " + "; ".join(parse_errors)]
    L.append("")

    L += ["## 3. Findings", "",
          "Sorted by severity. Evidence is abbreviated here; Appendix A has the full text. "
          "Findings sharing a root cause are merged (merged ids shown).", ""]
    for sev in SEVERITIES:
        group = [f for f in findings if f["severity"] == sev]
        if not group:
            continue
        L += [f"### {sev} ({len(group)})", ""]
        for f in group:
            merged = other_ids(f)
            locs = all_locations(f)
            accepted = "" if f["open"] else " (risk accepted, see section 7)"
            L += [f"#### [{sev}] {f['id']} - {f['title']}{accepted}",
                  f"- **Area:** {area_name(f['skill'])}",
                  f"- **Location:** `{location_str(f)}`" + (f" (+{len(locs) - 1} more, see Appendix A)" if len(locs) > 1 else ""),
                  f"- **Confidence:** {f.get('confidence', 'confirmed')}" + (f" - merged with {', '.join(merged)}" if merged else ""),
                  "- **Evidence:**", "", "```", body_evidence((f.get("extra") or {}).get("primary_evidence", f.get("evidence")), a.evidence_lines), "```", "",
                  f"- **Impact:** {f['impact']}",
                  f"- **Remediation:** {f['remediation']}",
                  f"- **Reference:** {', '.join(f.get('references', [])) or '-'}", ""]

    L += ["## 4. Pass/fail matrix by audit area", "",
          "| Audit area | Run status | Critical | High | Medium | Low | Info | Result |",
          "|---|---|---|---|---|---|---|---|"]
    for s in skills:
        st = statuses.get(s, {}).get("status") or ("completed" if s in docs_by_skill else "unknown")
        c = by_skill[s]["counts_rollup"]
        if st == "failed":
            result = "FAILED (skill error)"
        elif st == "skipped":
            result = "NOT RUN"
        elif c["Critical"] or c["High"]:
            result = "FAIL"
        elif c["Medium"] or c["Low"]:
            result = "WARN"
        else:
            result = "PASS"
        L.append(f"| {area_name(s)} | {st} | " + " | ".join(str(c[k]) for k in SEVERITIES) + f" | {result} |")
    L.append("")

    L += ["## 5. OWASP Top 10 / ASVS coverage", ""]
    mapper_md = read_text(os.path.join(audit, "reports", f"{MAPPER}.md"))
    if mapper_md:
        # keep the Top 10 table and the section matrix in the body; the rest goes to the appendix
        keep = re.split(r"\n### ASVS controls", mapper_md, maxsplit=1)[0]
        L += [demote(keep, 2), "", "Control-level detail and the per-finding mapping are in Appendix D.", ""]
    else:
        L += [f"`{MAPPER}` did not run; findings carry only the references their own skills assigned. "
              "Run it to obtain the coverage matrix and the list of ASVS controls not assessed.", ""]

    L += ["## 6. Compliance status", ""]
    for name, label in ((GDPR, "GDPR"), (SOC2, "SOC 2")):
        md = read_text(os.path.join(audit, "reports", f"{name}.md"))
        L += [f"### {label}", ""]
        if md:
            L += [demote(md, 3), ""]
        else:
            st = statuses.get(name, {}).get("status")
            L += [f"`{name}` " + (f"was {st}" + (f" ({statuses[name].get('reason')})" if statuses[name].get("reason") else "") if st else "did not run") + "; no compliance statement can be made for this framework.", ""]

    L += ["## 7. Remediation plan", "",
          "### Must fix before launch (Critical and High)", ""]
    blockers = [f for f in open_findings if f["severity"] in ("Critical", "High")]
    if blockers:
        L += ["| Priority | Id | Finding | Where | Fix summary |", "|---|---|---|---|---|"]
        for i, f in enumerate(blockers, 1):
            L.append(f"| {i} | {f['id']} | {f['title']} | `{location_str(f)}` | {f['remediation'].split('. ')[0].replace('|', '/')} |")
    else:
        L.append("None. No Critical or High findings are open.")
    if rdoc["risk_accepted"]:
        L += ["", "### Risk accepted (not blocking while the acceptance is valid)", "",
              "| Id | Severity | Finding | Accepted by | Date | Expires | Reason |", "|---|---|---|---|---|---|---|"]
        for r in rdoc["risk_accepted"]:
            rec = (r["acceptance"]["records"] or [{}])[0]
            L.append(f"| {r['id']} | {r['severity']} | {r['title']} | {rec.get('accepted_by', '-')} | {rec.get('date', '-')} | "
                     f"{rec.get('expires') or '-'} | {str(rec.get('reason', '-')).replace('|', '/')} |")
    L += ["", "### Ticket for post-launch (Medium and Low)", ""]
    later = [f for f in open_findings if f["severity"] in ("Medium", "Low")]
    if later:
        L += ["| Id | Severity | Finding | Suggested window |", "|---|---|---|---|"]
        for f in later:
            window = "first release after launch (30 days)" if f["severity"] == "Medium" else "next quarter"
            L.append(f"| {f['id']} | {f['severity']} | {f['title']} | {window} |")
    else:
        L.append("None.")
    info = [f for f in findings if f["severity"] == "Info"]
    if info:
        L += ["", "### Record only (Info)", ""] + [f"- {f['id']} - {f['title']}" for f in info]
    L.append("")

    body_words = len(" ".join(L).split())
    pages = body_words / WORDS_PER_PAGE

    # ---- appendices -----------------------------------------------------------
    L += ["---", "", "## Appendix A. Full evidence", ""]
    for f in findings:
        L += [f"### {f['id']} - {f['title']}", f"- Area: {area_name(f['skill'])}; severity {f['severity']}; confidence {f.get('confidence', 'confirmed')}"]
        for loc in all_locations(f):
            L.append(f"- Location: `{loc}`")
        L += ["", "```", str(f.get("evidence", "")).strip(), "```", ""]

    L += ["## Appendix B. Scripts and tools used", ""]
    any_tool = False
    for s in skills:
        st = statuses.get(s, {})
        tools = st.get("scripts") or st.get("tools") or []
        ev_dir = os.path.join(audit, "evidence", s)
        ev_files = sorted(os.path.relpath(p, root).replace(os.sep, "/") for p in glob.glob(os.path.join(ev_dir, "**", "*"), recursive=True) if os.path.isfile(p))
        if tools or ev_files:
            any_tool = True
            L.append(f"- **{area_name(s)}**: " + (", ".join(f"`{t}`" for t in tools) if tools else "scripts not recorded in status file")
                     + (f"; evidence: {', '.join(f'`{e}`' for e in ev_files[:20])}" + (" ..." if len(ev_files) > 20 else "") if ev_files else ""))
    if not any_tool:
        L.append("No status file listed scripts and no files were found under `audit/evidence/`. "
                 "Each skill used its own `scripts/` plus the shared audit skills (audit-stack-detection, audit-code-scan, "
                 "audit-finding-writer, audit-findings-rollup) per its SKILL.md.")
    L.append("")

    L += ["## Appendix C. Excluded false positives", ""]
    if false_positives:
        L += ["| Id | Area | Title | Why excluded |", "|---|---|---|---|"]
        for f in false_positives:
            L.append(f"| {f['id']} | {area_name(f['skill'])} | {f['title']} | {str(f.get('impact', '')).replace('|', '/')[:160]} |")
    else:
        L.append("None recorded.")
    L.append("")

    if mapper_md:
        rest = re.split(r"\n### ASVS controls", mapper_md, maxsplit=1)
        if len(rest) > 1:
            L += ["## Appendix D. ASVS control detail and per-finding mapping", "", demote("### ASVS controls" + rest[1], 1), ""]

    L += ["## Appendix E. Source files", ""]
    for s in sorted(docs):
        L.append(f"- `audit/findings/{s}.json` ({len(docs[s].get('findings', []))} findings, generated {docs[s].get('generated_at', 'n/a')})")
    for s in sorted(statuses):
        L.append(f"- `audit/status/{s}.json` ({statuses[s].get('status')})")
    L.append("")

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))

    # ---- export ---------------------------------------------------------------
    exports = {}
    if a.docx or a.pdf:
        pandoc = shutil.which("pandoc")
        for fmt, flag in (("docx", a.docx), ("pdf", a.pdf)):
            if not flag:
                continue
            target = os.path.splitext(out)[0] + "." + fmt
            cmd = ["pandoc", out, "-o", target, "--toc", "--from", "gfm"]
            if fmt == "pdf":
                cmd += ["--pdf-engine=xelatex"]
            if not pandoc:
                exports[fmt] = "pandoc not found on PATH; install it (https://pandoc.org/installing.html) and run: " + " ".join(cmd)
                continue
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                exports[fmt] = target
            except (subprocess.CalledProcessError, OSError) as e:
                exports[fmt] = f"pandoc failed: {getattr(e, 'stderr', e)}"

    os.makedirs(os.path.join(audit, "status"), exist_ok=True)
    with open(os.path.join(audit, "status", f"{SKILL}.json"), "w", encoding="utf-8") as fh:
        json.dump({"skill": SKILL, "status": "completed" if docs else "skipped",
                   "reason": None if docs else "no findings files under audit/findings",
                   "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
                   "scripts": ["scripts/build_report.py"], "exports": exports}, fh, indent=2)

    print(json.dumps({"report": out, "verdict": v, "counts": counts, "findings": len(findings),
                      "merged": rdoc["summary"]["merged"], "false_positives": len(false_positives),
                      "open": rdoc["summary"]["open"], "caveats": caveats, "parse_errors": rdoc["parse_errors"],
                      "areas": len(skills), "body_pages_estimate": round(pages, 1),
                      "body_warning": "body exceeds ~15 pages; lower --evidence-lines or split findings" if pages > 15 else None,
                      "exports": exports}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
