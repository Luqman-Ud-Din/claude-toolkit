# Load-test tools and profiles

Pick one tool the team already has. All commands assume `$BASE` (e.g.
`https://staging.example.com`) and `$TOKEN` (a JWT for a test tenant). Never
run against production without the owner's written go-ahead; use a staging
copy with production-like data volume - an empty database passes every test.

## Profiles (same for every tool)
| Profile | Shape | Purpose | Pass |
|---|---|---|---|
| smoke | 1 VU, 1 min | script works, auth works | 0 errors |
| load | ramp to target RPS over 2 min, hold 10 min | normal peak | thresholds in `thresholds.json` |
| stress | 2x target for 5 min | find the knee | p95 degrades gracefully, error rate < 5%, recovers within 2 min after |
| spike | 0 -> 5x target in 10 s, hold 1 min | autoscaling / queueing behaviour | no 5xx storm, recovery < 2 min |
| soak | target for 30-60 min | leaks, pool exhaustion | flat p95 and memory (reuse `audit-backend-resource-leak` sampling) |

Target RPS = expected peak concurrent users x requests per user per second (from the endpoint inventory: calls per page / think time). Write the arithmetic into the plan.

## k6 (preferred - thresholds in the script, JSON summary for the grader)
```bash
# generate skeleton from the inventory
python scripts/loadtest_plan.py k6 --inventory audit/evidence/audit-endpoint-inventory/endpoints.probe.json --base-url $BASE --rps 50 --out loadtest.js
k6 run -e BASE=$BASE -e TOKEN=$TOKEN --summary-export=summary.json loadtest.js          # legacy summary (metrics.*.p(95))
k6 run -e BASE=$BASE -e TOKEN=$TOKEN --out json=raw.json loadtest.js                   # per-request stream (large)
python scripts/loadtest_plan.py grade summary.json --format k6 --out loadtest-result.md
```
Script skeleton uses `scenarios` with `constant-arrival-rate` (true RPS, not VU-bound) and `thresholds: { http_req_duration: ['p(95)<500'], http_req_failed: ['rate<0.01'] }`; per-endpoint tags (`tags: { name: 'GET /api/products' }`) give per-endpoint percentiles in `summary.json` under `metrics['http_req_duration{name:...}']` when `--summary-trend-stats` and `systemTags` include `name`.

## bombardier (single endpoint, fixed rate, JSON output)
```bash
bombardier -c 50 -r 50 -d 10m -l -H "Authorization: Bearer $TOKEN" --print r --format json $BASE/api/products?page=1 > bomb.json
python scripts/loadtest_plan.py grade bomb.json --format bombardier --kind read
# POST: -m POST -H "Content-Type: application/json" -f body.json
```

## wrk / wrk2 (fixed connections; wrk2 adds -R for constant rate)
```bash
wrk2 -t4 -c50 -d10m -R50 --latency -H "Authorization: Bearer $TOKEN" $BASE/api/products?page=1
# POST via Lua: wrk -s post.lua ...   (wrk.method="POST"; wrk.body=...; wrk.headers["Content-Type"]="application/json")
```
Paste the `Latency Distribution` block into the results table by hand (no JSON).

## JMeter (headless)
```bash
jmeter -n -t perf.jmx -Jhost=$HOST -Jthreads=50 -Jduration=600 -l results.jtl -e -o report/
# perf.jmx: Thread Group (threads, ramp 120 s, duration), HTTP Header Manager (Authorization), one HTTP Sampler per inventory row, Constant Throughput Timer for RPS, Summary Report listener.
```
Read p50/p95/p99 from `report/statistics.json` (`pct1ResTime`, `pct2ResTime`, `pct3ResTime`, `errorPct`, `throughput`).

## autocannon (Node shops)
```bash
npx autocannon -c 50 -d 600 -H "Authorization=Bearer $TOKEN" --json $BASE/api/products?page=1 > ac.json
```
`ac.json`: `latency.p50/p97_5/p99`, `requests.average`, `errors`, `non2xx`.

## Locust (Python shops)
```bash
locust -f locustfile.py --headless -u 50 -r 5 -t 10m --host $BASE --csv=locust
```
`locust_stats.csv` has 50%/95%/99% columns per endpoint.

## Frontend: Core Web Vitals
```bash
npx lighthouse $BASE/dashboard --preset=desktop --output=json --output-path=lh.json --extra-headers='{"Authorization":"Bearer '$TOKEN'"}'
npx lighthouse $BASE/dashboard --form-factor=mobile --throttling-method=simulate --output=json --output-path=lh-mobile.json
# read: audits['largest-contentful-paint'].numericValue, audits['cumulative-layout-shift'].numericValue, audits['interaction-to-next-paint'] (lab: 'total-blocking-time'), audits['server-response-time']
npx unlighthouse --site $BASE            # whole-site crawl
# WebPageTest: webpagetest test $BASE/dashboard --location Dulles:Chrome --connectivity 4G --runs 3
```
Field data: CrUX (`https://developer.chrome.com/docs/crux`) if the site is public; else `web-vitals` library reporting to the analytics endpoint.
API calls per page: DevTools > Network > XHR filter, reload, count; duplicates = same URL more than once.

## Sampling the server during the run
Reuse `audit-backend-resource-leak/references/load-test-recipes.md` samplers (dotnet-counters, jstat, `process.memoryUsage`, psutil) plus CPU: `top -b -d 15 -p <pid>`, `docker stats --no-stream`, `kubectl top pod`. Pool saturation: EF/Hikari/pg pool metrics (`Hikari pool.ActiveConnections`, `pg_stat_activity`, `Microsoft.Data.SqlClient` `active-hard-connections`).

## Interpreting
- p95 rises with RPS while CPU is low -> waiting on something: pool exhaustion, lock, sequential upstream calls, sync-over-async.
- p95 rises with CPU near 100% -> compute/serialization/allocation; profile (dotnet-trace, async-profiler, `--cpu-prof`, py-spy).
- Error rate jumps at a fixed concurrency -> pool or thread-pool limit; compare with `references/<stack>.md` pool defaults.
- Fine at 1 instance, worse at 2 -> shared-state or session affinity problem (see STATE findings).
