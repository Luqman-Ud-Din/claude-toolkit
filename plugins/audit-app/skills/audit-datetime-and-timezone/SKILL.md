---
name: audit-datetime-and-timezone
description: Finds date, time, timezone and DST bugs across backend, frontend, database and infrastructure - timestamps not stored as UTC or offset-aware types, local-time calls (DateTime.Now, LocalDateTime.now, new Date, datetime.now) where UTC was meant, naive zone-less datetimes, date-only values stored as midnight timestamps, conversion scattered through business logic, user timezone guessed not stored, non-ISO 8601 strings in APIs, "today" and end-of-day cutoffs in the wrong zone, DST hazards in schedules and duration math, cron jobs without a zone, naive/aware comparisons, sorting on formatted strings, server or DB zones not UTC, tests on real time, and displays without a zone label. Use it whenever the user asks about timezones, DST, dates, timestamps, UTC, datetime handling, scheduling correctness, cron, expiry, deadlines, "today" logic, or reviews billing, deadline, subscription or reporting flows - even when the user does not name this skill. Also run it as part of a general pre-production or application audit.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit datetime and timezone

Date bugs are silent: the code compiles, the tests pass in the developer's
zone, and a month later an invoice is dated yesterday, a trial ends an hour
early, or a report double-counts the DST hour. This skill finds them by
mapping every date field the system stores, every place it is converted, and
every decision that depends on one, then checking each against one rule:
store and compute in UTC (or offset-aware types), convert only at the edges,
and make every zone assumption explicit.

Read-only rule: never modify the audited code. Write only under `audit/`.

## Inputs and prerequisites

- Path to the audited repository (backend and frontend may be separate roots).
- `audit/stack.json` if `audit-application` already ran; otherwise this skill runs `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`.
- Access to the schema (EF/JPA entity classes, migrations, SQL scripts, Prisma/Sequelize models) and to infra files (Dockerfiles, compose, k8s CronJobs, crontabs, CI config) if they are in the repo.
- Optional: what zones the users are in and where the servers run. If unknown, assume users span multiple zones and servers run in UTC, and record the assumption.
- Python 3 for the bundled scripts.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack detection), `audit-code-scan` (grep pass, and the shared `repo_walk.py` walker the bundled scripts import) and `audit-finding-writer` (`$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`). A missing one stops the scripts with an error naming it.

## Coordination with sibling skills

- `audit-business-logic` hands you the date-driven decisions it finds (cutoffs, expiry, billing periods); you own whether the zone and boundary are right, it owns whether the rule itself is right.
- `audit-concurrency-and-race-condition` owns overlapping/duplicate job runs; you own whether the job fires at the intended wall-clock time across DST and whether its window math is correct. Hand overlap questions to it.
- `audit-db-schema` owns column types in general; you still record the type of every date column in the field map because the zone convention is your topic.

## Workflow

1. **Resolve the stack.** Run `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Open only the matching `references/<stack>.md` for the backend and for the frontend. Always also read `references/infra-and-db.md` for cron, container, and column-type checks (they are stack-independent). Unknown stack: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
2. **Automated pass.** Run
   `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<backend>.json --patterns scripts/patterns/<frontend>.json --patterns scripts/patterns/infra.json --out audit/evidence/audit-datetime-and-timezone/hits.json --md audit/evidence/audit-datetime-and-timezone/hits.md`.
   The patterns cover local-time APIs, naive constructors, non-ISO format strings, cron expressions without a zone, real time in tests, string-sorted dates, and timestamp columns without zone. Then run
   `python scripts/date_field_map.py <repo> --out audit/evidence/audit-datetime-and-timezone/date-fields.json --md audit/evidence/audit-datetime-and-timezone/date-fields.md` to seed the date-field map from entity/model/migration files. Hits are pointers, not findings.
3. **Manual trace.** Do these three things by hand, in this order:
   - **Complete the date-field map.** For each field the script found (and any it missed), record storage type, whether it is UTC / offset-aware / local / naive / date-only, and where it is converted (API edge, UI, nowhere). A date-only concept (birth date, due date, invoice date) stored as a midnight timestamp is a finding; a timestamp stored in a zone-less column with no documented convention is a finding.
   - **Trace the date-driven decision flows** with `references/decision-flows.md`: "today" and day-boundary logic, cutoffs and expiry, billing periods and proration, scheduling and cron, durations and SLAs, reports grouped by day/month, sorting and comparisons. For each: what zone does the code assume, what zone does the user expect, and what happens at 23:30 on a DST-change day. Record verified / violated / not traceable with file:line.
   - **Check the environment**: server/container `TZ`, DB session zone (`timezone` in PostgreSQL, MySQL `time_zone`, SQL Server `datetimeoffset` usage), JVM `-Duser.timezone`, Node `process.env.TZ`, and whether tests pin the clock.
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (block below, prefix `TIME`). Rate with `audit-finding-writer/references/severity-rubric.md`: a wrong-zone decision that moves money or entitlements is Medium or higher; a display-only ambiguity is Low.
5. **Produce the outputs.**
   - `audit/findings/audit-datetime-and-timezone.json` (`$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py init` then `add`; `md` renders the findings section).
   - `audit/reports/audit-datetime-and-timezone.md` in the template below: date-field map, decision flows traced, environment table, findings, not checked.
   - `audit/evidence/audit-datetime-and-timezone/` with `hits.json`, `date-fields.json`, and any command output (for example `SELECT current_setting('TimeZone')` if the user ran it).
   - `audit/status/audit-datetime-and-timezone.json`: the status record defined in `audit-core:audit-finding-writer` (references/run-status.md).
6. **List what was not checked.** Production server/DB zone settings you could not read, third-party callbacks whose timestamp format is undocumented, generated code, and flows handed to siblings. Put them in `scope.not_checked` and in the report. Also list what the automated pass did not read: folders skipped by the shared walker (`repo_walk.SKIP_DIRS` in `audit-code-scan`: `.git`, `node_modules`, `bin`, `obj`, `dist`, `build`, `target`, `coverage`, `.angular`, `.next`, the `audit` workspace and similar) and files over 2 MB.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `TIME`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Impact:** Plain language: which users, in which zones, on which days get a wrong result, and what it costs them.
- **Remediation:** The concrete fix in this stack (UTC/offset type, explicit zone, edge conversion, pinned clock), with a short example.
- **Reference:** CWE-682 (incorrect calculation), CWE-704 (incorrect type conversion), CWE-20, CWE-367 (time-of-check) where they fit; otherwise cite ISO 8601 / RFC 3339 / IANA tz and add tag "no-standard".


## Output template (`audit/reports/audit-datetime-and-timezone.md`)

```markdown
# Datetime and timezone audit

Target: <repo> @ <commit> | Stack: <backend>/<frontend> | Date: <ISO date>
Assumptions: users in <zones>; servers expected in UTC.

## Summary
| Severity | Count |
|---|---|
| Critical | n | ...

## Date-field map
| Entity.Field | Storage type | Zone convention | Date-only? | Converted at | Notes / finding |
|---|---|---|---|---|---|
| Order.CreatedUtc | datetime2 | UTC (by name) | no | API: ISO with Z | ok |
| Invoice.DueDate | datetime | unknown (local midnight) | yes | never | TIME-002 |
| Subscription.TrialEndsAt | timestamp without time zone | server local | no | UI: formatDate local | TIME-001 |

## Date-driven decision flows traced
| Flow | Decision | Zone assumed | Zone expected | DST-safe? | Status | Location |
|---|---|---|---|---|---|---|
| Daily sales report | rows where CreatedUtc in [today 00:00, 24:00) | server local | branch local | no | violated | ReportService.cs:52 |
| Trial expiry job | TrialEndsAt < now | UTC | UTC | yes | verified | TrialJob.cs:20 |

## Environment
| Setting | Value found | Where | Ok? |
|---|---|---|---|
| Container TZ | not set (UTC default) | Dockerfile | yes |
| Cron zone | none on "0 2 * * *" | k8s/cronjob.yaml:12 | TIME-004 |
| DB column default | timestamp without time zone | migrations/001.sql | TIME-003 |

## Findings
<finding blocks>

## Handed off
| To | Item | Location |

## Not checked
- <item>: <reason>
```

## Examples

**Input:** `ReportService.cs:52` computes `var start = DateTime.Today; var end = start.AddDays(1);` and filters `o.CreatedUtc >= start && o.CreatedUtc < end`.

**Output:**
```markdown
### [Medium] TIME-001 - Daily report uses server-local "today" against UTC timestamps
- **Location:** `Reports/ReportService.cs:52` (GetDailySales)
- **Confidence:** confirmed
- **Evidence:**

```csharp
var start = DateTime.Today;               // Kind=Local, server zone
var end = start.AddDays(1);
.Where(o => o.CreatedUtc >= start && o.CreatedUtc < end)
```

- **Impact:** For a branch five hours ahead of the server, sales made between 19:00 and midnight local time land in the next day's report; daily totals never reconcile with the till. On DST-change days the window is 23 or 25 hours.
- **Remediation:** Take the branch zone from the stored branch record: `var tz = TimeZoneInfo.FindSystemTimeZoneById(branch.IanaZone); var startUtc = TimeZoneInfo.ConvertTimeToUtc(localDate.ToDateTime(TimeOnly.MinValue), tz);` and compare UTC to UTC. Use `TimeProvider` so tests can pin the clock.
- **Reference:** CWE-682; ISO 8601; IANA tz
```

**Input:** `k8s/cronjob.yaml` has `schedule: "0 2 * * *"` and no `timeZone:` field, and the job sends "end of day" statements.

**Output:** `[Low] TIME-004 - Statement cron runs at 02:00 in the cluster zone with no explicit timeZone` with remediation `spec.timeZone: "Asia/Karachi"` (k8s >= 1.27) or an explicit conversion in the job, tags `["no-standard"]`.

## Bundled files

- `references/decision-flows.md` - the date-driven decision flows to trace and the questions to ask of each (today, cutoff, expiry, billing period, DST, duration, reporting, sorting).
- `references/infra-and-db.md` - stack-independent checks: cron zones (crontab, k8s, Hangfire, Quartz, node-cron, Celery beat), container/JVM/Node/DB zone settings, column types per database, ISO 8601 / RFC 3339 rules.
- `references/<stack>.md` - local-time APIs, naive types, format strings, test-clock idioms, false positives per stack (dotnet, java-spring, node-express, python-django, angular, react, vue); add one from `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` - stack detection (honours `audit/stack.json`; atomic skill).
- `scripts/patterns/<stack>.json`, `patterns/infra.json` - automated pass run by `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- `scripts/date_field_map.py` - seeds the date-field map from entities, models, migrations and SQL. Walks files with `audit-code-scan`'s `repo_walk.py`.
- `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` - init / add / validate / md / summary for findings.json (atomic skill).
- `evals/` - sample repo with a local-time cutoff, a zone-less timestamp column, a cron without a zone, and a frontend parsing a date string without offset, plus correct negatives.
