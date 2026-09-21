#!/usr/bin/env python3
"""Load-test recipe runner for audit-backend-resource-leak.

Two sub-commands:

  plan   Print (or write) the 15-minute leak-confirmation procedure for a stack:
         load-driver command, sampler command, GC-force command, thresholds.
         python leak_loadtest.py plan --stack dotnet [--base-url https://host] [--rps 50]
                [--endpoints /api/a,/api/b] [--out plan.md]

  grade  Score a samples CSV against the pass/fail thresholds and print a
         Markdown verdict table.
         python leak_loadtest.py grade samples.csv [--format generic|dotnet-counters]
                [--baseline-minutes 5] [--out result.md]

Generic CSV columns (header optional, missing columns allowed):
  ts,working_set_bytes,gen2_count,handles,threads
  ts = unix seconds or ISO-8601. dotnet-counters CSV (--format dotnet-counters)
  is the `dotnet-counters collect --format csv` layout (Timestamp,Provider,
  Counter Name,Counter Type,Value) and is pivoted automatically.

Thresholds (see references/load-test-recipes.md):
  working set slope after baseline  < 2 MB/min pass, >= 5 MB/min fail, else inconclusive
  last-5-min mean vs first-5-min-after-baseline mean  within 10% pass
  handles / threads  within +/-10% of post-baseline mean pass
  gen2: heap-after-gen2 is not derivable from counts alone; the grader reports
  gen2 rate and flags a working set that rises while gen2 keeps firing.

Read-only: reads the CSV, writes only the --out file. Python 3 stdlib only.
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime

MB = 1024 * 1024

DRIVERS = {
    "k6": "k6 run --vus 20 --duration 15m -e BASE={base} -e TOKEN=$TOKEN script.js\n"
          "# script.js:\n# import http from 'k6/http';\n# const eps = {eps_json};\n"
          "# export default () => {{ for (const p of eps) http.get(`${{__ENV.BASE}}${{p}}`, {{headers: {{Authorization: `Bearer ${{__ENV.TOKEN}}`}}}}); }};",
    "bombardier": "bombardier -c 20 -r {rps} -d 15m -H \"Authorization: Bearer $TOKEN\" {base}{ep0}",
    "wrk": "wrk -t4 -c20 -d15m -H \"Authorization: Bearer $TOKEN\" {base}{ep0}",
    "jmeter": "jmeter -n -t leak.jmx -Jduration=900 -Jthreads=20 -Jhost={host} -l results.jtl   # Thread Group: 20 threads, loop forever, duration 900; HTTP Header Manager with Authorization; one sampler per endpoint",
}

SAMPLERS = {
    "dotnet": (
        "dotnet-counters collect -p <pid> --refresh-interval 15 --format csv -o samples.csv "
        "--counters \"System.Runtime[working-set,gen-2-gc-count,gc-heap-size,threadpool-thread-count,alloc-rate]\"\n"
        "# handles: Windows  handle.exe -p <pid> | find /c \"File\"   Linux  ls /proc/<pid>/fd | wc -l\n"
        "# before/after: dotnet-gcdump collect -p <pid> -o before.gcdump ... -o after.gcdump; dotnet-gcdump report after.gcdump | head -40",
        "dotnet-gcdump collect -p <pid> -o final.gcdump   # forces a full GC; then take the last sample",
        "grade samples.csv --format dotnet-counters",
    ),
    "java-spring": (
        "while true; do echo \"$(date +%s),$(ps -o rss= -p <pid>)000,$(jstat -gc <pid> | awk 'NR==2{print $15}'),$(ls /proc/<pid>/fd | wc -l),$(jcmd <pid> Thread.print | grep -c tid=)\" >> samples.csv; sleep 15; done\n"
        "# also: jcmd <pid> GC.class_histogram | head -30 before and after; spring.datasource.hikari.leak-detection-threshold=30000",
        "jcmd <pid> GC.run",
        "grade samples.csv",
    ),
    "node-express": (
        "node --trace-gc dist/main.js 2>&1 | tee gc.log   # Mark-sweep 'heap after' should plateau\n"
        "while true; do echo \"$(date +%s),$(ps -o rss= -p <pid>)000,,$(lsof -p <pid> | wc -l)\" >> samples.csv; sleep 15; done\n"
        "# or in-process: setInterval(() => fs.appendFileSync('samples.csv', [Date.now(), process.memoryUsage().rss, 0, process.getActiveResourcesInfo().length].join(',')+'\\n'), 15000)\n"
        "# heap snapshots: node --heapsnapshot-signal=SIGUSR2 ...; kill -USR2 <pid> before and after",
        "node --expose-gc ... then global.gc() (or DevTools > Memory > collect garbage)",
        "grade samples.csv",
    ),
    "python-django": (
        "python -c \"import psutil,time; p=psutil.Process(<pid>); f=open('samples.csv','a')\n"
        "while True: f.write(f'{int(time.time())},{p.memory_info().rss},,{p.num_fds() if hasattr(p,\\\"num_fds\\\") else len(p.open_files())},{p.num_threads()}\\n'); f.flush(); time.sleep(15)\"\n"
        "# in-process sites: tracemalloc.start(25); s1=take_snapshot() ... s2.compare_to(s1,'lineno')[:20]\n"
        "# run gunicorn with --max-requests 0 so recycling does not hide the slope",
        "gc.collect() via a management command or debug endpoint",
        "grade samples.csv",
    ),
}

THRESHOLDS_MD = """| Metric | Pass | Fail |
|---|---|---|
| Working set / RSS slope (minutes 5-15) | < 2 MB/min and last-5-min mean within 10% of minutes 5-10 mean | >= 5 MB/min or monotonic rise |
| Gen2 / full GC | rate stable; heap after gen2 within 15% of warm-up baseline | heap-after-gen2 rises each collection |
| Handle / FD count | flat within +/-10% after warm-up | rises with request count |
| Thread count | flat | rises with request count |
| Post-GC residual | within 15% of baseline | > 15% above baseline |
"""


def plan(args):
    stack = args.stack
    if stack not in SAMPLERS:
        print(f"unknown stack '{stack}'; choose from {sorted(SAMPLERS)}", file=sys.stderr)
        return 2
    eps = [e.strip() for e in args.endpoints.split(",") if e.strip()] or ["/api/health"]
    base = args.base_url.rstrip("/")
    host = base.split("//", 1)[-1].split("/", 1)[0] or "host"
    sampler, force_gc, grade_cmd = SAMPLERS[stack]
    lines = [f"# 15-minute leak confirmation plan ({stack})", "",
             f"Target: `{base}`  Endpoints: {', '.join('`' + e + '`' for e in eps)}  Rate: {args.rps} RPS  Steady state: 15 min (+2 min warm-up)", "",
             "## Steps",
             "1. Start the service in production mode (Release build, production env/profile, debug query logging off). Note the PID.",
             "2. Start the sampler (below) writing samples.csv every 15 s.",
             "3. Warm-up 2 min at ~20% RPS (these samples are excluded by --baseline-minutes).",
             "4. Steady state 15 min at target RPS with one of the load drivers below.",
             "5. Stop the load, wait 60 s, force a GC, take the final sample.",
             f"6. `python scripts/leak_loadtest.py {grade_cmd} --baseline-minutes 5 --out audit/evidence/audit-backend-resource-leak/loadtest-result.md`", "",
             "## Load driver (pick one)", "```bash"]
    for name, tmpl in DRIVERS.items():
        lines.append(f"# {name}")
        lines.append(tmpl.format(base=base, host=host, rps=args.rps, ep0=eps[0], eps_json=json.dumps(eps)))
        lines.append("")
    lines += ["```", "", "## Sampler", "```bash", sampler, "```", "",
              "## Force GC before final sample", "```bash", force_gc, "```", "",
              "## Thresholds", THRESHOLDS_MD]
    text = "\n".join(lines)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(args.out)
    else:
        print(text)
    return 0


def _parse_ts(v):
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(v[:26], fmt).timestamp()
        except ValueError:
            continue
    return None


def _num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def load_generic(path):
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = None
        for rec in reader:
            if not rec:
                continue
            if header is None and _parse_ts(rec[0]) is None:
                header = [h.strip().lower() for h in rec]
                continue
            if header is None:
                header = ["ts", "working_set_bytes", "gen2_count", "handles", "threads"]
            d = dict(zip(header, rec))
            ts = _parse_ts(d.get("ts") or d.get("timestamp"))
            if ts is None:
                continue
            rows.append({"ts": ts,
                         "ws": _num(d.get("working_set_bytes") or d.get("working_set") or d.get("rss")),
                         "gen2": _num(d.get("gen2_count") or d.get("gen2")),
                         "handles": _num(d.get("handles") or d.get("fds")),
                         "threads": _num(d.get("threads"))})
    return rows


def load_dotnet_counters(path):
    """Pivot dotnet-counters CSV (Timestamp,Provider,Counter Name,Counter Type,Value)."""
    by_ts = {}
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for rec in reader:
            if len(rec) < 5 or rec[0].lower() == "timestamp":
                continue
            ts = _parse_ts(rec[0])
            if ts is None:
                continue
            name = rec[2].strip().lower()
            val = _num(rec[4])
            row = by_ts.setdefault(ts, {"ts": ts, "ws": None, "gen2": None, "handles": None, "threads": None})
            if "working set" in name:
                row["ws"] = val * MB if val is not None and val < 1e7 else val  # dotnet-counters reports MB
            elif "gen 2 gc count" in name:
                row["gen2"] = val
            elif "threadpool thread count" in name:
                row["threads"] = val
            elif "handle" in name:
                row["handles"] = val
    return [by_ts[k] for k in sorted(by_ts)]


def _slope(points):
    """Least-squares slope in units per second."""
    n = len(points)
    if n < 2:
        return 0.0
    sx = sum(p[0] for p in points); sy = sum(p[1] for p in points)
    sxx = sum(p[0] * p[0] for p in points); sxy = sum(p[0] * p[1] for p in points)
    den = n * sxx - sx * sx
    return 0.0 if den == 0 else (n * sxy - sx * sy) / den


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def grade(args):
    rows = load_dotnet_counters(args.path) if args.format == "dotnet-counters" else load_generic(args.path)
    if len(rows) < 4:
        print("need at least 4 samples", file=sys.stderr)
        return 2
    t0 = rows[0]["ts"]
    steady = [r for r in rows if r["ts"] - t0 >= args.baseline_minutes * 60]
    if len(steady) < 4:
        steady = rows
    t_start, t_end = steady[0]["ts"], steady[-1]["ts"]
    span = t_end - t_start
    verdicts = []

    ws_pts = [(r["ts"], r["ws"]) for r in steady if r["ws"] is not None]
    if len(ws_pts) >= 4:
        slope_mb_min = _slope(ws_pts) * 60 / MB
        first5 = _mean([v for t, v in ws_pts if t - t_start < 300])
        last5 = _mean([v for t, v in ws_pts if t_end - t <= 300])
        drift = (last5 - first5) / first5 * 100 if first5 else 0.0
        monotonic = all(ws_pts[i][1] <= ws_pts[i + 1][1] for i in range(len(ws_pts) - 1)) and len(ws_pts) > 6
        if slope_mb_min >= 5 or monotonic:
            v = "FAIL"
        elif slope_mb_min < 2 and abs(drift) <= 10:
            v = "PASS"
        else:
            v = "INCONCLUSIVE"
        verdicts.append(("Working set / RSS", f"slope {slope_mb_min:.2f} MB/min, drift {drift:+.1f}% (first-5 {first5 / MB:.0f} MB -> last-5 {last5 / MB:.0f} MB){', monotonic rise' if monotonic else ''}", v))
    else:
        verdicts.append(("Working set / RSS", "no data", "NOT MEASURED"))

    g_pts = [(r["ts"], r["gen2"]) for r in steady if r["gen2"] is not None]
    if len(g_pts) >= 2 and span > 0:
        gen2_rate = (g_pts[-1][1] - g_pts[0][1]) / (span / 60)
        ws_v = verdicts[0][2]
        note = f"{gen2_rate:.2f} gen2/min"
        if gen2_rate > 0 and ws_v == "FAIL":
            v, note = "FAIL", note + "; gen2 keeps firing while working set rises -> managed heap leak, take a heap diff"
        elif gen2_rate == 0 and ws_v == "FAIL":
            v, note = "FAIL", note + "; no gen2 yet working set rises -> native/unmanaged growth (handles, pinned buffers)"
        else:
            v = "PASS" if ws_v == "PASS" else "INFO"
        verdicts.append(("Gen2 / full GC", note, v))
    else:
        verdicts.append(("Gen2 / full GC", "no data", "NOT MEASURED"))

    for key, label in (("handles", "Handle / FD count"), ("threads", "Thread count")):
        pts = [(r["ts"], r[key]) for r in steady if r[key] is not None]
        if len(pts) >= 4:
            m = _mean([v for _, v in pts])
            first = _mean([v for t, v in pts if t - t_start < 300]) or m
            last = _mean([v for t, v in pts if t_end - t <= 300]) or m
            pct = (last - first) / first * 100 if first else 0.0
            v = "PASS" if abs(pct) <= 10 else "FAIL"
            verdicts.append((label, f"{first:.0f} -> {last:.0f} ({pct:+.1f}%)", v))
        else:
            verdicts.append((label, "no data", "NOT MEASURED"))

    overall = "FAIL" if any(v == "FAIL" for _, _, v in verdicts) else (
        "INCONCLUSIVE" if any(v == "INCONCLUSIVE" for _, _, v in verdicts) else "PASS")
    out = [f"### Load-test results ({os.path.basename(args.path)})",
           f"Samples: {len(rows)} total, {len(steady)} after {args.baseline_minutes}-min baseline, steady span {span / 60:.1f} min.", "",
           "| Metric | Observed | Verdict |", "|---|---|---|"]
    out += [f"| {m} | {o} | {v} |" for m, o, v in verdicts]
    out += ["", f"**Overall: {overall}**", "",
            "INCONCLUSIVE: extend to 30 min or repeat at 2x RPS. FAIL: take a heap diff (gcdump / MAT / DevTools / tracemalloc) and grep for the holder of the growing type."]
    text = "\n".join(out)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(args.out)
    else:
        print(text)
    return 0 if overall == "PASS" else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--stack", required=True, help="dotnet | java-spring | node-express | python-django")
    p.add_argument("--base-url", default="https://localhost:5001")
    p.add_argument("--rps", type=int, default=50)
    p.add_argument("--endpoints", default="", help="comma-separated paths")
    p.add_argument("--out")
    p = sub.add_parser("grade")
    p.add_argument("path")
    p.add_argument("--format", choices=["generic", "dotnet-counters"], default="generic")
    p.add_argument("--baseline-minutes", type=float, default=5)
    p.add_argument("--out")
    a = ap.parse_args()
    return plan(a) if a.cmd == "plan" else grade(a)


if __name__ == "__main__":
    sys.exit(main())
