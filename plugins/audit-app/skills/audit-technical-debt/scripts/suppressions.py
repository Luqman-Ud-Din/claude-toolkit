#!/usr/bin/env python3
"""Inventory lint, analyzer and type-checker suppressions.

Usage:
    python suppressions.py <repo_root> [--out suppressions.json] [--md suppressions.md]

Recognised forms:
  C#       #pragma warning disable [codes]; [SuppressMessage("Cat", "CA1234:...", Justification="...")];
           // ReSharper disable [once] Rule; <NoWarn> in *.csproj/Directory.Build.props;
           dotnet_diagnostic.<ID>.severity = none|silent in .editorconfig; GlobalSuppressions.cs;
           [ExcludeFromCodeCoverage]
  Java     @SuppressWarnings("x") / ({"x","y"}); @SuppressFBWarnings; // NOSONAR; // NOPMD; CHECKSTYLE:OFF
  TS/JS    eslint-disable, eslint-disable-line, eslint-disable-next-line (rules, "-- reason");
  Vue      @ts-ignore, @ts-nocheck, @ts-expect-error; tslint:disable; istanbul/c8/v8 ignore;
           // NOSONAR; "rule": "off" in .eslintrc*.json
  Python   # noqa[: codes]; # type: ignore[...]; # pylint: disable=...; # nosec; # pragma: no cover;
           # mypy: ignore-errors; ignore / extend-ignore / per-file-ignores in setup.cfg, .flake8, tox.ini
Each item: file, line, tool, kind (line | next-line | block | file | project | coverage), rules,
justification (text after "--", Justification=, or a trailing comment), blanket (no rule
named - suppresses everything), security_related (rule id is a security analyzer rule:
CA2100, CA3xxx, CA5xxx, SCS*, SYSLIB0011, Sonar S2068/S2077/S4790/S5332/S2245/S4507, eslint
security/*, no-eval, no-implied-eval, detect-*, no-unsanitized, react/no-danger, Bandit B1xx-B7xx
or any nosec, SpotBugs SQL_/XSS/CRYPTO/PATH_TRAVERSAL/COMMAND_INJECTION/WEAK_), and
deprecation_related (CS0612, CS0618, SYSLIB*, "deprecation", @typescript-eslint/no-deprecated,
import/no-deprecated). Read-only against the audited repo.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

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
_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
try:
    _spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _WALK)
    repo_walk = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(repo_walk)
except (FileNotFoundError, AttributeError, ImportError):
    sys.exit("audit-code-scan must be reachable from this skill (audit-core plugin or sibling layout; expected " + _WALK + ")")

EXTRA_SKIP = ("vendor",)  # vendored third-party code, on top of repo_walk.SKIP_DIRS
EXT = {".cs", ".java", ".kt", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".py", ".csproj", ".props",
       ".editorconfig", ".json", ".cfg", ".ini", ".toml", ".html"}
SECURITY_RULE = re.compile(r"^(CA2100|CA21\d\d|CA3\d{3}|CA5\d{3}|SCS\d+|SYSLIB0011|S2068|S2077|S4790|S5332|S5542|S2245|"
                           r"S4507|S3649|B[1-7]\d\d)$|^security/|^no-eval$|^no-implied-eval$|detect-|no-unsanitized|"
                           r"react/no-danger|@microsoft/sdl|^(SQL_|XSS|CRYPTO|PATH_TRAVERSAL|COMMAND_INJECTION|WEAK_)", re.I)
DEPRECATION_RULE = re.compile(r"^(CS0612|CS0618|CS0619|SYSLIB\d+)$|deprecat", re.I)


def split_rules(s):
    return [r for r in re.split(r"[,\s]+", (s or "").strip()) if r and r not in ("--", "*/", "-->")]


def mk(rel, n, tool, kind, rules, just, snippet, force_security=False):
    rules = [r.split(":")[0].strip("\"'{} ") for r in rules]
    rules = [r for r in rules if r]
    return {"file": rel, "line": n, "tool": tool, "kind": kind, "rules": rules,
            "justification": (just or "").strip() or None, "blanket": not rules and kind != "coverage",
            "security_related": force_security or any(SECURITY_RULE.search(r) for r in rules),
            "deprecation_related": any(DEPRECATION_RULE.search(r) for r in rules), "snippet": snippet.strip()[:200]}


def scan_line(rel, ext, n, line, low_name):
    out = []
    s = line
    if ext == ".cs":
        m = re.search(r"#pragma\s+warning\s+disable\b\s*([^/\n]*)(?://\s*(.*))?", s)
        if m:
            out.append(mk(rel, n, "roslyn", "block", split_rules(m.group(1)), m.group(2), s))
        m = re.search(r"SuppressMessage\(\s*\"([^\"]*)\"\s*,\s*\"([^\"]*)\"(?:.*?Justification\s*=\s*\"([^\"]*)\")?", s)
        if m:
            out.append(mk(rel, n, "roslyn", "file" if "assembly:" in s else "block", [m.group(2)], m.group(3), s))
        m = re.search(r"//\s*ReSharper\s+disable\s+(once\s+)?([\w, ]+)", s)
        if m:
            out.append(mk(rel, n, "resharper", "line" if m.group(1) else "block", split_rules(m.group(2)), None, s))
        if re.search(r"\[ExcludeFromCodeCoverage", s):
            out.append(mk(rel, n, "coverage", "coverage", [], None, s))
    if ext in (".csproj", ".props"):
        m = re.search(r"<NoWarn>([^<]*)</NoWarn>", s)
        if m:
            rules = [r for r in split_rules(m.group(1).replace(";", " ")) if not r.startswith("$(")]
            if rules:
                out.append(mk(rel, n, "msbuild", "project", rules, None, s))
    if low_name == ".editorconfig":
        m = re.search(r"dotnet_diagnostic\.(\w+)\.severity\s*=\s*(none|silent)", s)
        if m:
            out.append(mk(rel, n, "editorconfig", "project", [m.group(1)], None, s))
    if ext in (".java", ".kt"):
        m = re.search(r"@SuppressWarnings\(\s*(?:value\s*=\s*)?(\{[^}]*\}|\"[^\"]*\")", s)
        if m:
            out.append(mk(rel, n, "javac", "block", re.findall(r"\"([^\"]+)\"", m.group(1)), None, s))
        m = re.search(r"@SuppressFBWarnings\(([^)]*)\)", s)
        if m:
            just = re.search(r"justification\s*=\s*\"([^\"]*)\"", m.group(1))
            out.append(mk(rel, n, "spotbugs", "block", re.findall(r"\"([A-Z_]+)\"", m.group(1)), just.group(1) if just else None, s))
        if re.search(r"//\s*NOPMD", s):
            out.append(mk(rel, n, "pmd", "line", [], s.split("NOPMD", 1)[1], s))
        if re.search(r"CHECKSTYLE:OFF", s):
            out.append(mk(rel, n, "checkstyle", "block", [], None, s))
    if ext in (".java", ".kt", ".cs", ".ts", ".tsx", ".js", ".jsx", ".vue", ".py") and re.search(r"(//|#)\s*NOSONAR", s):
        out.append(mk(rel, n, "sonar", "line", [], s.split("NOSONAR", 1)[1], s))
    if ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".html"):
        m = re.search(r"eslint-disable(-next-line|-line)?\b([^\n]*?)(?:\s--\s*(.*?))?\s*(?:\*/|-->|$)", s)
        if m:
            kind = {"-next-line": "next-line", "-line": "line"}.get(m.group(1), "block" if n > 3 else "file")
            out.append(mk(rel, n, "eslint", kind, split_rules(m.group(2).replace(",", " ")), m.group(3), s))
        m = re.search(r"@ts-(ignore|nocheck|expect-error)\b\s*:?\s*(.*)", s)
        if m:
            out.append(mk(rel, n, "tsc", "file" if m.group(1) == "nocheck" else "next-line", [], m.group(2), s))
        m = re.search(r"tslint:disable(-next-line|-line)?(?::([\w\- ]+))?", s)
        if m:
            out.append(mk(rel, n, "tslint", "next-line" if m.group(1) else "block", split_rules(m.group(2)), None, s))
        if re.search(r"(istanbul|c8|v8)\s+ignore", s):
            out.append(mk(rel, n, "coverage", "coverage", [], None, s))
    if ext == ".json" and low_name.startswith(".eslintrc"):
        m = re.search(r"\"([@\w/\-]+)\"\s*:\s*(\"off\"|0\b|\[\s*\"off\")", s)
        if m:
            out.append(mk(rel, n, "eslint", "project", [m.group(1)], None, s))
    if ext == ".py":
        m = re.search(r"#\s*noqa\b(?::\s*([\w, ]+))?", s)
        if m:
            out.append(mk(rel, n, "flake8", "line", split_rules(m.group(1)), None, s))
        m = re.search(r"#\s*type:\s*ignore(?:\[([\w, -]+)\])?", s)
        if m:
            out.append(mk(rel, n, "mypy", "line", split_rules(m.group(1)), None, s))
        m = re.search(r"#\s*pylint:\s*disable\s*=\s*([\w,\- ]+)", s)
        if m:
            out.append(mk(rel, n, "pylint", "line" if s.strip()[0] != "#" else "block", split_rules(m.group(1)), None, s))
        m = re.search(r"#\s*nosec\b\s*([\w, ]*)", s)
        if m:
            out.append(mk(rel, n, "bandit", "line", split_rules(m.group(1)), None, s, force_security=True))
        if re.search(r"#\s*pragma:\s*no\s*cover", s):
            out.append(mk(rel, n, "coverage", "coverage", [], None, s))
        if re.search(r"#\s*mypy:\s*ignore-errors", s):
            out.append(mk(rel, n, "mypy", "file", [], None, s))
    if ext in (".cfg", ".ini", ".toml") and low_name in ("setup.cfg", ".flake8", "tox.ini", "pyproject.toml"):
        m = re.search(r"^\s*(extend-ignore|ignore|per-file-ignores)\s*=\s*(.*)$", s)
        if m and m.group(2).strip():
            out.append(mk(rel, n, "flake8", "project", split_rules(m.group(2).replace(",", " ").strip("[]\"'")), None, s))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    items = []
    for full in repo_walk.iter_files(root, exts=EXT, names={".editorconfig", ".flake8"}, extra_skip=EXTRA_SKIP):
        low = os.path.basename(full).lower()
        ext = ".editorconfig" if low == ".editorconfig" else os.path.splitext(low)[1]
        if ext not in EXT and low not in (".flake8",):
            continue
        if ext == ".json" and not low.startswith(".eslintrc"):
            continue
        rel = repo_walk.rel(root, full)
        try:
            with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        if low == ".flake8":
            ext = ".cfg"
        for n, line in enumerate(lines, 1):
            items.extend(scan_line(rel, ext, n, line, low))
    summary = {"total": len(items), "blanket": sum(i["blanket"] for i in items),
               "security_related": sum(i["security_related"] for i in items),
               "deprecation_related": sum(i["deprecation_related"] for i in items),
               "without_justification": sum(1 for i in items if not i["justification"] and i["kind"] != "coverage"),
               "by_tool": {}, "by_rule": {}}
    for i in items:
        summary["by_tool"][i["tool"]] = summary["by_tool"].get(i["tool"], 0) + 1
        for r in i["rules"] or ["(all)"]:
            summary["by_rule"][r] = summary["by_rule"].get(r, 0) + 1
    summary["by_rule"] = dict(sorted(summary["by_rule"].items(), key=lambda kv: -kv[1])[:25])
    result = {"root": root, "summary": summary, "items": items}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("| Tool | Kind | Location | Rules | Justified | Security | Snippet |\n|---|---|---|---|---|---|---|\n")
            for i in items:
                fh.write("| %s | %s | `%s:%d` | %s | %s | %s | `%s` |\n" % (i["tool"], i["kind"], i["file"], i["line"],
                                                                        ", ".join(i["rules"]) or "(all)",
                                                                        "yes" if i["justification"] else "no",
                                                                        "yes" if i["security_related"] else "",
                                                                        i["snippet"].replace("|", "/")[:80]))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
