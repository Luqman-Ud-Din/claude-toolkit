#!/usr/bin/env python3
"""Console summary for audit-application, and the Critical/High table for the security checkpoint.

Usage:
    python summary.py [repo_root] [--json] [--accepted accepted.json] [--as-of YYYY-MM-DD]
    python summary.py [repo_root] --critical-high [--phase security] [--json] [--accepted ...]

Summary (end of run): skills run / skipped / failed / not yet run for the plan in
audit/plan.json (or the last run), which ran with limited access, finding counts by severity
after cross-skill de-duplication, timings from audit/run-log.json, checkpoint answers and their
mode, and the go/no-go line.

Counts, skill categories and the verdict come from audit-findings-rollup
($AUDIT_CORE_ROOT/skills/audit-findings-rollup/scripts/findings_rollup.py), computed when this script runs, so they
include every result recorded so far. It is the same rule audit-report-generator prints: any open
Critical or High is NO-GO, only Medium/Low is CONDITIONAL GO, otherwise GO; valid risk
acceptances (--accepted) are honoured, and failed, skipped and limited areas become caveats. The
verdict line of audit/audit-report.md is read too and flagged when it is stale or disagrees.

Only the plan's skills are counted. Infrastructure steps run by atomic skills (endpoint
inventory, findings rollup) are never counted as skills.

--critical-high lists Critical and High findings (false positives excluded) for the skills of one
phase, which is what the security checkpoint shows the user.
Read-only: reads audit/ and prints; writes nothing.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
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

SEVERITIES = fr.SEVERITIES
VERDICT_RE = re.compile(r"\*\*Recommendation:\s*([A-Z][A-Z -]*?)\.\*\*\s*(.*)")
CAVEAT_WIDTH = 220


def load(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def ts(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fmt_dur(sec):
    if sec is None:
        return "-"
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


def area(skill):
    return skill.replace("audit-", "").replace("-", " ")


def critical_high(root, phase, accepted=None, as_of=None):
    here_profiles = load(os.path.normpath(os.path.join(HERE, "..", "references", "profiles.json")), {})
    skills = next((p.get("skills", []) for p in here_profiles.get("phases", []) if p["id"] == phase), [])
    acc = fr.load_acceptances(accepted, as_of) if accepted else None
    rows = fr.critical_high(fr.load_findings(root)["findings"], acc, skills=skills)
    return skills, rows


def _report_verdict(audit, newest):
    report_path = os.path.join(audit, "audit-report.md")
    if not os.path.exists(report_path):
        return None
    with open(report_path, "r", encoding="utf-8", errors="ignore") as fh:
        m = VERDICT_RE.search(fh.read())
    if not m:
        return None
    mtime = datetime.fromtimestamp(os.path.getmtime(report_path), tz=timezone.utc)
    return {"verdict": m.group(1).strip(), "why": m.group(2).strip(), "stale": bool(newest and newest > mtime)}


def build(root, accepted=None, as_of=None):
    audit = os.path.join(root, "audit")
    runlog = load(os.path.join(audit, "run-log.json"), {"runs": []}) or {"runs": []}
    run = runlog["runs"][-1] if runlog.get("runs") else None
    plan = load(os.path.join(audit, "plan.json")) or (run or {}).get("plan") or {"items": []}
    run_start = ts(run["started_at"]) if run else None

    skill_items = [i for i in plan["items"] if i["type"] == "skill"]
    plan_skills = [i["id"] for i in skill_items]  # ALL plan skills, skipped ones included
    order = {s: n for n, s in enumerate(plan_skills)}
    phase_of = {i["id"]: i.get("phase") for i in skill_items}

    doc = fr.rollup(root, acceptances=accepted, expected=plan_skills, as_of=as_of)
    sk = doc["skills"]
    statuses = fr.load_status(audit)["skills"]

    def planned(rows, key=lambda r: r["skill"]):
        return sorted((r for r in rows if key(r) in order), key=lambda r: order[key(r)])

    failed = [{"skill": x["skill"], "reason": x["reason"], "kind": None} for x in planned(sk["failed"])]
    skipped = [{"skill": x["skill"], "reason": x["reason"], "kind": x.get("skip_kind") or "self-skipped"}
               for x in planned(sk["skipped"])]
    limited = [{"skill": x["skill"], "reason": x["reason"], "kind": None, "items": x.get("items", [])}
               for x in planned(sk["limited_access"])]
    not_run_yet = [{"skill": x["skill"], "reason": "no status file"} for x in planned(sk["not_run"])]
    not_run_yet += [{"skill": s, "reason": "no status file (findings file present)"}
                    for s in sorted((s for s in sk["no_status_file"] if s in order), key=order.get)]
    not_run_yet += [{"skill": x["skill"], "reason": f"unfinished status '{x['status']}'" + (f": {x['reason']}" if x.get("reason") else "")}
                    for x in planned(sk["other_status"])]
    not_run_yet.sort(key=lambda r: order[r["skill"]])
    completed = [s for s in sk["completed"] if s in order]

    this_run, reused, newest = 0, 0, None
    for s in plan_skills:
        st = statuses.get(s)
        if not st:
            continue
        fin = ts(st.get("finished_at"))
        if st.get("status") == "completed":
            if run_start and fin and fin >= run_start:
                this_run += 1
            else:
                reused += 1
        if fin and st.get("status") in ("completed", "failed") and phase_of.get(s) != "reporting":
            newest = fin if newest is None or fin > newest else newest

    v = doc["verdict"]
    report = _report_verdict(audit, newest)
    verdict = {"verdict": v["verdict"], "reason": v["reason"], "caveats": v["caveats"],
               "why": " ".join([v["reason"]] + v["caveats"]),
               "blockers": [b["id"] for b in v["blockers"]],
               "source": "audit-findings-rollup (computed from audit/findings and audit/status when this summary ran)",
               "stale": bool(report and report["stale"]),
               "report": dict(report, agrees=report["verdict"] == v["verdict"]) if report else None}

    timings, checkpoints = {}, []
    if run:
        fin = ts(run.get("finished_at"))
        last = max((ts(e.get("finished_at") or e.get("at")) for e in run.get("events", []) if (e.get("finished_at") or e.get("at"))), default=None)
        end = fin or last
        timings["run_s"] = (end - run_start).total_seconds() if (end and run_start) else None
        by_phase, items = {}, []
        for e in run.get("events", []):
            if e.get("event") == "finish" and e.get("duration_s") is not None:
                by_phase[e["phase"]] = by_phase.get(e["phase"], 0) + e["duration_s"]
                items.append((e["duration_s"], e["id"]))
            if e.get("event") == "checkpoint":
                checkpoints.append({"id": e["id"], "answer": e.get("answer"), "mode": e.get("mode")})
        timings["by_phase_s"] = by_phase
        timings["slowest"] = [{"id": i, "duration_s": d} for d, i in sorted(items, reverse=True)[:3]]

    summ = doc["summary"]
    return {
        "root": os.path.abspath(root),
        "run": {"run_id": run.get("run_id"), "mode": run.get("mode"), "profile": run.get("profile"),
                "single_skill": run.get("single_skill"),
                "multi_tenant": run.get("multi_tenant"), "resumed": run.get("resumed"), "force": run.get("force"),
                "started_at": run.get("started_at"), "finished_at": run.get("finished_at"),
                "outcome": run.get("outcome")} if run else None,
        "skills": {"planned": sum(1 for i in skill_items if i["action"] != "skip"), "completed": len(completed),
                   "completed_this_run": this_run, "reused_from_earlier_runs": reused, "limited_access": limited,
                   "failed": failed, "skipped": skipped, "not_run_yet": not_run_yet},
        "findings": {"deduplicated": summ["deduplicated"], "raw": summ["raw"], "open": summ["open"],
                     "merged": summ["merged"], "cross_skill_groups": summ["cross_skill_groups"],
                     "false_positives": summ["false_positives"], "risk_accepted": summ["risk_accepted"],
                     "parse_errors": doc["parse_errors"]},
        "timings": timings, "checkpoints": checkpoints,
        "report": "audit/audit-report.md" if os.path.exists(os.path.join(audit, "audit-report.md")) else None,
        "rollup": {"as_of": doc["as_of"], "acceptances": doc["acceptances"] if accepted else None},
        "go_no_go": verdict,
    }


def print_summary(s):
    r = s["run"] or {}
    k = s["skills"]
    print("=" * 72)
    print("audit-application summary")
    print(f"Repo: {s['root']}")
    if r:
        mt = {True: "yes", False: "no", None: "unknown"}[r.get("multi_tenant")]
        how = "resumed" if r.get("resumed") else "fresh"
        if r.get("force"):
            how = "forced full re-run"
        scope = f"single skill {r.get('single_skill')}" if r.get("mode") == "single-skill" else f"profile {r.get('profile')}"
        print(f"Run #{r['run_id']} ({how}; {scope}; multi-tenant {mt}); "
              f"duration {fmt_dur(s['timings'].get('run_s'))}; outcome {r.get('outcome') or 'in progress'}")
    print(f"Skills: {k['planned']} planned | {k['completed']} run | {len(k['skipped'])} skipped | "
          f"{len(k['failed'])} failed | {len(k['not_run_yet'])} not run yet")
    print(f"  run this time: {k['completed_this_run']}; reused from earlier runs: {k['reused_from_earlier_runs']}; "
          f"ran with limited access: {len(k['limited_access'])}")
    for e in k["failed"]:
        print(f"  FAILED   {e['skill']} - {e['reason']}")
    for e in k["limited_access"]:
        print(f"  LIMITED  {e['skill']} - {e['reason']}")
    kinds = {}
    for e in k["skipped"]:
        kinds.setdefault(e["kind"] or "skipped", []).append(e)
    for kind, rows in kinds.items():
        if len(rows) > 4:
            print(f"  SKIPPED  {len(rows)} x {kind}")
        else:
            for e in rows:
                print(f"  SKIPPED  {e['skill']} - {e['reason']}")
    for e in k["not_run_yet"]:
        print(f"  NOT RUN  {e['skill']} - {e['reason']}")
    f = s["findings"]
    c = f["deduplicated"]
    print("Findings by severity (after cross-skill de-duplication): "
          + " | ".join(f"{sev} {c[sev]}" for sev in SEVERITIES))
    print(f"  raw {sum(f['raw'].values())}, merged {f['merged']} ({f['cross_skill_groups']} cross-skill groups), "
          f"false positives excluded {f['false_positives']}"
          + (f", risk-accepted {f['risk_accepted']}" if f["risk_accepted"] else ""))
    for e in f["parse_errors"]:
        print(f"  UNREADABLE {e['file']} - {e['error']}")
    t = s["timings"]
    if t.get("by_phase_s"):
        print("Timings: " + "; ".join(f"{p} {fmt_dur(v)}" for p, v in t["by_phase_s"].items())
              + ("; slowest " + ", ".join(f"{x['id']} {fmt_dur(x['duration_s'])}" for x in t["slowest"]) if t["slowest"] else ""))
    if s["checkpoints"]:
        print("Checkpoints: " + "; ".join(f"{cp['id']} = {cp['answer']} ({cp['mode']})" for cp in s["checkpoints"]))
    print(f"Report: {s['report'] or 'not generated'}")
    g = s["go_no_go"]
    print(f"GO/NO-GO: {g['verdict']} - {g['reason']}")
    for cav in g["caveats"]:
        text = cav if len(cav) <= CAVEAT_WIDTH else cav[:CAVEAT_WIDTH].rsplit(" ", 1)[0] + " ... (full list: --json)"
        print(f"  caveat: {text}")
    rep = g.get("report")
    if rep and (rep["stale"] or not rep["agrees"]):
        state = "is older than the newest skill result" if rep["stale"] else "disagrees"
        print(f"  note: audit/audit-report.md says {rep['verdict']} and {state}; re-run audit-report-generator")
    print("=" * 72)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--critical-high", action="store_true")
    ap.add_argument("--phase", default="security")
    ap.add_argument("--accepted", default=None, help="risk-acceptance JSON list (audit-findings-rollup format)")
    ap.add_argument("--as-of", default=None, help="date acceptances are checked against (default today, UTC)")
    a = ap.parse_args()
    if not os.path.isdir(os.path.join(a.root, "audit")):
        print("error: no audit/ workspace; run run_state.py init first", file=sys.stderr)
        return 2
    if a.critical_high:
        skills, rows = critical_high(a.root, a.phase, a.accepted, a.as_of)
        if a.json:
            print(json.dumps({"phase": a.phase, "count": len(rows), "findings": rows}, indent=2))
            return 0
        print(f"Critical/High findings from the {a.phase} phase ({len(rows)}):")
        if not rows:
            print("  none recorded")
        for r in rows:
            state = "" if r["open"] else f"; risk accepted ({r['acceptance']['status']})"
            print(f"  [{r['severity']}] {r['id']:<12} {area(r['skill']):<32} {r['title']}  ({r['location']}; {r['confidence']}{state})")
        return 0
    s = build(a.root, a.accepted, a.as_of)
    if a.json:
        print(json.dumps(s, indent=2))
    else:
        print_summary(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
