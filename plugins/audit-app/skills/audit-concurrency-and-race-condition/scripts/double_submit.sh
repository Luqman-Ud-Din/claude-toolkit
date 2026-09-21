#!/usr/bin/env bash
# Fire N identical requests at once against a URL to confirm a double-submit /
# missing-idempotency race, and print each response's status and body.
#
# Usage:
#   bash double_submit.sh <url> [-n 2] [-X POST] [-H 'Authorization: Bearer ...'] [-d '{"orderId":1}'] [-o out.txt]
#
# Example:
#   bash double_submit.sh https://test.example.com/api/payments/charge -n 2 \
#        -H 'Authorization: Bearer eyJ...' -H 'Content-Type: application/json' -d '{"orderId":42}' \
#        -o audit/evidence/audit-concurrency-and-race-condition/double-submit-charge.txt
#
# Two 200s (or two created records / two charges visible afterwards) confirm the race.
# One 200 and one 409/duplicate-key error means a guard exists.
# Use ONLY against a test environment; this sends real requests. Requires curl.
set -euo pipefail

url="${1:-}"; shift || true
[ -z "$url" ] && { sed -n '2,15p' "$0"; exit 1; }
n=2; method="POST"; data=""; out=""; headers=()
while [ $# -gt 0 ]; do
  case "$1" in
    -n) n="$2"; shift 2;;
    -X) method="$2"; shift 2;;
    -H) headers+=(-H "$2"); shift 2;;
    -d) data="$2"; shift 2;;
    -o) out="$2"; shift 2;;
    *) echo "unknown arg: $1"; exit 1;;
  esac
done

tmp="$(mktemp -d)"
for i in $(seq 1 "$n"); do
  (
    if [ -n "$data" ]; then
      curl -s -o "$tmp/body.$i" -w "%{http_code} %{time_total}s" -X "$method" "${headers[@]}" --data "$data" "$url" > "$tmp/status.$i" 2>&1
    else
      curl -s -o "$tmp/body.$i" -w "%{http_code} %{time_total}s" -X "$method" "${headers[@]}" "$url" > "$tmp/status.$i" 2>&1
    fi
  ) &
done
wait

report=""
for i in $(seq 1 "$n"); do
  report+="--- request $i: $(cat "$tmp/status.$i")"$'\n'
  report+="$(head -c 1000 "$tmp/body.$i")"$'\n'
done
echo "$report"
if [ -n "$out" ]; then
  mkdir -p "$(dirname "$out")"
  { echo "url: $url"; echo "method: $method"; echo "n: $n"; echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo; echo "$report"; } > "$out"
  echo "saved to $out"
fi
rm -rf "$tmp"
