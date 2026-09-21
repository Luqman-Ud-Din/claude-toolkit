#!/usr/bin/env python3
"""Churn x complexity hotspots: how often each file (and, where cheap, each
function) changed in a window, joined with complexity into a ranking.

Usage:
    python churn.py <repo_root> [--complexity complexity.json] [--since-days 365]
                    [--last-commits N] [--top 20] [--function-top 15]
                    [--history synthetic-history.json | --no-git] [--as-of YYYY-MM-DD]
                    [--out churn.json] [--md churn.md]

Window: --since-days and --last-commits both apply when both are given; with
neither, the last 365 days before the as-of date are used.

Sources (history via $AUDIT_CORE_ROOT/skills/audit-git-history/scripts/githist.py; synthetic format in
$AUDIT_CORE_ROOT/skills/audit-git-history/references/githist-contract.md):
  git        `git log --no-merges --numstat` for file churn; for the --function-top
             files with the highest commits x max-CC, `git log -p -U0` hunk ranges are
             mapped onto the CURRENT function spans (approximate: lines move between
             commits, so small functions next to a hot one can collect stray counts).
  synthetic  commit file entries may name "functions" (exact) or "hunks" (mapped as above).
  none       (--no-git or no work tree) churn is empty; the hotspot list is empty and
             says why. Run complexity.py alone in that case.

Scoring:
  function hotspot score = commits touching the function x its cyclomatic complexity
  file hotspot score     = commits touching the file x the file's highest function CC
                           (used only when no function-level data exists for that file)
  score_norm             = score / max score x 100
A function that is both complex and changed often is where debt charges the most
interest; complex code nobody touches can wait. Read-only against the audited repo.
"""
import argparse
import importlib.util
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import complexity  # noqa: E402

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
_GITHIST = os.path.join(_SKILLS, "audit-git-history", "scripts", "githist.py")
if not os.path.exists(_GITHIST):
    sys.exit("audit-git-history must be reachable from this skill (audit-core plugin or sibling layout; expected " + _GITHIST + ")")
_spec = importlib.util.spec_from_file_location("audit_git_history_githist", _GITHIST)
githist = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = githist
_spec.loader.exec_module(githist)


def overlaps(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--complexity", help="complexity.json from complexity.py (computed if omitted)")
    ap.add_argument("--since-days", type=int)
    ap.add_argument("--last-commits", type=int)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--function-top", type=int, default=15, help="files to resolve function churn for (git mode)")
    ap.add_argument("--out")
    ap.add_argument("--md")
    githist.add_history_args(ap)
    a = ap.parse_args()

    if a.complexity:
        with open(a.complexity, "r", encoding="utf-8") as fh:
            files = json.load(fh)["files"]
    else:
        files = complexity.analyze_repo(a.root)
    cidx = {f["file"]: f for f in files}

    hist = githist.History(a.root, a.history, a.no_git)
    as_of = githist.resolve_as_of(hist, a.as_of)
    since_days = a.since_days if (a.since_days or a.last_commits) else 365
    commits = hist.commits(since_days=since_days, last_n=a.last_commits, as_of=as_of)

    stats = {}
    fn_commits = defaultdict(int)
    has_fn_data = set()
    for c in commits:
        seen = set()
        for f in c["files"]:
            p = f["path"]
            if p in seen:
                continue
            seen.add(p)
            s = stats.setdefault(p, {"path": p, "commits": 0, "added": 0, "deleted": 0, "authors": set(), "last_change": None})
            s["commits"] += 1
            s["added"] += f.get("added") or 0
            s["deleted"] += f.get("deleted") or 0
            if c.get("author"):
                s["authors"].add(c["author"])
            if c["date"] and (s["last_change"] is None or c["date"] > s["last_change"]):
                s["last_change"] = c["date"]
            funcs = cidx.get(p, {}).get("functions", [])
            touched = set()
            if f.get("functions"):
                has_fn_data.add(p)
                names = set(f["functions"])
                touched = {i for i, fn in enumerate(funcs) if fn["name"] in names}
            elif f.get("hunks"):
                has_fn_data.add(p)
                touched = {i for i, fn in enumerate(funcs) for h in f["hunks"] if overlaps((fn["start"], fn["end"]), h)}
            for i in touched:
                fn_commits[(p, i)] += 1

    if hist.mode == "git":
        ranked = sorted((p for p in stats if p in cidx and cidx[p]["functions"]),
                        key=lambda p: stats[p]["commits"] * max(fn["cyclomatic"] for fn in cidx[p]["functions"]),
                        reverse=True)[:a.function_top]
        for p in ranked:
            hunks = hist.hunks_for_file(p, since_days=since_days, last_n=a.last_commits, as_of=as_of)
            if not hunks:
                continue
            has_fn_data.add(p)
            funcs = cidx[p]["functions"]
            for _, ranges in hunks.items():
                for i, fn in enumerate(funcs):
                    if any(overlaps((fn["start"], fn["end"]), r) for r in ranges):
                        fn_commits[(p, i)] += 1

    functions = []
    for (p, i), n in fn_commits.items():
        fn = cidx[p]["functions"][i]
        functions.append({"file": p, "name": fn["name"], "start": fn["start"], "end": fn["end"],
                          "cyclomatic": fn["cyclomatic"], "length": fn["length"], "commits": n})
    functions.sort(key=lambda x: x["commits"] * x["cyclomatic"], reverse=True)

    hotspots = []
    for fn in functions:
        hotspots.append({"kind": "function", "file": fn["file"], "name": fn["name"], "start": fn["start"],
                         "commits": fn["commits"], "cyclomatic": fn["cyclomatic"], "length": fn["length"],
                         "score": fn["commits"] * fn["cyclomatic"]})
    for p, s in stats.items():
        if p not in cidx or p in has_fn_data or not cidx[p]["functions"]:
            continue
        top = max(cidx[p]["functions"], key=lambda fn: fn["cyclomatic"])
        hotspots.append({"kind": "file", "file": p, "name": None, "start": None, "commits": s["commits"],
                         "cyclomatic": top["cyclomatic"], "length": cidx[p]["lines"],
                         "score": s["commits"] * top["cyclomatic"], "hottest_function": top["name"]})
    hotspots = [h for h in hotspots if h["score"] > 0]
    hotspots.sort(key=lambda h: (h["score"], h["commits"]), reverse=True)
    mx = hotspots[0]["score"] if hotspots else 0
    for r, h in enumerate(hotspots, 1):
        h["rank"] = r
        h["score_norm"] = round(h["score"] * 100.0 / mx, 1) if mx else 0.0

    file_rows = sorted(stats.values(), key=lambda s: s["commits"], reverse=True)
    for s in file_rows:
        s["authors"] = len(s["authors"])
        s["last_change"] = githist.iso(s["last_change"])
    result = {
        "history": {"mode": hist.mode, "reason": hist.reason},
        "as_of": githist.iso(as_of),
        "window": {"since_days": since_days, "last_commits": a.last_commits},
        "commits_in_window": len(commits),
        "max_file_commits": max((s["commits"] for s in file_rows), default=0),
        "files": file_rows,
        "functions": functions,
        "hotspots": hotspots[:a.top] if a.top > 0 else hotspots,
        "note": ("function churn from hunk mapping is approximate" if hist.mode == "git" else
                 "no history available: " + hist.reason if hist.mode == "none" else "synthetic history"),
    }
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("Window: %s commits (since_days=%s, last_commits=%s), source: %s\n\n"
                     % (len(commits), since_days, a.last_commits, hist.mode))
            fh.write("| Rank | Kind | Location | Commits | CC | Lines | Score |\n|---|---|---|---|---|---|---|\n")
            for h in result["hotspots"]:
                loc = "%s:%s" % (h["file"], h["start"]) if h["start"] else h["file"]
                name = h["name"] or ("(file; hottest: %s)" % h.get("hottest_function"))
                fh.write("| %d | %s | `%s` %s | %d | %d | %d | %d (%.0f) |\n" % (h["rank"], h["kind"], loc, name, h["commits"],
                                                                            h["cyclomatic"], h["length"], h["score"], h["score_norm"]))
    print(json.dumps({"history": hist.mode, "commits_in_window": len(commits),
                      "top": ["#%d %s %s commits=%d cc=%d score=%d" % (h["rank"], h["file"], h["name"] or "", h["commits"],
                                                                    h["cyclomatic"], h["score"]) for h in hotspots[:5]]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
