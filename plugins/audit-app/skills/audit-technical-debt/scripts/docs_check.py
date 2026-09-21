#!/usr/bin/env python3
"""Missing and stale documentation: README, ADRs, API docs, runbooks, changelog,
contributing guide, env example, per-service READMEs, and README references to
paths that no longer exist.

Usage:
    python docs_check.py <repo_root> [--stale-days 365] [--history FILE | --no-git] [--as-of YYYY-MM-DD]
                         [--out docs.json] [--md docs.md]

Checks (status present | missing | stale | partial | unknown-age):
  readme           README* at the root; partial when it has none of: install/setup, run,
                   test, deploy, configuration headings or commands
  readme-fresh     README last changed more than --stale-days before the newest code
                   commit (needs git or a synthetic history; else unknown-age)
  adr              docs/adr, docs/decisions, adr, architecture/decisions, doc/adr (count, newest)
  api-docs         openapi*/swagger* spec files, or a generator in code/manifests
                   (Swashbuckle, NSwag, springdoc, springfox, drf-spectacular, drf-yasg,
                   @nestjs/swagger, swagger-jsdoc, tsoa, fastapi)
  runbook          RUNBOOK*, runbooks/, docs/runbook*, docs/operations, playbooks/, ops/
  changelog, contributing, env-example (.env.example when code reads env vars)
  service-readmes  build units (dirs with *.csproj, package.json, pom.xml, pyproject.toml)
                   that have no README (Info)
  dangling refs    backticked or linked relative paths in root/docs Markdown that do not
                   exist (README drift: a described folder or file that is gone)
Documentation quality (is it correct?) is a manual step; this only finds absence and age.
Read-only against the audited repo.
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
CODE_EXT = {".cs", ".java", ".kt", ".ts", ".tsx", ".js", ".jsx", ".vue", ".py", ".go", ".rb", ".php"}
API_GEN = re.compile(r"Swashbuckle|NSwag|springdoc|springfox|drf[-_]spectacular|drf[-_]yasg|@nestjs/swagger|swagger-jsdoc|"
                     r"\btsoa\b|from fastapi|FastAPI\(", re.I)
SECTIONS = {"setup": r"install|setup|getting started|prerequisite", "run": r"\brun\b|start|usage",
            "test": r"\btest", "deploy": r"deploy|release|publish", "config": r"config|environment|settings|\.env"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--stale-days", type=int, default=365)
    ap.add_argument("--out")
    ap.add_argument("--md")
    githist.add_history_args(ap)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    hist = githist.History(root, a.history, a.no_git)
    as_of = githist.resolve_as_of(hist, a.as_of)

    all_files, dirs, manifests_dirs, env_used, api_gen = [], set(), set(), False, False
    # Every file counts for the listing (a large openapi.json is still an API doc), so no size cap;
    # a folder is known when it holds at least one listed file (git cannot track empty folders).
    for full in repo_walk.iter_files(root, globs=["*"], extra_skip=EXTRA_SKIP, max_bytes=None):
        rel = repo_walk.rel(root, full)
        rd, fn = rel.rsplit("/", 1) if "/" in rel else ("", rel)
        d = rd
        while d not in dirs:
            dirs.add(d)
            if not d:
                break
            d = d.rsplit("/", 1)[0] if "/" in d else ""
        all_files.append(rel)
        low = fn.lower()
        if low.endswith((".csproj", "package.json", "pom.xml", "pyproject.toml", "build.gradle")):
            manifests_dirs.add(rd)
        ext = os.path.splitext(low)[1]
        if ext in CODE_EXT or low.endswith((".csproj", "package.json", "requirements.txt", "pom.xml")):
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    t = fh.read(200000)
            except OSError:
                continue
            if API_GEN.search(t):
                api_gen = True
            if re.search(r"process\.env\.|os\.environ|Environment\.GetEnvironmentVariable|System\.getenv|import\.meta\.env", t):
                env_used = True
    lower_files = {f.lower(): f for f in all_files}
    checks = []

    def age_of(path):
        lc = hist.last_change(path)
        return (lc, (as_of - lc["date"]).days if lc and lc["date"] else None)

    readme = next((f for f in all_files if "/" not in f and f.lower().startswith("readme")), None)
    if not readme:
        checks.append({"id": "readme", "status": "missing", "path": None, "detail": "no README at repository root"})
    else:
        with open(os.path.join(root, readme), "r", encoding="utf-8", errors="ignore") as fh:
            rt = fh.read()
        found = [k for k, rx in SECTIONS.items() if re.search(rx, rt, re.I)]
        lines = len(rt.splitlines())
        checks.append({"id": "readme", "status": "present" if len(found) >= 3 and lines >= 15 else "partial", "path": readme,
                       "detail": "%d lines; covers: %s; missing: %s" % (lines, ", ".join(found) or "-",
                                                                     ", ".join(k for k in SECTIONS if k not in found) or "-")})
        lc, age = age_of(readme)
        newest_code = None
        if hist.mode != "none":
            for c in hist.commits(as_of=as_of):
                if any(os.path.splitext(f["path"])[1].lower() in CODE_EXT for f in c["files"]):
                    newest_code = c["date"]
                    break
        if lc is None or age is None:
            checks.append({"id": "readme-fresh", "status": "unknown-age", "path": readme, "detail": "no history: " + hist.reason})
        else:
            lag = (newest_code - lc["date"]).days if newest_code else 0
            checks.append({"id": "readme-fresh", "status": "stale" if lag > a.stale_days else "present", "path": readme,
                           "age_days": age, "detail": "README last changed %s; newest code change %d days later"
                                                      % (githist.iso(lc["date"])[:10], max(lag, 0))})

    adr_dirs = [d for d in dirs if re.search(r"(^|/)(adr|adrs|decisions)$", d, re.I)]
    adr_files = [f for f in all_files if any(f.startswith(d + "/") for d in adr_dirs) and f.lower().endswith((".md", ".adoc", ".rst"))]
    checks.append({"id": "adr", "status": "present" if adr_files else "missing", "path": adr_dirs[0] if adr_dirs else None,
                   "detail": "%d decision records" % len(adr_files) if adr_files else "no ADR folder (docs/adr, docs/decisions)"})
    specs = [f for f in all_files if re.search(r"(^|/)(openapi|swagger)[\w.-]*\.(json|ya?ml)$", f, re.I)]
    checks.append({"id": "api-docs", "status": "present" if specs or api_gen else "missing", "path": specs[0] if specs else None,
                   "detail": ("spec files: " + ", ".join(specs[:3])) if specs else ("generated from code annotations" if api_gen
                                                                                  else "no OpenAPI spec or generator found")})
    runbooks = [f for f in all_files if re.search(r"(^|/)(runbooks?|playbooks?|ops|operations)(/|\.md$)|runbook", f, re.I)]
    checks.append({"id": "runbook", "status": "present" if runbooks else "missing", "path": runbooks[0] if runbooks else None,
                   "detail": "%d runbook files" % len(runbooks) if runbooks else "no runbook for on-call / incident steps"})
    for cid, rx in (("changelog", r"^(changelog|changes|history)(\.md)?$"), ("contributing", r"^contributing(\.md)?$")):
        hit = next((f for f in all_files if "/" not in f and re.match(rx, f, re.I)), None)
        checks.append({"id": cid, "status": "present" if hit else "missing", "path": hit, "detail": ""})
    if env_used:
        hit = next((f for f in all_files if re.search(r"\.env\.(example|sample|template)$", f, re.I)), None)
        checks.append({"id": "env-example", "status": "present" if hit else "missing", "path": hit,
                       "detail": "code reads environment variables"})

    no_readme = sorted(d for d in manifests_dirs if d and not any(f.lower().startswith((d + "/readme").lower()) for f in all_files))
    dangling = []
    md_files = [f for f in all_files if f.lower().endswith(".md") and ("/" not in f or f.lower().startswith("docs/"))]
    for mdf in md_files:
        with open(os.path.join(root, mdf), "r", encoding="utf-8", errors="ignore") as fh:
            for n, line in enumerate(fh, 1):
                for m in re.finditer(r"`([^`\s]+)`|\]\(([^)\s#]+)\)", line):
                    ref = m.group(1) or m.group(2)
                    if re.match(r"^[a-z]+://|^mailto:|^#|^\$|^-|^<|[*{}<>|=]|^audit/", ref) or "/" not in ref:
                        continue
                    if not re.search(r"\.\w{1,6}$|/$", ref) and not re.match(r"^[\w.-]+(/[\w.-]+)+$", ref):
                        continue
                    base = os.path.dirname(mdf)
                    cands = [os.path.normpath(os.path.join(base, ref)).replace(os.sep, "/"), ref.strip("./").rstrip("/")]
                    if not any(c.lower() in lower_files or c in dirs or c.rstrip("/") in dirs for c in cands):
                        dangling.append({"doc": mdf, "line": n, "reference": ref})

    result = {"root": root, "history": {"mode": hist.mode, "reason": hist.reason}, "as_of": githist.iso(as_of),
              "checks": checks, "dangling_references": dangling, "build_units_without_readme": no_readme,
              "note": "Presence and age only; whether the content is correct is a manual review step."}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("| Check | Status | Path | Detail |\n|---|---|---|---|\n")
            for c in checks:
                fh.write("| %s | %s | %s | %s |\n" % (c["id"], c["status"], c.get("path") or "", c.get("detail", "")))
            if dangling:
                fh.write("\n| Doc | Line | Missing path |\n|---|---|---|\n")
                for d in dangling:
                    fh.write("| `%s` | %d | `%s` |\n" % (d["doc"], d["line"], d["reference"]))
    print(json.dumps({"checks": {c["id"]: c["status"] for c in checks}, "dangling_references": len(dangling),
                      "build_units_without_readme": no_readme}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
