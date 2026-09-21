#!/usr/bin/env python3
"""Workspace, status and resume state for audit-application. Appends timings to audit/run-log.json.

Usage (every command takes --root <audited repo>, default "."):
    python run_state.py init       [--profile P] [--skills a,b] [--skill NAME] [--multi-tenant yes|no]
                                   [--force] [--redetect] [--non-interactive]
                                   [--answers provided|interactive|auto-continued]
                                   [--simulate-failure NAME]
    python run_state.py next       [--wave]            # next pending item (or the whole parallel wave)
    python run_state.py status     [--json] [--preview [--force]]
    python run_state.py start      ID                  # skill id, or an infrastructure step id ("endpoint-inventory", "dedupe")
    python run_state.py complete   ID [--reason TEXT] [--limited "no test URL" ...]
    python run_state.py fail       ID --reason TEXT
    python run_state.py skip       ID --reason TEXT [--kind user|deferred|n/a]
    python run_state.py checkpoint ID --answer TEXT [--mode interactive|auto-continued|provided] [--data JSON|file]
    python run_state.py defer      --reason TEXT       # user stopped: remaining audit skills -> skipped (deferred)
    python run_state.py finish     [--outcome TEXT]

Contract:
  * audit/status/<skill>.json is the source of truth:
    {"skill","status":"completed|failed|skipped","reason","started_at","finished_at"}.
    Children write it; complete/fail/skip fill in or normalise whatever a child did not write.
    Orchestrator-written skips carry "skipped_by":"audit-application" and "skip_kind".
    Limited access is recorded on a completed status as "limited_access":[...] and a reason
    starting "limited access: ", which audit-report-generator prints in its scope table.
  * Resume: an item is done for the current run when its result was recorded during this run
    (including failed - failures continue, they never loop). From earlier runs, completed and
    child-written skipped results are reused; failed results and orchestrator-written skips are
    retried; with --force nothing earlier is reused. Reporting steps (dedupe, mapper, report) are
    also redone when an audit skill finished after them. A checkpoint is re-asked when a skill of
    the phase before it finished after the last answer.
  * Infrastructure steps (type "action", run by an atomic skill: endpoint-inventory runs
    audit-endpoint-inventory, dedupe runs audit-findings-rollup) write no status file and are never
    counted as skills. A step with "needed_by" is not needed when every skill that reads its output
    already has a result for this run, so a resume never re-runs the inventory just to retry an
    unrelated skill.
  * Checkpoints answered without a user (headless run, CI, subagent) are recorded with mode
    "auto-continued" - never silently skipped.

This script manages plan and state only. Child skills are invoked by Claude through the Skill
tool or subagents, as SKILL.md instructs. It writes only under audit/ and never touches the
audited code.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import plan as planmod  # noqa: E402

detect_stack = planmod.detect_stack  # audit-stack-detection, loaded by file path in plan.py
ORCH = "audit-application"


# ---------------------------------------------------------------- helpers
def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat() if dt else None


def parse_ts(s):
    if not s or not isinstance(s, str):
        return None
    t = s.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        try:
            dt = datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def save_json(path, doc):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    os.replace(tmp, path)


def emit(doc):
    print(json.dumps(doc, indent=2))


class Workspace:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.audit = os.path.join(self.root, "audit")
        self.status_dir = os.path.join(self.audit, "status")
        self.findings_dir = os.path.join(self.audit, "findings")
        self.reports_dir = os.path.join(self.audit, "reports")
        self.evidence_dir = os.path.join(self.audit, "evidence")
        self.own_evidence = os.path.join(self.evidence_dir, ORCH)
        self.runlog_path = os.path.join(self.audit, "run-log.json")
        self.plan_path = os.path.join(self.audit, "plan.json")
        self.stack_path = os.path.join(self.audit, "stack.json")

    def status_path(self, skill):
        return os.path.join(self.status_dir, f"{skill}.json")

    def status(self, skill):
        p = self.status_path(skill)
        doc = load_json(p)
        if not isinstance(doc, dict):
            return None, None
        fin = parse_ts(doc.get("finished_at"))
        if fin is None:
            fin = datetime.fromtimestamp(os.path.getmtime(p), tz=timezone.utc)
        return doc, fin

    def runlog(self):
        doc = load_json(self.runlog_path)
        if not isinstance(doc, dict):
            doc = {"skill": ORCH, "root": self.root, "runs": []}
        return doc


def current_run(runlog):
    if not runlog["runs"]:
        raise SystemExit("error: no run recorded; run `run_state.py init` first")
    return runlog["runs"][-1]


def find_item(run, item_id):
    for it in run["plan"]["items"]:
        if it["id"] == item_id and it["type"] in ("skill", "action"):
            return it
    raise SystemExit(f"error: '{item_id}' is not a skill or action in the current run's plan")


def open_start(run, item_id):
    started = None
    for ev in run.get("events", []):
        if ev.get("id") != item_id:
            continue
        if ev["event"] == "start":
            started = ev
        elif ev["event"] in ("finish",):
            started = None
    return started


def last_action_finish(runlog, action_id):
    """(finished_at, status, run_id) of the latest finish of an action across runs."""
    for run in reversed(runlog["runs"]):
        for ev in reversed(run.get("events", [])):
            if ev.get("event") == "finish" and ev.get("id") == action_id and ev.get("type") == "action":
                return parse_ts(ev.get("finished_at")), ev.get("status"), run["run_id"]
    return None, None, None


def last_checkpoint(runlog, cp_id):
    for run in reversed(runlog["runs"]):
        for ev in reversed(run.get("events", [])):
            if ev.get("event") == "checkpoint" and ev.get("id") == cp_id:
                return parse_ts(ev.get("at")), ev
    return None, None


def result_time(ws, runlog, item):
    if item["type"] == "skill":
        return ws.status(item["id"])[1]
    if item["type"] == "action":
        return last_action_finish(runlog, item["id"])[0]
    return None


# ---------------------------------------------------------------- resume logic
def upstream_newer(ws, runlog, plan_items, item, fin):
    idx = plan_items.index(item)
    newest, who = None, None
    for up in plan_items[:idx]:
        if up["type"] not in ("skill", "action") or up["action"] == "skip":
            continue
        t = result_time(ws, runlog, up)
        if t and (newest is None or t > newest):
            newest, who = t, up["id"]
    if newest and fin and newest > fin:
        return f"stale: {who} finished after this step last ran"
    return None


def action_state(ws, runlog, run, item, rs, force, items):
    fin, st, _run_id = last_action_finish(runlog, item["id"])
    if fin is None:
        return False, "not run yet"
    in_run = fin >= rs
    if not in_run and (force or st != "completed"):
        return False, "--force: earlier result not reused" if force else f"{st} in an earlier run"
    stale = upstream_newer(ws, runlog, items, item, fin)
    if stale:
        return False, stale
    return True, "recorded in this run" if in_run else "reused from an earlier run"


def action_outputs(profiles, action_id):
    for ph in profiles["phases"]:
        for act in ph.get("actions", []):
            if act["id"] == action_id:
                return act.get("outputs", [])
    return []


def item_state(ws, runlog, run, item):
    rs = parse_ts(run["started_at"])
    force = bool(run.get("force"))
    items = run["plan"]["items"]
    if item["action"] == "skip":
        return True, f"not run ({item.get('kind')}): {item.get('reason')}"
    if item["type"] == "setup" or (item["type"] == "checkpoint" and item["phase"] == "setup"):
        return True, "handled by init"

    if item["type"] == "skill":
        doc, fin = ws.status(item["id"])
        if doc is None:
            started = open_start(run, item["id"])
            return False, "started in this run but no result recorded (interrupted?)" if started else "no status file yet"
        in_run = fin >= rs
        if not in_run:
            st = doc.get("status")
            if force:
                return False, "--force: earlier result not reused"
            if st == "failed":
                return False, f"failed in an earlier run: {doc.get('reason')}"
            if st == "skipped" and doc.get("skipped_by") == ORCH:
                return False, f"skipped by the orchestrator in an earlier run ({doc.get('skip_kind')}); re-evaluated"
            if st not in ("completed", "skipped"):
                return False, f"unrecognised status '{st}'"
        if item.get("derived"):
            stale = upstream_newer(ws, runlog, items, item, fin)
            if stale:
                return False, stale
        return True, ("recorded in this run" if in_run else "reused from an earlier run") + f" ({doc.get('status')})"

    if item["type"] == "action":
        done, why = action_state(ws, runlog, run, item, rs, force, items)
        if not done and item.get("needed_by"):
            readers = [it for it in items if it["type"] == "skill" and it["id"] in item["needed_by"]
                       and it["action"] != "skip"]
            if readers and all(item_state(ws, runlog, run, it)[0] for it in readers):
                return True, (f"not needed in this run ({why}): every skill that reads it already has a result "
                              f"({', '.join(it['id'] for it in readers)})")
        return done, why

    if item["type"] == "checkpoint":
        at, ev = last_checkpoint(runlog, item["id"])
        if at is None:
            return False, "not answered yet"
        if force and at < rs:
            return False, "--force: ask again"
        newest, who = None, None
        for it in items:
            if it["type"] == "skill" and it["phase"] == item.get("after_phase") and it["action"] != "skip":
                t = ws.status(it["id"])[1]
                if t and (newest is None or t > newest):
                    newest, who = t, it["id"]
        if newest and newest > at:
            return False, f"ask again: {who} finished after the last answer"
        return True, f"answered '{ev.get('answer')}' ({ev.get('mode')})"
    return True, "n/a"


def pending_items(ws, runlog, run):
    out = []
    for it in run["plan"]["items"]:
        if it["type"] == "setup" or it["action"] == "skip":
            continue
        done, why = item_state(ws, runlog, run, it)
        if not done:
            out.append((it, why))
    return out


def _brief(it, why):
    d = {"type": it["type"], "id": it["id"], "phase": it["phase"], "why_pending": why}
    for k in ("wave", "prefix", "parallel_group", "text", "needed_by"):
        if it.get(k) is not None:
            d[k] = it[k]
    if it.get("simulate_failure"):
        d["simulate_failure"] = True
    return d


def preview_text(root, force=False):
    """Used by plan.py --dry-run: what would a re-run do with the existing workspace?"""
    ws = Workspace(root)
    runlog = ws.runlog()
    if not runlog["runs"]:
        return None
    base = next((r for r in reversed(runlog["runs"]) if r.get("mode") != "single-skill"), runlog["runs"][-1])
    fake = {"run_id": "preview", "started_at": iso(now()), "force": force, "plan": base["plan"], "events": []}
    pend = pending_items(ws, runlog, fake)
    total = sum(1 for i in base["plan"]["items"] if i["type"] != "setup" and i["action"] != "skip")
    lines = [f"Resume preview (existing workspace, last run #{base['run_id']}, profile {base.get('profile')}"
             f"{', --force' if force else ''}): {total - len(pend)} of {total} items would be reused."]
    for it, why in pend:
        lines.append(f"  next: {it['id']} - {why}")
    if not pend:
        lines.append("  nothing pending; pass --force to re-run everything")
    return "\n".join(lines)


# ---------------------------------------------------------------- status writers
def write_orch_skip(ws, skill, kind, reason, started=None):
    doc, _ = ws.status(skill)
    if doc is not None and doc.get("skipped_by") != ORCH:
        return False  # a real result (completed/failed/child skip) from an earlier run survives
    if doc is not None and doc.get("skip_kind") == kind and doc.get("reason") == reason:
        return False  # idempotent: keep the original timestamp so reporting is not made stale
    save_json(ws.status_path(skill), {"skill": skill, "status": "skipped", "reason": reason,
                                      "started_at": iso(started), "finished_at": iso(now()),
                                      "skipped_by": ORCH, "skip_kind": kind})
    return True


def contract_warnings(ws, item, profiles):
    meta = profiles["skills"].get(item["id"], {})
    w = []
    fpath = os.path.join(ws.findings_dir, f"{item['id']}.json")
    if not os.path.exists(fpath):
        if not meta.get("findings_optional"):
            w.append(f"no audit/findings/{item['id']}.json written")
    else:
        doc = load_json(fpath)
        if not isinstance(doc, dict):
            w.append(f"audit/findings/{item['id']}.json does not parse")
        else:
            for k in ("findings", "scope"):
                if k not in doc:
                    w.append(f"audit/findings/{item['id']}.json has no '{k}'")
            bad = [f.get("id") for f in doc.get("findings", []) if isinstance(f, dict)
                   and not str(f.get("id", "")).startswith(meta.get("prefix", "") + "-")]
            if bad and meta.get("prefix"):
                w.append(f"finding ids without prefix {meta['prefix']}-: {', '.join(map(str, bad[:5]))}")
    if not meta.get("findings_optional") and not os.path.exists(os.path.join(ws.reports_dir, f"{item['id']}.md")):
        w.append(f"no audit/reports/{item['id']}.md written")
    return w


# ---------------------------------------------------------------- commands
def cmd_init(a):
    ws = Workspace(a.root)
    profiles = planmod.load_profiles()
    for d in (ws.audit, ws.findings_dir, ws.evidence_dir, ws.status_dir, ws.reports_dir, ws.own_evidence):
        os.makedirs(d, exist_ok=True)
    runlog = ws.runlog()
    prev_plan = load_json(ws.plan_path)

    stack = None if a.redetect else load_json(ws.stack_path)
    if not isinstance(stack, dict):
        stack = detect_stack.detect(ws.root)
    answers = a.answers or ("auto-continued" if a.non_interactive else "interactive")
    setup_events = []
    if a.multi_tenant in ("yes", "no"):
        stack["multi_tenant"] = a.multi_tenant == "yes"
        stack["multi_tenant_source"] = f"setup answer ({answers})"
        setup_events.append(("multi-tenant", a.multi_tenant, answers))
    elif not isinstance(stack.get("multi_tenant"), bool) and not a.skill:
        if a.non_interactive:
            default = profiles["checkpoints"]["multi-tenant"]["default_non_interactive"]
            stack["multi_tenant"] = default == "yes"
            stack["multi_tenant_source"] = "auto-continued default"
            setup_events.append(("multi-tenant", default, "auto-continued"))
        else:
            print("error: ask whether the application is multi-tenant (references/checkpoints.md), "
                  "then pass --multi-tenant yes|no", file=sys.stderr)
            return 2
    save_json(ws.stack_path, stack)

    skills = [s for s in (a.skills or "").split(",") if s.strip()] or None
    profile = None
    if not a.skill:
        profile = a.profile or ("custom" if skills else None)
        if not profile and isinstance(prev_plan, dict) and prev_plan.get("profile"):
            profile = prev_plan["profile"]
            skills = skills or prev_plan.get("custom_skills")
            setup_events.append(("scope-profile", f"{profile} (reused from audit/plan.json)", "provided"))
        elif not profile and a.non_interactive:
            profile = profiles["checkpoints"]["scope-profile"]["default_non_interactive"]
            setup_events.append(("scope-profile", profile, "auto-continued"))
        elif not profile:
            print("error: ask for a scope profile (references/checkpoints.md), then pass --profile", file=sys.stderr)
            return 2
        else:
            setup_events.append(("scope-profile", profile + (f": {','.join(skills)}" if skills else ""), answers))
    try:
        plan = planmod.build_plan(ws.root, profile=profile, skills=skills, single=a.skill,
                                  multi_tenant=None, simulate_failure=a.simulate_failure,
                                  profiles=profiles, stack=stack, stack_source="audit/stack.json")
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if runlog["runs"] and not runlog["runs"][-1].get("finished_at"):
        runlog["runs"][-1]["interrupted"] = True
    started = now()
    run = {"run_id": len(runlog["runs"]) + 1, "started_at": iso(started), "finished_at": None,
           "mode": plan["mode"], "profile": plan["profile"], "custom_skills": plan["custom_skills"],
           "single_skill": plan["single_skill"], "force": bool(a.force), "non_interactive": bool(a.non_interactive),
           "simulate_failure": plan["simulate_failure"], "multi_tenant": plan["multi_tenant"],
           "resumed": bool(runlog["runs"]) and not a.force, "plan": planmod.stable(plan), "events": []}
    for cp, ans, mode in setup_events:
        run["events"].append({"event": "checkpoint", "id": cp, "phase": "setup", "answer": ans, "mode": mode,
                              "at": iso(started)})
    if plan["mode"] != "single-skill":
        save_json(ws.plan_path, planmod.stable(plan))
        for it in plan["items"]:
            if it["type"] == "skill" and it["action"] == "skip":
                wrote = write_orch_skip(ws, it["id"], it["kind"], it["reason"])
                run["events"].append({"event": "skip", "id": it["id"], "type": "skill", "phase": it["phase"],
                                      "kind": it["kind"], "reason": it["reason"], "status_written": wrote,
                                      "at": iso(now())})
    runlog["runs"].append(run)
    save_json(ws.runlog_path, runlog)
    pend = pending_items(ws, runlog, run)
    emit({"run_id": run["run_id"], "workspace": ws.audit.replace(os.sep, "/"), "mode": run["mode"],
          "profile": run["profile"], "multi_tenant": run["multi_tenant"], "force": run["force"],
          "resumed": run["resumed"], "planned_skills": plan["counts"]["skills_run"],
          "skipped_skills": plan["counts"]["skills_skipped"], "pending": len(pend),
          "next": _brief(*pend[0]) if pend else {"type": "done"}, "warnings": plan["warnings"]})
    return 0


def cmd_next(a):
    ws = Workspace(a.root)
    runlog = ws.runlog()
    run = current_run(runlog)
    pend = pending_items(ws, runlog, run)
    if not pend:
        emit({"type": "done"})
        return 0
    first, why = pend[0]
    if a.wave and first["type"] == "skill" and first.get("parallel_group"):
        group = [_brief(it, w) for it, w in pend if it.get("parallel_group") == first["parallel_group"]]
        emit({"type": "wave", "parallel_group": first["parallel_group"], "items": group})
    else:
        emit(_brief(first, why))
    return 0


def cmd_status(a):
    ws = Workspace(a.root)
    runlog = ws.runlog()
    if a.preview:
        print(preview_text(a.root, force=a.force) or "no runs recorded")
        return 0
    run = current_run(runlog)
    rows = []
    for it in run["plan"]["items"]:
        if it["type"] == "setup":
            continue
        done, why = item_state(ws, runlog, run, it)
        doc = ws.status(it["id"])[0] if it["type"] == "skill" else None
        rows.append({"order": it.get("order"), "type": it["type"], "id": it["id"], "phase": it["phase"],
                     "action": it["action"], "state": "done" if done else "pending",
                     "status": doc.get("status") if doc else None, "why": why})
    if a.json:
        emit({"run_id": run["run_id"], "items": rows, "pending": [r["id"] for r in rows if r["state"] == "pending"]})
        return 0
    print(f"run #{run['run_id']} ({run['mode']}, profile {run.get('profile')}, force={run.get('force')})")
    for r in rows:
        if r["action"] == "skip":
            continue
        print(f"  {str(r['order'] or ''):>3} {r['state']:<8} {r['type']:<10} {r['id']:<42} {r['why']}")
    skipped = sum(1 for r in rows if r["action"] == "skip")
    print(f"  ({skipped} skills not in this run's plan are recorded as skipped with a reason)")
    return 0


def cmd_start(a):
    ws = Workspace(a.root)
    runlog = ws.runlog()
    run = current_run(runlog)
    it = find_item(run, a.id)
    ev = {"event": "start", "id": it["id"], "type": it["type"], "phase": it["phase"], "at": iso(now())}
    run["events"].append(ev)
    save_json(ws.runlog_path, runlog)
    emit(ev)
    return 0


def _finish(ws, runlog, run, it, status, reason, extra=None):
    st_ev = open_start(run, it["id"])
    started = parse_ts(st_ev["at"]) if st_ev else None
    fin = now()
    ev = {"event": "finish", "id": it["id"], "type": it["type"], "phase": it["phase"], "status": status,
          "reason": reason, "started_at": iso(started), "finished_at": iso(fin),
          "duration_s": round((fin - started).total_seconds(), 3) if started else None}
    ev.update(extra or {})
    run["events"].append(ev)
    save_json(ws.runlog_path, runlog)
    return ev


def cmd_complete(a):
    ws = Workspace(a.root)
    runlog = ws.runlog()
    run = current_run(runlog)
    it = find_item(run, a.id)
    if it["type"] == "action":
        missing = [o for o in action_outputs(planmod.load_profiles(), it["id"])
                   if not os.path.exists(os.path.join(ws.root, *o.split("/")))]
        extra = {"skill": it.get("skill")}
        if missing:
            extra["contract_warnings"] = [f"{it.get('skill') or it['id']} did not write {o}" for o in missing]
        emit(_finish(ws, runlog, run, it, "completed", a.reason, extra))
        return 0
    profiles = planmod.load_profiles()
    st_ev = open_start(run, it["id"])
    started = parse_ts(st_ev["at"]) if st_ev else parse_ts(run["started_at"])
    doc, fin = ws.status(it["id"])
    warnings = []
    if doc is not None and fin is not None and fin >= started:
        new = dict(doc)
        if doc.get("status") in ("failed", "skipped"):
            warnings.append(f"child reported '{doc['status']}' ({doc.get('reason')}); kept as {doc['status']}")
        elif doc.get("status") != "completed":
            warnings.append(f"child wrote unrecognised status '{doc.get('status')}'; normalised to completed")
            new["status"] = "completed"
    else:
        new = {"skill": it["id"], "status": "completed", "reason": None, "started_at": iso(started),
               "finished_at": iso(now()), "written_by": ORCH}
        warnings.append(f"child did not write audit/status/{it['id']}.json in this run; written by the orchestrator")
    new.setdefault("skill", it["id"])
    new.setdefault("reason", None)
    new["started_at"] = new.get("started_at") or iso(started)
    new["finished_at"] = new.get("finished_at") or iso(now())
    if a.reason and new["status"] == "completed":
        new["reason"] = a.reason
    if a.limited and new["status"] == "completed":
        limited = list(new.get("limited_access") or []) + [x for x in a.limited if x not in (new.get("limited_access") or [])]
        new["limited_access"] = limited
        prefix = "limited access: " + "; ".join(limited)
        rest = new.get("reason")
        new["reason"] = prefix if not rest or rest.startswith("limited access") else f"{prefix} | {rest}"
    if new["status"] == "completed":
        warnings += contract_warnings(ws, it, profiles)
    save_json(ws.status_path(it["id"]), new)
    ev = _finish(ws, runlog, run, it, new["status"], new.get("reason"),
                 {"limited_access": new.get("limited_access") or [], "contract_warnings": warnings})
    emit(ev)
    return 0


def cmd_fail(a):
    ws = Workspace(a.root)
    runlog = ws.runlog()
    run = current_run(runlog)
    it = find_item(run, a.id)
    if it["type"] == "skill":
        st_ev = open_start(run, it["id"])
        started = parse_ts(st_ev["at"]) if st_ev else parse_ts(run["started_at"])
        doc, fin = ws.status(it["id"])
        new = dict(doc) if (doc is not None and fin is not None and fin >= started) else {}
        if new.get("status") == "failed" and new.get("reason") and new["reason"] != a.reason:
            new["child_reason"] = new["reason"]
        new.update({"skill": it["id"], "status": "failed", "reason": a.reason,
                    "started_at": new.get("started_at") or iso(started), "finished_at": iso(now())})
        save_json(ws.status_path(it["id"]), new)
    emit(_finish(ws, runlog, run, it, "failed", a.reason))
    return 0


def cmd_skip(a):
    ws = Workspace(a.root)
    runlog = ws.runlog()
    run = current_run(runlog)
    it = find_item(run, a.id)
    if it["type"] == "skill":
        st_ev = open_start(run, it["id"])
        save_json(ws.status_path(it["id"]), {"skill": it["id"], "status": "skipped", "reason": a.reason,
                                             "started_at": st_ev["at"] if st_ev else None, "finished_at": iso(now()),
                                             "skipped_by": ORCH, "skip_kind": a.kind})
    emit(_finish(ws, runlog, run, it, "skipped", a.reason, {"kind": a.kind}))
    return 0


def cmd_checkpoint(a):
    ws = Workspace(a.root)
    runlog = ws.runlog()
    run = current_run(runlog)
    data = None
    if a.data:
        if os.path.exists(a.data):
            data = load_json(a.data, default=None)
        else:
            try:
                data = json.loads(a.data)
            except ValueError:
                data = a.data
    at = iso(now())
    ev = {"event": "checkpoint", "id": a.id, "answer": a.answer, "mode": a.mode, "at": at}
    if data is not None:
        path = os.path.join(ws.own_evidence, f"checkpoint-{a.id}.json")
        save_json(path, {"id": a.id, "answer": a.answer, "mode": a.mode, "at": at, "data": data})
        ev["data_file"] = os.path.relpath(path, ws.root).replace(os.sep, "/")
    run["events"].append(ev)
    save_json(ws.runlog_path, runlog)
    emit(ev)
    return 0


def cmd_defer(a):
    ws = Workspace(a.root)
    runlog = ws.runlog()
    run = current_run(runlog)
    deferred = []
    for it, _why in pending_items(ws, runlog, run):
        if it["type"] == "skill" and not it.get("derived"):
            write_orch_skip(ws, it["id"], "deferred", f"deferred: {a.reason}")
            run["events"].append({"event": "skip", "id": it["id"], "type": "skill", "phase": it["phase"],
                                  "kind": "deferred", "reason": f"deferred: {a.reason}", "status_written": True,
                                  "at": iso(now())})
            deferred.append(it["id"])
    save_json(ws.runlog_path, runlog)
    emit({"deferred": deferred, "note": "reporting steps stay pending so the report covers what ran; "
                                        "a later plain re-run resumes the deferred skills"})
    return 0


def cmd_finish(a):
    ws = Workspace(a.root)
    runlog = ws.runlog()
    run = current_run(runlog)
    fin = now()
    started = parse_ts(run["started_at"])
    by_phase, by_item = {}, {}
    for ev in run.get("events", []):
        if ev.get("event") == "finish" and ev.get("duration_s") is not None:
            by_phase[ev["phase"]] = round(by_phase.get(ev["phase"], 0) + ev["duration_s"], 3)
            by_item[ev["id"]] = ev["duration_s"]
    counts = {"completed": 0, "failed": 0, "skipped": 0, "pending": 0, "limited_access": 0}
    for it in run["plan"]["items"]:
        if it["type"] != "skill":
            continue
        doc = ws.status(it["id"])[0]
        st = (doc or {}).get("status")
        counts[st if st in counts else "pending"] += 1
        if doc and doc.get("limited_access"):
            counts["limited_access"] += 1
    pend = [i["id"] for i, _ in pending_items(ws, runlog, run)]
    run.update({"finished_at": iso(fin), "duration_s": round((fin - started).total_seconds(), 3),
                "outcome": a.outcome or ("completed" if not pend else "incomplete"),
                "pending_at_finish": pend, "timings": {"by_phase_s": by_phase, "by_item_s": by_item},
                "counts": counts})
    save_json(ws.runlog_path, runlog)
    emit({k: run[k] for k in ("run_id", "started_at", "finished_at", "duration_s", "outcome", "counts",
                              "pending_at_finish", "timings")})
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn):
        p = sub.add_parser(name)
        p.add_argument("--root", default=".")
        p.set_defaults(fn=fn)
        return p

    p = add("init", cmd_init)
    p.add_argument("--profile")
    p.add_argument("--skills")
    p.add_argument("--skill")
    p.add_argument("--multi-tenant", choices=["yes", "no"])
    p.add_argument("--force", action="store_true")
    p.add_argument("--redetect", action="store_true")
    p.add_argument("--non-interactive", action="store_true")
    p.add_argument("--answers", choices=["provided", "interactive", "auto-continued"])
    p.add_argument("--simulate-failure", action="append", default=[])
    p = add("next", cmd_next)
    p.add_argument("--wave", action="store_true")
    p = add("status", cmd_status)
    p.add_argument("--json", action="store_true")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--force", action="store_true")
    p = add("start", cmd_start)
    p.add_argument("id")
    p = add("complete", cmd_complete)
    p.add_argument("id")
    p.add_argument("--reason")
    p.add_argument("--limited", action="append", default=[])
    p = add("fail", cmd_fail)
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p = add("skip", cmd_skip)
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.add_argument("--kind", choices=["user", "deferred", "n/a"], default="user")
    p = add("checkpoint", cmd_checkpoint)
    p.add_argument("id")
    p.add_argument("--answer", required=True)
    p.add_argument("--mode", choices=["interactive", "auto-continued", "provided"], default="interactive")
    p.add_argument("--data")
    p = add("defer", cmd_defer)
    p.add_argument("--reason", required=True)
    p = add("finish", cmd_finish)
    p.add_argument("--outcome")
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
