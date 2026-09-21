# Load-test recipes for leak confirmation

The goal is not throughput; it is a flat line. Run a fixed, moderate load for
15 minutes and watch process metrics. Use whichever load tool is installed; the
sampling side is what differs per stack. `scripts/leak_loadtest.py plan --stack <id>`
prints the matching subset of this file with the target URL filled in.

## Procedure (all stacks)
1. Start the service in Release/production mode with production-like config (`ASPNETCORE_ENVIRONMENT=Production`, `NODE_ENV=production`, `DEBUG=False`, `spring.profiles.active=prod`). Debug-mode query logs are themselves a leak.
2. Record the PID. Start the sampler (per stack below) writing `samples.csv` with columns `ts,working_set_bytes,gen2_count,handles,threads` (missing columns allowed; the grader skips them).
3. Warm-up: 2 min at ~20% of the target RPS. Discard (the grader uses `--baseline-minutes`).
4. Steady state: 15 min at target RPS against the endpoint set (the endpoints named in the findings, else top 5 by traffic; include one upload and one download if present).
5. Stop the load. Wait 60 s. Force a GC (command per stack). Take one more sample.
6. `python scripts/leak_loadtest.py grade samples.csv --baseline-minutes 5 --out audit/evidence/audit-backend-resource-leak/loadtest-result.md`.

## Thresholds
| Metric | Pass | Fail |
|---|---|---|
| Working set / RSS slope, minutes 5-15 | < 2 MB/min and last-5-min mean within 10% of minutes 5-10 mean | >= 5 MB/min, or monotonic rise every sample |
| Gen2 / full-GC | count rate stable; heap after each gen2 within 15% of warm-up baseline | heap-after-gen2 rises each collection |
| Handle / FD count | flat within +/-10% after warm-up | rises with request count |
| Thread count | flat | rises with request count |
| Post-GC residual (step 5) | within 15% of warm-up baseline | > 15% above baseline |
Between 2 and 5 MB/min is "inconclusive": extend to 30 min or repeat at 2x RPS.

## Load drivers (pick one)
```bash
# k6 - constant arrival rate, 15 min
k6 run --vus 20 --duration 15m -e BASE=https://host script.js
# script.js: import http from 'k6/http'; export default () => { http.get(`${__ENV.BASE}/api/products?page=1`, {headers:{Authorization:`Bearer ${__ENV.TOKEN}`}}); }

# bombardier - fixed rate
bombardier -c 20 -r 50 -d 15m -H "Authorization: Bearer $TOKEN" https://host/api/products?page=1

# wrk - fixed connections, script for headers/POST
wrk -t4 -c20 -d15m -H "Authorization: Bearer $TOKEN" https://host/api/products?page=1
wrk -t4 -c20 -d15m -s post.lua https://host/api/orders      # post.lua sets wrk.method/body/headers

# JMeter - headless
jmeter -n -t leak.jmx -Jduration=900 -Jthreads=20 -Jhost=host -l results.jtl
# leak.jmx: Thread Group (20 threads, loop forever, duration 900), HTTP Header Manager (Authorization), HTTP Samplers per endpoint.

# autocannon (Node shops) / hey
npx autocannon -c 20 -d 900 -H "Authorization=Bearer $TOKEN" https://host/api/products
hey -z 15m -c 20 -H "Authorization: Bearer $TOKEN" https://host/api/products
```

## Samplers per stack

### .NET
```bash
dotnet tool install -g dotnet-counters dotnet-gcdump dotnet-dump
dotnet-counters collect -p <pid> --refresh-interval 15 --format csv -o samples.csv \
  --counters "System.Runtime[working-set,gen-2-gc-count,gc-heap-size,threadpool-thread-count,alloc-rate]"
# grade with: python scripts/leak_loadtest.py grade samples.csv --format dotnet-counters
# handles (not a runtime counter): Windows  handle.exe -p <pid> | find /c "File"   Linux  ls /proc/<pid>/fd | wc -l
# before/after object counts: dotnet-gcdump collect -p <pid> -o before.gcdump   ... after.gcdump ; dotnet-gcdump report after.gcdump | head -40
# force GC before final sample: dotnet-gcdump collect triggers a full GC as a side effect
# root of a growing type: dotnet-dump collect -p <pid>; dotnet-dump analyze core --command "dumpheap -stat" "gcroot <addr>"
```
Watch: `Working Set`, `Gen 2 GC Count`, `GC Heap Size` (should saw-tooth around a flat mean), `ThreadPool Thread Count`.

### Java / Spring
```bash
# sampler (15 s)
while true; do echo "$(date +%s),$(ps -o rss= -p <pid>)000,$(jstat -gc <pid> | awk 'NR==2{print $15}'),$(ls /proc/<pid>/fd | wc -l),$(jcmd <pid> Thread.print | grep -c tid=)" >> samples.csv; sleep 15; done
jstat -gc <pid> 15000                      # OU = old-gen used, FGC = full GC count
jcmd <pid> GC.heap_info                    # human-readable heap
jcmd <pid> GC.class_histogram | head -30   # before and after; diff instance counts
jcmd <pid> GC.run                          # force GC before the final sample
jcmd <pid> VM.native_memory summary        # off-heap (needs -XX:NativeMemoryTracking=summary)
jcmd <pid> GC.heap_dump /tmp/after.hprof   # Eclipse MAT > Leak Suspects
```
Also set `spring.datasource.hikari.leak-detection-threshold=30000` for the run.

### Node
```bash
node --inspect --trace-gc dist/main.js 2>&1 | tee gc.log     # Mark-sweep lines: heap after GC should plateau
# sampler inside the app (env-gated), 15 s:
# setInterval(() => require('fs').appendFileSync('samples.csv', [Date.now(), process.memoryUsage().rss, 0, process.getActiveResourcesInfo().length].join(',')+'\n'), 15000)
# or from the shell:  while true; do echo "$(date +%s),$(ps -o rss= -p <pid>)000,,$(lsof -p <pid> | wc -l)" >> samples.csv; sleep 15; done
kill -USR2 <pid>                          # with --heapsnapshot-signal=SIGUSR2: writes Heap.*.heapsnapshot before/after
node --expose-gc ... ; global.gc()        # force GC before final sample (or DevTools "collect garbage")
npx clinic heapprofiler -- node dist/main.js
```
Compare snapshots in Chrome DevTools > Memory > "Objects allocated between snapshot 1 and 2", sort by retained size.

### Python / Django
```bash
# sampler (psutil), 15 s:
python - <<'EOF'
import psutil, time, gc
p = psutil.Process(<pid>)
with open('samples.csv','a') as f:
    while True:
        f.write(f"{int(time.time())},{p.memory_info().rss},,{p.num_fds() if hasattr(p,'num_fds') else len(p.open_files())},{p.num_threads()}\n"); f.flush(); time.sleep(15)
EOF
# in-process allocation sites (env-gated at boot): 
#   import tracemalloc; tracemalloc.start(25); s1 = tracemalloc.take_snapshot()
#   ... after steady state: s2 = tracemalloc.take_snapshot(); for st in s2.compare_to(s1,'lineno')[:20]: print(st)
memray run -o out.bin -m gunicorn app.wsgi ; memray flamegraph out.bin     # Linux/macOS
python -c "import gc; gc.collect()"        # run via a management command / debug endpoint before the final sample
```
Gunicorn: run with `--max-requests 0` for the test so worker recycling does not hide the slope.

## Interpreting
- Saw-tooth with a flat floor: healthy.
- Saw-tooth whose floor rises: managed-heap leak -> heap diff (gcdump / MAT / DevTools / tracemalloc) names the type; grep the repo for who holds it.
- RSS rises while managed heap is flat: native/unmanaged (ImageSharp, SQL client, zlib, file handles) -> handle count and native memory tracking.
- Threads rise: per-request executor/timer -> TIMER class.
- Handles rise: DISP class; `lsof`/`handle.exe` output names the file or socket.
