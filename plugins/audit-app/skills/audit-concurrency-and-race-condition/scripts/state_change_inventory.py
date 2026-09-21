#!/usr/bin/env python3
"""Seed the state-changing operations inventory: list every entry point that
can change state (mutating HTTP handlers, queue consumers, scheduled jobs,
webhooks) together with the transaction / idempotency / lock / constraint
markers found in the same file, so the reviewer can fill in the inventory
table quickly.

Usage:
    python state_change_inventory.py <repo_root> [--out inventory.json] [--md inventory.md]

Per operation it records:
  entry        : the handler line (e.g. [HttpPost("pay")], @PostMapping, router.post, def post)
  kind         : http | job | consumer | webhook
  money        : name suggests money/stock/uniqueness (pay, charge, refund, stock, register, ...)
  transaction  : transaction/atomic-update markers seen in the file
  idempotency  : idempotency-key / event-id markers seen in the file
  lock         : lock / version / unique-constraint markers seen in the file
  check_then_act: exists/any/count-then-write shapes seen in the file

Everything is a heuristic pointer; the reviewer confirms each row. Read-only.
"""
import argparse
import json
import os
import re
import sys

import importlib.util

def _audit_core_skills_dir():
    """Resolve the explicit core installation, or the original sibling layout."""
    env = os.environ.get("AUDIT_CORE_ROOT")
    if env:
        skills = os.path.join(env, "skills")
        if os.path.isdir(os.path.join(skills, "audit-code-scan")):
            return skills
        sys.exit("AUDIT_CORE_ROOT does not contain audit-core skills: " + env)
    sibling = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if os.path.isdir(os.path.join(sibling, "audit-code-scan")):
        return sibling
    sys.exit("audit-core is unavailable. Enable audit-core and restart Claude Code, "
             "or set AUDIT_CORE_ROOT to its plugin directory when running manually.")

_SKILLS = _audit_core_skills_dir()


def _load_atomic(skill, module, alias):
    """Load an atomic skill's script by path under a unique module name."""
    path = os.path.join(_SKILLS, skill, "scripts", module + ".py")
    if not os.path.exists(path):
        sys.exit(f"{skill} must be reachable from this skill (audit-core plugin or sibling layout; expected {path})")
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


repo_walk = _load_atomic("audit-code-scan", "repo_walk", "audit_code_scan_repo_walk")

# Schema migrations are not entry points; skipped on top of the shared walker defaults.
MIGRATION_DIRS = ("Migrations", "migrations")
EXTS = {".cs", ".java", ".kt", ".ts", ".js", ".mjs", ".py"}

ENTRY = [
    ("http", re.compile(r"\[Http(Post|Put|Patch|Delete)(\([^)]*\))?\]|Map(Post|Put|Patch|Delete)\(")),
    ("http", re.compile(r"@(Post|Put|Patch|Delete)Mapping|@RequestMapping\([^)]*method\s*=\s*RequestMethod\.(POST|PUT|PATCH|DELETE)")),
    ("http", re.compile(r"(router|app|fastify|server)\.(post|put|patch|delete)\(|@(Post|Put|Patch|Delete)\(")),
    ("http", re.compile(r"def\s+(post|put|patch|delete|create|update|destroy|perform_create|perform_update|perform_destroy)\s*\(|@(app|router)\.(post|put|patch|delete)\(|methods\s*=\s*\[[^\]]*(POST|PUT|PATCH|DELETE)")),
    ("consumer", re.compile(r"@(KafkaListener|RabbitListener|SqsListener|JmsListener)|@shared_task|@app\.task|new Worker\(|\.process\(\s*(async\s*)?\(|@Processor\(|@Process\(")),
    ("job", re.compile(r"RecurringJob\.AddOrUpdate|BackgroundJob\.(Enqueue|Schedule)|@Scheduled\(|cron\.schedule\(|new CronJob\(|@Cron\(|@Interval\(|beat_schedule|@periodic_task|add_job\(|class\s+\w+\s*:\s*BackgroundService|IJob\b")),
]
WEBHOOK_PATH = re.compile(r"webhook|callback|hook", re.I)
WEBHOOK_CODE = re.compile(r"Route\(\s*\"[^\"]*(webhook|callback)|Mapping\(\s*\"[^\"]*(webhook|callback)|\.(post|all)\(\s*['\"][^'\"]*(webhook|callback)|constructEvent|construct_event|csrf_exempt|Stripe-Signature|X-Hub-Signature", re.I)
MONEY = re.compile(r"pay|charge|refund|capture|debit|credit|transfer|withdraw|deposit|checkout|order|invoice|wallet|stock|inventory|reserve|register|signup|invite|redeem|coupon|voucher|approve|subscri", re.I)

MARKERS = {
    "transaction": re.compile(r"BeginTransaction|TransactionScope|ExecuteUpdate|ExecuteDelete|@Transactional|@Modifying|\$transaction\(|\.transaction\(|startTransaction|withTransaction|transaction\.atomic|select_for_update|F\(\s*['\"]|updateMany\(\s*\{\s*where|findOneAndUpdate|FOR UPDATE|UPDLOCK"),
    "idempotency": re.compile(r"Idempotency-?Key|idempotency_?key|IdempotencyKey|EventId|event\.id|event_id|eventId|RequestId|jobId\s*:|HTTP_IDEMPOTENCY_KEY", re.I),
    "lock": re.compile(r"\block\s*\(|synchronized|@Lock\(|LockModeType|SchedulerLock|DisableConcurrentExecution|DisallowConcurrentExecution|redlock|Redlock|threading\.Lock|cache\.add\(|SET\s+\w+\s+\w+\s+NX|IsRowVersion|IsConcurrencyToken|@Version|@VersionColumn|version:\s*true|RowVersion|IntegerVersionField|version_id_col", re.I),
    "unique": re.compile(r"IsUnique\(\)|IsUnique\s*=\s*true|unique\s*=\s*[Tt]rue|@Unique|UniqueConstraint|unique_together|@unique|@@unique|\.unique\(\)|CREATE UNIQUE|UNIQUE\s*\(", re.I),
    "check_then_act": re.compile(r"if\s*\(\s*!?\s*(await\s+)?[\w.]+\.(Any|AnyAsync|Exists|ExistsAsync|Count|CountAsync|existsBy\w*|exists|count\w*|findOne|findFirst|findUnique|countDocuments)\s*\(|if\s+not\s+[\w.]+\.filter\([^)]*\)\.exists\(\)|if\s*\(\s*\w+\.(Balance|Quantity|Qty|Stock|Available|balance|quantity|qty|stock|available)\w*\s*(>=|>|<|<=)|\.isPresent\(\)|get_or_create\(|update_or_create\("),
}


def iter_files(root):
    for path in repo_walk.iter_files(root, exts=EXTS, names=frozenset(), extra_skip=MIGRATION_DIRS):
        if not re.search(r"\.(spec|test)\.[jt]s$|Tests?\.cs$|Test\.java$|test_\w+\.py$", os.path.basename(path)):
            yield path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out")
    ap.add_argument("--md")
    args = ap.parse_args()

    ops = []
    for path in iter_files(args.root):
        rel = repo_walk.rel(args.root, path)
        text = repo_walk.read_text(path)
        lines = text.splitlines()
        file_markers = {k: sorted({m.group(0).strip()[:40] for m in rx.finditer(text)})[:6] for k, rx in MARKERS.items()}
        is_webhook_file = bool(WEBHOOK_PATH.search(os.path.basename(rel))) or bool(WEBHOOK_CODE.search(text))
        for n, line in enumerate(lines, 1):
            for kind, rx in ENTRY:
                if rx.search(line):
                    # grab the following non-empty line to name the handler when the attribute is on its own line
                    nxt = ""
                    for j in range(n, min(n + 3, len(lines))):
                        if lines[j].strip():
                            nxt = lines[j].strip()
                            break
                    label = line.strip()
                    if label.startswith("[") or label.startswith("@"):
                        label = label + "  " + nxt
                    ops.append({
                        "file": rel, "line": n, "kind": "webhook" if (kind == "http" and is_webhook_file) else kind,
                        "entry": label[:200],
                        "money_or_uniqueness": bool(MONEY.search(label) or MONEY.search(rel)),
                        "transaction": file_markers["transaction"],
                        "idempotency": file_markers["idempotency"],
                        "lock_or_version": file_markers["lock"],
                        "unique_constraint_in_file": file_markers["unique"],
                        "check_then_act_in_file": file_markers["check_then_act"],
                        "idempotent": "", "concurrent_self_safe": "", "finding": "",
                    })
                    break

    ops.sort(key=lambda o: (not o["money_or_uniqueness"], o["file"], o["line"]))
    result = {"root": os.path.abspath(args.root), "count": len(ops), "operations": ops,
              "risky_without_markers": [
                  f"{o['file']}:{o['line']}" for o in ops
                  if o["money_or_uniqueness"] and not o["transaction"] and not o["idempotency"] and not o["lock_or_version"]]}
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("| Operation | Kind | Money/uniq? | Transaction markers | Idempotency markers | Lock/version markers | Unique constraint in file | Check-then-act in file |\n|---|---|---|---|---|---|---|---|\n")
            for o in ops:
                cell = lambda v: ", ".join(v).replace("|", "/") if v else "-"
                fh.write(f"| `{o['file']}:{o['line']}` {o['entry'][:60].replace('|', '/')} | {o['kind']} | {'yes' if o['money_or_uniqueness'] else 'no'} | {cell(o['transaction'])} | {cell(o['idempotency'])} | {cell(o['lock_or_version'])} | {cell(o['unique_constraint_in_file'])} | {cell(o['check_then_act_in_file'])} |\n")
    print(json.dumps({"count": len(ops), "risky_without_markers": result["risky_without_markers"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
