#!/usr/bin/env python3
"""Rate-limited probe sender for LLM/agentic application testing.

Sends a list of {id, category, payload} probes to a single target endpoint,
logging each request/response pair to an evidence JSON file in the shape
shared-llm-probe-runner's SKILL.md defines. Standard library only (urllib) so
it runs with no extra install.

Usage:
    python probe_runner.py --url <endpoint> --probes <probes.json> \
        --out audit/llm/evidence/<calling-skill>.json [--min-interval 2.5] \
        [--header "Authorization: Bearer ..."]

probes.json: [{"id": "...", "category": "...", "payload": {...or "text"}}]

This script only SENDS what it is given and records what came back - it makes
no judgment about whether a response is a finding. That call belongs to the
calling skill and, ultimately, audit-finding-writer.
"""
import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def send_one(url, payload, headers, timeout=30):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for h in headers:
        name, _, value = h.partition(":")
        req.add_header(name.strip(), value.strip())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        return None, str(e.reason)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--probes", required=True, help="path to probes.json")
    ap.add_argument("--out", required=True, help="path to write evidence JSON")
    ap.add_argument("--min-interval", type=float, default=2.5,
                     help="minimum seconds between requests (default 2.5)")
    ap.add_argument("--header", action="append", default=[],
                     help="extra header, e.g. 'Authorization: Bearer xyz' (repeatable)")
    args = ap.parse_args()

    with open(args.probes, "r", encoding="utf-8") as fh:
        probes = json.load(fh)

    evidence = []
    last_sent = 0.0
    for probe in probes:
        wait = args.min_interval - (time.time() - last_sent)
        if wait > 0:
            time.sleep(wait)

        status, raw_response = send_one(args.url, probe.get("payload", probe.get("text")), args.header)
        last_sent = time.time()

        entry = {
            "id": probe.get("id"),
            "category": probe.get("category"),
            "payload": probe.get("payload", probe.get("text")),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "response": raw_response,
            "observed_behavior": None,  # fill in after reviewing the response
        }
        evidence.append(entry)

        if status == 429:
            print(f"warning: 429 on probe {entry['id']}; backing off 10s", flush=True)
            time.sleep(10)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, indent=2)
    print(f"wrote {len(evidence)} probe results to {args.out}")
    print("next: fill in 'observed_behavior' for each entry before handing off to audit-finding-writer")


if __name__ == "__main__":
    main()
