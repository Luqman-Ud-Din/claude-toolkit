# Architecture review checklist

Work through every block; each "no" is a candidate finding. Cite evidence
(file, compose line, script output) for every answer - "seems fine" is not an
answer.

## 1. Structure discovery
- List modules (build units), runtime services (processes/containers), data stores, queues/brokers, caches, gateways, external integrations (payment, tax, SMS, email, storage, identity providers), background job hosts, and clients.
- For each edge: protocol (HTTP/gRPC/AMQP/DB), sync or async, who initiates, what fails when the target is down.
- Evidence: `modules.json`, `topology.json`, DI registrations, HTTP client base addresses, queue names, connection strings (names only).

## 2. Layering and dependency direction
| Check | Pass |
|---|---|
| No circular references between build units | `module_graph.py` reports zero cycles |
| Domain/core does not depend on infrastructure, web, or a specific ORM/driver | edges only point inward (presentation -> application -> domain; infrastructure -> domain via interfaces) |
| Presentation does not reach the database directly | no `DbContext`/`EntityManager`/`prisma` in controllers or components |
| Shared kernel is small and stable | `Shared*` has high fan-in, near-zero fan-out, no business rules |
| Instability gradient | modules with high fan-in have low instability (Ce/(Ca+Ce)) |

## 3. Module boundaries and coupling
- Shared database between services (same connection string or same table names in two services' models).
- Leaky abstractions: entity classes returned from APIs, ORM types in interfaces, repository interfaces that mirror the ORM.
- God modules: one project/package everything depends on and that depends on everything; one class > 1000 lines or > 30 public members that many modules touch.
- Feature envy across modules: module A reaching into module B's internals (`internal`/`_private` access, deep relative imports).
- Cross-cutting concerns duplicated (auth, tenancy, logging) instead of centralised.

## 4. Data ownership and consistency
- Every table/entity has exactly one writing module (`data_ownership.py`).
- Dual writes (DB + queue, DB + external API) without an outbox or saga; distributed transactions; two-phase commit.
- Read models / reporting reading another service's tables directly.
- Reference data (companies, products) replicated or shared - who is the source of truth, how do copies converge.
- Tenant boundary: is the tenant chosen per request (header/claim -> connection), and is that decision made in one place.

## 5. Resilience
| Pattern | Look for |
|---|---|
| Single points of failure | infra components with one instance and many dependents (`topology.json`), one gateway, one job host holding all schedules, one shared cache |
| Timeouts | every outbound HTTP/DB/queue client has a timeout shorter than the caller's |
| Retries with backoff | Polly / Resilience4j / axios-retry / tenacity; retries only on idempotent operations; jitter |
| Circuit breakers / bulkheads | breaker around each external dependency; separate connection pools or thread pools for slow dependencies |
| Graceful degradation | what the UI does when a non-critical dependency (SMS, tax API, reports) is down |
| Idempotent consumers | message handlers de-duplicate by message id; at-least-once assumed |
| Dead-letter and replay | DLQ configured, someone owns it |
| Backpressure | bounded queues/channels, prefetch limits, rate limits at the edge |
| Startup/shutdown | health checks gate traffic; in-flight work drains on SIGTERM |

## 6. Statefulness and horizontal scalability
- In-process state that must be shared: static holders, `IMemoryCache`/Guava/lru-cache used as source of truth, in-memory sessions, SignalR/Socket.IO without a backplane, local file storage, singleton counters, in-memory rate limiters, schedulers that assume one instance.
- Sticky sessions required? Long-running requests? Large in-process caches warmed on start?
- Database as the scaling limit: single writer instance, no read replicas, per-tenant DB count growth, connection pool per tenant.

## 7. Synchronous vs asynchronous integration
- Sync chains deeper than two hops on a user request; fan-out calls in a loop.
- Async used where the user needs the result immediately (and polling to compensate) or sync used for work that can wait (emails, reports, webhooks).
- Event contracts versioned; consumers tolerate unknown fields.
- Ordering assumptions on queues that do not guarantee order.

## 8. Security architecture
- Trust boundaries: internet -> edge -> gateway -> services -> data -> third parties. Draw them.
- Where authentication happens (gateway, each service, both), whether internal services accept unauthenticated calls from the network, whether the gateway can be bypassed (service ports published in compose/k8s).
- Where authorization happens (per endpoint, per resource, in the DB via tenant selection).
- Secrets flow: source (env, vault, file in image), rotation, which components see which secrets, secrets in queue messages or logs.
- Internal transport: TLS between services, DB and broker connections encrypted.
- Delegate endpoint-level checks; keep the map.

## 9. Fit for purpose
- Number of deployable units vs team size (rule of thumb: > 1 service per 2 engineers is expensive).
- Number of technologies (languages, brokers, DBs) vs the team's ability to operate them.
- Complexity without a driver: CQRS/event sourcing/microservices for a CRUD app with one team; or a monolith with one DB serving 50 tenants at 10x growth with no read scaling plan.
- Missing basics: no gateway when there are many services, no queue when there is heavy background work done in requests, no cache when the same reference data is read per request.

## 10. Documentation and decisions
- ADRs exist, are dated, have status; last one newer than the last major structural change.
- README diagram matches `modules.json`/`topology.json` (`doc_drift.py`).
- Runbook names the SPOFs and how to recover them.

## "Design risks for the next 12 months" prompts
For each risk: trend (what grows), trigger (the number or event where it breaks), symptom (what users/on-call see), mitigation (structural), when to act (before which milestone).
- Data growth: largest tables, per-tenant DB count, backup window, index size.
- Traffic growth: the sync chain with the most hops, the single-instance components, the connection pools.
- Team growth: the god module everyone edits, the cycle that blocks splitting, missing contracts between teams.
- Compliance/tenancy: shared DB with tenant column vs DB-per-tenant, data residency, per-tenant export/delete.
- Third-party dependence: one tax/payment/SMS provider with no fallback; API deprecations announced.
- Operational: single job host, single broker, manual deploys, no rollback tested (delegate mechanics, keep the risk).
