#!/usr/bin/env python3
"""Cross-account authorization probe (IDOR / broken-access-control tester).

Authenticates as user A and calls each endpoint in an inventory using user B's
identifiers. A well-behaved API answers 403 or 404; a 2xx that returns B's data
is a broken access control (IDOR) or a missing-auth finding.

SAFETY: this script NEVER runs on its own. It does nothing unless the user
supplies a base URL on the command line. Point it only at a disposable test
environment with throwaway data - it issues real reads and writes.

Usage:
    python authz_probe.py --base-url http://localhost:5000 \
        --token-a "<JWT for user A>"    --token-b "<JWT for user B>" \
        --ids-b ids-b.json             --endpoints endpoints.probe.json \
        [--also-anon] [--timeout 10] [--out results.json]

Credentials may be given inline (--token-a/--token-b) or from a file
(--token-a-file/--token-b-file); a file lets you keep secrets out of shell
history. --ids-b is a JSON object mapping id-parameter names to user B's values,
e.g. {"order": 1002, "user": 2}.

Endpoint inventory shape (produced by audit-endpoint-inventory (endpoints.probe.json), then hand-verified):
{
  "base_path": "",
  "endpoints": [
    {"method": "GET", "path": "/api/orders/{id}", "auth_required": true,
     "roles": [], "ownership_check": "N", "id_params": {"id": "order"},
     "body": {"role": "Admin"}}
  ]
}
- id_params maps a {placeholder} in the path to a key in --ids-b. The inventory
  names the resource ({"id": "order"}), so --ids-b needs one key per distinct value.
- body (optional) is sent as JSON; use it to probe mass-assignment/privilege
  fields (e.g. a self-service profile endpoint that accepts "role").

Verdict per endpoint (printed as a pass/fail table):
  PASS  - blocked (401/403/404) when it should be, as expected.
  FAIL  - 2xx reaching user B's resource: likely IDOR / missing ownership check.
  FAIL  - 2xx with no token (when --also-anon) on an auth_required endpoint.
  WARN  - unexpected status (5xx, redirect); inspect by hand.
Read-only with respect to the repo; it only touches the target URL you name.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request


def _load_token(inline, file_path):
    if inline:
        return inline
    if file_path:
        with open(file_path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    return None


def _fill_path(path, id_params, ids_b):
    for placeholder, key in (id_params or {}).items():
        if key not in ids_b:
            raise KeyError(f"ids-b is missing '{key}' needed for {{{placeholder}}} in {path}")
        path = path.replace("{" + placeholder + "}", str(ids_b[key]))
    return path


def _request(method, url, token, body, timeout):
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(4096).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2048).decode("utf-8", "ignore") if e.fp else ""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, str(e)


def classify(ep, status_a, also_anon, status_anon):
    """Return (verdict, note)."""
    auth_required = ep.get("auth_required", True)
    if also_anon and auth_required and status_anon is not None and 200 <= status_anon < 300:
        return "FAIL", f"reachable with NO token (status {status_anon}); missing authentication"
    if status_a is None:
        return "WARN", "request error (see raw)"
    if 200 <= status_a < 300:
        if ep.get("ownership_check") == "N" or not auth_required:
            return "FAIL", f"user A got 2xx ({status_a}) on user B's resource; broken access control"
        return "WARN", f"2xx ({status_a}) - confirm the body is not user B's data"
    if status_a in (401, 403, 404):
        return "PASS", f"blocked as expected ({status_a})"
    return "WARN", f"unexpected status {status_a}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", required=True, help="target base URL (test env only)")
    ap.add_argument("--token-a"); ap.add_argument("--token-a-file")
    ap.add_argument("--token-b"); ap.add_argument("--token-b-file")
    ap.add_argument("--ids-b", required=True, help="JSON file: id-param name -> user B's value")
    ap.add_argument("--endpoints", required=True, help="endpoint inventory JSON")
    ap.add_argument("--also-anon", action="store_true", help="also call each endpoint with no token")
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--out", help="write full results JSON here")
    args = ap.parse_args()

    token_a = _load_token(args.token_a, args.token_a_file)
    if not token_a:
        print("ERROR: provide --token-a or --token-a-file (user A's identity).", file=sys.stderr)
        return 2
    with open(args.ids_b, "r", encoding="utf-8") as fh:
        ids_b = json.load(fh)
    with open(args.endpoints, "r", encoding="utf-8") as fh:
        inv = json.load(fh)

    base = args.base_url.rstrip("/") + inv.get("base_path", "")
    rows, results = [], []
    for ep in inv.get("endpoints", []):
        try:
            path = _fill_path(ep["path"], ep.get("id_params"), ids_b)
        except KeyError as e:
            rows.append(("SKIP", ep["method"], ep["path"], str(e)))
            continue
        url = base + path
        status_a, raw_a = _request(ep["method"], url, token_a, ep.get("body"), args.timeout)
        status_anon = None
        if args.also_anon:
            status_anon, _ = _request(ep["method"], url, None, ep.get("body"), args.timeout)
        verdict, note = classify(ep, status_a, args.also_anon, status_anon)
        rows.append((verdict, ep["method"], path, note))
        results.append({"method": ep["method"], "path": path, "status_a": status_a,
                        "status_anon": status_anon, "verdict": verdict, "note": note,
                        "raw_a": raw_a[:500]})

    w = max((len(r[2]) for r in rows), default=20)
    print(f"{'VERDICT':7} {'METHOD':7} {'PATH':{w}} NOTE")
    print("-" * (7 + 1 + 7 + 1 + w + 1 + 4))
    for verdict, method, path, note in rows:
        print(f"{verdict:7} {method:7} {path:{w}} {note}")
    fails = sum(1 for r in rows if r[0] == "FAIL")
    print(f"\n{fails} FAIL, "
          f"{sum(1 for r in rows if r[0] == 'WARN')} WARN, "
          f"{sum(1 for r in rows if r[0] == 'PASS')} PASS of {len(rows)}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"base_url": args.base_url, "results": results}, fh, indent=2)
        print(f"wrote {args.out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
