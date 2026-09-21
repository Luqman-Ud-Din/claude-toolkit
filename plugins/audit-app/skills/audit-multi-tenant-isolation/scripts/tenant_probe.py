#!/usr/bin/env python3
"""Cross-tenant isolation probe.

Authenticates as a user in tenant A and attempts to reach tenant B's data
through every endpoint - read, write, list, search, download, export - including
with TAMPERED tenant identifiers (tenant B's id injected into the body, query
string, or a header). A correct multi-tenant API answers 403/404 or silently
returns only tenant A's rows; a 2xx that exposes or modifies tenant B's data is
a cross-tenant leak.

SAFETY: this script NEVER runs on its own. It does nothing unless the user
supplies a base URL. Point it only at a disposable test environment seeded with
two throwaway tenants - it issues real reads AND writes.

Usage:
    python tenant_probe.py --base-url http://localhost:5000 \
        --tenants tenants.json --endpoints endpoints.json \
        [--tenant-header X-Tenant-Id] [--timeout 10] [--out results.json]

tenants.json:
{
  "tenant_a": {"token": "<JWT A>", "ids": {"document": 5001, "invoice": 7001}},
  "tenant_b": {"token": "<JWT B>", "ids": {"document": 5002, "invoice": 7002}}
}
Tokens may instead be file paths via {"token_file": "..."}.

endpoints.json (audit-endpoint-inventory endpoints.probe.json plus tamper values):
{
  "base_path": "",
  "endpoints": [
    {"method":"GET","path":"/api/documents/{id}","operation":"read",
     "id_params":{"id":"document"}},
    {"method":"POST","path":"/api/invoices/create","operation":"write",
     "body":{"tenantId":"{tenant_b}","total":1}}     # {tenant_b} is substituted
  ]
}
Placeholders in body/query/path: {id_param} -> tenant B's id from tenants.json;
{tenant_b} / {tenant_a} -> that tenant's numeric id (from ids, key "tenant" or
first id). The point of {tenant_b} is to TAMPER: send tenant B's identifier
while authenticated as tenant A.

For each endpoint two calls are made as tenant A:
  1. "as-A"      - untampered, using tenant B's resource ids in the path.
  2. "tampered"  - additionally injecting tenant B's tenant id into body, query,
                   and the --tenant-header (if given).
Verdicts (pass/fail table):
  PASS  - blocked (401/403/404) or returned nothing of tenant B's.
  FAIL  - 2xx reaching/altering tenant B's data: cross-tenant leak.
  WARN  - 2xx that needs a human to confirm the body is tenant B's.
Read-only w.r.t. the repo; only touches the URL you name.
"""
import argparse
import copy
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def _token(t):
    if "token_file" in t:
        with open(t["token_file"], "r", encoding="utf-8") as fh:
            return fh.read().strip()
    return t.get("token", "")


def _tenant_num(t):
    ids = t.get("ids", {})
    if "tenant" in ids:
        return ids["tenant"]
    return next(iter(ids.values()), None)


def _sub_scalar(val, ids_b, tb_num, ta_num):
    if isinstance(val, str):
        out = val.replace("{tenant_b}", str(tb_num)).replace("{tenant_a}", str(ta_num))
        for k, v in ids_b.items():
            out = out.replace("{" + k + "}", str(v))
        return out
    return val


def _sub_obj(obj, ids_b, tb_num, ta_num):
    if obj is None:
        return None
    obj = copy.deepcopy(obj)
    for k, v in obj.items():
        obj[k] = _sub_scalar(v, ids_b, tb_num, ta_num)
    return obj


def _fill_path(path, id_params, ids_b):
    for placeholder, key in (id_params or {}).items():
        path = path.replace("{" + placeholder + "}", str(ids_b[key]))
    return path


def _request(method, url, token, body, headers, timeout):
    hdrs = {"Accept": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    hdrs.update(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(4096).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2048).decode("utf-8", "ignore") if e.fp else ""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, str(e)


def classify(status, kind):
    if status is None:
        return "WARN", "request error (see raw)"
    if status in (401, 403, 404):
        return "PASS", f"blocked ({status})"
    if 200 <= status < 300:
        return "FAIL", f"2xx ({status}) reached tenant B via {kind}; cross-tenant leak"
    return "WARN", f"unexpected status {status}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", required=True, help="target base URL (test env only)")
    ap.add_argument("--tenants", required=True, help="tenants.json with token + ids for A and B")
    ap.add_argument("--endpoints", required=True, help="data-access-path inventory JSON")
    ap.add_argument("--tenant-header", help="header name to tamper, e.g. X-Tenant-Id")
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--out")
    args = ap.parse_args()

    with open(args.tenants, "r", encoding="utf-8") as fh:
        tenants = json.load(fh)
    with open(args.endpoints, "r", encoding="utf-8") as fh:
        inv = json.load(fh)

    a, b = tenants["tenant_a"], tenants["tenant_b"]
    token_a = _token(a)
    if not token_a:
        print("ERROR: tenant_a token missing.", file=sys.stderr)
        return 2
    ids_b = b.get("ids", {})
    tb_num, ta_num = _tenant_num(b), _tenant_num(a)
    base = args.base_url.rstrip("/") + inv.get("base_path", "")

    rows, results = [], []
    for ep in inv.get("endpoints", []):
        try:
            path = _fill_path(ep["path"], ep.get("id_params"), ids_b)
        except KeyError as e:
            rows.append(("SKIP", ep["method"], ep.get("operation", ""), ep["path"], f"missing id {e}"))
            continue
        url = base + path
        op = ep.get("operation", "")

        # Call 1: as tenant A, untampered (uses tenant B ids in the path only).
        body1 = _sub_obj(ep.get("body"), ids_b, tb_num, ta_num) if "{tenant" not in json.dumps(ep.get("body") or {}) else None
        q = ep.get("query")
        u1 = url + ("?" + urllib.parse.urlencode({k: _sub_scalar(v, ids_b, tb_num, ta_num) for k, v in q.items()}) if q else "")
        s1, r1 = _request(ep["method"], u1, token_a, body1, None, args.timeout)
        v1, n1 = classify(s1, "path")

        # Call 2: tampered - inject tenant B's id into body/query/header.
        body2 = _sub_obj(ep.get("body"), ids_b, tb_num, ta_num)
        if body2 is None and ep["method"] in ("POST", "PUT", "PATCH"):
            body2 = {"tenantId": tb_num}
        q2 = dict(q or {})
        q2["tenantId"] = tb_num
        u2 = url + "?" + urllib.parse.urlencode({k: _sub_scalar(v, ids_b, tb_num, ta_num) for k, v in q2.items()})
        headers2 = {args.tenant_header: str(tb_num)} if args.tenant_header else None
        s2, r2 = _request(ep["method"], u2, token_a, body2, headers2, args.timeout)
        v2, n2 = classify(s2, "tampered tenant id")

        verdict = "FAIL" if "FAIL" in (v1, v2) else ("WARN" if "WARN" in (v1, v2) else "PASS")
        note = n2 if v2 == "FAIL" else n1
        rows.append((verdict, ep["method"], op, path, note))
        results.append({"method": ep["method"], "operation": op, "path": path,
                        "as_a": {"status": s1, "verdict": v1}, "tampered": {"status": s2, "verdict": v2},
                        "verdict": verdict, "note": note, "raw": (r2 or r1)[:400]})

    w = max((len(r[3]) for r in rows), default=20)
    print(f"{'VERDICT':7} {'METHOD':6} {'OP':9} {'PATH':{w}} NOTE")
    print("-" * (7 + 6 + 9 + w + 8))
    for verdict, method, op, path, note in rows:
        print(f"{verdict:7} {method:6} {op:9} {path:{w}} {note}")
    fails = sum(1 for r in rows if r[0] == "FAIL")
    print(f"\n{fails} FAIL, {sum(1 for r in rows if r[0]=='WARN')} WARN, "
          f"{sum(1 for r in rows if r[0]=='PASS')} PASS of {len(rows)}")
    if fails:
        print("At least one cross-tenant access succeeded - confirm and write TENANT findings.")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"base_url": args.base_url, "results": results}, fh, indent=2)
        print(f"wrote {args.out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
