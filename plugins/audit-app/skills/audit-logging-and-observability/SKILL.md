---
name: audit-logging-and-observability
description: Reviews logging, tracing and monitoring - structured logging, correlation and trace ids propagated frontend to backend to downstream calls, sensible log levels (errors at Error, no hot-path info spam), no PII, passwords or tokens in logs, security events logged (login, failed auth, permission denied, admin action, export and delete), a centralised sink with retention, metrics and traces exported via OpenTelemetry or equivalent, and alerts for error rate, latency and saturation. Use it whenever the user asks about logging, log levels, structured logs, Serilog, log4j or Logback, winston, pino, structlog, observability, monitoring, metrics, dashboards, tracing, distributed tracing, OpenTelemetry, APM, correlation ids, request ids, trace ids, span context, alerting, alert rules, SLOs, "will we know when this breaks", "what happens during an incident", incident response readiness, or whether secrets or personal data end up in logs - even when they do not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: logging and observability

Logging and observability decide what happens on the worst day. This skill
answers two questions: **when production breaks at 02:00, can one engineer
reconstruct a single user's request end to end and be paged before the
customer calls?** - and **does that same log stream leak passwords, tokens or
personal data to everyone with log access?** The two are in tension: more
logging helps the first and hurts the second, so every finding names which
side it is on.

Read-only rule: never modify the audited code, config or dashboards. Write
only under `audit/`.

## Inputs and prerequisites

- Repository root(s): backend and frontend. Correlation is an end-to-end
  property, so audit both halves or say which half you could not see.
- Logging configuration: `appsettings*.json` Serilog sections, `logback.xml` /
  `application*.yml`, `logger.ts`, `settings.py` `LOGGING`, `.env`.
- Telemetry and alert definitions if they are in the repo: OpenTelemetry
  setup, Prometheus rule files, Grafana provisioning, `*.tf` for CloudWatch /
  Azure Monitor / Datadog monitors, `alertmanager.yml`.
- Optional from the user, asked once: where logs are shipped and for how long
  they are kept, which alerting tool pages the on-call, and read access to the
  dashboards. If it is not supplied, the matrix cell is `?`, never `Y`.
- `audit/stack.json` or `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>` (without `--write`). Python 3 stdlib only.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection`,
  `audit-code-scan` (grep pass and the shared file walker every script imports),
  `audit-sensitive-data-catalog` (which argument names are sensitive) and
  `audit-finding-writer` (findings I/O).

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`; open only
   `references/<stack>.md` for each detected backend and frontend, plus
   `references/opentelemetry.md` once. The stack file names the logger APIs,
   the config keys, the correlation-id middleware for that framework, and the
   false positives its grep patterns produce. Open the logger reference that
   matches what the manifest pulls in (`serilog.md`, `logback-log4j2.md`,
   `pino-winston.md`, `structlog.md`) for redaction and enrichment idioms.
2. **Automated pass** (evidence under `audit/evidence/audit-logging-and-observability/`):
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out hits.json`
     finds the dangerous shapes: whole request bodies logged, passwords / tokens /
     card fields in a log call, catch blocks logging at Debug/Trace,
     string-concatenated messages, stdout writers in server code, and the
     correlation-id middleware marker. `LOG-CORRELATION-MARKER` is an absence
     check: **zero hits across the repo means there is no correlation-id
     middleware** - that is the finding, not a clean result.
   - `python scripts/log_scan.py <repo> --out log-statements.json --md sensitive-log-table.md`
     inventories every log statement with its level, lists the ones whose
     arguments carry a sensitive name (classified by `audit-sensitive-data-catalog`,
     mapped to the categories in `references/sensitive-fields.md`) or a whole
     object (and the sensitive members the same handler reads from that object,
     e.g. `req.body.password`), and flags multi-line catch/except blocks that log
     below Warning. Its first table is the report's "file:line | logger call |
     sensitive fields | level" table.
   - `python scripts/correlation_check.py <repo> --out correlation.json --md correlation.md`
     walks the hops frontend outbound -> backend inbound -> log enrichment ->
     backend outbound (downstream) -> response echo and reports the first broken
     hop. Run it on the frontend repo too when the halves live apart.
   - `python scripts/alert_matrix.py <repo> --out alerts.json --md alert-matrix.md`
     reads alert-rule files (Prometheus/Alertmanager, Azure Monitor ARM/Bicep/
     Terraform, Datadog and Grafana JSON, CloudWatch) and builds signal -> alert
     exists `Y`/`N`/`?` -> source file for the signals in
     `references/alert-signals.md`.
   Every hit is a candidate. Open the file before rating it.
3. **Manual trace of the highest-risk flows**, in this order:
   1. **One request end to end.** Pick a real flow (login, or a write endpoint).
      Follow the correlation id: does the frontend generate or forward one, does
      middleware read or create it, is it on every log line for that request, is
      it forwarded on outbound HTTP calls and queue messages, does the response
      return it so support can quote it? A broken link anywhere makes the whole
      chain useless - that is one High finding, not four.
   2. **The authentication flow.** Are successful login, failed login, lockout,
      logout, token refresh, permission denied, password change and MFA changes
      logged with who/what/when/where - and does any of them log the password,
      the token or the full request body?
   3. **Admin and data-movement actions.** Role change, impersonation, export,
      bulk delete, tenant switch: logged with the actor and the target, or
      invisible?
   4. **The error path.** Take three `catch` blocks: is the exception object
      logged (not just `ex.Message`), at Error, once, and not swallowed? Count
      the swallow-and-continue blocks.
   5. **The hot path.** A list endpoint or a per-item loop logging at Info once
      per row is both a cost and an incident-time noise problem.
   6. **The sink.** Where do logs go when the container dies - stdout to a
      collector, a file in the container, or a database the app also serves
      from? What is the retention, and who can read it?
   7. **Metrics and traces.** Is anything exported at all, are the standard four
      (error rate, latency, traffic, saturation) available per service, and do
      spans carry the same correlation id as the logs?
4. **Write findings** with `python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py"` (prefix `LOG-`), one per root
   cause. Severity guidance (rubric:
   `$AUDIT_CORE_ROOT/skills/audit-finding-writer/references/severity-rubric.md`): credentials, tokens
   or card data written to logs = **Critical**; other PII in logs, no
   correlation id at all, errors swallowed or logged below Warning, no alerting
   on error rate = **High**; unstructured logs, no centralised sink, missing
   security-event logging, no metrics/traces = **Medium**; hot-path Info spam,
   missing retention policy = **Low/Medium**. Group all "field X logged in N
   places" hits into one finding with a `root_cause_key`.
5. **Produce the outputs** at the fixed paths:
   - `audit/findings/audit-logging-and-observability.json`
   - `audit/reports/audit-logging-and-observability.md` (template below,
     including the sensitive-field log table, the correlation-id propagation
     table and the alert coverage matrix)
   - `audit/evidence/audit-logging-and-observability/` (hits.json,
     log-statements.json, correlation.json, alerts.json and the three Markdown tables)
   - `audit/status/audit-logging-and-observability.json`:
     the status record defined in `audit-core:audit-finding-writer` (references/run-status.md)
6. **List what was not checked** and why. Typical entries: the log sink and its
   retention (lives in the logging SaaS, not the repo), alert routing and the
   on-call rota, dashboards, sampling rules applied by the collector, log
   volumes and cost, and any service whose source you did not have. Runtime log
   content was not inspected unless the user supplied samples - say so. List the
   folders the shared walker skips (`repo_walk.SKIP_DIRS` in `audit-code-scan`), plus
   `wwwroot` for `log_scan.py`, when they could hold server code.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `LOG`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Evidence:**

```lang
<the log statement, the config block, or the search that proves the absence>
```

- **Impact:** Plain language: what a reader of the logs gains, or what the on-call cannot see during an incident.
- **Remediation:** The concrete change in this stack (destructuring policy, redaction filter, middleware registration, alert rule), with a short example.
- **Reference:** CWE-532 (information in log file), CWE-117 (log injection), CWE-778 (insufficient logging), ASVS 7.x, OWASP-A09:2021.


## Output template (`audit/reports/audit-logging-and-observability.md`)

```markdown
## audit-logging-and-observability

**Stack:** dotnet (backend), angular (frontend) - **Logger:** Serilog -> stdout
**Correlation id:** absent - **Telemetry:** none exported - **Alerts:** 0 rules found

One paragraph: could an engineer reconstruct one request end to end, and would
anyone be paged before a customer complains?

### Log statements containing sensitive fields
| # | File:line | Logger call | Sensitive fields | Level | Fix |
|---|---|---|---|---|---|
| 1 | `src/routes/auth.js:10` | `logger.info({ body: req.body }, 'login attempt')` | req.body (whole-object), password, email | info | log `{ userId, ip }` only; pino `redact` paths |
| 2 | `Payments/ChargeService.cs:88` | `_log.LogInformation("charging {@Request}", request)` | {@Request}, CardNumber, Cvv | info | destructuring policy / `[NotLogged]`; log the charge id |

### Correlation-id propagation (frontend -> backend -> downstream)
| Hop | Status | Evidence | Fix / note |
|---|---|---|---|
| frontend_outbound | present / absent / n/a | `src/app/core/interceptors/correlation.interceptor.ts:12` | interceptor sends X-Correlation-Id or traceparent |
| backend_inbound | absent | - | correlation middleware first in the pipeline |
| log_enrichment | absent | - | id on every log line (LogContext / MDC / child logger / contextvars) |
| backend_outbound | absent | outbound call `src/services/orders.js:8` | forward the header / instrument the HTTP client |
| response_echo | absent | - | return X-Correlation-Id so support can quote it |
Chain: broken at backend_inbound.

### Alert coverage matrix
| Signal | Alert exists | Source file | Routed to on-call |
|---|---|---|---|
| Error rate (5xx / exceptions) | N | - | - |
| Latency (p95/p99) | Y | `monitoring/prometheus-rules.yml:4 (OrdersApiHighLatencyP95)` | ? no receiver in repo |
| Saturation - CPU / memory / pool-queue depth | N | - | - |
| Availability / uptime probe | N | - | - |
| Dependency health (DB, broker, cache) | N | - | - |
| Security - failed-login spike / permission denied / admin action | N | - | - |
| Background job failures / backlog | N | - | - |
| Certificate expiry / disk space | N | - | - |
Legend: Y = rule in the repo, N = rule files exist but none covers the signal, ? = no rule files in the repo (may live in a SaaS console - request an export; never promote ? to Y).

### Observability baseline
| Item | Status | Evidence |
|---|---|---|
| Structured logging | pass/fail | |
| Correlation / trace id propagated frontend -> backend -> downstream | fail | |
| Log levels sensible (errors at Error, no hot-path Info spam) | | |
| No PII / secrets in logs | | |
| Security events logged (login, failed auth, denied, admin, export/delete) | | |
| Centralised sink with retention | | |
| Metrics exported | | |
| Traces exported | | |

### Findings
(LOG- blocks, highest severity first)

### Not checked
- item - reason
```

## Examples

**Input (log_scan.py):** `src/auth/auth.controller.ts:24 [info] logger.info({ body: req.body }, 'login attempt') -> SENSITIVE: request body on an auth route`

**Output:**
```markdown
### [Critical] LOG-001 - Login handler writes the whole request body, including the password, to the log
- **Location:** `src/auth/auth.controller.ts:24` (login)
- **Confidence:** confirmed
- **Evidence:**

```ts
logger.info({ body: req.body }, 'login attempt');   // req.body = { email, password }
```

- **Impact:** Every user's plaintext password is stored in the log system and copied to anyone who can read logs - support staff, contractors, the log vendor - and is kept for the whole retention period. It also means a log leak is a full credential leak.
- **Remediation:** Log only non-secret identifiers (`{ email: req.body.email, ip: req.ip }`), and add a pino redaction config so it cannot happen again: `pino({ redact: ['req.body.password', 'req.headers.authorization', '*.token'] })`. Purge the affected log indices and force a password reset if the logs were retained.
- **Reference:** CWE-532, ASVS-7.1.1, OWASP-A09:2021
```

**Input (grep hit):** `src/orders/orders.service.ts:61  } catch (err) { logger.debug('could not reserve stock', err); }`

**Output:** `[High] LOG-004 - Stock reservation failures are logged at Debug and the request continues` -
impact: the default production level is `info`, so these disappear entirely; orders
complete without stock and nobody is alerted. Remediation: log at `error` with the
exception object and the correlation id, then rethrow or return a failure to the caller.

## Bundled files

- `references/<stack>.md` - loggers, config keys, correlation-id middleware, redaction APIs, security-event hooks and false positives per stack (`dotnet` Serilog/ILogger, `java-spring` Logback/MDC, `node-express` pino/winston, `python-django` structlog/logging, `angular`, `react`, `vue`); to add a stack, copy `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `references/opentelemetry.md` - the vendor-neutral baseline: traces/metrics/logs, W3C `traceparent`, resource attributes, sampling, exporter config per stack.
- `references/serilog.md`, `references/logback-log4j2.md`, `references/pino-winston.md`, `references/structlog.md` - per-logger templates, destructuring/redaction, context enrichment, sinks and retention.
- `references/sensitive-fields.md` - how catalog categories map to log-leak severities, false positives, and the redaction patterns per logger.
- `references/alert-signals.md` - the alert-signal catalogue (error rate, latency, saturation, availability, dependencies, security events, jobs, certs, disk), thresholds, and rule shapes per tool.
- `scripts/log_scan.py` - log-statement inventory, level classification, sensitive-field table (names classified by `audit-sensitive-data-catalog`), low-level catch and concatenation detection.
- `scripts/correlation_check.py` - hop-by-hop correlation-id propagation check.
- `scripts/alert_matrix.py` - alert-rule discovery (Prometheus, Azure Monitor, Datadog, Grafana, CloudWatch) and the signal -> alert -> source matrix.
- `scripts/patterns/<stack>.json` - the automated pattern pass (all seven stacks), run with `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- Atomic scripts called: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`,
  `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`, `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`;
  imported: `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py` (all three scripts),
  `$AUDIT_CORE_ROOT/skills/audit-sensitive-data-catalog/scripts/catalog.py` (`log_scan.py`).
- `evals/` - an Express sample logging a password in a request body, with no correlation-id middleware and an exception caught and logged at Debug, plus the negatives that must not be flagged.
