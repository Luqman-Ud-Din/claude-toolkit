# Child contracts for audit-application

Built from the child SKILL.md files as they are (read, not edited). The shared
contract, from `audit-finding-writer/references/findings-schema.md`, is four paths
per skill, all relative to the audited repo:

| Artifact | Path |
|---|---|
| Findings | `audit/findings/<skill>.json` |
| Markdown section | `audit/reports/<skill>.md` |
| Status | `audit/status/<skill>.json` - `{"skill","status":"completed|failed|skipped","reason","started_at","finished_at"}` |
| Evidence | `audit/evidence/<skill>/` |

Every child reads `audit/stack.json` when present. Setup writes it once with
`audit-stack-detection` (`$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`); a standalone
child runs the same script without `--write`.
Columns below: **Wave** is the execution order inside the phase (`references/profiles.json`);
**Parallel-safe** means safe to run concurrently with the other members of its wave;
**Depends on** lists inputs produced by other skills (soft = optional, the child degrades
and records the gap). Evidence files listed are the ones each child names beyond the four
standard paths.

## Pipeline children

| Skill | Phase | Wave | Inputs (beyond repo + stack.json) | Outputs (evidence, extra) | Prefix | Parallel-safe | Depends on |
|---|---|---|---|---|---|---|---|
| audit-system-design | discovery | 1 | docs/ADRs, deployment descriptors, scale context (asked once) | `evidence/audit-system-design/` (diagrams, module graph, topology, data ownership, doc drift) | ARCH | Y | - |
| audit-privacy-data-flow-mapper | discovery | 1 | schema exports, vendor list (optional) | `data-inventory.json`, `inventory.md`, `data-flow.mmd`, `hits.json` | PII | Y | - |
| audit-api-contract | discovery | 1 | `evidence/audit-endpoint-inventory/endpoints.json`; current + previous OpenAPI (optional), frontend root | `spec-diff.json/.md`, `hits.json/.md` | API | Y | endpoint-inventory step |
| audit-db-schema | discovery | 1 | migrations, DDL, ORM models, read-only connection (optional) | `migrations.json/.md`, `checklist.json/.md`, `live-schema.sql`, `hits.json` | DB | Y | - |
| audit-authz-and-access-control | security | 1 | `evidence/audit-endpoint-inventory/endpoints.json` + `endpoints.probe.json`; test URL + two users' tokens (optional probe) | `probe.json`, `hits.json` | AUTHZ | Y | endpoint-inventory step |
| audit-multi-tenant-isolation | security | 1 | `evidence/audit-endpoint-inventory/endpoints.probe.json` (probe input); test URL + `tenants.json` for two tenants (optional probe); runs only when multi-tenant | `paths.json/.md`, `probe.json`, `hits.json` | TENANT | Y | endpoint-inventory step |
| audit-secrets-and-config | security | 1 | git history (not shallow); gitleaks/trufflehog optional | `keys.json/.md`, `history.json/.md`, `hits.json` | SEC | Y | - |
| audit-security-headers-and-middleware | security | 1 | pipeline + hosting config; staging URL (optional, never production) | `middleware.json/.md`, `live-headers.json/.md`, `hits-<stack>.json/.md` | HDR | Y | - |
| audit-dependency-vulnerabilities | security | 1 | lockfiles / restored `obj/`; scanners and network optional | `dep-audit.json/.md`, `hits.json` | DEP | Y | - |
| audit-injection-vulnerabilities | security | 2 | `evidence/audit-endpoint-inventory/endpoints.json` (reachability, soft); authz findings (soft) | `hits-<stack>.json/.md` | INJ | Y | endpoint-inventory step, authz (soft) |
| audit-frontend-xss-and-dom-safety | security | 2 | `findings/audit-security-headers-and-middleware.json` (CSP, soft) | `hits-<stack>.json/.md`, `scripts.json` | XSS | Y | headers (soft) |
| audit-client-auth-and-storage | security | 3 | production build output (optional); headers, authz and XSS findings (soft) | `hits-<stack>.json/.md`, `secrets.json/.md` | CAUTH | Y | headers, authz, XSS (soft) |
| audit-async-and-dependency-injection | quality | 1 | multi-tenant answer (raises captive-DbContext severity) | `hits.json`, `di.json/.md`, `<id>-trace.md` | ASYNC | Y | - |
| audit-orm-query-and-data-access | quality | 1 | `evidence/audit-endpoint-inventory/endpoints.json` (unbounded endpoints); `findings/audit-db-schema.json` (index list, soft); query log (optional) | `hits.json/.md`, `unbounded.json/.md`, `<id>-trace.md` | ORM | Y | endpoint-inventory step, db-schema (soft) |
| audit-backend-resource-leak | quality | 1 | running instance + load tool (optional) | `hits.json/.md`, `loadtest-plan.md`, `<id>-trace.md` | LEAK | Y | - |
| audit-frontend-best-practices | quality | 1 | Node for the bundle report (optional) | `hits.json`, `config.json`, `routes.json`, `bundle.json` | FEBP | Y | - (self-skips without a frontend) |
| audit-frontend-memory-leak | quality | 1 | Chromium DevTools for confirmation (manual) | `leaks.json`, `hits.json`, `heap-<route>.md` | FELEAK | Y | - (self-skips without a frontend) |
| audit-accessibility-and-i18n | quality | 1 | required locales / RTL; axe-core + served build (optional) | `hits.json`, `templates.json/.md`, `axe/` | A11Y | Y | - |
| audit-business-logic | quality | 1 | confirmed critical flows (checkpoint), domain summary | `hits.json/.md`, `flows.json`, `<flow>.mmd` | BIZ | Y | critical-flows checkpoint |
| audit-concurrency-and-race-condition | quality | 2 | schema, job config, replica count; business-logic hand-offs | `hits.json/.md`, `inventory.json/.md` | RACE | Y | business-logic (soft), db-schema (soft) |
| audit-datetime-and-timezone | quality | 2 | schema, infra files, user zones; business-logic hand-offs | `hits.json/.md`, `date-fields.json/.md` | TIME | Y | business-logic (soft) |
| audit-performance-and-scalability | quality | 2 | `evidence/audit-endpoint-inventory/endpoints.json` + `endpoints.probe.json` (latency table, k6 input); ORM, leak, frontend-best-practices findings (soft); env URL + load tool (optional) | `hits.json`, `loadtest.js` | PERF | Y | endpoint-inventory step; orm, leak, febp (soft) |
| audit-technical-debt | quality | 3 | git history; `findings/*.json` (TEST, DEP, FEBP, ORM, ASYNC, LEAK, FELEAK, ARCH) | `evidence/audit-technical-debt/` (churn, complexity, duplicates, score) | DEBT | N (reads the whole findings folder) | every quality skill; deps, tests, system-design |
| audit-logging-and-observability | readiness | 1 | logging config, telemetry and alert definitions; log retention answers (asked once) | `evidence/audit-logging-and-observability/` | LOG | Y | - |
| audit-test-coverage-and-ci | readiness | 1 | CI files; toolchain to run the suite (optional); critical paths | `tests.json/.md`, `ci.json/.md`, `hits.json` | TEST | Y | critical-flows checkpoint |
| audit-infra-and-deployment | readiness | 1 | Dockerfiles, manifests, IaC; hadolint/trivy/checkov optional; backup/DR records | `scorecard.json/.md`, `hits.json` | INFRA | Y | - (self-skips without deployment artifacts) |
| audit-licensing-and-compliance | readiness | 1 | manifests, local package caches, distribution model | `license-inventory.md`, `THIRD-PARTY-NOTICES.md`, `hits.json` | LIC | Y | - |
| audit-gdpr-data-protection | readiness | 1 | `evidence/audit-privacy-data-flow-mapper/data-inventory.json` | `gdpr-checks.json`, `rights-matrix.md`, `hits.json` | GDPR | N (may write the mapper's inventory, see 7) | privacy mapper |
| audit-soc2-controls-evidence | readiness | 2 | `gh` CLI (optional); data inventory, dependency findings, `gdpr-checks.json` | `control-matrix.json/.md`, `hits.json`, collected evidence | SOC2 | Y | gdpr, privacy mapper, deps (soft) |
| audit-production-readiness-checklist | readiness | 3 | `findings/*.json` + `status/*.json` (through audit-findings-rollup); deployment descriptors; launch owner answers; accepted-risk file | `readiness.json/.md`, `summary.json/.md`, `hits.json` | READY | N (aggregates everything) | every earlier skill |
| audit-owasp-asvs-mapper | reporting | 2 | `findings/*.json`, `status/*.json` (loaded through audit-findings-rollup) | `reports/audit-owasp-asvs-mapper.md`, own findings (MAP-001/002), **edits other skills' findings files** (adds references, `extra.mapping`) | MAP | N | dedupe step; all findings |
| audit-report-generator | reporting | 3 | `findings/*.json`, `status/*.json` (through audit-findings-rollup: de-duplication, counts, verdict), mapper/GDPR/SOC 2 reports, evidence | **`audit/audit-report.md`** (+ .docx/.pdf), own status; findings/report only for RPT findings | RPT | N | mapper |

## Infrastructure steps (atomic skills, not audit areas)

Plan items of type `action`. They write no `audit/status/` file and no findings, so they get no
row in the report's scope table or pass/fail matrix, and `summary.py` and `run_state.py finish`
never count them as skills. `--skill <name>` refuses every skill in this table.

| Skill | Plan step | When it is planned | Writes | Read by |
|---|---|---|---|---|
| audit-stack-detection | setup `detect-stack` | always (plan.py detects in memory; `run_state.py init` writes the file with `multi_tenant`) | `audit/stack.json` | every child |
| audit-endpoint-inventory | discovery `endpoint-inventory`, before the discovery skills | when api-contract, authz, multi-tenant isolation, ORM or performance is planned | `evidence/audit-endpoint-inventory/endpoints.json`, `endpoints.md`, `endpoints.probe.json` | api-contract, authz, multi-tenant isolation, ORM, performance; injection (soft) |
| audit-findings-rollup | reporting `dedupe` | always | `evidence/audit-findings-rollup/rollup.json`, `rollup.md` | the reporting phase; readiness, mapper, report generator and technical debt import it; `summary.py` recomputes it at read time |
| audit-code-scan | none (library) | - | nothing of its own; children write `hits.json` into their own evidence folder | every child with a grep pass or a file walk |
| audit-sensitive-data-catalog | none (library) | - | nothing | children that judge sensitive names and values |
| audit-git-history | none (library) | - | nothing | technical debt, secrets, SOC 2 |

## Helper (not a pipeline step)

| Skill | Role | Prefix |
|---|---|---|
| audit-finding-writer | Owns the finding format, severity rubric and `findings.py`; every child calls `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` to emit findings. `--skill audit-finding-writer` is refused. | FW |

## Inconsistencies with the shared contract and how the orchestrator reconciles them

1. **Report generator's deliverable path.** It writes `audit/audit-report.md`, not
   `audit/reports/audit-report-generator.md`, and writes findings/report files only when
   it has RPT findings. Reconciled: `profiles.json` marks it `findings_optional`, so
   `run_state.py complete` does not warn about missing files; `summary.py` reads the
   verdict from `audit/audit-report.md`.
2. **Every file in `audit/findings/` and `audit/status/` becomes an audit area.**
   report-generator, owasp-asvs-mapper, production-readiness and technical-debt read both
   folders through audit-findings-rollup, so nothing but child findings and status may be
   written there. The rollup itself lives under `audit/evidence/audit-findings-rollup/`. The
   orchestrator writes **no** `audit/status/audit-application.json` (its own run state lives
   in `run-log.json`), infrastructure steps write no status file, and
   `audit/findings/audit-application.json` is written only when there is a real APP finding.
3. **The mapper mutates other skills' findings files.** It adds references and
   `extra.mapping`. Reconciled: it runs alone, after the rollup step and before the report.
   The rollup never edits originals. `summary.py` recomputes the rollup at read time, so its
   counts include the mapper's MAP findings and its verdict matches the report's.
4. **Missing status means "completed" to some consumers.** The mapper treats a skill without
   a status file as completed, which would let an unrun area look verified. The rollup, and so
   readiness, lists it under `no_status_file` instead. Reconciled: `init` writes `skipped` status files, with reason and
   `skip_kind`, for every skill the plan does not run. A real earlier result is never
   overwritten.
5. **The readiness checklist is listed first in phase 5** by the spec, but it aggregates all
   findings and statuses and reports missing siblings as "not run". Reconciled: it stays in
   phase 5 but runs in wave 3, after its siblings, as the spec already does for
   technical-debt in phase 4.
6. **SOC 2 reads GDPR's `gdpr-checks.json`.** It runs in wave 2 of phase 5.
7. **GDPR can write into another skill's evidence folder.** If
   `data-inventory.json` is missing, `gdpr_check.py` runs
   `../audit-privacy-data-flow-mapper/scripts/pii_scan.py` to create it. In `full` and
   `compliance-only` the mapper runs in discovery, so this never triggers. In a custom list
   without the mapper it does, and the orchestrator notes it in the run log. GDPR is marked
   not parallel-safe.
8. **Security-phase soft inputs.** Injection reads the endpoint inventory
   (`evidence/audit-endpoint-inventory/endpoints.json`, written in discovery before any reader); XSS reads the
   headers findings (CSP); client-auth reads headers, authz and XSS findings. The spec calls
   the phase independent, and it is: the children degrade gracefully. Waves 1-3 still order
   them so the optional inputs exist when the reader starts.
9. **Quality-phase hand-offs.** Business-logic hands check-then-act sites to concurrency and
   date rules to datetime; performance reads ORM, leak and frontend findings. They run in
   wave 2; technical-debt runs in wave 3.
10. **Children that skip themselves.** frontend-best-practices and frontend-memory-leak write
    `skipped` when no frontend is detected; infra writes `skipped` when there are no deployment
    artifacts. These child-written skips carry no `skipped_by` and are reused on resume. The
    orchestrator also pre-skips stack-n/a children (`skip_kind: n/a`) to save a run; those are
    re-evaluated on every resume.
11. **Limited access has no field in the shared status schema.** Reconciled: `complete
    --limited` adds a `limited_access` list and prefixes `reason` with `limited access:`.
    The report generator prints `status - reason` in its scope table, so the gap reaches the
    report unchanged.
12. **Extra status keys.** The report generator adds `scripts` and `exports`, and children may
    add `scripts`. `complete` and `fail` preserve unknown keys.
13. **Critical flows.** Business-logic picks "every flow the app has (usually 4-8)" and
    test-coverage asks for a list "to use verbatim". Reconciled: the orchestrator confirms 3-5
    at the discovery checkpoint, stores them through `run_state.py checkpoint --data` in
    `audit/evidence/audit-application/checkpoint-critical-flows.json`, and passes them in the
    invocation of business-logic, concurrency, datetime and test-coverage.
14. **The multi-tenant answer is not read by any child from `stack.json`.** The orchestrator
    uses it to plan and passes it in the invocation (async's severity rule and system-design's
    tenancy note depend on it).
15. **Endpoint inventory on resume.** The `endpoint-inventory` step carries `needed_by`. A
    re-run marks it not needed when every planned skill that reads it already has a result, so
    retrying an unrelated skill (for example secrets) never re-runs the inventory. When a reader
    is pending and the inventory has never finished, the inventory runs first. A workspace from
    before the step existed therefore resumes exactly as it did.
16. **Status shorthand.** Several children (async, ORM, leak, a11y, frontend skills, performance)
    document the status as `{"skill","status","reason","started_at","finished_at"}` key lists.
    It is the same schema; `complete` normalises missing values.
