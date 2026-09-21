# The seven leak classes

Every pattern id in `scripts/patterns/*.json` starts with one of these class
codes, so `hits.json` can be grouped into the "Leak class summary" table.
For each class: what it is, what proves it, how to rate it.

| Code | Class | Proof of leak | Proof of safety | Typical severity |
|---|---|---|---|---|
| DISP | Disposable not disposed | Object created (stream, connection, response, context, image, package, scope, CTS) and no `using`/`try-with-resources`/`with`/`finally close()` on every exit path; or stored in a field of a longer-lived object | Wrapped in the language's scoped-disposal construct, or ownership handed to a framework helper that disposes (`File(stream)`, `pipeline()`, Spring Data) | High if per request, Medium if per job/iteration, Low if once at startup |
| SUB | Subscription never removed | `+=`/`on`/`addListener`/`connect`/`subscribe` on a publisher that outlives the subscriber, executed per request/connection/instance, with no matching remove on the same object | Subscribed once at startup on a singleton; or removed in the subscriber's dispose/destroy/disconnect path | High if per request or per connection, Medium per instance of a pooled object |
| STAT | Static / singleton collection grows | Writes (`Add`, `push`, `put`, `append`, indexer set) exist; no `Remove`/`Clear`/`delete`/`splice`/`pop`; key space depends on input (user id, request id, order id, timestamp) | Key space bounded by design (enum, route table, tenant list) - state the bound in the finding; or removal proven | Critical when keyed by request/user/time at production rate; Medium when bounded by a slow-growing key (tenants) |
| CACHE | Cache without bound | Cache construction with no size limit AND no expiration; or expiration only but keys derived from unbounded input (search terms, ids) with high cardinality | Both a max size and an expiration, or one of them plus a provably small key space | High if keys are user-controlled; Medium if keys are ids with large but finite cardinality; Low if config-keyed |
| TIMER | Per-request timers / cancellation sources | `Timer`, `setInterval`, `threading.Timer`, `CancellationTokenSource`, `ScheduledExecutor` created inside a handler, middleware, or per-instance constructor, no clear/dispose on completion | Created once at startup, or cleared/disposed in `finally`/destroy hook | High for intervals (fire forever), Medium for timeouts/CTS (cleaned by GC eventually but hold callbacks) |
| ALLOC | Hot-path allocation without pooling | Large buffers (`new byte[N]`, `Buffer.alloc`, `bytearray`), full-entity serialization, per-call regex/ObjectMapper/DateFormat construction, `ToArray()` on big streams, in a request path or tight loop | Pooled (`ArrayPool`, `RecyclableMemoryStream`), cached static instances, streaming instead of buffering | Medium (LOH fragmentation / GC pressure), High when combined with unbounded input size |
| BG | Background worker accumulates or swallows | Loop with empty/log-less `catch`; state kept across iterations (`List` field appended per run, DbContext/EntityManager reused across iterations); no cancellation honoured; fire-and-forget task with no continuation | Scope per iteration, exception logged with context, state local to the iteration, cancellation token respected | High (silent failure + growth) ; Critical if the worker is the only path for a business process (e.g. invoice submission) and errors are dropped |

## Rating notes
- Multiply by rate: a per-request leak of 1 KB at 50 RPS is 4.3 GB/day. Write the arithmetic into Impact.
- A restart schedule (`--max-requests`, nightly recycle, Kubernetes memory limit restarts) is a mitigation, not a fix: rate one level down and name it in Impact.
- Multi-tenant systems: a per-tenant collection is bounded by tenant count; say the expected count. A per-tenant *DbContext* kept in a static dictionary is not bounded - its change tracker grows.
- `confidence: likely` when you could not follow the object to the end of its scope (for example, ownership passes through an interface you could not resolve).

## Evidence to keep
For each confirmed finding save `audit/evidence/audit-backend-resource-leak/<id>-trace.md` with: creation site, every exit path, which paths dispose/remove, and the framework helper (if any) you relied on.
