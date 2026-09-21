#!/usr/bin/env python3
"""Check correlation-id / trace-context propagation hop by hop:
frontend -> backend inbound -> backend log enrichment -> backend outbound (downstream)
-> id returned to the caller.

Usage:
    python correlation_check.py <repo_root> [--out correlation.json] [--md correlation.md]

How it decides (heuristic, read-only; confirm each hop by reading the code):
  * Frontend code = files under a folder whose package.json depends on @angular/core, react,
    vue, next or nuxt (or .tsx/.jsx/.vue files). Backend code = every other .cs/.java/.kt/.py/
    .js/.ts file.
  * frontend_outbound  present when an HTTP interceptor / fetch wrapper sets X-Correlation-Id,
    X-Request-Id or traceparent, or OTel web instrumentation propagates trace headers.
  * backend_inbound    present when middleware reads/creates the id (correlation middleware
    packages, genReqId, MDC.put, LogContext.PushProperty, asgi-correlation-id, OTel server
    instrumentation).
  * log_enrichment     present when the id reaches every log line (Enrich.FromLogContext,
    %X{...} / includeMdcKeyName, pino-http req.log / child loggers, merge_contextvars, a logging
    Filter adding request_id).
  * backend_outbound   n/a when there are no outbound HTTP calls; present when outbound clients
    forward the header or are OTel/Micrometer-instrumented; absent otherwise.
  * response_echo      present when the id is written back on the response.
The chain is reported as broken at the first absent hop.
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
CODE_EXT = {".cs", ".java", ".kt", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".json", ".xml", ".yml", ".yaml"}
FRONTEND_DEPS = re.compile(r"\"(?:@angular/core|react|vue|next|nuxt)\"\s*:")

HOPS = {
    "frontend_outbound": re.compile(
        r"x-correlation-id|x-request-id|correlation[-_]?id|traceparent|propagateTraceHeaderCorsUrls|"
        r"@opentelemetry/instrumentation-(?:fetch|xml-http-request)|@microsoft/applicationinsights-web|enableCorsCorrelation|sentry-trace", re.I),
    "backend_inbound": re.compile(
        r"X-Correlation-Id|X-Request-Id|CorrelationIdMiddleware|UseCorrelationId|AddCorrelationId|genReqId|express-request-id|"
        r"cls-rtracer|asgi_correlation_id|asgi-correlation-id|django_guid|django-guid|MDC\.put\(|LogContext\.PushProperty|"
        r"AddAspNetCoreInstrumentation|@opentelemetry/sdk-node|auto-instrumentations-node|opentelemetry-instrument|"
        r"micrometer-tracing|DjangoInstrumentor|FastAPIInstrumentor|FlaskInstrumentor|correlation_id\s*=|request_id\s*=|nestjs-cls|ClsModule", re.I),
    "log_enrichment": re.compile(
        r"Enrich\.FromLogContext|Enrich\.WithCorrelationId|%X\{|includeMdcKeyName|pino-http|pinoHttp|req\.log\.|\.child\(\s*\{\s*(?:reqId|requestId|correlationId|traceId)|"
        r"merge_contextvars|bind_contextvars|CorrelationIdFilter|RequestIDLogFilter|logging\.Filter|AsyncLocalStorage|mixin\s*\(|"
        r"LoggingInstrumentor|Enrich\.WithSpan|trace_id|traceId", re.I),
    "backend_outbound_markers": re.compile(
        r"AddHttpMessageHandler|DelegatingHandler|AddHttpClientInstrumentation|RestTemplateBuilder|WebClient\.Builder|"
        r"@opentelemetry/instrumentation-http|auto-instrumentations-node|RequestsInstrumentor|HTTPXClientInstrumentor|"
        r"propagation\.inject|propagate\.inject|headers\[['\"]x-(?:correlation|request)-id|['\"]x-(?:correlation|request)-id['\"]\s*:|"
        r"Headers\.Add\(\s*\"X-(?:Correlation|Request)-Id|traceparent", re.I),
    "backend_outbound_calls": re.compile(
        r"\bnew HttpClient\(|IHttpClientFactory|HttpClient\b.*(?:GetAsync|PostAsync|SendAsync)|\baxios(?:\.\w+)?\(|\baxios\.(?:get|post|put|delete|request)\(|"
        r"\bfetch\(|\bgot\(|\bundici\b|\brequests\.(?:get|post|put|delete|request)\(|\bhttpx\.|\bRestTemplate\b|\bWebClient\b|\bOkHttpClient\b|urllib\.request", re.I),
    "response_echo": re.compile(
        r"(?:setHeader|set|header)\(\s*['\"]x-(?:correlation|request)-id|Response\.Headers\[\s*\"X-(?:Correlation|Request)-Id|"
        r"res\.setHeader\(\s*['\"]x-|addHeader\(\s*\"X-(?:Correlation|Request)-Id|response\[['\"]X-(?:Correlation|Request)-Id|asgi_correlation_id", re.I),
}
FIX = {
    "frontend_outbound": "add an HTTP interceptor that generates a UUID per user action and sends X-Correlation-Id (or enable OTel web fetch/XHR instrumentation with propagateTraceHeaderCorsUrls)",
    "backend_inbound": "register correlation middleware first in the pipeline: read X-Correlation-Id / traceparent or create one",
    "log_enrichment": "push the id into the logging context (Serilog LogContext, SLF4J MDC, pino-http child logger, structlog contextvars) so every line carries it",
    "backend_outbound": "forward the id on outbound HTTP/queue calls (DelegatingHandler, RestTemplateBuilder bean, axios interceptor, OTel client instrumentation)",
    "response_echo": "return the id in the X-Correlation-Id response header and in error bodies so support can quote it",
}


COMMENT_LINE_RX = re.compile(r"^\s*(?://|#|\*|/\*|<!--)")


def read(path):
    """Read a file, blanking whole-line comments (keeps line numbers) so a comment that merely
    mentions a correlation header does not count as the middleware being present."""
    try:
        if os.path.getsize(path) > 1_500_000:
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return None
    if path.endswith(".json"):
        return text
    return "\n".join("" if COMMENT_LINE_RX.match(l) else l for l in text.split("\n"))


def first_hits(files, rx, limit=3):
    out = []
    for rel, text in files:
        m = rx.search(text)
        if m:
            out.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1} ({m.group(0).strip()[:40]})")
            if len(out) >= limit:
                break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    frontend_roots = []
    fe, be = [], []
    for pj_path in repo_walk.iter_files(root, exts=set(), names={"package.json"}, max_bytes=None):
        if FRONTEND_DEPS.search(read(pj_path) or ""):
            frontend_roots.append(os.path.dirname(os.path.abspath(pj_path)))
    for full in repo_walk.iter_files(root, exts=CODE_EXT, max_bytes=None):
        fn = os.path.basename(full)
        ext = os.path.splitext(fn)[1].lower()
        if fn.endswith((".min.js", ".d.ts")) or fn in ("package-lock.json", "tsconfig.json"):
            continue
        full = os.path.abspath(full)
        text = read(full)
        if text is None:
            continue
        rel = repo_walk.rel(root, full)
        is_fe = ext in (".tsx", ".jsx", ".vue") or any(full.startswith(r + os.sep) for r in frontend_roots)
        (fe if is_fe else be).append((rel, text))
    # a folder can be classified as frontend only after its package.json is seen; re-sort late arrivals
    moved = [(r, t) for r, t in be if any(os.path.join(root, r).replace("/", os.sep).startswith(fr + os.sep) for fr in frontend_roots)]
    be = [x for x in be if x not in moved]
    fe += moved
    fe_code = [(r, t) for r, t in fe if not r.endswith((".json", ".xml", ".yml", ".yaml"))] or fe

    hops = []

    def hop(name, applicable, hits, note=""):
        status = "n/a" if not applicable else ("present" if hits else "absent")
        hops.append({"hop": name, "status": status, "evidence": hits, "fix": "" if status != "absent" else FIX[name], "note": note})

    hop("frontend_outbound", bool(fe_code), first_hits(fe_code, HOPS["frontend_outbound"]),
        "" if fe_code else "no frontend code in this repo - audit the frontend repo or mark not checked")
    hop("backend_inbound", bool(be), first_hits(be, HOPS["backend_inbound"]))
    hop("log_enrichment", bool(be), first_hits(be, HOPS["log_enrichment"]))
    calls = first_hits([(r, t) for r, t in be if not r.endswith((".json", ".xml", ".yml", ".yaml"))], HOPS["backend_outbound_calls"])
    hop("backend_outbound", bool(calls), first_hits(be, HOPS["backend_outbound_markers"]),
        ("outbound calls at " + "; ".join(calls)) if calls else "no outbound HTTP calls found")
    hop("response_echo", bool(be), first_hits(be, HOPS["response_echo"]))
    broken = next((h["hop"] for h in hops if h["status"] == "absent"), None)
    res = {"root": root, "generated_at": datetime.now(timezone.utc).isoformat(), "frontend_roots": [os.path.relpath(r, root) for r in frontend_roots],
           "chain_intact": broken is None, "broken_at": broken, "hops": hops}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        o = ["### Correlation-id propagation (frontend -> backend -> downstream)", "",
             "| Hop | Status | Evidence | Fix / note |", "|---|---|---|---|"]
        for h in hops:
            ev = "; ".join(f"`{e}`" for e in h["evidence"]) or "-"
            o.append(f"| {h['hop']} | {h['status']} | {ev} | {(h['fix'] or h['note']).replace('|', '/')} |")
        o += ["", f"Chain: {'intact' if broken is None else 'broken at ' + broken}", ""]
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(o))
    print(json.dumps({"broken_at": broken, "hops": {h["hop"]: h["status"] for h in hops}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
