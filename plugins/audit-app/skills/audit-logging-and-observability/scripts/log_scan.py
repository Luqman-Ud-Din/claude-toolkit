#!/usr/bin/env python3
"""Inventory log statements and flag the ones that leak sensitive fields, log a
caught exception below Warning, or build the message by string concatenation.

Usage:
    python log_scan.py <repo_root> [--out log-statements.json] [--md sensitive-log-table.md]
                       [--only-flagged] [--context 6]

What it does (read-only against the audited repo):
  * Finds logger calls in .cs, .java, .kt, .js, .mjs, .cjs, .ts, .tsx, .jsx, .vue and .py files:
    ILogger LogX / Serilog Log.X, SLF4J/Log4j log.x, pino/winston/console/Nest Logger,
    Python logging/structlog, plus stdout writers (Console.WriteLine, System.out.println,
    print) which are reported with level "stdout".
  * Reads the call's argument list (up to 8 lines), removes string-literal text but keeps
    interpolation / template placeholders ({Email}, ${user.token}, f"{password}"), then
    classifies each identifier with audit-sensitive-data-catalog and maps the result to the
    categories in references/sensitive-fields.md. Only plain values count, so userPassword and
    refreshToken hit while passwordPolicy, tokenExpiry and passwordHash do not.
  * Flags whole-object logging (req.body, request.data, headers, {@Dto} destructuring).
  * Flags a log call at trace/debug (or info) that sits inside a catch / except / .catch
    block within --context lines of the handler start.
  * Flags concatenated / interpolated messages (+, $"", f"", template literal, String.format,
    % formatting, .format()).

Outputs:
  JSON: {"root", "generated_at", "summary": {...}, "statements": [{"file", "line", "call",
         "level", "sensitive_fields": [{"field", "category"}], "whole_object": bool,
         "in_catch": bool, "catch_low_level": bool, "concatenated": bool, "snippet"}]}
  Markdown: the report table "file:line | logger call | sensitive fields | level", then the
         catch-block and concatenation tables.
Every row is a candidate; open the file and confirm the data shape before writing a finding.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone

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
_SDC_PATH = os.path.join(_SKILLS, "audit-sensitive-data-catalog", "scripts", "catalog.py")
if not os.path.exists(_SDC_PATH):
    sys.exit("audit-sensitive-data-catalog must be reachable from this skill (audit-core plugin or sibling layout; expected " + _SDC_PATH + ")")
_spec = importlib.util.spec_from_file_location("sensitive_data_catalog", _SDC_PATH)
sdc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sdc)

# Folders skipped on top of repo_walk.SKIP_DIRS: wwwroot holds static client libraries.
EXTRA_SKIP = ("wwwroot",)
CODE_EXT = {".cs", ".java", ".kt", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".py"}
MAX_BYTES = 1_500_000

WHOLE_OBJECT_RX = re.compile(
    r"\b(?:req|request|ctx\.request|context\.Request|HttpContext\.Request|Request)\s*\.\s*(?:body|Body|data|POST|json|form|Form|headers|Headers)\b"
    r"|\{@\w+\}|\bJSON\.stringify\s*\(\s*(?:req|request|body|payload)\b"
    r"|(?:^|[\s,(\{])(?:body|payload|headers|dto|model|form)(?=\s*[,)}])", re.I)

LEVEL_MAP = {
    "trace": "trace", "logtrace": "trace", "verbose": "trace", "finest": "trace",
    "debug": "debug", "logdebug": "debug", "fine": "debug",
    "info": "info", "information": "info", "loginformation": "info", "log": "info", "msg": "info",
    "warn": "warn", "warning": "warn", "logwarning": "warn",
    "error": "error", "logerror": "error", "exception": "error", "severe": "error",
    "critical": "critical", "logcritical": "critical", "fatal": "critical",
}
LOG_CALL_RX = re.compile(
    r"(?P<call>(?:\b(?:_?logger|_?log|LOG|LOGGER|log|Log|console|this\.logger|this\.log|self\.logger|self\.log|"
    r"req\.log|request\.log|logging|structlog\.get_logger\(\)|_logger|Logger|winston|pino)\s*\.\s*"
    r"(?P<level>LogTrace|LogDebug|LogInformation|LogWarning|LogError|LogCritical|trace|verbose|debug|info|"
    r"information|warn|warning|error|exception|critical|fatal|log|Verbose|Debug|Information|Warning|Error|Fatal|severe|fine|finest|msg))"
    r"|(?P<stdout>\bConsole\.Write(?:Line)?|\bSystem\.(?:out|err)\.print(?:ln|f)?|\bDebug\.WriteLine|(?<![\w.])print|\be\.printStackTrace))\s*\(")
CATCH_RX = re.compile(r"\bcatch\s*(?:\(|\{)|\bexcept\b[^:]*:|\.catch\s*\(|\brescue\b|\bonError\b|catchError\s*\(")
CONCAT_RX = re.compile(
    r"^\s*(?:\$@?\"|@\$\"|f\"|f'|rf\"|fr\"|`[^`]*\$\{|String\.format\s*\(|string\.Format\s*\()"
    r"|^\s*(?:\"[^\"]*\"|'[^']*')\s*\+"
    r"|^\s*[\w.]+\s*\+\s*(?:\"|')"
    r"|^\s*(?:\"[^\"]*\"|'[^']*')\s*%\s*[\w(]"
    r"|^\s*(?:\"[^\"]*\"|'[^']*')\s*\.format\s*\(")
STRING_RX = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`", re.S)
PLACEHOLDER_RX = re.compile(r"\$?\{\s*@?([A-Za-z_][\w.]*)")
IDENT_RX = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
EXCEPTION_ARG_RX = re.compile(r"(?:^|[,(\s{])(?:ex|e|err|error|exc|exception|throwable|t)\s*(?:[,)}]|$)", re.I)


_CRED_SUBS = {"password", "security-answer", "pin"}
_TOKEN_SUBS = {"token", "session", "cookie", "otp"}


def classify_identifier(identifier):
    """Return (normalised_name, category) when the identifier is a sensitive name, else None.
    Hashed, encrypted and masked forms (passwordHash, maskedPan) are not reported."""
    r = sdc.classify_name(identifier)
    if not r["sensitive"] or r["form"] != "plain":
        return None
    if r["category"] == "secret" or r["subcategory"] in _CRED_SUBS:
        cat = "credentials"
    elif r["subcategory"] in _TOKEN_SUBS:
        cat = "tokens"
    elif r["category"] == "financial":
        cat = "financial"
    else:
        cat = "personal"
    return r["matched"], cat


def extract_args(lines, idx, start_col):
    """Return the raw argument text of a call starting at lines[idx][start_col] == '('."""
    depth, out, quote = 0, [], None
    for j in range(idx, min(idx + 8, len(lines))):
        seg = lines[j][start_col:] if j == idx else lines[j]
        k = 0
        while k < len(seg):
            ch = seg[k]
            if quote:
                if ch == "\\":
                    out.append(seg[k:k + 2])
                    k += 2
                    continue
                if ch == quote:
                    quote = None
            elif ch in "\"'`":
                quote = ch
            elif ch == "(":
                depth += 1
                if depth == 1:
                    k += 1
                    continue
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return "".join(out)
            out.append(ch)
            k += 1
        out.append(" ")
        if quote in ("\"", "'"):
            quote = None
    return "".join(out)


def analyse_args(args):
    placeholders = []
    for s in STRING_RX.findall(args):
        placeholders += PLACEHOLDER_RX.findall(s)
    code = STRING_RX.sub(" \"\" ", args)
    found, seen = [], set()
    for token in IDENT_RX.findall(code) + [p for ph in placeholders for p in ph.split(".")]:
        hit = classify_identifier(token)
        if hit and hit[0] not in seen:
            seen.add(hit[0])
            found.append({"field": token, "category": hit[1]})
    whole = bool(WHOLE_OBJECT_RX.search(code)) or bool(re.search(r"\{@\w+\}", args))
    if whole:
        found.append({"field": (WHOLE_OBJECT_RX.search(code) or re.search(r"\{@\w+\}", args)).group(0).strip(" ,({"),
                      "category": "whole-object"})
    return found, whole, code


ACCESS_RX = re.compile(r"\b(?:req\.body|request\.body|request\.data|request\.POST|ctx\.request\.body|req|request|dto|model|input|command)\s*\.\s*(\w+)"
                       r"|\b(?:req\.body|request\.data|request\.POST)\[['\"](\w+)['\"]\]")


def inside_block(lines, c, i, col):
    """True when (line i, column col) is still inside the handler block that starts on line c.
    try/catch blocks are tracked by braces; promise .catch( / catchError( by parentheses."""
    m = CATCH_RX.search(lines[c])
    promise = m.group(0).lstrip().startswith((".catch", "catchError"))
    open_ch, close_ch = ("(", ")") if promise else ("{", "}")
    start = (m.end() - 1) if promise else m.start()
    if i == c:
        text = lines[c][start:col]
    else:
        text = lines[c][start:] + "\n" + "\n".join(lines[c + 1:i]) + "\n" + lines[i][:col]
    text = STRING_RX.sub('""', text)
    depth, opened = 0, False
    for ch in text:
        if ch == open_ch:
            depth += 1
            opened = True
        elif ch == close_ch and opened:
            depth -= 1
            if depth == 0:
                return False
    return opened


def scan_file(path, rel, context):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return []
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    is_py = rel.endswith(".py")
    catch_lines = [i for i, l in enumerate(lines) if CATCH_RX.search(l)]
    out = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("//", "#", "*", "/*")):
            continue
        for m in LOG_CALL_RX.finditer(line):
            if m.group("stdout") == "print" and not is_py:
                continue
            level = "stdout" if m.group("stdout") else LEVEL_MAP.get(m.group("level").lower(), "info")
            call = (m.group("call") or m.group("stdout")).replace(" ", "")
            args = extract_args(lines, i, m.end() - 1)
            fields, whole, code = analyse_args(args)
            if whole:
                # A whole body/DTO was logged: report the sensitive members the same handler reads
                # from that object (req.body.password on a login route), since they are in the log too.
                window = "\n".join(lines[max(0, i - 15): i + 15])
                for acc in ACCESS_RX.findall(window):
                    name = acc[0] or acc[1]
                    hit = classify_identifier(name)
                    if hit and not any(f["field"].lower().endswith(name.lower()) for f in fields):
                        fields.append({"field": name, "category": hit[1] + " (inside the logged object)"})
            in_catch = False
            for c in sorted((c for c in catch_lines if 0 <= i - c <= context), reverse=True):
                if is_py:
                    # an except block ends when indentation returns to the except line's level
                    indent = len(lines[c]) - len(lines[c].lstrip())
                    if all((len(l) - len(l.lstrip())) > indent or not l.strip() for l in lines[c + 1:i + 1]):
                        in_catch = True
                        break
                elif inside_block(lines, c, i, m.start()):
                    in_catch = True
                    break
            low = in_catch and level in ("trace", "debug", "info", "stdout")
            concat = bool(CONCAT_RX.search(args)) and level != "stdout"
            out.append({
                "file": rel, "line": i + 1, "call": call, "level": level,
                "sensitive_fields": fields, "whole_object": whole,
                "in_catch": in_catch, "catch_low_level": low,
                "catch_exception_arg": bool(in_catch and EXCEPTION_ARG_RX.search(code)),
                "concatenated": concat, "snippet": stripped[:220],
            })
    return out


def md_escape(s):
    return s.replace("|", "\\|").replace("`", "'")


def to_markdown(res):
    st = res["statements"]
    o = ["### Log statements containing sensitive fields", "",
         "| # | File:line | Logger call | Sensitive fields | Level |", "|---|---|---|---|---|"]
    n = 0
    for s in st:
        if s["sensitive_fields"]:
            n += 1
            f = ", ".join(f"{x['field']} ({x['category']})" for x in s["sensitive_fields"])
            o.append(f"| {n} | `{s['file']}:{s['line']}` | `{md_escape(s['snippet'][:110])}` | {f} | {s['level']} |")
    if n == 0:
        o.append("| - | none found | | | |")
    o += ["", "### Caught exceptions logged below Warning", "",
          "| # | File:line | Logger call | Level | Exception object passed |", "|---|---|---|---|---|"]
    n = 0
    for s in st:
        if s["catch_low_level"]:
            n += 1
            o.append(f"| {n} | `{s['file']}:{s['line']}` | `{md_escape(s['snippet'][:110])}` | {s['level']} | {'yes' if s['catch_exception_arg'] else 'no'} |")
    if n == 0:
        o.append("| - | none found | | | |")
    o += ["", "### Concatenated / interpolated log messages", "",
          "| # | File:line | Logger call | Level |", "|---|---|---|---|"]
    n = 0
    for s in st:
        if s["concatenated"]:
            n += 1
            o.append(f"| {n} | `{s['file']}:{s['line']}` | `{md_escape(s['snippet'][:110])}` | {s['level']} |")
    if n == 0:
        o.append("| - | none found | | |")
    sm = res["summary"]
    o += ["", f"Totals: {sm['statements']} log statements; by level {json.dumps(sm['by_level'])}; "
          f"{sm['sensitive']} with sensitive fields; {sm['catch_low_level']} low-level catch logs; "
          f"{sm['concatenated']} concatenated; {sm['stdout']} stdout writers.", ""]
    return "\n".join(o)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out")
    ap.add_argument("--md")
    ap.add_argument("--only-flagged", action="store_true", help="keep only flagged statements in the JSON")
    ap.add_argument("--context", type=int, default=6, help="lines after a catch/except that count as inside it")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    statements = []
    for full in repo_walk.iter_files(root, exts=CODE_EXT, extra_skip=EXTRA_SKIP, max_bytes=None):
        if full.endswith((".min.js", ".d.ts")):
            continue
        statements += scan_file(full, repo_walk.rel(root, full), a.context)
    by_level = {}
    for s in statements:
        by_level[s["level"]] = by_level.get(s["level"], 0) + 1
    summary = {"statements": len(statements), "by_level": by_level,
               "sensitive": sum(1 for s in statements if s["sensitive_fields"]),
               "catch_low_level": sum(1 for s in statements if s["catch_low_level"]),
               "concatenated": sum(1 for s in statements if s["concatenated"]),
               "stdout": by_level.get("stdout", 0)}
    if a.only_flagged:
        statements = [s for s in statements if s["sensitive_fields"] or s["catch_low_level"] or s["concatenated"]]
    res = {"root": root, "generated_at": datetime.now(timezone.utc).isoformat(), "summary": summary, "statements": statements}
    for path in (a.out, a.md):
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(to_markdown(res))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
