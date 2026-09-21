#!/usr/bin/env python3
"""Language-agnostic complexity pass: per-function cyclomatic complexity
(approximated by counting branch keywords), approximate cognitive complexity
(branches weighted by nesting), function length and file length.

Usage:
    python complexity.py <repo_root> [--out complexity.json] [--md complexity.md]
                         [--top 30] [--cc 15] [--cognitive 15] [--fn-lines 80]
                         [--file-lines 600] [--exclude GLOB ...]

Languages: C# (.cs), Java (.java), TypeScript/JavaScript (.ts .tsx .js .jsx .mjs .cjs),
Python (.py), and Vue single-file components (the <script> block of .vue).
Angular components are plain .ts and are covered; templates (.html) are not analysed.

How it works (an approximation, not a parser):
  * comments and string contents are blanked first, so keywords inside them do not count;
  * brace languages: a function starts at a signature line (method, constructor,
    function declaration, arrow function assigned to a name, Express-style route
    handler, or an anonymous callback at top level) and ends when its braces close;
    nested functions and lambdas count toward the enclosing function;
  * Python: a def ends at the next non-blank line indented at or left of the def;
  * cyclomatic = 1 + count of: if, for, foreach, while, case, catch, when (C#),
    elif / except / and / or (Python), &&, ||, ?? and the ternary " ? ";
  * cognitive ~= sum over branch points of (1 + nesting depth inside the function);
    boolean operators add 1 without the nesting increment.
Flags: CC > --cc moderate, > 20 high, > 50 very high; cognitive > --cognitive;
function > --fn-lines long, > 150 oversized; file > --file-lines long, > 1000 oversized.
Numbers from Roslyn metrics, radon, PMD, ESLint complexity or SonarQube will differ by
a few points; the rank order is what the debt audit uses.
Generated and vendored code (Migrations/, *.designer.cs, *.g.cs, *.min.js, *.d.ts,
node_modules, wwwroot/lib, vendor, dist) is skipped. Read-only against the audited repo.

Importable: analyze_repo(root), analyze_file(path, rel), function_at(index, rel, line).
"""
import argparse
import fnmatch
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

# Folders skipped on top of repo_walk.SKIP_DIRS (audit-code-scan): vendored third-party code and
# generated migrations are not this codebase's debt. Hidden folders (.github, .vscode, ...) are
# also skipped by iter_code_files.
EXTRA_SKIP = ("vendor", "Migrations", "migrations")
SKIP_FILE_GLOBS = ["*.designer.cs", "*.Designer.cs", "*.g.cs", "*.g.i.cs", "*.min.js", "*.generated.*",
                   "*.d.ts", "AssemblyInfo.cs", "*.bundle.js"]
LANG_BY_EXT = {".cs": "csharp", ".java": "java", ".ts": "ts", ".tsx": "ts", ".js": "js", ".jsx": "js",
               ".mjs": "js", ".cjs": "js", ".py": "python", ".vue": "vue"}

BRANCH_RE = {
    "csharp": re.compile(r"\b(?:if|for|foreach|while|case|catch|when)\b|&&|\|\||\?\?|\s\?\s"),
    "java": re.compile(r"\b(?:if|for|while|case|catch)\b|&&|\|\||\s\?\s"),
    "ts": re.compile(r"\b(?:if|for|while|case|catch)\b|&&|\|\||\?\?|\s\?\s"),
    "js": re.compile(r"\b(?:if|for|while|case|catch)\b|&&|\|\||\?\?|\s\?\s"),
    "python": re.compile(r"\b(?:if|elif|for|while|except|and|or|case)\b"),
}
BOOL_OPS = {"&&", "||", "??", "?", "and", "or"}
NOT_NAMES = {"if", "for", "foreach", "while", "switch", "catch", "using", "return", "new", "else", "lock", "throw",
             "await", "function", "typeof", "do", "try", "with", "super", "this", "sizeof", "nameof", "fixed",
             "checked", "unchecked", "yield", "synchronized", "describe", "it", "test", "expect", "beforeEach",
             "afterEach", "beforeAll", "afterAll", "import", "require", "case", "default", "when", "get", "set",
             "base", "var", "in", "of", "is", "as", "not", "and", "or"}
STATEMENT_START = re.compile(r"^\s*(?:return|else|new|await|throw|var|let|const|yield|if|for|foreach|while|switch|"
                             r"catch|using|lock|do|try|case|default)\b")
CS_SIG = re.compile(r"^\s*(?:\[[^\]]*\]\s*)*(?:(?:public|private|protected|internal|static|virtual|override|async|"
                    r"sealed|abstract|extern|unsafe|new|partial|readonly)\s+)*"
                    r"(?:[\w.]+(?:<[^()]*?>)?(?:\[\])*\??\s+)?(\w+)\s*(?:<[^()]*?>)?\s*\(")
JAVA_SIG = re.compile(r"^\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:(?:public|private|protected|static|final|synchronized|"
                      r"abstract|native|default|strictfp)\s+)*(?:<[^>]+>\s+)?"
                      r"(?:[\w.]+(?:<[^()]*?>)?(?:\[\])*\s+)?(\w+)\s*\(")
JS_SIGS = [
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)\s*(?:<[^>]*>)?\s*\("),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*(?::[^=]+)?=\s*(?:async\s+)?"
               r"(?:function\b|\([^)]*\)\s*(?::\s*[^=]+)?=>|\w+\s*=>)"),
    re.compile(r"^\s*(?:(?:public|private|protected|static|async|readonly|override|abstract|get|set)\s+)*"
               r"(\w+)\s*(?:<[^>]*>)?\s*\([^;]*$"),
    re.compile(r"^\s*(\w+)\s*:\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>)"),
]
ROUTE_SIG = re.compile(r"^\s*\w+(?:\.\w+)*\.(get|post|put|patch|delete|use|all)\(\s*['\"`]([^'\"`]*)['\"`]")
ANON_SIG = re.compile(r"(?:=>\s*\{\s*$|\bfunction\s*\([^)]*\)\s*\{\s*$)")
PY_DEF = re.compile(r"^(\s*)(?:async\s+)?def\s+(\w+)\s*\(")


def _blank(s):
    return re.sub(r"[^\n]", " ", s)


def strip_c_like(text):
    """Blank comments and string contents; keep line structure and the quote characters."""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        nx = text[i + 1] if i + 1 < n else ""
        if c == "/" and nx == "/":
            j = text.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
            continue
        if c == "/" and nx == "*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(_blank(text[i:j]))
            i = j
            continue
        if text.startswith('"""', i):
            j = text.find('"""', i + 3)
            j = n if j == -1 else j + 3
            out.append('"' + _blank(text[i + 1:j - 1]) + '"')
            i = j
            continue
        if c in "\"'`":
            verbatim = c == '"' and i > 0 and text[i - 1] == "@"
            j = i + 1
            while j < n:
                ch = text[j]
                if ch == "\\" and not verbatim:
                    j += 2
                    continue
                if ch == c:
                    if verbatim and j + 1 < n and text[j + 1] == c:
                        j += 2
                        continue
                    break
                if ch == "\n" and c != "`" and not verbatim:
                    break
                j += 1
            closed = j < n and text[j] == c
            out.append(c + _blank(text[i + 1:min(j, n)]) + (c if closed else ""))
            i = j + 1 if closed else j
            continue
        out.append(c)
        i += 1
    return "".join(out)


def strip_python(text):
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "#":
            j = text.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
            continue
        if text.startswith('"""', i) or text.startswith("'''", i):
            q = text[i:i + 3]
            j = text.find(q, i + 3)
            j = n if j == -1 else j + 3
            out.append(q[0] + _blank(text[i + 1:j - 1]) + q[0])
            i = j
            continue
        if c in "\"'":
            j = i + 1
            while j < n and text[j] not in (c, "\n"):
                j += 2 if text[j] == "\\" else 1
            closed = j < n and text[j] == c
            out.append(c + " " * (min(j, n) - i - 1) + (c if closed else ""))
            i = j + 1 if closed else j
            continue
        out.append(c)
        i += 1
    return "".join(out)


def vue_script(text):
    """(text with everything outside <script> / <script setup> blocks blanked, 'ts'|'js') or (None, None)."""
    blocks = list(re.finditer(r"<script\b([^>]*)>(.*?)</script>", text, re.S))
    if not blocks:
        return None, None
    lang = "ts" if any(re.search(r"lang\s*=\s*['\"]ts", m.group(1)) for m in blocks) else "js"
    out, pos = [], 0
    for m in blocks:
        out.append(_blank(text[pos:m.start(2)]))
        out.append(m.group(2))
        pos = m.end(2)
    out.append(_blank(text[pos:]))
    return "".join(out), lang


def _sig_name(line, lang, depth):
    code = line.split("=>")[0] if lang == "csharp" else line
    if lang in ("csharp", "java"):
        if STATEMENT_START.match(line):
            return None
        head = code.split("(")[0]
        if "=" in head or "." in head.split()[-1] if head.split() else False:
            return None
        m = (CS_SIG if lang == "csharp" else JAVA_SIG).match(line)
        if not m or m.group(1) in NOT_NAMES:
            return None
        # a bare call statement such as Foo(x); or Foo(x) { at depth 0 is not a declaration
        if re.match(r"^\s*\w+\s*\(", line) and depth == 0:
            return None
        if re.match(r"^\s*\w+\s*\(", line) and not re.search(r"\)\s*(?::\s*(?:base|this)\s*\(.*\))?\s*\{?\s*$", line):
            return None
        return m.group(1)
    m = ROUTE_SIG.match(line)
    if m:
        return "%s %s" % (m.group(1).upper(), m.group(2))
    if STATEMENT_START.match(line) and not re.match(r"^\s*(?:export\s+)?(?:const|let|var)\s", line):
        return None
    for rx in JS_SIGS:
        m = rx.match(line)
        if m and m.group(1) not in NOT_NAMES:
            return m.group(1)
    return None


def brace_functions(stripped, lang):
    lines = stripped.split("\n")
    funcs = []
    depth = 0
    cur = None
    pending = None
    br = BRANCH_RE[lang]
    for idx, line in enumerate(lines, 1):
        line_start_depth = depth
        if cur is None:
            if pending is None:
                name = _sig_name(line, lang, depth)
                if name is None and lang in ("ts", "js") and depth == 0 and ANON_SIG.search(line):
                    name = "<anonymous:%d>" % idx
                if name:
                    pending = {"name": name, "start": idx, "waited": 0}
            if pending is not None:
                brace = line.find("{")
                semi = line.find(";")
                arrow = line.find("=>")
                expr_bodied = lang == "csharp" and arrow != -1 and (brace == -1 or arrow < brace)
                if expr_bodied:
                    hits = br.findall(line)
                    if semi != -1:
                        funcs.append({"name": pending["name"], "start": pending["start"], "end": idx,
                                      "cyclomatic": 1 + len(hits), "cognitive": len(hits)})
                        pending = None
                    else:
                        pending = None  # multi-line expression body: ignored (rare, small)
                elif brace != -1 and (semi == -1 or brace < semi):
                    cur = {"name": pending["name"], "start": pending["start"], "open_depth": depth,
                           "opened": False, "cc": 1, "cog": 0}
                    pending = None
                elif semi != -1 or pending["waited"] >= 4:
                    pending = None
                else:
                    pending["waited"] += 1
        if cur is not None:
            hits = br.findall(line)
            nest = max(0, line_start_depth - cur["open_depth"] - 1)
            cur["cc"] += len(hits)
            cur["cog"] += sum(1 if h.strip() in BOOL_OPS else 1 + nest for h in hits)
        for ch in line:
            if ch == "{":
                depth += 1
                if cur is not None and not cur["opened"] and depth == cur["open_depth"] + 1:
                    cur["opened"] = True
            elif ch == "}":
                depth = max(0, depth - 1)
                if cur is not None and cur["opened"] and depth <= cur["open_depth"]:
                    funcs.append({"name": cur["name"], "start": cur["start"], "end": idx,
                                  "cyclomatic": cur["cc"], "cognitive": cur["cog"]})
                    cur = None
    if cur is not None:
        funcs.append({"name": cur["name"], "start": cur["start"], "end": len(lines),
                      "cyclomatic": cur["cc"], "cognitive": cur["cog"], "unterminated": True})
    return funcs


def python_functions(stripped):
    lines = stripped.split("\n")
    funcs = []
    br = BRANCH_RE["python"]
    for i, first in enumerate(lines):
        m = PY_DEF.match(first)
        if not m:
            continue
        indent = len(m.group(1).expandtabs())
        j = i + 1
        while j < len(lines) and not lines[j - 1].rstrip().endswith(":") and j - i < 10:
            j += 1
        end = j
        body_indent = None
        cc, cog = 1, 0
        while j < len(lines):
            ln = lines[j].expandtabs()
            if ln.strip() == "":
                j += 1
                continue
            ind = len(ln) - len(ln.lstrip())
            if ind <= indent:
                break
            if body_indent is None:
                body_indent = ind
            nest = max(0, (ind - body_indent) // 4)
            hits = br.findall(ln)
            cc += len(hits)
            cog += sum(1 if h in BOOL_OPS else 1 + nest for h in hits)
            end = j + 1
            j += 1
        funcs.append({"name": m.group(2), "start": i + 1, "end": end, "cyclomatic": cc, "cognitive": cog})
    return funcs


def analyze_file(path, rel):
    lang = LANG_BY_EXT.get(os.path.splitext(path)[1].lower())
    if not lang:
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return None
    total_lines = len(text.splitlines())
    src, eff = text, lang
    if lang == "vue":
        src, eff = vue_script(text)
        if src is None:
            return {"file": rel, "language": "vue", "lines": total_lines, "code_lines": 0, "functions": []}
    if eff == "python":
        stripped = strip_python(src)
        funcs = python_functions(stripped)
    else:
        stripped = strip_c_like(src)
        funcs = brace_functions(stripped, eff)
    code_lines = sum(1 for ln in stripped.split("\n") if ln.strip() and ln.strip() not in ("{", "}", "};", "});"))
    for f in funcs:
        f["length"] = f["end"] - f["start"] + 1
    return {"file": rel, "language": lang, "lines": total_lines, "code_lines": code_lines, "functions": funcs}


def in_hidden_dir(rel):
    """True when any folder in a repo-relative path starts with a dot (.github, .vscode, ...)."""
    return any(p.startswith(".") for p in rel.split("/")[:-1])


def iter_code_files(root, excludes=()):
    for full in repo_walk.iter_files(root, exts=set(LANG_BY_EXT), names=frozenset(), extra_skip=EXTRA_SKIP):
        rel = repo_walk.rel(root, full)
        if in_hidden_dir(rel) or "wwwroot/lib" in rel.rsplit("/", 1)[0]:
            continue
        if any(fnmatch.fnmatch(os.path.basename(full), g) for g in SKIP_FILE_GLOBS):
            continue
        if any(fnmatch.fnmatch(rel, g) for g in excludes):
            continue
        yield full, rel


def analyze_repo(root, excludes=()):
    return [r for r in (analyze_file(full, rel) for full, rel in iter_code_files(root, excludes)) if r]


def function_index(files):
    return {f["file"]: f["functions"] for f in files}


def function_at(index, rel, line):
    """Innermost function in index[rel] containing line, or None."""
    best = None
    for f in index.get(rel, []):
        if f["start"] <= line <= f["end"] and (best is None or f["length"] < best["length"]):
            best = f
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out")
    ap.add_argument("--md")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--cc", type=int, default=15, help="flag functions with cyclomatic above this")
    ap.add_argument("--cognitive", type=int, default=15)
    ap.add_argument("--fn-lines", type=int, default=80)
    ap.add_argument("--file-lines", type=int, default=600)
    ap.add_argument("--exclude", action="append", default=[], help="repo-relative glob to skip (repeatable)")
    a = ap.parse_args()

    files = analyze_repo(a.root, a.exclude)
    all_funcs = [dict(fn, file=f["file"]) for f in files for fn in f["functions"]]
    all_funcs.sort(key=lambda x: (x["cyclomatic"], x["length"]), reverse=True)
    flagged = []
    for f in all_funcs:
        flags = []
        if f["cyclomatic"] > 50:
            flags.append("cc-very-high")
        elif f["cyclomatic"] > 20:
            flags.append("cc-high")
        elif f["cyclomatic"] > a.cc:
            flags.append("cc-moderate")
        if f["cognitive"] > a.cognitive:
            flags.append("cognitive")
        if f["length"] > 150:
            flags.append("oversized-function")
        elif f["length"] > a.fn_lines:
            flags.append("long-function")
        if flags:
            flagged.append(dict(f, flags=flags))
    big_files = sorted([{"file": f["file"], "lines": f["lines"], "code_lines": f["code_lines"],
                         "flag": "oversized-file" if f["lines"] > 1000 else "long-file"}
                        for f in files if f["lines"] > a.file_lines], key=lambda x: -x["lines"])
    fn_lines = sum(fn["length"] for fn in all_funcs)
    complex_lines = sum(fn["length"] for fn in all_funcs if fn["cyclomatic"] > a.cc)
    result = {
        "root": os.path.abspath(a.root),
        "thresholds": {"cc": a.cc, "cognitive": a.cognitive, "fn_lines": a.fn_lines, "file_lines": a.file_lines},
        "totals": {"files": len(files), "code_lines": sum(f["code_lines"] for f in files),
                   "functions": len(all_funcs), "function_lines": fn_lines,
                   "lines_in_complex_functions": complex_lines,
                   "complex_function_line_share": round(complex_lines / fn_lines, 3) if fn_lines else 0.0},
        "flagged_functions": flagged[:a.top] if a.top > 0 else flagged,
        "large_files": big_files,
        "files": files,
        "note": "Approximate keyword-count metrics; confirm top items by reading the code or with the stack's analyzer.",
    }
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("| Function | Location | CC | Cognitive | Lines | Flags |\n|---|---|---|---|---|---|\n")
            for f in result["flagged_functions"]:
                fh.write("| %s | `%s:%d` | %d | %d | %d | %s |\n" % (f["name"], f["file"], f["start"], f["cyclomatic"],
                                                                   f["cognitive"], f["length"], ", ".join(f["flags"])))
            fh.write("\n| File | Lines | Flag |\n|---|---|---|\n")
            for b in big_files:
                fh.write("| `%s` | %d | %s |\n" % (b["file"], b["lines"], b["flag"]))
    print(json.dumps({"files": len(files), "functions": len(all_funcs), "flagged": len(flagged),
                      "top": ["%s:%d %s cc=%d len=%d" % (f["file"], f["start"], f["name"], f["cyclomatic"], f["length"])
                              for f in flagged[:5]]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
