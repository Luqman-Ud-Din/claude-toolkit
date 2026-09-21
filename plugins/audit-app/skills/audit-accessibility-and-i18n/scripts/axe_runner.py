#!/usr/bin/env python3
"""Wrap an automated accessibility checker (axe-core CLI, falling back to pa11y)
for audit-accessibility-and-i18n.

Usage:
    python axe_runner.py --url http://localhost:4200/ [--url ...] [--urls-file urls.txt]
                         [--out audit/evidence/audit-accessibility-and-i18n/axe]
                         [--tool auto|axe|pa11y] [--tags wcag2a,wcag2aa,wcag21a,wcag21aa,wcag22aa]

Behaviour:
  * Detects `axe` (from `npm i -g @axe-core/cli`, needs Chrome/chromedriver) or runs it through
    `npx --no-install @axe-core/cli`; otherwise tries `pa11y`. Nothing is installed.
  * Runs each URL, saves the raw JSON per URL under --out, and writes summary.md / summary.json
    with violations grouped by WCAG criterion (from axe tags `wcag111` -> 1.1.1, or pa11y codes
    `1_1_1`), impact, rule id, help URL, and the first node selectors.
  * If no tool is available, writes not-run.json with the install command and exits 0 so the
    skill can record "not run" under Not checked.
The audited repo is never modified; only --out is written. Requires the app to be served.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

WIN = os.name == "nt"


def run(cmd, timeout=300):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=WIN)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, "", str(e)


def detect(tool):
    candidates = []
    if tool in ("auto", "axe"):
        if shutil.which("axe"):
            candidates.append(("axe", ["axe"]))
        candidates.append(("axe", ["npx", "--no-install", "@axe-core/cli"]))
    if tool in ("auto", "pa11y"):
        if shutil.which("pa11y"):
            candidates.append(("pa11y", ["pa11y"]))
        candidates.append(("pa11y", ["npx", "--no-install", "pa11y"]))
    for name, base in candidates:
        rc, out, err = run(base + ["--version"], timeout=90)
        if rc == 0 and re.search(r"\d+\.\d+", out + err):
            return name, base, (out + err).strip().splitlines()[-1]
    return None, None, None


def criterion_from_axe_tags(tags):
    out = []
    for t in tags:
        m = re.fullmatch(r"wcag(\d)(\d)(\d{1,2})", t)
        if m:
            out.append(f"{m.group(1)}.{m.group(2)}.{m.group(3)}")
    return out or ["best-practice"]


def run_axe(base, url, tags, out_dir, idx):
    rc, out, err = run(base + [url, "--tags", tags, "--stdout"], timeout=600)
    raw_path = os.path.join(out_dir, f"axe-{idx}.json")
    with open(raw_path, "w", encoding="utf-8") as fh:
        fh.write(out or err)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"url": url, "error": (err or out)[:500], "violations": []}
    res = data[0] if isinstance(data, list) else data
    v = []
    for viol in res.get("violations", []):
        v.append({"rule": viol.get("id"), "impact": viol.get("impact"), "help": viol.get("help"),
                  "helpUrl": viol.get("helpUrl"), "criteria": criterion_from_axe_tags(viol.get("tags", [])),
                  "nodes": [n.get("target") for n in viol.get("nodes", [])][:10], "node_count": len(viol.get("nodes", []))})
    return {"url": url, "engine": res.get("testEngine", {}).get("version"), "violations": v, "passes": len(res.get("passes", [])), "incomplete": len(res.get("incomplete", []))}


def run_pa11y(base, url, out_dir, idx):
    rc, out, err = run(base + [url, "--reporter", "json", "--standard", "WCAG2AA"], timeout=600)
    raw_path = os.path.join(out_dir, f"pa11y-{idx}.json")
    with open(raw_path, "w", encoding="utf-8") as fh:
        fh.write(out or err)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"url": url, "error": (err or out)[:500], "violations": []}
    grouped = {}
    for item in data:
        code = item.get("code", "")
        m = re.search(r"\.(\d)_(\d)_(\d{1,2})\.", code)
        crit = f"{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else "unknown"
        g = grouped.setdefault(code, {"rule": code, "impact": item.get("type"), "help": item.get("message"), "helpUrl": None, "criteria": [crit], "nodes": [], "node_count": 0})
        g["node_count"] += 1
        if len(g["nodes"]) < 10:
            g["nodes"].append(item.get("selector"))
    return {"url": url, "violations": list(grouped.values())}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--urls-file")
    ap.add_argument("--out", default="audit/evidence/audit-accessibility-and-i18n/axe")
    ap.add_argument("--tool", default="auto", choices=["auto", "axe", "pa11y"])
    ap.add_argument("--tags", default="wcag2a,wcag2aa,wcag21a,wcag21aa,wcag22aa")
    a = ap.parse_args()
    urls = list(a.url)
    if a.urls_file:
        with open(a.urls_file, "r", encoding="utf-8") as fh:
            urls += [l.strip() for l in fh if l.strip() and not l.startswith("#")]
    os.makedirs(a.out, exist_ok=True)
    name, base, version = detect(a.tool)
    if not name:
        doc = {"status": "not-run", "checked_at": datetime.now(timezone.utc).isoformat(),
               "reason": "no accessibility CLI found (axe-core CLI or pa11y)",
               "install": "npm i -g @axe-core/cli   (needs Chrome + matching chromedriver)  or  npm i -g pa11y",
               "urls": urls}
        with open(os.path.join(a.out, "not-run.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
        print("automated checker not run: " + doc["reason"] + "\n  install: " + doc["install"])
        return 0
    if not urls:
        print("no --url given; nothing to check (tool available: %s %s)" % (name, version))
        return 0
    results = []
    for i, u in enumerate(urls, 1):
        print(f"[{name}] {u}")
        results.append(run_axe(base, u, a.tags, a.out, i) if name == "axe" else run_pa11y(base, u, a.out, i))
    by_crit = {}
    for r in results:
        for v in r["violations"]:
            for c in v["criteria"]:
                e = by_crit.setdefault(c, {"criterion": c, "rules": {}, "nodes": 0})
                e["nodes"] += v["node_count"]
                e["rules"].setdefault(v["rule"], {"impact": v["impact"], "help": v["help"], "helpUrl": v["helpUrl"], "urls": []})["urls"].append(r["url"])
    summary = {"tool": name, "version": version, "tags": a.tags, "checked_at": datetime.now(timezone.utc).isoformat(),
               "urls": [r["url"] for r in results], "by_criterion": by_crit, "results": results}
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    md = [f"## Automated check: {name} {version} ({a.tags})", "", "| Criterion | Rule | Impact | Nodes | Pages | Help |", "|---|---|---|---|---|---|"]
    for c in sorted(by_crit, key=lambda k: [int(x) if x.isdigit() else 99 for x in k.split(".")]):
        for rule, d in by_crit[c]["rules"].items():
            md.append(f"| {c} | {rule} | {d['impact']} | {sum(1 for r in results for v in r['violations'] if v['rule']==rule for _ in range(v['node_count']))} | {len(set(d['urls']))} | {d['helpUrl'] or d['help']} |")
    for r in results:
        if r.get("error"):
            md.append(f"\n**{r['url']}**: error - {r['error']}")
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"written: {a.out}/summary.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
