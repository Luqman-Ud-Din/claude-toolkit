#!/usr/bin/env python3
"""Inventory TODO / FIXME / HACK / XXX comments with their age from git blame,
and find blocks of commented-out code.

Usage:
    python todo_age.py <repo_root> [--markers TODO,FIXME,HACK,XXX] [--include-docs]
                       [--min-commented-lines 3] [--history FILE | --no-git] [--as-of YYYY-MM-DD]
                       [--out todos.json] [--md todos.md]

What it reports:
  todos           file, line, marker, text, owner "TODO(name)", ticket (ABC-123, #123, URL),
                  author, date, age_days (from `git blame --line-porcelain`, a synthetic
                  history's blame ranges, or null with --no-git), security_related (text
                  mentions auth, password, token, tenant, payment, ...).
  summary         counts per marker and per age bucket (<90d, 90d-1y, 1-3y, >3y, unknown).
  commented_code  runs of >= --min-commented-lines consecutive line comments (// or #)
                  where at least 60% of the non-empty lines look like code (end in ; { } ),
                  start with a keyword, contain an assignment or =>). XML doc comments
                  (///), shebangs and prose are ignored.
Markers are matched case-sensitively and only after a comment token (//, #, /*, *, <!--, --),
so identifiers like "todoList" and strings like "XXX-XXX" are not reported.
Age with a synthetic history uses the smallest blame range containing the line, else the
newest commit touching the file (marked approx). Read-only against the audited repo.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

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
_GITHIST = os.path.join(_SKILLS, "audit-git-history", "scripts", "githist.py")
if not os.path.exists(_GITHIST):
    sys.exit("audit-git-history must be reachable from this skill (audit-core plugin or sibling layout; expected " + _GITHIST + ")")
_spec = importlib.util.spec_from_file_location("audit_git_history_githist", _GITHIST)
githist = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = githist
_spec.loader.exec_module(githist)
_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
try:
    _spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _WALK)
    repo_walk = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(repo_walk)
except (FileNotFoundError, AttributeError, ImportError):
    sys.exit("audit-code-scan must be reachable from this skill (audit-core plugin or sibling layout; expected " + _WALK + ")")

EXTRA_SKIP = ("vendor",)  # vendored third-party code, on top of repo_walk.SKIP_DIRS
CODE_EXT = {".cs", ".java", ".kt", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".py", ".html", ".scss",
            ".css", ".sql", ".sh", ".ps1", ".yml", ".yaml", ".xml", ".csproj", ".gradle", ".properties", ".razor",
            ".cshtml", ".go", ".rb", ".php", ".tf", ".json"}
DOC_EXT = {".md", ".txt", ".rst", ".adoc"}
SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "packages.lock.json"}
LINE_COMMENT = {".cs": "//", ".java": "//", ".kt": "//", ".ts": "//", ".tsx": "//", ".js": "//", ".jsx": "//",
                ".mjs": "//", ".cjs": "//", ".vue": "//", ".scss": "//", ".go": "//", ".php": "//", ".py": "#", ".rb": "#"}
SECURITY_RE = re.compile(r"\b(security|auth\w*|password|passwd|secret|token|crypt\w*|tenant|permission|role|xss|csrf|"
                         r"sql|inject\w*|payment|pci|pii|gdpr|vulnerab\w*|cve|sanitiz\w*|encrypt\w*)\b", re.I)
CODE_LIKE = re.compile(r"(;\s*$|\{\s*$|^\}|^\)|\)\s*\{?\s*$|^(if|else|for|foreach|while|return|var|let|const|public|"
                       r"private|protected|import|from|def|class|using|await|try|catch|switch|case|new|throw|print|"
                       r"self\.|this\.)\b|^[\w.\[\]]+\s*(=|\+=|-=)\s*\S|=>|^@\w+)")
PROSE = re.compile(r"^[A-Za-z][a-z]+(\s+[a-z',]+){4,}[.!?:]?$")


def iter_files(root, include_docs):
    exts = CODE_EXT | (DOC_EXT if include_docs else set())
    for full in repo_walk.iter_files(root, exts=exts, names=frozenset(), extra_skip=EXTRA_SKIP):
        fn = os.path.basename(full)
        if fn in SKIP_FILES or fn.endswith(".min.js"):
            continue
        yield full, repo_walk.rel(root, full)


def bucket(age):
    if age is None:
        return "unknown"
    if age < 90:
        return "<90d"
    if age < 365:
        return "90d-1y"
    if age <= 1095:
        return "1-3y"
    return ">3y"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--markers", default="TODO,FIXME,HACK,XXX")
    ap.add_argument("--include-docs", action="store_true")
    ap.add_argument("--min-commented-lines", type=int, default=3)
    ap.add_argument("--out")
    ap.add_argument("--md")
    githist.add_history_args(ap)
    a = ap.parse_args()

    markers = [m.strip() for m in a.markers.split(",") if m.strip()]
    mark_re = re.compile(r"(//|#|/\*|^\s*\*|<!--|--|@\*)[^\n]*?\b(" + "|".join(map(re.escape, markers)) +
                         r")\b\s*(?:\(([^)]*)\))?\s*[:\-]?\s*(.*)$")
    hist = githist.History(a.root, a.history, a.no_git)
    as_of = githist.resolve_as_of(hist, a.as_of)

    todos, blocks = [], []
    for full, rel in iter_files(a.root, a.include_docs):
        try:
            with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        ext = os.path.splitext(full)[1].lower()
        for n, line in enumerate(lines, 1):
            m = mark_re.search(line)
            if not m:
                continue
            text = re.sub(r"\s*(\*/|-->|\*@)\s*$", "", m.group(4)).strip()
            info = hist.line_info(rel, n)
            date = info["date"] if info else None
            ticket = re.search(r"([A-Z][A-Z0-9]+-\d+|#\d+|https?://\S+)", text)
            todos.append({"file": rel, "line": n, "marker": m.group(2), "text": text[:240],
                          "owner": (m.group(3) or "").strip() or None, "ticket": ticket.group(1) if ticket else None,
                          "author": info.get("author") if info else None, "commit": info.get("commit") if info else None,
                          "date": githist.iso(date), "age_days": (as_of - date).days if date else None,
                          "approx": bool(info and info.get("approx")),
                          "security_related": bool(SECURITY_RE.search(text))})
        prefix = LINE_COMMENT.get(ext)
        if not prefix:
            continue
        run = []
        for n, line in enumerate(lines + [""], 1):
            s = line.strip()
            is_comment = s.startswith(prefix) and not s.startswith("///") and not s.startswith("#!") \
                and not s.startswith("#region") and not s.startswith("#endregion") and "-*-" not in s
            if is_comment:
                run.append((n, s[len(prefix):].strip()))
                continue
            if len(run) >= a.min_commented_lines:
                body = [t for _, t in run if t]
                if body and not any(re.search(r"\b(" + "|".join(markers) + r")\b", t) for t in body):
                    code = sum(1 for t in body if CODE_LIKE.search(t) and not PROSE.match(t))
                    if code / len(body) >= 0.6:
                        info = hist.line_info(rel, run[0][0])
                        date = info["date"] if info else None
                        blocks.append({"file": rel, "start": run[0][0], "end": run[-1][0], "lines": len(run),
                                       "sample": " | ".join(t for _, t in run[:4])[:200],
                                       "date": githist.iso(date), "age_days": (as_of - date).days if date else None})
            run = []

    todos.sort(key=lambda t: (t["age_days"] is None, -(t["age_days"] or 0)))
    summary = {"total": len(todos), "by_marker": {}, "by_age": {}, "security_related": sum(t["security_related"] for t in todos),
               "commented_code_blocks": len(blocks), "commented_code_lines": sum(b["lines"] for b in blocks)}
    for t in todos:
        summary["by_marker"][t["marker"]] = summary["by_marker"].get(t["marker"], 0) + 1
        b = bucket(t["age_days"])
        summary["by_age"][b] = summary["by_age"].get(b, 0) + 1
    result = {"history": {"mode": hist.mode, "reason": hist.reason}, "as_of": githist.iso(as_of),
              "markers": markers, "summary": summary, "todos": todos, "commented_code": blocks}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("| Marker | Location | Age (days) | Date | Author | Text |\n|---|---|---|---|---|---|\n")
            for t in todos:
                fh.write("| %s | `%s:%d` | %s | %s | %s | %s |\n" % (t["marker"], t["file"], t["line"], t["age_days"],
                                                                 (t["date"] or "")[:10], t["author"] or "",
                                                                 t["text"].replace("|", "\\|")[:100]))
            fh.write("\n| Commented-out block | Lines | Age (days) | Sample |\n|---|---|---|---|\n")
            for b in blocks:
                fh.write("| `%s:%d-%d` | %d | %s | `%s` |\n" % (b["file"], b["start"], b["end"], b["lines"], b["age_days"],
                                                              b["sample"].replace("|", "/")[:90]))
    print(json.dumps({"history": hist.mode, "summary": summary,
                      "oldest": ["%s:%d %s %s days" % (t["file"], t["line"], t["marker"], t["age_days"]) for t in todos[:3]]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
