#!/usr/bin/env python3
"""Seed the date-field map: list every date/time field declared in entities,
ORM models, migrations and SQL schemas, with its declared type and a first
guess at its zone convention.

Usage:
    python date_field_map.py <repo_root> [--out date-fields.json] [--md date-fields.md]

Detects (heuristics, per line):
  * C#      : DateTime / DateTimeOffset / DateOnly / TimeOnly properties; HasColumnType("datetime...")
  * Java/Kt : LocalDateTime / LocalDate / Instant / OffsetDateTime / ZonedDateTime / java.util.Date fields
  * TS/JS   : TypeORM @Column({type:'timestamp'|'timestamptz'|'date'}), Prisma DateTime [@db.X], Sequelize DataTypes.DATE, Mongoose Date
  * Python  : Django DateTimeField/DateField, SQLAlchemy Column(DateTime(timezone=True|False))
  * SQL     : columns typed timestamp[tz], datetime[2], date, datetimeoffset

Zone guess rules: type is zone-aware -> "utc/offset-aware"; name ends with Utc -> "utc (by name)";
date-only type -> "date-only"; otherwise "unknown (zone-less)". The reviewer confirms each row by hand
and fills in "converted at". Read-only.
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
EXTS = {".cs", ".java", ".kt", ".ts", ".js", ".py", ".sql", ".prisma", ".xml"}

RULES = [
    # (stack, regex with named groups type & name, aware?, dateonly?)
    ("dotnet", re.compile(r"\b(?P<type>DateTimeOffset|DateTime|DateOnly|TimeOnly)\??\s+(?P<name>\w+)\s*\{\s*get;"), None, None),
    ("dotnet", re.compile(r"HasColumnType\(\s*\"(?P<type>datetimeoffset|datetime2?|smalldatetime|date|timestamp(?: with(?:out)? time zone)?|timestamptz)(?:\(\d+\))?\"\s*\)"), None, None),
    ("java", re.compile(r"\b(?:private|protected|public)\s+(?P<type>LocalDateTime|LocalDate|LocalTime|Instant|OffsetDateTime|ZonedDateTime|java\.util\.Date|Date|Timestamp)\s+(?P<name>\w+)\s*(;|=)"), None, None),
    ("node", re.compile(r"@Column\(\s*\{[^}]*type:\s*['\"](?P<type>timestamptz|timestamp|datetime|date|timestamp with time zone|timestamp without time zone)['\"][^}]*\}\s*\)\s*\n?\s*(?P<name>\w+)?"), None, None),
    ("node", re.compile(r"^\s*(?P<name>\w+)\s+(?P<type>DateTime)\??\s*(?P<attrs>.*)$"), None, None),
    ("node", re.compile(r"(?P<name>\w+)\s*:\s*\{[^}]*type:\s*(?P<type>DataTypes\.DATE(?:ONLY)?|Date)\b"), None, None),
    ("python", re.compile(r"(?P<name>\w+)\s*=\s*models\.(?P<type>DateTimeField|DateField|TimeField)\("), None, None),
    ("python", re.compile(r"(?P<name>\w+)\s*=\s*Column\(\s*(?P<type>DateTime|Date|TIMESTAMP)(?P<args>\([^)]*\))?"), None, None),
    ("sql", re.compile(r"^\s*\[?(?P<name>\w+)\]?\s+(?P<type>timestamptz|timestamp(?: with(?:out)? time zone)?|datetimeoffset|datetime2?|smalldatetime|date)(?:\(\d+\))?\b", re.IGNORECASE), None, None),
]

AWARE_TYPES = {"datetimeoffset", "offsetdatetime", "zoneddatetime", "instant", "timestamptz", "timestamp with time zone"}
DATEONLY_TYPES = {"dateonly", "localdate", "date", "datefield", "datetypes.dateonly"}


def classify(typ, name, extra=""):
    t = typ.lower()
    x = (extra or "").lower()
    if t in AWARE_TYPES or "timestamptz" in x or "timezone=true" in x.replace(" ", ""):
        return "utc/offset-aware", False
    if t in DATEONLY_TYPES or "@db.date" in x:
        return "date-only", True
    if name and name.lower().endswith("utc"):
        return "utc (by name; confirm converter)", False
    if t == "datetimefield":
        return "aware if USE_TZ=True (confirm settings)", False
    return "unknown (zone-less)", False


def iter_files(root):
    return repo_walk.iter_files(root, exts=EXTS, names=frozenset())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out")
    ap.add_argument("--md")
    args = ap.parse_args()

    rows = []
    for path in iter_files(args.root):
        rel = repo_walk.rel(args.root, path)
        ext = os.path.splitext(path)[1].lower()
        lines = repo_walk.read_lines(path)
        entity = os.path.splitext(os.path.basename(path))[0]
        for n, line in enumerate(lines, 1):
            for stack, rx, _, _ in RULES:
                if stack == "sql" and ext not in (".sql", ".xml"):
                    continue
                if stack == "node" and ext not in (".ts", ".js", ".prisma"):
                    continue
                if stack == "dotnet" and ext != ".cs":
                    continue
                if stack == "java" and ext not in (".java", ".kt"):
                    continue
                if stack == "python" and ext != ".py":
                    continue
                m = rx.search(line)
                if not m:
                    continue
                gd = m.groupdict()
                typ = gd.get("type") or ""
                name = gd.get("name") or ""
                extra = gd.get("attrs") or gd.get("args") or line
                if stack == "sql" and typ.lower() in ("date",) and name.lower() in ("create", "alter", "update"):
                    continue
                zone, dateonly = classify(typ, name, extra)
                rows.append({"entity": entity, "field": name, "type": typ.strip(), "zone_guess": zone,
                             "date_only": dateonly, "file": rel, "line": n, "converted_at": "",
                             "snippet": line.strip()[:160]})
                break

    result = {"root": os.path.abspath(args.root), "count": len(rows), "fields": rows}
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("| Entity.Field | Storage type | Zone convention (guess) | Date-only? | Converted at | Location |\n|---|---|---|---|---|---|\n")
            for r in rows:
                fh.write(f"| {r['entity']}.{r['field']} | {r['type']} | {r['zone_guess']} | {'yes' if r['date_only'] else 'no'} |  | `{r['file']}:{r['line']}` |\n")
    print(json.dumps({"count": len(rows),
                      "zone_less": sum(1 for r in rows if r["zone_guess"].startswith("unknown")),
                      "date_only": sum(1 for r in rows if r["date_only"])}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
