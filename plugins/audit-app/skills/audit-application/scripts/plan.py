#!/usr/bin/env python3
"""Resolve the ordered audit plan for audit-application from references/profiles.json.

Usage:
    python plan.py [repo_root] [--profile full|security-only|pre-launch|compliance-only|custom]
                   [--skills a,b,c]            # with --profile custom (the audit- prefix is optional)
                   [--skill NAME]              # one skill through the same workspace
                   [--multi-tenant yes|no|unknown]
                   [--simulate-failure NAME]   # test hook: NAME is marked failed instead of invoked
                   [--dry-run] [--json] [--stable] [--out plan.json] [--verbose]

What it does:
  * Reads phases, skills, waves, conditions and profiles from references/profiles.json
    (the data, not this file, defines the plan).
  * Resolves the stack from audit/stack.json when present; otherwise detects it in memory
    with audit-stack-detection ($AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py) and writes
    nothing. File walks use audit-code-scan's repo_walk, so they read the same files as every
    other audit script.
  * Applies the multi-tenant condition (--multi-tenant, else audit/stack.json multi_tenant)
    and the stack applicability rules (backend-only children are n/a on a frontend-only
    repo and vice versa; XSS and accessibility also apply to server-rendered templates).
  * Emits the ordered plan: setup steps, skills per phase and wave, the user checkpoints,
    and the infrastructure steps run by atomic skills (type "action": the endpoint inventory in
    discovery, planned only when a skill that reads it is planned, and the findings rollup in
    reporting). Actions get no status file and are never counted as skills. Skills that will not run stay in the plan with action "skip",
    a kind (out-of-profile | not-multi-tenant | n/a) and a reason, so run_state.py can
    write their status files and the report's scope section stays honest.
  * --dry-run prints the human-readable plan (plus a resume preview when an audit/
    workspace already exists) and writes nothing. --json prints the machine-readable plan.
    --stable drops machine-dependent fields (timestamp, absolute root, tool probe) so the
    output can be compared with a stored expected file.

This script only plans. Child skills are invoked by Claude through the Skill tool or
subagents, as SKILL.md instructs; run_state.py records what happened. Read-only against
the audited code.
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
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


def _load_atomic(skill, filename, module_name):
    """Load a sibling atomic skill's module by file path under a unique name, so a same-named
    script in another skill folder can never be picked up instead."""
    import importlib.util
    path = os.path.join(_SKILLS, skill, "scripts", filename)
    if not os.path.exists(path):
        sys.exit(f"{skill} must be reachable from this skill (audit-core plugin or sibling layout; expected {path})")
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


detect_stack = _load_atomic("audit-stack-detection", "detect_stack.py", "audit_stack_detection_detect_stack")
_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
try:
    _spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _WALK)
    repo_walk = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(repo_walk)
except (FileNotFoundError, AttributeError, ImportError):
    sys.exit("audit-code-scan must be reachable from this skill (audit-core plugin or sibling layout; expected " + _WALK + ")")

PROFILES_PATH = os.path.normpath(os.path.join(HERE, "..", "references", "profiles.json"))
TEMPLATE_EXTS = (".cshtml", ".razor", ".jsp", ".jspx", ".ejs", ".hbs", ".handlebars", ".pug", ".njk",
                 ".ftl", ".erb", ".twig", ".jinja", ".jinja2")
CODE_EXTS = (".cs", ".java", ".kt", ".ts", ".js", ".py")
TENANCY_RE = re.compile(r"\b(TenantId|tenant_id|tenantId|CompanyId|company_id|companyId|OrganizationId|"
                        r"organization_id|organizationId|OrgId|org_id|HasQueryFilter|X-Tenant[-A-Za-z]*)\b")
TOOLS_BY_STACK = {
    "dotnet": ["dotnet"], "java-spring": ["java", "mvn", "gradle"], "node-express": ["node", "npm"],
    "python-django": ["python", "pip-audit"], "angular": ["node", "npm", "npx"], "react": ["node", "npm", "npx"],
    "vue": ["node", "npm", "npx"], "containers": ["docker", "trivy", "hadolint"],
}
COMMON_TOOLS = ["git", "gitleaks", "gh", "pandoc", "k6"]
CHECKPOINT_TEXT = {
    "critical-flows": "confirm the 3-5 critical business flows to trace",
    "security-gate": "show Critical/High findings; ask whether to continue or stop and fix",
}


def load_profiles(path=None):
    with open(path or PROFILES_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def normalize_skill(name, profiles):
    n = (name or "").strip()
    if not n:
        raise ValueError("empty skill name")
    cand = n if n.startswith("audit-") else "audit-" + n
    if cand in profiles["skills"]:
        return cand
    if cand in profiles.get("helpers", {}):
        raise ValueError(f"{cand} is a helper skill, not a pipeline step: {profiles['helpers'][cand]['note']}")
    if cand in profiles.get("infrastructure", {}):
        raise ValueError(f"{cand} is an atomic skill, not a pipeline step you can run with --skill. {profiles['infrastructure'][cand]['note']}")
    matches = [s for s in profiles["skills"] if s.startswith(cand + "-")]
    if len(matches) == 1:  # short forms: authz, secrets, xss-less names like injection
        return matches[0]
    hint = f" (ambiguous: {', '.join(matches)})" if matches else ""
    raise ValueError(f"unknown skill '{name}'{hint}. Known: {', '.join(profiles['skills'])}")


def resolve_stack(root):
    p = os.path.join(root, "audit", "stack.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                return json.load(fh), "audit/stack.json"
        except ValueError:
            pass
    return detect_stack.detect(root), "detected (not written)"


def _walk(root, exts, max_depth=6):
    """repo_walk's shared skip list and size cap, limited to the given extensions."""
    return repo_walk.iter_files(root, exts=set(exts), names=set(), max_depth=max_depth)


def server_templates(root, limit=5):
    """Server-rendered template files make XSS and accessibility applicable without an SPA."""
    hits = []
    for path in _walk(root, TEMPLATE_EXTS + (".html",)):
        rel = repo_walk.rel(root, path)
        low = os.path.basename(path).lower()
        if low.endswith(TEMPLATE_EXTS) or (low.endswith(".html") and "/templates/" in "/" + rel.lower()):
            hits.append(rel)
            if len(hits) >= limit:
                break
    return hits


def tenancy_signals(root, max_files=4000):
    """Hints for the setup question 'is the application multi-tenant?'. Never decides it."""
    tokens, files, seen = {}, [], 0
    for path in _walk(root, CODE_EXTS):
        if not path.endswith(CODE_EXTS):  # extension match is case-sensitive, as before
            continue
        seen += 1
        if seen > max_files:
            break
        text = repo_walk.read_text(path, limit=200_000)
        found = TENANCY_RE.findall(text)
        if found:
            for t in found:
                tokens[t] = tokens.get(t, 0) + 1
            if len(files) < 5:
                files.append(repo_walk.rel(root, path))
    return {"tokens": dict(sorted(tokens.items(), key=lambda kv: -kv[1])), "example_files": files}


def _not_applicable(requires, backend, frontend, templates, any_stack):
    if not any_stack:
        return None  # unknown stack: cannot tell, let the child decide and say so
    if requires == "backend" and not backend:
        return "n/a: no backend stack detected"
    if requires == "frontend" and not frontend:
        return "n/a: no frontend stack detected"
    if requires == "frontend-or-templates" and not frontend and not templates:
        return "n/a: no frontend stack and no server-rendered templates detected"
    return None


def build_plan(root, profile=None, skills=None, single=None, multi_tenant=None, simulate_failure=(),
               profiles=None, stack=None, stack_source=None):
    profiles = profiles or load_profiles()
    known = profiles["skills"]
    if stack is None:
        stack, stack_source = resolve_stack(root)
    warnings = []

    custom = None
    if single:
        single = normalize_skill(single, profiles)
        selected, profile_name = {single}, None
    else:
        profile_name = profile or "full"
        if profile_name not in profiles["profiles"]:
            raise ValueError(f"unknown profile '{profile_name}'. Known: {', '.join(profiles['profiles'])}")
        spec = profiles["profiles"][profile_name]["skills"]
        if profile_name == "custom":
            if not skills:
                raise ValueError("--profile custom needs --skills a,b,c")
            selected = {normalize_skill(s, profiles) for s in skills}
            custom = sorted(selected)
        elif spec == "all":
            selected = set(known)
        else:
            selected = set(spec)
        if profiles.get("reporting_always"):
            selected |= {s for s, m in known.items() if m["phase"] == "reporting"}

    if multi_tenant in ("yes", "no"):
        mt, mt_source = multi_tenant == "yes", "--multi-tenant"
    elif isinstance(stack.get("multi_tenant"), bool):
        mt, mt_source = stack["multi_tenant"], "audit/stack.json"
    else:
        mt, mt_source = None, "unknown (asked at setup)"

    backend, frontend = stack.get("primary_backend"), stack.get("primary_frontend")
    stack_ids = [s.get("id") for s in stack.get("stacks", [])]
    any_stack = bool(stack_ids)
    needs_templates = not frontend and any(known[s]["requires"] == "frontend-or-templates" for s in selected)
    templates = server_templates(root) if needs_templates else []
    if not any_stack:
        warnings.append("no known stack markers found; applicability cannot be decided, every selected skill is planned and will decide for itself")

    sims = set()
    for s in simulate_failure or ():
        sims.add(normalize_skill(s, profiles))

    decisions = {}
    for name, meta in known.items():
        d = {"action": "run", "kind": None, "reason": None}
        if name not in selected:
            d = {"action": "skip", "kind": "out-of-profile", "reason": f"not in scope profile '{profile_name}'"}
        elif meta.get("condition") == "multi_tenant" and mt is False:
            if single:
                warnings.append(f"{name}: application recorded as not multi-tenant; running anyway because it was requested explicitly")
            else:
                d = {"action": "skip", "kind": "not-multi-tenant", "reason": "application is not multi-tenant (setup answer)"}
        elif meta.get("condition") == "multi_tenant" and mt is None and not single:
            d = {"action": "conditional", "kind": "multi-tenant-unknown",
                 "reason": "runs only if the application is multi-tenant (asked at setup)"}
        else:
            na = _not_applicable(meta["requires"], backend, frontend, templates, any_stack)
            if na and single:
                warnings.append(f"{name}: {na}; running anyway because it was requested explicitly")
            elif na:
                d = {"action": "skip", "kind": "n/a", "reason": na}
        decisions[name] = d

    items = []
    for ph in profiles["phases"]:
        pid = ph["id"]
        if pid == "setup":
            if not single:
                for st in ph["steps"]:
                    items.append({"type": "checkpoint" if st.get("type") == "checkpoint" else "setup", "id": st["id"],
                                  "phase": "setup", "action": "run", "text": st["text"]})
            continue
        entries = [(known[n]["wave"], i, "skill", n) for i, n in enumerate(ph.get("skills", []))]
        entries += [(a["wave"], -1, "action", a["id"]) for a in ph.get("actions", [])]
        entries.sort(key=lambda e: (e[0], e[1]))
        phase_items = []
        for wave, _idx, typ, name in entries:
            if typ == "action":
                if single:
                    continue
                act = next(a for a in ph["actions"] if a["id"] == name)
                users = None
                if act.get("needed_by"):
                    users = [s for s in act["needed_by"] if decisions.get(s, {}).get("action") in ("run", "conditional")]
                    if not users:
                        continue  # nothing planned reads this step's output
                ai = {"type": "action", "id": name, "phase": pid, "wave": wave, "action": "run",
                      "skill": act.get("skill"), "text": act["text"]}
                if act.get("derived"):
                    ai["derived"] = True
                if users is not None:
                    ai["needed_by"] = users
                ai["parallel_group"] = None
                phase_items.append(ai)
                continue
            if single and name != single:
                continue
            meta, d = known[name], decisions[name]
            it = {"type": "skill", "id": name, "phase": pid, "wave": wave, "prefix": meta["prefix"],
                  "action": d["action"], "kind": d["kind"], "reason": d["reason"],
                  "parallel_group": f"{pid}-wave{wave}" if ph.get("parallel") else None}
            if meta.get("derived"):
                it["derived"] = True
            if name in sims and it["action"] != "skip":
                it["simulate_failure"] = True
            phase_items.append(it)
        items.extend(phase_items)
        cp = ph.get("checkpoint_after")
        if cp and not single:
            needed = profiles["checkpoints"][cp].get("needed_by")
            pool = needed if needed else [i["id"] for i in phase_items if i["type"] == "skill"]
            users = [s for s in pool if decisions.get(s, {}).get("action") in ("run", "conditional")]
            if users:
                items.append({"type": "checkpoint", "id": cp, "phase": pid, "after_phase": pid, "action": "run",
                              "text": CHECKPOINT_TEXT[cp], "needed_by": users})

    order = 0
    for it in items:
        if it["action"] != "skip":
            order += 1
            it["order"] = order
        else:
            it["order"] = None

    skip_kinds = {}
    for it in items:
        if it["action"] == "skip":
            skip_kinds[it["kind"]] = skip_kinds.get(it["kind"], 0) + 1
    tools = {}
    for sid in stack_ids + ["common"]:
        for t in (COMMON_TOOLS if sid == "common" else TOOLS_BY_STACK.get(sid, [])):
            tools[t] = bool(shutil.which(t))

    return {
        "plan_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": os.path.abspath(root),
        "mode": "single-skill" if single else "profile",
        "profile": profile_name,
        "profile_description": profiles["profiles"][profile_name]["description"] if profile_name else None,
        "custom_skills": custom,
        "single_skill": single,
        "multi_tenant": mt,
        "multi_tenant_source": mt_source,
        "tenancy_signals": tenancy_signals(root) if (mt is None and not single) else None,
        "stack": {"source": stack_source, "primary_backend": backend, "primary_frontend": frontend,
                  "stacks": stack_ids, "server_templates": templates},
        "simulate_failure": sorted(sims),
        "items": items,
        "counts": {
            "skills_run": sum(1 for i in items if i["type"] == "skill" and i["action"] == "run"),
            "skills_conditional": sum(1 for i in items if i["type"] == "skill" and i["action"] == "conditional"),
            "skills_skipped": skip_kinds,
            "checkpoints": [i["id"] for i in items if i["type"] == "checkpoint"],
        },
        "warnings": warnings,
        "tools_on_path": tools,
    }


def stable(plan):
    p = dict(plan)
    for k in ("generated_at", "root", "tools_on_path"):
        p.pop(k, None)
    return p


def format_text(plan, profiles, verbose=False, dry_run=False, preview=None):
    L = []
    L.append("audit-application plan" + ("  [DRY RUN - nothing is executed or written]" if dry_run else ""))
    L.append(f"Repo:          {plan['root']}")
    if plan["mode"] == "single-skill":
        L.append(f"Mode:          single skill ({plan['single_skill']}) through the existing audit/ workspace")
    else:
        L.append(f"Profile:       {plan['profile']} - {plan['profile_description']}")
    mt = {True: "yes", False: "no", None: "unknown"}[plan["multi_tenant"]]
    L.append(f"Multi-tenant:  {mt}  (source: {plan['multi_tenant_source']})")
    st = plan["stack"]
    L.append(f"Stack:         backend {st['primary_backend'] or '-'}, frontend {st['primary_frontend'] or '-'}"
             f"  [{', '.join(st['stacks']) or 'none detected'}]  ({st['source']})")
    if plan.get("tenancy_signals") and plan["tenancy_signals"]["tokens"]:
        toks = ", ".join(f"{k} x{v}" for k, v in list(plan["tenancy_signals"]["tokens"].items())[:6])
        L.append(f"Tenancy hints: {toks} (e.g. {', '.join(plan['tenancy_signals']['example_files'][:3])})")
    if plan["simulate_failure"]:
        L.append(f"Simulated failure (test hook): {', '.join(plan['simulate_failure'])}")
    for w in plan["warnings"]:
        L.append(f"WARNING: {w}")
    L.append("")

    titles = {p["id"]: (p["number"], p["title"], p.get("parallel")) for p in profiles["phases"]}
    by_phase = {}
    for it in plan["items"]:
        by_phase.setdefault(it["phase"], []).append(it)
    for ph in profiles["phases"]:
        pid = ph["id"]
        num, title, parallel = titles[pid]
        rows = [i for i in by_phase.get(pid, []) if i["action"] != "skip"]
        if plan["mode"] == "single-skill" and not rows:
            continue
        head = f"Phase {num} - {title}"
        if parallel and sum(1 for i in rows if i["type"] == "skill") > 1:
            head += "  (independent within a wave: parallel subagents where available, otherwise sequential in this order)"
        elif pid == "reporting":
            head += "  (sequential)"
        L.append(head)
        skills = [i for i in rows if i["type"] == "skill"]
        if pid not in ("setup", "reporting") and not skills:
            L.append("       (no skills from this phase in this plan)")
        waves = sorted({i["wave"] for i in skills})
        wave_no = {w: n for n, w in enumerate(waves, 1)}
        last_wave = None
        for it in rows:
            if it["type"] == "setup":
                L.append(f"  {it['order']:>3}. {it['text']}")
            elif it["type"] == "checkpoint":
                extra = f" (used by {', '.join(it['needed_by'])})" if it.get("needed_by") and pid == "discovery" else ""
                L.append(f"  {it['order']:>3}. [checkpoint] {it['id']} - {it['text']}{extra}")
            elif it["type"] == "action":
                used = f" (used by {', '.join(it['needed_by'])})" if it.get("needed_by") else ""
                L.append(f"  {it['order']:>3}. [infrastructure: {it.get('skill') or it['id']}] {it['text']}{used}")
            else:
                tag = ""
                if parallel and len(waves) > 1 and it["wave"] != last_wave:
                    L.append(f"       wave {wave_no[it['wave']]}:")
                last_wave = it["wave"]
                if it["action"] == "conditional":
                    tag = f"  [conditional: {it['reason']}]"
                if it.get("simulate_failure"):
                    tag += "  [simulated failure]"
                L.append(f"  {it['order']:>3}. {it['id']:<40} {it['prefix']}{tag}")
        L.append("")

    skipped = [i for i in plan["items"] if i["action"] == "skip"]
    if skipped:
        L.append(f"Not run ({len(skipped)} skills; each gets audit/status/<skill>.json = skipped with the reason):")
        kinds = {}
        for i in skipped:
            kinds.setdefault(i["kind"], []).append(i)
        for kind, rows in kinds.items():
            if kind == "out-of-profile" and not verbose:
                L.append(f"  - out-of-profile: {len(rows)} skills (--verbose lists them)")
            else:
                for i in rows:
                    L.append(f"  - {i['id']}: {i['reason']}")
        L.append("")
    if plan["mode"] != "single-skill":
        L.append("Checkpoints are user pauses. In non-interactive runs they are not skipped: the documented default is")
        L.append("applied and recorded in audit/run-log.json with mode \"auto-continued\".")
    missing = [t for t, ok in plan.get("tools_on_path", {}).items() if not ok]
    if missing:
        L.append(f"Tools not on PATH (children record the gap as limited access / not checked): {', '.join(missing)}")
    if preview:
        L.append("")
        L.append(preview)
    return "\n".join(L)


def resume_preview(root, force=False):
    runlog = os.path.join(root, "audit", "run-log.json")
    if not os.path.exists(runlog):
        return None
    try:
        import run_state  # lazy: run_state imports this module
        return run_state.preview_text(root, force=force)
    except Exception as e:  # preview is advisory; never fail a dry run on it
        return f"Resume preview unavailable: {e}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--skills", default=None, help="comma-separated list for --profile custom")
    ap.add_argument("--skill", default=None, help="plan a single skill")
    ap.add_argument("--multi-tenant", choices=["yes", "no", "unknown"], default=None)
    ap.add_argument("--simulate-failure", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stable", action="store_true")
    ap.add_argument("--force", action="store_true", help="resume preview as if --force were passed")
    ap.add_argument("--out", default=None)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    profiles = load_profiles()
    skills = [s for s in (a.skills or "").split(",") if s.strip()] or None
    profile = a.profile
    if skills and not profile and not a.skill:
        profile = "custom"
    try:
        plan = build_plan(a.root, profile=profile, skills=skills, single=a.skill,
                          multi_tenant=a.multi_tenant, simulate_failure=a.simulate_failure, profiles=profiles)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    doc = stable(plan) if a.stable else plan
    if a.out and not a.dry_run:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
    if a.json:
        print(json.dumps(doc, indent=2))
    else:
        print(format_text(plan, profiles, verbose=a.verbose, dry_run=a.dry_run,
                          preview=resume_preview(a.root, a.force) if a.dry_run else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
