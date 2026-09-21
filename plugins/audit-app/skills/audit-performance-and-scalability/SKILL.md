---
name: audit-performance-and-scalability
description: End-to-end performance, latency, throughput and scalability review - blocking or sequential outbound calls, missing caching and invalidation, no response compression, oversized payloads, chatty APIs, pool sizing, missing timeouts and circuit breakers, hot-path allocation, inline background work, in-process session or file state that blocks horizontal scaling, render-blocking resources, images, re-renders, repeated API calls per page, client caching, Core Web Vitals, CDN and autoscaling readiness - plus a load-test plan with p50/p95/p99, error-rate and throughput thresholds that it runs and grades when an environment exists. Use whenever the user asks about performance, latency, slow endpoints, response times, throughput, scalability, load testing, k6 or JMeter, caching, Core Web Vitals, LCP/INP/CLS, or "will this handle production traffic", and in any pre-production audit. Delegates queries to audit-orm-query-and-data-access, memory to audit-backend-resource-leak, bundle to audit-frontend-best-practices.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: performance and scalability

"Will it hold up on launch day?" has three parts: how long one request takes,
how many requests the system serves before it degrades, and whether adding
another instance helps. This skill answers all three by reading the code for
the patterns that decide them, estimating per-endpoint latency, mapping what
should be cached where, and writing (and if possible running) a load test whose
pass/fail thresholds are written down before the first run.

Read-only rule: never modify the audited code. Write only under `audit/`
(findings, reports, evidence, status).

## What this skill owns and what it delegates

| Concern | Owner | This skill does |
|---|---|---|
| N+1, unbounded queries, tracking, indexes, transactions | `audit-orm-query-and-data-access` | Reads its findings.json if present; otherwise notes "query layer not reviewed" and estimates latency from code shape only |
| Memory/handle leaks, unbounded caches (as leaks), background-worker stability | `audit-backend-resource-leak` | Reads its 15-minute leak result if present; the load-test plan here reuses its sampling commands |
| Bundle size, lazy routes, change detection, image pipeline, framework hygiene | `audit-frontend-best-practices` | Reads its findings; here only measures/estimates the *runtime* effect (render-blocking, calls per page, CWV) |
| API shape (paging contracts, DTO size) | `audit-api-contract` | Cross-references payload findings |
| Infra (autoscaling rules, CDN config, replicas) | `audit-infra-and-deployment` | Records what the code *needs* (stateless, cache-backed, CDN-able); infra skill verifies the environment |

State in the report which of these ran and which findings were consumed.

## Inputs / prerequisites

- Repo root(s): backend and, if present, frontend.
- `audit/stack.json` if the orchestrator wrote it; otherwise `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection`, `audit-code-scan`, `audit-endpoint-inventory` (which itself needs `audit-sensitive-data-catalog`) and `audit-finding-writer`.
- Optional: sibling findings (`audit/findings/audit-orm-query-and-data-access.json`, `audit-backend-resource-leak.json`, `audit-frontend-best-practices.json`).
- Optional: a running environment URL + auth token, and one load tool (k6 preferred; bombardier, wrk, JMeter, autocannon, Locust also covered in `references/load-test-tools.md`).
- Python 3 (stdlib only).

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Open
   `references/<backend>.md` and `references/<frontend>.md` only. Each lists the
   concrete APIs for blocking calls, sequential fan-out, caching, compression,
   timeouts/circuit breakers, session state, pool sizing, and (frontend) render
   blocking, re-renders, per-page calls, client caching, CWV tooling.
2. **Automated pass.**
   `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<backend>.json [--patterns scripts/patterns/<frontend>.json] --out audit/evidence/audit-performance-and-scalability/hits.json --md .../hits.md`
   then run `audit-endpoint-inventory`, or reuse
   `audit/evidence/audit-endpoint-inventory/endpoints.json` when the orchestrator
   already produced it (all detected stacks in one run):
   `python "$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py" <repo>`.
   For the latency table read each HTTP record's `path_raw`, `handler`,
   `outbound.calls` (with `via` for calls made one hop away in a service) and
   `outbound.sequential` (lines in `sequential_evidence`), `data_access.db_call_count`,
   `response.projection`, `data_access.paging_seen` and
   `data_access.inline_background_work`; `endpoints.probe.json` feeds the k6 generator.
   Pattern classes: BLOCK (sync over async), SEQ (sequential awaits that are
   independent), CACHE (missing/unsafe), COMPRESS, PAYLOAD, CHATTY, POOL,
   TIMEOUT, ALLOC, INLINE-BG, STATE (in-process session/file), and for the
   frontend RENDER-BLOCK, RERENDER, CALLS-PER-PAGE, CLIENT-CACHE, IMAGE.
3. **Manual trace of the highest-risk flows.** (a) The landing page and the top
   3 business flows (login -> dashboard -> main list -> save): for each, list every
   backend call in order, mark which are sequential but independent, which hit
   external services with no timeout, which return more than the UI renders.
   (b) Horizontal-scaling blockers: `grep` for in-memory session, local file
   writes as state, static caches that must be coherent, singleton locks - one
   instance today means an outage tomorrow. (c) Dependencies: every outbound
   HTTP/queue/DB call - timeout? retry with backoff? circuit breaker? pool size
   vs expected concurrency. (d) Frontend: open the landing route, count API calls
   on load (DevTools or code), find duplicates, render-blocking `<script>`/`<link>`,
   unoptimised images, components re-rendering on every store change.
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (`init`, `add`, `md`). Severity
   per `audit-finding-writer/references/severity-rubric.md`, non-security
   scale: an in-process session store on a service meant to scale out is High;
   a chatty page that makes five identical calls is Medium; missing compression
   on a 2 MB list is Medium; a sequential fan-out on the checkout path is High.
5. **Produce the outputs** (template below): per-endpoint latency table
   (measured, or estimated with reasoning from the inventory), caching
   opportunity map (what -> where -> TTL -> invalidation trigger), the load-test
   plan with thresholds (`python scripts/loadtest_plan.py k6 --inventory audit/evidence/audit-endpoint-inventory/endpoints.probe.json --base-url <url> --out audit/evidence/audit-performance-and-scalability/loadtest.js`; use the probe file, whose rows carry `route`, `method`, `kind` and `weight`),
   and if an environment exists run it and grade:
   `python scripts/loadtest_plan.py grade summary.json --format k6|bombardier --thresholds references/thresholds.json --out .../loadtest-result.md`.
   Write `audit/status/audit-performance-and-scalability.json`
   (`{"skill","status":"completed|failed|skipped","reason","started_at","finished_at"}`).
6. **List what was not checked**: the load test if not run (no environment),
   query plans (delegated), memory over time (delegated), bundle analysis
   (delegated), CDN/autoscaling config (infra skill), and third-party latency
   you could not measure.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `PERF`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Reference:** CWE-nnn, ASVS-x.y.z, OWASP-A0n:2021 (use what applies; see references/<stack>.md)


Recurring references: CWE-400 (uncontrolled resource consumption), CWE-770
(allocation without limits), CWE-1050 (excessive platform resource consumption
within a loop), CWE-1088 (synchronous access of remote resource without
timeout), CWE-1072 (no connection pooling), CWE-407 (inefficient algorithmic
complexity), ASVS-12.x/13.x; web.dev Core Web Vitals thresholds (LCP 2.5 s,
INP 200 ms, CLS 0.1).

## Output template (`audit/reports/audit-performance-and-scalability.md`)

```markdown
## audit-performance-and-scalability findings
| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| n | n | n | n | n |

### Scope and delegation
- Stack: <backend> / <frontend>; roots: <paths>
- Consumed: audit-orm-query-and-data-access (<n> findings | not run), audit-backend-resource-leak (<result> | not run), audit-frontend-best-practices (<n> | not run)
- Environment: <URL | none - load test planned, not run>

### Findings
<one block per finding, ordered by severity>

### Per-endpoint latency table
| Endpoint | Handler | Outbound calls (seq/par) | DB calls | Payload (est.) | Measured p50/p95/p99 (ms) | Estimated p95 (ms) + reasoning | Finding |
|---|---|---|---|---|---|---|---|
| POST /api/orders | OrdersService.create | 3 seq (customer, pricing, tax) | 4 | 2 KB | - | ~900: 3 x 250 ms upstream in series + 4 x 10 ms DB | PERF-001 |

### Caching opportunity map
| What | Where | TTL | Invalidation trigger | Expected win | Finding |
|---|---|---|---|---|---|
| Product catalogue list per company | Distributed (Redis) keyed by companyId+page | 5 min | product create/update/delete event | removes ~60% of DB reads on the landing page | PERF-003 |
| Tax rates | In-process IMemoryCache | 24 h | config change | 1 upstream call per request -> per day | PERF-001 |
| Static assets | CDN, immutable hashed filenames | 1 year | new build | LCP -0.8 s | PERF-007 |

### Horizontal-scaling blockers
| Blocker | Location | Fix |
|---|---|---|
| In-process session store | api/src/app.ts:14 | Redis/SQL session store or stateless JWT |

### Frontend runtime
| Page | API calls on load | Duplicates | Render-blocking resources | Largest image | LCP / INP / CLS (measured or -) | Finding |
|---|---|---|---|---|---|---|

### Load-test plan
Tool: <k6 | ...> (`references/load-test-tools.md`). Script: audit/evidence/audit-performance-and-scalability/loadtest.js
Profiles: smoke (1 VU, 1 min), load (target RPS = <expected peak> for 10 min), stress (2x for 5 min), soak (target for 30 min; reuse leak sampling).
| Metric | Threshold |
|---|---|
| p50 latency | <= 200 ms (read), <= 400 ms (write) |
| p95 latency | <= 500 ms (read), <= 1000 ms (write) |
| p99 latency | <= 1500 ms |
| Error rate (non-2xx/3xx) | < 1% |
| Throughput | >= target RPS sustained with p95 within threshold |
| CPU / memory | < 70% CPU at target; memory flat (see audit-backend-resource-leak) |

### Load-test results
| Profile | Endpoint set | RPS achieved | p50 | p95 | p99 | Error rate | Verdict |
|---|---|---|---|---|---|---|---|
| (not run - no environment) | | | | | | | |

### Not checked
- <item> - <reason>
```

## Examples

**Input (grep hit, Node):**
`src/orders/orders.service.ts:22-24: const c = await customers.get(id); const p = await pricing.quote(items); const t = await tax.rate(region);`

**Output:**
```markdown
### [High] PERF-001 - Order creation waits on three independent upstream calls in series
- **Location:** `src/orders/orders.service.ts:22` (create)
- **Confidence:** confirmed
- **Evidence:**

```ts
const c = await this.customers.get(dto.customerId);   // ~250 ms
const p = await this.pricing.quote(dto.items);        // ~250 ms, does not use c
const t = await this.tax.rate(dto.region);            // ~250 ms, does not use c or p
```

- **Impact:** Every order pays the sum of three network round-trips (~750 ms) instead of the slowest one (~250 ms); at checkout peak this is the p95 driver and the first thing customers feel. High: main revenue path, every request.
- **Remediation:** `const [c, p, t] = await Promise.all([this.customers.get(...), this.pricing.quote(...), this.tax.rate(...)]);` with per-call `AbortSignal.timeout(2000)`; cache `tax.rate` by region for 24 h (see caching map).
- **Reference:** CWE-1050, CWE-1088
```

**Input (frontend trace):** dashboard component subscribes to `api.get('products')`
in five widgets on init.

**Output:** `[Medium] PERF-004 - Dashboard fetches the product list five times on
load` with remediation to fetch once in the container (or a `shareReplay(1)`
service cache / React Query key) and pass down; add the row to the "Frontend
runtime" table with Duplicates = 4.

## Bundled files

- `references/<stack>.md` - blocking/sequential/caching/compression/timeout/pool/state patterns and tooling per backend; render-blocking/re-render/calls-per-page/client-cache/CWV per frontend; to add a stack, copy `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `references/load-test-tools.md` - k6, bombardier, wrk, JMeter, autocannon, Locust, Lighthouse/WebPageTest commands, profile definitions.
- `references/caching-map.md` - how to fill the what/where/TTL/invalidation map, cache layers per stack, invalidation patterns.
- `references/thresholds.json` - default p50/p95/p99/error/throughput thresholds consumed by `loadtest_plan.py grade`.
- `scripts/patterns/<stack>.json` - grep patterns for the automated pass (backend and frontend pattern files).
- `scripts/loadtest_plan.py` - `k6` generates a k6 script skeleton from audit-endpoint-inventory's `endpoints.probe.json`; `grade` scores a k6 or bombardier JSON summary against thresholds.
- Atomic scripts this skill calls: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` (stack), `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` (automated pass), `$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py` (route, handler, outbound/DB call facts for the latency table and the k6 input), `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (findings I/O).
- `evals/` - prompts and a fixture (Express API + Angular page) with three sequential outbound calls, an uncompressed full-entity list, in-process session state, and a page calling the same API five times.
