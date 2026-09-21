#!/usr/bin/env python3
"""Grade every database migration in a repository for reversibility, data loss,
raw SQL, and real-looking PII in seed data.

Usage:
    python migration_reversibility.py <repo_root> [--out migrations.json] [--md migrations.md]

Tools recognised (by path/content):
  EF Core     Migrations/*.cs with Up()/Down()                 -> Down() empty / throws = irreversible
  Flyway      db/migration/V*__*.sql                           -> no matching U*__*.sql = irreversible
  Liquibase   db/changelog/*.xml|yaml|yml|sql changeSets       -> no <rollback> for non-auto-reversible changes
  Django      <app>/migrations/*.py                            -> RunPython/RunSQL without reverse = irreversible
  Alembic     alembic/versions/*.py                            -> downgrade() empty/pass/raise = irreversible
  Knex        migrations/*.js|ts with exports.up/down          -> down missing/empty = irreversible
  TypeORM     *.ts with implements MigrationInterface          -> down() empty/throws = irreversible
  Sequelize   migrations/*.js with up/down                     -> down empty = irreversible
  Prisma      prisma/migrations/*/migration.sql                -> forward-only; flagged once, data-loss warnings surfaced
  Drizzle     drizzle/*.sql                                    -> forward-only

Grades: reversible | irreversible | initial (first migration, missing reverse tolerated)
Flags:  data_loss (drop/narrow/delete), raw_sql, seed_pii (candidate values listed)
Read-only against the audited repo.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

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
_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
try:
    _spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _WALK)
    repo_walk = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(repo_walk)
except (FileNotFoundError, AttributeError, ImportError):
    sys.exit("audit-code-scan must be reachable from this skill (audit-core plugin or sibling layout; expected " + _WALK + ")")
_SDC_PATH = os.path.join(_SKILLS, "audit-sensitive-data-catalog", "scripts", "catalog.py")
if not os.path.exists(_SDC_PATH):
    sys.exit("audit-sensitive-data-catalog must be reachable from this skill (audit-core plugin or sibling layout; expected " + _SDC_PATH + ")")
_spec = importlib.util.spec_from_file_location("sensitive_data_catalog", _SDC_PATH)
sdc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sdc)

DATA_LOSS_SQL = re.compile(r"\b(DROP\s+TABLE|DROP\s+COLUMN|TRUNCATE(\s+TABLE)?|DELETE\s+FROM|ALTER\s+COLUMN\s+\w+\s+(?:TYPE\s+)?\w+\s*\(\s*\d+|MODIFY\s+COLUMN|ALTER\s+TABLE\s+\w+\s+DROP)\b", re.I)
UPDATE_NO_WHERE = re.compile(r"\bUPDATE\s+[\w\[\]\".`]+\s+SET\b(?![^;]*\bWHERE\b)", re.I | re.S)


def _read(p):
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def rel(root, p):
    return repo_walk.rel(root, p)


def walk(root):
    # Tools are recognised by file name (V1__init.sql, db.changelog-master.xml, migration.sql), so every
    # file name is accepted; folders come from repo_walk's shared skip list, with no size cap.
    for path in repo_walk.iter_files(root, globs=["*"], max_bytes=None):
        fn = os.path.basename(path)
        d = os.path.dirname(os.path.join(root, repo_walk.rel(root, path)))
        yield path, fn, d.replace(os.sep, "/")


_SEED_RULES = ["V-EMAIL", "V-PASSWORD-HASH", "V-PHONE", "V-IBAN", "V-CARD"]


def seed_pii(text):
    """Real-looking personal data and password hashes in seed data (audit-sensitive-data-catalog)."""
    hits = []
    for m in sdc.find_values(text, rules=_SEED_RULES):
        rid, v = m["rule_id"], m["value"]
        if rid == "V-EMAIL":
            if m["placeholder"] or m["attributes"]["generic_mailbox"]:
                continue
            hits.append("email " + v)
        elif rid == "V-PASSWORD-HASH":
            hits.append("password hash %s..." % v[:12])
        elif rid == "V-PHONE":
            hits.append("phone " + v)
        elif rid == "V-IBAN":
            hits.append("iban-shaped " + v)
        elif rid == "V-CARD" and m["checksum_ok"] and not m["placeholder"]:
            hits.append("card-shaped %s..." % re.sub(r"\D", "", v)[:6])
    return sorted(set(hits))[:10]


def body_is_empty(body):
    b = re.sub(r"//[^\n]*|#[^\n]*|/\*.*?\*/|\"\"\".*?\"\"\"|'''.*?'''", "", body, flags=re.S).strip()
    if not b or b in ("pass", "return", "return;", "return Promise.resolve();", "return Promise.resolve()"):
        return True
    if re.match(r"^(throw\s+new\s+\w*(NotSupported|NotImplemented|Error)\w*|raise\s+\w*(NotImplemented|Error)\w*)", b):
        return True
    return False


def cs_method_body(text, name):
    m = re.search(r"void\s+" + name + r"\s*\(\s*MigrationBuilder\s+\w+\s*\)\s*\{", text)
    if not m:
        return None
    depth, i = 0, m.end() - 1
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[m.end():i]
        i += 1
    return text[m.end():]


def js_fn_body(text, names):
    for name in names:
        m = re.search(r"(?:exports\.%s|export\s+(?:async\s+)?function\s+%s|(?:async\s+)?%s\s*\([^)]*\)\s*\{|%s\s*[:=]\s*(?:async\s*)?(?:function\s*)?\([^)]*\)\s*(?:=>)?\s*\{|(?:public\s+)?(?:async\s+)?%s\s*\([^)]*\)(?:\s*:\s*[\w<>]+)?\s*\{)" % (name, name, name, name, name), text)
        if not m:
            continue
        start = text.find("{", m.end() - 1 if text[m.end() - 1] == "{" else m.end())
        if start < 0:
            return ""
        depth, i = 0, start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start + 1:i]
            i += 1
        return text[start + 1:]
    return None


def py_fn_body(text, name):
    m = re.search(r"^def\s+" + name + r"\s*\([^)]*\)\s*(?:->[^:]+)?:\s*\n", text, re.M)
    if not m:
        return None
    lines = []
    for line in text[m.end():].splitlines():
        if line.strip() and not line.startswith((" ", "\t")):
            break
        lines.append(line)
    return "\n".join(lines)


def grade(entry, reverse_body, forward_body, tool, initial=False):
    entry["tool"] = tool
    if reverse_body is None:
        entry["reversible"] = "initial" if initial else "no (reverse step missing)"
    elif body_is_empty(reverse_body):
        entry["reversible"] = "initial" if initial else "no (reverse step empty or throws)"
    else:
        entry["reversible"] = "yes"
    fb = forward_body or ""
    entry["data_loss"] = bool(DATA_LOSS_SQL.search(fb) or UPDATE_NO_WHERE.search(fb) or re.search(r"\b(DropTable|DropColumn|dropTable|dropColumn|dropColumns|removeColumn|RemoveField|DeleteModel|drop_table|drop_column)\b", fb))
    entry["raw_sql"] = bool(re.search(r"(migrationBuilder\.Sql\(|\.raw\(|RunSQL\(|op\.execute\(|queryRunner\.query\(|sequelize\.query\(|<sql>|^\s*-\s*sql:)", fb, re.M))
    pii = seed_pii(fb)
    entry["seed_pii"] = pii
    return entry


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args()
    root = a.root
    entries = []
    flyway_v, flyway_u = {}, set()
    liquibase_files = []
    ef_by_dir = {}

    for path, fn, d in walk(root):
        low = fn.lower()
        rp = rel(root, path)
        parts = d.lower().split("/")
        # EF Core
        if low.endswith(".cs") and not low.endswith((".designer.cs", "modelsnapshot.cs")) and "migrations" in parts:
            text = _read(path)
            if "MigrationBuilder" in text:
                up, down = cs_method_body(text, "Up"), cs_method_body(text, "Down")
                ef_by_dir.setdefault(d, []).append((rp, text, up, down))
            continue
        # Flyway
        m = re.match(r"([VUR])(\d[\w.]*)__(.+)\.sql$", fn, re.I)
        if m and ("migration" in parts or "db" in parts or "flyway" in parts):
            kind, ver = m.group(1).upper(), m.group(2)
            if kind == "V":
                flyway_v[ver] = (rp, _read(path))
            elif kind == "U":
                flyway_u.add(ver)
            elif kind == "R":
                text = _read(path)
                entries.append(grade({"file": rp, "name": fn}, "repeatable", text, "flyway"))
                entries[-1]["reversible"] = "n/a (repeatable; must be idempotent)"
            continue
        # Liquibase
        if "changelog" in parts or low.startswith("db.changelog") or "liquibase" in parts:
            if low.endswith((".xml", ".yaml", ".yml", ".sql", ".json")):
                liquibase_files.append((rp, _read(path)))
            continue
        # Django / Alembic
        if low.endswith(".py") and ("migrations" in parts or "versions" in parts) and not low.startswith("__"):
            text = _read(path)
            if "alembic" in text or "versions" in parts:
                up, down = py_fn_body(text, "upgrade"), py_fn_body(text, "downgrade")
                if up is not None:
                    entries.append(grade({"file": rp, "name": fn}, down, up, "alembic", initial="down_revision = None" in text))
                    continue
            if "migrations.Migration" in text or "from django.db import migrations" in text:
                e = {"file": rp, "name": fn, "tool": "django"}
                ops = text[text.find("operations"):] if "operations" in text else text
                irreversible = []
                for rp_m in re.finditer(r"RunPython\(([^()]*(?:\([^()]*\))?[^()]*)\)", ops):
                    args = rp_m.group(1)
                    if "reverse_code" not in args and args.count(",") < 1:
                        irreversible.append("RunPython without reverse_code")
                    elif "noop" in args:
                        irreversible.append("RunPython reverse is noop")
                for rs_m in re.finditer(r"RunSQL\(([^()]*(?:\([^()]*\))?[^()]*)\)", ops):
                    if "reverse_sql" not in rs_m.group(1) and rs_m.group(1).count(",") < 1:
                        irreversible.append("RunSQL without reverse_sql")
                initial = "initial = True" in text or fn.startswith("0001")
                e["reversible"] = ("no (" + "; ".join(irreversible) + ")") if irreversible else "yes (schema ops auto-reverse)"
                if initial and irreversible:
                    e["reversible"] = "initial"
                e["data_loss"] = bool(re.search(r"\b(RemoveField|DeleteModel|AlterField|RunSQL)\b", ops) and (re.search(r"\b(RemoveField|DeleteModel)\b", ops) or DATA_LOSS_SQL.search(ops) or re.search(r"max_length\s*=\s*\d+", ops)))
                e["raw_sql"] = "RunSQL(" in ops
                e["seed_pii"] = seed_pii(text)
                entries.append(e)
            continue
        # Knex / TypeORM / Sequelize
        if low.endswith((".js", ".ts", ".mjs", ".cjs")) and ("migrations" in parts or "migration" in parts or "seeds" in parts):
            text = _read(path)
            if "MigrationInterface" in text:
                entries.append(grade({"file": rp, "name": fn}, js_fn_body(text, ["down"]), js_fn_body(text, ["up"]), "typeorm"))
            elif "queryInterface" in text:
                entries.append(grade({"file": rp, "name": fn}, js_fn_body(text, ["down"]), js_fn_body(text, ["up"]), "sequelize"))
            elif "seeds" in parts or "seed" in low:
                pii = seed_pii(text)
                entries.append({"file": rp, "name": fn, "tool": "seed", "reversible": "n/a", "data_loss": False, "raw_sql": ".raw(" in text, "seed_pii": pii})
            elif re.search(r"\b(up|down)\b", text):
                entries.append(grade({"file": rp, "name": fn}, js_fn_body(text, ["down"]), js_fn_body(text, ["up"]), "knex"))
            continue
        # Prisma / Drizzle
        if low == "migration.sql" and "migrations" in parts:
            text = _read(path)
            e = grade({"file": rp, "name": os.path.basename(d)}, None, text, "prisma")
            e["reversible"] = "no (tool is forward-only; needs restore/forward-fix procedure)"
            if "Warnings:" in text:
                e["data_loss"] = True
                e["note"] = "prisma emitted a data-loss warning block in this migration"
            entries.append(e)
            continue
        if low.endswith(".sql") and "drizzle" in parts:
            e = grade({"file": rp, "name": fn}, None, _read(path), "drizzle")
            e["reversible"] = "no (tool is forward-only; needs restore/forward-fix procedure)"
            entries.append(e)
            continue
        # seed sql / fixtures
        if (low.endswith(".sql") and re.search(r"seed|data|fixture", low)) or (low.endswith((".json", ".yaml", ".yml")) and "fixtures" in parts):
            pii = seed_pii(_read(path))
            if pii:
                entries.append({"file": rp, "name": fn, "tool": "seed", "reversible": "n/a", "data_loss": False, "raw_sql": False, "seed_pii": pii})

    for d, items in ef_by_dir.items():
        items.sort()
        for i, (rp, text, up, down) in enumerate(items):
            entries.append(grade({"file": rp, "name": os.path.basename(rp)[:-3]}, down, up, "ef-core", initial=(i == 0 and len(items) > 1 and "InitialCreate" in rp) or ("InitialCreate" in rp)))
    for ver, (rp, text) in sorted(flyway_v.items()):
        e = grade({"file": rp, "name": os.path.basename(rp)}, "x" if ver in flyway_u else None, text, "flyway", initial=ver in ("1", "1.0", "001", "0001", "1_0"))
        if ver not in flyway_u and e["reversible"] != "initial":
            e["reversible"] = "no (no U%s__ undo script)" % ver
        entries.append(e)
    AUTO_ROLLBACK = {"createTable", "addColumn", "createIndex", "addForeignKeyConstraint", "renameColumn", "renameTable", "addUniqueConstraint", "createSequence", "createView", "addPrimaryKey", "addNotNullConstraint", "addDefaultValue"}
    for rp, text in liquibase_files:
        if rp.endswith(".sql"):
            sets = re.split(r"--\s*changeset\s+", text, flags=re.I)[1:]
            for cs in sets:
                head = cs.splitlines()[0].strip() if cs.strip() else "?"
                e = grade({"file": rp, "name": head}, "x" if re.search(r"--\s*rollback", cs, re.I) else None, cs, "liquibase")
                if not re.search(r"--\s*rollback", cs, re.I):
                    e["reversible"] = "no (formatted SQL changeSet without -- rollback)"
                entries.append(e)
        elif rp.endswith(".xml"):
            for cs in re.finditer(r"<changeSet\b([^>]*)>(.*?)</changeSet>", text, re.S):
                attrs, body = cs.groups()
                cid = re.search(r'id="([^"]+)"', attrs)
                changes = set(re.findall(r"<(\w+)\b", body)) - {"rollback", "comment", "column", "constraints", "where", "preConditions"}
                has_rb = "<rollback" in body
                non_auto = [c for c in changes if c not in AUTO_ROLLBACK]
                e = grade({"file": rp, "name": cid.group(1) if cid else "?"}, "x" if (has_rb or not non_auto) else None, body, "liquibase")
                if not has_rb and non_auto:
                    e["reversible"] = "no (no <rollback> for: %s)" % ", ".join(sorted(non_auto)[:5])
                entries.append(e)
        else:
            for cs in re.finditer(r"-\s*changeSet:\s*\n((?:[ \t]+.*\n?)+)", text):
                body = cs.group(1)
                cid = re.search(r"id:\s*(\S+)", body)
                changes = set(re.findall(r"^\s+-\s*(\w+):", body, re.M)) - {"column", "columns", "constraints", "rollback"}
                has_rb = "rollback:" in body
                non_auto = [c for c in changes if c not in AUTO_ROLLBACK]
                e = grade({"file": rp, "name": cid.group(1) if cid else "?"}, "x" if (has_rb or not non_auto) else None, body, "liquibase")
                if not has_rb and non_auto:
                    e["reversible"] = "no (no rollback for: %s)" % ", ".join(sorted(non_auto)[:5])
                entries.append(e)

    entries.sort(key=lambda e: e["file"])
    summary = {"migrations": len(entries),
               "irreversible": sum(1 for e in entries if str(e.get("reversible", "")).startswith("no")),
               "data_loss": sum(1 for e in entries if e.get("data_loss")),
               "raw_sql": sum(1 for e in entries if e.get("raw_sql")),
               "seed_pii_files": sum(1 for e in entries if e.get("seed_pii"))}
    doc = {"root": os.path.abspath(root), "summary": summary, "migrations": entries,
           "note": "Model/migration sync is not checked here: run the tool command from references/migration-hygiene.md."}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
    md = ["# Migration reversibility report", "", f"Migrations: {summary['migrations']}  Irreversible: {summary['irreversible']}  Data loss: {summary['data_loss']}  Raw SQL: {summary['raw_sql']}  Seed PII files: {summary['seed_pii_files']}", "",
          "| Migration | Tool | Reversible | Data loss | Raw SQL | Seed PII | File |", "|---|---|---|---|---|---|---|"]
    for e in entries:
        md.append(f"| {e['name']} | {e['tool']} | {e.get('reversible')} | {'yes' if e.get('data_loss') else 'no'} | {'yes' if e.get('raw_sql') else 'no'} | {'; '.join(e.get('seed_pii') or []) or 'no'} | `{e['file']}` |")
    md += ["", doc["note"], ""]
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(md))
    print(json.dumps(summary, indent=2) if (a.out or a.md) else "\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
