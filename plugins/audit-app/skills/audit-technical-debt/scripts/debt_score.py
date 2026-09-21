#!/usr/bin/env python3
"""Join the debt evidence and the other audit skills' findings into one ranked
debt inventory, a churn-vs-complexity hotspot list, a pay-down roadmap, a
maintainability score, and draft DEBT findings for launch risks.

Usage:
    python debt_score.py <repo_root> --evidence audit/evidence/audit-technical-debt
                         [--findings-dir audit/findings] [--history FILE | --no-git] [--as-of YYYY-MM-DD]
                         [--out debt.json] [--md debt.md] [--candidates-dir DIR]

Evidence files read from --evidence when present (each is optional; a missing one is
listed under not_checked and its score input is dropped with its weight):
  complexity.json (complexity.py)  churn.json (churn.py)        todos.json (todo_age.py)
  duplicates.json (duplicates.py)  dead_code.json (dead_code.py) eol.json (eol_check.py)
  suppressions.json (suppressions.py) docs.json (docs_check.py) hits.json
  ($AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py with scripts/patterns/<stack>.json: DEPR-* = deprecated
  API, MIX-<family>-<variant> = inconsistent pattern)

Consumed findings (audit/findings/*.json, except this skill's own file, loaded with
audit-findings-rollup's load_findings: underscore-prefixed files are ignored and unreadable
files are listed under not_checked): mapped into debt items BY ID PREFIX and never re-detected
or re-flagged:
  TEST->test-debt  DEP->dependency  FEBP->frontend-practices  ORM->data-access
  ASYNC->async-di  LEAK/FELEAK->resource-leak  ARCH->design
  (also DB->schema, API->api-contract, PERF->performance, LOG->observability,
   TIME->datetime, A11Y->accessibility-i18n, INFRA->infrastructure, LIC->licensing)
Security and compliance prefixes (AUTHZ, INJ, SEC, HDR, XSS, CAUTH, TENANT, RACE, BIZ, GDPR,
SOC2, PII, ...) are counted but not turned into debt: they are defects owned elsewhere.
A native item at the same file:line as a consumed finding, or an EOL item for a package a
DEP finding already names, is dropped in favour of the consumed item.

Ranking (details and rationale: references/scoring-and-prioritisation.md):
  impact 1-10 per category rule; effort S/M/L/XL = 1/1.5/2/3 points;
  change multiplier = 1 + commits touching the item's function (or file) in the churn
  window / the most commits any file received (1.0 without history or for repo-wide items);
  priority = impact x multiplier / effort points.
  Buckets: quick-win = S, or M with impact >= 6; long-term = XL, or L with impact <= 4;
  next-quarter = the rest.
Maintainability score 0-100 = weighted mean of available sub-scores:
  complexity 20, hotspots 15, duplication 10, dead code 5, dependency/runtime currency 15,
  hygiene (TODO/suppressions/commented-out/deprecated/mixed) 10, tests 10, docs 5,
  consumed quality findings (ORM/ASYNC/LEAK/FELEAK/FEBP/ARCH) 10.
Launch-risk candidates (--candidates-dir writes one DEBT-NNN.json per candidate, ready for
`$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py add --from`): EOL runtime/framework/security package with no DEP finding;
top-3 hotspot with CC >= 50 that TEST findings or the file list show is untested; security
analyzer suppressions; security-related FIXME/HACK. All are confidence "likely" until
confirmed by reading the code. Read-only against the audited repo.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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


def _load_sibling(skill, script, name):
    """Load an atomic skill's module by file path under a unique name (a bare import could pick up a
    same-named script from another skill's folder)."""
    path = os.path.join(_SKILLS, skill, "scripts", script)
    if not os.path.exists(path):
        sys.exit("%s must be reachable from this skill (audit-core plugin or sibling layout; expected %s)" % (skill, path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


githist = _load_sibling("audit-git-history", "githist.py", "audit_git_history_githist")
fr = _load_sibling("audit-findings-rollup", "findings_rollup.py", "audit_findings_rollup")

SELF = "audit-technical-debt"
EFFORT_POINTS = {"S": 1.0, "M": 1.5, "L": 2.0, "XL": 3.0}
SEV_IMPACT = {"Critical": 10, "High": 8, "Medium": 5, "Low": 3, "Info": 1}
HINT_IMPACT = {"Info": 1, "Low": 2, "Medium": 4, "High": 6, "Critical": 8}
PREFIX_MAP = {
    "TEST": ("test-debt", "M", "audit-test-coverage-and-ci"),
    "DEP": ("dependency", "S", "audit-dependency-vulnerabilities"),
    "FEBP": ("frontend-practices", "M", "audit-frontend-best-practices"),
    "ORM": ("data-access", "M", "audit-orm-query-and-data-access"),
    "ASYNC": ("async-di", "M", "audit-async-and-dependency-injection"),
    "LEAK": ("resource-leak", "M", "audit-backend-resource-leak"),
    "FELEAK": ("resource-leak", "S", "audit-frontend-memory-leak"),
    "ARCH": ("design", "XL", "audit-system-design"),
    "DB": ("schema", "L", "audit-db-schema"),
    "API": ("api-contract", "M", "audit-api-contract"),
    "PERF": ("performance", "M", "audit-performance-and-scalability"),
    "LOG": ("observability", "M", "audit-logging-and-observability"),
    "TIME": ("datetime", "M", "audit-datetime-and-timezone"),
    "A11Y": ("accessibility-i18n", "M", "audit-accessibility-and-i18n"),
    "INFRA": ("infrastructure", "M", "audit-infra-and-deployment"),
    "LIC": ("licensing", "M", "audit-licensing-and-compliance"),
}
PRIMARY_SKILLS = ["audit-test-coverage-and-ci", "audit-frontend-best-practices", "audit-orm-query-and-data-access",
                  "audit-async-and-dependency-injection", "audit-backend-resource-leak", "audit-frontend-memory-leak",
                  "audit-dependency-vulnerabilities", "audit-system-design"]
QUALITY_PREFIXES = {"ORM", "ASYNC", "LEAK", "FELEAK", "FEBP", "ARCH"}
WEIGHTS = {"complexity": 20, "hotspots": 15, "duplication": 10, "dead_code": 5, "currency": 15, "hygiene": 10,
           "tests": 10, "docs": 5, "quality_findings": 10}
BACKEND_PRODUCTS = {"dotnet", "dotnet-framework", "nodejs", "python", "java", "spring-boot", "django", "express"}


def load(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--findings-dir")
    ap.add_argument("--out")
    ap.add_argument("--md")
    ap.add_argument("--candidates-dir")
    ap.add_argument("--hotspot-top", type=int, default=10)
    githist.add_history_args(ap)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    fdir = a.findings_dir or os.path.join(root, "audit", "findings")
    hist = githist.History(root, a.history, a.no_git)
    as_of = githist.resolve_as_of(hist, a.as_of)

    names = ["complexity", "churn", "todos", "duplicates", "dead_code", "eol", "suppressions", "docs", "hits"]
    ev = {n: load(os.path.join(a.evidence, n + ".json")) for n in names}
    not_checked = [{"item": n + ".json", "reason": "evidence file missing; its category is absent from the inventory "
                                                  "and its score input is dropped"} for n in names if ev[n] is None]
    if hist.mode == "none":
        not_checked.append({"item": "ages", "reason": "no history (" + hist.reason + "); age column is empty"})

    # ------------------------------------------------------------------ churn lookups
    churn = ev["churn"] or {}
    file_commits = {f["path"]: f["commits"] for f in churn.get("files", [])}
    fn_commits = {(f["file"], f["name"]): f["commits"] for f in churn.get("functions", [])}
    max_commits = max([churn.get("max_file_commits") or 0] + [1]) if churn else 0
    hotspots = churn.get("hotspots", [])
    hot_rank = {}
    for h in hotspots:
        key = (h["file"], h["name"] or h.get("hottest_function"))
        hot_rank.setdefault(key, h)

    def multiplier(file=None, fn=None):
        if not max_commits or not file:
            return 1.0
        c = fn_commits.get((file, fn)) if fn else None
        if c is None:
            c = file_commits.get(file, 0)
        return round(1.0 + min(c, max_commits) / float(max_commits), 3)

    age_cache = {}

    def age_days(file):
        if not file or file == "." or hist.mode == "none":
            return None
        if file not in age_cache:
            lc = hist.last_change(file)
            age_cache[file] = (as_of - lc["date"]).days if lc and lc.get("date") else None
        return age_cache[file]

    items = []

    def add(category, title, file, line=None, symbol=None, impact=1, effort="S", mult=None, age=None, source="",
            notes="", launch_risk=False, finding_ref=None, extra=None):
        it = {"category": category, "item": title, "file": file, "line": line, "symbol": symbol,
              "age_days": age if age is not None else age_days(file), "impact": int(clamp(round(impact), 1, 10)),
              "effort": effort, "multiplier": mult if mult is not None else multiplier(file, symbol),
              "source": source, "notes": notes, "launch_risk": launch_risk, "finding_ref": finding_ref}
        if extra:
            it.update(extra)
        items.append(it)
        return it

    # ------------------------------------------------------------------ consumed findings
    consumed = {"by_prefix": {}, "not_debt": {}, "files": [], "missing_skills": []}
    consumed_items = []
    consumed_locs = {}
    test_text = []
    present_skills = set()
    # Loading is audit-findings-rollup's (underscore files ignored, unreadable files reported, not fatal).
    fl = fr.load_findings(fdir, exclude_skills={SELF})
    present_skills = {s["skill"] for s in fl["sources"]}
    consumed["files"] = [os.path.basename(s["file"]) for s in fl["sources"]]
    for e in fl["parse_errors"]:
        not_checked.append({"item": e["file"], "reason": "findings file unreadable: " + e["error"]})
    for f in fl["findings"]:
        if f.get("confidence") == "false-positive":
            continue
        skill = f["skill"]
        prefix = str(f.get("id", "")).split("-")[0]
        if prefix not in PREFIX_MAP:
            consumed["not_debt"][prefix] = consumed["not_debt"].get(prefix, 0) + 1
            continue
        cat, default_effort, _ = PREFIX_MAP[prefix]
        eff = next((t.split(":", 1)[1] for t in f.get("tags", []) if str(t).startswith("effort:")), default_effort)
        if eff not in EFFORT_POINTS:
            eff = default_effort
        loc = f.get("location") or {}
        sev = f.get("severity", "Info")
        entry = consumed["by_prefix"].setdefault(prefix, {"skill": skill, "category": cat, "count": 0})
        entry["count"] += 1
        it = add(cat, "%s: %s" % (f.get("id"), f.get("title")), loc.get("file"), loc.get("line"), loc.get("symbol"),
                 SEV_IMPACT.get(sev, 1), eff, source=skill, launch_risk=sev in ("Critical", "High"),
                 finding_ref=f.get("id"), notes="consumed from %s; not re-flagged" % skill,
                 extra={"severity": sev, "_finding": f})
        consumed_items.append(it)
        if loc.get("file") and loc.get("line"):
            consumed_locs[(loc["file"], loc["line"])] = it
        if prefix == "TEST":
            test_text.append(" ".join(str(f.get(k, "")) for k in ("title", "evidence", "impact")) + " " + str(loc.get("file")))
    consumed["missing_skills"] = [s for s in PRIMARY_SKILLS if s not in present_skills]
    for s in consumed["missing_skills"]:
        not_checked.append({"item": s, "reason": "no audit/findings/%s.json; its issues are not re-detected here - "
                                                 "run it and re-score" % s})

    def consumed_at(file, line):
        return consumed_locs.get((file, line))

    # ------------------------------------------------------------------ hotspots and complexity
    comp = ev["complexity"] or {}
    thr = (comp.get("thresholds") or {}).get("cc", 15)
    fn_lines_thr = (comp.get("thresholds") or {}).get("fn_lines", 80)
    test_files_exist = any(re.search(r"(Tests?\.cs|\.spec\.|\.test\.|_test\.py|test_\w+\.py|Test\.java)$", f["file"])
                           for f in comp.get("files", []))
    hot_items = {}
    for f in comp.get("files", []):
        for fn in f["functions"]:
            if fn["cyclomatic"] <= thr and fn["length"] <= fn_lines_thr:
                continue
            h = hot_rank.get((f["file"], fn["name"]))
            commits = h["commits"] if h else 0
            is_hot = bool(h and h["rank"] <= a.hotspot_top and commits >= 2 and fn["cyclomatic"] > thr)
            eff = "XL" if fn["length"] > 600 or fn["cyclomatic"] > 150 else ("L" if fn["length"] > 150 or fn["cyclomatic"] > 50 else "M")
            if is_hot:
                impact = 6 + min(3, fn["cyclomatic"] // 25) + (1 if fn["length"] > 150 else 0)
                title = "%s: CC %d, %d lines, changed in %d of the last %d commits (hotspot #%d)" % (
                    fn["name"], fn["cyclomatic"], fn["length"], commits, churn.get("commits_in_window", 0), h["rank"])
                cat = "hotspot"
            else:
                impact = (6 if fn["cyclomatic"] > 50 else 4 if fn["cyclomatic"] > 20 else 2) + (1 if fn["length"] > 150 else 0)
                title = "%s: CC %d, cognitive %d, %d lines" % (fn["name"], fn["cyclomatic"], fn["cognitive"], fn["length"])
                cat = "complexity"
            stem = os.path.splitext(os.path.basename(f["file"]))[0]
            untested = (not test_files_exist) or any(stem in t or fn["name"] in t for t in test_text)
            it = add(cat, title, f["file"], fn["start"], fn["name"], impact, eff, source="complexity.py+churn.py",
                     extra={"cyclomatic": fn["cyclomatic"], "length": fn["length"], "end": fn["end"], "commits": commits,
                            "hot_rank": h["rank"] if h else None, "untested": untested})
            if is_hot:
                it["notes"] = ("first slice (quick win): characterization tests around %s, then extract one step at a "
                               "time behind them" % fn["name"])
                hot_items[(f["file"], fn["name"])] = it
    for b in comp.get("large_files", []):
        if b["lines"] > 1000:
            add("oversized-file", "%s is %d lines" % (os.path.basename(b["file"]), b["lines"]), b["file"], None, None,
                5 if b["lines"] > 2000 else 3, "L", source="complexity.py")

    def inside_hot(file, start, end):
        for (hf, _), it in hot_items.items():
            if hf == file and it["line"] <= start and end <= it["end"]:
                return it
        return None

    # ------------------------------------------------------------------ duplicates
    dup = ev["duplicates"] or {}
    for c in dup.get("clones", []):
        occ = c["occurrences"]
        host = [inside_hot(o["file"], o["start"], o["end"]) for o in occ]
        if host and all(host) and all(h is host[0] for h in host):
            host[0]["notes"] += "; contains a %d-line internal duplicate (%s)" % (
                c["lines"], ", ".join("%d-%d" % (o["start"], o["end"]) for o in occ))
            continue
        o0 = occ[0]
        if c.get("function_clone"):
            fns = [o["function"] for o in occ if o.get("function")]
            title = "Near-identical functions %s (%d matching lines)" % (" and ".join(dict.fromkeys(fns)), c["lines"])
        else:
            title = "Duplicated %d-line block in %d places" % (c["lines"], len(occ))
        impact = 2 + min(3, c["lines"] / 10.0) + (1 if c.get("function_clone") else 0) \
            + (1 if any(hot_rank.get((o["file"], o.get("function"))) for o in occ) else 0) \
            - (1 if all(o.get("test_code") for o in occ) else 0)
        eff = "S" if c["lines"] <= 30 and len(occ) == 2 else "M"
        mult = max(multiplier(o["file"], o.get("function")) for o in occ)
        add("duplication", title, o0["file"], o0["start"], o0.get("function"), impact, eff, mult=mult, source="duplicates.py",
            notes="also at " + ", ".join("%s:%d" % (o["file"], o["start"]) for o in occ[1:]))

    # ------------------------------------------------------------------ dead code
    dead = ev["dead_code"] or {}
    for u in dead.get("unreferenced_files", []):
        add("dead-code", "Unreferenced module %s (%s)" % (os.path.basename(u["file"]), ", ".join(u["symbols"][:4])),
            u["file"], u.get("line"), None, 3, "S", source="dead_code.py", notes=u.get("reason", "") + "; heuristic - confirm")
    for u in dead.get("unreferenced_symbols", []):
        add("dead-code", "Unreferenced %s %s" % (u["kind"], u["symbol"]), u["file"], u["line"], u["symbol"], 1, "S",
            source="dead_code.py", notes="heuristic - confirm")
    for u in dead.get("unreachable", []):
        add("unreachable-code", "Unreachable statement after %s" % u["after"], u["file"], u["line"], None, 2, "S",
            source="dead_code.py")
    for u in dead.get("orphan_projects", []):
        add("dead-code", "Project not in any solution: %s" % os.path.basename(u["file"]), u["file"], None, None, 2, "S",
            source="dead_code.py")

    # ------------------------------------------------------------------ TODOs and commented-out code
    todos = ev["todos"] or {}
    for t in todos.get("todos", []):
        age = t.get("age_days")
        impact = {"TODO": 1, "FIXME": 2}.get(t["marker"], 3) + (1 if age and age > 365 else 0) \
            + (1 if age and age > 1095 else 0) + (2 if t.get("security_related") else 0)
        it = add("todo", "%s: %s" % (t["marker"], t["text"][:90]), t["file"], t["line"], None, impact,
                 "M" if t["marker"] in ("HACK", "XXX") else "S", age=age if age is not None else -1, source="todo_age.py",
                 notes=("owner %s" % t["owner"] if t.get("owner") else "") + (" ticket %s" % t["ticket"] if t.get("ticket") else ""))
        if age is None:
            it["age_days"] = None
        if t.get("security_related") and (t["marker"] != "TODO" or (age or 0) > 365):
            it["launch_risk"] = True
            it["candidate"] = "security-todo"
    for b in todos.get("commented_code", []):
        add("commented-out-code", "%d commented-out lines" % b["lines"], b["file"], b["start"], None,
            1 + (1 if b["lines"] >= 10 else 0), "S", age=b.get("age_days"), source="todo_age.py", notes=b.get("sample", "")[:80])

    # ------------------------------------------------------------------ suppressions (grouped per tool+rule)
    sup = ev["suppressions"] or {}
    groups = {}
    for s in sup.get("items", []):
        if s["kind"] == "coverage":
            continue
        key = (s["tool"], ",".join(s["rules"]) or "(all)")
        groups.setdefault(key, []).append(s)
    for (tool, rule), rows in groups.items():
        sec = any(r["security_related"] for r in rows)
        blanket = any(r["blanket"] for r in rows)
        project = any(r["kind"] in ("project", "file") for r in rows)
        impact = 6 if sec else 3 if (blanket or project) else 1
        impact += 1 if len(rows) >= 10 else 0
        r0 = rows[0]
        it = add("suppression", "%s suppression of %s (%d place%s%s)" % (tool, rule, len(rows), "" if len(rows) == 1 else "s",
                                                                       ", no justification" if not any(r["justification"] for r in rows) else ""),
                 r0["file"], r0["line"], None, impact, "M" if sec else "S", source="suppressions.py",
                 notes="deprecation-related: see deprecated-api items" if any(r["deprecation_related"] for r in rows) else "")
        if sec:
            it["launch_risk"] = True
            it["candidate"] = "security-suppression"

    # ------------------------------------------------------------------ EOL
    eol = ev["eol"] or {}
    if eol.get("stale_table"):
        not_checked.append({"item": "EOL table freshness", "reason": "references/eol-dates.json is %s days old; refresh before trusting"
                                                                  % eol.get("table_age_days")})
    for e in eol.get("items", []):
        if e["status"] not in ("eol", "eol-soon"):
            continue
        linked = next((ci for ci in consumed_items if ci["category"] == "dependency" and (
            e["product"].lower() in json.dumps(ci["_finding"]).lower())), None)
        if e["status"] == "eol":
            impact = 4 if e["floor"] else 8 + (1 if e["security_sensitive"] or e["kind"] == "runtime" else 0)
        else:
            impact = 6 if (e.get("days_to_eol") or 999) <= 90 else 5
        eff = "L" if e["kind"] in ("runtime", "framework") or e["security_sensitive"] else "M"
        title = "%s %s %s (EOL %s)%s" % (e["label"], e["declared"], "is past end-of-life" if e["status"] == "eol" else "reaches end-of-life soon",
                                         e["eol"], "; successor: " + e["successor"] if e.get("successor") else "")
        it = add("eol-" + e["kind"], title, e["file"], e["line"], e["product"], impact, eff, source="eol_check.py",
                 extra={"eol": e})
        if linked:
            it["finding_ref"] = linked["finding_ref"]
            it["notes"] = "covered by %s; no new finding" % linked["finding_ref"]
        elif e["status"] == "eol" and not e["floor"]:
            it["launch_risk"] = True
            it["candidate"] = "eol"
        elif e["status"] == "eol-soon" and (e.get("days_to_eol") or 999) <= 90:
            it["launch_risk"] = True
            it["candidate"] = "eol-soon"

    # ------------------------------------------------------------------ deprecated APIs and inconsistent patterns
    hits = (ev["hits"] or {}).get("hits", [])
    depr, mix = {}, {}
    for h in hits:
        if consumed_at(h["file"], h["line"]):
            continue
        pid = h["pattern_id"]
        if pid.startswith("DEPR-"):
            depr.setdefault(pid, []).append(h)
        elif pid.startswith("MIX-"):
            parts = pid.split("-", 2)
            if len(parts) == 3:
                mix.setdefault(parts[1], {}).setdefault(parts[2], []).append(h)
    for pid, rows in depr.items():
        r0 = rows[0]
        impact = HINT_IMPACT.get(r0.get("severity_hint"), 2) + (1 if len(rows) >= 10 else 0)
        eff = "S" if len(rows) <= 5 else "M" if len(rows) < 30 else "L"
        mult = max(multiplier(r["file"]) for r in rows)
        add("deprecated-api", "%s (%d use%s)" % (r0["description"], len(rows), "" if len(rows) == 1 else "s"), r0["file"],
            r0["line"], None, impact, eff, mult=mult, source="grep_scan.py:" + pid,
            notes="also " + ", ".join("%s:%d" % (r["file"], r["line"]) for r in rows[1:4]) if len(rows) > 1 else "")
    for fam, variants in mix.items():
        if len(variants) < 2:
            continue
        total = sum(len(v) for v in variants.values())
        minority = min(variants.items(), key=lambda kv: len(kv[1]))
        add("inconsistent-pattern", "Mixed %s approaches: %s" % (fam.lower(), ", ".join("%s (%d)" % (k.lower(), len(v))
                                                                                     for k, v in sorted(variants.items()))),
            minority[1][0]["file"], minority[1][0]["line"], None, 3 + (1 if len(variants) >= 3 else 0),
            "M" if total <= 20 else "L", mult=1.0, source="grep_scan.py:MIX-" + fam)

    # ------------------------------------------------------------------ docs
    docs = ev["docs"] or {}
    for c in docs.get("checks", []):
        spec = {("readme", "missing"): (4, "M"), ("readme", "partial"): (2, "S"), ("readme-fresh", "stale"): (2, "S"),
                ("adr", "missing"): (1, "M"), ("api-docs", "missing"): (2, "M"), ("runbook", "missing"): (3, "M"),
                ("changelog", "missing"): (1, "S"), ("contributing", "missing"): (1, "S"),
                ("env-example", "missing"): (2, "S")}.get((c["id"], c["status"]))
        if spec:
            add("docs", "%s %s%s" % (c["id"], c["status"], ": " + c["detail"] if c.get("detail") else ""),
                c.get("path") or ".", None, None, spec[0], spec[1], mult=1.0, source="docs_check.py",
                age=c.get("age_days"))
    if docs.get("dangling_references"):
        d = docs["dangling_references"]
        add("docs", "Docs reference %d path%s that no longer exist: %s" % (len(d), "" if len(d) == 1 else "s",
                                                                         ", ".join(x["reference"] for x in d[:5])),
            d[0]["doc"], d[0]["line"], None, 2, "S", mult=1.0, source="docs_check.py")

    # ------------------------------------------------------------------ dedupe native vs consumed
    final = []
    for it in items:
        if it["source"] and not it.get("finding_ref"):
            c = consumed_at(it["file"], it["line"])
            if c:
                c["notes"] += "; also detected by " + it["source"]
                continue
        final.append(it)
    items = final

    # ------------------------------------------------------------------ priority, buckets, ids
    for it in items:
        pts = EFFORT_POINTS[it["effort"]]
        it["priority"] = round(it["impact"] * it["multiplier"] / pts, 2)
        if it["effort"] == "S" or (it["effort"] == "M" and it["impact"] >= 6):
            it["bucket"] = "quick-win"
        elif it["effort"] == "XL" or (it["effort"] == "L" and it["impact"] <= 4):
            it["bucket"] = "long-term"
        else:
            it["bucket"] = "next-quarter"
    items.sort(key=lambda x: (-x["priority"], -x["impact"], x["file"] or ""))
    for n, it in enumerate(items, 1):
        it["id"] = "TD-%03d" % n
        it["rank"] = n

    # ------------------------------------------------------------------ launch-risk candidates
    cands = []
    for it in items:
        kind = it.get("candidate")
        if it["category"] == "hotspot" and it.get("hot_rank") and it["hot_rank"] <= 3 and it["cyclomatic"] >= 50 and it["untested"]:
            kind = "hotspot"
        if not kind or it.get("finding_ref"):
            continue
        loc = {"file": it["file"]}
        if it.get("line"):
            loc["line"] = it["line"]
        if it.get("symbol"):
            loc["symbol"] = it["symbol"]
        if kind == "eol":
            e = it["eol"]
            sev = "High" if (e["kind"] == "runtime" or e["security_sensitive"] or e["product"] in BACKEND_PRODUCTS) else "Medium"
            c = {"title": "%s %s is past end-of-life and receives no security fixes" % (e["label"], e["declared"]),
                 "severity": sev, "evidence": "%s:%s: %s\neol_check.py: cycle %s, EOL %s (%d days ago), table as of %s" % (
                     e["file"], e["line"], e["evidence"], e["cycle"], e["eol"], e["days_past_eol"], eol.get("table_as_of")),
                 "impact": "Vulnerabilities found in %s from now on will not be patched; the product ships with a component "
                           "nobody maintains%s." % (e["label"], ", in the authentication path" if e["security_sensitive"] else ""),
                 "remediation": "Plan the migration to %s; until then pin the last version, watch advisories, and record the "
                                "accepted risk with an owner and a date." % (e.get("successor") or "a supported version"),
                 "references": ["CWE-1104", "ASVS-14.2.1", "OWASP-A06:2021"], "tags": ["technical-debt", "eol", e["product"]],
                 "root_cause_key": "eol:%s@%s" % (e["product"], e["cycle"])}
        elif kind == "eol-soon":
            e = it["eol"]
            c = {"title": "%s %s reaches end-of-life on %s" % (e["label"], e["declared"], e["eol"]), "severity": "Low",
                 "evidence": "%s:%s: %s" % (e["file"], e["line"], e["evidence"]),
                 "impact": "Within three months the platform stops receiving security fixes unless upgraded.",
                 "remediation": "Schedule the upgrade to %s before %s." % (e.get("successor") or "a supported version", e["eol"]),
                 "references": ["CWE-1104", "OWASP-A06:2021"], "tags": ["technical-debt", "eol-soon"],
                 "root_cause_key": "eol:%s@%s" % (e["product"], e["cycle"])}
        elif kind == "hotspot":
            c = {"title": "%s is a %d-line, CC %d function changed in %d of the last %d commits with no tests" % (
                it["symbol"], it["length"], it["cyclomatic"], it["commits"], churn.get("commits_in_window", 0)),
                 "severity": "Medium",
                 "evidence": "complexity.py: %s:%d-%d cyclomatic=%d length=%d\nchurn.py: hotspot #%d, %d commits in window" % (
                     it["file"], it["line"], it["end"], it["cyclomatic"], it["length"], it["hot_rank"], it["commits"]),
                 "impact": "Nearly every recent change lands in this one function, and nothing checks it automatically, so the "
                           "next change is likely to break an unrelated branch (tax, discount, stock) without anyone noticing "
                           "before customers do.",
                 "remediation": "Before further feature work: add characterization tests that pin current outputs for "
                                "representative inputs, then extract one step at a time (validation, pricing, tax, FX, "
                                "allocation) into separately tested methods; stop adding branches to %s." % it["symbol"],
                 "references": ["CWE-1121", "CWE-1120"], "tags": ["technical-debt", "hotspot"],
                 "root_cause_key": "hotspot:%s:%s" % (it["file"], it["symbol"])}
        elif kind == "security-suppression":
            c = {"title": "Security analyzer rule suppressed: %s" % it["item"], "severity": "Medium",
                 "evidence": "suppressions.py: %s:%s" % (it["file"], it["line"]),
                 "impact": "A security check that would flag this code has been silenced, so the defect it guards against "
                           "can ship unnoticed.",
                 "remediation": "Remove the suppression and fix the flagged code, or document the justification and have a "
                                "security owner approve it.",
                 "references": ["CWE-1127"], "tags": ["technical-debt", "suppression"],
                 "root_cause_key": "suppression:%s:%s" % (it["file"], it["line"])}
        else:
            c = {"title": "Security-related debt marker left in code: %s" % it["item"][:80], "severity": "Low",
                 "evidence": "todo_age.py: %s:%s (age %s days)" % (it["file"], it["line"], it["age_days"]),
                 "impact": "A known security shortcut is documented only in a comment and has no owner or deadline.",
                 "remediation": "Turn the comment into a tracked ticket with an owner, fix it before launch if it affects "
                                "authentication, tenancy or payments, then delete the marker.",
                 "references": ["CWE-546"], "tags": ["technical-debt", "todo"],
                 "root_cause_key": "todo:%s:%s" % (it["file"], it["line"])}
        c.update({"confidence": "likely", "location": loc, "inventory_id": it["id"]})
        cands.append(c)
    sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
    cands.sort(key=lambda c: sev_order[c["severity"]])
    for n, c in enumerate(cands, 1):
        c["id"] = "DEBT-%03d" % n
        for it in items:
            if it["id"] == c["inventory_id"]:
                it["finding_ref"] = c["id"]
                it["launch_risk"] = True
    if a.candidates_dir:
        os.makedirs(a.candidates_dir, exist_ok=True)
        for c in cands:
            body = {k: v for k, v in c.items() if k != "inventory_id"}
            with open(os.path.join(a.candidates_dir, c["id"] + ".json"), "w", encoding="utf-8") as fh:
                json.dump(body, fh, indent=2)

    # ------------------------------------------------------------------ maintainability score
    comps = []
    kloc = max(1.0, ((comp.get("totals") or {}).get("code_lines") or 0) / 1000.0)

    def component(name, measure, sub):
        comps.append({"input": name, "measure": measure, "sub_score": None if sub is None else round(clamp(sub), 1),
                      "weight": WEIGHTS[name]})

    if comp:
        share = (comp.get("totals") or {}).get("complex_function_line_share", 0.0)
        component("complexity", "%.0f%% of function lines are in functions with CC > %d" % (share * 100, thr), 100 - 150 * share)
    else:
        component("complexity", "complexity.json missing", None)
    if churn and churn.get("history", {}).get("mode") != "none" and comp:
        complex_files = {f["file"] for f in comp.get("files", []) if any(fn["cyclomatic"] > thr for fn in f["functions"])}
        code_files = {f["file"] for f in comp.get("files", [])}
        touches = sum(c for p, c in file_commits.items() if p in code_files)
        hot = sum(c for p, c in file_commits.items() if p in complex_files)
        share = hot / float(touches) if touches else 0.0
        component("hotspots", "%d of %d code-file changes landed in files with a CC > %d function" % (hot, touches, thr),
                  100 * (1 - share))
    else:
        component("hotspots", "no churn history", None)
    component("duplication", "%.1f%% duplicated lines" % dup["duplication_pct"] if dup else "duplicates.json missing",
              100 - 5 * dup["duplication_pct"] if dup else None)
    if dead:
        s = dead.get("summary", {})
        pen = (20 * s.get("unreferenced_files", 0) + 4 * s.get("unreferenced_symbols", 0) + 10 * s.get("unreachable", 0)
               + 10 * s.get("orphan_projects", 0)) / kloc
        component("dead_code", "%d modules, %d symbols, %d unreachable per %.1f KLOC" % (
            s.get("unreferenced_files", 0), s.get("unreferenced_symbols", 0), s.get("unreachable", 0), kloc), 100 - pen)
    else:
        component("dead_code", "dead_code.json missing", None)
    dep_items = [ci for ci in consumed_items if ci["category"] == "dependency"]
    if eol or dep_items:
        st = (eol or {}).get("items", [])
        n_eol = sum(1 for e in st if e["status"] == "eol" and not e["floor"])
        n_soon = sum(1 for e in st if e["status"] == "eol-soon")
        n_floor = sum(1 for e in st if e["status"] == "eol" and e["floor"])
        dh = sum(1 for d in dep_items if d["severity"] in ("Critical", "High"))
        dm = sum(1 for d in dep_items if d["severity"] == "Medium")
        dl = sum(1 for d in dep_items if d["severity"] in ("Low", "Info"))
        component("currency", "%d past EOL, %d EOL soon, %d EOL floors, DEP findings %d high / %d medium / %d low" % (
            n_eol, n_soon, n_floor, dh, dm, dl), 100 - 35 * n_eol - 10 * n_soon - 5 * n_floor - 10 * dh - 4 * dm - dl)
    else:
        component("currency", "eol.json and DEP findings missing", None)
    if todos or sup or ev["hits"]:
        w = 0.0
        for t in todos.get("todos", []):
            yrs = (t.get("age_days") or 0) / 365.0
            w += {"TODO": 1, "FIXME": 2}.get(t["marker"], 3) * (1 + min(yrs, 5) / 2)
        w += 2 * len(todos.get("commented_code", []))
        for s in sup.get("items", []):
            if s["kind"] != "coverage":
                w += 5 if s["security_related"] else 3 if s["blanket"] else 1
        w += sum(len(v) for v in depr.values()) + 5 * sum(1 for v in mix.values() if len(v) >= 2)
        component("hygiene", "weighted markers %.1f per KLOC (TODO age-weighted, suppressions, commented-out, deprecated, mixed)"
                  % (w / kloc), 100 - 5 * w / kloc)
    else:
        component("hygiene", "todos/suppressions/hits missing", None)
    tests = [ci for ci in consumed_items if ci["category"] == "test-debt"]
    if "audit-test-coverage-and-ci" in present_skills:
        th = sum(1 for t in tests if t["severity"] in ("Critical", "High"))
        tm = sum(1 for t in tests if t["severity"] == "Medium")
        tl = sum(1 for t in tests if t["severity"] in ("Low", "Info"))
        component("tests", "TEST findings %d high / %d medium / %d low" % (th, tm, tl), 100 - 35 * th - 15 * tm - 5 * tl)
    else:
        component("tests", "audit-test-coverage-and-ci not run", None)
    if docs:
        st = {c["id"]: c["status"] for c in docs.get("checks", [])}
        pts = {"present": 30, "partial": 15}.get(st.get("readme"), 0) + {"present": 20, "unknown-age": 10}.get(st.get("readme-fresh"), 0) \
            + (15 if st.get("api-docs") == "present" else 0) + (15 if st.get("adr") == "present" else 0) \
            + (20 if st.get("runbook") == "present" else 0)
        component("docs", ", ".join("%s=%s" % kv for kv in st.items() if kv[0] in ("readme", "readme-fresh", "api-docs", "adr", "runbook")), pts)
    else:
        component("docs", "docs.json missing", None)
    q = [ci for ci in consumed_items if str(ci["finding_ref"]).split("-")[0] in QUALITY_PREFIXES]
    if any(PREFIX_MAP[p][2] in present_skills for p in QUALITY_PREFIXES):
        pen = sum({"Critical": 25, "High": 12, "Medium": 5, "Low": 2}.get(x["severity"], 0) for x in q)
        component("quality_findings", "%d findings from ORM/ASYNC/LEAK/FELEAK/FEBP/ARCH" % len(q), 100 - pen)
    else:
        component("quality_findings", "none of the ORM/ASYNC/LEAK/FELEAK/FEBP/ARCH skills have run", None)
    avail = [c for c in comps if c["sub_score"] is not None]
    wsum = sum(c["weight"] for c in avail)
    score = round(sum(c["sub_score"] * c["weight"] for c in avail) / wsum, 1) if wsum else None
    for c in comps:
        c["contribution"] = round(c["sub_score"] * c["weight"] / wsum, 1) if (wsum and c["sub_score"] is not None) else None
        c["status"] = "used" if c["sub_score"] is not None else "excluded (input missing; weight redistributed)"
    grade = None if score is None else "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D" if score >= 40 else "E"

    for it in items:
        it.pop("_finding", None)
        if "eol" in it:
            it["eol"] = {k: it["eol"][k] for k in ("product", "cycle", "eol", "status", "days_past_eol")}
    roadmap = {b: [it["id"] for it in items if it["bucket"] == b] for b in ("quick-win", "next-quarter", "long-term")}
    result = {"skill": SELF, "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "as_of": githist.iso(as_of), "history": {"mode": hist.mode, "reason": hist.reason},
              "maintainability": {"score": score, "grade": grade, "components": comps, "available_weight": wsum},
              "inventory": items, "hotspots": hotspots, "roadmap": roadmap, "consumed": consumed,
              "launch_risk_candidates": cands, "not_checked": not_checked}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(render_md(result))
    print(json.dumps({"maintainability": score, "grade": grade, "items": len(items), "candidates": [c["id"] + " " + c["severity"] + " " + c["title"] for c in cands],
                      "top5": ["%s %s p=%.2f %s" % (it["id"], it["category"], it["priority"], it["item"][:70]) for it in items[:5]]}, indent=2))
    return 0


def loc_str(it):
    if not it.get("file"):
        return "."
    return "%s:%s" % (it["file"], it["line"]) if it.get("line") else it["file"]


def render_md(r):
    out = []
    m = r["maintainability"]
    out.append("### Maintainability score: %s / 100 (grade %s)\n" % (m["score"], m["grade"]))
    out.append("| Input | Measure | Sub-score | Weight | Contribution |\n|---|---|---|---|---|")
    for c in m["components"]:
        out.append("| %s | %s | %s | %d | %s |" % (c["input"], c["measure"], "-" if c["sub_score"] is None else c["sub_score"],
                                                  c["weight"], c["contribution"] if c["contribution"] is not None else "excluded"))
    out.append("\n### Debt inventory\n")
    out.append("| Rank | ID | Item | Category | Location | Age (days) | Impact | Effort | Priority | Bucket | Source / finding |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for it in r["inventory"]:
        out.append("| %d | %s | %s | %s | `%s` | %s | %d | %s | %.2f | %s | %s |" % (
            it["rank"], it["id"], it["item"].replace("|", "/"), it["category"], loc_str(it),
            "-" if it["age_days"] is None else it["age_days"], it["impact"], it["effort"], it["priority"], it["bucket"],
            (it["finding_ref"] + " " if it.get("finding_ref") else "") + it["source"]))
    out.append("\n### Churn vs complexity hotspots\n")
    out.append("| Rank | Function / file | Location | Commits | CC | Lines | Score |\n|---|---|---|---|---|---|---|")
    for h in r["hotspots"]:
        out.append("| %d | %s | `%s` | %d | %d | %d | %d |" % (h["rank"], h["name"] or "(file)", "%s:%s" % (h["file"], h["start"]) if h.get("start") else h["file"],
                                                            h["commits"], h["cyclomatic"], h["length"], h["score"]))
    out.append("\n### Pay-down roadmap\n")
    by_id = {it["id"]: it for it in r["inventory"]}
    for b, label in (("quick-win", "Quick wins (days, do alongside feature work)"), ("next-quarter", "Next quarter (planned)"),
                     ("long-term", "Long term (needs a plan and budget)")):
        out.append("**%s**\n" % label)
        for i in r["roadmap"][b] or []:
            it = by_id[i]
            out.append("- %s %s (`%s`, impact %d, effort %s)%s" % (i, it["item"], loc_str(it), it["impact"], it["effort"],
                                                                 " - launch risk " + (it["finding_ref"] or "") if it["launch_risk"] else ""))
        if not r["roadmap"][b]:
            out.append("- (none)")
        out.append("")
    out.append("### Consumed findings\n")
    out.append("| Prefix | Skill | Mapped to | Count |\n|---|---|---|---|")
    for p, e in sorted(r["consumed"]["by_prefix"].items()):
        out.append("| %s | %s | %s | %d |" % (p, e["skill"], e["category"], e["count"]))
    if r["consumed"]["not_debt"]:
        out.append("\nNot treated as debt (owned by security/compliance skills): " +
                   ", ".join("%s x%d" % kv for kv in sorted(r["consumed"]["not_debt"].items())))
    out.append("\n### Launch-risk candidates (confirm, then add with $AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py)\n")
    for c in r["launch_risk_candidates"]:
        out.append("- [%s] %s - %s (`%s`)" % (c["severity"], c["id"], c["title"], c["location"]["file"]))
    if not r["launch_risk_candidates"]:
        out.append("- (none)")
    out.append("\n### Not checked\n")
    for n in r["not_checked"]:
        out.append("- %s - %s" % (n["item"], n["reason"]))
    if not r["not_checked"]:
        out.append("- (nothing recorded)")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.exit(main())
