#!/usr/bin/env python3
"""Evaluate the technical GDPR checks for a repository and write the
rights-fulfilment matrix.

Usage:
    python gdpr_check.py <repo_root> [--inventory PATH] [--out gdpr-checks.json]
                         [--md rights-matrix.md] [--no-run-mapper] [--mapper PATH]

Inputs:
  * The personal-data inventory written by audit-privacy-data-flow-mapper
    (default: <repo>/audit/evidence/audit-privacy-data-flow-mapper/data-inventory.json).
    If it does not exist, the sibling scanner (../../audit-privacy-data-flow-mapper/
    scripts/pii_scan.py, or --mapper) is run to create it under audit/evidence/.
    --no-run-mapper skips that and records the gap as not-checked.
  * The repository source (read-only).

Checks (ids match references/gdpr-article-map.md):
  right-access, right-portability, right-erasure, right-rectification,
  right-restriction-objection, consent-capture, consent-withdrawal,
  retention-enforcement, minimisation-logs-urls-analytics, encryption-transit,
  encryption-at-rest-pseudonymisation, access-logging-pii, processors-transfers,
  breach-detection, privacy-by-design.

Each check gets status implemented | partial | missing | not-checked, a list of
evidence lines {file, line, snippet, note}, and a note explaining the status.
"missing" means "no code matched the patterns"; confirm by hand before it becomes
a finding. Output: JSON (--out) and a Markdown matrix (--md). Writes nothing else.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
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

PERSONAL = ("identifier", "contact", "financial", "health", "special-category")
CODE_EXT = {".cs", ".java", ".kt", ".ts", ".tsx", ".js", ".jsx", ".vue", ".py", ".rb", ".go", ".php",
            ".sql", ".prisma", ".json", ".yml", ".yaml", ".xml", ".properties", ".toml", ".env", ".md", ".txt", ".cshtml", ".html"}
MAX_BYTES = 1_500_000

SUBJECT = r"(?:users?|customers?|accounts?|profiles?|members?|persons?|people|contacts?|patients?|employees?|clients?|subscribers?|me|self)"
NON_SUBJECT = r"(?:sessions?|tokens?|logins?|logout|carts?|baskets?|orders?|items?|products?|files?|uploads?|images?|notifications?|jobs?|cache|keys?|devices?|posts?|comments?|likes?|favou?rites?|roles?|permissions?)"

# route declarations by verb, framework-agnostic
ROUTE = {
    "delete": re.compile(r"\[HttpDelete(?:\s*\(\s*\"([^\"]*)\")?|@DeleteMapping(?:\s*\(\s*(?:value\s*=\s*)?\"([^\"]*)\")?|(?:router|app|route|r)\.delete\s*\(\s*['\"`]([^'\"`]*)|@Delete\s*\(\s*['\"]?([^'\")]*)|methods\s*=\s*\[?['\"]DELETE|def\s+(?:destroy|delete|perform_destroy)\s*\(|Map(?:Delete)\s*\(\s*\"([^\"]*)\"|\.delete\s*\(\s*['\"]([^'\"]*)['\"]\s*,", re.I),
    "put": re.compile(r"\[Http(?:Put|Patch)(?:\s*\(\s*\"([^\"]*)\")?|@(?:PutMapping|PatchMapping)(?:\s*\(\s*(?:value\s*=\s*)?\"([^\"]*)\")?|(?:router|app|route|r)\.(?:put|patch)\s*\(\s*['\"`]([^'\"`]*)|@(?:Put|Patch)\s*\(\s*['\"]?([^'\")]*)|methods\s*=\s*\[?['\"](?:PUT|PATCH)|def\s+(?:update|partial_update|perform_update)\s*\(|Map(?:Put|Patch)\s*\(\s*\"([^\"]*)\"", re.I),
    "get": re.compile(r"\[HttpGet(?:\s*\(\s*\"([^\"]*)\")?|@GetMapping(?:\s*\(\s*(?:value\s*=\s*)?\"([^\"]*)\")?|(?:router|app|route|r)\.get\s*\(\s*['\"`]([^'\"`]*)|@Get\s*\(\s*['\"]?([^'\")]*)|def\s+(?:retrieve|get|show)\s*\(|MapGet\s*\(\s*\"([^\"]*)\"", re.I),
}
SELF_ROUTE = re.compile(r"/(?:me|self|profile|account|my-?data|personal-?data|gdpr|privacy)\b", re.I)
EXPORT = re.compile(r"\b(?:export|download|portab\w*|takeout|data[_\-]?dump|my[_\-]?data|personal[_\-]?data|gdpr[_\-]?(?:export|request)|subject[_\-]?access|dsar|sar)\b", re.I)
ERASE_SYMBOL = re.compile(r"\b(?:anonymi[sz]e\w*|pseudonymi[sz]e\w*|erase\w*|forget\w*|scrub\w*|gdpr[_\-]?delete\w*|delete[_\-]?(?:account|user|customer|profile|personal[_\-]?data|me)\w*|right[_\-]?to[_\-]?be[_\-]?forgotten|purge[_\-]?(?:user|customer|account)\w*|hard[_\-]?delete|softdelete|IsDeleted\s*=\s*true)\b", re.I)
RESTRICT = re.compile(r"\b(?:restrict(?:ed|ion)?[_\-]?processing|do[_\-]?not[_\-]?(?:contact|process|sell)|opt[_\-]?out|unsubscribe\w*|objection|object[_\-]?to[_\-]?processing|marketing[_\-]?(?:opt|preferences|suppress)|suppression[_\-]?list|DoNotContact|OptOut)\b", re.I)
CONSENT_FIELD = re.compile(r"\b(\w*(?:consent|opt[_\-]?in|agree(?:d|ment)?[_\-]?(?:to|terms|privacy)?|accept(?:ed)?[_\-]?(?:terms|privacy|policy|tos)|terms[_\-]?accepted|privacy[_\-]?accepted|marketing[_\-]?(?:allowed|permission|preference)|newsletter[_\-]?subscri\w*|gdpr[_\-]?consent)\w*)\b", re.I)
BOOL_TYPE = re.compile(r"\b(?:bool|Boolean|boolean|BooleanField|bit\b|tinyint\(1\)|Bool)\b|default\s*[:=]\s*(?:false|true|False|True)|@Column\s*\(\s*\{\s*default\s*:\s*(?:false|true)", re.I)
CONSENT_TS = re.compile(r"\b\w*(?:consent|opt[_\-]?in|agree|accept|terms|privacy)\w*(?:At|_at|Date|_date|On|_on|Time|_time|Timestamp|_timestamp|When|Given)\b|\b(?:consented|agreed|accepted|opted)[_\-]?(?:at|on|date|time)\b", re.I)
CONSENT_VER = re.compile(r"\b\w*(?:consent|policy|terms|privacy|tos)\w*(?:Version|_version|Ver|_ver|Text|_text|Hash|_hash|Id)\b", re.I)
CONSENT_SRC = re.compile(r"\b\w*(?:consent|optin)\w*(?:Source|_source|Ip|_ip|Channel|_channel|Method|_method|Evidence|_evidence)\b", re.I)
WITHDRAW = re.compile(r"\b(?:withdraw\w*|revoke[_\-]?consent|consent[_\-]?revok\w*|opt[_\-]?out|unsubscribe\w*|remove[_\-]?consent|update[_\-]?consent|consent[_\-]?withdraw\w*|setConsent|UpdateConsent|ConsentController)\b", re.I)
SCHEDULER = re.compile(r"\b(?:RecurringJob|BackgroundJob\.Schedule|BackgroundService|IHostedService|PeriodicTimer|Quartz|IJob\b|@Scheduled|@EnableScheduling|cron\s*[:=(]|node-cron|cron\.schedule|schedule\.scheduleJob|agenda|bull|BullMQ|@Cron|CronJob|celery|@periodic_task|beat_schedule|crontab|apscheduler|django[_\-]?cron|management/commands|Hangfire|TimerTrigger|schedule\.every)\b", re.I)
RETAIN = re.compile(r"\b(?:retention|purge\w*|prune\w*|cleanup|clean_up|cleanUp|expire[sd]?\w*|older[_ ]?than|delete\w*old|anonymi[sz]e\w*|ttl|time[_\-]?to[_\-]?live|max[_\-]?age|archive\w*|AddDays\(\s*-|AddMonths\(\s*-|timedelta\(\s*days|DATEADD\(\s*(?:day|month|year)\s*,\s*-|interval\s*'-?\d+)\b", re.I)
HTTPS = re.compile(r"\b(?:UseHttpsRedirection|UseHsts|RequireHttpsAttribute|RequireHttps|SECURE_SSL_REDIRECT|SECURE_HSTS_SECONDS|SESSION_COOKIE_SECURE|helmet\s*\(|hsts|strict-transport-security|server\.ssl\.enabled\s*=\s*true|requires-channel\s*=\s*\"https|forceSSL|force_ssl|https:\s*true|ssl:\s*\{|sslmode=require|Encrypt=True|TrustServerCertificate=False|redirectHttpToHttps|ssl_redirect)\b", re.I)
HTTP_WEAK = re.compile(r"\bssl\s*:\s*false|sslmode=disable|Encrypt=False|TrustServerCertificate=True|SECURE_SSL_REDIRECT\s*=\s*False|verify\s*=\s*False|rejectUnauthorized\s*:\s*false|http://(?!localhost|127\.0\.0\.1|schemas\.|www\.w3\.org)[a-z0-9.-]+\.[a-z]{2,}", re.I)
AT_REST = re.compile(r"\b(?:IsEncrypted|EncryptedColumn|ValueConverter<string,\s*string>|Encrypt(?:ion)?Converter|AttributeEncryptor|@Convert\s*\(\s*converter|ColumnTransformer|pgcrypto|pgp_sym_encrypt|AES_ENCRYPT|EncryptedField|django[_\-]?fernet|django[_\-]?encrypted|fernet|EncryptedType|AlwaysEncrypted|Always Encrypted|ColumnEncryptionSetting|DataProtection|IDataProtector|KMS|KeyVault|Key Vault|aws:kms|sse-kms|SSE-S3|ServerSideEncryption|Transparent Data Encryption|TDE\b|storage_encrypted\s*=\s*true|encrypted\s*=\s*true)\b", re.I)
PSEUDO = re.compile(r"\b(?:bcrypt|argon2|scrypt|PBKDF2|Rfc2898DeriveBytes|PasswordHasher|make_password|BCryptPasswordEncoder|hashlib\.sha256|sha256Hex|HMAC|pseudonymi[sz]e\w*|tokeni[sz]e\w*|mask\w*Email|MaskEmail|redact\w*)\b", re.I)
AUDIT = re.compile(r"\b(?:AuditLog\w*|audit_log\w*|AuditTrail|Audit(?:able|ed|Entry|Record)\b|@Audited|Envers|django[_\-]?auditlog|auditlog|simple_history|HistoricalRecords|pghistory|ChangeTracker\.Entries|EntityAudit|TemporalTable|IsTemporal|SYSTEM_VERSIONING|history_table|access[_\-]?log\w*|AccessLog|DataAccessLog|LogAccess|RecordAccess|who[_\-]?accessed|viewed[_\-]?by|paper_trail|audited\b)\b", re.I)
SECURITY_EVENT = re.compile(r"\b(?:failed[_\-]?login\w*|login[_\-]?fail\w*|LoginFailed|InvalidCredentials|invalid[_\-]?password|lockout|Lockout|axes|too[_\-]?many[_\-]?attempts|brute[_\-]?force|SecurityEvent\w*|security[_\-]?event\w*|AuthenticationFailure|AbstractAuthenticationFailureEvent|AuthenticationFailureBadCredentialsEvent|user_login_failed|privilege[_\-]?(?:change|escalat)\w*|role[_\-]?changed|RoleChanged|password[_\-]?(?:changed|reset)\w*|PasswordChanged|mfa[_\-]?fail\w*|suspicious\w*|anomal\w*|impossible[_\-]?travel)\b", re.I)
ALERTING = re.compile(r"\b(?:PagerDuty|pagerduty|OpsGenie|opsgenie|VictorOps|AlertRule|alertmanager|Alertmanager|SIEM|siem|Splunk|splunk|Sentinel|Wazuh|Elastic\s*Security|CloudWatch\s*Alarm|aws_cloudwatch_metric_alarm|azurerm_monitor_metric_alert|google_monitoring_alert_policy|Datadog\s*Monitor|datadog_monitor|Grafana\s*alert|slack[_\-]?(?:alert|webhook|notify)|hooks\.slack\.com|SendAlert|raise[_\-]?alert|alert\s*\(|notifySecurity|security@)\b", re.I)
LOG_SHIP = re.compile(r"\b(?:Serilog|WriteTo|Seq\b|Elasticsearch|Loki|Logstash|Splunk|Datadog|datadoghq|CloudWatch|ApplicationInsights|appinsights|Sentry|Stackdriver|google\.cloud\.logging|winston\.transports\.(?:File|Http|Stream)|pino[_\-]?(?:datadog|elasticsearch|loki)|logging\.handlers\.(?:SysLogHandler|HTTPHandler|WatchedFileHandler|RotatingFileHandler|TimedRotatingFileHandler)|logback|log4j2?\.xml|fluentd|fluent-bit|filebeat|papertrail|logtail|betterstack|syslog)\b", re.I)
PBD = re.compile(r"\b(?:DPIA|dpia|privacy[_\-]?impact|privacy[_\-]?review|privacy[_\-]?checklist|privacy[_\-]?by[_\-]?design|data[_\-]?protection[_\-]?(?:policy|review|impact)|PRIVACY\.md|privacy[_\-]?champion|records?[_\-]?of[_\-]?processing|RoPA|ropa)\b", re.I)
PBD_FILES = re.compile(r"(?:^|/)(?:PRIVACY|SECURITY|DPIA|DATA[_-]?PROTECTION)[^/]*\.md$|(?:^|/)\.github/(?:PULL_REQUEST_TEMPLATE|pull_request_template)\.md$|(?:^|/)docs?/(?:privacy|dpia|gdpr)", re.I)
REGION_HINT = re.compile(r"\b(?:us1|us-east-1|us-west-2|us-central1|eu-west-1|eu-central-1|europe-west|ap-southeast|\.us\.|\.eu\.|api\.eu\.|eu\.|region\s*[:=]\s*['\"]?[a-z]{2}-[a-z]+-\d)\b", re.I)
LOG_CALL = re.compile(r"(?:_?logger|_?log|logging|console|Log|winston|pino)\s*\.\s*(?:Log)?(?:Information|Info|Debug|Warn(?:ing)?|Error|Critical|Trace|log|print)\w*\s*\(|\bprint\s*\(|Console\.Write", re.I)
ANALYTICS_CALL = re.compile(r"\b(?:identify|track|trackEvent|logEvent|setUser|setUserProperties|people\.set|TrackEvent|gtag|mixpanel|amplitude|posthog|segment|analytics)\b\s*[.(]", re.I)
ROUTE_PARAM = re.compile(r"(?:Route|HttpGet|GetMapping|router\.get|app\.get|path|re_path)\s*\(\s*['\"][^'\"]*[{:<]\s*(\w+)|\?(\w+)=", re.I)


def has_pii_token(line):
    """A personal-data name (audit-sensitive-data-catalog) appears on the line."""
    return any(r["category"] in PERSONAL for r in sdc.find_names(line))


def url_has_pii(line):
    """A route parameter or query-string key on the line is a personal-data name."""
    return any(sdc.classify_name(n)["category"] in PERSONAL
               for m in ROUTE_PARAM.finditer(line) for n in m.groups() if n)


JS_MODULE_KW = re.compile(r"^\s*(?:export|import)\s+(?:default|const|let|var|class|function|async|interface|type|enum|abstract|\{|\*)")
ASSIGN_RE = re.compile(r"^\s*(?:(?:var|let|const|val|final|await|return)\s+)?(?:[\w<>\[\]?.,\s]+\s+)?(\w+)\s*(?::\s*[\w<>\[\]?]+)?\s*=\s*(?!=)")
_OPENS = re.compile(r"[({\[]")
_CLOSES = re.compile(r"[)}\]]")


def _bal(line):
    return len(_OPENS.findall(line)) - len(_CLOSES.findall(line))


def statement_block(lines, i, ext):
    """Return (start, end) of the statement containing 0-based line i, inclusive.
    C-like languages: start after the nearest boundary above (a line ending in ';' or '}',
    or in '{' with balanced parentheses - so 'identify({' is not a boundary); a lone '{'
    under an assignment (C# object initialisers) folds into the assignment line.
    Python/Ruby: walk up while brackets opened above line i are still unclosed."""
    clike = ext not in (".py", ".rb")
    start = i
    if clike:
        b = -1
        for j in range(i - 1, max(-1, i - 15), -1):
            prev = lines[j].rstrip()
            if not prev.strip():
                continue
            parens = prev.count("(") - prev.count(")")
            if prev.endswith(";") or prev.endswith("}") or (prev.endswith("{") and parens <= 0):
                b = j
                break
        if b >= 0 and lines[b].strip() == "{" and b - 1 >= 0 and ASSIGN_RE.match(lines[b - 1]):
            start = b - 1
        else:
            start = b + 1
        while start < i and not lines[start].strip():
            start += 1
    else:
        acc = 0
        for j in range(i - 1, max(-1, i - 15), -1):
            acc += _bal(lines[j])
            if acc > 0:
                start = j
            else:
                break
    end, depth = i, 0
    for j in range(start, min(len(lines), i + 15)):
        depth += _bal(lines[j])
        cur = lines[j].rstrip()
        end = j
        if j >= i and depth <= 0 and (not clike or cur.endswith((";", ")", "}", "},", ");"))):
            break
    return start, end


def block_has(lines, i, ext, rx):
    start, end = statement_block(lines, i, ext)
    return any(rx.search(lines[j]) for j in range(start, end + 1))


def read(path):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


def iter_files(root):
    # Shared skip list from repo_walk with this checker's extension set; read() applies the size cap.
    return repo_walk.iter_files(root, exts=CODE_EXT, names={"dockerfile"}, max_bytes=None)


def rel(root, p):
    return repo_walk.rel(root, p)


def ev(file, line, snippet, note=""):
    return {"file": file, "line": line, "snippet": snippet.strip()[:200], "note": note}


def load_inventory(root, path, run_mapper, mapper, not_checked):
    path = path or os.path.join(root, "audit", "evidence", "audit-privacy-data-flow-mapper", "data-inventory.json")
    if not os.path.exists(path) and run_mapper:
        cand = mapper or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                                       "audit-privacy-data-flow-mapper", "scripts", "pii_scan.py"))
        if os.path.exists(cand):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                subprocess.run([sys.executable, cand, root, "--out", path,
                                "--md", os.path.join(os.path.dirname(path), "inventory.md"),
                                "--mermaid", os.path.join(os.path.dirname(path), "data-flow.mmd")],
                               check=False, capture_output=True, text=True, timeout=900)
            except Exception as e:  # noqa: BLE001
                not_checked.append({"item": "personal-data inventory", "reason": f"mapper failed: {e}"})
        else:
            not_checked.append({"item": "personal-data inventory", "reason": "audit-privacy-data-flow-mapper not found next to this skill; pass --mapper or --inventory"})
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh), path
        except (OSError, json.JSONDecodeError) as e:
            not_checked.append({"item": "personal-data inventory", "reason": f"could not read {path}: {e}"})
    else:
        not_checked.append({"item": "personal-data inventory", "reason": f"{path} not found"})
    return None, path


def scan_repo(root):
    """One pass over the repo collecting evidence buckets."""
    b = {k: [] for k in ("delete_routes", "put_routes", "get_routes", "self_routes", "export", "erase", "restrict",
                         "consent_fields", "consent_ts", "consent_ver", "consent_src", "withdraw", "scheduler",
                         "retain_in_sched", "retain", "https", "http_weak", "at_rest", "pseudo", "audit",
                         "sec_event", "alerting", "log_ship", "pbd", "pbd_files", "region", "log_pii", "analytics_pii", "url_pii")}
    for path in iter_files(root):
        r = rel(root, path)
        text = read(path)
        if text is None:
            continue
        if PBD_FILES.search(r):
            b["pbd_files"].append(ev(r, 0, r, "privacy/PR-template document present"))
        lines = text.splitlines()
        file_has_sched = bool(SCHEDULER.search(text)) or bool(re.search(r"(?:^|/)(?:jobs?|tasks?|schedulers?|cron|workers?|BackgroundJobs?|management/commands)(?:/|$)", r, re.I))
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if not s:
                continue
            for verb in ("delete", "put", "get"):
                mo = ROUTE[verb].search(line)
                if mo:
                    route = next((g for g in mo.groups() if g), "") or ""
                    ctx = (route + " " + r + " " + line).lower()
                    subj = bool(re.search(SUBJECT, ctx)) and not (re.search(NON_SUBJECT, route.lower() or "") and not re.search(SUBJECT, route.lower()))
                    note = "subject resource" if subj else "non-subject resource (excluded)"
                    if verb == "delete" and re.search(NON_SUBJECT, (route or "").lower()) and not re.search(SUBJECT, (route or "").lower()):
                        note = "excluded: " + re.search(NON_SUBJECT, (route or "").lower()).group(0) + " resource, not personal-data erasure"
                        subj = False
                    b[f"{verb}_routes"].append(ev(r, i, s, note) | {"route": route, "subject": subj})
                    if SELF_ROUTE.search(route or "") or SELF_ROUTE.search(line):
                        b["self_routes"].append(ev(r, i, s, "self-service route"))
            if EXPORT.search(line) and not JS_MODULE_KW.match(line) and not re.search(r"^\s*(?:import|from|using|require)\b", line) and \
                    (ROUTE["get"].search(line) or ROUTE["put"].search(line) or re.search(r"\b(?:def|function|async|public|Task|void)\b", line) or "route" in r.lower() or "controller" in r.lower()):
                b["export"].append(ev(r, i, s))
            if ERASE_SYMBOL.search(line):
                b["erase"].append(ev(r, i, s))
            if RESTRICT.search(line):
                b["restrict"].append(ev(r, i, s))
            cm = CONSENT_FIELD.search(line)
            if cm and re.search(r"(?:\{\s*get;|@Column|models\.\w+Field|:\s*(?:boolean|Boolean|bool|Date|DateTime|string|number)\b|\bbool\b|\bBoolean\b|\bboolean\b|Column<|AddColumn|DataTypes\.|t\.(?:boolean|datetime|string)|BOOLEAN|BIT\b|TIMESTAMP|DATETIME)", line):
                b["consent_fields"].append(ev(r, i, s, "boolean" if BOOL_TYPE.search(line) else "non-boolean"))
            if CONSENT_TS.search(line):
                b["consent_ts"].append(ev(r, i, s))
            if CONSENT_VER.search(line):
                b["consent_ver"].append(ev(r, i, s))
            if CONSENT_SRC.search(line):
                b["consent_src"].append(ev(r, i, s))
            if WITHDRAW.search(line) and (ROUTE["put"].search(line) or ROUTE["delete"].search(line) or ROUTE["get"].search(line) or re.search(r"\b(?:def|function|async|public|Task|void|router|app)\b", line)):
                b["withdraw"].append(ev(r, i, s))
            if SCHEDULER.search(line):
                b["scheduler"].append(ev(r, i, s))
            if RETAIN.search(line):
                item = ev(r, i, s, "inside scheduled/job code" if file_has_sched else "not in a job file")
                b["retain"].append(item)
                if file_has_sched:
                    b["retain_in_sched"].append(item)
            if HTTPS.search(line):
                b["https"].append(ev(r, i, s))
            if HTTP_WEAK.search(line) and not s.startswith(("//", "#", "*")):
                b["http_weak"].append(ev(r, i, s))
            if AT_REST.search(line):
                b["at_rest"].append(ev(r, i, s))
            if PSEUDO.search(line):
                b["pseudo"].append(ev(r, i, s))
            if AUDIT.search(line):
                b["audit"].append(ev(r, i, s))
            if SECURITY_EVENT.search(line):
                b["sec_event"].append(ev(r, i, s))
            if ALERTING.search(line):
                b["alerting"].append(ev(r, i, s))
            if LOG_SHIP.search(line):
                b["log_ship"].append(ev(r, i, s))
            if PBD.search(line):
                b["pbd"].append(ev(r, i, s))
            if REGION_HINT.search(line) and re.search(r"https?://|region|host|endpoint|url", line, re.I):
                b["region"].append(ev(r, i, s))
            if has_pii_token(line):
                ext = os.path.splitext(r)[1].lower()
                if (LOG_CALL.search(line) or block_has(lines, i - 1, ext, LOG_CALL)) and not re.search(r"\b(?:Id|_id|id)\b\s*[,)]", line):
                    b["log_pii"].append(ev(r, i, s))
                if ANALYTICS_CALL.search(line) or block_has(lines, i - 1, ext, ANALYTICS_CALL):
                    b["analytics_pii"].append(ev(r, i, s, "analytics call (same statement)"))
            if url_has_pii(line):
                b["url_pii"].append(ev(r, i, s))
    return b


def evaluate(b, inv, not_checked):
    checks = []

    def add(cid, article, right, status, evidence, note, owner=None):
        checks.append({"id": cid, "article": article, "check": right, "status": status,
                       "evidence": evidence[:25], "note": note, "organisational_owner": owner})

    inv_fields = (inv or {}).get("fields", [])
    inv_tps = (inv or {}).get("third_parties", [])
    def direct(p):  # skip occurrences the mapper attributed through variable flow; the sink line itself is listed anyway
        return not str(p.get("context", "")).startswith("flow:")
    inv_log = [p | {"field": f["field"]} for f in inv_fields for p in f.get("processors", []) if p.get("type") in ("log", "url") and direct(p)]
    inv_an = [p | {"field": f["field"]} for f in inv_fields for p in f.get("processors", []) if direct(p) and (p.get("type") == "analytics"
              or (p.get("type") in ("outbound", "messaging") and any(t in ("Segment", "Mixpanel", "Amplitude", "Google Analytics", "PostHog", "Firebase", "Application Insights", "Sentry") for t in p.get("third_parties", []))))]
    subj_get = [x for x in b["get_routes"] if x["subject"]]
    subj_put = [x for x in b["put_routes"] if x["subject"]]
    subj_del = [x for x in b["delete_routes"] if x["subject"]]
    other_del = [x for x in b["delete_routes"] if not x["subject"]]

    # Access
    if b["self_routes"] or b["export"]:
        add("right-access", "Art.15", "Right of access (subject can obtain their data)", "implemented", b["self_routes"] + b["export"], "self-service or export route found")
    elif subj_get:
        add("right-access", "Art.15", "Right of access (subject can obtain their data)", "partial", subj_get, "read-by-id endpoints exist (admin/support path); no self-service or export route found")
    else:
        add("right-access", "Art.15", "Right of access (subject can obtain their data)", "missing", [], "no read endpoint on a subject resource found")
    # Portability
    add("right-portability", "Art.20", "Portability / export in a machine-readable format",
        "implemented" if b["export"] else "missing", b["export"], "export/download symbols found" if b["export"] else "no export/download/portability symbol found")
    # Erasure
    if subj_del or b["erase"]:
        st = "implemented" if subj_del else "partial"
        note = "DELETE route on a subject resource found" if subj_del else "anonymise/erase symbols found but no DELETE route on a subject resource; confirm they are reachable"
        if inv_tps:
            note += f"; confirm the path also reaches: {', '.join(t['name'] for t in inv_tps)} and caches/logs"
        add("right-erasure", "Art.17", "Erasure (row, dependants, files, cache, vendors)", st, subj_del + b["erase"] + other_del, note)
    else:
        add("right-erasure", "Art.17", "Erasure (row, dependants, files, cache, vendors)", "missing", other_del,
            "no DELETE route on a user/customer/account resource and no anonymise/erase symbol" + ("; the DELETE routes found are on non-subject resources" if other_del else ""))
    # Rectification
    add("right-rectification", "Art.16", "Rectification (subject data can be corrected)",
        "implemented" if subj_put else "missing", subj_put, "PUT/PATCH on a subject resource" if subj_put else "no update endpoint on a subject resource")
    # Restriction / objection
    add("right-restriction-objection", "Art.18/21", "Restriction of processing / objection / opt-out",
        "implemented" if b["restrict"] else "missing", b["restrict"], "opt-out / do-not-contact / restriction symbols found" if b["restrict"] else "no opt-out, unsubscribe, suppression or restriction flag found")
    # Consent capture
    cf = b["consent_fields"]
    if not cf:
        add("consent-capture", "Art.7(1)", "Consent captured with timestamp, policy version and source", "missing", [], "no consent/opt-in field found in models (may be lawful basis other than consent - organisational to confirm)", "DPO")
    else:
        has_ts, has_ver, has_src = bool(b["consent_ts"]), bool(b["consent_ver"]), bool(b["consent_src"])
        booleans = [x for x in cf if x["note"] == "boolean"]
        if has_ts and has_ver:
            st, note = "implemented", "consent field with timestamp and version"
        elif has_ts or has_ver:
            st, note = "partial", "consent field with " + ("timestamp" if has_ts else "version") + " only"
        else:
            st, note = "partial" if not booleans else "partial", "consent stored as a bare boolean - no timestamp, no policy version, no source" if booleans else "consent field without timestamp/version"
        add("consent-capture", "Art.7(1)", "Consent captured with timestamp, policy version and source", st,
            cf + b["consent_ts"] + b["consent_ver"] + b["consent_src"], note)
    # Consent withdrawal
    add("consent-withdrawal", "Art.7(3)", "Consent can be withdrawn as easily as given (endpoint/job stops downstream use)",
        "implemented" if b["withdraw"] else ("missing" if cf else "not-checked"), b["withdraw"],
        "withdraw/revoke/unsubscribe path found" if b["withdraw"] else ("no withdrawal path found for the consent field(s)" if cf else "no consent field to withdraw"))
    # Retention
    if b["retain_in_sched"]:
        add("retention-enforcement", "Art.5(1)(e)", "Retention enforced by scheduled purge/anonymise jobs", "implemented", b["retain_in_sched"], "purge/expiry logic inside scheduled job code; confirm it covers every storage location in the inventory")
    elif b["scheduler"] and b["retain"]:
        add("retention-enforcement", "Art.5(1)(e)", "Retention enforced by scheduled purge/anonymise jobs", "partial", b["scheduler"][:5] + b["retain"][:10], "schedulers and expiry code exist but not together; confirm which job enforces retention")
    elif b["retain"]:
        add("retention-enforcement", "Art.5(1)(e)", "Retention enforced by scheduled purge/anonymise jobs", "partial", b["retain"], "expiry/TTL code found (likely cache/session), no scheduled purge of stored personal data")
    else:
        add("retention-enforcement", "Art.5(1)(e)", "Retention enforced by scheduled purge/anonymise jobs", "missing", [], "no scheduler and no purge/expiry logic found; logs and backups need their own retention (organisational)", "Ops / DPO")
    # Minimisation
    mini = [ev(p["file"], p["line"], p.get("snippet", ""), f"{p['field']} in {p['type']} (inventory)") for p in inv_log] + b["log_pii"] + b["url_pii"]
    ana = [ev(p["file"], p["line"], p.get("snippet", ""), f"{p['field']} to {', '.join(p.get('third_parties') or ['analytics'])} (inventory)") for p in inv_an] + b["analytics_pii"]
    if mini or ana:
        add("minimisation-logs-urls-analytics", "Art.5(1)(c)", "No PII in logs, URLs, error trackers or analytics", "missing", mini + ana,
            f"{len(mini)} log/URL and {len(ana)} analytics/error-tracker occurrence(s) carry personal data")
    else:
        add("minimisation-logs-urls-analytics", "Art.5(1)(c)", "No PII in logs, URLs, error trackers or analytics", "implemented" if inv else "not-checked", [],
            "no PII found in log, URL or analytics sinks" if inv else "inventory unavailable; grep found nothing but coverage is partial")
    # Encryption in transit
    if b["https"] and not b["http_weak"]:
        add("encryption-transit", "Art.32", "Encryption in transit (HTTPS/HSTS, TLS to DB and vendors)", "implemented", b["https"], "HTTPS/HSTS/TLS markers found, no weak settings")
    elif b["https"] or b["http_weak"]:
        add("encryption-transit", "Art.32", "Encryption in transit (HTTPS/HSTS, TLS to DB and vendors)", "partial", b["https"][:10] + b["http_weak"], "weak/disabled TLS settings or plain-http endpoints found" if b["http_weak"] else "HTTPS markers found; TLS to DB/vendors not visible")
    else:
        add("encryption-transit", "Art.32", "Encryption in transit (HTTPS/HSTS, TLS to DB and vendors)", "not-checked", [], "no TLS configuration in code (may be terminated at the load balancer - infra evidence needed)", "Ops")
    # At rest / pseudonymisation
    if b["at_rest"]:
        add("encryption-at-rest-pseudonymisation", "Art.32/25", "Encryption at rest, field-level encryption, pseudonymisation", "partial", b["at_rest"] + b["pseudo"][:10], "at-rest/field encryption markers found; disk/TDE/KMS still infra-level")
    elif b["pseudo"]:
        add("encryption-at-rest-pseudonymisation", "Art.32/25", "Encryption at rest, field-level encryption, pseudonymisation", "partial", b["pseudo"], "hashing/pseudonymisation of some values (e.g. passwords) found; no field-level encryption; disk/TDE is infra-level (not checked)", "Ops")
    else:
        add("encryption-at-rest-pseudonymisation", "Art.32/25", "Encryption at rest, field-level encryption, pseudonymisation", "not-checked", [], "nothing in code; disk/TDE/KMS is infra-level", "Ops")
    # Access logging
    add("access-logging-pii", "Art.30/32", "Audit trail for access to and changes of personal data",
        "implemented" if b["audit"] else "missing", b["audit"], "audit/history mechanism found; confirm it covers reads of PII, not only writes" if b["audit"] else "no audit-log / history / temporal-table mechanism found")
    # Processors / transfers
    if inv_tps:
        regions = b["region"]
        add("processors-transfers", "Art.28/30/44-46", "Processor list, DPAs, cross-border transfer mechanism", "partial",
            [ev(f, 0, t["name"] + " (" + t.get("category", "") + ") fields: " + ", ".join(t.get("fields", [])), "from inventory")
             for t in inv_tps for f in sorted(t.get("files", []), key=lambda x: x.endswith((".json", ".csproj", ".xml", ".txt", ".toml")))[:1]] + regions,
            f"{len(inv_tps)} processor(s) identified in code: " + ", ".join(t['name'] for t in inv_tps) + "; DPAs and transfer mechanisms are contractual" + ("; region hints found (non-EU endpoints likely)" if regions else ""), "DPO / Legal")
    else:
        add("processors-transfers", "Art.28/30/44-46", "Processor list, DPAs, cross-border transfer mechanism", "not-checked" if not inv else "implemented", b["region"],
            "inventory unavailable" if not inv else "no third-party processors identified in code (confirm hosting/backup providers organisationally)", "DPO / Legal")
    # Breach detection
    have = [bool(b["sec_event"]), bool(b["log_ship"]), bool(b["alerting"])]
    st = "implemented" if all(have) else ("partial" if any(have) else "missing")
    add("breach-detection", "Art.33/34", "Security events logged centrally with alerting (72-hour notification)", st,
        b["sec_event"][:10] + b["log_ship"][:10] + b["alerting"][:10],
        "security events: %s; central log shipping: %s; alerting: %s" % tuple("yes" if h else "no" for h in have) + "; the notification runbook is organisational", "Security lead")
    # Privacy by design
    add("privacy-by-design", "Art.25/35", "Privacy-by-design triggers (DPIA/privacy checklist in the delivery process)",
        "implemented" if b["pbd_files"] else ("partial" if b["pbd"] else "missing"), b["pbd_files"] + b["pbd"][:10],
        "privacy/DPIA document or PR template present" if b["pbd_files"] else ("privacy/DPIA mentions found in code or docs" if b["pbd"] else "no DPIA, privacy checklist or PR-template trigger in the repo"), "Product + DPO")
    return checks


ORG_ITEMS = [
    {"item": "Data-processing agreements with every processor and their sub-processor lists", "article": "Art.28", "owner": "DPO / Legal", "why": "contracts are not in the repository"},
    {"item": "Transfer mechanism for non-EU/UK processors (SCCs, UK IDTA, DPF) and transfer impact assessment", "article": "Art.44-46", "owner": "DPO / Legal", "why": "contractual and jurisdictional"},
    {"item": "Records of processing activities (RoPA) kept current with the inventory", "article": "Art.30", "owner": "DPO", "why": "document, not code (the inventory is an input to it)"},
    {"item": "Retention schedule per data category, including logs and backups", "article": "Art.5(1)(e)", "owner": "DPO + Ops", "why": "policy decision; code can only enforce it"},
    {"item": "Backup and DR copies: re-deletion after restore, encryption, retention", "article": "Art.17, 32", "owner": "Ops", "why": "backup system outside the repository"},
    {"item": "Vendor-side deletion and retention settings (analytics, error trackers, email providers)", "article": "Art.17, 28", "owner": "Engineering + DPO", "why": "vendor consoles, not code"},
    {"item": "Infrastructure encryption at rest (disk, TDE, KMS) and key rotation", "article": "Art.32", "owner": "Ops", "why": "cloud/DB configuration unless IaC is in the repo"},
    {"item": "Lawful basis per processing purpose; consent text and version history", "article": "Art.6, 7", "owner": "DPO / Legal", "why": "legal assessment"},
    {"item": "Breach notification runbook (72-hour), incident roles, supervisory authority contact", "article": "Art.33, 34", "owner": "Security lead", "why": "process"},
    {"item": "DPIA for high-risk processing and a privacy review step for new features", "article": "Art.35, 25", "owner": "Product + DPO", "why": "process"},
    {"item": "Data-subject request intake, identity verification and one-month SLA tracking", "article": "Art.12", "owner": "Support + DPO", "why": "process around the endpoints"},
    {"item": "Staff access reviews, training and confidentiality commitments", "article": "Art.32, 39", "owner": "HR / Security", "why": "organisational"},
]


def to_markdown(res):
    o = ["# GDPR rights-fulfilment matrix", "", f"Root: `{res['root']}` - inventory: `{res['inventory_path']}` ({'loaded' if res['inventory_loaded'] else 'NOT available'}) - generated {res['generated_at']}", "",
         "| Right / obligation | Article | Implemented | Endpoint / job / evidence | Notes |", "|---|---|---|---|---|"]
    label = {"implemented": "Y", "partial": "Partial", "missing": "N", "not-checked": "Not checked"}
    for c in res["checks"]:
        locs = []
        for e in c["evidence"]:
            loc = f"`{e['file']}:{e['line']}`" if e["line"] else f"`{e['file']}`"
            if loc not in locs:
                locs.append(loc)
        evs = "; ".join(locs[:4]) or "-"
        o.append(f"| {c['check']} | {c['article']} | {label[c['status']]} | {evs} | {c['note']} |")
    o += ["", "## Evidence detail", ""]
    for c in res["checks"]:
        if not c["evidence"]:
            continue
        o.append(f"### {c['id']} ({c['status']})")
        for e in c["evidence"][:15]:
            snippet = e["snippet"].replace("|", "\\|")
            o.append(f"- `{e['file']}:{e['line']}` {snippet}" + (f"  - {e['note']}" if e.get("note") else ""))
        o.append("")
    o += ["## Outside code scope - needs organisational owner", "", "| Item | Article | Suggested owner | Why it cannot be verified in code |", "|---|---|---|---|"]
    for it in res["organisational"]:
        o.append(f"| {it['item']} | {it['article']} | {it['owner']} | {it['why']} |")
    o += ["", "## Not checked", ""]
    for n in res["not_checked"]:
        o.append(f"- {n['item']} - {n['reason']}")
    if not res["not_checked"]:
        o.append("- (nothing recorded)")
    return "\n".join(o) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--inventory", help="data-inventory.json path")
    ap.add_argument("--out", help="gdpr-checks.json path")
    ap.add_argument("--md", help="rights-matrix.md path")
    ap.add_argument("--no-run-mapper", action="store_true", help="do not run the sibling scanner when the inventory is missing")
    ap.add_argument("--mapper", help="path to audit-privacy-data-flow-mapper/scripts/pii_scan.py")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    not_checked = [
        {"item": "backups / DR copies", "reason": "outside the repository"},
        {"item": "vendor-side retention and deletion", "reason": "vendor consoles, not code"},
        {"item": "infrastructure encryption (disk, TDE, KMS)", "reason": "not visible unless IaC is in the repo"},
        {"item": "legal basis, DPAs, DPIA records, training", "reason": "organisational"},
    ]
    inv, inv_path = load_inventory(root, a.inventory, not a.no_run_mapper, a.mapper, not_checked)
    buckets = scan_repo(root)
    checks = evaluate(buckets, inv, not_checked)
    if inv:
        for n in inv.get("not_checked", []):
            not_checked.append({"item": "inventory: " + n.get("item", ""), "reason": n.get("reason", "")})
    res = {
        "skill": "audit-gdpr-data-protection",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": root,
        "inventory_path": inv_path,
        "inventory_loaded": bool(inv),
        "inventory_summary": {"fields": [f["field"] for f in inv.get("fields", [])], "third_parties": [t["name"] for t in inv.get("third_parties", [])]} if inv else None,
        "checks": checks,
        "summary": {s: sum(1 for c in checks if c["status"] == s) for s in ("implemented", "partial", "missing", "not-checked")},
        "organisational": ORG_ITEMS,
        "not_checked": not_checked,
    }
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(to_markdown(res))
    print(json.dumps({"inventory_loaded": bool(inv), "summary": res["summary"],
                      "checks": {c["id"]: c["status"] for c in checks}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
