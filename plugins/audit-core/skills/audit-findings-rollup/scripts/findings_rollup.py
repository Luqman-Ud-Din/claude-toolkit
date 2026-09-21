#!/usr/bin/env python3
"""Roll every audit/findings/*.json and audit/status/*.json up into one view: findings
de-duplicated by root_cause_key, severity counts, the Critical/High list, risk-accepted
findings, skills that did not run cleanly, and the go/no-go verdict.

Usage:
    python findings_rollup.py rollup  [repo_root] [--audit-dir DIR] [--accepted FILE] [--as-of YYYY-MM-DD]
                                      [--expected skill-a,skill-b] [--out-dir DIR] [--print]
    python findings_rollup.py verdict [repo_root] [--audit-dir DIR] [--accepted FILE] [--as-of YYYY-MM-DD]
                                      [--expected ...] [--text]
    python findings_rollup.py counts  [repo_root] [--audit-dir DIR] [--accepted FILE] [--as-of YYYY-MM-DD]
    python findings_rollup.py dedupe  <findings.json> [--key root_cause_key|title] [--write] [--json]

rollup   writes audit/evidence/audit-findings-rollup/rollup.json and rollup.md (or --out-dir).
         It refuses to write anywhere inside audit/findings/.
verdict  prints the verdict object only; writes nothing.
counts   prints raw / de-duplicated / open severity counts; writes nothing.
dedupe   merges findings sharing root_cause_key inside ONE findings file. Without --write it
         only prints what it would merge; --write rewrites that same file (merged findings and
         a recomputed summary). It never creates a file.

Verdict rule (one function, verdict()):
    NO-GO           any open Critical or High finding
    CONDITIONAL GO  only Medium or Low findings are open
    GO              nothing above Info is open
    "Open" excludes confidence false-positive and findings covered by a valid, unexpired risk
    acceptance. Failed, skipped, limited-access and not-run skills and unreadable files never
    change the verdict word; each adds a caveat naming them.

Risk acceptance (--accepted): a JSON list of {"id", "accepted_by", "date", "reason"} records,
optionally with "expires" (YYYY-MM-DD). All four fields are required; an "expires" earlier than
--as-of (default: today, UTC) makes the record expired. A merged finding is covered only when
every id in it is covered.

Importable: load_findings, load_status, load_acceptances, merge_by_root_cause, severity_counts,
critical_high, skill_summary, verdict, rollup, render_md, write_rollup.
Python 3 standard library only. Read-only against the audited repository.
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import date, datetime, timezone

TOOL = "audit-findings-rollup"
SCHEMA_VERSION = 1
SEVERITIES = ["Critical", "High", "Medium", "Low", "Info"]
ORDER = {s: i for i, s in enumerate(SEVERITIES)}
FALSE_POSITIVE = "false-positive"
ACCEPTANCE_REQUIRED = ("id", "accepted_by", "date", "reason")
NO_GO, CONDITIONAL_GO, GO = "NO-GO", "CONDITIONAL GO", "GO"
OUT_SUBDIR = os.path.join("evidence", TOOL)


# --------------------------------------------------------------------------- helpers
def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh), None
    except (OSError, ValueError) as exc:
        return None, str(exc)


def _rank(sev):
    return ORDER.get(sev, len(SEVERITIES))


def _norm_sev(sev):
    return sev if sev in ORDER else "Info"


def _zero():
    return {s: 0 for s in SEVERITIES}


def _is_fp(f):
    return f.get("confidence") == FALSE_POSITIVE


def _display(path):
    """audit/<folder>/<name> when the path sits in an audit workspace, else the path as given."""
    p = os.path.normpath(path)
    parent = os.path.dirname(p)
    if os.path.basename(os.path.dirname(parent)) == "audit":
        return "audit/%s/%s" % (os.path.basename(parent), os.path.basename(p))
    return p.replace(os.sep, "/")


def location_str(f, symbol=False):
    """file[:line][ (symbol)]; file defaults to '.'."""
    loc = f.get("location") if isinstance(f.get("location"), dict) else {}
    s = str(loc.get("file") or ".")
    if loc.get("line") not in (None, ""):
        s += ":%s" % loc["line"]
    if symbol and loc.get("symbol"):
        s += " (%s)" % loc["symbol"]
    return s


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def resolve_audit_dir(source="."):
    """Accept a repo root or an audit/ directory; return the audit/ directory."""
    if os.path.basename(os.path.normpath(source)) == "audit":
        return source
    return os.path.join(source, "audit")


def _resolve_dir(source, folder):
    if isinstance(source, (list, tuple)) or os.path.isfile(source):
        return None
    if os.path.isdir(os.path.join(source, "audit", folder)):
        return os.path.join(source, "audit", folder)
    if os.path.basename(os.path.normpath(source)) == "audit":
        return os.path.join(source, folder)
    return source


def _as_of(value=None):
    if value is None:
        return datetime.now(timezone.utc).date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _parse_date(value):
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _ids_of(f):
    extra = f.get("extra") if isinstance(f.get("extra"), dict) else {}
    ids = [f.get("id")]
    for i in extra.get("merged_ids") or []:
        if i not in ids:
            ids.append(i)
    return [i for i in ids if i]


# --------------------------------------------------------------------------- loading
def load_findings(source=".", skip_underscore=True, exclude_skills=()):
    """Load findings from a repo root, an audit/ dir, a findings dir, one file or a list of files.

    Returns {"sources", "documents", "findings", "parse_errors", "ignored_files"}. Every finding
    is a shallow copy with "skill" and "source_file" added; "documents" keeps each raw document
    (mutable, with its absolute "path") for consumers that write back to their own files.
    Underscore-prefixed files are ignored only when a directory is globbed.
    """
    d = _resolve_dir(source, "findings")
    if isinstance(source, (list, tuple)):
        paths = list(source)
    elif d is None:
        paths = [source]
    else:
        paths = sorted(glob.glob(os.path.join(d, "*.json")))
    exclude = set(exclude_skills or ())
    out = {"sources": [], "documents": [], "findings": [], "parse_errors": [], "ignored_files": []}
    for p in paths:
        shown = _display(p)
        if d is not None and skip_underscore and os.path.basename(p).startswith("_"):
            out["ignored_files"].append({"file": shown, "reason": "underscore-prefixed file"})
            continue
        doc, err = _read_json(p)
        if err is None and not isinstance(doc, dict):
            err = "top level is not an object"
        if err:
            out["parse_errors"].append({"file": shown, "error": err})
            continue
        skill = doc.get("skill") or os.path.splitext(os.path.basename(p))[0]
        if skill in exclude:
            out["ignored_files"].append({"file": shown, "reason": "skill %s excluded by caller" % skill})
            continue
        found = [f for f in (doc.get("findings") or []) if isinstance(f, dict)]
        out["sources"].append({"file": shown, "skill": skill, "findings": len(found),
                               "has_findings_array": isinstance(doc.get("findings"), list)})
        out["documents"].append({"path": os.path.abspath(p), "file": shown, "skill": skill, "doc": doc})
        for f in found:
            c = dict(f)
            c["skill"] = skill
            c["source_file"] = shown
            out["findings"].append(c)
    return out


def load_status(source="."):
    """Load audit/status/*.json. Returns {"skills": {name: record}, "sources", "parse_errors"}.

    record: skill, status (string or None), reason, skip_kind, skipped_by, limited_access (list),
    started_at, finished_at, file, raw (the document as written).
    """
    d = _resolve_dir(source, "status")
    if isinstance(source, (list, tuple)):
        paths = list(source)
    elif d is None:
        paths = [source]
    else:
        paths = sorted(glob.glob(os.path.join(d, "*.json")))
    out = {"skills": {}, "sources": [], "parse_errors": []}
    for p in paths:
        shown = _display(p)
        doc, err = _read_json(p)
        if err is None and not isinstance(doc, dict):
            err = "top level is not an object"
        if err:
            out["parse_errors"].append({"file": shown, "error": err})
            continue
        name = doc.get("skill") or os.path.splitext(os.path.basename(p))[0]
        reason = doc.get("reason")
        limited = doc.get("limited_access")
        if isinstance(limited, str):
            limited = [limited]
        limited = [str(x) for x in (limited or [])]
        if not limited and isinstance(reason, str) and reason.lower().startswith("limited access:"):
            limited = [reason.split(":", 1)[1].strip()]
        out["skills"][name] = {"skill": name, "status": doc.get("status"), "reason": reason or None,
                               "skip_kind": doc.get("skip_kind"), "skipped_by": doc.get("skipped_by"),
                               "limited_access": limited, "started_at": doc.get("started_at"),
                               "finished_at": doc.get("finished_at"), "file": shown, "raw": doc}
        out["sources"].append({"file": shown, "skill": name, "status": doc.get("status")})
    return out


def load_acceptances(source=None, as_of=None):
    """Validate risk-acceptance records. source: a path to a JSON list, a list of records, or None.

    Returns {"file", "as_of", "valid": [...], "expired": [...], "invalid": [...], "parse_error"}.
    Valid needs every field in ACCEPTANCE_REQUIRED non-empty and, when "expires" is present, a
    date on or after as_of. A later valid record for the same id replaces an earlier one.
    """
    if isinstance(source, dict) and "valid" in source:  # already loaded
        return source
    day = _as_of(as_of)
    res = {"file": None, "as_of": day.isoformat(), "valid": [], "expired": [], "invalid": [], "parse_error": None}
    records = source
    if isinstance(source, str):
        res["file"] = source.replace(os.sep, "/")
        if not os.path.exists(source):
            res["parse_error"] = "file not found"
            return res
        records, err = _read_json(source)
        if err:
            res["parse_error"] = err
            return res
    if records is None:
        return res
    if not isinstance(records, list):
        res["parse_error"] = "top level is not a list of acceptance records"
        return res
    valid = {}
    for r in records:
        if not isinstance(r, dict):
            res["invalid"].append({"record": r, "why": "not an object"})
            continue
        missing = [k for k in ACCEPTANCE_REQUIRED if not r.get(k)]
        if missing:
            res["invalid"].append({"record": r, "why": "missing " + ", ".join(missing)})
            continue
        if r.get("expires"):
            exp = _parse_date(r["expires"])
            if exp is None:
                res["invalid"].append({"record": r, "why": "expires is not a YYYY-MM-DD date"})
                continue
            if exp < day:
                res["expired"].append({"record": r, "why": "expired %s (as of %s)" % (exp.isoformat(), day.isoformat())})
                continue
        valid[r["id"]] = r
    res["valid"] = list(valid.values())
    return res


# --------------------------------------------------------------------------- merging
def _starts_with_location(evidence, head):
    """True when the evidence text already begins with exactly this file:line (not the same
    prefix followed by more digits), so the merged evidence does not repeat the location."""
    if not isinstance(evidence, str):
        return False
    text = evidence.lstrip()
    return text.startswith(head) and not text[len(head):len(head) + 1].isdigit()


def _merge_group(group):
    members = sorted(group, key=lambda f: _rank(f.get("severity")))  # stable: ties keep input order
    base = dict(members[0])
    extra = dict(base["extra"]) if isinstance(base.get("extra"), dict) else {}
    ids, locations, refs, tags, evidence, merged_members = [], [], [], [], [], []
    for f in members:
        fx = f.get("extra") if isinstance(f.get("extra"), dict) else {}
        loc = f.get("location") if isinstance(f.get("location"), dict) else {}
        for i in [f.get("id")] + list(fx.get("merged_ids") or []):
            if i not in ids:
                ids.append(i)
        if isinstance(fx.get("locations"), list) and fx.get("locations"):
            locations.extend(fx["locations"])          # already merged earlier: keep its record
            evidence.append(str(f.get("evidence", "")).strip())
        else:
            locations.append(loc)
            head = "%s:%s" % (loc.get("file") or ".", loc.get("line", ""))
            if _starts_with_location(f.get("evidence"), head):
                evidence.append(f["evidence"].strip())     # already opens with its own file:line
            else:
                evidence.append(("%s\n%s" % (head, f.get("evidence", ""))).strip())
        for r in f.get("references") or []:
            if r not in refs:
                refs.append(r)
        for t in f.get("tags") or []:
            if t not in tags:
                tags.append(t)
        m = {"id": f.get("id"), "severity": f.get("severity"), "title": f.get("title"), "location": location_str(f)}
        if f.get("skill"):
            m = dict({"skill": f["skill"]}, **m)
        merged_members.append(m)
    base["references"] = refs
    base["tags"] = tags
    base["evidence"] = "\n\n".join(evidence)
    extra["merged_ids"] = ids
    extra["locations"] = locations
    extra["primary_evidence"] = members[0].get("evidence")
    extra["merged_members"] = merged_members
    base["extra"] = extra
    return base


def merge_by_root_cause(findings, key="root_cause_key"):
    """Merge findings that share a non-empty root_cause_key (or, key="title", a normalised title).

    Works on one file's findings or on many skills' findings. False positives and findings with
    no key pass through unmerged. The merged finding is a copy of the highest-severity member
    (ties: first in input order), so its severity is the group's highest; every id, location,
    reference, tag and evidence text is kept. Output keeps input order (a group sits where its
    first member was).
    """
    groups, order = {}, []
    for f in findings:
        if not isinstance(f, dict):
            continue
        k = None
        if not _is_fp(f):
            k = norm_title(f.get("title")) if key == "title" else f.get("root_cause_key")
        if not k:
            order.append((None, f))
            continue
        if k not in groups:
            groups[k] = []
            order.append((k, None))
        groups[k].append(f)
    out = []
    for k, f in order:
        if k is None:
            out.append(f)
        else:
            g = groups[k]
            out.append(g[0] if len(g) == 1 else _merge_group(g))
    return out


def merge_report(findings, key="root_cause_key"):
    """[(key, [ids in input order])] for every group that would merge."""
    groups = {}
    for f in findings:
        if not isinstance(f, dict) or _is_fp(f):
            continue
        k = norm_title(f.get("title")) if key == "title" else f.get("root_cause_key")
        if k:
            groups.setdefault(k, []).append(f.get("id"))
    return [(k, ids) for k, ids in groups.items() if len(ids) > 1]


# --------------------------------------------------------------------------- facts
def severity_counts(findings):
    """Counts by severity, false positives excluded; unknown severities count as Info."""
    c = _zero()
    for f in findings:
        if isinstance(f, dict) and not _is_fp(f):
            c[_norm_sev(f.get("severity"))] += 1
    return c


def acceptance_coverage(finding, acceptances):
    """{"status": accepted|partial|expired|none, "records", "expired", "uncovered_ids"}."""
    acc = acceptances or {"valid": [], "expired": []}
    valid = {r["id"]: r for r in acc.get("valid", [])}
    expired = {}
    for e in acc.get("expired", []):
        expired.setdefault(e["record"]["id"], e["record"])
    ids = _ids_of(finding)
    covered = [i for i in ids if i in valid]
    uncovered = [i for i in ids if i not in valid]
    if ids and not uncovered:
        status = "accepted"
    elif covered:
        status = "partial"
    elif any(i in expired for i in ids):
        status = "expired"
    else:
        status = "none"
    return {"status": status, "records": [valid[i] for i in covered],
            "expired": [expired[i] for i in ids if i in expired and i not in valid], "uncovered_ids": uncovered}


def _row(f, acceptances):
    cov = acceptance_coverage(f, acceptances)
    return {"id": f.get("id"), "skill": f.get("skill"), "severity": _norm_sev(f.get("severity")),
            "title": f.get("title"), "location": location_str(f), "confidence": f.get("confidence", "confirmed"),
            "root_cause_key": f.get("root_cause_key"),
            "merged_ids": [i for i in _ids_of(f) if i != f.get("id")],
            "open": cov["status"] != "accepted", "acceptance": cov}


def critical_high(findings, acceptances=None, skills=None):
    """Critical and High findings (false positives excluded), accepted ones included and flagged.

    Pass merged findings for the de-duplicated list, raw findings for one row per finding;
    skills limits rows to those skill names. Sorted by severity, skill, id.
    """
    acc = load_acceptances(acceptances)
    wanted = set(skills) if skills else None
    rows = [_row(f, acc) for f in findings
            if isinstance(f, dict) and not _is_fp(f) and f.get("severity") in ("Critical", "High")
            and (wanted is None or f.get("skill") in wanted)]
    rows.sort(key=lambda r: (ORDER[r["severity"]], str(r["skill"]), str(r["id"])))
    return rows


def skill_summary(findings_load, status_load, expected=None):
    """Per-skill state from load_findings() and load_status(). expected: names that should have run."""
    status = status_load.get("skills", {})
    files = {}
    for s in findings_load.get("sources", []):
        files.setdefault(s["skill"], s["file"])
    names = sorted(set(files) | set(status) | set(expected or []))
    res = {"by_skill": [], "completed": [], "failed": [], "skipped": [], "limited_access": [], "not_run": [],
           "other_status": [], "no_status_file": [],
           "unreadable": list(findings_load.get("parse_errors", [])) + list(status_load.get("parse_errors", []))}
    live = [f for f in findings_load.get("findings", []) if not _is_fp(f)]
    for n in names:
        st = status.get(n)
        mine = [f for f in live if f.get("skill") == n]
        res["by_skill"].append({
            "skill": n, "status": st["status"] if st else None, "reason": st["reason"] if st else None,
            "skip_kind": st["skip_kind"] if st else None, "limited_access": st["limited_access"] if st else [],
            "status_file": st["file"] if st else None, "findings_file": files.get(n),
            "counts_raw": severity_counts(mine),
            "critical_high_ids": [f.get("id") for f in mine if f.get("severity") in ("Critical", "High")]})
        if st is None:
            if n in files:
                res["no_status_file"].append(n)
            else:
                res["not_run"].append({"skill": n, "reason": "no status file and no findings file"})
            continue
        s = st["status"]
        if s == "completed":
            res["completed"].append(n)
            if st["limited_access"]:
                res["limited_access"].append({"skill": n, "reason": st["reason"], "items": st["limited_access"]})
        elif s == "failed":
            res["failed"].append({"skill": n, "reason": st["reason"]})
        elif s == "skipped":
            res["skipped"].append({"skill": n, "reason": st["reason"], "skip_kind": st["skip_kind"],
                                   "skipped_by": st["skipped_by"]})
        else:
            res["other_status"].append({"skill": n, "status": s, "reason": st["reason"]})
    return res


# --------------------------------------------------------------------------- verdict
def verdict(findings, acceptances=None, skills=None):
    """The go/no-go rule. The only place the verdict word is decided.

    findings: merged findings for de-duplicated counts (raw findings work too). acceptances: a
    path, a list of records, or a load_acceptances() result. skills: a skill_summary() result,
    used for caveats only - it never changes the verdict word.
    """
    acc = load_acceptances(acceptances)
    open_counts, accepted_counts, blockers = _zero(), _zero(), []
    for f in findings:
        if not isinstance(f, dict) or _is_fp(f):
            continue
        sev = _norm_sev(f.get("severity"))
        row = _row(f, acc)
        if row["open"]:
            open_counts[sev] += 1
            if sev in ("Critical", "High"):
                b = {k: row[k] for k in ("id", "skill", "severity", "title", "location", "merged_ids")}
                b["acceptance"] = row["acceptance"]["status"]
                blockers.append(b)
        else:
            accepted_counts[sev] += 1
    blockers.sort(key=lambda r: (ORDER[r["severity"]], str(r["skill"]), str(r["id"])))
    c = open_counts
    if c["Critical"] or c["High"]:
        word = NO_GO
        reason = "%d Critical and %d High findings are open." % (c["Critical"], c["High"])
    elif c["Medium"] or c["Low"]:
        word = CONDITIONAL_GO
        reason = "No open Critical or High findings; %d Medium and %d Low are open." % (c["Medium"], c["Low"])
    else:
        word = GO
        reason = "No open findings above Info."
    ch_acc = accepted_counts["Critical"] + accepted_counts["High"]
    if ch_acc:
        reason += " %d Critical/High finding(s) are covered by a valid risk acceptance." % ch_acc
    caveats = []
    sk = skills or {}
    if sk.get("failed"):
        caveats.append("Failed: %s. The verdict does not cover these areas." % ", ".join(x["skill"] for x in sk["failed"]))
    if sk.get("not_run"):
        caveats.append("Not run: %s." % ", ".join(x["skill"] for x in sk["not_run"]))
    if sk.get("skipped"):
        caveats.append("Skipped: %s." % ", ".join(x["skill"] for x in sk["skipped"]))
    if sk.get("other_status"):
        caveats.append("Did not finish: %s." % ", ".join("%s (%s)" % (x["skill"], x["status"]) for x in sk["other_status"]))
    if sk.get("limited_access"):
        caveats.append("Limited access: %s." % ", ".join(x["skill"] for x in sk["limited_access"]))
    if sk.get("unreadable"):
        caveats.append("Unreadable files: %s." % ", ".join(x["file"] for x in sk["unreadable"]))
    if acc.get("expired"):
        caveats.append("Expired risk acceptances not applied: %s." % ", ".join(str(e["record"]["id"]) for e in acc["expired"]))
    return {"verdict": word, "reason": reason, "caveats": caveats, "open": open_counts,
            "accepted": accepted_counts, "blockers": blockers}


# --------------------------------------------------------------------------- rollup
def _expected_from_plan(audit_dir):
    plan, err = _read_json(os.path.join(audit_dir, "plan.json"))
    if err or not isinstance(plan, dict):
        return None
    return [i["id"] for i in plan.get("items", [])
            if isinstance(i, dict) and i.get("type") == "skill" and i.get("action") != "skip"]


def rollup(source=".", acceptances=None, expected=None, as_of=None):
    """Build the full rollup document for a repo root or audit/ dir. Writes nothing."""
    audit_dir = resolve_audit_dir(source)
    day = _as_of(as_of)
    fl = load_findings(os.path.join(audit_dir, "findings"))
    sl = load_status(os.path.join(audit_dir, "status"))
    expected_source = "caller" if expected is not None else None
    if expected is None:
        expected = _expected_from_plan(audit_dir)
        expected_source = "audit/plan.json" if expected is not None else None
    acc = load_acceptances(acceptances, day)
    live = [f for f in fl["findings"] if not _is_fp(f)]
    fps = [f for f in fl["findings"] if _is_fp(f)]
    merged = merge_by_root_cause(live)
    for f in merged:
        cov = acceptance_coverage(f, acc)
        f["open"] = cov["status"] != "accepted"
        f["acceptance"] = cov
    merged.sort(key=lambda f: (_rank(f.get("severity")), 0 if f.get("confidence", "confirmed") == "confirmed" else 1,
                               str(f.get("id")), str(f.get("skill"))))
    by_key = {}
    for f in live:
        if f.get("root_cause_key"):
            by_key.setdefault(f["root_cause_key"], []).append(f)
    groups = []
    for k, g in by_key.items():
        if len(g) < 2:
            continue
        primary = sorted(g, key=lambda f: _rank(f.get("severity")))[0]
        sk = sorted({str(f.get("skill")) for f in g})
        groups.append({"root_cause_key": k, "severity": _norm_sev(primary.get("severity")),
                       "primary": {"skill": primary.get("skill"), "id": primary.get("id")},
                       "members": [{"skill": f.get("skill"), "id": f.get("id"), "severity": f.get("severity"),
                                    "title": f.get("title"), "location": location_str(f)} for f in g],
                       "skills": sk, "cross_skill": len(sk) > 1})
    skills = skill_summary(fl, sl, expected)
    for e in skills["by_skill"]:
        e["counts_rollup"] = severity_counts([f for f in merged if f.get("skill") == e["skill"]])
    v = verdict(merged, acc, skills)
    accepted_rows = [_row(f, acc) for f in merged if not f["open"]]
    matched = {i for f in merged for i in _ids_of(f)}
    return {
        "tool": TOOL, "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(), "as_of": day.isoformat(),
        "audit_dir": os.path.abspath(audit_dir).replace(os.sep, "/"),
        "sources": {"findings": fl["sources"], "status": sl["sources"], "acceptances": acc["file"],
                    "expected_skills": expected, "expected_source": expected_source},
        "parse_errors": fl["parse_errors"] + sl["parse_errors"] + (
            [{"file": acc["file"], "error": acc["parse_error"]}] if acc["parse_error"] else []),
        "ignored_files": fl["ignored_files"],
        "summary": {"raw": severity_counts(live), "deduplicated": severity_counts(merged), "open": v["open"],
                    "merged": len(live) - len(merged), "false_positives": len(fps),
                    "cross_skill_groups": sum(1 for g in groups if g["cross_skill"]),
                    "risk_accepted": len(accepted_rows)},
        "verdict": v,
        "critical_high": critical_high(merged, acc),
        "risk_accepted": accepted_rows,
        "acceptances": {"valid": acc["valid"], "expired": acc["expired"], "invalid": acc["invalid"],
                        "unmatched": [r for r in acc["valid"] if r["id"] not in matched]},
        "skills": skills,
        "groups": groups,
        "findings": merged,
        "false_positives": [{"skill": f.get("skill"), "id": f.get("id"), "severity": f.get("severity"),
                             "title": f.get("title"), "location": location_str(f), "impact": f.get("impact")}
                            for f in fps],
    }


def _cell(v):
    return str(v if v not in (None, "") else "-").replace("|", "/").replace("\n", " ")


def render_md(doc):
    """rollup.md from a rollup() document."""
    v, s = doc["verdict"], doc["summary"]
    L = ["# Audit findings rollup", "", "**Recommendation: %s.** %s" % (v["verdict"], v["reason"]), ""]
    if v["caveats"]:
        L += ["Caveats (they never change the verdict word):", ""] + ["- " + c for c in v["caveats"]] + [""]
    L += ["As of %s. Sources: %d findings file(s), %d status file(s); risk acceptances: %s." % (
        doc["as_of"], len(doc["sources"]["findings"]), len(doc["sources"]["status"]),
        doc["sources"]["acceptances"] or "none"), "",
        "## Severity counts", "", "| Count | " + " | ".join(SEVERITIES) + " |", "|---|---|---|---|---|---|"]
    for label, key in (("Raw (false positives excluded)", "raw"), ("After de-duplication", "deduplicated"),
                       ("Open (after risk acceptance)", "open")):
        L.append("| %s | %s |" % (label, " | ".join(str(s[key][x]) for x in SEVERITIES)))
    L += ["", "Merged: %d (%d cross-skill group(s)). False positives excluded: %d. Risk-accepted: %d." % (
        s["merged"], s["cross_skill_groups"], s["false_positives"], s["risk_accepted"]), "",
        "## Critical and High findings", ""]
    if doc["critical_high"]:
        L += ["| Id | Severity | Skill | Title | Location | Confidence | State |", "|---|---|---|---|---|---|---|"]
        for r in doc["critical_high"]:
            a = r["acceptance"]
            if not r["open"]:
                state = "accepted"
            elif a["status"] == "expired":
                state = "OPEN (acceptance expired)"
            elif a["status"] == "partial":
                state = "OPEN (acceptance misses %s)" % ", ".join(str(i) for i in a["uncovered_ids"])
            else:
                state = "OPEN"
            ids = str(r["id"]) + (" (+%s)" % ", ".join(str(i) for i in r["merged_ids"]) if r["merged_ids"] else "")
            L.append("| %s |" % " | ".join(_cell(x) for x in (ids, r["severity"], r["skill"], r["title"],
                                                            "`%s`" % r["location"], r["confidence"], state)))
    else:
        L.append("None.")
    L += ["", "## Risk-accepted findings", ""]
    if doc["risk_accepted"]:
        L += ["| Id | Severity | Skill | Title | Accepted by | Date | Expires | Reason |", "|---|---|---|---|---|---|---|---|"]
        for r in doc["risk_accepted"]:
            for rec in r["acceptance"]["records"]:
                L.append("| %s |" % " | ".join(_cell(x) for x in (rec["id"], r["severity"], r["skill"], r["title"],
                                                                rec["accepted_by"], rec["date"], rec.get("expires"),
                                                                rec["reason"])))
    else:
        L.append("None.")
    acc = doc["acceptances"]
    if acc["expired"] or acc["invalid"] or acc["unmatched"]:
        L += ["", "Acceptance records not applied:", ""]
        L += ["- %s: %s" % (e["record"].get("id"), e["why"]) for e in acc["expired"]]
        L += ["- %s: invalid, %s" % (e["record"].get("id") if isinstance(e["record"], dict) else e["record"], e["why"])
              for e in acc["invalid"]]
        L += ["- %s: valid but matches no finding" % r["id"] for r in acc["unmatched"]]
    sk = doc["skills"]
    L += ["", "## Skills not run, failed, skipped or with limited access", ""]
    rows = ([(x["skill"], "failed", x["reason"]) for x in sk["failed"]]
            + [(x["skill"], "not run", x["reason"]) for x in sk["not_run"]]
            + [(x["skill"], "status " + str(x["status"]), x["reason"]) for x in sk["other_status"]]
            + [(x["skill"], "skipped" + (" (%s)" % x["skip_kind"] if x["skip_kind"] else ""), x["reason"]) for x in sk["skipped"]]
            + [(x["skill"], "limited access", "; ".join(x["items"])) for x in sk["limited_access"]]
            + [(x["file"], "unreadable", x["error"]) for x in sk["unreadable"]])
    if rows:
        L += ["| Skill | State | Reason |", "|---|---|---|"] + ["| %s |" % " | ".join(_cell(c) for c in r) for r in rows]
    else:
        L.append("None: every known skill completed with full access.")
    L += ["", "## Merged root causes", ""]
    if doc["groups"]:
        L += ["| root_cause_key | Severity | Primary | Members | Cross-skill |", "|---|---|---|---|---|"]
        for g in doc["groups"]:
            members = ", ".join("%s (%s, %s)" % (m["id"], m["skill"], m["severity"]) for m in g["members"])
            L.append("| %s |" % " | ".join(_cell(x) for x in (g["root_cause_key"], g["severity"], g["primary"]["id"],
                                                            members, "yes" if g["cross_skill"] else "no")))
    else:
        L.append("None.")
    L += ["", "## False positives excluded", ""]
    if doc["false_positives"]:
        L += ["| Id | Skill | Title |", "|---|---|---|"]
        L += ["| %s | %s | %s |" % (_cell(f["id"]), _cell(f["skill"]), _cell(f["title"])) for f in doc["false_positives"]]
    else:
        L.append("None.")
    if doc["parse_errors"]:
        L += ["", "## Parse errors", ""] + ["- %s: %s" % (e["file"], e["error"]) for e in doc["parse_errors"]]
    L.append("")
    return "\n".join(L)


def write_rollup(doc, out_dir):
    """Write rollup.json and rollup.md into out_dir. Refuses any path inside an audit/findings folder."""
    target = os.path.abspath(out_dir)
    parts = os.path.normcase(target).replace("\\", "/").split("/")
    if any(parts[i] == "audit" and parts[i + 1] == "findings" for i in range(len(parts) - 1)):
        raise ValueError("refusing to write the rollup inside audit/findings/: " + out_dir)
    os.makedirs(target, exist_ok=True)
    jp, mp = os.path.join(target, "rollup.json"), os.path.join(target, "rollup.md")
    for path, text in ((jp, json.dumps(doc, indent=2)), (mp, render_md(doc))):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    return jp, mp


# --------------------------------------------------------------------------- CLI
def _expected_arg(values):
    if not values:
        return None
    return [s.strip() for v in values for s in v.split(",") if s.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, full=True):
        p.add_argument("root", nargs="?", default=".", help="repo root (or its audit/ directory)")
        p.add_argument("--audit-dir", default=None, help="audit workspace, default <root>/audit")
        p.add_argument("--accepted", default=None, help="JSON list of risk-acceptance records")
        p.add_argument("--as-of", default=None, help="date acceptances are checked against (default today, UTC)")
        if full:
            p.add_argument("--expected", action="append",
                           help="comma-separated skills that should have run (default: audit/plan.json)")

    p = sub.add_parser("rollup", help="write rollup.json and rollup.md")
    common(p)
    p.add_argument("--out-dir", default=None)
    p.add_argument("--print", dest="print_doc", action="store_true", help="print the full JSON, not a short summary")
    p = sub.add_parser("verdict", help="print the verdict object")
    common(p)
    p.add_argument("--text", action="store_true")
    p = sub.add_parser("counts", help="print severity counts")
    common(p, full=False)
    p = sub.add_parser("dedupe", help="merge one findings file by root_cause_key")
    p.add_argument("path")
    p.add_argument("--key", choices=["root_cause_key", "title"], default="root_cause_key")
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true", help="print the merged document")
    a = ap.parse_args(argv)

    if a.cmd == "dedupe":
        doc, err = _read_json(a.path)
        if err or not isinstance(doc, dict):
            print("error: cannot read %s: %s" % (a.path, err or "top level is not an object"), file=sys.stderr)
            return 2
        findings = [f for f in (doc.get("findings") or []) if isinstance(f, dict)]
        report = merge_report(findings, a.key)
        merged = merge_by_root_cause(findings, a.key)
        if a.json:
            print(json.dumps(dict(doc, findings=merged, summary=severity_counts(merged)), indent=2))
        else:
            print("\n".join("%s: merging %s" % (k, ids) for k, ids in report) if report else "nothing to merge")
        if a.write and report:
            doc["findings"] = merged
            doc["summary"] = severity_counts(merged)
            tmp = a.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2)
            os.replace(tmp, a.path)
            if not a.json:
                print("wrote %s" % a.path)
        return 0

    audit_dir = a.audit_dir or resolve_audit_dir(a.root)
    if not os.path.isdir(audit_dir):
        print("error: no audit workspace at %s" % audit_dir, file=sys.stderr)
        return 2
    try:
        doc = rollup(audit_dir, a.accepted, _expected_arg(getattr(a, "expected", None)), a.as_of)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if a.cmd == "counts":
        print(json.dumps(doc["summary"], indent=2))
    elif a.cmd == "verdict":
        v = doc["verdict"]
        if a.text:
            print("%s - %s" % (v["verdict"], v["reason"]) + "".join("\n  caveat: " + c for c in v["caveats"]))
        else:
            print(json.dumps(v, indent=2))
    else:
        try:
            jp, mp = write_rollup(doc, a.out_dir or os.path.join(audit_dir, OUT_SUBDIR))
        except ValueError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
        if a.print_doc:
            print(json.dumps(doc, indent=2))
        else:
            print(json.dumps({"json": jp.replace(os.sep, "/"), "md": mp.replace(os.sep, "/"),
                              "verdict": doc["verdict"]["verdict"], "reason": doc["verdict"]["reason"],
                              "caveats": doc["verdict"]["caveats"], "summary": doc["summary"],
                              "parse_errors": doc["parse_errors"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
