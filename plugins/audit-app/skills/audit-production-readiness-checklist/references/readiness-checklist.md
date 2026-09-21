# Production readiness checklist (template)

Copy this table into the report and fill every row. `pass` needs evidence you
can cite; `fail` needs evidence of the gap; `unknown` needs the sentence "what
would make it pass". Default owners are suggestions for the blocker table.

| # | Item | Pass when | Fail when | Unknown when | Evidence to collect | Default owner |
|---|---|---|---|---|---|---|
| 1 | Environment-specific configuration separated | per-environment config files or env-var overrides exist; production values are injected at deploy time; the environment name is set in the container/CI | one config for all environments, or production values edited by hand on the server | config exists but the production injection path is outside the repo | `appsettings.*.json`, `application-*.yml`, `.env.example` + `.gitignore`, `settings/`, compose/k8s `env`, CI variables | dev lead |
| 2 | No hard-coded production secrets or connection strings | production config holds placeholders/references only | literal password, key, token, or a non-localhost connection string with credentials in any committed file | production config not in the repo | grep results, `audit-secrets-and-config` findings | dev lead + ops |
| 3 | Debug / developer features off in production | developer exception pages, `DEBUG`, `show-sql`, `synchronize`, source maps, Swagger UI, sensitive-data logging are gated on the development environment | any of those enabled unconditionally or in a production profile | the switch is controlled outside the repo | `Program.cs`, `settings.py`, `application-prod.yml`, `angular.json` prod config | dev lead |
| 4 | Health checks that verify dependencies | liveness endpoint and a readiness endpoint that checks DB, broker, cache; orchestrator probes point at them; endpoint excluded from auth | no health endpoint, or one that returns 200 unconditionally, or probes not configured | endpoint exists, probes live in infra outside the repo | `AddHealthChecks`, actuator config, terminus, `django-health-check`, compose `healthcheck`, k8s `readinessProbe` | dev + ops |
| 5 | Graceful shutdown | SIGTERM stops accepting requests, drains in-flight work and background jobs within the orchestrator grace period | process killed mid-request, jobs re-run or lost | framework default assumed but drain timeout unknown | shutdown hooks, `server.shutdown`, `terminationGracePeriodSeconds`, gunicorn `graceful_timeout` | dev |
| 6 | Timeouts and retries on all external calls | every DB/HTTP/queue client has a timeout shorter than the caller's; retries with backoff on idempotent calls; breaker or fallback on non-critical dependencies | any client without timeout, or retries on non-idempotent writes | clients configured in code you could not trace | client registrations, resilience libs, `audit-system-design` evidence | dev |
| 7 | Caching strategy defined | what is cached, where, TTL and invalidation are written down; cache is shared across instances when it must be | per-instance cache holding authoritative state; no strategy for hot reference data at expected load | no cache found and load unknown | cache config, `audit-performance-and-scalability` evidence | dev |
| 8 | Load test results available | a report exists for the expected peak (RPS, p95, error rate) on a production-like environment, dated within the release cycle | no load test | scripts exist but no results in the repo | `k6/`, `*.jmx`, `locustfile.py`, `artillery*.yml`, `docs/perf*` | dev + QA |
| 9 | Feature flags for risky changes | a flag system exists and the risky changes of this release are behind flags with a documented kill switch | risky change shipped unflagged with no rollback path | no flag system but no risky change identified | flag libs, config sections, release notes | product + dev |
| 10 | Runbook documented | a runbook names services, dependencies, SPOFs, how to restart/scale/rollback, where logs and dashboards are, and escalation | none, or a README with build instructions only | runbook lives in a wiki you could not read | `RUNBOOK.md`, `docs/operations/`, `docs/runbook*` | ops |
| 11 | On-call and alerting in place | alert rules for error rate, latency, saturation and dependency health exist and route to a rota | no alerts, or alerts to nobody | alerting is configured in a SaaS console outside the repo | alert rule files, `audit-logging-and-observability` alert matrix | ops |
| 12 | Rollback procedure tested | a written rollback for app and database, exercised on a staging environment in this release cycle; last migration reversible | no procedure, or an irreversible migration in this release | procedure written but no evidence it was exercised | deploy scripts, `docs/*rollback*`, `audit-db-schema` migration report | ops + dev |
| 13 | Launch checklist with owners | a checklist for this launch with an owner and status per item exists and is current | none | exists outside the repo | `LAUNCH*.md`, `docs/launch*`, project tracker export | product / release manager |
| 14 | Backups and restore | backups scheduled, restore tested, retention documented | no backups | managed by the platform, not visible | docs, IaC, `audit-infra-and-deployment` | ops |
| 15 | Centralised logging with retention | logs shipped off the box with correlation ids and a retention policy | local files only | sink configured outside the repo | `audit-logging-and-observability` findings | ops |
| 16 | CI runs tests and security scans on the release branch | pipeline exists and passes | no CI or tests skipped | CI outside the repo | `.github/workflows`, `azure-pipelines.yml`, `audit-test-coverage-and-ci` | dev |
| 17 | Sibling audits' Critical/High findings dispositioned | every Critical/High is fixed or covered by a valid acceptance record | any open Critical or High (no valid, unexpired acceptance record) | a sibling audit did not run (listed as a caveat) | `aggregate_findings.py` output (audit-findings-rollup verdict) | release manager |

## Evidence that usually lives outside the repo

Alert routing (PagerDuty/Opsgenie), dashboards, DR and restore drills, load-test
reports, on-call rota, wiki runbooks, cloud HA settings. Ask for a screenshot
or export; without it the item is `unknown`, not `pass`. Say so in the report.

## Status semantics

- `pass`: evidence cited, reviewer confirmed.
- `fail`: evidence of the gap cited; becomes a READY- finding.
- `unknown`: not verifiable from the inputs; the report says what would flip it. Unknown on items 2, 4, 12 or 17 is named in the judgement paragraph and the conditions; it does not change the recommendation word, which only open findings decide.
- `n/a`: item does not apply (say why), for example feature flags for a first release with no risky change.
