#!/usr/bin/env python3
"""Manage the machine-readable findings.json every audit skill emits.

Usage:
    python findings.py init     <skill-name> [--out audit/findings/<skill>.json] [--root .]
    python findings.py add      <findings.json> --from finding.json      # append one finding (validates it)
    python findings.py validate <findings.json>
    python findings.py md       <findings.json> [--out audit/reports/<skill>.md]
    python findings.py summary  <findings.json>

Canonical schema (documented in audit-finding-writer/references/findings-schema.md):
{
  "skill": "audit-xyz",
  "generated_at": "ISO-8601",
  "target": {"root": "...", "commit": "..."},
  "stack": {...subset of audit/stack.json...},
  "scope": {"checked": ["..."], "not_checked": [{"item": "...", "reason": "..."}]},
  "findings": [
    {
      "id": "XYZ-001",
      "title": "...",
      "severity": "Critical|High|Medium|Low|Info",
      "confidence": "confirmed|likely|false-positive",
      "location": {"file": "path", "line": 12, "symbol": "optional"},
      "evidence": "code snippet or command output",
      "impact": "business-language impact",
      "remediation": "concrete fix, with example",
      "references": ["CWE-284", "ASVS-4.1.1", "OWASP-A01:2021"],
      "tags": [],
      "root_cause_key": "optional string used to de-duplicate across skills"
    }
  ],
  "summary": {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
}
Read-only with respect to the audited code: this only writes under audit/.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

SEVERITIES = ["Critical", "High", "Medium", "Low", "Info"]
CONFIDENCE = {"confirmed", "likely", "false-positive"}
REQUIRED = ["id", "title", "severity", "location", "evidence", "impact", "remediation", "references"]


def _load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save(path, doc):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)


def _git_commit(root):
    try:
        return subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None


def summarize(doc):
    s = {k: 0 for k in SEVERITIES}
    for f in doc.get("findings", []):
        if f.get("confidence") == "false-positive":
            continue
        sev = f.get("severity", "Info")
        s[sev] = s.get(sev, 0) + 1
    doc["summary"] = s
    return s


def validate_finding(f):
    errors = []
    for k in REQUIRED:
        if k not in f or f[k] in ("", None, []):
            errors.append(f"missing '{k}'")
    if f.get("severity") not in SEVERITIES:
        errors.append(f"severity must be one of {SEVERITIES}")
    if f.get("confidence", "confirmed") not in CONFIDENCE:
        errors.append(f"confidence must be one of {sorted(CONFIDENCE)}")
    loc = f.get("location") or {}
    if not isinstance(loc, dict) or "file" not in loc:
        errors.append("location must be an object with at least 'file'")
    return errors


def validate(doc):
    errors = []
    for k in ("skill", "findings", "scope"):
        if k not in doc:
            errors.append(f"top-level '{k}' missing")
    ids = set()
    for i, f in enumerate(doc.get("findings", [])):
        for e in validate_finding(f):
            errors.append(f"finding[{i}] ({f.get('id', '?')}): {e}")
        if f.get("id") in ids:
            errors.append(f"duplicate id {f.get('id')}")
        ids.add(f.get("id"))
    return errors


def to_markdown(doc):
    out = [f"## {doc.get('skill')} findings", ""]
    s = summarize(doc)
    out.append("| " + " | ".join(SEVERITIES) + " |")
    out.append("|" + "---|" * len(SEVERITIES))
    out.append("| " + " | ".join(str(s[k]) for k in SEVERITIES) + " |")
    out.append("")
    order = {k: i for i, k in enumerate(SEVERITIES)}
    for f in sorted(doc.get("findings", []), key=lambda x: order.get(x.get("severity"), 99)):
        if f.get("confidence") == "false-positive":
            continue
        loc = f.get("location", {})
        where = f"{loc.get('file')}:{loc.get('line')}" if loc.get("line") else loc.get("file")
        out += [
            f"### [{f['severity']}] {f['id']} - {f['title']}",
            f"- **Location:** `{where}`" + (f" ({loc['symbol']})" if loc.get("symbol") else ""),
            f"- **Confidence:** {f.get('confidence', 'confirmed')}",
            "- **Evidence:**", "", "```", str(f["evidence"]).strip(), "```", "",
            f"- **Impact:** {f['impact']}",
            f"- **Remediation:** {f['remediation']}",
            f"- **Reference:** {', '.join(f.get('references', []))}",
            "",
        ]
    nc = doc.get("scope", {}).get("not_checked", [])
    out.append("### Not checked")
    if nc:
        for item in nc:
            out.append(f"- {item.get('item')} - {item.get('reason')}")
    else:
        out.append("- (nothing recorded; the skill should list what it could not verify)")
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("skill"); p.add_argument("--out"); p.add_argument("--root", default=".")
    p = sub.add_parser("add"); p.add_argument("path"); p.add_argument("--from", dest="src", required=True)
    p = sub.add_parser("validate"); p.add_argument("path")
    p = sub.add_parser("md"); p.add_argument("path"); p.add_argument("--out")
    p = sub.add_parser("summary"); p.add_argument("path")
    a = ap.parse_args()

    if a.cmd == "init":
        out = a.out or os.path.join(a.root, "audit", "findings", f"{a.skill}.json")
        stack = {}
        sp = os.path.join(a.root, "audit", "stack.json")
        if os.path.exists(sp):
            stack = _load(sp)
        doc = {"skill": a.skill, "generated_at": datetime.now(timezone.utc).isoformat(),
               "target": {"root": os.path.abspath(a.root), "commit": _git_commit(a.root)},
               "stack": stack, "scope": {"checked": [], "not_checked": []}, "findings": [],
               "summary": {k: 0 for k in SEVERITIES}}
        _save(out, doc)
        print(out)
        return 0

    doc = _load(a.path)
    if a.cmd == "add":
        f = _load(a.src)
        errs = validate_finding(f)
        if errs:
            print("\n".join(errs), file=sys.stderr)
            return 1
        doc["findings"].append(f)
        summarize(doc)
        _save(a.path, doc)
        print(f"added {f['id']}")
        return 0
    if a.cmd == "validate":
        errs = validate(doc)
        print("\n".join(errs) if errs else "findings.json is valid")
        return 1 if errs else 0
    if a.cmd == "md":
        text = to_markdown(doc)
        if a.out:
            os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
            with open(a.out, "w", encoding="utf-8") as fh:
                fh.write(text)
            print(a.out)
        else:
            print(text)
        return 0
    if a.cmd == "summary":
        print(json.dumps(summarize(doc), indent=2))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
