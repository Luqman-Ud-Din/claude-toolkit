#!/usr/bin/env python3
"""Extract the HTTP middleware/pipeline order from source for a given stack,
compare it with the expected order, and emit a Mermaid diagram with issues marked.

Usage:
    python extract_middleware.py <repo_root> --stack dotnet|node-express|python-django|java-spring
                                 [--file <pipeline file> ...] [--out middleware.json] [--md middleware.md]

Per stack it looks for:
  dotnet         Program.cs / Startup.cs: every `app.Use*(` / `app.Map*(` / `app.Run(` call in source order,
                 plus `builder.Services.Add*` registrations that matter (AddCors, AddRateLimiter, AddAntiforgery, AddHsts).
  node-express   app.ts/server.ts/index.js/main.ts: `app.use(...)`, `app.get|post|...(...)`, `app.register(...)` (Fastify),
                 `app.enableCors(`, `app.useGlobal*(` (Nest) in source order.
  python-django  settings*.py: the MIDDLEWARE list (order = execution order for requests).
  java-spring    *SecurityConfig*.java / any file with `SecurityFilterChain`: `http.xxx(` chain calls and
                 `addFilterBefore/After/At(` registrations in source order.

Every registration is classified into a stage (exception, hsts, https, headers, static, routing, cors,
bodylimit, session, csrf, authentication, authorization, ratelimit, endpoints, other) and ranked against
the canonical order from references/headers-checklist.md. Issues reported:
  * out-of-order pairs that matter (auth after endpoints, authz before authn, cors after authn, ...)
  * expected stages that are absent (headers, hsts, cors, authentication, authorization, ratelimit, csrf*)
    (* csrf is only reported as missing when a cookie/session stage is present)
Everything is a candidate for the manual pass: conditional registrations and extension methods that
hide pipeline pieces must be opened by hand. Read-only.
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

CANON = ["exception", "hsts", "https", "headers", "static", "routing", "cors", "bodylimit", "session",
         "csrf", "authentication", "authorization", "ratelimit", "endpoints"]
RANK = {s: i for i, s in enumerate(CANON)}
EXPECTED_PRESENT = ["exception", "headers", "hsts", "cors", "authentication", "authorization", "ratelimit", "endpoints"]

# (regex, stage) - first match wins; applied to the registration text
CLASSIFIERS = {
    "dotnet": [
        (r"UseDeveloperExceptionPage|UseExceptionHandler|UseStatusCodePages", "exception"),
        (r"UseHsts", "hsts"),
        (r"UseHttpsRedirection", "https"),
        (r"UseCsp|UseXfo|UseXContentTypeOptions|UseReferrerPolicy|UseSecurityHeaders|Headers\.(Append|Add|\[)|UseNWebsec|X-Frame-Options|Content-Security-Policy", "headers"),
        (r"UseStaticFiles|UseSpaStaticFiles|UseDefaultFiles|MapStaticAssets|UseFileServer", "static"),
        (r"UseRouting", "routing"),
        (r"UseCors", "cors"),
        (r"MaxRequestBodySize|RequestSizeLimit", "bodylimit"),
        (r"UseSession", "session"),
        (r"UseAntiforgery|AutoValidateAntiforgery", "csrf"),
        (r"UseAuthentication|UseJwtBearer|UseIdentity\b", "authentication"),
        (r"UseAuthorization", "authorization"),
        (r"UseRateLimiter|UseIpRateLimiting|UseClientRateLimiting", "ratelimit"),
        (r"MapControllers|MapControllerRoute|MapDefaultControllerRoute|UseEndpoints|MapRazorPages|MapGet|MapPost|MapPut|MapDelete|MapHub|MapGraphQL|MapBlazorHub|MapFallback|UseMvc\b|UseOcelot|MapReverseProxy|app\.Run\(", "endpoints"),
    ],
    "node-express": [
        (r"errorHandler|\(err,\s*req,\s*res|useGlobalFilters|setErrorHandler", "exception"),
        (r"helmet\.hsts|hsts\s*:", "hsts"),
        (r"sslify|forceSSL|requireHTTPS|httpsRedirect", "https"),
        (r"helmet\(|helmet\.|@fastify/helmet|securityHeaders|setHeader\(\s*['\"](X-Frame|Content-Security|Strict-Transport)", "headers"),
        (r"express\.static|serveStatic|fastifyStatic|@fastify/static|ServeStaticModule", "static"),
        (r"cors\(|enableCors|@fastify/cors|fastifyCors", "cors"),
        (r"express\.json|express\.urlencoded|bodyParser|useBodyParser|bodyLimit|multer\(", "bodylimit"),
        (r"session\(|cookieSession|expressSession|@fastify/session|cookieParser|cookie-parser|fastifyCookie", "session"),
        (r"csurf|csrf|@fastify/csrf", "csrf"),
        (r"passport\.(initialize|authenticate|session)|authenticate\b|jwtMiddleware|verifyToken|requireAuth|authMiddleware|useGlobalGuards|AuthGuard|expressjwt|jwtCheck", "authentication"),
        (r"authorize\b|requireRole|rbac|checkPermission|RolesGuard|PoliciesGuard", "authorization"),
        (r"rateLimit|RateLimit|rate-limit|slowDown|ThrottlerGuard|@fastify/rate-limit|rateLimiter", "ratelimit"),
        (r"app\.(get|post|put|patch|delete|all)\s*\(|Router\(\)|router\b|app\.use\(\s*['\"][^'\"]+['\"]\s*,\s*\w*(Router|routes|router|Routes)|listen\(", "endpoints"),
    ],
    "python-django": [
        (r"SecurityMiddleware", "headers"),
        (r"WhiteNoiseMiddleware|StaticFilesMiddleware", "static"),
        (r"CorsMiddleware|corsheaders", "cors"),
        (r"SessionMiddleware", "session"),
        (r"CsrfViewMiddleware", "csrf"),
        (r"AuthenticationMiddleware|RemoteUserMiddleware|JWTAuthMiddleware|TokenMiddleware", "authentication"),
        (r"CSPMiddleware|XFrameOptionsMiddleware|PermissionsPolicyMiddleware|ReferrerPolicyMiddleware", "headers"),
        (r"RatelimitMiddleware|AxesMiddleware|ThrottleMiddleware", "ratelimit"),
        (r"CommonMiddleware", "routing"),
        (r"MessageMiddleware|LocaleMiddleware|GZipMiddleware|ConditionalGetMiddleware", "other"),
    ],
    "java-spring": [
        (r"exceptionHandling", "exception"),
        (r"httpStrictTransportSecurity|hsts", "hsts"),
        (r"requiresChannel|requiresSecure", "https"),
        (r"\.headers\(|contentSecurityPolicy|frameOptions|referrerPolicy|permissionsPolicy|xssProtection|contentTypeOptions", "headers"),
        (r"\.cors\(|CorsFilter|CorsConfigurationSource", "cors"),
        (r"sessionManagement|sessionCreationPolicy", "session"),
        (r"\.csrf\(", "csrf"),
        (r"oauth2ResourceServer|oauth2Login|formLogin|httpBasic|addFilterBefore|addFilterAfter|addFilterAt|jwtAuthenticationConverter|authenticationProvider|UsernamePasswordAuthenticationFilter", "authentication"),
        (r"authorizeHttpRequests|authorizeRequests|authorizeExchange|requestMatchers|antMatchers|anyRequest", "authorization"),
        (r"RateLimit|Bucket4j|bucket4j|RequestRateLimiter|rateLimiter", "ratelimit"),
        (r"http\.build\(\)", "endpoints"),
    ],
}

PIPELINE_FILE_HINTS = {
    "dotnet": [r"^Program\.cs$", r"^Startup\.cs$", r"ApplicationBuilderExtensions\.cs$", r"Middleware.*Extensions\.cs$"],
    "node-express": [r"^(app|server|index|main)\.(js|ts|mjs|cjs)$"],
    "python-django": [r"^settings.*\.py$", r"^(base|prod|production|local|dev|development)\.py$"],
    "java-spring": [r"SecurityConfig\w*\.(java|kt)$", r"WebSecurity\w*\.(java|kt)$", r"SecurityConfiguration\w*\.(java|kt)$"],
}

EXTRACTORS = {
    "dotnet": re.compile(r"^[ \t]*(?:app|application|builder\.App)\s*\.\s*((?:Use|Map|Run)\w*)\s*\(", re.M),
    "node-express": re.compile(r"^[ \t]*(?:app|server|fastify|router)\s*\.\s*(use|get|post|put|patch|delete|all|register|enableCors|useGlobalGuards|useGlobalFilters|useGlobalPipes|useBodyParser|setErrorHandler|listen)\s*\(([^\n]*)", re.M),
    "java-spring": re.compile(r"(\.\s*(?:csrf|cors|headers|sessionManagement|exceptionHandling|authorizeHttpRequests|authorizeRequests|oauth2ResourceServer|oauth2Login|formLogin|httpBasic|addFilterBefore|addFilterAfter|addFilterAt|requiresChannel|logout|rememberMe|securityMatcher|build)\s*\()", re.M),
}


def find_pipeline_files(root, stack):
    hints = [re.compile(h, re.I) for h in PIPELINE_FILE_HINTS[stack]]
    found = []
    # Shared skip list from audit-code-scan; every hint names a source extension the walker reads.
    for full in repo_walk.iter_files(root, names=frozenset()):
        fn = os.path.basename(full)
        if any(h.search(fn) for h in hints):
            if stack == "java-spring" and "SecurityFilterChain" not in repo_walk.read_text(full):
                continue
            if stack == "python-django" and "MIDDLEWARE" not in repo_walk.read_text(full):
                continue
            found.append(full)
    return found


def classify(stack, text):
    for rx, stage in CLASSIFIERS[stack]:
        if re.search(rx, text):
            return stage
    return "other"


def extract(stack, path, root):
    src = repo_walk.read_text(path)
    rel = repo_walk.rel(root, path)
    regs = []
    if stack == "python-django":
        m = re.search(r"MIDDLEWARE\s*(?:\+?=|:)\s*[\[(]([^\]\)]*)[\])]", src, re.S)
        if not m:
            return regs
        start = src[:m.start()].count("\n") + 1
        for i, line in enumerate(m.group(1).splitlines()):
            s = line.strip().strip(",").strip("'\"")
            if not s or s.startswith("#"):
                continue
            regs.append({"file": rel, "line": start + i, "text": s, "stage": classify(stack, s)})
        return regs
    rx = EXTRACTORS[stack]
    for m in rx.finditer(src):
        line_no = src.count("\n", 0, m.start()) + 1
        line_text = src[m.start():src.find("\n", m.start()) if src.find("\n", m.start()) != -1 else len(src)].strip()
        # conditional context: look back one line for `if (` guards
        prev = src.rfind("\n", 0, m.start() - 1)
        prev_line = src[src.rfind("\n", 0, prev) + 1:prev].strip() if prev > 0 else ""
        cond = bool(re.search(r"^\s*if\s*\(|IsDevelopment|IsProduction|NODE_ENV|DEBUG", prev_line + " " + line_text))
        text = m.group(1) if stack != "node-express" else (m.group(1) + "(" + (m.group(2) or "")[:120])
        # inline lambda middleware (app.Use(async (ctx, next) => { ... })) sets its headers a few
        # lines below the registration - classify on a small window so it is not all "other"
        window = line_text
        if re.search(r"=>\s*$|=>\s*\{|\(\s*$", line_text):
            end = src.find("\n", m.start())
            window = line_text + " " + src[end:end + 400].replace("\n", " ") if end != -1 else line_text
        regs.append({"file": rel, "line": line_no, "text": line_text[:160], "call": text, "stage": classify(stack, window),
                     "conditional": cond})
    return regs


def analyse(regs, stack):
    issues = []
    stages_present = [r["stage"] for r in regs if r["stage"] in RANK]
    first_index = {}
    for i, r in enumerate(regs):
        first_index.setdefault(r["stage"], i)
    last_index = {}
    for i, r in enumerate(regs):
        last_index[r["stage"]] = i

    def before(a, b):  # a registered before b (using first occurrence of a and last of b / first of b)
        return first_index[a] < first_index[b]

    checks = [
        ("authentication", "endpoints", "Critical", "authentication registered after endpoints - routes execute unauthenticated"),
        ("authorization", "endpoints", "Critical", "authorization registered after endpoints"),
        ("authentication", "authorization", "Medium", "authorization registered before authentication - user is not populated when policies run"),
        ("cors", "authentication", "Medium", "CORS registered after authentication - preflight requests are rejected"),
        ("hsts", "endpoints", "Low", "HSTS registered after endpoints"),
        ("https", "endpoints", "Low", "HTTPS redirect registered after endpoints"),
        ("headers", "endpoints", "Low", "security headers middleware registered after endpoints - responses from routes miss headers"),
        ("routing", "endpoints", "Low", "routing registered after endpoints"),
        ("session", "authentication", "Medium", "session registered after authentication (Django: SessionMiddleware must precede AuthenticationMiddleware)"),
        ("routing", "cors", "Info", "CORS registered before routing - in ASP.NET Core UseCors must sit between UseRouting and the endpoints"),
    ]
    if stack == "node-express":
        checks = [c for c in checks if c[0] != "routing"]
        # Express: error handler must be LAST
        if "exception" in first_index and "endpoints" in last_index and last_index["exception"] < last_index["endpoints"]:
            issues.append({"severity": "Medium", "stage": "exception", "issue": "Express error handler registered before the last route - errors from later routes bypass it"})
    if stack == "python-django":
        if "cors" in first_index and "routing" in first_index and first_index["cors"] > first_index["routing"]:
            issues.append({"severity": "Medium", "stage": "cors", "issue": "CorsMiddleware placed below CommonMiddleware - must be above it"})
        checks = [c for c in checks if not (c[0] == "routing" and c[1] == "cors")]
    for a, b, sev, msg in checks:
        if a in first_index and b in first_index and not before(a, b):
            if stack == "dotnet" and a == "exception":
                continue
            issues.append({"severity": sev, "stage": a, "issue": msg,
                           "evidence": f"{a} first at index {first_index[a]}, {b} first at index {first_index[b]}"})
    if stack == "dotnet" and "exception" in first_index and first_index["exception"] != 0:
        issues.append({"severity": "Low", "stage": "exception", "issue": "exception handler is not the first middleware - errors thrown earlier are not handled"})

    expected = list(EXPECTED_PRESENT)
    if stack == "python-django":
        expected = ["headers", "cors", "session", "csrf", "authentication"]
    if stack == "java-spring":
        expected = ["headers", "cors", "authentication", "authorization", "ratelimit"]
    for s in expected:
        if s not in first_index:
            sev = {"authentication": "High", "authorization": "High", "headers": "Medium", "hsts": "Medium", "cors": "Low",
                   "ratelimit": "Medium", "exception": "Low", "endpoints": "Info", "csrf": "High", "session": "Info"}.get(s, "Low")
            issues.append({"severity": sev, "stage": s, "issue": f"no '{s}' stage found in the pipeline file(s) - confirm it is not hidden in an extension method or host config"})
    if "session" in first_index and "csrf" not in first_index and stack != "python-django":
        issues.append({"severity": "High", "stage": "csrf", "issue": "session/cookie stage present but no CSRF protection stage found"})
    return issues


def mermaid(regs, issues):
    bad_stages = {i["stage"]: i for i in issues if not i["issue"].startswith("no '")}
    missing = [i for i in issues if i["issue"].startswith("no '")]
    lines = ["flowchart TD"]
    ids = []
    for n, r in enumerate(regs):
        label = r.get("call") or r["text"]
        label = re.sub(r"[\[\]\"`|{}]", "", label)[:60]
        mark = ""
        if r["stage"] in bad_stages:
            mark = f"  ✖ {bad_stages[r['stage']]['issue'][:60]}"
        if r.get("conditional"):
            mark += "  (conditional)"
        nid = f"N{n}"
        ids.append(nid)
        lines.append(f"    {nid}[\"{n + 1}. {label} : {r['stage']}{mark}\"]")
    for a, b in zip(ids, ids[1:]):
        lines.append(f"    {a} --> {b}")
    for k, m in enumerate(missing):
        lines.append(f"    M{k}[\"✖ missing: {m['stage']} - {m['issue'][:50]}\"]:::missing")
    if missing:
        lines.append("    classDef missing stroke-dasharray: 5 5")
    for n, r in enumerate(regs):
        if r["stage"] in bad_stages:
            lines.append(f"    style N{n} stroke:#d00,stroke-width:2px")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--stack", required=True, choices=sorted(CLASSIFIERS))
    ap.add_argument("--file", action="append", default=[], help="pipeline file(s) to parse instead of auto-detect")
    ap.add_argument("--out", default=None)
    ap.add_argument("--md", default=None)
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    files = [os.path.join(root, f) if not os.path.isabs(f) else f for f in args.file] or find_pipeline_files(root, args.stack)
    result = {"root": root, "stack": args.stack, "expected_order": CANON, "pipelines": []}
    for f in files:
        regs = extract(args.stack, f, root)
        if not regs:
            continue
        issues = analyse(regs, args.stack)
        result["pipelines"].append({"file": repo_walk.rel(root, f), "registrations": regs,
                                    "issues": issues, "mermaid": mermaid(regs, issues)})
    if not result["pipelines"]:
        result["warning"] = "no pipeline registrations found - pass --file or check references/<stack>.md for where the pipeline lives"

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    md = []
    for p in result["pipelines"]:
        md.append(f"### {p['file']}\n")
        md.append("| # | Line | Registration | Stage | Conditional |\n|---|---|---|---|---|")
        for n, r in enumerate(p["registrations"], 1):
            md.append(f"| {n} | {r['line']} | `{r['text'].replace('|', chr(92) + '|')[:90]}` | {r['stage']} | {'yes' if r.get('conditional') else ''} |")
        md.append("\nIssues:\n")
        for i in p["issues"] or [{"severity": "-", "issue": "none detected by the extractor"}]:
            md.append(f"- [{i['severity']}] {i['issue']}")
        md.append("\n```mermaid\n" + p["mermaid"] + "\n```\n")
    if "warning" in result:
        md.append(result["warning"])
    text = "\n".join(md)
    try:  # Windows consoles default to cp1252 and choke on the diagram markers
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
