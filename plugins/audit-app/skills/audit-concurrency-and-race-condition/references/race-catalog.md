# Race catalog: the seven classes, what proves each safe, severity

For every state-changing operation in the inventory, decide which classes
apply and record the evidence that closes each one. "Evidence" means a
file:line, a constraint in a migration, or a config value; not "the developer
says it is fine".

## 1. Check-then-act (TOCTOU)

Shape: read a value, decide, then write, with the read and write not
atomic. Balance >= amount then debit; stock >= qty then decrement; `!exists(email)`
then insert; `status == Pending` then set Paid; `count < limit` then add.

Proves it safe (any one):
- Atomic conditional write: `UPDATE ... SET x = x - @q WHERE id=@id AND x >= @q` and 0 rows treated as failure; Mongo `findOneAndUpdate` with the condition in the filter; Redis `DECRBY` + check.
- Row lock inside one transaction: `SELECT ... FOR UPDATE` / `WITH (UPDLOCK, HOLDLOCK)` / `select_for_update()` / `@Lock(PESSIMISTIC_WRITE)` around both statements.
- Serializable isolation with retry on serialization failure.
- Optimistic version column checked on write (class 4).
- For uniqueness: a database unique constraint plus handling of the violation (class 1 is closed by class 3's fix).

Not evidence: an `exists` check "right before" the insert; an application-level `lock` in a multi-instance deployment; `async` methods (no locking implied).

## 2. Double submit

Shape: the same user action arrives twice (double click, browser retry on timeout, mobile app resend, back button + resubmit) and the server processes both.

Proves it safe: an idempotency key (class 3); a natural guard that makes the second call a no-op (`WHERE Status='Pending'` returning 0 rows); a unique constraint on the natural key (order number, cart id + submitted). Client-side button disabling is evidence of *intent* only; record it in the frontend column and still require a server guard.

## 3. Missing idempotency key

Shape: operations that are retried by design (payment webhooks, queue consumers with at-least-once delivery, HTTP clients with retry policies, mobile sync, third-party callbacks) with no way to recognise a repeat.

Proves it safe:
- A key stored *before* the side effect in a table with a unique index (`IdempotencyKeys(key, response, created_at)`), and a replay returning the stored result.
- Provider event id recorded with a unique constraint (`WebhookEvents(provider, event_id)`), insert first, process second, ignore duplicates.
- Consumer marks message id processed in the same transaction as its effect (outbox/inbox pattern).
- The same key passed to the downstream provider (`Stripe-Idempotency-Key`, `PayPal-Request-Id`).

Not evidence: "the provider only sends once" (they do not); deduping in memory (lost on restart, not shared across instances).

## 4. Optimistic concurrency not handled

Shape: entity has a version/rowversion/`@Version`/ETag column, or should have, and the code either ignores it (last write wins) or throws the concurrency exception to the user without retry or merge.

Proves it safe: version column exists; the ORM includes it in the `WHERE` of updates (EF `IsRowVersion()`, JPA `@Version`, Django `F()`-based or `django-concurrency`, Sequelize `version: true`, Prisma manual `where: { version }`); `DbUpdateConcurrencyException` / `OptimisticLockException` / `StaleObjectError` caught with a reload-and-retry or a 409 to the client; `If-Match` honoured on PUT.

Damage without it: two admins edit the same record; the second silently erases the first's changes; a stock adjustment based on a stale quantity.

## 5. Shared mutable state in singletons and statics

Shape: `static` fields, singleton services, module-level variables, DI singletons holding request data or mutable caches; `HttpContext`/request captured in a singleton; global counters.

Proves it safe: immutable after startup (`static readonly` immutable collection, frozen dict); thread-safe types (class 6); state scoped per request/scope (`AddScoped`, request-scoped beans, `contextvars`, `AsyncLocalStorage`); explicit synchronisation with a documented reason.

Special case (multi-tenant): a static holding the current tenant/DB name set per request is a cross-tenant race between two concurrent requests. Rate Critical if it selects the database; hand the isolation consequence to `audit-multi-tenant-isolation` as well.

## 6. Non-thread-safe collections across requests

Shape: `Dictionary`, `List`, `HashSet`, `HashMap`, `ArrayList`, plain JS objects/arrays, Python dict/list mutated from concurrent request handlers or threads without a lock.

Proves it safe: `ConcurrentDictionary`/`ConcurrentHashMap`/`CopyOnWriteArrayList`/`queue.Queue`; a `lock`/`synchronized`/`threading.Lock` around every access (reads included for non-atomic structures); Node single-threaded *and* no `await` between read and write (an `await` reopens the window); use of `IMemoryCache`/Redis instead.

Damage: corrupted dictionary throws for unrelated requests; lost updates; infinite loops on some implementations.

## 7. Distributed jobs that run twice

Shape: cron/Hangfire/Quartz/Celery beat/BullMQ repeat/k8s CronJob where the app runs on more than one instance or a job overruns its interval.

Proves it safe: `[DisableConcurrentExecution]` (Hangfire, per server: still needs a shared storage), Quartz `@DisallowConcurrentExecution` with clustered JobStore, ShedLock/`@SchedulerLock`, Redis/DB lease lock (`SET NX PX`), k8s `concurrencyPolicy: Forbid` and a single CronJob (not one per replica), Celery beat run as exactly one process plus a per-task lock, BullMQ single repeatable job key; *and* the job body idempotent per item (status guard in the UPDATE).

Not evidence: "we only run one instance today"; `@Scheduled` with `fixedDelay` (prevents overlap in one JVM only).

## Severity guidance

| Class | Typical severity | Move up when |
|---|---|---|
| Check-then-act on money/stock | High | unauthenticated or cross-tenant trigger -> Critical |
| Double submit on payment/order | High | provider charge without key -> High; internal-only order duplicate -> Medium |
| Missing idempotency on webhook/consumer | High (money) / Medium (other) | webhook also unauthenticated -> Critical |
| Optimistic concurrency ignored | Medium | on stock/ledger -> High |
| Shared static request state | Medium | selects tenant/DB -> Critical |
| Unsafe collection | Medium | crash affects all requests -> High |
| Double-running job | Low (idempotent body) / Medium / High (money) | |

## Writing the reproduction note

For each confirmed race give: the two actors (A: POST /pay, B: POST /pay 50 ms later, or A: pod-1 job, B: pod-2 job), the shared resource (row, static field), the window (between line X read and line Y write), and the observable result. If the user can run it, `scripts/double_submit.sh` fires two identical requests and prints both responses; record the output under `audit/evidence/`.
