---
name: audit-concurrency-and-race-condition
description: Finds race conditions and concurrency bugs in an application - check-then-act without a lock or transaction (balance check then debit, uniqueness check then insert), double-submit on orders and payments, missing idempotency keys on retried or webhook-driven operations, optimistic concurrency (rowversion, @Version, ETag) not handled, shared mutable state in singletons and statics, non-thread-safe collections used across requests, and scheduled or distributed jobs that can run twice. Use it whenever the user asks about race conditions, concurrency, thread safety, double submission, duplicate orders or payments, idempotency, retries, webhooks, transactions, locking, deadlocks, optimistic or pessimistic concurrency, or reviews payment, order, stock or inventory flows - even when the user never says "race" or names this skill. Also run it as part of a general pre-production or application audit.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit concurrency and race conditions

A race is a bug that only shows up when two things happen at once: two
clicks on "Pay", a webhook retried by the provider, two pods running the same
nightly job, two requests reading a static cache. Tests run one request at a
time, so these ship. This skill inventories every operation that changes
state, asks of each one "what happens if it runs twice, or concurrently with
itself or its neighbour", and reports the ones with no answer.

Read-only rule: never modify the audited code. Write only under `audit/`.

## Inputs and prerequisites

- Path to the audited repository (backend; frontend root too if separate, for double-submit evidence).
- `audit/stack.json` if `audit-application` already ran; otherwise this skill runs `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`.
- Access to schema/migrations (unique constraints, rowversion/version columns) and job configuration (Hangfire, Quartz, cron, Celery, BullMQ, k8s CronJob replicas).
- Optional: how many instances run in production (single process vs N replicas). If unknown, assume N > 1 and say so.
- Python 3 for the bundled scripts.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack detection), `audit-code-scan` (grep pass, and the shared `repo_walk.py` walker the bundled scripts import) and `audit-finding-writer` (`$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`). A missing one stops the scripts with an error naming it.

## Coordination with sibling skills

- `audit-business-logic` hands you check-then-act sites, replayable webhooks, and overlapping jobs it noticed while tracing rules; you own the mechanics (lock, transaction, constraint, idempotency key). Hand back anything that is a rule problem rather than a timing problem (wrong state allowed, wrong amount).
- `audit-datetime-and-timezone` owns whether a job fires at the right wall-clock time; you own whether two firings can overlap.
- `audit-db-schema` owns general schema quality; you still record missing unique constraints and version columns here because they are the fix for the race.
- `audit-async-and-dependency-injection` owns captive dependencies and async misuse in general; you own the specific case of mutable state shared across requests. Cross-reference by `root_cause_key`.

## Workflow

1. **Resolve the stack.** Run `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Open only the matching `references/<stack>.md` for the backend and, if present, the frontend. Always read `references/race-catalog.md` (the seven race classes, what proves each one safe, and severity guidance). Unknown stack: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
2. **Automated pass.** Run
   `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<backend>.json [--patterns scripts/patterns/<frontend>.json] --out audit/evidence/audit-concurrency-and-race-condition/hits.json --md audit/evidence/audit-concurrency-and-race-condition/hits.md`.
   Patterns cover check-then-act shapes (exists/any/count followed by insert or update), shared static mutable state, non-thread-safe collections, missing idempotency keys on payment/webhook handlers, version/rowversion columns and whether concurrency exceptions are caught, and scheduler registrations without a distributed lock. Then run
   `python scripts/state_change_inventory.py <repo> --out audit/evidence/audit-concurrency-and-race-condition/inventory.json --md audit/evidence/audit-concurrency-and-race-condition/inventory.md` to list every state-changing entry point (POST/PUT/PATCH/DELETE handlers, jobs, queue consumers, webhooks) with the transaction, idempotency, and lock markers found in the same file. Hits are pointers, not findings.
3. **Manual trace.** Complete the inventory by hand: for each state-changing operation record *idempotent?* (safe to run twice with the same input: key, unique constraint, or natural no-op), *transaction?* (which statements share one unit of work and at what isolation), *lock/guard?* (row lock, optimistic version, distributed lock, atomic update), and *concurrent-self-safe?* (two copies at once). Then trace the highest-risk operations in this order, using the checklist in `references/race-catalog.md`:
   1. Money movement: pay, refund, wallet debit, credit application, invoice numbering.
   2. Stock: reserve, decrement, transfer, adjust.
   3. Uniqueness: registration, invite, coupon redeem, slug/number generation.
   4. Webhooks and retried consumers: provider callbacks, queue handlers, retry policies.
   5. Scheduled jobs: can two instances/pods run the same job at once.
   6. In-process shared state: statics, singletons, caches, counters.
   For each, name the two operations that interleave, the window between them, and the observable damage (negative stock, double charge, duplicate user).
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (block below, prefix `RACE`). Rate with `audit-finding-writer/references/severity-rubric.md`: a race that moves money or stock is High by default; duplicate rows without financial effect are Medium; in-process state corruption that only affects one request is Medium; a job that can double-run harmlessly is Low.
5. **Produce the outputs.**
   - `audit/findings/audit-concurrency-and-race-condition.json` (`$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py init` then `add`; `md` renders the findings section).
   - `audit/reports/audit-concurrency-and-race-condition.md` in the template below: the state-changing operations inventory, shared-state inventory, findings, not checked.
   - `audit/evidence/audit-concurrency-and-race-condition/` with `hits.json`, `inventory.json`, and any reproduction notes (for example a two-request `curl` pair the user ran, or `scripts/double_submit.sh` output).
   - `audit/status/audit-concurrency-and-race-condition.json`: the status record defined in `audit-core:audit-finding-writer` (references/run-status.md).
6. **List what was not checked.** Database isolation level in production, actual replica count, provider retry semantics you could not confirm, stored procedures, queue delivery guarantees (at-least-once vs exactly-once), and anything handed to siblings. Put them in `scope.not_checked` and in the report. Also list what the automated pass did not read: folders skipped by the shared walker (`repo_walk.SKIP_DIRS` in `audit-code-scan`: `.git`, `node_modules`, `bin`, `obj`, `dist`, `build`, `target`, `coverage`, `.angular`, `.next`, the `audit` workspace and similar) and files over 2 MB; `state_change_inventory.py` also skips `migrations`/`Migrations` folders and test files on purpose.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `RACE`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Evidence:**

```lang
<the two statements that race, or the shared state and its writers>
```

- **Impact:** Plain language: what two concurrent actors produce (double charge, negative stock, duplicate account), how easy it is to trigger (double click, retry, two pods).
- **Remediation:** The concrete fix in this stack: unique constraint + handled violation, atomic conditional update, row lock in a transaction, optimistic version with retry, idempotency key table, distributed job lock, immutable/concurrent state.
- **Reference:** CWE-362 (race condition), CWE-367 (TOCTOU), CWE-366 (race within a thread), CWE-662 (improper synchronization), CWE-820 (missing synchronization), CWE-915; ASVS-11.1.4 / 11.1.6 (business logic, anti-automation)


## Output template (`audit/reports/audit-concurrency-and-race-condition.md`)

```markdown
# Concurrency and race-condition audit

Target: <repo> @ <commit> | Stack: <backend>/<frontend> | Date: <ISO date>
Assumptions: <N> instances in production; DB isolation <level or unknown>; queues at-least-once.

## Summary
| Severity | Count |
|---|---|
| Critical | n | ...

## State-changing operations inventory
| Operation | Entry point | Idempotent? | How | Transaction? | Lock / guard | Concurrent-self-safe? | Finding |
|---|---|---|---|---|---|---|---|
| Charge order | POST /api/payments/charge | no | - | no | none | no | RACE-001 |
| Register user | POST /api/users | no | exists-check only, no unique index | no | none | no | RACE-002 |
| Reserve stock | StockService.Reserve | n/a | - | yes (ReadCommitted) | none (check-then-act) | no | RACE-003 |
| Expire trials job | Hangfire trial-expiry | yes | status guard in same UPDATE | per row | DisableConcurrentExecution | yes | - |
| Stripe webhook | POST /webhooks/stripe | yes | event id unique table | yes | unique constraint | yes | - |

## Shared in-process state
| Symbol | Type | Mutated by | Thread-safe? | Finding |
|---|---|---|---|---|
| RateLimiter.Hits | static Dictionary<string,int> | every request | no | RACE-004 |
| Settings.Cache | static readonly IReadOnlyDictionary | startup only | yes (immutable) | - |

## Findings
<finding blocks>

## Handed off
| To | Item | Location |

## Not checked
- <item>: <reason>
```

## Examples

**Input:** `PaymentsController.Charge` reads the order, calls the gateway, then sets `Status = Paid`, with no key on the request and no status guard in the update.

**Output:**
```markdown
### [High] RACE-001 - Charge endpoint has no idempotency key; a retried request charges twice
- **Location:** `Payments/PaymentsController.cs:28` (Charge)
- **Confidence:** confirmed
- **Evidence:**

```csharp
var order = _repo.Get(request.OrderId);          // no status check, no key lookup
var ok = _gateway.Charge(order.CustomerId, order.Total);
order.Status = OrderStatus.Paid; _repo.Save(order);
```

- **Impact:** A double click, a mobile retry, or a gateway timeout followed by a client retry charges the card twice; the second charge is not visible in the order, so support finds it only when the customer complains. Rated High: money moves and any customer can trigger it.
- **Remediation:** Require an `Idempotency-Key` header (or derive one from `orderId` + attempt), store it in an `IdempotencyKeys` table with a unique index before calling the gateway, return the stored response on replay, and pass the same key to the gateway (`Stripe idempotency_key`). Also guard the status transition atomically: `UPDATE Orders SET Status='Paid' WHERE Id=@id AND Status='Pending'` and treat 0 rows as "already paid".
- **Reference:** CWE-362, ASVS-11.1.4
```

**Input:** `static Dictionary<string,int> _hits` in a rate limiter incremented from every request.

**Output:** `[Medium] RACE-004 - Static Dictionary mutated per request without synchronization` with remediation `ConcurrentDictionary<string,int>` + `AddOrUpdate`, or `IMemoryCache`; note that the corrupted dictionary can throw and take down unrelated requests. Reference CWE-662.

## Bundled files

- `references/race-catalog.md` - the seven race classes (check-then-act, double submit, idempotency, optimistic concurrency, shared state, collections, jobs), what proves each safe, severity guidance, and how to write the reproduction note.
- `references/<stack>.md` - transaction/lock/idempotency idioms, unsafe collections, scheduler locks, false positives per stack (dotnet, java-spring, node-express, python-django, angular, react, vue); add one from `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` - stack detection (honours `audit/stack.json`; atomic skill).
- `scripts/patterns/<stack>.json` - automated pass run by `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- `scripts/state_change_inventory.py` - lists state-changing entry points with transaction/idempotency/lock markers to seed the inventory table. Walks files with `audit-code-scan`'s `repo_walk.py`.
- `scripts/double_submit.sh` - fires two identical requests concurrently against a URL (curl) to confirm a double-submit race; read-only against the repo, use only against a test environment.
- `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` - init / add / validate / md / summary for findings.json (atomic skill).
- `evals/` - sample repo with a check-then-insert without a unique constraint, a payment endpoint with no idempotency key, and a shared static map mutated per request, plus correct negatives.
