#!/usr/bin/env python3
"""Evaluate the production readiness checklist items that can be judged from
repository files, and emit pass / fail / unknown with evidence per item.

Usage:
    python readiness_probe.py <repo_root> [--out readiness.json] [--md readiness.md]

Items (ids used in the JSON):
  ENV_CONFIG_SEPARATED   per-environment config files / env-var injection / environment set in container
  NO_HARDCODED_PROD_SECRETS  literal passwords/keys or non-localhost connection strings with credentials in committed config
  DEBUG_OFF              developer/debug switches enabled unconditionally or in production profiles
  HEALTH_CHECKS          health endpoint exists; readiness verifies dependencies; probes configured
  GRACEFUL_SHUTDOWN      shutdown hooks / graceful settings present
  TIMEOUTS_RETRIES       outbound clients with timeouts and resilience libraries
  CACHING_STRATEGY       cache layer present (shared vs per-instance noted)
  LOAD_TEST_RESULTS      load-test scripts and results/reports present
  FEATURE_FLAGS          feature-flag system present
  RUNBOOK                runbook / operations docs present
  ALERTING               alert rule definitions present
  ROLLBACK_PROCEDURE     rollback documented in docs or deploy pipeline
  LAUNCH_CHECKLIST       launch checklist with owners present
  BACKUPS                backup/restore documented or configured
Everything is a candidate for the reviewer; "unknown" means the evidence is not in the repo.
Files are walked with audit-code-scan's repo_walk (shared skip list); secret and connection-string
values are recognised with audit-sensitive-data-catalog. "provisional_recommendation" previews the
rollup rule on the READY- findings the failed items would become; the verdict itself comes from
audit-findings-rollup (aggregate_findings.py).
Read-only against the audited repo.
"""
import argparse
import json
import os
import re
import importlib.util
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
_SDC_PATH = os.path.join(_SKILLS, "audit-sensitive-data-catalog", "scripts", "catalog.py")
if not os.path.exists(_SDC_PATH):
    sys.exit("audit-sensitive-data-catalog must be reachable from this skill (audit-core plugin or sibling layout; expected " + _SDC_PATH + ")")
_spec = importlib.util.spec_from_file_location("sensitive_data_catalog", _SDC_PATH)
sdc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sdc)

SECRETISH = ("credential", "secret")
CODE_EXT = {".cs", ".java", ".kt", ".ts", ".js", ".mjs", ".py", ".json", ".yml", ".yaml", ".properties", ".toml", ".env", ".md", ".txt", ".sh", ".ps1", ".tf", ".bicep", ".xml", ".config", ".jmx", ".scala"}
PROD_CONFIG = re.compile(r"(appsettings\.(production|prod|staging|release)\.json|application-(prod|production|staging)\.(ya?ml|properties)|\.env\.(production|prod|staging)$|settings/(prod|production|staging)\.py|config/(production|staging)\.(json|ya?ml|js|ts)|web\.release\.config)$", re.I)
DEV_CONFIG = re.compile(r"(appsettings\.development\.json|application-(dev|local|test)\.(ya?ml|properties)|\.env\.(development|local|test|example|sample)$|settings/(dev|local|test)\.py|launchsettings\.json|\.env\.example|\.env\.sample)$", re.I)
CONN_HOST = re.compile(r"(?i)\b(?:server|data source|host|hostname)\s*=\s*([^;\"',\s]+)")
LOCALHOSTS = re.compile(r"(?i)^(localhost|127\.0\.0\.1|\(localdb\)|\.|::1|host\.docker\.internal|db|database|postgres|mysql|redis|rabbitmq|mssql|sqlserver|mongo)$")


def _read(p):
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def rel(root, p):
    return os.path.relpath(p, root).replace(os.sep, "/")


class Probe:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.files = []
        for p in repo_walk.iter_files(self.root, globs=["*"]):
            fn = os.path.basename(p)
            ext = os.path.splitext(fn)[1].lower()
            if ext in CODE_EXT or fn.lower() in ("dockerfile", "makefile", "procfile") or fn.lower().startswith(".env") or fn.lower().startswith("dockerfile"):
                self.files.append(p)
        self.texts = {}
        self.items = []

    def text(self, p):
        if p not in self.texts:
            self.texts[p] = _read(p)
        return self.texts[p]

    def grep(self, rx, exts=None, names_rx=None, limit=20):
        out = []
        crx = re.compile(rx, re.I | re.M)
        for p in self.files:
            fn = os.path.basename(p)
            if exts and os.path.splitext(fn)[1].lower() not in exts and fn.lower() not in exts:
                continue
            if names_rx and not re.search(names_rx, rel(self.root, p), re.I):
                continue
            t = self.text(p)
            for m in crx.finditer(t):
                line = t.count("\n", 0, m.start()) + 1
                snippet = t.splitlines()[line - 1].strip()[:160] if t else ""
                out.append(f"{rel(self.root, p)}:{line}: {snippet}")
                if len(out) >= limit:
                    return out
        return out

    def names(self, rx):
        return [rel(self.root, p) for p in self.files if re.search(rx, rel(self.root, p), re.I)]

    def add(self, iid, item, status, evidence, needed="", severity_if_fail="High"):
        self.items.append({"id": iid, "item": item, "status": status, "evidence": evidence[:12], "what_would_make_it_pass": needed, "severity_if_fail": severity_if_fail})

    # ------------------------------------------------------------------ items
    def env_config(self):
        prod = [f for f in self.names(PROD_CONFIG.pattern)]
        dev = [f for f in self.names(DEV_CONFIG.pattern)]
        env_inject = self.grep(r"(ASPNETCORE_ENVIRONMENT|DOTNET_ENVIRONMENT|SPRING_PROFILES_ACTIVE|NODE_ENV|DJANGO_SETTINGS_MODULE|FLASK_ENV|APP_ENV)\s*[:=]", exts={".yml", ".yaml", "dockerfile", ".json", ".sh", ".ps1", ".tf", ".bicep"}, limit=10)
        env_inject += self.grep(r"^(ENV|ARG)\s+(ASPNETCORE_ENVIRONMENT|SPRING_PROFILES_ACTIVE|NODE_ENV|DJANGO_SETTINGS_MODULE)", names_rx=r"dockerfile", limit=5)
        env_api = self.grep(r"(AddEnvironmentVariables\(|os\.environ|process\.env|environ\.get|env\.str\(|env\.db\(|\$\{[A-Z_]+\}|runtimeConfig)", limit=5)
        gitignore = [p for p in self.files if os.path.basename(p) == ".gitignore"]
        env_ignored = any(re.search(r"^\s*\.env", self.text(p), re.M) for p in gitignore)
        ev = [f"production config: {', '.join(prod) or 'none'}", f"dev/example config: {', '.join(dev) or 'none'}"] + env_inject[:4] + env_api[:3]
        if env_ignored:
            ev.append(".gitignore ignores .env files")
        if (prod or env_api) and env_inject:
            self.add("ENV_CONFIG_SEPARATED", "Environment-specific configuration separated", "pass", ev)
        elif prod or env_api:
            self.add("ENV_CONFIG_SEPARATED", "Environment-specific configuration separated", "unknown", ev, "show where the production environment name/profile is set (Dockerfile, compose, CI, k8s)", "Medium")
        else:
            self.add("ENV_CONFIG_SEPARATED", "Environment-specific configuration separated", "fail", ev or ["no per-environment config files and no environment-variable configuration found"], "add appsettings.{Env}.json / application-{profile}.yml / settings per env and inject production values from the host", "High")

    def secrets(self):
        hits = []
        for p in self.files:
            rp = rel(self.root, p)
            fn = os.path.basename(p).lower()
            is_prod = bool(PROD_CONFIG.search(rp))
            is_dev = bool(DEV_CONFIG.search(rp)) or "test" in rp.lower().split("/") or fn.endswith((".md", ".txt"))
            if is_dev and not is_prod:
                continue
            if os.path.splitext(fn)[1] not in (".json", ".yml", ".yaml", ".properties", ".env", ".py", ".ts", ".js", ".cs", ".java", ".xml", ".config", ".toml", ".tf", ".bicep") and not fn.startswith(".env"):
                continue
            t = self.text(p)
            for i, line in enumerate(t.splitlines(), 1):
                ms = sdc.find_values(line, dedupe=False)
                conn = [m for m in ms if m["rule_id"] in ("V-URL-CREDENTIALS", "V-CONN-STRING-PASSWORD")]
                if conn:
                    hm = CONN_HOST.search(line)
                    host = conn[0]["attributes"].get("host") or (hm.group(1) if hm else "")
                    if host and not LOCALHOSTS.match(host) and all(m["placeholder"] is None for m in conn):
                        hits.append(f"{rp}:{i}: {line.strip()[:160]}" + ("  [PRODUCTION CONFIG]" if is_prod else ""))
                        continue
                if is_prod and any(m["sensitive"] and m["category"] in SECRETISH and len(m["value"]) >= 6 for m in ms) \
                        and not re.search(r"(?i)(localhost|127\.0\.0\.1|example|sample|changeme|placeholder)", line):
                    hits.append(f"{rp}:{i}: {line.strip()[:160]}  [PRODUCTION CONFIG]")
        if hits:
            self.add("NO_HARDCODED_PROD_SECRETS", "No hard-coded production secrets or connection strings", "fail", hits, "replace literals with environment variables / secret store references, rotate the exposed values, purge git history", "Critical")
        else:
            self.add("NO_HARDCODED_PROD_SECRETS", "No hard-coded production secrets or connection strings", "pass", ["no credential-bearing connection strings to non-local hosts and no literal secrets in production config files (heuristic; audit-secrets-and-config is authoritative)"])

    def debug(self):
        hits = []
        for line in self.grep(r"UseDeveloperExceptionPage\(\)|UseSwaggerUI\(|EnableSensitiveDataLogging\(|EnableDetailedErrors\(", exts={".cs"}):
            f, ln, _ = line.split(":", 2)
            t = self.text(os.path.join(self.root, f))
            idx = int(ln)
            ctx = "\n".join(t.splitlines()[max(0, idx - 6): idx])
            if not re.search(r"IsDevelopment\(\)|IsEnvironment\(|IsStaging\(\)|#if\s+DEBUG", ctx):
                hits.append(line + "  [not guarded by IsDevelopment()]")
        hits += self.grep(r"\"DetailedErrors\"\s*:\s*true|\"MinimumLevel\"\s*:\s*\"(Debug|Verbose)\"|\"Default\"\s*:\s*\"(Debug|Verbose|Trace)\"", names_rx=PROD_CONFIG.pattern)
        hits += self.grep(r"^\s*DEBUG\s*=\s*True", exts={".py"}, names_rx=r"(prod|production|settings\.py$|base\.py$)")
        hits += self.grep(r"(debug|show-sql|include-stacktrace)\s*[:=]\s*(true|always)|logging\.level\.root\s*[:=]\s*(DEBUG|TRACE)|h2\.console\.enabled\s*[:=]\s*true", names_rx=r"application-(prod|production|staging)|application\.(ya?ml|properties)$")
        hits += self.grep(r"synchronize\s*:\s*true|sync\(\s*\{\s*(force|alter)\s*:\s*true|errorhandler\(\)|morgan\(\s*['\"]dev['\"]\s*\)", exts={".ts", ".js"})
        hits += self.grep(r"(ENV|ARG)\s+NODE_ENV\s*=?\s*development|ASPNETCORE_ENVIRONMENT\s*[=:]\s*Development|SPRING_PROFILES_ACTIVE\s*[=:]\s*(dev|local)", exts={"dockerfile", ".yml", ".yaml"})
        hits += self.grep(r"\"sourceMap\"\s*:\s*true|productionBrowserSourceMaps\s*:\s*true|GENERATE_SOURCEMAP\s*=\s*true", exts={".json", ".js", ".ts", ".env"}, names_rx=r"(angular\.json|next\.config|\.env\.production)")
        hits += self.grep(r"app\.run\([^)]*debug\s*=\s*True|FastAPI\([^)]*debug\s*=\s*True", exts={".py"})
        if hits:
            self.add("DEBUG_OFF", "Debug / developer features off in production", "fail", hits, "gate developer pages, sensitive logging, swagger, source maps and ORM sync on the development environment", "High")
        else:
            self.add("DEBUG_OFF", "Debug / developer features off in production", "pass", ["no unguarded developer exception pages, DEBUG=True, show-sql, synchronize:true, dev NODE_ENV or production source maps found"])

    def health(self):
        endpoint = self.grep(r"AddHealthChecks\(|MapHealthChecks\(|spring-boot-starter-actuator|management\.endpoint\.health|@nestjs/terminus|HealthCheckService|@godaddy/terminus|lightship|health_check\b|['\"]/health(z|/live|/ready|check)?['\"]|/actuator/health|def health|healthz|HealthController|HealthCheck", limit=15)
        deps = self.grep(r"\.Add(SqlServer|NpgSql|MySql|Redis|RabbitMQ|MongoDb|Kafka|AzureServiceBus|UrlGroup|Elasticsearch)\(|HealthIndicator|health_check\.(db|cache|contrib)|pingCheck\(|TypeOrmHealthIndicator|MongooseHealthIndicator|PrismaHealthIndicator|MicroserviceHealthIndicator|HttpHealthIndicator|\$queryRaw`SELECT 1|SELECT 1['\"]|cursor\(\)\.execute\(['\"]SELECT 1|readiness\.include|\.ping\(\)", limit=15)
        probes = self.grep(r"^\s*healthcheck:|HEALTHCHECK\s|readinessProbe:|livenessProbe:", exts={".yml", ".yaml", "dockerfile"}, limit=10)
        ev = ["endpoint: " + (endpoint[0] if endpoint else "none found")] + endpoint[1:4] + ["dependency checks: " + (deps[0] if deps else "none found")] + deps[1:4] + ["probes: " + (probes[0] if probes else "none found")] + probes[1:3]
        if not endpoint:
            self.add("HEALTH_CHECKS", "Health checks that verify dependencies", "fail", ev, "add a liveness endpoint and a readiness endpoint that checks DB/broker/cache; point container/orchestrator probes at them; keep them unauthenticated", "High")
        elif not deps:
            self.add("HEALTH_CHECKS", "Health checks that verify dependencies", "fail", ev, "extend the readiness endpoint with database/broker/cache checks (AspNetCore.HealthChecks.*, actuator indicators, terminus indicators, django-health-check contrib)", "High")
        elif not probes:
            self.add("HEALTH_CHECKS", "Health checks that verify dependencies", "unknown", ev, "show the orchestrator/container probe configuration targeting the endpoint (may live in infra outside the repo)", "Medium")
        else:
            self.add("HEALTH_CHECKS", "Health checks that verify dependencies", "pass", ev)

    def shutdown(self):
        hits = self.grep(r"ShutdownTimeout|IHostApplicationLifetime|ApplicationStopping|server\.shutdown\s*[:=]\s*graceful|timeout-per-shutdown-phase|enableShutdownHooks\(|process\.on\(\s*['\"]SIGTERM['\"]|SIGTERM|graceful[_-]?timeout|--graceful-timeout|timeout-graceful-shutdown|terminationGracePeriodSeconds|http-terminator|stoppable\(|kill_timeout|task_reject_on_worker_lost|acks_late", limit=10)
        dotnet = any(p.endswith(".csproj") for p in self.files) or bool(self.names(r"\.csproj$"))
        if hits:
            self.add("GRACEFUL_SHUTDOWN", "Graceful shutdown", "pass", hits)
        elif self.names(r"Program\.cs$") or self.names(r"\.csproj$"):
            self.add("GRACEFUL_SHUTDOWN", "Graceful shutdown", "unknown", ["no explicit shutdown configuration; .NET host drains on SIGTERM with a 5 s default ShutdownTimeout"], "confirm HostOptions.ShutdownTimeout and background services honour cancellation; compare with the orchestrator grace period", "Medium")
        else:
            self.add("GRACEFUL_SHUTDOWN", "Graceful shutdown", "fail", ["no SIGTERM handler, graceful shutdown setting or termination grace period found"], "add a shutdown hook that stops accepting requests, drains in-flight work and closes pools/queues", "Medium")

    def timeouts(self):
        clients = self.grep(r"AddHttpClient|new\s+HttpClient\(|RestTemplate|WebClient\.|@FeignClient|axios\.create|axios\.(get|post)|\bfetch\(|requests\.(get|post|put|delete|request)|httpx\.(Client|AsyncClient|get|post)", limit=40)
        with_timeout = self.grep(r"\.Timeout\s*=|AddStandardResilienceHandler|AddTransientHttpErrorPolicy|AddPolicyHandler|connectTimeout|readTimeout|responseTimeout|timeout\s*[:=]\s*\d|AbortSignal\.timeout|timeout=\(?\d|httpx\.Timeout|@TimeLimiter|@Retry|@CircuitBreaker|tenacity|pybreaker|opossum|cockatiel|p-retry|axios-retry|EnableRetryOnFailure|CommandTimeout|connect_timeout|statement_timeout|hikari\.connection-timeout", limit=40)
        bare = self.grep(r"new\s+HttpClient\(\)|requests\.(get|post|put|delete)\((?![^)]*timeout)|new\s+RestTemplate\(\)", limit=15)
        ev = [f"outbound client sites: {len(clients)}", f"timeout/resilience markers: {len(with_timeout)}"] + with_timeout[:4] + [b + "  [no timeout]" for b in bare[:6]]
        if not clients:
            self.add("TIMEOUTS_RETRIES", "Timeouts and retries on all external calls", "unknown", ["no outbound HTTP client code found; DB/broker timeouts not assessed"], "list every external dependency and its timeout/retry configuration", "Medium")
        elif bare:
            self.add("TIMEOUTS_RETRIES", "Timeouts and retries on all external calls", "fail", ev, "set a timeout on every client and a retry-with-backoff/circuit-breaker policy on external calls", "High")
        elif with_timeout:
            self.add("TIMEOUTS_RETRIES", "Timeouts and retries on all external calls", "unknown", ev, "confirm every client site listed carries a timeout and a retry policy (script matched markers, not per-client coverage)", "Medium")
        else:
            self.add("TIMEOUTS_RETRIES", "Timeouts and retries on all external calls", "fail", ev, "add timeouts and resilience policies to the outbound clients", "High")

    def caching(self):
        shared = self.grep(r"AddStackExchangeRedisCache|AddOutputCache|AddResponseCaching|spring\.cache\.type\s*[:=]\s*(redis|hazelcast)|cache-manager-redis|ioredis|RedisCache|django_redis|CACHES\s*=|@Cacheable|routeRules|staleTime", limit=8)
        local = self.grep(r"AddMemoryCache\(|IMemoryCache|spring\.cache\.type\s*[:=]\s*(simple|caffeine)|node-cache|lru-cache|LocMemCache", limit=8)
        if shared:
            self.add("CACHING_STRATEGY", "Caching strategy defined", "unknown", shared + local, "document what is cached, TTL and invalidation; confirm shared cache for authoritative data", "Low")
        elif local:
            self.add("CACHING_STRATEGY", "Caching strategy defined", "unknown", local, "per-instance cache found; confirm it holds only tolerant reference data or move to a shared cache; document the strategy", "Medium")
        else:
            self.add("CACHING_STRATEGY", "Caching strategy defined", "unknown", ["no cache layer found"], "state whether caching is needed at expected load (audit-performance-and-scalability) and document the decision", "Low")

    def load_tests(self):
        scripts = self.names(r"(k6|loadtest|load-test|load_test|perf|performance|gatling|locustfile|artillery|\.jmx$|nbomber|autocannon)")
        results = [f for f in scripts if re.search(r"(result|report|summary)", f, re.I)] + self.names(r"(load|perf)[\w-]*(result|report)")
        if results:
            self.add("LOAD_TEST_RESULTS", "Load test results available", "pass", results[:8])
        elif scripts:
            self.add("LOAD_TEST_RESULTS", "Load test results available", "unknown", scripts[:8], "attach the latest run's report (RPS, p95, error rate, environment, date)", "Medium")
        else:
            self.add("LOAD_TEST_RESULTS", "Load test results available", "fail", ["no load-test scripts or reports found (k6, JMeter, Gatling, Locust, Artillery, NBomber)"], "run a load test at expected peak on a production-like environment and store the report", "High")

    def flags(self):
        hits = self.grep(r"FeatureManagement|IFeatureManager|\[FeatureGate|LaunchDarkly|launchdarkly|Unleash|unleash-client|Flagsmith|flagsmith|GrowthBook|openfeature|Togglz|togglz|ff4j|django-waffle|waffle\.|django_flags|\"FeatureFlags\"|\"Features\"\s*:\s*\{|FEATURES\s*=\s*\{|featureFlags|@vercel/flags", limit=8)
        if hits:
            self.add("FEATURE_FLAGS", "Feature flags for risky changes", "pass", hits)
        else:
            self.add("FEATURE_FLAGS", "Feature flags for risky changes", "unknown", ["no feature-flag system found"], "identify the risky changes in this release; if any, put them behind a flag with a documented kill switch", "Medium")

    def docs(self):
        runbook = self.names(r"(runbook|run-book|playbook|operations?[/_-]|on-?call|incident|ops-guide|SRE)")
        runbook_words = self.grep(r"(?i)^#+\s*.*(runbook|on-?call|incident response|operations guide)", exts={".md"}, limit=5)
        if runbook or runbook_words:
            self.add("RUNBOOK", "Runbook documented", "pass", runbook[:6] + runbook_words[:3])
        else:
            self.add("RUNBOOK", "Runbook documented", "fail", ["no runbook/operations/on-call document found"], "write a runbook: services, dependencies, SPOFs, restart/scale/rollback steps, log and dashboard locations, escalation", "High")
        alerts = self.names(r"(alert|alerts|alerting|alertmanager|monitors?/|prometheus.*rules|grafana/provisioning|pagerduty|opsgenie)") + self.grep(r"azurerm_monitor_(metric|scheduled_query_rules)_alert|aws_cloudwatch_metric_alarm|datadog_monitor|groups:\s*$\s*-\s*name:.*\n(\s*rules:)", exts={".tf", ".yml", ".yaml", ".bicep", ".json"}, limit=5)
        if alerts:
            self.add("ALERTING", "On-call and alerting in place", "unknown", alerts[:8], "confirm alerts cover error rate, latency, saturation and dependency health, and route to an on-call rota (audit-logging-and-observability alert matrix)", "Medium")
        else:
            self.add("ALERTING", "On-call and alerting in place", "fail", ["no alert rule definitions found in the repo"], "define alerts for error rate, latency, saturation and dependency health; route them to an on-call rota; if configured in a SaaS console, export or screenshot the rules", "High")
        rollback = self.grep(r"(?i)rollback|rollout undo|roll back|slot swap|releases:rollback|previous (build|release|version)", exts={".md", ".yml", ".yaml", ".sh", ".ps1", ".txt"}, limit=8)
        if rollback:
            self.add("ROLLBACK_PROCEDURE", "Rollback procedure tested", "unknown", rollback, "show that the documented rollback was exercised this release cycle (staging run, ticket, date) and that the last migration is reversible", "Medium")
        else:
            self.add("ROLLBACK_PROCEDURE", "Rollback procedure tested", "fail", ["no rollback step in docs or deploy pipeline"], "write and rehearse an app + database rollback; add a rollback job to the pipeline", "High")
        launch = self.names(r"(launch|go-?live|release-?checklist|readiness|checklist)")
        owners = [f for f in launch if re.search(r"(?i)owner", self.text(os.path.join(self.root, f)))]
        if owners:
            self.add("LAUNCH_CHECKLIST", "Launch checklist with owners", "pass", owners[:5])
        elif launch:
            self.add("LAUNCH_CHECKLIST", "Launch checklist with owners", "unknown", launch[:5], "add an owner and status per item", "Low")
        else:
            self.add("LAUNCH_CHECKLIST", "Launch checklist with owners", "fail", ["no launch/go-live checklist found"], "create a launch checklist with an owner and status per item (template in references/readiness-checklist.md)", "Medium")
        backups = self.grep(r"(?i)backup|restore|point-in-time|pitr|snapshot", exts={".md", ".tf", ".bicep", ".yml", ".yaml", ".sh", ".ps1"}, limit=6)
        if backups:
            self.add("BACKUPS", "Backups and restore", "unknown", backups, "show the backup schedule, retention and the last restore test", "Medium")
        else:
            self.add("BACKUPS", "Backups and restore", "unknown", ["no backup/restore configuration or documentation in the repo"], "confirm platform-managed backups and a tested restore (audit-infra-and-deployment)", "High")

    def run(self):
        for fn in (self.env_config, self.secrets, self.debug, self.health, self.shutdown, self.timeouts, self.caching, self.load_tests, self.flags, self.docs):
            try:
                fn()
            except Exception as exc:  # keep going; report the probe failure as unknown
                self.add(fn.__name__.upper(), fn.__name__, "unknown", [f"probe error: {exc}"], "re-run after fixing the probe", "Low")
        summary = {s: sum(1 for i in self.items if i["status"] == s) for s in ("pass", "fail", "unknown")}
        blockers = [i for i in self.items if i["status"] == "fail" and i["id"] in ("NO_HARDCODED_PROD_SECRETS", "HEALTH_CHECKS", "ROLLBACK_PROCEDURE", "DEBUG_OFF")]
        failed = [i for i in self.items if i["status"] == "fail"]
        # Preview of the audit-findings-rollup rule on the READY- findings these failed items become;
        # unknown items create no finding and do not change it.
        if any(i["severity_if_fail"] in ("Critical", "High") for i in failed):
            preview = "NO-GO"
        elif failed:
            preview = "CONDITIONAL GO"
        else:
            preview = "GO"
        return {"root": self.root, "items": self.items, "summary": summary,
                "blocking_item_ids": [b["id"] for b in blockers],
                "provisional_recommendation": preview}


def to_md(doc):
    out = ["# Readiness probe", "", f"pass {doc['summary']['pass']}  fail {doc['summary']['fail']}  unknown {doc['summary']['unknown']}  provisional: {doc['provisional_recommendation']}", "",
           "| Item | Status | Evidence | What would make it pass |", "|---|---|---|---|"]
    for i in doc["items"]:
        ev = "<br>".join(e.replace("|", "\\|") for e in i["evidence"][:5])
        out.append(f"| {i['item']} | **{i['status']}** | {ev} | {i['what_would_make_it_pass']} |")
    out += ["", "File-based heuristics only; evidence outside the repo (dashboards, rotas, DR drills) must be supplied by the team."]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root"); ap.add_argument("--out"); ap.add_argument("--md")
    a = ap.parse_args()
    doc = Probe(a.root).run()
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(to_md(doc))
    print(to_md(doc) if not (a.out or a.md) else json.dumps({"summary": doc["summary"], "blocking_item_ids": doc["blocking_item_ids"], "provisional_recommendation": doc["provisional_recommendation"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
