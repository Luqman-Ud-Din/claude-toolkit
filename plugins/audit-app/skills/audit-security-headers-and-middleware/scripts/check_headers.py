#!/usr/bin/env python3
"""Fetch a URL and grade its security headers and cookie flags.

Usage:
    python check_headers.py <url> [--path /extra/path ...] [--header "Name: value" ...]
                            [--method GET] [--no-redirect] [--insecure] [--timeout 15]
                            [--out live-headers.json] [--md live-headers.md]

Only runs against the URL the user supplied (plus any --path suffixes on the
same origin). Sends one plain request per path with a browser-like User-Agent
and nothing else; follows redirects by default so the final response is graded
(the redirect chain is recorded).

Grades (per references/headers-checklist.md):
  pass          - header present with an acceptable value
  missing       - header absent
  misconfigured - header present but weak (see 'why')
  info          - observation only (Server/X-Powered-By present, COOP/CORP absent, Cache-Control)

Cookie flags: every Set-Cookie is parsed and graded for HttpOnly, Secure, SameSite.
Cookies whose name audit-sensitive-data-catalog classifies as a credential or secret
(session, auth, token, API-key cookies) are graded stricter.

Exit code 0 always (this is evidence collection, not a gate). Stdlib only.
"""
import argparse
import importlib.util
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

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
_SDC_PATH = os.path.join(_SKILLS, "audit-sensitive-data-catalog", "scripts", "catalog.py")
if not os.path.exists(_SDC_PATH):
    sys.exit("audit-sensitive-data-catalog must be reachable from this skill (audit-core plugin or sibling layout; expected " + _SDC_PATH + ")")
_spec = importlib.util.spec_from_file_location("sensitive_data_catalog", _SDC_PATH)
sdc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sdc)

SECRETISH = ("credential", "secret")

HSTS_MIN = 15552000  # 180 days
UA = "Mozilla/5.0 (audit-security-headers-and-middleware; +check_headers.py)"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url, method, extra_headers, follow, insecure, timeout):
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    handlers = [urllib.request.HTTPSHandler(context=ctx)]
    if not follow:
        handlers.append(NoRedirect())
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, **extra_headers})
    chain = []
    try:
        with opener.open(req, timeout=timeout) as resp:
            headers = resp.headers
            status = resp.status
            final = resp.geturl()
            body_head = resp.read(2048)
    except urllib.error.HTTPError as e:
        headers, status, final, body_head = e.headers, e.code, e.geturl() if hasattr(e, "geturl") else url, b""
    except Exception as e:  # network error
        return {"url": url, "error": f"{type(e).__name__}: {e}"}
    if final != url:
        chain.append({"from": url, "to": final})
    raw = {}
    cookies = []
    for k, v in headers.items():
        if k.lower() == "set-cookie":
            cookies.append(v)
        else:
            raw.setdefault(k, []).append(v)
    return {"url": url, "final_url": final, "status": status, "redirects": chain,
            "headers": {k: "; ".join(v) for k, v in raw.items()},
            "set_cookie": cookies, "content_type": headers.get("Content-Type", ""),
            "body_head": body_head.decode("utf-8", "ignore")[:200]}


def h(headers, name):
    for k, v in headers.items():
        if k.lower() == name.lower():
            return v
    return None


def grade_csp(value):
    if value is None:
        return "missing", "no Content-Security-Policy header"
    low = value.lower()
    problems = []
    directives = {d.strip().split(" ")[0]: d.strip() for d in low.split(";") if d.strip()}
    script = directives.get("script-src") or directives.get("default-src")
    if not script:
        problems.append("no script-src or default-src")
    else:
        if "'unsafe-inline'" in script and "'nonce-" not in script and "'sha256-" not in script and "'strict-dynamic'" not in script:
            problems.append("script-src allows 'unsafe-inline' without nonce/hash")
        if "'unsafe-eval'" in script:
            problems.append("script-src allows 'unsafe-eval'")
        if re.search(r"(^|\s)\*(\s|$)", script) or " http:" in script or " https:" in script and "'self'" not in script:
            problems.append("script-src allows any host")
        if " data:" in script:
            problems.append("script-src allows data:")
    if "object-src" not in directives and "default-src" not in directives:
        problems.append("no object-src (and no default-src)")
    if "frame-ancestors" not in directives:
        problems.append("no frame-ancestors (X-Frame-Options must cover framing)")
    if "base-uri" not in directives:
        problems.append("no base-uri")
    return ("misconfigured", "; ".join(problems)) if problems else ("pass", "")


def grade_hsts(value, is_https):
    if value is None:
        return ("missing", "no Strict-Transport-Security header" + ("" if is_https else " (response was not HTTPS)"))
    m = re.search(r"max-age\s*=\s*(\d+)", value, re.I)
    if not m:
        return "misconfigured", "no max-age"
    age = int(m.group(1))
    if age == 0:
        return "misconfigured", "max-age=0 disables HSTS"
    if age < HSTS_MIN:
        return "misconfigured", f"max-age {age} < {HSTS_MIN} (180 days)"
    if "includesubdomains" not in value.lower():
        return "pass", "consider includeSubDomains"
    return "pass", ""


def grade_headers(headers, is_https):
    rows = []

    def add(name, expected, status, why, value):
        rows.append({"header": name, "expected": expected, "value": value, "status": status, "why": why})

    v = h(headers, "Content-Security-Policy")
    ro = h(headers, "Content-Security-Policy-Report-Only")
    s, why = grade_csp(v)
    if v is None and ro:
        s, why = "misconfigured", "only Report-Only policy present (not enforced)"
    add("Content-Security-Policy", "default-src/script-src without unsafe-inline/eval or *, object-src 'none', frame-ancestors, base-uri", s, why, v or ro)

    v = h(headers, "Strict-Transport-Security")
    s, why = grade_hsts(v, is_https)
    add("Strict-Transport-Security", f"max-age>={HSTS_MIN}; includeSubDomains", s, why, v)

    v = h(headers, "X-Content-Type-Options")
    add("X-Content-Type-Options", "nosniff", "pass" if v and v.strip().lower() == "nosniff" else ("missing" if v is None else "misconfigured"),
        "" if v and v.strip().lower() == "nosniff" else ("absent" if v is None else f"value '{v}'"), v)

    v = h(headers, "X-Frame-Options")
    csp = (h(headers, "Content-Security-Policy") or "").lower()
    if v is None:
        if "frame-ancestors" in csp:
            add("X-Frame-Options", "DENY or SAMEORIGIN (or CSP frame-ancestors)", "pass", "covered by CSP frame-ancestors", None)
        else:
            add("X-Frame-Options", "DENY or SAMEORIGIN (or CSP frame-ancestors)", "missing", "absent and no frame-ancestors", None)
    else:
        ok = v.strip().upper() in ("DENY", "SAMEORIGIN")
        add("X-Frame-Options", "DENY or SAMEORIGIN", "pass" if ok else "misconfigured", "" if ok else f"value '{v}' (ALLOW-FROM is ignored by browsers)", v)

    v = h(headers, "Referrer-Policy")
    good = {"no-referrer", "same-origin", "strict-origin", "strict-origin-when-cross-origin"}
    if v is None:
        add("Referrer-Policy", "strict-origin-when-cross-origin or stricter", "missing", "absent", None)
    else:
        pol = [p.strip().lower() for p in v.split(",")][-1]
        add("Referrer-Policy", "strict-origin-when-cross-origin or stricter", "pass" if pol in good else "misconfigured",
            "" if pol in good else f"policy '{pol}' leaks the URL", v)

    v = h(headers, "Permissions-Policy") or h(headers, "Feature-Policy")
    if v is None:
        add("Permissions-Policy", "disable unused features (camera=(), microphone=(), geolocation=())", "missing", "absent", None)
    else:
        bad = re.search(r"(camera|microphone|geolocation|payment)\s*=\s*\*", v)
        add("Permissions-Policy", "disable unused features", "misconfigured" if bad else "pass", "sensitive feature allowed for all origins" if bad else "", v)

    for name in ("Server", "X-Powered-By", "X-AspNet-Version", "X-AspNetMvc-Version"):
        v = h(headers, name)
        if v:
            versioned = bool(re.search(r"\d", v))
            add(name, "absent", "misconfigured" if versioned else "info", "version disclosed" if versioned else "product disclosed", v)
        else:
            add(name, "absent", "pass", "", None)

    v = h(headers, "Cache-Control")
    add("Cache-Control", "no-store for authenticated responses", "info", "check on authenticated pages", v)
    for name in ("Cross-Origin-Opener-Policy", "Cross-Origin-Resource-Policy"):
        v = h(headers, name)
        add(name, "same-origin (hardening)", "pass" if v else "info", "" if v else "absent (optional hardening)", v)

    v = h(headers, "Access-Control-Allow-Origin")
    if v:
        cred = (h(headers, "Access-Control-Allow-Credentials") or "").lower() == "true"
        if v.strip() == "*" and cred:
            add("Access-Control-Allow-Origin", "explicit origin", "misconfigured", "wildcard with credentials", v)
        elif v.strip() == "*":
            add("Access-Control-Allow-Origin", "explicit origin", "info", "wildcard without credentials (fine for public APIs)", v)
        else:
            add("Access-Control-Allow-Origin", "explicit origin", "pass", "verify it is an allow-list, not a reflected Origin", v)
    return rows


def grade_cookies(set_cookie_values, is_https):
    rows = []
    for raw in set_cookie_values:
        parts = [p.strip() for p in raw.split(";")]
        name = parts[0].split("=", 1)[0].strip()
        attrs = {p.split("=", 1)[0].strip().lower(): (p.split("=", 1)[1].strip() if "=" in p else True) for p in parts[1:]}
        r = sdc.classify_name(name, context="cookie")
        authish = r["sensitive"] and r["category"] in SECRETISH
        problems = []
        if "httponly" not in attrs and not name.lower().startswith(("xsrf", "csrf")):
            problems.append("no HttpOnly")
        if "secure" not in attrs and is_https:
            problems.append("no Secure")
        ss = attrs.get("samesite")
        if ss is None:
            problems.append("no SameSite (browser default Lax)")
        elif str(ss).lower() == "none" and "secure" not in attrs:
            problems.append("SameSite=None without Secure")
        status = "pass" if not problems else ("misconfigured" if authish or "no HttpOnly" in problems or "no Secure" in problems else "info")
        rows.append({"cookie": name, "auth_like": authish, "httponly": "httponly" in attrs, "secure": "secure" in attrs,
                     "samesite": ss if ss is not None else None, "path": attrs.get("path"), "expires": attrs.get("expires") or attrs.get("max-age"),
                     "status": status, "why": "; ".join(problems)})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--path", action="append", default=[], help="extra path(s) on the same origin")
    ap.add_argument("--header", action="append", default=[], help='extra request header, e.g. "Authorization: Bearer x"')
    ap.add_argument("--method", default="GET")
    ap.add_argument("--no-redirect", action="store_true")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification (self-signed staging)")
    ap.add_argument("--timeout", type=int, default=15)
    ap.add_argument("--out", default=None)
    ap.add_argument("--md", default=None)
    args = ap.parse_args()

    extra = {}
    for hdr in args.header:
        if ":" in hdr:
            k, v = hdr.split(":", 1)
            extra[k.strip()] = v.strip()
    base = args.url if re.match(r"^https?://", args.url, re.I) else "https://" + args.url
    targets = [base] + [urllib.parse.urljoin(base if base.endswith("/") else base + "/", p.lstrip("/")) for p in args.path]

    results = []
    for t in targets:
        r = fetch(t, args.method.upper(), extra, not args.no_redirect, args.insecure, args.timeout)
        if "error" in r:
            results.append(r)
            continue
        is_https = r["final_url"].lower().startswith("https://")
        r["header_grades"] = grade_headers(r["headers"], is_https)
        r["cookie_grades"] = grade_cookies(r["set_cookie"], is_https)
        r["summary"] = {s: sum(1 for g in r["header_grades"] if g["status"] == s) for s in ("pass", "missing", "misconfigured", "info")}
        r["summary"]["cookies_misconfigured"] = sum(1 for c in r["cookie_grades"] if c["status"] == "misconfigured")
        results.append(r)

    doc = {"requested": args.url, "results": results}
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
    lines = []
    for r in results:
        if "error" in r:
            lines.append(f"### {r['url']}\n\nrequest failed: {r['error']}\n")
            continue
        lines.append(f"### {r['final_url']} (HTTP {r['status']})\n")
        if r["redirects"]:
            lines.append("Redirects: " + " -> ".join([r["redirects"][0]["from"]] + [x["to"] for x in r["redirects"]]) + "\n")
        lines.append("| Header | Expected | Value | Status | Why |\n|---|---|---|---|---|")
        for g in r["header_grades"]:
            val = (g["value"] or "").replace("|", "\\|")
            lines.append(f"| {g['header']} | {g['expected']} | `{val[:100]}` | **{g['status']}** | {g['why']} |")
        lines.append("")
        lines.append("| Cookie | Auth-like | HttpOnly | Secure | SameSite | Path | Expires | Status | Why |\n|---|---|---|---|---|---|---|---|---|")
        for c in r["cookie_grades"]:
            lines.append(f"| {c['cookie']} | {'yes' if c['auth_like'] else 'no'} | {'yes' if c['httponly'] else 'no'} | {'yes' if c['secure'] else 'no'} | "
                         f"{c['samesite'] or '-'} | {c['path'] or '-'} | {c['expires'] or 'session'} | **{c['status']}** | {c['why']} |")
        if not r["cookie_grades"]:
            lines.append("| (no Set-Cookie on this response) | | | | | | | | |")
        lines.append("")
    text = "\n".join(lines)
    try:  # Windows consoles default to cp1252 and choke on non-ASCII values
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
