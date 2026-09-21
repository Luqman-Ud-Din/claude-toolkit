#!/usr/bin/env python3
"""List third-party scripts without Subresource Integrity, inline scripts and
inline event handlers (CSP blockers), and javascript: URLs in HTML-like files.

Usage:
    python scan_html_scripts.py <repo_root> [--out scripts.json] [--md scripts.md]
                                [--own-host example.com ...]

Scans *.html, *.htm, *.cshtml, *.razor, *.ejs, *.hbs, *.njk, *.jsp, *.ftl,
*.ftlh, *.vue and *.tsx/*.jsx files that contain a literal <script tag.

Output (JSON):
{
  "root": "...",
  "external_scripts": [{"file", "line", "src", "integrity": true|false, "crossorigin": true|false}],
  "inline_scripts":   [{"file", "line", "snippet"}],
  "inline_handlers":  [{"file", "line", "attr", "snippet"}],
  "javascript_urls":  [{"file", "line", "snippet"}],
  "summary": {"external_without_sri": n, "inline_scripts": n, "inline_handlers": n, "javascript_urls": n}
}
Every row is a candidate for the manual pass: a tag manager legitimately has no
SRI (record it as Low with the CSP host allow-list as the control); a JSON-LD
block is not a CSP problem (skipped here by type).
Read-only: nothing in the audited repo is modified.
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
_REPO_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
if not os.path.exists(_REPO_WALK):
    sys.exit("audit-code-scan must be reachable from this skill (audit-core plugin or sibling layout; expected " + _REPO_WALK + ")")
_rw_spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _REPO_WALK)
repo_walk = importlib.util.module_from_spec(_rw_spec)
_rw_spec.loader.exec_module(repo_walk)

EXTS = {".html", ".htm", ".cshtml", ".razor", ".ejs", ".hbs", ".handlebars", ".njk", ".jsp", ".jspx",
        ".ftl", ".ftlh", ".vue", ".tsx", ".jsx", ".mustache"}

SCRIPT_TAG = re.compile(r"<script\b([^>]*)>", re.IGNORECASE)
SRC_ATTR = re.compile(r"\bsrc\s*=\s*[\"']?([^\"'\s>]+)", re.IGNORECASE)
TYPE_ATTR = re.compile(r"\btype\s*=\s*[\"']?([^\"'\s>]+)", re.IGNORECASE)
INTEGRITY = re.compile(r"\bintegrity\s*=", re.IGNORECASE)
CROSSORIGIN = re.compile(r"\bcrossorigin\b", re.IGNORECASE)
HANDLER = re.compile(r"<[a-zA-Z][^>]*?\s(on[a-z]+)\s*=\s*[\"']", re.IGNORECASE)
JS_URL = re.compile(r"(href|src|action|formaction|xlink:href)\s*=\s*[\"']\s*javascript:", re.IGNORECASE)
NON_CSP_TYPES = {"application/json", "application/ld+json", "text/template", "text/x-template",
                 "text/x-handlebars-template", "importmap"}


def iter_files(root):
    # Shared skip list and size cap from audit-code-scan; only the HTML-like extensions above.
    return repo_walk.iter_files(root, exts=EXTS, names=frozenset())


def is_external(src, own_hosts):
    s = src.strip().lower()
    if s.startswith("//"):
        host = s[2:].split("/", 1)[0]
    elif s.startswith("http://") or s.startswith("https://"):
        host = s.split("//", 1)[1].split("/", 1)[0]
    else:
        return False
    return not any(host == h or host.endswith("." + h) for h in own_hosts)


def scan_file(path, rel, own_hosts, result):
    text = repo_walk.read_text(path)
    if "<script" not in text.lower():
        # still look for handlers / javascript: urls
        pass
    lines = text.splitlines()
    for n, line in enumerate(lines, 1):
        for m in SCRIPT_TAG.finditer(line):
            attrs = m.group(1)
            src = SRC_ATTR.search(attrs)
            typ = TYPE_ATTR.search(attrs)
            if src:
                if is_external(src.group(1), own_hosts):
                    result["external_scripts"].append({
                        "file": rel, "line": n, "src": src.group(1),
                        "integrity": bool(INTEGRITY.search(attrs)),
                        "crossorigin": bool(CROSSORIGIN.search(attrs)),
                    })
            else:
                if typ and typ.group(1).lower() in NON_CSP_TYPES:
                    continue
                # Vue SFC <script setup>/<script lang=ts> blocks are component code, not inline page scripts
                if rel.endswith(".vue"):
                    continue
                # find first non-empty content after the tag (same line or following lines)
                after = line[m.end():].strip()
                idx = n
                while not after and idx < len(lines):
                    after = lines[idx].strip()
                    idx += 1
                if after.lower().startswith("</script"):
                    continue
                result["inline_scripts"].append({"file": rel, "line": n, "snippet": after[:120]})
        for h in HANDLER.finditer(line):
            result["inline_handlers"].append({"file": rel, "line": n, "attr": h.group(1).lower(),
                                              "snippet": line.strip()[:120]})
        if JS_URL.search(line):
            result["javascript_urls"].append({"file": rel, "line": n, "snippet": line.strip()[:120]})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out", default=None)
    ap.add_argument("--md", default=None)
    ap.add_argument("--own-host", action="append", default=[],
                    help="hostname(s) considered first-party (no SRI needed)")
    args = ap.parse_args()

    own = [h.lower() for h in args.own_host]
    result = {"root": os.path.abspath(args.root), "external_scripts": [], "inline_scripts": [],
              "inline_handlers": [], "javascript_urls": []}
    for path in iter_files(args.root):
        rel = repo_walk.rel(args.root, path)
        scan_file(path, rel, own, result)

    result["summary"] = {
        "external_without_sri": sum(1 for s in result["external_scripts"] if not s["integrity"]),
        "external_total": len(result["external_scripts"]),
        "inline_scripts": len(result["inline_scripts"]),
        "inline_handlers": len(result["inline_handlers"]),
        "javascript_urls": len(result["javascript_urls"]),
    }
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("| File | Kind | src / snippet | SRI | Issue |\n|---|---|---|---|---|\n")
            for s in result["external_scripts"]:
                fh.write(f"| `{s['file']}:{s['line']}` | external | {s['src']} | "
                         f"{'present' if s['integrity'] else 'missing'} | "
                         f"{'' if s['integrity'] else 'no integrity attribute'} |\n")
            for s in result["inline_scripts"]:
                snippet = s["snippet"].replace("|", "\\|")
                fh.write(f"| `{s['file']}:{s['line']}` | inline | `{snippet}` | n/a | blocks nonce/hash CSP |\n")
            for s in result["inline_handlers"]:
                snippet = s["snippet"].replace("|", "\\|")
                fh.write(f"| `{s['file']}:{s['line']}` | handler {s['attr']} | `{snippet}` | n/a | blocks strict CSP |\n")
            for s in result["javascript_urls"]:
                snippet = s["snippet"].replace("|", "\\|")
                fh.write(f"| `{s['file']}:{s['line']}` | javascript: URL | `{snippet}` | n/a | script in URL |\n")
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
