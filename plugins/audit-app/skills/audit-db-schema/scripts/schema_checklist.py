#!/usr/bin/env python3
"""Build a table-by-table schema checklist from SQL DDL files and ORM models.

Usage:
    python schema_checklist.py <repo_root> [--stack dotnet|java-spring|node-express|python-django|auto]
                               [--out checklist.json] [--md checklist.md] [--no-code-scan]

Sources parsed (all best-effort, regex based, read-only):
  * SQL DDL       : CREATE TABLE / ALTER TABLE ADD CONSTRAINT / CREATE [UNIQUE] INDEX in *.sql
  * dotnet        : EF Core *ModelSnapshot.cs / *.Designer.cs (preferred), entity classes reachable
                    from DbSet<T>, fluent IEntityTypeConfiguration<T> / OnModelCreating
  * java-spring   : JPA @Entity classes (@Table indexes, @Id, @Column, @ManyToOne/@JoinColumn, @Version)
  * node-express  : Prisma schema.prisma, TypeORM *.entity.ts, Knex createTable migrations
  * python-django : Django models.Model classes, SQLAlchemy declarative models

For every table the checklist records: pk, fks (and whether each is indexed), indexes,
money columns and their types, timestamp columns and zone-awareness, unbounded strings,
audit columns, soft-delete column, concurrency token, sensitive plaintext columns, and a
list of issue codes. It also proposes indexes with the justifying query/code path
(unindexed FKs, plus columns the code filters/sorts by).

Everything reported is a candidate; the skill confirms each one before it becomes a
finding. Never modifies the audited repository.
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

SECRETISH = ("credential", "secret")

MONEY_RE = re.compile(r"(price|amount|total|cost|balance|tax|discount|fee|rate|salary|wage|credit|debit|paid|payable|receivable|subtotal|charge|vat|commission|value)", re.I)
FLOAT_TYPES = {"float", "real", "double", "double precision", "float4", "float8", "binary_float", "binary_double", "number"}
NAIVE_TS = {"datetime", "datetime2", "smalldatetime", "timestamp", "timestamp without time zone", "localdatetime", "date_time"}
TZ_TS = {"datetimeoffset", "timestamptz", "timestamp with time zone", "instant", "offsetdatetime", "zoneddatetime"}
FREE_TEXT_RE = re.compile(r"(note|notes|description|desc|comment|comments|body|content|remarks|remark|text|json|html|message|payload|address|reason|detail|details)$", re.I)
AUDIT_CREATED_AT = re.compile(r"^(created(_?at|_?on|_?date|_?time)?|creation_?date|date_?created|inserted_?at)$", re.I)
AUDIT_UPDATED_AT = re.compile(r"^(updated(_?at|_?on|_?date|_?time)?|modified(_?at|_?on|_?date|_?time)?|last_?modified(_?at|_?on)?|date_?modified|date_?updated)$", re.I)
AUDIT_CREATED_BY = re.compile(r"^(created_?by(_?id|_?user_?id)?|creator(_?id)?|inserted_?by)$", re.I)
AUDIT_UPDATED_BY = re.compile(r"^(updated_?by(_?id|_?user_?id)?|modified_?by(_?id)?|last_?modified_?by(_?id)?)$", re.I)
SOFT_DELETE_RE = re.compile(r"^(is_?deleted|deleted|deleted_?at|deleted_?on|is_?active|is_?archived|archived_?at|del_?flag)$", re.I)
CONCURRENCY_RE = re.compile(r"^(row_?version|version|timestamp|xmin|concurrency_?stamp|etag)$", re.I)
_SCHEMA_SUBS = {"national-id", "bank-account", "payment-card", "card-security"}
SHARED_REF_RE = re.compile(r"^(company|companies|branch|branches|tenant|tenants|user|users|aspnetusers|product|products|item|items|customer|customers|supplier|suppliers|vendor|vendors|category|categories|currency|currencies|account|accounts|role|roles|country|countries|warehouse|warehouses)$", re.I)
TENANT_RE = re.compile(r"^(company_?id|tenant_?id|branch_?id|organization_?id|org_?id)$", re.I)
ID_LIKE_RE = re.compile(r"^(\w+?)_?id$", re.I)


# ----------------------------------------------------------------------------- helpers
def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def iter_files(root, exts):
    # Shared skip list from repo_walk; no size cap, so large EF model snapshots are still parsed.
    return repo_walk.iter_files(root, exts={e for e in exts if e.startswith(".")},
                                names={e.lower() for e in exts if not e.startswith(".")}, max_bytes=None)


def rel(root, path):
    return repo_walk.rel(root, path)


def sensitive_plaintext(name):
    """Credential, secret, national-id and payment column names whose name says the value is plain
    (audit-sensitive-data-catalog; hashed, encrypted and masked forms are skipped)."""
    r = sdc.classify_name(name)
    return r["sensitive"] and r["form"] == "plain" and (r["category"] in SECRETISH or r["subcategory"] in _SCHEMA_SUBS)


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def balanced(text, start, open_ch="(", close_ch=")"):
    """Return (body, end_index) for the bracket block starting at text[start] == open_ch."""
    depth = 0
    i = start
    in_str = None
    while i < len(text):
        c = text[i]
        if in_str:
            if c == in_str and text[i - 1] != "\\":
                in_str = None
        elif c in ("'", '"'):
            in_str = c
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i
        i += 1
    return text[start + 1:], len(text)


def split_top(body, sep=","):
    parts, depth, cur, in_str = [], 0, [], None
    for c in body:
        if in_str:
            cur.append(c)
            if c == in_str:
                in_str = None
            continue
        if c in ("'", '"'):
            in_str = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if c == sep and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def unq(name):
    return re.sub(r'^[\[\]"`]+|[\[\]"`]+$', "", name.strip()).split(".")[-1]


def norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


class Table:
    def __init__(self, name, source, kind):
        self.name = name
        self.source = source
        self.kind = kind
        self.columns = []      # {name,type,nullable,length,precision,scale}
        self.pk = []
        self.fks = []          # {column, ref_table, ref_column, on_delete, indexed}
        self.indexes = []      # {name, columns, unique}
        self.uniques = []
        self.checks = []
        self.query_filter = False

    def col(self, name, type_="", nullable=True, length=None, precision=None, scale=None):
        for c in self.columns:
            if c["name"].lower() == name.lower():
                if type_ and not c["type"]:
                    c["type"] = type_
                if length is not None:
                    c["length"] = length
                if precision is not None:
                    c["precision"], c["scale"] = precision, scale
                return c
        c = {"name": name, "type": type_ or "", "nullable": nullable, "length": length,
             "precision": precision, "scale": scale}
        self.columns.append(c)
        return c

    def add_index(self, cols, unique=False, name=None):
        cols = [unq(c).strip() for c in cols if c.strip()]
        if not cols:
            return
        key = [c.lower() for c in cols]
        for ix in self.indexes:
            if [c.lower() for c in ix["columns"]] == key:
                ix["unique"] = ix["unique"] or unique
                return
        self.indexes.append({"name": name, "columns": cols, "unique": unique})

    def add_fk(self, column, ref_table, ref_column="", on_delete=None):
        column = unq(column)
        for fk in self.fks:
            if fk["column"].lower() == column.lower():
                if on_delete and not fk["on_delete"]:
                    fk["on_delete"] = on_delete
                if ref_table and not fk["ref_table"]:
                    fk["ref_table"] = unq(ref_table)
                return
        self.fks.append({"column": column, "ref_table": unq(ref_table) if ref_table else "",
                         "ref_column": unq(ref_column) if ref_column else "", "on_delete": on_delete, "indexed": False})


class Schema:
    def __init__(self):
        self.tables = {}
        self.sources = []

    def table(self, name, source, kind):
        key = norm(name)
        if key not in self.tables:
            self.tables[key] = Table(unq(name), source, kind)
        t = self.tables[key]
        if source not in t.source:
            t.source += ";" + source
        return t

    def find(self, name):
        return self.tables.get(norm(name)) or self.tables.get(norm(name) + "s") or self.tables.get(norm(name).rstrip("s"))


# ----------------------------------------------------------------------------- SQL DDL
SQL_CREATE_TABLE = re.compile(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w\[\]\".`]+)\s*\(", re.I)
SQL_ALTER_ADD = re.compile(r"\bALTER\s+TABLE\s+(?:ONLY\s+)?([\w\[\]\".`]+)\s+ADD\s+(?:CONSTRAINT\s+[\w\[\]\"`]+\s+)?(PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK)\s*\(([^)]*)\)(.*?)(?:;|$)", re.I | re.S)
SQL_CREATE_INDEX = re.compile(r"\bCREATE\s+(UNIQUE\s+)?(?:CLUSTERED\s+|NONCLUSTERED\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w\[\]\"`.]+)\s+ON\s+([\w\[\]\".`]+)\s*(?:USING\s+\w+\s*)?\(([^)]*)\)", re.I)
SQL_REFERENCES = re.compile(r"REFERENCES\s+([\w\[\]\".`]+)\s*(?:\(([^)]*)\))?(.*)", re.I | re.S)
SQL_ON_DELETE = re.compile(r"ON\s+DELETE\s+(CASCADE|SET\s+NULL|SET\s+DEFAULT|RESTRICT|NO\s+ACTION)", re.I)


def parse_sql_column(item, t):
    m = re.match(r'([\[\]"`\w]+)\s+([\w ]+?)(?:\s*\(\s*(\d+|max)\s*(?:,\s*(\d+))?\s*\))?(?=\s|$)(.*)', item, re.I | re.S)
    if not m:
        return
    name, typ, p1, p2, rest = m.group(1), m.group(2).strip().lower(), m.group(3), m.group(4), m.group(5) or ""
    rest_l = rest.lower()
    length = precision = scale = None
    if p1:
        if typ in ("decimal", "numeric", "number", "money"):
            precision, scale = int(p1), int(p2) if p2 else 0
        elif p1.lower() == "max":
            length = "max"
        else:
            length = int(p1)
    c = t.col(unq(name), typ, nullable="not null" not in rest_l and "primary key" not in rest_l, length=length, precision=precision, scale=scale)
    if typ in ("int", "integer", "bigint", "smallint", "tinyint", "bit", "boolean", "bool", "date", "uniqueidentifier", "uuid", "serial", "bigserial"):
        pass
    if "primary key" in rest_l:
        t.pk = [c["name"]]
    if re.search(r"\bunique\b", rest_l):
        t.add_index([c["name"]], unique=True)
    if "identity" in rest_l or "autoincrement" in rest_l or "auto_increment" in rest_l:
        c["identity"] = True
    rm = SQL_REFERENCES.search(rest)
    if rm:
        od = SQL_ON_DELETE.search(rm.group(3) or "")
        t.add_fk(c["name"], rm.group(1), (rm.group(2) or "").strip(), od.group(1).upper() if od else "NO ACTION")
    if re.search(r"\bcheck\s*\(", rest_l):
        t.checks.append(c["name"])


def parse_sql(schema, root, path, text):
    src = rel(root, path)
    text_nc = re.sub(r"--[^\n]*", "", text)
    text_nc = re.sub(r"/\*.*?\*/", "", text_nc, flags=re.S)
    for m in SQL_CREATE_TABLE.finditer(text_nc):
        body, end = balanced(text_nc, m.end() - 1)
        t = schema.table(m.group(1), f"{src}:{line_of(text_nc, m.start())}", "sql")
        for item in split_top(body):
            il = item.lower()
            if il.startswith("constraint") or il.startswith("primary key") or il.startswith("foreign key") \
                    or il.startswith("unique") or il.startswith("check") or il.startswith("index") or il.startswith("key ") or il.startswith("key("):
                if "primary key" in il:
                    cols = re.search(r"primary\s+key\s*(?:clustered|nonclustered)?\s*\(([^)]*)\)", item, re.I)
                    if cols:
                        t.pk = [unq(c) for c in cols.group(1).split(",")]
                elif "foreign key" in il:
                    fm = re.search(r"foreign\s+key\s*\(([^)]*)\)\s*references\s+([\w\[\]\".`]+)\s*(?:\(([^)]*)\))?(.*)", item, re.I | re.S)
                    if fm:
                        od = SQL_ON_DELETE.search(fm.group(4) or "")
                        for col in fm.group(1).split(","):
                            t.add_fk(col, fm.group(2), (fm.group(3) or "").split(",")[0], od.group(1).upper() if od else "NO ACTION")
                elif il.startswith("unique") or " unique" in il:
                    cols = re.search(r"unique\s*(?:key|index)?\s*[\w\[\]\"`]*\s*\(([^)]*)\)", item, re.I)
                    if cols:
                        t.add_index(cols.group(1).split(","), unique=True)
                elif il.startswith("check") or " check" in il:
                    t.checks.append(item[:80])
                elif il.startswith("index") or il.startswith("key"):
                    cols = re.search(r"\(([^)]*)\)", item)
                    if cols:
                        t.add_index(cols.group(1).split(","))
            else:
                parse_sql_column(item, t)
    for m in SQL_ALTER_ADD.finditer(text_nc):
        t = schema.table(m.group(1), f"{src}:{line_of(text_nc, m.start())}", "sql")
        kind, cols, rest = m.group(2).lower(), [unq(c) for c in m.group(3).split(",")], m.group(4) or ""
        if kind.startswith("primary"):
            t.pk = cols
        elif kind.startswith("foreign"):
            rm = SQL_REFERENCES.search(rest)
            od = SQL_ON_DELETE.search(rest)
            for c in cols:
                t.add_fk(c, rm.group(1) if rm else "", (rm.group(2) or "").split(",")[0] if rm else "", od.group(1).upper() if od else "NO ACTION")
        elif kind == "unique":
            t.add_index(cols, unique=True)
        else:
            t.checks.append(m.group(0)[:80])
    for m in SQL_CREATE_INDEX.finditer(text_nc):
        t = schema.table(m.group(3), f"{src}:{line_of(text_nc, m.start())}", "sql")
        cols = [re.sub(r"\s+(asc|desc)$", "", c.strip(), flags=re.I) for c in m.group(4).split(",")]
        t.add_index(cols, unique=bool(m.group(1)), name=unq(m.group(2)))


# ----------------------------------------------------------------------------- EF Core
CS_TYPE_MAP = {"decimal": "decimal", "double": "double", "float": "float", "single": "float", "datetime": "datetime",
               "datetimeoffset": "datetimeoffset", "string": "string", "int": "int", "long": "bigint", "guid": "uniqueidentifier",
               "bool": "bit", "byte[]": "varbinary", "short": "smallint", "byte": "tinyint", "dateonly": "date", "timeonly": "time"}


def cs_type(raw):
    raw = raw.replace("?", "").strip()
    low = raw.lower()
    return CS_TYPE_MAP.get(low, low), raw.endswith("?")


def parse_ef_snapshot(schema, root, path, text):
    src = rel(root, path)
    for m in re.finditer(r'modelBuilder\.Entity\(\s*"([^"]+)"\s*,\s*b\s*=>\s*\{', text):
        body, end = balanced(text, m.end() - 1, "{", "}")
        clr = m.group(1).split(".")[-1]
        tm = re.search(r'b\.ToTable\(\s*"([^"]+)"', body)
        t = schema.table(tm.group(1) if tm else clr, f"{src}:{line_of(text, m.start())}", "ef-snapshot")
        for pm in re.finditer(r'b\.Property<([^>]+)>\(\s*"([^"]+)"\s*\)((?:\s*\.[A-Za-z]+\([^;]*?\))*)\s*;', body):
            typ, nullable = cs_type(pm.group(1))
            chain = pm.group(3)
            length = precision = scale = None
            ct = re.search(r'HasColumnType\(\s*"([^"]+)"', chain)
            if ct:
                ctl = ct.group(1).lower()
                mm = re.match(r"(\w+(?: \w+)?)\s*(?:\(\s*(\d+|max)\s*(?:,\s*(\d+))?\s*\))?", ctl)
                if mm:
                    typ = mm.group(1)
                    if mm.group(2):
                        if typ in ("decimal", "numeric"):
                            precision, scale = int(mm.group(2)), int(mm.group(3) or 0)
                        else:
                            length = mm.group(2) if mm.group(2) == "max" else int(mm.group(2))
            ml = re.search(r"HasMaxLength\(\s*(\d+)\s*\)", chain)
            if ml:
                length = int(ml.group(1))
            pr = re.search(r"HasPrecision\(\s*(\d+)\s*(?:,\s*(\d+))?\s*\)", chain)
            if pr:
                precision, scale = int(pr.group(1)), int(pr.group(2) or 0)
            c = t.col(pm.group(2), typ, nullable=nullable and "IsRequired()" not in chain, length=length, precision=precision, scale=scale)
            if "IsConcurrencyToken" in chain or "IsRowVersion" in chain:
                c["concurrency"] = True
        for km in re.finditer(r'b\.HasKey\(([^)]*)\)', body):
            t.pk = re.findall(r'"([^"]+)"', km.group(1))
        for im in re.finditer(r'b\.HasIndex\(([^)]*)\)((?:\s*\.[A-Za-z]+\([^)]*\))*)', body):
            t.add_index(re.findall(r'"([^"]+)"', im.group(1)), unique="IsUnique()" in im.group(2))
        for fm in re.finditer(r'b\.HasOne\(\s*"([^"]+)"[^;]*?HasForeignKey\(([^)]*)\)([^;]*);', body, re.S):
            od = re.search(r"DeleteBehavior\.(\w+)", fm.group(3))
            for col in re.findall(r'"([^"]+)"', fm.group(2)):
                t.add_fk(col, fm.group(1).split(".")[-1], "", od.group(1).upper() if od else "CASCADE")
        if "HasQueryFilter" in body:
            t.query_filter = True


def parse_ef_entities(schema, root, files):
    """Entity classes reachable from DbSet<T>, plus fluent configuration."""
    texts = {p: _read(p) for p in files}
    dbsets = set()
    for p, txt in texts.items():
        for m in re.finditer(r"DbSet<(\w+)>\s+(\w+)", txt):
            dbsets.add(m.group(1))
    if not dbsets:
        return
    class_re = re.compile(r"public\s+(?:partial\s+|sealed\s+)?class\s+(\w+)\b[^{]*\{")
    prop_re = re.compile(r"((?:\s*\[[^\]]+\]\s*)*)\s*public\s+(?:virtual\s+)?([\w<>\[\]?,\s.]+?)\s+(\w+)\s*\{\s*get;", re.S)
    for p, txt in texts.items():
        for cm in class_re.finditer(txt):
            cls = cm.group(1)
            if cls not in dbsets:
                continue
            body, _ = balanced(txt, cm.end() - 1, "{", "}")
            tname = cls
            tm = re.search(r'\[Table\(\s*"([^"]+)"', txt[max(0, cm.start() - 300):cm.start()])
            if tm:
                tname = tm.group(1)
            t = schema.table(tname, f"{rel(root, p)}:{line_of(txt, cm.start())}", "ef-entity")
            navs = {}
            for pm in prop_re.finditer(body):
                attrs, rawtype, name = pm.group(1) or "", pm.group(2).strip(), pm.group(3)
                base = rawtype.replace("?", "")
                if base.startswith(("ICollection", "List", "IEnumerable", "HashSet", "IList")):
                    continue
                typ, nullable = cs_type(base) if base.lower().replace("?", "") in CS_TYPE_MAP else (None, rawtype.endswith("?"))
                if typ is None:
                    navs[name] = base   # navigation property
                    fk_attr = re.search(r'ForeignKey\(\s*"(\w+)"', attrs)
                    if fk_attr:
                        t.add_fk(fk_attr.group(1), base)
                    continue
                length = precision = scale = None
                ml = re.search(r"(?:MaxLength|StringLength)\(\s*(\d+)", attrs)
                if ml:
                    length = int(ml.group(1))
                ct = re.search(r'Column\([^)]*TypeName\s*=\s*"([^"]+)"', attrs)
                if ct:
                    mm = re.match(r"(\w+)\s*(?:\(\s*(\d+|max)\s*(?:,\s*(\d+))?\s*\))?", ct.group(1).lower())
                    if mm:
                        typ = mm.group(1)
                        if mm.group(2) and typ in ("decimal", "numeric"):
                            precision, scale = int(mm.group(2)), int(mm.group(3) or 0)
                        elif mm.group(2):
                            length = mm.group(2) if mm.group(2) == "max" else int(mm.group(2))
                if "[Required]" in attrs:
                    nullable = False
                c = t.col(name, typ, nullable=nullable, length=length, precision=precision, scale=scale)
                if "[Key]" in attrs or (name.lower() in ("id", cls.lower() + "id") and not t.pk):
                    t.pk = [name]
                if "[Timestamp]" in attrs or "ConcurrencyCheck" in attrs:
                    c["concurrency"] = True
                fk_attr = re.search(r'ForeignKey\(\s*"(\w+)"', attrs)
                if fk_attr:
                    t.add_fk(name, fk_attr.group(1))
            # convention: <Nav>Id + navigation <Nav> => FK with an EF-generated index
            for nav, navtype in navs.items():
                for c in t.columns:
                    if c["name"].lower() in (nav.lower() + "id", navtype.lower() + "id"):
                        t.add_fk(c["name"], navtype)
                        t.add_index([c["name"]], name="(EF convention)")
    # fluent configuration
    for p, txt in texts.items():
        for m in re.finditer(r"(?:IEntityTypeConfiguration<(\w+)>|modelBuilder\.Entity<(\w+)>\s*\(\s*\))", txt):
            cls = m.group(1) or m.group(2)
            t = schema.find(cls)
            if not t:
                continue
            seg = txt[m.end(): m.end() + 6000] if m.group(1) else txt[m.end(): txt.find("modelBuilder.Entity<", m.end() + 1) if txt.find("modelBuilder.Entity<", m.end() + 1) > 0 else len(txt)]
            for km in re.finditer(r"HasKey\(\s*\w+\s*=>\s*(?:new\s*\{)?([^})]*)\}?\s*\)", seg):
                t.pk = re.findall(r"\.(\w+)", km.group(1))
            for im in re.finditer(r"HasIndex\(\s*\w+\s*=>\s*(?:new\s*\{)?([^})]*)\}?\s*\)((?:\s*\.[A-Za-z]+\([^)]*\))*)", seg):
                t.add_index(re.findall(r"\.(\w+)", im.group(1)), unique="IsUnique()" in im.group(2))
            for pm in re.finditer(r"Property\(\s*\w+\s*=>\s*\w+\.(\w+)\s*\)((?:\s*\.[A-Za-z]+\([^;]*?\))*)", seg):
                chain = pm.group(2)
                c = t.col(pm.group(1))
                ml = re.search(r"HasMaxLength\(\s*(\d+)", chain)
                if ml:
                    c["length"] = int(ml.group(1))
                pr = re.search(r"HasPrecision\(\s*(\d+)\s*(?:,\s*(\d+))?", chain)
                if pr:
                    c["precision"], c["scale"] = int(pr.group(1)), int(pr.group(2) or 0)
                ct = re.search(r'HasColumnType\(\s*"([^"]+)"', chain)
                if ct:
                    mm = re.match(r"(\w+)\s*(?:\(\s*(\d+)\s*(?:,\s*(\d+))?\s*\))?", ct.group(1).lower())
                    if mm:
                        c["type"] = mm.group(1)
                        if mm.group(2) and c["type"] in ("decimal", "numeric"):
                            c["precision"], c["scale"] = int(mm.group(2)), int(mm.group(3) or 0)
                if "IsRowVersion" in chain or "IsConcurrencyToken" in chain:
                    c["concurrency"] = True
                if "IsRequired()" in chain:
                    c["nullable"] = False
            for fm in re.finditer(r"HasOne\(\s*\w+\s*=>\s*\w+\.(\w+)\s*\)[^;]*?HasForeignKey\(\s*\w+\s*=>\s*\w+\.(\w+)\s*\)([^;]*);", seg, re.S):
                od = re.search(r"DeleteBehavior\.(\w+)", fm.group(3))
                t.add_fk(fm.group(2), fm.group(1), "", od.group(1).upper() if od else "CASCADE")
                t.add_index([fm.group(2)], name="(EF convention)")
            if "HasQueryFilter" in seg:
                t.query_filter = True


# ----------------------------------------------------------------------------- JPA
JAVA_TYPES = {"bigdecimal": "decimal", "double": "double", "float": "float", "string": "string", "localdatetime": "localdatetime",
              "instant": "instant", "offsetdatetime": "offsetdatetime", "zoneddatetime": "zoneddatetime", "date": "datetime",
              "timestamp": "timestamp", "localdate": "date", "long": "bigint", "integer": "int", "int": "int", "boolean": "bit", "uuid": "uuid"}


def parse_jpa(schema, root, path, text):
    if "@Entity" not in text:
        return
    src = rel(root, path)
    cm = re.search(r"@Entity[\s\S]*?class\s+(\w+)", text)
    if not cm:
        return
    cls = cm.group(1)
    head = text[:cm.end()]
    tm = re.search(r'@Table\s*\(([\s\S]*?)\)\s*(?=@|public|class)', head)
    tname = cls
    t = None
    if tm:
        nm = re.search(r'name\s*=\s*"([^"]+)"', tm.group(1))
        if nm:
            tname = nm.group(1)
    t = schema.table(tname, f"{src}:{line_of(text, cm.start())}", "jpa")
    if tm:
        for im in re.finditer(r'@Index\s*\(([^)]*)\)', tm.group(1)):
            cl = re.search(r'columnList\s*=\s*"([^"]+)"', im.group(1))
            if cl:
                t.add_index(cl.group(1).split(","), unique="unique = true" in im.group(1).replace(" ", " "))
        for um in re.finditer(r'@UniqueConstraint\s*\(([^)]*)\)', tm.group(1)):
            cl = re.search(r'columnNames\s*=\s*\{([^}]*)\}', um.group(1))
            if cl:
                t.add_index(re.findall(r'"([^"]+)"', cl.group(1)), unique=True)
    body = text[cm.end():]
    field_re = re.compile(r"((?:\s*@\w+(?:\([^;{]*?\))?\s*)*)\s*(?:private|protected|public)\s+(?:final\s+)?([\w<>\[\].]+)\s+(\w+)\s*(?:=[^;]*)?;", re.S)
    for fm in field_re.finditer(body):
        attrs, jtype, name = fm.group(1) or "", fm.group(2), fm.group(3)
        if "static" in fm.group(0).split(jtype)[0]:
            continue
        if re.search(r"@(OneToMany|ManyToMany|Transient)", attrs):
            continue
        col_name = name
        cm2 = re.search(r'@Column\s*\(([^)]*)\)', attrs)
        jc = re.search(r'@JoinColumn\s*\(([^)]*)\)', attrs)
        if re.search(r"@(ManyToOne|OneToOne)", attrs):
            fk_col = col_name + "_id"
            if jc:
                nm = re.search(r'name\s*=\s*"([^"]+)"', jc.group(1))
                if nm:
                    fk_col = nm.group(1)
            t.col(fk_col, "bigint", nullable="optional = false" not in attrs and (not jc or "nullable = false" not in jc.group(1)))
            od = re.search(r"@OnDelete\s*\([^)]*OnDeleteAction\.(\w+)", attrs)
            cascade = "CASCADE" if od and od.group(1) == "CASCADE" else ("CASCADE(orm)" if "CascadeType.REMOVE" in attrs or "CascadeType.ALL" in attrs else "NO ACTION")
            t.add_fk(fk_col, jtype.split("<")[-1].rstrip(">"), "id", cascade)
            continue
        length = precision = scale = None
        nullable = True
        typ = JAVA_TYPES.get(jtype.split("<")[0].split(".")[-1].lower(), jtype.lower())
        if cm2:
            a = cm2.group(1)
            nm = re.search(r'name\s*=\s*"([^"]+)"', a)
            if nm:
                col_name = nm.group(1)
            ln = re.search(r"length\s*=\s*(\d+)", a)
            if ln:
                length = int(ln.group(1))
            pr = re.search(r"precision\s*=\s*(\d+)", a)
            sc = re.search(r"scale\s*=\s*(\d+)", a)
            if pr:
                precision, scale = int(pr.group(1)), int(sc.group(1)) if sc else 0
            if "nullable = false" in a.replace(" ", " "):
                nullable = False
            cd = re.search(r'columnDefinition\s*=\s*"([^"]+)"', a)
            if cd:
                mm = re.match(r"(\w+(?: \w+)?)\s*(?:\(\s*(\d+)\s*(?:,\s*(\d+))?\s*\))?", cd.group(1).lower())
                if mm:
                    typ = mm.group(1)
                    if mm.group(2) and typ in ("decimal", "numeric"):
                        precision, scale = int(mm.group(2)), int(mm.group(3) or 0)
                    elif mm.group(2):
                        length = int(mm.group(2))
        elif typ == "string":
            length = 255   # Hibernate default
        if "@Lob" in attrs:
            length = None
        c = t.col(col_name, typ, nullable=nullable, length=length, precision=precision, scale=scale)
        if "@Id" in attrs or "@EmbeddedId" in attrs:
            t.pk.append(col_name)
        if "@Version" in attrs:
            c["concurrency"] = True
        if re.search(r"@Index\b", attrs):
            t.add_index([col_name])
    if re.search(r"@(SQLDelete|SoftDelete|Where\s*\(\s*clause)", text):
        t.query_filter = True


# ----------------------------------------------------------------------------- Prisma
def parse_prisma(schema, root, path, text):
    src = rel(root, path)
    for m in re.finditer(r"\bmodel\s+(\w+)\s*\{", text):
        body, _ = balanced(text, m.end() - 1, "{", "}")
        name = m.group(1)
        mp = re.search(r'@@map\(\s*"([^"]+)"', body)
        t = schema.table(mp.group(1) if mp else name, f"{src}:{line_of(text, m.start())}", "prisma")
        rels = {}
        for line in body.splitlines():
            line = line.split("//")[0].strip()
            if not line or line.startswith("@@"):
                continue
            fm = re.match(r"(\w+)\s+([\w\[\]?]+)\s*(.*)", line)
            if not fm:
                continue
            fname, ftype, rest = fm.groups()
            base = ftype.rstrip("?[]")
            nullable = ftype.endswith("?")
            if "@relation" in rest:
                fl = re.search(r"fields\s*:\s*\[([^\]]*)\]", rest)
                od = re.search(r"onDelete\s*:\s*(\w+)", rest)
                if fl:
                    for col in fl.group(1).split(","):
                        rels[col.strip()] = (base, od.group(1).upper() if od else "CASCADE" if not nullable else "SET NULL")
                continue
            if base[0].isupper() and base not in ("Int", "BigInt", "Float", "Decimal", "String", "DateTime", "Boolean", "Bytes", "Json"):
                continue   # relation list / enum
            typ = base.lower()
            length = precision = scale = None
            db = re.search(r"@db\.(\w+)(?:\(([^)]*)\))?", rest)
            if db:
                typ = db.group(1).lower()
                args = [a.strip() for a in (db.group(2) or "").split(",") if a.strip()]
                if typ in ("decimal", "money") and args:
                    precision, scale = int(args[0]), int(args[1]) if len(args) > 1 else 0
                elif args and args[0].isdigit():
                    length = int(args[0])
            if typ == "float":
                typ = "double"
            if typ == "datetime":
                typ = "timestamp"
            c = t.col(fname, typ, nullable=nullable, length=length, precision=precision, scale=scale)
            if "@id" in rest:
                t.pk = [fname]
            if "@unique" in rest:
                t.add_index([fname], unique=True)
        for col, (ref, od) in rels.items():
            t.add_fk(col, ref, "id", od)
        for im in re.finditer(r"@@(id|index|unique)\(\s*\[([^\]]*)\]", body):
            cols = [c.strip() for c in im.group(2).split(",")]
            if im.group(1) == "id":
                t.pk = cols
            else:
                t.add_index(cols, unique=im.group(1) == "unique")


# ----------------------------------------------------------------------------- TypeORM
def parse_typeorm(schema, root, path, text):
    if "@Entity" not in text:
        return
    src = rel(root, path)
    for cm in re.finditer(r"((?:@\w+\([^)]*\)\s*)*)@Entity\s*\(([^)]*)\)((?:\s*@\w+\([^)]*\))*)\s*export\s+class\s+(\w+)", text):
        cls = cm.group(4)
        nm = re.search(r"['\"](\w+)['\"]", cm.group(2))
        t = schema.table(nm.group(1) if nm else cls, f"{src}:{line_of(text, cm.start())}", "typeorm")
        for im in re.finditer(r"@(Index|Unique)\(\s*(?:['\"][^'\"]*['\"]\s*,\s*)?\[([^\]]*)\]", cm.group(1) + cm.group(3)):
            t.add_index(re.findall(r"['\"](\w+)['\"]", im.group(2)), unique=im.group(1) == "Unique")
        brace = text.find("{", cm.end())
        body, _ = balanced(text, brace, "{", "}")
        field_re = re.compile(r"((?:\s*@\w+(?:\((?:[^()]|\([^()]*\))*\))?\s*)+)\s*(\w+)\s*[?!]?\s*:\s*([\w<>\[\]| ]+)", re.S)
        for fm in field_re.finditer(body):
            attrs, name, tstype = fm.group(1), fm.group(2), fm.group(3).strip()
            if re.search(r"@(OneToMany|ManyToMany)\b", attrs):
                continue
            if re.search(r"@(ManyToOne|OneToOne)\b", attrs):
                jc = re.search(r"@JoinColumn\s*\(\s*\{[^}]*name\s*:\s*['\"](\w+)['\"]", attrs)
                col = jc.group(1) if jc else name + "Id"
                od = re.search(r"onDelete\s*:\s*['\"](\w+)['\"]", attrs)
                ref = re.search(r"@(?:ManyToOne|OneToOne)\s*\(\s*\(\)\s*=>\s*(\w+)", attrs)
                t.col(col, "int", nullable="nullable: false" not in attrs)
                t.add_fk(col, ref.group(1) if ref else tstype, "id", od.group(1).upper() if od else "NO ACTION")
                if re.search(r"@Index\(\s*\)", attrs):
                    t.add_index([col])
                continue
            col_dec = re.search(r"@(Column|PrimaryColumn|PrimaryGeneratedColumn|CreateDateColumn|UpdateDateColumn|DeleteDateColumn|VersionColumn)\s*\(((?:[^()]|\([^()]*\))*)\)", attrs)
            if not col_dec:
                continue
            kind, args = col_dec.group(1), col_dec.group(2)
            col_name = name
            nm = re.search(r"name\s*:\s*['\"](\w+)['\"]", args)
            if nm:
                col_name = nm.group(1)
            typ = None
            tm = re.search(r"^\s*['\"](\w[\w ]*)['\"]", args) or re.search(r"type\s*:\s*['\"](\w[\w ]*)['\"]", args)
            if tm:
                typ = tm.group(1).lower()
            elif kind in ("CreateDateColumn", "UpdateDateColumn", "DeleteDateColumn"):
                typ = "timestamp"
            elif kind == "VersionColumn":
                typ = "int"
            else:
                typ = {"number": "int", "string": "string", "boolean": "bit", "date": "timestamp"}.get(tstype.lower(), tstype.lower())
            if typ == "varchar" or typ == "text" or typ == "nvarchar" or typ == "char":
                pass
            length = precision = scale = None
            ln = re.search(r"length\s*:\s*(\d+)", args)
            if ln:
                length = int(ln.group(1))
            elif typ == "string":
                length = 255
            pr = re.search(r"precision\s*:\s*(\d+)", args)
            sc = re.search(r"scale\s*:\s*(\d+)", args)
            if pr:
                precision, scale = int(pr.group(1)), int(sc.group(1)) if sc else 0
            c = t.col(col_name, typ, nullable="nullable: true" in args.replace(" ", " ") or kind == "DeleteDateColumn", length=length, precision=precision, scale=scale)
            if kind.startswith("Primary"):
                t.pk.append(col_name)
            if kind == "VersionColumn":
                c["concurrency"] = True
            if kind == "DeleteDateColumn":
                t.query_filter = True
            if "unique: true" in args.replace(" ", " "):
                t.add_index([col_name], unique=True)
            if re.search(r"@Index\(\s*(?:\{[^}]*\})?\s*\)", attrs):
                t.add_index([col_name])


# ----------------------------------------------------------------------------- Knex
def parse_knex(schema, root, path, text):
    src = rel(root, path)
    for m in re.finditer(r"\.(createTable|createTableIfNotExists|alterTable|table)\(\s*['\"](\w+)['\"]\s*,\s*(?:async\s*)?(?:function\s*)?\(?\s*(\w+)\s*\)?\s*(?:=>)?\s*\{", text):
        body, _ = balanced(text, m.end() - 1, "{", "}")
        t = schema.table(m.group(2), f"{src}:{line_of(text, m.start())}", "knex")
        v = re.escape(m.group(3))
        for cm in re.finditer(v + r"\.(\w+)\(\s*(?:['\"](\w+)['\"])?([^;]*?);", body, re.S):
            meth, col, rest = cm.group(1), cm.group(2), cm.group(0)
            if meth in ("increments", "bigIncrements"):
                t.col(col or "id", "int", nullable=False)
                t.pk = [col or "id"]
                continue
            if meth == "primary":
                t.pk = re.findall(r"['\"](\w+)['\"]", rest)
                continue
            if meth in ("index", "unique"):
                t.add_index(re.findall(r"['\"](\w+)['\"]", cm.group(3) if col is None else cm.group(0).split("(", 1)[1]), unique=meth == "unique")
                continue
            if meth == "timestamps":
                t.col("created_at", "timestamptz" if "true" in rest else "timestamp")
                t.col("updated_at", "timestamptz" if "true" in rest else "timestamp")
                continue
            if meth in ("foreign",):
                fk = re.search(r"foreign\(\s*['\"](\w+)['\"]\s*\)[^;]*references\(\s*['\"]([\w.]+)['\"]\s*\)(?:[^;]*inTable\(\s*['\"](\w+)['\"]\s*\))?", rest)
                if fk:
                    ref = fk.group(3) or fk.group(2).split(".")[0]
                    od = re.search(r"onDelete\(\s*['\"](\w+)['\"]", rest, re.I)
                    t.add_fk(fk.group(1), ref, "", od.group(1).upper() if od else "NO ACTION")
                continue
            if not col:
                continue
            typ = {"float": "float", "double": "double", "decimal": "decimal", "string": "string", "text": "text", "integer": "int",
                   "bigInteger": "bigint", "boolean": "bit", "timestamp": "timestamp", "datetime": "datetime", "date": "date",
                   "uuid": "uuid", "json": "json", "jsonb": "jsonb", "binary": "varbinary", "enu": "string", "enum": "string"}.get(meth, meth.lower())
            length = precision = scale = None
            args = re.match(r"\(\s*['\"]\w+['\"]\s*(?:,\s*(\d+))?(?:\s*,\s*(\d+))?", cm.group(0)[cm.group(0).find("("):])
            if meth == "decimal":
                precision, scale = (int(args.group(1)) if args and args.group(1) else 8), (int(args.group(2)) if args and args.group(2) else 2)
            elif meth == "string":
                length = int(args.group(1)) if args and args.group(1) else 255
            if meth in ("timestamp", "datetime") and re.search(r"useTz\s*:\s*true", rest):
                typ = "timestamptz"
            c = t.col(col, typ, nullable="notNullable" not in rest and "primary()" not in rest, length=length, precision=precision, scale=scale)
            if ".primary()" in rest:
                t.pk = [col]
            if ".unique()" in rest:
                t.add_index([col], unique=True)
            if ".index(" in rest:
                t.add_index([col])
            rm = re.search(r"references\(\s*['\"]([\w.]+)['\"]\s*\)(?:[^;]*inTable\(\s*['\"](\w+)['\"]\s*\))?", rest)
            if rm:
                ref = rm.group(2) or rm.group(1).split(".")[0]
                od = re.search(r"onDelete\(\s*['\"]([\w ]+)['\"]", rest, re.I)
                t.add_fk(col, ref, "", od.group(1).upper() if od else "NO ACTION")


# ----------------------------------------------------------------------------- Django / SQLAlchemy
DJANGO_TYPES = {"FloatField": "double", "DecimalField": "decimal", "CharField": "string", "TextField": "text", "EmailField": "string",
                "DateTimeField": "datetime", "DateField": "date", "IntegerField": "int", "BigIntegerField": "bigint", "PositiveIntegerField": "int",
                "BooleanField": "bit", "UUIDField": "uuid", "JSONField": "json", "AutoField": "int", "BigAutoField": "bigint", "SlugField": "string", "URLField": "string"}


def parse_django(schema, root, path, text):
    if "models.Model" not in text and "(Model)" not in text:
        return
    src = rel(root, path)
    use_tz = None
    for m in re.finditer(r"^class\s+(\w+)\s*\(([^)]*)\)\s*:", text, re.M):
        if "Model" not in m.group(2):
            continue
        cls = m.group(1)
        start = m.end()
        nxt = re.search(r"^class\s+\w+", text[start:], re.M)
        body = text[start: start + nxt.start()] if nxt else text[start:]
        if "abstract = True" in body:
            continue
        dt = re.search(r"db_table\s*=\s*['\"](\w+)['\"]", body)
        t = schema.table(dt.group(1) if dt else cls.lower(), f"{src}:{line_of(text, m.start())}", "django")
        explicit_pk = False
        for fm in re.finditer(r"^\s+(\w+)\s*=\s*models\.(\w+)\(", body, re.M):
            name, ftype = fm.groups()
            args, _ = balanced(body, fm.end() - 1)
            if ftype in ("ManyToManyField", "GenericRelation"):
                continue
            if ftype in ("ForeignKey", "OneToOneField"):
                ref = re.match(r"\s*['\"]?([\w.]+)['\"]?", args)
                od = re.search(r"on_delete\s*=\s*models\.(\w+)", args)
                col = name + "_id"
                t.col(col, "bigint", nullable="null=True" in args.replace(" ", ""))
                t.add_fk(col, (ref.group(1).split(".")[-1] if ref else "").lower(), "id", od.group(1).upper() if od else "CASCADE")
                if "db_index=False" not in args.replace(" ", ""):
                    t.add_index([col], name="(django auto)")
                if "primary_key=True" in args.replace(" ", ""):
                    t.pk = [col]; explicit_pk = True
                continue
            typ = DJANGO_TYPES.get(ftype, ftype.lower())
            length = precision = scale = None
            ml = re.search(r"max_length\s*=\s*(\d+)", args)
            if ml:
                length = int(ml.group(1))
            md = re.search(r"max_digits\s*=\s*(\d+)", args)
            dp = re.search(r"decimal_places\s*=\s*(\d+)", args)
            if md:
                precision, scale = int(md.group(1)), int(dp.group(1)) if dp else 0
            c = t.col(name, typ, nullable="null=True" in args.replace(" ", ""), length=length, precision=precision, scale=scale)
            if "primary_key=True" in args.replace(" ", ""):
                t.pk = [name]; explicit_pk = True
            if "unique=True" in args.replace(" ", ""):
                t.add_index([name], unique=True)
            elif "db_index=True" in args.replace(" ", ""):
                t.add_index([name])
        if not explicit_pk:
            t.col("id", "bigint", nullable=False)
            t.pk = ["id"]
        for im in re.finditer(r"models\.Index\(\s*fields\s*=\s*\[([^\]]*)\]", body):
            t.add_index([c.strip("'\" ").lstrip("-") for c in im.group(1).split(",")])
        for um in re.finditer(r"UniqueConstraint\(\s*fields\s*=\s*\[([^\]]*)\]", body):
            t.add_index([c.strip("'\" ") for c in um.group(1).split(",")], unique=True)
        for um in re.finditer(r"unique_together\s*=\s*[\[(]\s*[\[(]?([^\])]*)", body):
            t.add_index([c.strip("'\" ") for c in um.group(1).split(",") if c.strip()], unique=True)
        if "CheckConstraint" in body:
            t.checks.append("Meta.constraints")
        if re.search(r"objects\s*=\s*\w*(SoftDelete|Active)\w*Manager", body):
            t.query_filter = True
    # settings
    if os.path.basename(path) == "settings.py":
        pass


def parse_sqlalchemy(schema, root, path, text):
    if "Column(" not in text or ("__tablename__" not in text and "Table(" not in text):
        return
    src = rel(root, path)
    for m in re.finditer(r"^class\s+(\w+)\s*\([^)]*\)\s*:", text, re.M):
        start = m.end()
        nxt = re.search(r"^class\s+\w+", text[start:], re.M)
        body = text[start: start + nxt.start()] if nxt else text[start:]
        tn = re.search(r"__tablename__\s*=\s*['\"](\w+)['\"]", body)
        if not tn:
            continue
        t = schema.table(tn.group(1), f"{src}:{line_of(text, m.start())}", "sqlalchemy")
        for cm in re.finditer(r"^\s+(\w+)\s*(?::\s*Mapped\[[^\]]*\])?\s*=\s*(?:mapped_column|Column)\(", body, re.M):
            name = cm.group(1)
            args, _ = balanced(body, cm.end() - 1)
            typ_m = re.search(r"\b(Float|Numeric|DECIMAL|Decimal|String|Text|DateTime|Date|Integer|BigInteger|Boolean|Uuid|UUID|JSON|LargeBinary|TIMESTAMP)\b(?:\(([^)]*)\))?", args)
            typ = typ_m.group(1).lower() if typ_m else ""
            length = precision = scale = None
            if typ_m and typ_m.group(2):
                nums = re.findall(r"\d+", typ_m.group(2))
                if typ in ("numeric", "decimal") and nums:
                    precision, scale = int(nums[0]), int(nums[1]) if len(nums) > 1 else 0
                elif nums:
                    length = int(nums[0])
                if typ in ("datetime", "timestamp") and "timezone=True" in typ_m.group(2).replace(" ", ""):
                    typ = "timestamptz"
            if typ == "float":
                typ = "double"
            c = t.col(name, typ, nullable="nullable=False" not in args.replace(" ", "") and "primary_key=True" not in args.replace(" ", ""), length=length, precision=precision, scale=scale)
            if "primary_key=True" in args.replace(" ", ""):
                t.pk.append(name)
            if "unique=True" in args.replace(" ", ""):
                t.add_index([name], unique=True)
            elif "index=True" in args.replace(" ", ""):
                t.add_index([name])
            fk = re.search(r"ForeignKey\(\s*['\"]([\w.]+)['\"]([^)]*)\)", args)
            if fk:
                od = re.search(r"ondelete\s*=\s*['\"](\w+)['\"]", fk.group(2), re.I)
                t.add_fk(name, fk.group(1).split(".")[0], fk.group(1).split(".")[-1], od.group(1).upper() if od else "NO ACTION")
        for im in re.finditer(r"(Index|UniqueConstraint)\(\s*(?:['\"][^'\"]*['\"]\s*,\s*)?((?:['\"]\w+['\"]\s*,?\s*)+)", body):
            t.add_index(re.findall(r"['\"](\w+)['\"]", im.group(2)), unique=im.group(1) == "UniqueConstraint")
        if "version_id_col" in body:
            for c in t.columns:
                if CONCURRENCY_RE.match(c["name"]):
                    c["concurrency"] = True


# ----------------------------------------------------------------------------- analysis
def is_money(col):
    typ = (col.get("type") or "").lower()
    if typ in NAIVE_TS | TZ_TS or typ in ("date", "time", "bit", "boolean", "bool"):
        return False
    return bool(MONEY_RE.search(col["name"])) and not re.search(r"(id|code|type|status|name|date|count|qty|quantity|percent|currency|_?at|_?on|_?time|_?by)$", col["name"], re.I)


def analyse(t, all_names, engine_auto_fk_index=False):
    issues = []
    cols = t.columns
    colnames = {c["name"].lower() for c in cols}
    index_leads = {ix["columns"][0].lower() for ix in t.indexes if ix["columns"]}
    if t.pk:
        index_leads.add(t.pk[0].lower())

    if not t.pk:
        issues.append({"code": "NO_PK", "detail": "no primary key defined"})
    for fk in t.fks:
        fk["indexed"] = fk["column"].lower() in index_leads or engine_auto_fk_index
        if not fk["indexed"]:
            issues.append({"code": "FK_NOT_INDEXED", "detail": f"{fk['column']} -> {fk['ref_table']} has no index whose leading column is the FK"})
        if fk["on_delete"] and fk["on_delete"].startswith("CASCADE") and SHARED_REF_RE.match(fk["ref_table"] or ""):
            issues.append({"code": "CASCADE_FROM_SHARED_REFERENCE", "detail": f"{fk['column']} cascades delete from shared table {fk['ref_table']}"})
    fk_cols = {fk["column"].lower() for fk in t.fks}
    for c in cols:
        n, typ = c["name"], (c["type"] or "").lower()
        nl = n.lower()
        if ID_LIKE_RE.match(n) and nl not in fk_cols and nl not in [p.lower() for p in t.pk] and nl != "id" and not TENANT_RE.match(n):
            base = ID_LIKE_RE.match(n).group(1)
            if norm(base) in all_names or norm(base) + "s" in all_names or norm(base) + "es" in all_names or norm(base)[:-1] in all_names:
                issues.append({"code": "FK_LIKE_COLUMN_WITHOUT_FK", "detail": f"{n} looks like a reference to {base} but has no foreign key (and therefore no FK index)"})
        if is_money(c):
            if typ in FLOAT_TYPES:
                issues.append({"code": "FLOAT_MONEY", "detail": f"{n} is {typ}; money must be decimal/numeric"})
            elif typ in ("decimal", "numeric", "money") and c.get("precision") is None:
                issues.append({"code": "MONEY_NO_PRECISION", "detail": f"{n} is {typ} without explicit precision/scale"})
            elif typ in ("int", "bigint", "integer") and not re.search(r"(cents|minor|paisa|pence)", nl):
                issues.append({"code": "MONEY_INTEGER_UNDOCUMENTED", "detail": f"{n} is {typ}; fine only if minor units are documented"})
        if typ in NAIVE_TS or (typ == "timestamp" and c.get("kind") != "tz"):
            if typ != "timestamp" or "timestamptz" not in typ:
                issues.append({"code": "NAIVE_TIMESTAMP", "detail": f"{n} is {typ} (no time zone)"})
        if typ in ("string", "nvarchar", "varchar", "nchar", "char", "text", "ntext", "clob", "longtext", "character varying") and (c.get("length") in (None, "max") or (isinstance(c.get("length"), int) and c["length"] > 4000)) and not FREE_TEXT_RE.search(n):
            if not (typ == "text" and t.kind in ("sql",) and FREE_TEXT_RE.search(n)):
                issues.append({"code": "UNBOUNDED_STRING", "detail": f"{n} is {typ} with no length bound"})
        if sensitive_plaintext(n) and typ in ("string", "nvarchar", "varchar", "text", "char", "nchar", "ntext", ""):
            issues.append({"code": "SENSITIVE_PLAINTEXT_COLUMN", "detail": f"{n} is stored as {typ or 'unknown'}; expect a hash or encrypted column"})
    audit = {"created_at": any(AUDIT_CREATED_AT.match(c["name"]) for c in cols),
             "updated_at": any(AUDIT_UPDATED_AT.match(c["name"]) for c in cols),
             "created_by": any(AUDIT_CREATED_BY.match(c["name"]) for c in cols),
             "updated_by": any(AUDIT_UPDATED_BY.match(c["name"]) for c in cols)}
    if not audit["created_at"] and not audit["updated_at"]:
        issues.append({"code": "NO_AUDIT_COLUMNS", "detail": "no created/updated timestamp columns"})
    soft = next((c["name"] for c in cols if SOFT_DELETE_RE.match(c["name"])), None)
    if soft and not t.query_filter and t.kind != "sql":
        issues.append({"code": "SOFT_DELETE_NO_QUERY_FILTER", "detail": f"{soft} present but no global query filter / soft-delete manager detected in the model"})
    conc = next((c["name"] for c in cols if c.get("concurrency") or (CONCURRENCY_RE.match(c["name"]) and (c["type"] or "").lower() in ("rowversion", "timestamp", "varbinary", "int", "bigint", "long"))), None)
    if not conc:
        issues.append({"code": "NO_CONCURRENCY_TOKEN", "detail": "no rowversion/version column (lost-update risk on concurrent edits)"})
    # redundant / duplicate indexes
    for i, a in enumerate(t.indexes):
        for j, b in enumerate(t.indexes):
            if i == j:
                continue
            ac = [c.lower() for c in a["columns"]]
            bc = [c.lower() for c in b["columns"]]
            if len(ac) < len(bc) and bc[:len(ac)] == ac and not a["unique"]:
                issues.append({"code": "REDUNDANT_INDEX", "detail": f"index on ({', '.join(a['columns'])}) is a left prefix of ({', '.join(b['columns'])})"})
    tenant_cols = [c["name"] for c in cols if TENANT_RE.match(c["name"])]
    return {
        "table": t.name, "source": t.source, "kind": t.kind,
        "pk": t.pk, "columns": cols, "fks": t.fks, "indexes": t.indexes, "checks": t.checks,
        "money_columns": [{"name": c["name"], "type": c["type"], "precision": c.get("precision"), "scale": c.get("scale")} for c in cols if is_money(c)],
        "timestamp_columns": [{"name": c["name"], "type": c["type"], "tz_aware": (c["type"] or "").lower() in TZ_TS} for c in cols if (c["type"] or "").lower() in NAIVE_TS | TZ_TS or "time" in (c["type"] or "").lower()],
        "unbounded_strings": [c["name"] for c in cols if any(i["code"] == "UNBOUNDED_STRING" and i["detail"].startswith(c["name"] + " ") for i in issues)],
        "audit_columns": audit, "soft_delete": soft, "query_filter": t.query_filter, "concurrency_token": conc,
        "tenant_columns": tenant_cols, "issues": issues,
    }


QUERY_HINT_RE = r"(?:\.Where\(|\.OrderBy(?:Descending)?\(|\.filter\(|\.exclude\(|\.order_by\(|where\s*:\s*\{|orderBy\s*:\s*\{|findBy|\bWHERE\b|\bORDER\s+BY\b|\.where\(|\.orderBy\(|createQueryBuilder)"


def scan_code_usage(root, tables, max_files=4000):
    """Find code lines that filter/sort by a column of a table (justification for index recommendations)."""
    wanted = {}
    for tb in tables:
        for c in tb["columns"]:
            if c["name"].lower() in ("id",) or len(c["name"]) < 3:
                continue
            wanted.setdefault(c["name"].lower(), []).append(tb["table"])
    hint = re.compile(QUERY_HINT_RE)
    usage = {}
    n = 0
    for path in iter_files(root, {".cs", ".java", ".kt", ".ts", ".js", ".py", ".sql"}):
        n += 1
        if n > max_files:
            break
        text = _read(path)
        if not hint.search(text):
            continue
        rp = rel(root, path)
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            if not hint.search(line) or re.search(r"CREATE\s+(UNIQUE\s+)?INDEX", line, re.I):
                continue
            ctx = " ".join(lines[max(0, i - 3): i + 2]).lower()
            for word in set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", line)):
                wl = word.lower()
                if wl in wanted:
                    entry = f"{rp}:{i}: {line.strip()[:140]}"
                    bucket = usage.setdefault(wl, [])
                    if not any(e["text"] == entry for e in bucket):
                        bucket.append({"text": entry, "ctx": ctx})
    return usage


def _stem(table):
    st = norm(table)
    for suf in ("ies", "es", "s"):
        if st.endswith(suf) and len(st) - len(suf) >= 4:
            return st[: -len(suf)] if suf != "ies" else st[:-3] + "y"
    return st


def _usage_for(usage, col, table):
    st = _stem(table)
    return [u["text"] for u in usage.get(col.lower(), []) if st in re.sub(r"[^a-z0-9]", "", u["ctx"])]


def recommend_indexes(tables, usage):
    recs = []
    for tb in tables:
        leads = {ix["columns"][0].lower() for ix in tb["indexes"] if ix["columns"]} | {p.lower() for p in tb["pk"][:1]}
        tenant = tb["tenant_columns"]
        in_any_index = {c.lower() for ix in tb["indexes"] for c in ix["columns"]} | {p.lower() for p in tb["pk"]}
        for fk in tb["fks"]:
            if not fk["indexed"]:
                cols = tenant + [fk["column"]] if tenant and fk["column"] not in tenant else [fk["column"]]
                just = [f"FK join/lookup {tb['table']}.{fk['column']} -> {fk['ref_table']}; cascades and joins scan without it"]
                just += _usage_for(usage, fk["column"], tb["table"])[:3]
                recs.append({"table": tb["table"], "columns": cols, "type": "non-clustered", "reason": "unindexed foreign key", "justifying_queries": just})
        for i in tb["issues"]:
            if i["code"] == "FK_LIKE_COLUMN_WITHOUT_FK":
                col = i["detail"].split(" ")[0]
                if col.lower() in in_any_index:
                    continue
                cols = tenant + [col] if tenant else [col]
                just = [f"{tb['table']}.{col} references another table by convention but has no FK constraint, so no index was generated"]
                just += _usage_for(usage, col, tb["table"])[:3]
                recs.append({"table": tb["table"], "columns": cols, "type": "non-clustered", "reason": "FK-like column without FK or index", "justifying_queries": just})
                in_any_index.add(col.lower())
        for c in tb["columns"]:
            cl = c["name"].lower()
            if cl in in_any_index or cl in {fk["column"].lower() for fk in tb["fks"]}:
                continue
            hits = _usage_for(usage, c["name"], tb["table"])
            if hits and not TENANT_RE.match(c["name"]) and not SOFT_DELETE_RE.match(c["name"]):
                cols = tenant + [c["name"]] if tenant else [c["name"]]
                recs.append({"table": tb["table"], "columns": cols, "type": "non-clustered", "reason": "filtered/sorted in code, no index found", "justifying_queries": hits[:3]})
    return recs


# ----------------------------------------------------------------------------- driver
def build(root, stack, code_scan=True):
    schema = Schema()
    sql_files = list(iter_files(root, {".sql"}))
    for p in sql_files:
        parse_sql(schema, root, p, _read(p))
        schema.sources.append(rel(root, p))
    stacks = {stack} if stack != "auto" else {"dotnet", "java-spring", "node-express", "python-django"}
    if "dotnet" in stacks:
        cs = list(iter_files(root, {".cs"}))
        snaps = [p for p in cs if p.endswith(("ModelSnapshot.cs", ".Designer.cs"))]
        # prefer the snapshot (complete); designer files repeat it per migration, so take snapshots first
        snaps = [p for p in snaps if p.endswith("ModelSnapshot.cs")] or snaps[-1:]
        for p in snaps:
            parse_ef_snapshot(schema, root, p, _read(p))
            schema.sources.append(rel(root, p))
        if not snaps:
            parse_ef_entities(schema, root, [p for p in cs if "Migrations" not in p.replace("\\", "/").split("/")])
            schema.sources.append("entity classes reachable from DbSet<T> (no ModelSnapshot found)")
    if "java-spring" in stacks:
        for p in iter_files(root, {".java", ".kt"}):
            parse_jpa(schema, root, p, _read(p))
    if "node-express" in stacks:
        for p in iter_files(root, {".prisma"}):
            parse_prisma(schema, root, p, _read(p)); schema.sources.append(rel(root, p))
        for p in iter_files(root, {".ts", ".js"}):
            txt = _read(p)
            if "@Entity" in txt:
                parse_typeorm(schema, root, p, txt)
            if "createTable" in txt or "alterTable" in txt:
                parse_knex(schema, root, p, txt)
    if "python-django" in stacks:
        for p in iter_files(root, {".py"}):
            txt = _read(p)
            if "migrations" in p.replace("\\", "/").split("/"):
                continue
            parse_django(schema, root, p, txt)
            parse_sqlalchemy(schema, root, p, txt)
    all_names = set(schema.tables.keys())
    tables = [analyse(t, all_names) for t in schema.tables.values()]
    # schema-wide naming consistency
    styles = set()
    for tb in tables:
        for c in tb["columns"]:
            if "_" in c["name"]:
                styles.add("snake_case")
            elif c["name"][:1].isupper():
                styles.add("PascalCase")
            elif c["name"][:1].islower():
                styles.add("camelCase")
    schema_issues = []
    if len(styles) > 1:
        schema_issues.append({"code": "NAMING_INCONSISTENT", "detail": f"column naming mixes {', '.join(sorted(styles))}"})
    usage = scan_code_usage(root, tables) if code_scan else {}
    recs = recommend_indexes(tables, usage)
    by_code = {}
    for tb in tables:
        for i in tb["issues"]:
            by_code[i["code"]] = by_code.get(i["code"], 0) + 1
    return {"root": os.path.abspath(root), "stack": stack, "sources": schema.sources, "tables": tables,
            "schema_issues": schema_issues, "recommended_indexes": recs,
            "summary": {"tables": len(tables), "issues_by_code": by_code, "recommended_indexes": len(recs)}}


def to_md(doc):
    out = ["# Schema checklist", "", f"Tables: {doc['summary']['tables']}  Issues: {json.dumps(doc['summary']['issues_by_code'])}", "",
           "| Table | PK | FKs (indexed/total) | Money | Timestamps | Unbounded strings | Audit | Soft delete | Concurrency | Issues |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for tb in doc["tables"]:
        money = ", ".join(f"{m['name']}:{m['type'] or '?'}" for m in tb["money_columns"]) or "-"
        ts = ", ".join(f"{t['name']}:{'tz' if t['tz_aware'] else 'naive'}" for t in tb["timestamp_columns"]) or "-"
        au = "".join("y" if tb["audit_columns"][k] else "n" for k in ("created_at", "updated_at", "created_by", "updated_by"))
        codes = ", ".join(sorted({i["code"] for i in tb["issues"]})) or "-"
        out.append(f"| {tb['table']} | {'yes' if tb['pk'] else 'NO'} | {sum(1 for f in tb['fks'] if f['indexed'])}/{len(tb['fks'])} | {money} | {ts} | {', '.join(tb['unbounded_strings']) or '-'} | {au} | {tb['soft_delete'] or '-'} | {tb['concurrency_token'] or '-'} | {codes} |")
    out += ["", "## Recommended indexes", "", "| Table | Columns | Reason | Justifying query / code path |", "|---|---|---|---|"]
    for r in doc["recommended_indexes"]:
        out.append(f"| {r['table']} | ({', '.join(r['columns'])}) | {r['reason']} | {'<br>'.join(q.replace('|', '\\|') for q in r['justifying_queries'])} |")
    if doc["schema_issues"]:
        out += ["", "## Schema-wide", ""] + [f"- {i['code']}: {i['detail']}" for i in doc["schema_issues"]]
    out += ["", "Every row is a candidate; confirm in the source before writing a finding."]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--stack", default="auto")
    ap.add_argument("--out")
    ap.add_argument("--md")
    ap.add_argument("--no-code-scan", action="store_true")
    a = ap.parse_args()
    doc = build(a.root, a.stack, code_scan=not a.no_code_scan)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(to_md(doc))
    if not a.out and not a.md:
        print(to_md(doc))
    else:
        print(json.dumps(doc["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
