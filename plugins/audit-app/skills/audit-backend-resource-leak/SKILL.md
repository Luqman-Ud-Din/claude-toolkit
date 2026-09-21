---
name: audit-backend-resource-leak
description: Finds memory and resource leaks in backend code - undisposed connections, streams, HTTP responses and DB contexts, event handlers never unsubscribed, static or singleton collections that grow forever, in-memory caches with no size limit or expiration, timers and CancellationTokenSources created per request, large hot-path allocations without pooling, and background services or workers that accumulate state or swallow exceptions - then hands over a 15-minute load-test procedure (working set, GC gen2, handle count, pass/fail thresholds) to prove memory stays flat. Use whenever the user asks about memory leaks, resource leaks, disposal, IDisposable, unbounded caches, growing memory, OOM or out-of-memory, handle or socket exhaustion, "memory keeps climbing", background service or hosted service issues, worker stability, or backend stability, and as part of any general backend quality, performance, or pre-production audit even when the user does not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: backend resource leaks

A leak rarely shows up in a unit test. It shows up at 3 a.m. after twelve hours of
traffic, as a slow climb in working set, a rising gen2 count, or "too many open
files". This skill finds the code shapes that cause those climbs and gives the
team a repeatable 15-minute procedure to confirm or refute each one under load.

Read-only rule: never modify the audited code. Write only under `audit/`
(findings, reports, evidence, status).

## Inputs / prerequisites

- Path to the audited repository root (backend). Frontend leaks belong to
  `audit-frontend-memory-leak`; the frontend reference files here only say where
  the frontend side of the topic is.
- `audit/stack.json` if `audit-application` already wrote it; otherwise run
  `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`.
- Optional: a running instance (URL) and a load tool (k6, bombardier, wrk,
  JMeter) to execute the load-test recipe. Without one, ship the procedure and
  mark the confirmation step as not run.
- Python 3 (stdlib only) for the bundled scripts.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack), `audit-code-scan` (grep pass), `audit-finding-writer` (findings.json).

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>` (honours
   `audit/stack.json`). Open only `references/<stack>.md` for the primary backend
   stack; it lists the disposable types, the cache APIs, the background-worker base
   classes, and the false positives for that runtime. Unknown stack: use
   `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md` and say so in `scope.not_checked`.
2. **Automated pass.** Run the pattern file for the stack:
   `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-backend-resource-leak/hits.json --md audit/evidence/audit-backend-resource-leak/hits.md`.
   Every hit is a candidate. The pattern ids map to the seven leak classes in
   `references/leak-classes.md` (disposal, subscription, static growth, cache
   bounds, per-request timers/CTS, hot-path allocation, background worker). Then
   run `python scripts/leak_loadtest.py plan --stack <stack> --out audit/evidence/audit-backend-resource-leak/loadtest-plan.md`
   to generate the stack-specific recipe you will paste into the report.
3. **Manual trace of the highest-risk flows.** In this order, because the blast
   radius shrinks as you go down: (a) anything registered as a singleton or held in
   a `static` field - trace every write to it and ask what removes entries; (b)
   every background worker/hosted service loop - what state survives an iteration,
   what happens on exception; (c) disposables created in request paths - follow the
   object to the end of its scope and confirm `using`/`try-with-resources`/`with`/
   `finally close()`; (d) caches - find the size limit and expiration or prove the key
   space is bounded; (e) event/observable subscriptions on long-lived publishers.
   Use the checklist section of `references/<stack>.md`. Save the traced call
   chain as evidence (`audit/evidence/audit-backend-resource-leak/<id>-trace.md`).
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`:
   `python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" init audit-backend-resource-leak --root <repo>` once, then
   `python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" add audit/findings/audit-backend-resource-leak.json --from <finding.json>`
   per finding, and `python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" md ... --out audit/reports/audit-backend-resource-leak.md`.
   Severity follows `audit-finding-writer/references/severity-rubric.md`: unbounded
   growth in a singleton at production rate is Critical; a leak bounded by a
   restart schedule or a small key space is Medium.
5. **Produce the outputs** listed below: findings, the report with the 15-minute
   load-test procedure (metrics, thresholds, per-stack commands from
   `references/load-test-recipes.md`), and, if an environment was available, the
   measured results graded by `python scripts/leak_loadtest.py grade <samples.csv>`.
   Write `audit/status/audit-backend-resource-leak.json`
   (`{"skill","status":"completed|failed|skipped","reason","started_at","finished_at"}`).
6. **List what was not checked** - native/unmanaged handles you could not see, third-party
   SDK internals, workers whose config lives outside the repo, and the load test itself if
   it was not run. Put each item in `scope.not_checked` with a reason.
   Also list the automated pass's coverage limits from `audit-code-scan`: folders on the shared skip list (`node_modules`, `bin`, `obj`, `dist`, `build`, `.git`, `audit`, ... - see `$AUDIT_CORE_ROOT/skills/audit-code-scan/references/repo-walk-api.md`) and files over 2 MB are not read, and patterns match one line at a time.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `LEAK`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Reference:** CWE-nnn, ASVS-x.y.z, OWASP-A0n:2021 (use what applies; see references/<stack>.md)


Recurring references for this topic: CWE-401 (memory not released), CWE-404
(improper resource shutdown), CWE-772 (missing release of resource), CWE-770
(allocation without limits), CWE-400 (uncontrolled resource consumption),
CWE-390 (error condition without action), ASVS-12.1 / 13.x for service limits.

## Output template (`audit/reports/audit-backend-resource-leak.md`)

```markdown
## audit-backend-resource-leak findings
| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| n | n | n | n | n |

### Scope
- Stack: <backend stack>, roots: <paths>
- Automated pass: <N> hits across <M> patterns (audit/evidence/audit-backend-resource-leak/hits.md)
- Manually traced: <list of singletons / workers / request paths>

### Findings
<one block per finding, format above, ordered by severity>

### Leak class summary
| Class | Candidates | Confirmed | Likely | False positive |
|---|---|---|---|---|
| Disposal | | | | |
| Subscriptions | | | | |
| Static / singleton growth | | | | |
| Cache bounds | | | | |
| Per-request timers / CTS | | | | |
| Hot-path allocation | | | | |
| Background workers | | | | |

### 15-minute load-test procedure
Target: <URL>. Tool: <k6 | bombardier | wrk | JMeter> (commands in references/load-test-recipes.md).
1. Warm up 2 min at 20% of target RPS; discard these samples.
2. Steady state 15 min at target RPS against the endpoints named in the findings
   (or the top 5 by traffic). Sample every 15 s with the stack's counter tool.
3. Stop load, wait 60 s, force a GC (stack command), take the final sample.

| Metric | Source | Pass | Fail |
|---|---|---|---|
| Working set / RSS | dotnet-counters `Working Set`, jcmd `GC.heap_info`, `process.memoryUsage().rss`, `psutil`/`/proc` | slope over minutes 5-15 < 2 MB/min AND last-5-min mean within 10% of minutes 5-10 mean | slope >= 5 MB/min or monotonic rise across all 15 min |
| GC gen2 / old-gen collections | `Gen 2 GC Count`, `jstat -gc` FGC, `--trace-gc` mark-sweep, `gc.get_count()[2]` | rate stable; heap after gen2 returns to within 15% of warm-up baseline | heap-after-gen2 rises every collection |
| Handle / FD count | `dotnet-counters` handle count is not exposed: use `ls /proc/<pid>/fd \| wc -l` or `handle.exe`, `lsof -p`, `process.getActiveResourcesInfo()` | flat within +/-10% after warm-up | grows with request count |
| Thread count | `ThreadPool Thread Count`, `jstack \| grep -c tid`, `process._getActiveHandles()`, `threading.active_count()` | flat | grows with request count |
| Post-GC residual | final sample after forced GC | within 15% of warm-up baseline | above baseline by more than 15% |

Grade with `python scripts/leak_loadtest.py grade samples.csv --baseline-minutes 5`.

### Load-test results
| Run | Endpoint set | RPS | Working set slope | Gen2 growth | Handles | Verdict |
|---|---|---|---|---|---|---|
| (not run - no environment) | | | | | | |

### Not checked
- <item> - <reason>
```

## Examples

**Input (grep hit, .NET):**
`Services/ReportService.cs:31: var stream = new FileStream(path, FileMode.Open);`
- opened, read, returned as a byte array, never disposed, no `using`.

**Output:**
```markdown
### [High] LEAK-002 - Report file stream opened without disposal on every export
- **Location:** `Services/ReportService.cs:31` (Export)
- **Confidence:** confirmed
- **Evidence:**

```csharp
var stream = new FileStream(path, FileMode.Open);   // no using; method returns before Dispose
return ReadAll(stream);
```

- **Impact:** Each export pins a file handle until the finalizer runs; under a burst of exports the process hits the OS handle limit and every file operation in the service fails until restart.
- **Remediation:** `using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 4096, useAsync: true);` or `await using` with an async reader; add a handle-count check to the 15-minute load test.
- **Reference:** CWE-772, CWE-404
```

**Input (reviewer note, Node):** "the metrics module pushes every request into a
module-level array and nothing ever splices it."

**Output:** `[Critical] LEAK-001 - Module-level request log array grows for the
life of the process` with remediation to cap it (ring buffer, `lru-cache` with
`max`, or ship to the metrics backend and drop), CWE-401 / CWE-770.

## Bundled files

- `references/<stack>.md` - disposable types, cache APIs, worker base classes, false positives, tooling per stack (dotnet, java-spring, node-express, python-django; angular, react, vue point to the frontend sibling). To add a stack, follow `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `references/leak-classes.md` - the seven leak classes, what proves each one, severity guidance.
- `references/load-test-recipes.md` - k6, bombardier, wrk, JMeter commands; dotnet-counters, jcmd/jstat, node --inspect/--trace-gc, tracemalloc sampling; thresholds.
- `scripts/patterns/<stack>.json` - pattern lists for the automated pass (format: `$AUDIT_CORE_ROOT/skills/audit-code-scan/references/pattern-file-format.md`).
- `scripts/leak_loadtest.py` - `plan` prints the stack recipe; `grade` scores a samples CSV against the thresholds.
- `evals/` - prompts and a fixture repo planting an undisposed stream, a growing static list, an unbounded MemoryCache, and a worker with an empty catch.

Atomic scripts this skill calls (installed next to it, not bundled):

- `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` - stack detection (honours `audit/stack.json`).
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` - pattern-driven automated pass.
- `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` - init / add / md / validate for findings.json.
