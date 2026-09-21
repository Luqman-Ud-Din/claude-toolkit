#!/usr/bin/env python3
"""Scan a repository for personal data (PII) and write a data inventory, a
Markdown inventory table and a Mermaid data-flow diagram.

Usage:
    python pii_scan.py <repo_root> [--out data-inventory.json] [--md inventory.md]
                       [--mermaid data-flow.mmd] [--catalog references/third-party-catalog.json]
                       [--max-occurrences 2000]

What it does (read-only against the audited repo; writes only the --out/--md/--mermaid paths):
  * Walks source, schema, config and template files with audit-code-scan's repo_walk (shared skip
    list, plus migrations_backup/).
  * Finds PII by FIELD NAME (email, phone, first_name, dob, ssn, iban, card_number, diagnosis, ...)
    and by VALUE (email literal, IBAN, Luhn-valid card, national ids) with audit-sensitive-data-catalog;
    only the catalog's personal-data canonical fields are inventoried - see references/pii-classification.md.
  * Classifies each field: identifier | contact | financial | health | special-category | credential | pii-adjacent.
  * Tags every occurrence with a SINK derived from the line and the file:
      model      - entity / ORM class property
      schema     - CREATE TABLE / migration / prisma / SQL column
      dto        - request/response shape
      collection - HTTP handler or form that receives the field
      log        - logger / console / print statement
      cache      - cache or redis key/value
      analytics  - analytics / telemetry / tracking call
      template   - email / SMS / notification template placeholder
      messaging  - email / SMS send call
      outbound   - HTTP call to another service (third party resolved from a domain / SDK catalog)
      url        - field in a route or query string
      code       - any other reference (kept for completeness, not a flow edge)
  * Resolves third parties from domains and SDK names found in the same file (catalog is a
    JSON file next to this script or references/third-party-catalog.json).
  * Collects retention hints (TTL, expiry, purge/cleanup jobs) so the inventory can say
    "unknown - no purge job found" honestly.
  * Emits data-inventory.json (schema: references/data-inventory-schema.md), a Markdown table
    (field, classification, storage locations, processors, third parties, retention) and a
    Mermaid flowchart collection -> storage -> processors -> third parties.

Every occurrence is a candidate. The skill must open the high-risk ones (log, cache,
outbound, analytics) and confirm the value, not just the name, is personal data.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from collections import defaultdict
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

# Folders skipped on top of repo_walk.SKIP_DIRS (reported in not_checked).
EXTRA_SKIP = ("migrations_backup",)
CODE_EXT = {".cs", ".java", ".kt", ".ts", ".tsx", ".js", ".jsx", ".vue", ".py", ".rb", ".go", ".php"}
SCHEMA_EXT = {".sql", ".prisma"}
TEMPLATE_EXT = {".html", ".cshtml", ".razor", ".hbs", ".handlebars", ".ejs", ".pug", ".jinja", ".jinja2",
                ".j2", ".txt", ".mjml", ".liquid", ".ftl", ".mustache"}
CONFIG_EXT = {".json", ".yml", ".yaml", ".xml", ".properties", ".env", ".toml", ".ini"}
ALL_EXT = CODE_EXT | SCHEMA_EXT | TEMPLATE_EXT | CONFIG_EXT
MAX_BYTES = 1_500_000

# ---------------------------------------------------------------------------
# PII names and values come from audit-sensitive-data-catalog. The inventory keeps the catalog's
# personal-data canonical fields; API keys, tokens, sessions and cookies have no canonical field.
# ---------------------------------------------------------------------------
PII_CANONICAL = {"email", "phone", "first_name", "last_name", "full_name", "address", "postal_code",
                 "date_of_birth", "national_id", "ip_address", "device_id", "geolocation", "iban",
                 "card_number", "card_security", "salary", "health", "special_category", "password",
                 "gender", "age", "signature", "photo"}
VALUE_LINE_SKIP = re.compile(r"(?:import|using|require|href=|xmlns|@\w+\.(?:png|jpg|svg))")


def _pii_class(r):
    return "pii-adjacent" if r["tier"] == "adjacent" else r["category"]


def match_pii(line):
    """Return [(field, classification, matched_by)] for the PII names and values on a line.
    One entry per (field, matched_by), so a line naming Email twice is one occurrence."""
    matched = []
    for r in sdc.find_names(line):
        if r["canonical"] in PII_CANONICAL:
            matched.append((r["canonical"], _pii_class(r), "name"))
    if not VALUE_LINE_SKIP.search(line):
        for m in sdc.find_values(line):
            if m["canonical"] not in PII_CANONICAL or m["confidence"] == "low":
                continue
            if m["placeholder"]:  # example domains, fixture mailboxes, test cards: never inventoried
                continue
            if m["attributes"].get("generic_mailbox"):
                matched.append((m["canonical"], m["category"], "value-generic"))
            elif m["sensitive"]:
                matched.append((m["canonical"], m["category"], "value"))
    seen, out = set(), []
    for field, cls, how in matched:
        if (field, how) not in seen:
            seen.add((field, how))
            out.append((field, cls, how))
    return out


# ---------------------------------------------------------------------------
# Sink detection: (sink, regex on the line). First match wins in this order.
# ---------------------------------------------------------------------------
SINK_LINE = [
    ("log", re.compile(r"(?:_?logger|_?log|logging|console|Log|Serilog|slf4j|winston|pino|bunyan|structlog)\s*\.\s*"
                       r"(?:Log)?(?:Information|Info|Debug|Warn(?:ing)?|Error|Critical|Trace|Verbose|Fatal|log|print|write)\w*\s*\(|"
                       r"\bprint\s*\(|System\.out\.print|Console\.Write|Debug\.WriteLine|Trace\.Write|logger\.(?:info|debug|warning|error)\b", re.I)),
    ("analytics", re.compile(r"\b(?:gtag|ga|fbq|mixpanel|amplitude|posthog|segment|analytics|heap|hotjar|clarity|appInsights|telemetry|TelemetryClient|firebase\.analytics|FirebaseAnalytics|logEvent|trackEvent|TrackEvent|TrackTrace|identify|setUserProperties|setUserId|Sentry|Bugsnag|Rollbar|setUser|captureException|dataLayer)\b\s*[.(]", re.I)),
    ("cache", re.compile(r"\b(?:cache|redis|memcache[d]?|IDistributedCache|IMemoryCache|_cache|_redis|_distributedCache|cacheManager|Cacheable|cache_key|CacheKey|CACHE_KEY|KeyPrefix|cache\.(?:set|get|put|add|delete)|StringSet|StringGet|SetStringAsync|GetStringAsync|SetAsync|GetOrCreate|GetOrCreateAsync)\b", re.I)),
    ("messaging", re.compile(r"\b(?:SmtpClient|MailMessage|SendGrid|SendGridClient|Twilio|MessageResource|SendEmailAsync|SendSmsAsync|SendMailAsync|send_mail|send_mass_mail|EmailMessage|EmailMultiAlternatives|nodemailer|sendMail|transporter|JavaMailSender|MimeMessage|SimpleMailMessage|MailKit|SmsSender|SmsService|SMSLibrary|PushNotification|FirebaseMessaging|notify\w*\(|OneSignal)\b", re.I)),
    ("outbound", re.compile(r"\b(?:HttpClient|PostAsJsonAsync|PostAsync|PutAsync|PatchAsync|GetAsync|SendAsync|HttpRequestMessage|RestClient|RestSharp|RestTemplate|WebClient|OkHttpClient|HttpPost|HttpGet|fetch|axios|got|superagent|requests\.(?:post|get|put|patch)|httpx|urllib|urlopen|http\.post|http\.get|http\.put|http\.patch|HttpService|\$http|ky)\b\s*[.(<]|https?://[a-z0-9.-]+\.[a-z]{2,}", re.I)),
    ("url", re.compile(r"(?:Route|HttpGet|HttpPost|HttpPut|HttpDelete|RequestMapping|GetMapping|PostMapping|router\.\w+|app\.\w+|path|re_path|url)\s*\(\s*['\"][^'\"]*[{:<]|\?[a-z_]*(?:email|phone|ssn|dob|name)=|[&?][a-zA-Z_]*=\$?\{|`[^`]*\?[^`]*\$\{", re.I)),
    ("collection", re.compile(r"\[(?:HttpPost|HttpPut|HttpPatch|FromBody|FromForm|FromQuery)\]|@(?:PostMapping|PutMapping|RequestBody|ModelAttribute|RequestParam)|router\.(?:post|put|patch)|app\.(?:post|put|patch)|req\.(?:body|query|params)|request\.(?:POST|GET|data|form|json)|serializer_class|ModelSerializer|forms\.\w+Field|FormControl|formControlName|FormGroup|<input|v-model|onChange=|useForm|register\(", re.I)),
    ("schema", re.compile(r"\bCREATE\s+TABLE|\bALTER\s+TABLE|\bADD\s+COLUMN|migrationBuilder\.|\.AddColumn<|table\.Column<|\bmodel\s+\w+\s*\{|@Column\(|@Entity\b|models\.(?:CharField|EmailField|TextField|IntegerField|DateField|DateTimeField|BooleanField|DecimalField)|column\s*:|Sequelize\.|DataTypes\.|t\.(?:string|text|integer)\b|\bcolumns?\b.*\bvarchar\b|\bvarchar\b|\bnvarchar\b", re.I)),
]
FILE_HINT = [
    ("template", re.compile(r"(?:^|/)(?:templates?|emails?|mail|sms|notifications?|views/emails?)(?:/|$)", re.I)),
    ("schema", re.compile(r"(?:^|/)(?:migrations?|schema|db|database|sql)(?:/|$)|schema\.prisma$|\.sql$", re.I)),
    ("dto", re.compile(r"(?:^|/)(?:dtos?|hostmodels?|viewmodels?|requests?|responses?|contracts?|payloads?|serializers?)(?:/|$)|(?:dto|request|response|viewmodel|payload|serializer)s?\.(?:cs|ts|java|kt|py|js)$", re.I)),
    ("model", re.compile(r"(?:^|/)(?:entit(?:y|ies)|models?|domain|schemas?)(?:/|$)|(?:entity|model)\.(?:cs|ts|java|kt|py|js)$|/models\.py$", re.I)),
    ("collection", re.compile(r"(?:^|/)(?:controllers?|handlers?|routes?|routers?|api|views|endpoints?|forms?|pages?|components?)(?:/|$)|(?:controller|handler|route|router|form|component|page)s?\.(?:cs|ts|tsx|jsx|java|kt|py|js|vue)$", re.I)),
]
MODEL_DECL = re.compile(r"\bpublic\s+(?:virtual\s+)?[\w<>?\[\]]+\s+(\w+)\s*\{\s*get;|"
                        r"@Column\b|@Entity\b|\bprivate\s+[\w<>]+\s+(\w+)\s*;|"
                        r"^\s*(\w+)\s*=\s*models\.\w+\(|"
                        r"^\s*(?:readonly\s+|public\s+|private\s+)?(\w+)\s*[?!]?\s*:\s*[\w<>\[\]| ]+;?\s*$|"
                        r"^\s*(\w+)\s+(?:String|Int|DateTime|Decimal|Boolean|BigInt)\b", re.I | re.M)
CLASS_DECL = re.compile(r"\b(?:class|interface|record|type|entity|model|table)\s+(\w+)|CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\[`\"]?(?:\w+[\]`\"]?\.)?[\[`\"]?(\w+)", re.I)
RETENTION = re.compile(r"\b(?:retention|purge|prune|cleanup|clean_up|cleanUp|delete\w*old|older[_ ]?than|expire[sd]?|expiry|ttl|time[_ ]?to[_ ]?live|SlidingExpiration|AbsoluteExpiration|AbsoluteExpirationRelativeToNow|setex|expireat|max_age|maxAge|anonymi[sz]e|pseudonymi[sz]e|erase|forget)\b", re.I)
SINK_RX = dict(SINK_LINE)
FLOW_SINKS = ("outbound", "messaging", "analytics", "log", "cache")
FLOW_LOOKAHEAD = 15
HOST_RE = re.compile(r"https?://([a-z0-9.-]+\.[a-z]{2,})", re.I)
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


def flow_sink(lines, i, ext, fields):
    """Where does the value on line i flow? Returns (sink, context).
    1. The statement block containing the line has a sink call (multi-line call args).
    2. The block assigns a variable that is passed (whole, or via .<pii property>) to a sink
       call within FLOW_LOOKAHEAD lines."""
    start, end = statement_block(lines, i, ext)
    for j in range(start, end + 1):
        if j == i:
            continue
        for cand in FLOW_SINKS:
            if SINK_RX[cand].search(lines[j]):
                return cand, f"block:{j + 1}"
    mo = ASSIGN_RE.match(lines[start])
    if not mo:
        return "code", "line"
    var = mo.group(1)
    if var in ("if", "for", "while", "return", "else", "switch"):
        return "code", "line"
    whole = re.compile(r"(?<![\w.])" + re.escape(var) + r"\b(?!\s*\.)")
    prop = re.compile(r"(?<![\w.])" + re.escape(var) + r"\.(\w+)")
    for j in range(end + 1, min(len(lines), end + 1 + FLOW_LOOKAHEAD)):
        nxt = lines[j]
        if re.match(r"\s*(?:public|private|protected|def |function |async def|class |export (?:default |async )?function)", nxt):
            break
        for cand in FLOW_SINKS:
            if not SINK_RX[cand].search(nxt):
                continue
            code_only = strip_strings(nxt)
            if whole.search(code_only):
                return cand, f"flow:{j + 1}"
            for pm in prop.finditer(code_only):
                if sdc.classify_name(pm.group(1))["canonical"] in fields:
                    return cand, f"flow:{j + 1}"
    return "code", "line"


_STR_RE = re.compile(r"\$?(?:\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)")
_INTERP_RE = re.compile(r"\$\{([^}]*)\}|\{([^}]*)\}")


def strip_strings(line):
    """Replace string-literal text with only its interpolated expressions, so a literal word
    like 'user' in 'Created user ${user.email}' is not mistaken for the variable."""
    def repl(m):
        parts = [a or b for a, b in _INTERP_RE.findall(m.group(0))]
        return " " + " ".join(p for p in parts if p) + " "
    return _STR_RE.sub(repl, line)
ANON = re.compile(r"\b(?:mask|redact|hash|anonymi[sz]e|pseudonymi[sz]e|encrypt|Protect\(|sha256|Sha256|HashData|obfuscat)\w*", re.I)

DEFAULT_CATALOG = [
    {"name": "Mailchimp", "category": "marketing", "domains": ["api.mailchimp.com", "mailchimp.com", "mandrillapp.com"], "sdk": ["MailchimpClient", "mailchimp_marketing", "@mailchimp/mailchimp_marketing", "Mailchimp.Net"]},
    {"name": "HubSpot", "category": "marketing", "domains": ["api.hubapi.com", "hubspot.com"], "sdk": ["HubSpot", "hubspot"]},
    {"name": "SendGrid", "category": "email", "domains": ["api.sendgrid.com", "sendgrid.net"], "sdk": ["SendGridClient", "@sendgrid/mail", "sendgrid"]},
    {"name": "Mailgun", "category": "email", "domains": ["api.mailgun.net", "api.eu.mailgun.net"], "sdk": ["mailgun", "Mailgun"]},
    {"name": "Amazon SES", "category": "email", "domains": ["email.us-east-1.amazonaws.com", "ses.amazonaws.com"], "sdk": ["AmazonSimpleEmailService", "SESClient", "boto3.client('ses')"]},
    {"name": "Twilio", "category": "sms", "domains": ["api.twilio.com"], "sdk": ["TwilioClient", "TwilioRestClient", "MessageResource", "twilio"]},
    {"name": "Vonage/Nexmo", "category": "sms", "domains": ["rest.nexmo.com", "api.nexmo.com", "api.vonage.com"], "sdk": ["Vonage", "nexmo"]},
    {"name": "Stripe", "category": "payments", "domains": ["api.stripe.com"], "sdk": ["StripeClient", "Stripe.", "stripe"]},
    {"name": "PayPal", "category": "payments", "domains": ["api.paypal.com", "api-m.paypal.com", "api.sandbox.paypal.com"], "sdk": ["PayPal"]},
    {"name": "Segment", "category": "analytics", "domains": ["api.segment.io", "cdn.segment.com"], "sdk": ["analytics-node", "@segment/analytics", "Segment.Analytics"]},
    {"name": "Mixpanel", "category": "analytics", "domains": ["api.mixpanel.com"], "sdk": ["mixpanel"]},
    {"name": "Amplitude", "category": "analytics", "domains": ["api.amplitude.com", "api2.amplitude.com"], "sdk": ["amplitude"]},
    {"name": "Google Analytics", "category": "analytics", "domains": ["www.google-analytics.com", "analytics.google.com", "googletagmanager.com"], "sdk": ["gtag", "ga(", "GoogleAnalytics", "dataLayer"]},
    {"name": "Firebase", "category": "analytics/push", "domains": ["firebaseio.com", "firebase.googleapis.com", "fcm.googleapis.com"], "sdk": ["firebase", "FirebaseAnalytics", "FirebaseMessaging", "@angular/fire", "FirebaseAdmin"]},
    {"name": "PostHog", "category": "analytics", "domains": ["app.posthog.com", "eu.posthog.com"], "sdk": ["posthog"]},
    {"name": "Hotjar", "category": "analytics", "domains": ["static.hotjar.com", "hotjar.com"], "sdk": ["hotjar", "hj("]},
    {"name": "Microsoft Clarity", "category": "analytics", "domains": ["clarity.ms"], "sdk": ["clarity("]},
    {"name": "Sentry", "category": "error-tracking", "domains": ["sentry.io", "ingest.sentry.io"], "sdk": ["Sentry", "@sentry/", "sentry_sdk", "raven"]},
    {"name": "Bugsnag", "category": "error-tracking", "domains": ["notify.bugsnag.com"], "sdk": ["Bugsnag"]},
    {"name": "Rollbar", "category": "error-tracking", "domains": ["api.rollbar.com"], "sdk": ["Rollbar"]},
    {"name": "Application Insights", "category": "error-tracking/analytics", "domains": ["dc.services.visualstudio.com", "applicationinsights.azure.com", "in.applicationinsights.azure.com"], "sdk": ["TelemetryClient", "ApplicationInsights", "appInsights"]},
    {"name": "Datadog", "category": "logging/monitoring", "domains": ["datadoghq.com", "http-intake.logs.datadoghq.com"], "sdk": ["datadog", "DogStatsd", "ddtrace"]},
    {"name": "New Relic", "category": "logging/monitoring", "domains": ["newrelic.com", "log-api.newrelic.com"], "sdk": ["newrelic", "NewRelic"]},
    {"name": "Intercom", "category": "support", "domains": ["api.intercom.io", "widget.intercom.io"], "sdk": ["Intercom", "intercom"]},
    {"name": "Zendesk", "category": "support", "domains": ["zendesk.com"], "sdk": ["Zendesk", "zendesk"]},
    {"name": "Freshdesk", "category": "support", "domains": ["freshdesk.com"], "sdk": ["Freshdesk"]},
    {"name": "Slack", "category": "messaging", "domains": ["hooks.slack.com", "slack.com/api"], "sdk": ["SlackClient", "@slack/web-api", "slack_sdk"]},
    {"name": "Google Drive", "category": "storage", "domains": ["www.googleapis.com/drive", "googleapis.com/upload/drive"], "sdk": ["DriveService", "Google.Apis.Drive", "googleapiclient"]},
    {"name": "Google Maps", "category": "geolocation", "domains": ["maps.googleapis.com"], "sdk": ["GoogleMaps", "@googlemaps"]},
    {"name": "Amazon S3", "category": "storage", "domains": ["s3.amazonaws.com", "amazonaws.com"], "sdk": ["AmazonS3Client", "S3Client", "boto3.client('s3')", "@aws-sdk/client-s3"]},
    {"name": "Azure Blob Storage", "category": "storage", "domains": ["blob.core.windows.net"], "sdk": ["BlobServiceClient", "BlobContainerClient"]},
    {"name": "Cloudinary", "category": "storage", "domains": ["api.cloudinary.com", "res.cloudinary.com"], "sdk": ["cloudinary", "Cloudinary"]},
    {"name": "Shopify", "category": "commerce", "domains": ["myshopify.com", "shopify.com"], "sdk": ["ShopifySharp", "Shopify", "shopify"]},
    {"name": "OpenAI", "category": "ai", "domains": ["api.openai.com"], "sdk": ["OpenAI", "openai"]},
    {"name": "Anthropic", "category": "ai", "domains": ["api.anthropic.com"], "sdk": ["Anthropic", "anthropic"]},
    {"name": "Auth0", "category": "identity", "domains": ["auth0.com"], "sdk": ["Auth0", "auth0"]},
    {"name": "Okta", "category": "identity", "domains": ["okta.com", "oktapreview.com"], "sdk": ["Okta", "okta"]},
    {"name": "Microsoft Entra / Graph", "category": "identity", "domains": ["graph.microsoft.com", "login.microsoftonline.com"], "sdk": ["GraphServiceClient", "@microsoft/microsoft-graph-client"]},
    {"name": "FBR (Pakistan tax)", "category": "government/tax", "domains": ["fbr.gov.pk", "gw.fbr.gov.pk"], "sdk": ["FbrInvoice", "FBR"]},
    {"name": "ZATCA (Saudi tax)", "category": "government/tax", "domains": ["zatca.gov.sa", "gw-fatoora.zatca.gov.sa"], "sdk": ["Zatca", "ZATCA"]},
]


def read(path):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


def iter_files(root):
    # Shared skip list from repo_walk plus EXTRA_SKIP, with this scanner's extension set. The size
    # cap is applied in read() so oversized files are listed in not_checked.
    return repo_walk.iter_files(root, exts=ALL_EXT, names={"dockerfile"}, extra_skip=EXTRA_SKIP, max_bytes=None)


def load_catalog(path):
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "third-party-catalog.json")
    if os.path.exists(here):
        with open(here, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return DEFAULT_CATALOG


def file_hint(rel):
    for sink, rx in FILE_HINT:
        if rx.search(rel):
            return sink
    return None


def is_minified_or_vendor(rel, text):
    low = rel.lower()
    if any(s in low for s in ("/vendor/", "/third_party/", "/lib/", ".min.", "/assets/i18n/", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "/wwwroot/lib/")):
        return True
    return text.count("\n") < 5 and len(text) > 20_000


def classify_line(line, rel, hint, ext):
    """Decide the sink for a line that contains a PII token."""
    for sink, rx in SINK_LINE:
        if rx.search(line):
            # 'url' only counts if the PII token is inside the route/query literal
            if sink == "schema" and ext in CODE_EXT and hint not in ("schema", "model"):
                # schema regex on code lines: only accept explicit migration/ORM APIs
                if not re.search(r"migrationBuilder\.|\.AddColumn<|table\.Column<|@Column\(|models\.\w+Field|DataTypes\.|column\s*:", line):
                    continue
            return sink
    if ext in SCHEMA_EXT:
        return "schema"
    if ext in TEMPLATE_EXT and hint == "template":
        return "template"
    if ext in TEMPLATE_EXT and re.search(r"\{\{|@Model\.|\$\{|<%=|\{%|\[\[", line):
        return "template"
    if hint in ("model", "schema") and MODEL_DECL.search(line):
        return "model"
    if hint == "dto" and MODEL_DECL.search(line):
        return "dto"
    if MODEL_DECL.search(line) and re.search(r"\{\s*get;|@Column|models\.\w+\(", line):
        return "model"
    if hint == "collection" and re.search(r"\.(?:Email|Phone|FirstName|LastName|Name|Dob|Ssn|Address)\b|\bmodel\.\w+|\breq\.|request\.|form\.", line, re.I):
        return "collection"
    return "code"


def find_class(lines, idx):
    """Nearest enclosing class/table name above a line."""
    for j in range(idx, max(-1, idx - 400), -1):
        mo = CLASS_DECL.search(lines[j])
        if mo:
            return mo.group(1) or mo.group(2)
    return None


def third_parties_in(text, catalog):
    found = []
    hosts = {h.lower() for h in HOST_RE.findall(text)}
    for vendor in catalog:
        hit = None
        for d in vendor.get("domains", []):
            if any(h == d.lower() or h.endswith("." + d.lower()) or d.lower() in h for h in hosts):
                hit = d
                break
        if not hit:
            for s in vendor.get("sdk", []):
                if s and s in text:
                    hit = s
                    break
        if hit:
            found.append({"name": vendor["name"], "category": vendor.get("category", "unknown"), "matched": hit})
    unresolved = sorted(h for h in hosts if not any(
        h == d.lower() or h.endswith("." + d.lower()) or d.lower() in h for v in catalog for d in v.get("domains", []))
        and not re.search(r"localhost|127\.0\.0\.1|schemas?\.|w3\.org|xmlsoap|microsoft\.com/|nuget\.org|npmjs|github\.com|example\.|apache\.org|json-schema|openapis|swagger|angular\.io|angular\.dev|dev\.to|stackoverflow|learn\.microsoft|docs\.|developer\.|fonts\.g", h))
    return found, unresolved


def scan(root, catalog, max_occ):
    occurrences = []
    third_party_files = {}
    unresolved_hosts = defaultdict(set)
    retention_hints = []
    skipped = []
    nfiles = 0
    dto_names = set()
    collection_files = {}
    for path in iter_files(root):
        rel = repo_walk.rel(root, path)
        text = read(path)
        if text is None:
            skipped.append({"file": rel, "reason": "unreadable or larger than 1.5 MB"})
            continue
        if is_minified_or_vendor(rel, text):
            continue
        nfiles += 1
        ext = os.path.splitext(rel)[1].lower()
        hint = file_hint(rel)
        lines = text.splitlines()
        if hint == "collection" and ext in CODE_EXT:
            collection_files[rel] = lines
        vendors, unresolved = third_parties_in(text, catalog)
        if vendors:
            third_party_files[rel] = vendors
        for h in unresolved:
            unresolved_hosts[h].add(rel)
        for i, line in enumerate(lines):
            s = line.strip()
            if not s or s.startswith(("//", "#", "*", "/*", "--", "<!--")) and not re.search(r"@Model|\{\{", s):
                if not (ext in TEMPLATE_EXT):
                    continue
            if RETENTION.search(line) and ext in CODE_EXT | CONFIG_EXT:
                retention_hints.append({"file": rel, "line": i + 1, "snippet": s[:200]})
            matched = match_pii(line)
            if not matched:
                continue
            sink = classify_line(line, rel, hint, ext)
            how_ctx = "line"
            if sink == "code" and ext in CODE_EXT:
                sink, how_ctx = flow_sink(lines, i, ext, [f for f, _, _ in matched])
            cls_name = find_class(lines, i) if sink in ("model", "schema", "dto") else None
            if sink == "dto" and cls_name:
                dto_names.add(cls_name)
            tp = vendors if sink in ("outbound", "messaging", "analytics") else []
            for field, cls, how in matched:
                if len(occurrences) >= max_occ:
                    break
                occurrences.append({
                    "field": field, "classification": cls, "matched_by": how, "context": how_ctx,
                    "sink": sink, "file": rel, "line": i + 1, "snippet": s[:240],
                    "container": cls_name,
                    "third_parties": [v["name"] for v in tp],
                    "protected": bool(ANON.search(line)),
                })
    # Handlers that receive a PII-bearing DTO are collection points even when the PII field
    # name never appears in the handler file.
    handler_points = []
    for rel, lines in collection_files.items():
        for i, line in enumerate(lines):
            for name in dto_names:
                if re.search(r"\b" + re.escape(name) + r"\b", line) and SINK_RX["collection"].search(line):
                    handler_points.append({"file": rel, "line": i + 1, "dto": name, "snippet": line.strip()[:200]})
    return occurrences, third_party_files, unresolved_hosts, retention_hints, skipped, nfiles, handler_points


def build_inventory(root, occ, tp_files, unresolved, retention_hints, skipped, nfiles, handler_points=()):
    fields = {}
    dto_fields = defaultdict(set)
    for o in occ:
        if o["sink"] == "dto" and o.get("container"):
            dto_fields[o["container"]].add(o["field"])
    for o in occ:
        f = fields.setdefault(o["field"], {
            "field": o["field"], "classification": o["classification"], "aliases": set(),
            "storage": [], "collection_points": [], "processors": [], "third_parties": [],
            "retention": None, "occurrence_count": 0, "occurrences": []})
        f["occurrence_count"] += 1
        f["occurrences"].append(o)
        loc = {"file": o["file"], "line": o["line"]}
        if o["sink"] in ("model", "schema"):
            f["storage"].append({"type": "table" if o["sink"] == "schema" or o["container"] else "model",
                                 "name": o["container"] or os.path.basename(o["file"]), **loc})
        elif o["sink"] == "cache":
            f["storage"].append({"type": "cache", "name": "cache/redis", **loc})
            f["processors"].append({"type": "cache", **loc, "snippet": o["snippet"][:160], "context": o["context"]})
        elif o["sink"] == "collection":
            f["collection_points"].append({"type": "handler/form", **loc})
        elif o["sink"] == "dto":
            f["collection_points"].append({"type": "dto", "name": o["container"], **loc})
        elif o["sink"] in ("log", "analytics", "template", "messaging", "url", "outbound"):
            f["processors"].append({"type": o["sink"], **loc, "snippet": o["snippet"][:160],
                                    "third_parties": o["third_parties"], "context": o["context"]})
        for tp in o["third_parties"]:
            if tp not in [t["name"] for t in f["third_parties"]]:
                f["third_parties"].append({"name": tp, "via": o["sink"], **loc})
    for hp in handler_points:
        for fname in dto_fields.get(hp["dto"], ()):
            if fname in fields:
                fields[fname]["collection_points"].append({"type": "handler", "dto": hp["dto"], "file": hp["file"], "line": hp["line"]})
    # de-duplicate storage/processors by (type,name,file)
    for f in fields.values():
        alias = set()
        for o in f["occurrences"]:
            for r in sdc.find_names(o["snippet"]):
                name = r["identifier"].split(".")[-1]
                if r["canonical"] == f["field"] and name.lower() != f["field"]:
                    alias.add(name)
        f["aliases"] = sorted(alias)[:10]
        seen, st = set(), []
        for s in f["storage"]:
            k = (s["type"], s.get("name"), s["file"])
            if k not in seen:
                seen.add(k)
                st.append(s)
        f["storage"] = st
        f["retention"] = "unknown - no retention/purge job found in code" if not retention_hints else \
            "unknown - see retention_hints (TTL/purge code exists; confirm it covers this field)"
    # third parties summary
    tps = {}
    for rel, vendors in tp_files.items():
        for v in vendors:
            e = tps.setdefault(v["name"], {"name": v["name"], "category": v["category"], "files": [], "fields": set(), "dpa": "unknown - organisational"})
            if rel not in e["files"]:
                e["files"].append(rel)
    for f in fields.values():
        for tp in f["third_parties"]:
            if tp["name"] in tps:
                tps[tp["name"]]["fields"].add(f["field"])
    for e in tps.values():
        e["fields"] = sorted(e["fields"])
    # flows
    flows = []
    for f in fields.values():
        cps = f["collection_points"] or [{"type": "unknown-collection", "file": "?", "line": 0}]
        stores = [s for s in f["storage"] if s["type"] != "cache"]
        for s in stores:
            flows.append({"field": f["field"], "from": "collection", "to": f"table:{s['name']}", "via": "write"})
        for p in f["processors"]:
            src = f"table:{stores[0]['name']}" if stores else "collection"
            if p["type"] == "outbound":
                for tp in p.get("third_parties") or ["unresolved third party"]:
                    flows.append({"field": f["field"], "from": src, "to": f"vendor:{tp}", "via": "http"})
            elif p["type"] in ("messaging", "analytics"):
                for tp in p.get("third_parties") or [p["type"]]:
                    flows.append({"field": f["field"], "from": src, "to": f"vendor:{tp}", "via": p["type"]})
            else:
                flows.append({"field": f["field"], "from": src, "to": f"proc:{p['type']}", "via": p["type"]})
        del cps
    not_checked = [
        {"item": "retention", "reason": "only code-visible TTLs/purge jobs are recorded; policy retention is organisational"},
        {"item": "binary / compiled templates and minified bundles", "reason": "skipped by the scanner"},
        {"item": "dynamically built payloads", "reason": "fields sent to vendors are inferred from the same file; confirm by hand"},
        {"item": "folders " + ", ".join(sorted(set(repo_walk.SKIP_DIRS) | set(EXTRA_SKIP))),
         "reason": "skipped by audit-code-scan's shared walker (plus migrations_backup); may hold source in unusual layouts"},
    ]
    if unresolved:
        not_checked.append({"item": "unresolved outbound hosts: " + ", ".join(sorted(unresolved)[:15]),
                            "reason": "not in references/third-party-catalog; classify by hand"})
    if skipped:
        not_checked.append({"item": f"{len(skipped)} file(s) skipped", "reason": "unreadable or over size limit"})
    inv = {
        "skill": "audit-privacy-data-flow-mapper",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": os.path.abspath(root),
        "files_scanned": nfiles,
        "fields": sorted(fields.values(), key=lambda f: (-len(f["third_parties"]), -f["occurrence_count"])),
        "third_parties": sorted(tps.values(), key=lambda t: t["name"]),
        "unresolved_hosts": {h: sorted(v) for h, v in unresolved.items()},
        "retention_hints": retention_hints[:200],
        "flows": flows,
        "stats": {
            "fields": len(fields),
            "occurrences": len(occ),
            "by_sink": {s: sum(1 for o in occ if o["sink"] == s) for s in
                        ("model", "schema", "dto", "collection", "log", "cache", "analytics", "template", "messaging", "outbound", "url", "code")},
            "by_classification": {c: len([f for f in fields.values() if f["classification"] == c]) for c in
                                  sorted({f["classification"] for f in fields.values()})},
        },
        "not_checked": not_checked,
    }
    return inv


def fmt_locs(items, key="type"):
    out = []
    for it in items:
        name = it.get("name") or it.get(key) or ""
        tp = ", ".join(it.get("third_parties") or [])
        label = f"{it.get(key)} {name}".strip() if it.get(key) != name else name
        if tp:
            label += f" -> {tp}"
        out.append(f"{label} (`{it['file']}:{it['line']}`)")
    return "; ".join(out) if out else "-"


def to_markdown(inv):
    o = ["# Personal-data inventory", "", f"Root: `{inv['root']}` - files scanned: {inv['files_scanned']} - generated: {inv['generated_at']}", "",
         "| Field | Classification | Storage locations | Processors (in-code) | Third parties | Retention |",
         "|---|---|---|---|---|---|"]
    for f in inv["fields"]:
        procs = [p for p in f["processors"] if p["type"] != "outbound"]
        tps = "; ".join(f"{t['name']} via {t['via']} (`{t['file']}:{t['line']}`)" for t in f["third_parties"]) or "-"
        o.append(f"| {f['field']} | {f['classification']} | {fmt_locs(f['storage'])} | {fmt_locs(procs)} | {tps} | {f['retention']} |")
    if not inv["fields"]:
        o.append("| (no PII field names or values found) | | | | | |")
    o += ["", "## Third parties / processors", "", "| Vendor | Category | Fields | Files | DPA known? |", "|---|---|---|---|---|"]
    for t in inv["third_parties"]:
        o.append(f"| {t['name']} | {t['category']} | {', '.join(t['fields']) or '-'} | {', '.join('`' + x + '`' for x in t['files'][:5])} | {t['dpa']} |")
    if not inv["third_parties"]:
        o.append("| (none resolved) | | | | |")
    if inv["unresolved_hosts"]:
        o += ["", "Unresolved outbound hosts: " + ", ".join(f"`{h}`" for h in sorted(inv["unresolved_hosts"])[:20])]
    o += ["", "## Occurrences by sink", "", "| Sink | Count |", "|---|---|"]
    for s, n in inv["stats"]["by_sink"].items():
        o.append(f"| {s} | {n} |")
    o += ["", "## Data-flow diagram", "", "```mermaid", to_mermaid(inv).rstrip(), "```", "", "## Not checked", ""]
    for n in inv["not_checked"]:
        o.append(f"- {n['item']} - {n['reason']}")
    return "\n".join(o) + "\n"


def _nid(prefix, name, ids):
    key = f"{prefix}:{name}"
    if key not in ids:
        ids[key] = f"{prefix}{len(ids) + 1}"
    return ids[key]


def to_mermaid(inv):
    ids, edges = {}, defaultdict(set)
    nodes = defaultdict(dict)
    for fl in inv["flows"]:
        for end in (fl["from"], fl["to"]):
            kind, _, name = end.partition(":")
            if kind == "collection":
                nodes["Collection"][_nid("C", "collection", ids)] = "Collection points (handlers/forms)"
            elif kind == "table":
                nodes["Storage"][_nid("S", name, ids)] = f"[({name})]"
            elif kind == "proc":
                nodes["Processing"][_nid("P", name, ids)] = {"log": "Application logs", "cache": "Cache / Redis", "template": "Email/SMS templates",
                                                              "url": "URLs / query strings", "analytics": "Analytics", "messaging": "Messaging"}.get(name, name)
            elif kind == "vendor":
                nodes["ThirdParties"][_nid("T", name, ids)] = name
        prefix = {"collection": "C", "table": "S", "proc": "P", "vendor": "T"}
        k_from, _, n_from = fl["from"].partition(":")
        k_to, _, n_to = fl["to"].partition(":")
        a = ids.get(f"{prefix.get(k_from, 'P')}:{n_from or 'collection'}")
        b = ids.get(f"{prefix.get(k_to, 'P')}:{n_to}")
        if a and b:
            edges[(a, b)].add(fl["field"])
    o = ["flowchart LR"]
    for group in ("Collection", "Storage", "Processing", "ThirdParties"):
        if not nodes[group]:
            continue
        o.append(f"  subgraph {group}")
        for nid, label in nodes[group].items():
            if isinstance(label, str) and label.startswith("[("):
                o.append(f"    {nid}{label}")
            else:
                o.append(f"    {nid}[\"{label}\"]")
        o.append("  end")
    for (a, b), fs in sorted(edges.items()):
        o.append(f"  {a} -->|{', '.join(sorted(fs))}| {b}")
    if len(o) == 1:
        o.append("  N[\"no personal-data flows found\"]")
    return "\n".join(o) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--out", help="data-inventory.json path")
    ap.add_argument("--md", help="Markdown inventory path")
    ap.add_argument("--mermaid", help="Mermaid .mmd path")
    ap.add_argument("--catalog", help="third-party catalog JSON (default: references/third-party-catalog.json or built-in)")
    ap.add_argument("--max-occurrences", type=int, default=2000)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    catalog = load_catalog(a.catalog)
    occ, tp_files, unresolved, retention_hints, skipped, nfiles, handler_points = scan(root, catalog, a.max_occurrences)
    inv = build_inventory(root, occ, tp_files, unresolved, retention_hints, skipped, nfiles, handler_points)
    for target, text in ((a.out, json.dumps(inv, indent=2)), (a.md, to_markdown(inv) if a.md else None),
                         (a.mermaid, to_mermaid(inv) if a.mermaid else None)):
        if target and text is not None:
            os.makedirs(os.path.dirname(os.path.abspath(target)) or ".", exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(text)
    print(json.dumps({"files_scanned": nfiles, "fields": inv["stats"]["fields"], "occurrences": inv["stats"]["occurrences"],
                      "by_sink": inv["stats"]["by_sink"], "third_parties": [t["name"] for t in inv["third_parties"]],
                      "unresolved_hosts": sorted(inv["unresolved_hosts"])[:10]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
