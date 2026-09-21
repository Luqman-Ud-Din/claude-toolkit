---
name: audit-application
description: Runs a complete pre-production audit of an application by orchestrating the configured audit-* skills in six phases - setup (detect the stack once, ask whether the app is multi-tenant, pick a scope profile - full, security-only, pre-launch, compliance-only or custom), discovery, security, quality and correctness, readiness and compliance, reporting - with user checkpoints, per-skill status files, resume after failure, cross-skill de-duplication, OWASP/ASVS mapping, the final go/no-go report and a console summary. Use it whenever the user invokes /audit-application or asks to audit the whole app, run a full pre-production review, do a security and quality audit, run all the audit skills, prepare a launch or release readiness review, resume, retry or re-run an audit, dry-run the audit plan, or asks which audits to run before going live - even when the skill is not named.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit application (orchestrator)

This skill runs the whole audit family against one application and turns 30-odd
separate reviews into one honest deliverable. It decides what runs, in which order,
with which shared inputs, pauses at the points where only the user can decide, keeps
going when a child fails, and makes sure the final report says exactly what was and
was not assessed.

Division of labour, stated plainly: **the bundled scripts manage plan and state only.**
`plan.py` resolves the plan, `run_state.py` records starts, results, checkpoints and
timings, and `summary.py` reads results through `audit-findings-rollup`. **You invoke every
child skill and run every infrastructure step** yourself, through the Skill tool, subagents
or the atomic skills' scripts, as this file instructs. No script here calls a skill.

Three steps of the plan are infrastructure, not audit areas. `audit-stack-detection` writes
`audit/stack.json` at setup, `audit-endpoint-inventory` writes the shared endpoint list in
discovery, and `audit-findings-rollup` de-duplicates findings and decides the go/no-go in
reporting. They write no status file and no findings, get no row in the report, and are never
counted as skills run.

Read-only rule: the orchestrator never modifies the audited code, and neither may any
child it launches. Everything is written under `audit/` in the audited repo.

## Inputs and prerequisites

- The audited repo root (or two roots when backend and frontend live in separate repos;
  pass both to every child and name both in the report).
- Arguments from `/audit-application`: `--profile <name>`, `--skills a,b,c` (custom),
  `--skill <name>`, `--force`, `--dry-run`, `--non-interactive`, and the test hook
  `--simulate-failure <name>`.
- Python 3 (stdlib only). Child skills ship in this plugin (`audit-app`); the atomic scripts come from the `audit-core` plugin via `$AUDIT_CORE_ROOT`.
- Shared skills required from the `audit-core` plugin: `audit-stack-detection` (setup),
  `audit-endpoint-inventory` (discovery step), `audit-findings-rollup` (reporting step and
  `summary.py`), `audit-code-scan` (`plan.py` file walks) and `audit-finding-writer`
  (`findings.py` for APP findings). The children also use `audit-code-scan`,
  `audit-sensitive-data-catalog` and `audit-git-history`.
- The per-stack prerequisites in `references/<stack>.md` (SDKs installed, restore/build
  possible, DB access, test URL and accounts). Missing ones do not stop the run; they
  become "limited access" on the affected children.

## Workflow

### How to run one child (used in every phase)

1. `python scripts/run_state.py next --root <repo> [--wave]` returns the next pending item
   (`--wave` returns the whole parallel wave). Items are skills, infrastructure steps
   (`type: action`: `endpoint-inventory`, `dedupe`), or checkpoints. Never pick the order
   yourself; the plan encodes dependencies (`references/child-contracts.md`).
2. `python scripts/run_state.py start <skill> --root <repo>`.
3. Invoke the child. Sequential: Skill tool, skill `<name>` (when installed as a plugin the
   skill is namespaced: `audit-app:<name>`; the two reporting children from audit-core are
   `audit-core:audit-owasp-asvs-mapper` and `audit-core:audit-report-generator`), with args carrying the shared
   context: repo root(s); "audit/stack.json is authoritative, do not re-detect"; the
   multi-tenant answer; the confirmed critical flows (from
   `audit/evidence/audit-application/checkpoint-critical-flows.json`, written by
   `run_state.py checkpoint critical-flows --data ...`) for the children
   that use them; "orchestrated by audit-application: write audit/findings/<skill>.json,
   audit/reports/<skill>.md, audit/evidence/<skill>/, audit/status/<skill>.json; do not
   modify code; do not re-ask setup questions". Parallel: one subagent per wave member
   (Agent tool) whose prompt is "invoke the Skill tool with skill <name>" (same namespacing) plus the same
   context and "reply with the status and severity counts; do not run run_state.py".
   Only the main thread writes `audit/run-log.json`, so state never races.
4. Record the result:
   - Child finished (its status file says completed): `run_state.py complete <skill>`.
     If its `scope.not_checked` or status reason shows missing access (no test URL, no
     tokens, no DB connection, scanner not installed, build impossible), add
     `--limited "<what>: <why>"` once per gap. `complete` keeps a child-written
     `failed`/`skipped`, fills in a missing status file, and prints `contract_warnings`
     (no findings file, unparseable JSON, ids without the prefix).
   - Child errored, timed out, or produced nothing usable:
     `run_state.py fail <skill> --reason "<what happened>"`. **Then continue.** A failure
     never aborts the run; the report carries it.
   - The user asks to skip it: `run_state.py skip <skill> --reason "..." --kind user`.
   - `next` marked the item `simulate_failure`: do not invoke; call `fail` with reason
     `simulated failure (--simulate-failure <skill>)`.
5. Repeat until `next` returns a checkpoint or `{"type": "done"}`.

An infrastructure step (`type: action`; its `skill` field names the atomic skill) is not a
child audit. Run `run_state.py start <id>`, then the command named in its `text` from this
skill's directory, then `run_state.py complete <id>`, which warns when the expected output is
missing. If the script errors, use `run_state.py fail <id> --reason "..."` and continue. The
children that read its output record the gap themselves.

### Phase 1 - Setup

1. If `--dry-run`: run `python scripts/plan.py <repo> --profile <p> [--skills ...]
   [--multi-tenant yes|no] --dry-run` (add `--json` for the machine-readable plan), show
   the output, and stop. It writes nothing and, when a workspace exists, previews what a
   re-run would resume.
2. Detect the stack once with audit-stack-detection:
   `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Do not pass `--write`:
   `init` writes `audit/stack.json` together with the multi-tenant answer. Then run
   `python scripts/plan.py <repo> --json` for the tenancy hints (it uses the same detection
   in memory). Open only `references/<stack>.md` for each detected stack: it lists the
   children that are n/a for that stack and the prerequisites to confirm.
3. Ask whether the application is multi-tenant, showing the tenancy hints
   (`references/checkpoints.md`, checkpoint `multi-tenant`). The answer decides whether
   `audit-multi-tenant-isolation` runs.
4. Confirm the stack prerequisites in one message (SDK installed, restore/build possible,
   read-only DB access, test URL and two accounts or tenants). Note which are missing; they
   become `--limited` on the children that needed them.
5. Ask for the scope profile (checkpoint `scope-profile`):
   - `full` - every phase and skill;
   - `security-only` - the eight security skills;
   - `pre-launch` - authz, multi-tenant isolation, secrets, injection, XSS, business-logic,
     datetime, concurrency, performance, readiness, dependencies;
   - `compliance-only` - privacy mapper, GDPR, SOC 2, licensing;
   - `custom` - a list (`--skills authz,secrets,db-schema`).
   Reporting (findings rollup, OWASP/ASVS mapper, report generator) runs for every profile.
6. Initialise: `python scripts/run_state.py init --root <repo> --profile <p>
   --multi-tenant yes|no [--skills ...] [--force] [--non-interactive]`. This creates
   `audit/findings`, `audit/evidence`, `audit/status` (and `audit/reports`), writes
   `audit/stack.json` with `multi_tenant` (every child reads it instead of re-detecting),
   writes `audit/plan.json`, opens a run in `audit/run-log.json`, records both setup
   answers, and writes `skipped` status files, with the reason, for every skill the plan
   will not run (out-of-profile, not multi-tenant, n/a for the stack). Those files are what
   make the report's scope section honest.

### Phase 2 - Discovery

First run the `endpoint-inventory` step: `run_state.py start endpoint-inventory`,
`python "$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py" <repo>`, then
`run_state.py complete endpoint-inventory`. It writes `endpoints.json`, `endpoints.md` and
`endpoints.probe.json` under `audit/evidence/audit-endpoint-inventory/`. It runs before
`audit-api-contract` because the endpoint inventory now comes from here, not from that skill.
The plan includes the step only when api-contract, authz, multi-tenant isolation, ORM or
performance is planned. Tell those children, and injection, that the inventory exists and must
be read, not re-run.

Then run `audit-system-design` (architecture map), `audit-privacy-data-flow-mapper`,
`audit-api-contract` (contract review over the shared inventory) and `audit-db-schema`:
their outputs feed later skills (the data inventory for GDPR and SOC 2, the index list for
ORM review). They are independent of each other.

**Checkpoint `critical-flows`.** Propose candidates with
`python ../audit-business-logic/scripts/flow_inventory.py <repo> --out audit/evidence/audit-application/flow-candidates.json`
(a sibling's read-only script), then ask the user to confirm the 3-5 critical business
flows to trace. Record: `run_state.py checkpoint critical-flows --answer "<flows>" --mode interactive --data '{"flows": [...]}'`.
Pass the list to business-logic, concurrency, datetime and test-coverage.

### Phase 3 - Security

Run `audit-authz-and-access-control`, `audit-multi-tenant-isolation` (only when the app is
multi-tenant; the plan already skipped it otherwise), `audit-injection-vulnerabilities`,
`audit-secrets-and-config`, `audit-security-headers-and-middleware`,
`audit-frontend-xss-and-dom-safety`, `audit-client-auth-and-storage`,
`audit-dependency-vulnerabilities`. They are independent: run each wave in parallel with
subagents when the Agent tool is available, otherwise sequentially in plan order. Wave 2
(injection, XSS) and wave 3 (client auth) wait only because they optionally read wave 1's
authz, CSP and cookie findings.

**Checkpoint `security-gate`.** Show `python scripts/summary.py <repo> --critical-high --phase security`
and ask: continue, or stop and fix. Record the answer with `run_state.py checkpoint security-gate`.
On **stop**: `run_state.py defer --reason "user stopped at security checkpoint to fix findings"`
(remaining audit skills become `skipped`, deferred), run Phase 6 so the team has the report
of what ran, then `finish --outcome "stopped at security gate"`. Tell the user to re-run
`/audit-application --force` after fixing (or `--skill <name>` for the areas they fixed),
and that a plain re-run resumes the deferred skills.

### Phase 4 - Quality & correctness

Run `audit-async-and-dependency-injection`, `audit-orm-query-and-data-access`,
`audit-backend-resource-leak`, `audit-frontend-best-practices`, `audit-frontend-memory-leak`,
`audit-accessibility-and-i18n`, `audit-concurrency-and-race-condition`, `audit-business-logic`,
`audit-datetime-and-timezone`, `audit-performance-and-scalability`, then
`audit-technical-debt` last, because it consumes the others' findings. Business-logic
runs in wave 1 so its hand-offs reach concurrency and datetime (wave 2); performance is in
wave 2 because it reads the ORM, leak and frontend findings.

### Phase 5 - Readiness & compliance

Run `audit-production-readiness-checklist`, `audit-logging-and-observability`,
`audit-test-coverage-and-ci`, `audit-infra-and-deployment`, `audit-licensing-and-compliance`,
`audit-gdpr-data-protection`, `audit-soc2-controls-evidence`. SOC 2 waits for GDPR's
`gdpr-checks.json`; the readiness checklist runs last in the phase because its go/no-go
aggregates every findings and status file, and a sibling that has not run yet would be
reported as "not run".

### Phase 6 - Reporting

1. Roll up the findings (the `dedupe` step): `run_state.py start dedupe`,
   `python "$AUDIT_CORE_ROOT/skills/audit-findings-rollup/scripts/findings_rollup.py" rollup <repo> [--accepted <file>]`,
   `run_state.py complete dedupe`. It merges findings that share `root_cause_key` across
   skills, counts severities without false positives, lists failed, skipped, not-run and
   limited-access skills, and applies the go/no-go rule into
   `audit/evidence/audit-findings-rollup/rollup.json` and `rollup.md`. The rule was decided by
   the user: any open Critical or High is NO-GO, only Medium or Low is CONDITIONAL GO, otherwise
   GO. A finding covered by a valid risk acceptance is not open. Failed or skipped areas become
   caveats, never a different verdict word. Nothing is written to `audit/findings/` and no
   original is modified. Pass `--accepted` when the readiness review or the user supplied a
   risk-acceptance file.
2. Run `audit-owasp-asvs-mapper` (start / Skill / complete).
3. Run `audit-report-generator`. In its args, list the security areas that failed, were
   skipped or ran with limited access (from `summary.py --json`) so its executive summary
   calls them out, and pass the same risk-acceptance file, if any.
4. `python scripts/run_state.py finish --root <repo>` (timings, counts), then
   `python scripts/summary.py <repo>` and show the console summary.

### Failures, skips and limited access

- Every child ends with `audit/status/<skill>.json`:
  `{"skill","status":"completed|failed|skipped","reason","started_at","finished_at"}`.
  The orchestrator adds `skipped_by`/`skip_kind` to its own skips and `limited_access`
  (plus a reason starting `limited access:`) to completed-but-constrained runs.
- `audit-report-generator` prints each status and reason in its scope table and adds an
  "audit incomplete" caveat for failures, so skipped, failed and limited areas reach the
  report without hand-editing it.

### Resume, --force, --skill, --dry-run

- **Re-running** `/audit-application` is `run_state.py init --root <repo>` with no profile:
  it reuses `audit/plan.json` and `audit/stack.json`, then `next` resumes from the first
  incomplete item. Completed and child-skipped results are reused; failed skills and the
  orchestrator's own skips are retried; the reporting steps and any checkpoint whose phase
  changed are redone. The `endpoint-inventory` step is marked not needed when every skill
  that reads it already has a result, so retrying an unrelated skill does not re-run it. Earlier
  runs stay in `audit/run-log.json`.
- **--force** reuses nothing: `init --force` makes every planned item pending again.
- **--skill <name>** runs one child through the same workspace:
  `init --skill <name>`, start, invoke, complete/fail, finish. No checkpoints, no
  reporting; afterwards a plain re-run refreshes reporting because it is now stale.
  `audit-finding-writer` and the six atomic skills (`audit-stack-detection`, `audit-code-scan`,
  `audit-endpoint-inventory`, `audit-findings-rollup`, `audit-sensitive-data-catalog`,
  `audit-git-history`) are helpers or infrastructure, not audit areas, so they are refused.
- **--dry-run**: `plan.py --dry-run` only. Nothing is created.

### Checkpoints in non-interactive runs

The pauses are user checkpoints, not optional steps. When nobody can answer (headless
`claude -p`, CI, you are yourself a subagent, or `--non-interactive`), apply the default
from `references/checkpoints.md` and record it with `--mode auto-continued`. The run log
then shows exactly which decisions were made without the user; nothing is silently skipped.
Answers given upfront as arguments are recorded as `provided`.

### Not checked (state these in the summary)

- Children that failed, were deferred, were skipped as n/a or out-of-profile, or ran with
  limited access (the summary lists each with its reason).
- Cross-skill de-duplication only merges findings that set `root_cause_key`.
- The endpoint inventory reads routes from source text; runtime-built routes and gateway
  auth are not seen (`audit-endpoint-inventory` Limits).
- Checkpoints answered with `auto-continued` defaults instead of by the user.
- `--skill` runs do not refresh technical-debt or readiness aggregates; re-run those skills.

## Finding format (prefix APP)

The orchestrator writes findings only for defects in the audit process that the report
must carry and a re-run cannot fix, for example a child that keeps reporting completed but
writes no scope or unparseable findings. Use
`python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" init audit-application` then `add`. Same block as every audit
skill (`audit-finding-writer/references/findings-schema.md`):

```markdown
### [Low] APP-001 - audit-injection-vulnerabilities completed without writing findings or scope
- **Location:** `audit/findings/audit-injection-vulnerabilities.json` (missing)
- **Confidence:** confirmed
- **Evidence:**

```text
run_state.py complete audit-injection-vulnerabilities -> contract_warnings:
  no audit/findings/audit-injection-vulnerabilities.json written (runs #1 and #2)
```

- **Impact:** The report cannot show what the injection review covered, so readers may assume coverage that was never verified.
- **Remediation:** Re-run `/audit-application --skill audit-injection-vulnerabilities`; if it still writes nothing, record the area as not assessed in the report scope.
- **Reference:** ASVS-1.1.2
```

JSON fields: `id`, `title`, `severity`, `confidence`, `location`, `evidence`, `impact`,
`remediation`, `references`, `tags`, optional `root_cause_key`.

## Output template

Workspace (relative to the audited repo):

```text
audit/
  stack.json            detected once by audit-stack-detection; multi_tenant set at setup
  plan.json             resolved plan (profile, items, skip reasons)
  run-log.json          runs[] -> events (start/finish with duration_s, skip, checkpoint + mode), timings, counts
  findings/<skill>.json
  reports/<skill>.md
  evidence/<skill>/, evidence/audit-application/checkpoint-<id>.json
  evidence/audit-endpoint-inventory/endpoints.json, endpoints.md, endpoints.probe.json
  evidence/audit-findings-rollup/rollup.json, rollup.md
  status/<skill>.json   one per audit skill: completed | failed | skipped, with reason
  audit-report.md       from audit-report-generator
```

Console summary (`summary.py`):

```text
========================================================================
audit-application summary
Repo: <root>
Run #<n> (fresh | resumed | forced full re-run; profile <p>; multi-tenant yes|no); duration <t>; outcome <o>
Skills: <planned> planned | <run> run | <skipped> skipped | <failed> failed | <n> not run yet
  run this time: <n>; reused from earlier runs: <n>; ran with limited access: <n>
  FAILED   <skill> - <reason>
  LIMITED  <skill> - limited access: <gap>
  SKIPPED  <n> x out-of-profile | <skill> - <reason>
Findings by severity (after cross-skill de-duplication): Critical <n> | High <n> | Medium <n> | Low <n> | Info <n>
  raw <n>, merged <n> (<n> cross-skill groups), false positives excluded <n>[, risk-accepted <n>]
Timings: <phase> <t>; ...; slowest <skill> <t>, ...
Checkpoints: critical-flows = <answer> (interactive|provided|auto-continued); security-gate = <answer> (...)
Report: audit/audit-report.md
GO/NO-GO: <GO | CONDITIONAL GO | NO-GO> - <reason from audit-findings-rollup>
  caveat: <one line each: failed, skipped, not-run, limited-access areas, unreadable files, expired acceptances>
  note: audit/audit-report.md says <verdict> and is older than the newest skill result   (only when stale or different)
========================================================================
```

## Examples

**Input:** `/audit-application --dry-run --profile pre-launch` on a .NET + Angular repo,
user says it is multi-tenant.
**Output (excerpt):** `Phase 2 - Discovery (no skills from this phase in this plan) 6. [infrastructure: audit-endpoint-inventory] ... (used by audit-authz-and-access-control, audit-multi-tenant-isolation, audit-performance-and-scalability) 7. [checkpoint] critical-flows`;
`Phase 3 - Security wave 1: authz, multi-tenant-isolation, secrets, dependencies; wave 2: injection, XSS; 14. [checkpoint] security-gate`;
`Phase 4: business-logic; wave 2: concurrency, datetime, performance`; `Phase 5: production-readiness-checklist`;
`Phase 6: [infrastructure: audit-findings-rollup], owasp-asvs-mapper, report-generator`; `out-of-profile: 19 skills`. No files written.

**Input:** a pre-launch run where `audit-secrets-and-config` fails, then `/audit-application` again.
**Output:** run 1 continues past the failure; `audit/status/audit-secrets-and-config.json` is
`failed` with its reason; the report scope row reads `secrets and config | failed - ...` and the
verdict carries the caveat. Run 2: `run_state.py next` returns only `audit-secrets-and-config`
(the endpoint inventory is not needed, because authz, tenant isolation and performance are
reused); after it completes, the security gate is asked again and the reporting steps rerun; no
other child is invoked.

## Bundled files

- `scripts/plan.py` - resolves the ordered plan from `references/profiles.json` (profiles, phases, waves, infrastructure steps, multi-tenant condition, stack n/a rules); `--dry-run` text, `--json`, `--stable`. Loads `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` by file path and walks files with `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py`.
- `scripts/run_state.py` - init workspace (writes `audit/stack.json`), start/complete/fail/skip, checkpoints, defer, next (resume honouring `--force`/`--skill` and the inventory's `needed_by`), status, finish; timings into `audit/run-log.json`.
- `scripts/summary.py` - console summary and the `--critical-high` table for the security checkpoint; counts, skill states and the verdict from `$AUDIT_CORE_ROOT/skills/audit-findings-rollup/scripts/findings_rollup.py`.
- Atomic scripts run by the plan: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` (setup), `$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py` (discovery), `$AUDIT_CORE_ROOT/skills/audit-findings-rollup/scripts/findings_rollup.py rollup` (reporting); `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` for APP findings.
- `references/profiles.json` - phases, infrastructure steps, skill metadata (prefix, wave, applicability, condition), helper and infrastructure skills, checkpoints and profiles as data.
- `references/child-contracts.md` - one row per child (phase, inputs, outputs, prefix, parallel-safe, depends-on) and every path inconsistency with how it is reconciled.
- `references/checkpoints.md` - exact wording, options, defaults and recording commands for each pause.
- `references/<stack>.md` - per stack: children that are n/a, prerequisites to confirm at setup, wrong n/a calls to avoid (dotnet, java-spring, node-express, python-django, angular, react, vue); add a stack from `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `evals/` - sample repo, the expected pre-launch dry-run plan, and the end-of-run workspace after a simulated failure for the resume test.
