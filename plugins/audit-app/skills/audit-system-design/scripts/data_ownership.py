#!/usr/bin/env python3
"""Map which module/service writes which table or entity, and flag tables with
more than one writer (shared database, dual writes, unclear ownership).

Usage:
    python data_ownership.py <repo_root> [--out ownership.json] [--md ownership.md]

A "unit" is the nearest ancestor directory containing a build manifest
(*.csproj, pom.xml, build.gradle, package.json, manage.py, pyproject.toml,
apps.py). Write evidence is collected per unit from:
  dotnet         DbSet<T> declarations, _db.T.Add/AddRange/Update/Remove, ExecuteSqlRaw/Interpolated,
                 [Table("x")], migrationBuilder.CreateTable("x")
  java-spring    @Entity/@Table(name), JpaRepository<T,..> + .save/.delete, @Modifying @Query, jdbcTemplate.update
  node-express   prisma.<model>.create|update|delete|upsert|createMany, TypeORM getRepository(T).save, knex('t').insert|update|del,
                 Model.create (mongoose), sequelize Model.create/update/destroy
  python-django  <Model>.objects.create|update|bulk_create|get_or_create|update_or_create, <model>.save(), session.add()
  any            INSERT INTO t / UPDATE t SET / DELETE FROM t / MERGE INTO t in code and .sql (excluding migrations folders)

Everything is a candidate: a "writer" may be a legitimate owner plus a data-migration script.
Read-only against the audited repo.
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

MANIFESTS = {"pom.xml", "build.gradle", "build.gradle.kts", "package.json", "manage.py", "pyproject.toml", "apps.py"}
CODE_EXT = {".cs", ".java", ".kt", ".ts", ".js", ".py", ".sql"}

RULES = [
    ("dotnet-dbset", r"DbSet<(\w+)>", "declares"),
    ("dotnet-write", r"\b\w+\.(\w+)\.(?:Add|AddRange|Update|UpdateRange|Remove|RemoveRange|ExecuteDelete|ExecuteUpdate)(?:Async)?\(", "writes"),
    ("dotnet-table", r'\[Table\(\s*"(\w+)"', "declares"),
    ("dotnet-migration", r'CreateTable\(\s*(?:name:\s*)?"(\w+)"', "creates"),
    ("java-entity", r'@Table\(\s*name\s*=\s*"(\w+)"', "declares"),
    ("java-entity2", r"@Entity\b[\s\S]{0,200}?class\s+(\w+)", "declares"),
    ("java-repo", r"(?:JpaRepository|CrudRepository|PagingAndSortingRepository|MongoRepository)<\s*(\w+)\s*,", "declares"),
    ("java-write", r"(\w+)Repository\.(?:save|saveAll|delete|deleteById|deleteAll|saveAndFlush)\(", "writes"),
    ("prisma-write", r"prisma\.(\w+)\.(?:create|createMany|update|updateMany|delete|deleteMany|upsert)\(", "writes"),
    ("typeorm-write", r"getRepository\(\s*(\w+)\s*\)\.(?:save|insert|update|delete|remove|upsert)\(", "writes"),
    ("typeorm-write2", r"(\w+)Repository\.(?:save|insert|update|delete|remove|upsert)\(", "writes"),
    ("knex-write", r"knex\(\s*['\"](\w+)['\"]\s*\)(?:\.\w+\([^)]*\))*\.(?:insert|update|del|delete|upsert)\(", "writes"),
    ("mongoose-seq-write", r"\b([A-Z]\w+)\.(?:create|insertMany|updateOne|updateMany|deleteOne|deleteMany|findOneAndUpdate|bulkCreate|destroy|upsert)\(", "writes"),
    ("django-write", r"\b([A-Z]\w+)\.objects\.(?:create|bulk_create|update|get_or_create|update_or_create|bulk_update)\(", "writes"),
    ("django-delete", r"\b([A-Z]\w+)\.objects(?:\.\w+\([^)]*\))*\.delete\(", "writes"),
    ("sql-insert", r"\bINSERT\s+INTO\s+[\[\"`]?(?:\w+[\]\"`]?\.)?[\[\"`]?(\w+)", "writes"),
    ("sql-update", r"\bUPDATE\s+[\[\"`]?(?:\w+[\]\"`]?\.)?[\[\"`]?(\w+)[\]\"`]?\s+SET\b", "writes"),
    ("sql-delete", r"\bDELETE\s+FROM\s+[\[\"`]?(?:\w+[\]\"`]?\.)?[\[\"`]?(\w+)", "writes"),
    ("sql-merge", r"\bMERGE\s+(?:INTO\s+)?[\[\"`]?(?:\w+[\]\"`]?\.)?[\[\"`]?(\w+)", "writes"),
]
NOISE = {"result", "results", "response", "request", "data", "item", "items", "list", "value", "values", "entity", "entities",
         "model", "models", "object", "objects", "string", "int", "set", "map", "array", "promise", "task", "console", "math",
         "json", "date", "object", "error", "logger", "log", "self", "this", "db", "context", "dbcontext", "session"}


def _read(p):
    return repo_walk.read_text(p)


def norm(name):
    n = re.sub(r"(Entity|Model|Dto|Table|Repository)$", "", name)
    n = n.lower()
    if n.endswith("ies") and len(n) > 4:
        return n[:-3] + "y"
    if n.endswith("es") and n[:-2].endswith(("s", "x", "z", "ch", "sh")) and len(n) > 4:
        return n[:-2]
    if n.endswith("s") and not n.endswith("ss") and len(n) > 3:
        return n[:-1]
    return n


def unit_of(path, root, manifest_dirs):
    d = os.path.dirname(path)
    best = None
    while True:
        if d in manifest_dirs and (best is None or len(d) > len(best)):
            best = d
        parent = os.path.dirname(d)
        if parent == d or len(d) < len(root):
            break
        d = parent
    return os.path.relpath(best, root).replace(os.sep, "/") if best else "."


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root"); ap.add_argument("--out"); ap.add_argument("--md")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    manifest_dirs = set()
    files = []
    for path in repo_walk.iter_files(root, exts=CODE_EXT | {".csproj", ".fsproj"}, names=MANIFESTS):
        low = os.path.basename(path).lower()
        if low in MANIFESTS or low.endswith((".csproj", ".fsproj")):
            manifest_dirs.add(os.path.dirname(path))
        if os.path.splitext(low)[1] in CODE_EXT:
            files.append(path)
    # a unit that is just a manifest root containing other units (e.g. solution root) is fine; nearest wins
    rules = [(rid, re.compile(rx), kind) for rid, rx, kind in RULES]
    tables = {}
    for p in files:
        parts = p.replace(os.sep, "/").split("/")
        is_migration = any(seg.lower() in ("migrations", "migration", "seeds", "fixtures") for seg in parts) or "migration" in os.path.basename(p).lower()
        unit = unit_of(p, root, manifest_dirs)
        text = _read(p)
        rp = os.path.relpath(p, root).replace(os.sep, "/")
        for rid, rx, kind in rules:
            if rid == "java-entity2":
                for m in rx.finditer(text):
                    _record(tables, m.group(1), unit, kind, f"{rp}:{text.count(chr(10), 0, m.start()) + 1}", rid, is_migration)
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for m in rx.finditer(line):
                    name = m.group(1)
                    if name.lower() in NOISE or len(name) < 3:
                        continue
                    _record(tables, name, unit, kind, f"{rp}:{i}", rid, is_migration)
    rows = []
    for key, info in sorted(tables.items()):
        writers = {u: ev for u, ev in info["units"].items() if any(e["kind"] == "writes" and not e["migration"] for e in ev)}
        declarers = {u for u, ev in info["units"].items() if any(e["kind"] in ("declares", "creates") for e in ev)}
        rows.append({"table": key, "names_seen": sorted(info["names"]), "declared_in": sorted(declarers),
                     "writers": {u: [e["where"] for e in ev if e["kind"] == "writes"][:5] for u, ev in writers.items()},
                     "writer_count": len(writers), "multi_writer": len(writers) > 1,
                     "declared_in_multiple_units": len(declarers) > 1})
    multi = [r for r in rows if r["multi_writer"] or r["declared_in_multiple_units"]]
    doc = {"root": root, "units": sorted(os.path.relpath(d, root).replace(os.sep, "/") for d in manifest_dirs),
           "tables": rows, "shared_tables": multi,
           "summary": {"tables": len(rows), "multi_writer_tables": sum(1 for r in rows if r["multi_writer"]),
                       "declared_in_multiple_units": sum(1 for r in rows if r["declared_in_multiple_units"])}}
    md = ["# Data ownership", "", f"Tables/entities seen: {doc['summary']['tables']}  Multi-writer: {doc['summary']['multi_writer_tables']}  Declared in several units: {doc['summary']['declared_in_multiple_units']}", "",
          "## Tables with more than one writer or declaration", "", "| Table | Declared in | Writers (unit: evidence) |", "|---|---|---|"]
    for r in multi:
        w = "<br>".join(f"{u}: {', '.join(ev)}" for u, ev in r["writers"].items()) or "-"
        md.append(f"| {r['table']} ({', '.join(r['names_seen'])}) | {', '.join(r['declared_in']) or '-'} | {w} |")
    if not multi:
        md.append("| none | | |")
    md += ["", "## All tables", "", "| Table | Declared in | Writer units |", "|---|---|---|"]
    md += [f"| {r['table']} | {', '.join(r['declared_in']) or '-'} | {', '.join(r['writers']) or '-'} |" for r in rows]
    md += ["", "Migration/seed folders are excluded from writer counts. Confirm ownership in the code before writing a finding."]
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(md) + "\n")
    print("\n".join(md) if not (a.out or a.md) else json.dumps(doc["summary"], indent=2))
    return 0


def _record(tables, name, unit, kind, where, rule, is_migration):
    key = norm(name)
    info = tables.setdefault(key, {"names": set(), "units": {}})
    info["names"].add(name)
    info["units"].setdefault(unit, []).append({"kind": kind, "where": where, "rule": rule, "migration": is_migration})


if __name__ == "__main__":
    sys.exit(main())
