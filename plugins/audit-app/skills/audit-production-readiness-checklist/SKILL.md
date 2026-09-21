---
name: audit-production-readiness-checklist
description: Runs a go/no-go production readiness review - environment-specific config separated, debug off, health checks that verify dependencies, graceful shutdown, timeouts and retries on external calls, caching strategy, load-test results, feature flags for risky changes, runbook, on-call and alerting, tested rollback, and a launch checklist with owners - and aggregates every other audit skill's findings.json into a blocker list. Use it whenever the user asks "is this ready for production", "can we ship", "are we safe to deploy", go-live or launch checklist, launch readiness, release review, release sign-off, pre-production sign-off, deployment readiness, operational readiness, or wants a final Go/No-Go summary after other audits - even when they do not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: production readiness checklist

The last gate before go-live. It answers one question - **Go or No-Go** - with
a checklist a release manager can sign, a list of blockers with owners, and a
roll-up of every Critical/High finding the other audit skills produced. It
does not re-audit what sibling skills own; it checks the operational basics
they do not cover and aggregates the rest.

Read-only rule: never modify the audited code or config. Write only under `audit/`.

## Inputs and prerequisites

- Repository root(s) (backend and frontend if separate; the checklist covers both).
- `audit/findings/*.json` and `audit/status/*.json` from sibling skills, if
  any have run. Missing files are reported as "not run", never assumed clean.
- Deployment descriptors and docs if present: `Dockerfile`, `docker-compose*`,
  `k8s/`, `helm/`, CI workflows, `README`, `docs/`, runbooks, load-test folders.
- Optional from the user: the launch date, the owner list, which environment
  is "production", and any evidence that lives outside the repo (dashboards,
  alert screenshots, load-test reports). Ask once; if not supplied, the item
  stays `unknown` and the report says what evidence would flip it.
- Optional risk-acceptance file for Highs the product owner accepted in writing: a JSON list
  of `{"id", "accepted_by", "date", "reason"}` plus optional `"expires"` (format and rules in
  `references/go-no-go-rules.md`). There is no default location; pass it with `--accepted`.
- `audit/stack.json` or `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`. Python 3 stdlib only.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack), `audit-code-scan`
  (grep pass and the shared file walker), `audit-sensitive-data-catalog` (secret values in the
  probe), `audit-findings-rollup` (aggregation and the Go / No-Go verdict), `audit-finding-writer`
  (`findings.py`).

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`; open only
   `references/<stack>.md` for each detected backend/frontend. It tells you
   where health checks, shutdown hooks, environment config and debug switches
   live in that stack and what "pass" looks like.
2. **Automated pass** (outputs under `audit/evidence/audit-production-readiness-checklist/`):
   - `python scripts/readiness_probe.py <repo> --out readiness.json --md readiness.md`
     evaluates every checklist item it can from files: env-specific config,
     hard-coded production secrets/connection strings, debug flags, health
     endpoints and whether they verify dependencies, graceful shutdown,
     timeouts/retries on outbound clients, caching, load-test artifacts,
     feature flags, runbook, alerting config, rollback procedure, launch
     checklist. Each item gets `pass | fail | unknown` with evidence. Its
     `provisional_recommendation` only previews the verdict rule on the READY- findings the
     failed items would become; it is not the verdict.
   - `python scripts/aggregate_findings.py <repo> --readiness readiness.json [--accepted accepted.json] --as-of <YYYY-MM-DD> --out summary.json --md summary.md`
     reads `audit/findings/*.json` + `audit/status/*.json` through `audit-findings-rollup`
     and builds the severity summary per skill, the Critical/High list, the blocker list and
     the Go/No-Go with its caveats (`references/go-no-go-rules.md`). The same verdict, with the
     full rolled-up view, comes from
     `python "$AUDIT_CORE_ROOT/skills/audit-findings-rollup/scripts/findings_rollup.py" rollup <repo> --accepted accepted.json --expected "<comma-joined EXPECTED_SKILLS>" --as-of <YYYY-MM-DD>`
     (writes `audit/evidence/audit-findings-rollup/rollup.json` and `rollup.md`).
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out hits.json`
     for stack-specific readiness smells (developer exception pages, `DEBUG =
     True`, `synchronize: true`, `ddl-auto: update`, `NODE_ENV=development` in
     a Dockerfile, `localhost` in production config, disabled TLS validation).
   All hits are candidates; open the file and confirm before rating.
3. **Manual trace of the highest-risk items** (in this order):
   1. Production configuration end to end: which file/env var wins in the
      production container, does it contain literals that belong in a secret
      store, is the environment name set correctly in the Dockerfile/compose/CI.
   2. Health endpoint: call path from the orchestrator probe to the code; does
      it hit the DB/broker/cache or just return 200; is it excluded from auth.
   3. Shutdown: what happens to in-flight requests and background jobs on
      SIGTERM; is the drain timeout shorter than the orchestrator's grace period.
   4. Every outbound dependency (DB, broker, cache, third-party API): timeout,
      retry, fallback - one table.
   5. Rollback: read the procedure; check the last migration is reversible
      (`audit-db-schema` evidence if present); ask when it was last exercised.
   6. On-call: is there a rota, an alert route, and a runbook that names the
      single points of failure (`audit-system-design` evidence if present).
   7. Walk the aggregated Critical/High list: for each, confirm it is open,
      assign it a blocker/accepted-risk status, name the owner.
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (prefix `READY-`). One finding
   per failed checklist item (not per file). Failed checklist items reach the verdict only
   through these findings, so never skip one. Sibling skills' findings are
   **referenced** in the blocker list by their own ids, never duplicated.
   Severity for readiness items (rubric: `$AUDIT_CORE_ROOT/skills/audit-finding-writer/references/severity-rubric.md`):
   hard-coded production secret = Critical; no health checks, debug on in
   production, no rollback procedure = High; missing runbook/alerting/load test
   = High for customer-facing launches, Medium for internal tools; missing
   feature flags, caching strategy, launch checklist = Medium/Low.
5. **Produce the outputs** at the fixed paths:
   - `audit/findings/audit-production-readiness-checklist.json`
   - `audit/reports/audit-production-readiness-checklist.md` (template below)
   - `audit/evidence/audit-production-readiness-checklist/` (probe, summary, hits)
   - `audit/status/audit-production-readiness-checklist.json`:
     the status record defined in `audit-core:audit-finding-writer` (references/run-status.md)
6. **List what was not checked** and why: evidence that lives outside the repo
   (alert routing, dashboards, DR drills, load-test reports, on-call rota),
   sibling skills that did not run (name each), environments you could not see.

## Go / No-Go decision

The verdict is decided by `audit-findings-rollup`, the one rule every audit skill shares
(`references/go-no-go-rules.md`); `aggregate_findings.py` prints it. Then write one paragraph
of judgement. In short:

- any open **Critical or High** finding from any skill (including READY-) = **NO-GO**;
- only Medium or Low findings open = **CONDITIONAL GO**, with each condition's owner and date;
- nothing above Info open = **GO**.

"Open" excludes false positives and findings covered by a valid risk-acceptance record
(`id`, `accepted_by`, `date`, `reason`, and no `expires` in the past). Sibling skills that
failed, were skipped, did not run or ran with limited access are listed as **caveats**
directly under the recommendation line; they never change the word, and a GO with caveats is
not a sign-off for the areas named. Before writing an acceptance record for a regulated-data
High (`GDPR`, `PII`, `SEC`, `TENANT` on payments, health or identity data), confirm the DPO or
security owner is the acceptor.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `READY`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Location:** `path/to/file.ext:LINE` (or `.` for repo-wide)
- **Evidence:**

```lang
<the config lines, probe output, or the absence proven by the search performed>
```

- **Impact:** What happens on launch day or during the first incident: who is paged, what cannot be diagnosed, what cannot be undone.
- **Remediation:** The concrete change in this stack, and who typically owns it (dev, ops, product).
- **Reference:** CWE-nnn / ASVS-x.y.z where it is a security gap (CWE-798 for committed secrets, CWE-489 for debug enabled); otherwise tags: ["readiness"]


## Output template (`audit/reports/audit-production-readiness-checklist.md`)

```markdown
## audit-production-readiness-checklist

# Recommendation: NO-GO | CONDITIONAL GO | GO

Caveats: Failed: ... / Not run: ... / Skipped: ... / Limited access: ... (from the rollup; omit when none)

One paragraph: the two or three things that decide it.

### Blocking issues
| # | Id | Source skill | Severity | Title | Location | Owner | Status |
|---|---|---|---|---|---|---|---|
| 1 | READY-001 | this | Critical | Production connection string with password committed | `appsettings.Production.json:4` | (unassigned) | open |
| 2 | SEC-003 | audit-secrets-and-config | Critical | ... | ... | | open |

### Readiness checklist
| Item | Status | Evidence | What would make it pass |
|---|---|---|---|
| Environment-specific configuration separated | pass | `appsettings.Production.json`, env vars in compose | |
| Debug/developer features off in production | fail | `Program.cs:14 app.UseDeveloperExceptionPage()` unguarded | wrap in `if (app.Environment.IsDevelopment())` |
| Health checks verify dependencies | fail | no `AddHealthChecks` in any Program.cs | `AddHealthChecks().AddSqlServer(...).AddRabbitMQ(...)`, `MapHealthChecks("/health/ready")` |
| Graceful shutdown | unknown | ... | |
| Timeouts and retries on all external calls | ... | | |
| Caching strategy defined | ... | | |
| Load test results available | ... | | |
| Feature flags for risky changes | ... | | |
| Runbook documented | ... | | |
| On-call and alerting in place | ... | | |
| Rollback procedure tested | ... | | |
| Launch checklist with owners | ... | | |

### Findings from other audit skills (Critical / High)
| Skill | Status | Critical | High | Medium | Low | Info | Critical/High ids |
|---|---|---|---|---|---|---|---|
| audit-secrets-and-config | completed | 1 | 2 | ... | | | SEC-001, SEC-003, SEC-004 |
| audit-db-schema | not run | - | - | - | - | - | |

### Findings
(READY- blocks, highest severity first)

### Conditions (CONDITIONAL GO: every open Medium/Low with an owner and date)
1. ...

### Not checked
- item - reason (e.g. alert routing lives in PagerDuty, not in the repo)
```

## Examples

**Input (readiness_probe.py):** `HARDCODED_PROD_SECRET: appsettings.Production.json:4  "Default": "Server=prod-sql.internal;Database=Ledger;User Id=sa;Password=P@ss..."`

**Output:**
```markdown
### [Critical] READY-001 - Production database credentials committed in appsettings.Production.json
- **Location:** `Ledger.Api/appsettings.Production.json:4` (ConnectionStrings.Default)
- **Confidence:** confirmed
- **Evidence:**

```json
"Default": "Server=prod-sql.internal;Database=Ledger;User Id=sa;Password=P@ss..."
```

- **Impact:** Everyone with repository access, and every CI log that prints config, holds the production `sa` password; a leak means full read/write of all customer data. Blocks launch until rotated.
- **Remediation:** Remove the literal, supply `ConnectionStrings__Default` from the host secret store (Key Vault / environment), rotate the password now, purge the value from git history, and add a CI secret scan. Owner: ops + dev lead.
- **Reference:** CWE-798, ASVS-2.10.4, OWASP-A02:2021
```

**Input (probe):** `HEALTH_CHECKS: fail - no AddHealthChecks/MapHealthChecks found; compose has no healthcheck`

**Output:** `[High] READY-002 - No health endpoint; orchestrator cannot detect a dead or DB-less instance` -
remediation: `builder.Services.AddHealthChecks().AddSqlServer(cs).AddRabbitMQ(...)`,
`app.MapHealthChecks("/health/live")` + `/health/ready` with dependency checks, compose/k8s probes pointing at them.

## Bundled files

- `references/<stack>.md` - where each checklist item lives per stack, pass criteria, false positives, tooling (`dotnet`, `java-spring`, `node-express`, `python-django`, `angular`, `react`, `vue`); add one from `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `references/readiness-checklist.md` - the full checklist template with pass/fail/unknown criteria, evidence to collect, and default owners.
- `references/go-no-go-rules.md` - the decision rules and the accepted-risk record format.
- `scripts/readiness_probe.py` - file-based evaluation of the checklist items (walks files with `audit-code-scan`'s `repo_walk`, recognises secret values with `audit-sensitive-data-catalog`).
- `scripts/aggregate_findings.py` - roll-up of `audit/findings/*.json` and `audit/status/*.json` through `audit-findings-rollup` into severity summary, blocker list, verdict and caveats.
- `scripts/patterns/<stack>.json` - readiness smells, run with `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- Atomic scripts called: `$AUDIT_CORE_ROOT/skills/audit-findings-rollup/scripts/findings_rollup.py`, `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` (and `repo_walk.py`), `$AUDIT_CORE_ROOT/skills/audit-sensitive-data-catalog/scripts/catalog.py`, `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`, `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`.
- `evals/` - sample project with no health checks and a hard-coded production connection string (plus a sibling findings file to aggregate); `evals.json` expects a No-Go.
