---
name: audit-async-and-dependency-injection
description: Detects async misuse and dependency-injection mistakes that cause deadlocks, thread-pool starvation, lost errors and captive dependencies - sync blocking on async work (.Result, .Wait(), GetAwaiter().GetResult(), .block(), Future.get), async void or unawaited handlers whose exceptions vanish, missing CancellationToken or AbortSignal propagation, fire-and-forget tasks with no error handling, HttpClient or HTTP sessions created per request, outbound calls with no timeout, and DI lifetime mismatches (singleton holding scoped or transient, NestJS scope bubbling, Spring singletons injecting request or prototype beans). Use whenever the user asks about async problems, await, deadlocks, hangs, thread starvation, "requests pile up", unobserved exceptions, HttpClient usage, socket exhaustion, dependency injection, service lifetimes, AddSingleton/AddScoped/AddTransient, @Scope, captive dependencies, DbContext shared across requests, or a backend code-quality review, even if the skill is not named.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: async usage and dependency injection

The two failure modes this skill hunts share a symptom - the service "just
hangs" or "goes weird after a while" - and a cause that is invisible at low
load: a thread blocked on a task, a singleton quietly holding one request's
`DbContext` for every request that follows, a background task whose exception
nobody observed. Reading the registrations and the async call shapes finds
them before the load does.

Read-only rule: never modify the audited code. Write only under `audit/`
(findings, reports, evidence, status).

## Inputs / prerequisites

- Path to the backend repository root (frontend DI is Angular's own topic; the
  frontend reference files say where it overlaps and hand off).
- `audit/stack.json` if `audit-application` wrote it; otherwise `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`.
- Python 3 (stdlib only) for the bundled scripts.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack), `audit-code-scan` (grep pass and the shared file walker `di_lifetimes.py` imports), `audit-finding-writer` (findings.json).
- Optional: a running instance to confirm starvation (thread-pool queue length)
  with the tooling in `references/<stack>.md`.

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Open only
   `references/<stack>.md`. It names the container (MS.DI, Spring, NestJS,
   Django = no container), the lifetime vocabulary, the blocking APIs, the
   cancellation and timeout idioms, and the false positives. Unknown stack:
   `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`, and say so in `scope.not_checked`.
2. **Automated pass.** Two scripts:
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-async-and-dependency-injection/hits.json --md .../hits.md`
     - classes BLOCK (sync-over-async), VOID (async void / unawaited), CANCEL
     (missing token), FIRE (fire-and-forget), HTTP (client per request), TIMEOUT,
     DI (registration smells). See `references/async-antipatterns.md`.
   - `python scripts/di_lifetimes.py <repo> --stack <stack> --out audit/evidence/audit-async-and-dependency-injection/di.json --md .../di.md`
     - parses registrations (`AddSingleton/AddScoped/AddTransient/AddDbContext/AddHostedService`;
     `@Component/@Service/@Bean/@Scope`; Nest `@Injectable({ scope })`), resolves
     each service's constructor parameters to their lifetimes, and flags captive
     dependencies (longer-lived consumer holding a shorter-lived dependency). For
     Django it prints why lifetimes do not apply and what to check instead.
3. **Manual trace of the highest-risk flows.** (a) Every `MISMATCH` row in the
   DI table: open the consumer, confirm the dependency is stored in a field
   (captive) rather than resolved per call via a factory/`IServiceScopeFactory`/
   `ObjectProvider`/`ModuleRef`; a captive `DbContext` in a multi-tenant app also
   serves the wrong tenant - hand that to `audit-multi-tenant-isolation`.
   (b) Every BLOCK hit on a request path or inside a lock: which thread waits, and
   could the continuation need that thread (ASP.NET Core has no sync context, but
   starvation still happens under load; legacy ASP.NET/WPF/WebFlux deadlock
   outright). (c) Every VOID/FIRE hit: where does the exception go? Is the work
   lost on restart? (d) Every HTTP hit: who disposes the client, is there a
   timeout, is DNS rotation honoured (long-lived `HttpClient` without
   `PooledConnectionLifetime`)? (e) CancellationToken: does the controller's token
   reach the DB/HTTP call, and does the background loop honour `stoppingToken`?
   Save traces as `audit/evidence/audit-async-and-dependency-injection/<id>-trace.md`.
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (`init`, `add`, `md`). Severity
   per `audit-finding-writer/references/severity-rubric.md`: a singleton holding
   a scoped `DbContext` is High (Critical when multi-tenant); `.Result` in a hot
   request path is High; `async void` in a handler that moves money is High;
   `new HttpClient()` per request is Medium (High when the endpoint is hot);
   missing CancellationToken on a long query is Low-Medium.
5. **Produce the outputs**: findings, the report with the DI registration table
   (service, lifetime, dependencies with their lifetimes, mismatch flag) from
   `di.md`, and `audit/status/audit-async-and-dependency-injection.json`
   (`{"skill","status":"completed|failed|skipped","reason","started_at","finished_at"}`).
6. **List what was not checked**: registrations built by reflection/assembly
   scanning (`Scrutor`, `@ComponentScan` with custom filters) the parser cannot
   see, factory lambdas whose captured services it cannot type, third-party
   libraries' internal async behaviour, and runtime confirmation if no
   environment was available. Also list the automated pass's coverage limits from `audit-code-scan`: folders on the shared skip list (`node_modules`, `bin`, `obj`, `dist`, `build`, `.git`, `audit`, ... - see `$AUDIT_CORE_ROOT/skills/audit-code-scan/references/repo-walk-api.md`) and files over 2 MB are not read, and patterns match one line at a time. `di_lifetimes.py`
   uses the same walker, so registrations or constructors in files over 2 MB or under
   skipped folders are not parsed.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `ASYNC`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Reference:** CWE-nnn, ASVS-x.y.z, OWASP-A0n:2021 (use what applies; see references/<stack>.md)


Recurring references: CWE-833 (deadlock), CWE-400 (resource consumption),
CWE-390 (error condition without action), CWE-248 (uncaught exception),
CWE-1088 (synchronous access of remote resource without timeout), CWE-772
(missing release), CWE-362 (shared resource without synchronisation - captive
scoped state), CWE-1188 (insecure default initialisation).

## Output template (`audit/reports/audit-async-and-dependency-injection.md`)

```markdown
## audit-async-and-dependency-injection findings
| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| n | n | n | n | n |

### Scope
- Stack / container: <stack>, <MS.DI | Spring | NestJS | none>
- Automated pass: <N> grep hits across <M> patterns; <K> registrations parsed, <J> mismatches
- Manually traced: <list>

### Findings
<one block per finding, ordered by severity>

### DI registration table
| Service (registered as) | Implementation | Lifetime | Dependencies (lifetime) | Mismatch | Location |
|---|---|---|---|---|---|
| ReportCache | ReportCache | Singleton | AppDbContext (Scoped), ILogger (Singleton) | CAPTIVE-SCOPED | Program.cs:14 |
| IOrderService | OrderService | Scoped | AppDbContext (Scoped), IHttpClientFactory (Singleton) | - | Program.cs:16 |
Rule: a consumer may only hold dependencies whose lifetime is equal or longer. Singleton > Scoped > Transient. Transient-in-singleton is "captive-transient" (usually fine, flag if the transient is disposable or stateful).

### Async hazard summary
| Class | Candidates | Confirmed | Likely | False positive |
|---|---|---|---|---|
| Sync-over-async (BLOCK) | | | | |
| async void / unawaited (VOID) | | | | |
| Missing cancellation (CANCEL) | | | | |
| Fire-and-forget (FIRE) | | | | |
| HTTP client per request (HTTP) | | | | |
| Missing timeout (TIMEOUT) | | | | |

### Outbound call inventory
| Call site | Client construction | Timeout | Retry / breaker | Cancellation propagated | Finding |
|---|---|---|---|---|---|

### Not checked
- <item> - <reason>
```

## Examples

**Input (di_lifetimes.py row):**
`ReportCache | Singleton | deps: AppDbContext (Scoped) | CAPTIVE-SCOPED | Program.cs:14`

**Output:**
```markdown
### [High] ASYNC-001 - Singleton ReportCache holds a scoped AppDbContext for the process lifetime
- **Location:** `Program.cs:14` (AddSingleton<ReportCache>) and `Services/ReportCache.cs:9` (constructor)
- **Confidence:** confirmed
- **Evidence:**

```csharp
builder.Services.AddDbContext<AppDbContext>(...);       // scoped
builder.Services.AddSingleton<ReportCache>();           // ctor: public ReportCache(AppDbContext db) => _db = db;
```

- **Impact:** The first request's DbContext is reused by every later request: its change tracker grows forever, concurrent requests share a non-thread-safe context (intermittent "A second operation started on this context" errors), and in this multi-tenant service the context stays bound to the first tenant's connection string.
- **Remediation:** Inject `IServiceScopeFactory` and create a scope per operation: `using var scope = _scopes.CreateScope(); var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();` - or make ReportCache scoped if it has no cross-request state. Enable `ValidateScopes = true` and `ValidateOnBuild = true` in the host so the container rejects this at startup.
- **Reference:** CWE-362, CWE-400
```

**Input (grep hit):** `Controllers/InvoiceController.cs:41: var result = _fbr.SubmitAsync(inv).Result;`

**Output:** `[High] ASYNC-002 - Invoice submission blocks a request thread on an
async call` - remediation `await _fbr.SubmitAsync(inv, ct)` and make the action
`async Task<IActionResult>`; CWE-833 / CWE-400.

## Bundled files

- `references/<stack>.md` - container, lifetimes, blocking APIs, cancellation/timeout idioms, false positives, tooling per stack (dotnet, java-spring, node-express, python-django; angular/react/vue explain the frontend overlap and hand off). To add a stack, follow `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `references/async-antipatterns.md` - the seven hazard classes with proof-of-defect / proof-of-safety and severity guidance.
- `scripts/patterns/<stack>.json` - pattern lists for the automated pass (format: `$AUDIT_CORE_ROOT/skills/audit-code-scan/references/pattern-file-format.md`).
- `scripts/di_lifetimes.py` - parses registrations per stack, cross-references constructor parameters, emits the DI table and mismatch flags; walks the repo with `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py`.

Atomic scripts this skill calls (installed next to it, not bundled):

- `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` - stack detection (honours `audit/stack.json`).
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` - pattern-driven automated pass.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py` - shared walker imported by `di_lifetimes.py`.
- `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` - init / add / md / validate for findings.json.
- `evals/` - prompts and a fixture with a sync block on an async call, an async void handler, a singleton depending on a scoped service, and an HttpClient built inside a request handler, plus correct negatives.
