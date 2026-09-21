#!/usr/bin/env python3
"""Shared helpers for inventory_endpoints.py: text slicing, parameter and
identifier classification, the repo-wide type index, and per-record facts
(auth evidence, ownership evidence, pagination, validation, outbound calls).

Not a CLI of its own; import it through inventory_endpoints.py.

Usage (module):
    import ep_common as c
    c.new_record(kind="http", stack="dotnet", framework="aspnet-controller", ...)

Everything here records facts found in source text. Nothing decides whether a
fact is a finding. Read-only: the audited repository is never modified.
"""
import hashlib
import os
import sys
import re

# --------------------------------------------------------------------------------------------
# Sensitive field names come from audit-sensitive-data-catalog (the single source of truth).
# Only credential and secret categories count as "sensitive fields" on a response type, the same
# filter audit-api-contract applied: PasswordHash, Salt and SecurityStamp in a response are
# over-exposure, while personal-data fields such as Email are recorded by the privacy skills.
import importlib.util as _ilu

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
_CATALOG_PATH = os.path.join(_SKILLS, "audit-sensitive-data-catalog", "scripts", "catalog.py")
try:
    _spec = _ilu.spec_from_file_location("sensitive_data_catalog", _CATALOG_PATH)
    sdc = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(sdc)
except (FileNotFoundError, AttributeError, ImportError) as _exc:  # pragma: no cover
    raise SystemExit("audit-sensitive-data-catalog must be installed next to audit-endpoint-inventory "
                     "(expected " + _CATALOG_PATH + "): " + str(_exc))

SECRETISH = frozenset(("credential", "secret"))
SENSITIVE_FIELDS_SOURCE = "audit-sensitive-data-catalog (categories: " + ", ".join(sorted(SECRETISH)) + ")"
_MEMBER_NAME = re.compile(r"\b([A-Za-z_]\w*)\b\s*(?:\{|:|=|;|\?)")


def is_sensitive_field(name):
    """True when the catalog classifies a member name as a credential or secret."""
    r = sdc.classify_name(name)
    return bool(r["sensitive"]) and r["category"] in SECRETISH
# --------------------------------------------------------------------------------------------

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
BODY_METHODS = {"POST", "PUT", "PATCH"}

CALLER_IDENTITY = re.compile(
    r"\bUser\s*\.|\bClaims?\b|ClaimTypes|GetClaim\w*|FindFirst(?:Value)?\b|\bIdentity\b|CurrentUser|\bCaller\w*|"
    r"AuthorizeAsync|IAuthorizationService|@AuthenticationPrincipal|SecurityContextHolder|\bPrincipal\b|"
    r"userDetails|getCurrentUser|req\.user\b|request\.user\b|ctx\.state\.user|@Req\(|@User\(|@CurrentUser|"
    r"current_user|get_current_user|request\.auth\b|_identityService|IIdentityService|GetClaimDetail|"
    r"_tenant\w*\.|TenantContext|CurrentTenant|ITenantProvider|tenantProvider|self\.request\.user")
OWNER_KEY = re.compile(
    r"\b\w*(?:UserId|OwnerId|CustomerId|CreatedBy|TenantId|CompanyId|BranchId|OrgId|OrganizationId|AccountId)\b|"
    r"\b(?:owner_id|user_id|tenant_id|company_id|customer_id|branch_id|org_id)\b", re.I)

TENANT_ID_NAME = re.compile(r"(tenant|company|org|organization|organisation|account|branch|workspace)_?(id|key|code)?$", re.I)
USER_ID_NAME = re.compile(r"(user|owner|customer|member|employee|created_?by|author|profile)_?(id|key)?$", re.I)
ID_LIKE_NAME = re.compile(r"(^|_)(id|pk|uuid|guid|slug)$|[a-z0-9](Id|ID|Uuid|Guid)$|^(id|pk)$", re.I)

PAGINATION = {
    "dotnet": re.compile(r"\.(?:Skip|Take)\s*\(|PaginationAssign|PagedList|PagedResult|PaginationModel|DataTableAjaxPostModel|"
                         r"PageSize|PageNumber|PageRequest|\.Paginate\(|Pagination|TOP\s*\(?\d|FETCH\s+NEXT", re.I),
    "java-spring": re.compile(r"Pageable|PageRequest|setMaxResults|\.limit\s*\(|Slice<|Page<|LIMIT\s+\d|pageSize|Pagination", re.I),
    "node-express": re.compile(r"\btake\b|\bskip\b|\blimit\b|\boffset\b|\bcursor\b|paginate|\bpageSize\b|\bperPage\b|per_page|"
                               r"\.slice\(|Pagination", re.I),
    "python-django": re.compile(r"pagination_class\s*=\s*(?!None)\w|paginate_queryset|Paginator\s*\(|\[\s*\w*\s*:\s*\w+\s*\]|"
                                r"\.paginate\(|page_size|PAGE_SIZE|LimitOffset|PageNumberPagination|CursorPagination|"
                                r"\.iterator\(|\blimit\b|\boffset\b", re.I),
}
MATERIALIZING = {
    "dotnet": re.compile(r"\.(ToList|ToListAsync|ToArray|ToArrayAsync|AsEnumerable|GetAll|GetAllAsync|FindAll|FindByCondition|"
                         r"FindByConditionAsync|GetList)\s*\("),
    "java-spring": re.compile(r"\.(findAll|getResultList|findBy(?!Id(?:And\w+)?\s*\()\w+|fetch|list|getAll\w*)\s*\("),
    "node-express": re.compile(r"\.(findMany|find|findAll|findAndCountAll|select|getMany|getRawMany|exec|aggregate)\s*\("),
    "python-django": re.compile(r"\.objects\.(all|filter|exclude|order_by|values|values_list)\s*\(|many\s*=\s*True"),
}
SINGLE_FETCH = re.compile(r"\.(Find|FindAsync|FirstOrDefault\w*|SingleOrDefault\w*|First\w*|Single\w*|findOne|findUnique|findFirst|"
                          r"findById|findByPk|getById|get_object_or_404|objects\.get)\s*\(")
COLLECTION_TYPE = re.compile(r"IEnumerable<|List<|IList<|ICollection<|IQueryable<|IReadOnlyList<|\[\]|Collection<|Set<|Iterable<|"
                             r"Array<|Page<|Paged|QuerySet|list\[|List\[", re.I)
VALIDATION = re.compile(
    r"\[(Required|Range|StringLength|MaxLength|MinLength|EmailAddress|RegularExpression)\b|AbstractValidator<|@Valid\b|"
    r"@Validated\b|@NotNull|@NotBlank|@Size\(|\.parse\(|safeParse\(|celebrate\(|Joi\.|ValidationPipe|@Is[A-Z]\w*\(|"
    r"is_valid\(|Field\(|serializer_class|z\.object\(")
ERROR_SHAPES = [
    ("{error}", re.compile(r"new\s*\{\s*error\b|\{\s*['\"]?error['\"]?\s*[:=]|Map\.of\(\s*\"error\"", re.I)),
    ("{message}", re.compile(r"new\s*\{\s*message\b|\{\s*['\"]?message['\"]?\s*[:=]|Map\.of\(\s*\"message\"", re.I)),
    ("{msg}", re.compile(r"\{\s*['\"]?msg['\"]?\s*[:=]", re.I)),
    ("{success:false}", re.compile(r"success\s*[:=]\s*false", re.I)),
    ("ProblemDetails/RFC9457", re.compile(r"ProblemDetails|ValidationProblem\(|\bProblem\(|ProblemDetail\b|problem\+json|createError\(")),
    ("{detail}", re.compile(r"\{\s*['\"]detail['\"]\s*:|HTTPException\(", re.I)),
    ("exception message/stack", re.compile(r"(StatusCode|BadRequest|Ok|Problem|json|send|Response|status)\s*\([^\n]*\b\w+\.(Message|StackTrace|getMessage\(\)|stack)\b")),
]
OUTBOUND = re.compile(
    r"(await\s+)?(this\.)?_?\w*(client|Client|http|Http|axios|fetch|api|Api|gateway|Gateway|restTemplate|RestTemplate|webClient|"
    r"WebClient|requests|session|httpx|feign|sms|Sms|mail|Mail|queue|Queue|bus|Bus|publisher|Publisher|producer|Producer)\w*"
    r"\.(get|post|put|patch|delete|send|request|exchange|retrieve|call|quote|rate|lookup|fetch|publish|enqueue|getFor\w+|"
    r"postFor\w+|GetAsync|PostAsync|SendAsync|PutAsync|DeleteAsync|PatchAsync|GetStringAsync|GetFromJsonAsync|"
    r"PostAsJsonAsync|PutAsJsonAsync|PublishAsync)\w*\s*\(|\bfetch\s*\(\s*[`'\"]|\baxios\s*\(")
DB_CALL = re.compile(
    r"(_db|_context|_manager|_repo|repository|Repository|prisma|repo|knex|sequelize|Model|\.objects|entityManager|jdbcTemplate|"
    r"dataSource)\w*(\.\w+)*\.(ToList|ToListAsync|First\w*|Single\w*|Find\w*|Where|Any\w*|Count\w*|Include|SaveChanges\w*|Add\w*|"
    r"Update\w*|Remove\w*|findMany|findUnique|findFirst|find|findOne|findAll|findById|findByPk|create|createMany|update|"
    r"updateMany|delete|deleteMany|save|saveAll|upsert|query|select|insert|all|filter|get|exists|count|bulk_create|values|"
    r"getResultList)\s*\(", re.I)
PROJECTION = re.compile(r"\.Select\s*\(|ProjectTo|select\s*:\s*\{|attributes\s*:|\.values\s*\(|\.values_list\s*\(|\.only\s*\(|"
                        r"Dto\b|Projection|\.map\s*\(\s*\w+\s*=>\s*\(\s*\{|serializer_class|MapTo|Mapper\.Map", re.I)
INLINE_BG = re.compile(r"sendMail|SendEmail|SendMail|send_mail|SendSms|nodemailer|puppeteer|PdfDocument|PDFDocument|write_pdf|"
                       r"ExcelPackage|Workbook\b|XSSFWorkbook|Image\.(Load|open)|sharp\s*\(|ImageIO|SubmitToFbr|PostInvoice", re.I)
CONCURRENT_BLOCK = re.compile(r"Promise\.(all|allSettled|race|any)\s*\(|Task\.WhenAll\s*\(|asyncio\.gather\s*\(|"
                              r"CompletableFuture\.allOf\s*\(|Mono\.zip\s*\(|Flux\.merge\s*\(")
ENTITY_RETURN = re.compile(r"return\s+Ok\(\s*(await\s+)?_?\w*(db|context)\w*\.", re.I)
VERSION_PLACEHOLDER = re.compile(r"\{(version|api-version|apiVersion)(:[^}]*)?\}", re.I)

SIMPLE_TYPES = {"int", "long", "short", "byte", "string", "bool", "boolean", "guid", "decimal", "double", "float", "datetime",
                "datetimeoffset", "dateonly", "timeonly", "char", "integer", "uuid", "str", "number", "date", "object"}
SERVICE_TYPE = re.compile(r"(DbContext|Service|Manager|Repository|Repo|Factory|Logger|ILogger\w*|HttpContext|ClaimsPrincipal|"
                          r"CancellationToken|IConfiguration|IMapper|IMediator|HttpRequest|HttpResponse|IOptions\w*|Client)\b")
WRAPPER_TYPES = {"Task", "ValueTask", "ActionResult", "IActionResult", "IResult", "Results", "Ok", "Promise", "Observable",
                 "ResponseEntity", "Mono", "Flux", "Optional", "List", "IEnumerable", "IList", "ICollection", "IQueryable",
                 "IReadOnlyList", "Page", "Set", "Collection", "Iterable", "Array", "Response", "JsonResult", "HttpResponse"}


# ---------------------------------------------------------------------------- record skeleton
def new_record(**kw):
    """Return a record with every contract key present, updated with kw."""
    rec = {
        "id": None, "kind": "http", "stack": None, "framework": None, "method": None, "path": None, "path_raw": None,
        "file": None, "line": None, "handler_line": None, "route_location": None, "symbol": None, "class": None, "handler": None,
        "auth": {"required": "unknown", "source": "none", "anonymous_marker": None, "roles": [], "policies": [],
                 "evidence": [], "client_guards": []},
        "ownership": {"check": "n/a", "evidence": [], "identity_refs": [], "owner_key_refs": []},
        "params": [], "id_params": {},
        "request": {"types": [], "has_body": False, "body_type": None, "body_type_named_as_dto": None},
        "validation": {"status": "n/a", "evidence": []},
        "response": {"type": None, "returns_collection": "unknown", "collection_evidence": [],
                     "pagination": {"status": "n/a", "evidence": []}, "sensitive_fields": [],
                     "returns_entity_like": False, "projection": False},
        "errors": {"shapes_in_file": [], "consistent_with_majority": "unknown"},
        "versioned": {"status": "no", "evidence": None},
        "outbound": {"calls": [], "sequential": False, "sequential_evidence": []},
        "data_access": {"db_call_count": 0, "materializing_calls": [], "paging_seen": False, "inline_background_work": False},
        "operation": None, "job": None, "notes": [],
    }
    for k, v in kw.items():
        if isinstance(v, dict) and isinstance(rec.get(k), dict):
            rec[k].update(v)
        else:
            rec[k] = v
    return rec


def assign_ids(records):
    """Stable id: kind|method|path|file|symbol hashed; line moves do not change it."""
    seen = {}
    for r in records:
        key = "|".join(str(r.get(k) or "") for k in ("kind", "method", "path", "file", "symbol"))
        base = "ep-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        n = seen.get(base, 0) + 1
        seen[base] = n
        r["id"] = base if n == 1 else f"{base}-{n}"


# ---------------------------------------------------------------------------- text helpers
_STR = re.compile(r'@?\$?"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`')


def strip_strings(s):
    return _STR.sub('""', s)


def strip_comment(line, lang):
    s = line
    if lang == "python":
        return re.sub(r"(^|\s)#.*$", "", s)
    s = re.sub(r"(^|[^:])//.*$", r"\1", s)
    return s


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def brace_body_end(lines, start, cap=400):
    """Index of the last line of a brace-delimited member starting at `start`
    (expression-bodied members end at the first top-level ';')."""
    depth, seen_open = 0, False
    for i in range(start, min(len(lines), start + cap)):
        s = strip_strings(lines[i])
        depth += s.count("{") - s.count("}")
        if "{" in s:
            seen_open = True
        if not seen_open and s.rstrip().endswith(";"):
            return i
        if seen_open and depth <= 0:
            return i
    return min(len(lines), start + cap) - 1


def indent_body_end(lines, start, cap=400):
    """Index of the last line of a Python def/class starting at `start`."""
    base = len(lines[start]) - len(lines[start].lstrip())
    last = start
    for i in range(start + 1, min(len(lines), start + cap)):
        ln = lines[i]
        if not ln.strip():
            continue
        ind = len(ln) - len(ln.lstrip())
        if ind <= base and not ln.lstrip().startswith((")", "]")):
            break
        last = i
    return last


def balanced_span(text, open_pos):
    """Given text[open_pos] in '([{', return index just past its matching close (strings skipped)."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = []
    i, n = open_pos, len(text)
    while i < n:
        ch = text[i]
        if ch in "\"'`":
            q = ch
            i += 1
            while i < n and text[i] != q:
                i += 2 if text[i] == "\\" else 1
        elif ch in pairs:
            stack.append(pairs[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
            if not stack:
                return i + 1
        i += 1
    return n


def statement_end(text, pos):
    """End offset of the statement starting at pos: first ';' at bracket depth 0, or end of a call chain."""
    i, n, depth = pos, len(text), 0
    while i < n:
        ch = text[i]
        if ch in "\"'`":
            q = ch
            i += 1
            while i < n and text[i] != q:
                i += 2 if text[i] == "\\" else 1
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth < 0:
                return i
        elif ch == ";" and depth == 0:
            return i + 1
        elif ch == "\n" and depth == 0:
            rest = text[i + 1:i + 200].lstrip()
            if not rest.startswith((".", "?.", ")", "&&", "||", "+")):
                return i
        i += 1
    return n


def split_args(s):
    """Split a comma-separated argument list at bracket depth 0."""
    out, depth, cur, i = [], 0, [], 0
    while i < len(s):
        ch = s[i]
        if ch in "\"'`":
            q = ch
            j = i + 1
            while j < len(s) and s[j] != q:
                j += 2 if s[j] == "\\" else 1
            cur.append(s[i:j + 1])
            i = j + 1
            continue
        prev = s[i - 1] if i else ""
        nxt = s[i + 1] if i + 1 < len(s) else ""
        if ch in "([{" or (ch == "<" and prev.isalnum() and nxt not in "= "):
            depth += 1
        elif ch in ")]}" or (ch == ">" and prev not in "=-" and depth > 0):
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


def join_path(*parts):
    segs = []
    for p in parts:
        if not p:
            continue
        p = p.strip()
        if p.startswith("~/"):
            segs = []
            p = p[1:]
        segs.append(p.strip("/"))
    path = "/" + "/".join(s for s in segs if s)
    return re.sub(r"/{2,}", "/", path)


def norm_path(p):
    p = p or "/"
    p = re.sub(r"\{(\*?\w+)(?::[^}]*)?\??\}", lambda m: "{" + m.group(1).lstrip("*") + "}", p)   # {id:int} -> {id}
    p = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", p)                                                  # <int:pk> -> {pk}
    p = re.sub(r"\(\?P<(\w+)>[^)]*\)", r"{\1}", p)                                               # (?P<pk>\d+) -> {pk}
    p = re.sub(r"(?<=/):(\w+)\??", r"{\1}", p)                                                   # /:id -> /{id}
    p = re.sub(r"\[(?:\.\.\.)?(\w+)\]", r"{\1}", p)                                              # next.js [id]
    p = p.replace("^", "").replace("$", "")
    p = re.sub(r"/{2,}", "/", "/" + p.strip("/"))
    return p if p != "" else "/"


def route_placeholders(path):
    return re.findall(r"\{(\w+)\}", norm_path(path))


# ---------------------------------------------------------------------------- params
def identifier_class(name):
    n = re.sub(r"[^A-Za-z0-9_]", "", name or "")
    core = re.sub(r"(_?(id|Id|ID|key|Key|code|Code))$", "", n)
    if not ID_LIKE_NAME.search(n) and not re.search(r"(Key|_key|Code|_code)$", n):
        return None
    if TENANT_ID_NAME.search(core + "id") or TENANT_ID_NAME.fullmatch(core or ""):
        return "tenant"
    if USER_ID_NAME.search(core + "id") or USER_ID_NAME.fullmatch(core or ""):
        return "user"
    return "resource" if ID_LIKE_NAME.search(n) else None


def make_param(name, where, typ=None, source_type=None):
    name = (name or "").strip()
    ident = identifier_class(name)
    return {"name": name, "in": where, "type": (typ or None), "id_like": bool(ID_LIKE_NAME.search(name)) or ident is not None,
            "identifier": ident, "source_type": source_type}


def dedupe_params(params):
    seen, out = set(), []
    for p in params:
        k = (p["name"].lower(), p["in"])
        if p["name"] and k not in seen:
            seen.add(k)
            out.append(p)
    return out


def singular(word):
    w = (word or "").lower()
    if w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith(("ses", "xes")):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def id_params_for(path):
    """{placeholder: ids-file key} for every non-version placeholder in a normalized path."""
    out = {}
    segs = norm_path(path).strip("/").split("/")
    for i, seg in enumerate(segs):
        m = re.fullmatch(r"\{(\w+)\}", seg)
        if not m:
            continue
        name = m.group(1)
        if VERSION_PLACEHOLDER.fullmatch("{" + name + "}"):
            continue
        low = name.lower()
        if "user" in low:
            key = "user"
        elif low in ("id", "pk", "key", "uuid", "guid", "slug"):
            prev = next((s for s in reversed(segs[:i]) if not s.startswith("{")), "")
            key = singular(re.sub(r"[^A-Za-z0-9]", "", prev)) or "id"
        else:
            key = re.sub(r"_?(id|pk|uuid|guid)$", "", low) or low
        out[name] = key
    return out


# ---------------------------------------------------------------------------- type index
CLASS_DECL = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:(?:public|internal|private|protected|sealed|abstract|partial|static|"
                        r"data|open|final)\s+)*(?:class|record|interface)\s+([A-Z]\w*)")
PY_CLASS = re.compile(r"^class\s+([A-Z]\w*)\s*(?:\(([^)]*)\))?\s*:")


def index_types(files_text):
    """{TypeName: {file, line, properties[{name,type}], validation[], sensitive_fields[], bases}} across the repo."""
    idx = {}
    for rel, text in files_text.items():
        ext = os.path.splitext(rel)[1].lower()
        lines = text.splitlines()
        rx = PY_CLASS if ext == ".py" else CLASS_DECL
        starts = [(i, m) for i, l in enumerate(lines) for m in [rx.match(l)] if m]
        for k, (i, m) in enumerate(starts):
            name = m.group(1)
            end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
            block = "\n".join(lines[i:end])
            props = _properties(block, ext)
            e = idx.setdefault(name, {"file": rel, "line": i + 1, "properties": [], "validation": [],
                                      "sensitive_fields": [], "bases": ""})
            have = {p["name"] for p in e["properties"]}
            e["properties"] += [p for p in props if p["name"] not in have]
            e["validation"] = sorted(set(e["validation"]) | {x.group(0) for x in VALIDATION.finditer(block)})[:6]
            sens = {p["name"] for p in props if is_sensitive_field(p["name"])}
            sens |= {n for n in (x.group(1) for x in _MEMBER_NAME.finditer(block)) if is_sensitive_field(n)}
            e["sensitive_fields"] = sorted(set(e["sensitive_fields"]) | sens)
            bm = re.search(r"(?:class|record|interface)\s+\w+[^:{(\n]*(?:\([^)]*\))?\s*(?::|extends|implements)\s*([^{\n]+)", lines[i])
            if ext == ".py" and m.group(2):
                e["bases"] = m.group(2)
            elif bm:
                e["bases"] = bm.group(1).strip()
    return idx


def _properties(block, ext):
    props = []
    if ext == ".cs":
        for m in re.finditer(r"public\s+(?:required\s+|virtual\s+|override\s+|new\s+)*([\w<>\[\],.?]+)\s+(\w+)\s*\{\s*(?:get|init|set)", block):
            props.append({"name": m.group(2), "type": m.group(1)})
        rm = re.search(r"record\s+(?:class\s+|struct\s+)?\w+(?:<[^>]*>)?\s*\(([^)]*)\)", block)
        if rm:
            for a in split_args(rm.group(1)):
                pm = re.match(r"(?:\[[^\]]*\]\s*)*([\w<>\[\],.?]+)\s+(\w+)", a)
                if pm:
                    props.append({"name": pm.group(2), "type": pm.group(1)})
    elif ext in (".java", ".kt"):
        for m in re.finditer(r"(?:private|protected|public)\s+(?:final\s+)?([\w<>\[\],.?]+)\s+(\w+)\s*(?:=[^;]*)?;", block):
            props.append({"name": m.group(2), "type": m.group(1)})
        for m in re.finditer(r"\b(?:val|var)\s+(\w+)\s*:\s*([\w<>?,. ]+)", block):
            props.append({"name": m.group(1), "type": m.group(2).strip()})
        rm = re.search(r"record\s+\w+\s*\(([^)]*)\)", block)
        if rm:
            for a in split_args(rm.group(1)):
                pm = re.match(r"(?:@\w+(?:\([^)]*\))?\s*)*([\w<>\[\],.?]+)\s+(\w+)", a)
                if pm:
                    props.append({"name": pm.group(2), "type": pm.group(1)})
    elif ext in (".ts", ".tsx", ".js", ".mjs", ".cjs"):
        for m in re.finditer(r"^\s*(?:@\w+\([^)]*\)\s*)*(?:public\s+|private\s+|protected\s+|readonly\s+)*(\w+)[?!]?\s*:\s*([^;=\n]+)",
                             block, re.M):
            if m.group(1) not in ("constructor", "return"):
                props.append({"name": m.group(1), "type": m.group(2).strip().rstrip(",")})
    elif ext == ".py":
        for m in re.finditer(r"^\s{4}(\w+)\s*:\s*([\w\[\], .|]+?)\s*(?:=|$)", block, re.M):
            props.append({"name": m.group(1), "type": m.group(2).strip()})
        for m in re.finditer(r"^\s{4}(\w+)\s*=\s*(?:models|serializers|fields)\.(\w+)", block, re.M):
            props.append({"name": m.group(1), "type": m.group(2)})
    return props


def type_names(s):
    return [t for t in dict.fromkeys(re.findall(r"\b([A-Z]\w+)\b", s or ""))]


# ---------------------------------------------------------------------------- facts from a handler body
def evidence(lines_with_no, rx, limit=3):
    out = []
    for no, text in lines_with_no:
        if rx.search(text):
            out.append({"line": no, "text": text.strip()[:160]})
            if len(out) >= limit:
                break
    return out


def numbered(lines, start_index):
    return [(start_index + i + 1, ln) for i, ln in enumerate(lines)]


def fill_body_facts(rec, body_lines, lang_stack, types, extra_sources=(), identity_rx=None, validation_rx=None,
                    selector_in=("route", "query")):
    """Populate ownership, pagination, collection, outbound, data_access, validation and response facts.

    body_lines     list of (line_no, text) for the handler (and route declaration)
    extra_sources  list of (file, via_symbol, [(line_no, text)]) one-hop callee bodies
    identity_rx    caller-identity regex (default CALLER_IDENTITY); meta-framework handlers pass a superset
    validation_rx  validation-marker regex (default VALIDATION)
    selector_in    parameter locations whose id-like names count as resource selectors for ownership
    """
    identity_rx = identity_rx or CALLER_IDENTITY
    validation_rx = validation_rx or VALIDATION
    lang = "python" if lang_stack == "python-django" else "c"
    code = [(no, strip_comment(t, lang)) for no, t in body_lines]
    text = "\n".join(t for _, t in code)
    all_code = list(code)
    for _, _, extra in extra_sources:
        all_code += [(no, strip_comment(t, lang)) for no, t in extra]

    # ownership
    rec["ownership"]["identity_refs"] = evidence(code, identity_rx, 5)
    rec["ownership"]["owner_key_refs"] = evidence(code, OWNER_KEY, 5)
    selectors = [p for p in rec["params"] if p["in"] in selector_in and p["id_like"]
                 and not VERSION_PLACEHOLDER.fullmatch("{" + p["name"] + "}")]
    if selectors:
        if rec["ownership"]["identity_refs"]:
            rec["ownership"]["check"] = "yes"
            rec["ownership"]["evidence"] = rec["ownership"]["identity_refs"][:3]
        elif rec["ownership"]["owner_key_refs"]:
            rec["ownership"]["check"] = "unknown"
            rec["ownership"]["evidence"] = rec["ownership"]["owner_key_refs"][:3]
        else:
            rec["ownership"]["check"] = "no"
            rec["ownership"]["evidence"] = []
    else:
        rec["ownership"]["check"] = "n/a"

    # data access and pagination
    stack_key = lang_stack if lang_stack in PAGINATION else "node-express"
    pag_rx, mat_rx = PAGINATION[stack_key], MATERIALIZING[stack_key]
    pag_ev = sorted({m.group(0).strip() for _, t in code for m in pag_rx.finditer(t)})[:6]
    mats = evidence(code, mat_rx, 5)
    rec["data_access"]["materializing_calls"] = mats
    rec["data_access"]["paging_seen"] = bool(pag_ev)
    rec["data_access"]["db_call_count"] = sum(1 for _, t in code if DB_CALL.search(t))
    rec["data_access"]["inline_background_work"] = bool(INLINE_BG.search(text))
    rec["response"]["projection"] = bool(PROJECTION.search(text))
    rec["response"]["returns_entity_like"] = bool(ENTITY_RETURN.search(text))

    rtype = rec["response"]["type"] or ""
    coll_ev = []
    if COLLECTION_TYPE.search(rtype):
        coll_ev.append({"line": rec["handler_line"] or rec["line"], "text": "declared type " + rtype})
    coll_ev += mats[:2]
    coll_ev += evidence(code, re.compile(r"\.(ToList|ToArray|findMany|findAll)\w*\(|\.objects\.all\(\)|\.find\(\s*\)"), 2)
    uniq = []
    for e in coll_ev:
        if e not in uniq:
            uniq.append(e)
    rec["response"]["collection_evidence"] = uniq[:3]
    declared_single = bool(rtype) and not COLLECTION_TYPE.search(rtype) and \
        bool([t for t in type_names(rtype) if t not in WRAPPER_TYPES and t not in ("IActionResult", "ActionResult")])
    if uniq:
        rec["response"]["returns_collection"] = "yes"
    elif declared_single or SINGLE_FETCH.search(text):
        rec["response"]["returns_collection"] = "no"
    else:
        rec["response"]["returns_collection"] = "unknown"

    method = rec["method"] or ""
    last = norm_path(rec["path"] or "/").rstrip("/").split("/")[-1]
    single_resource = bool(re.fullmatch(r"\{\w+\*?\}", last))   # {slug*} is a meta-framework catch-all
    if rec["kind"] == "http" and method in ("GET", "ANY") and (rec["response"]["returns_collection"] == "yes" or not single_resource):
        rec["response"]["pagination"] = {"status": "yes" if pag_ev else "no", "evidence": pag_ev}
    else:
        rec["response"]["pagination"] = {"status": "n/a", "evidence": pag_ev}

    # outbound calls (handler plus one-hop callees)
    calls = []
    sources = [(rec["file"], None, code)] + [(f, via, [(no, strip_comment(t, lang)) for no, t in ex]) for f, via, ex in extra_sources]
    for f, via, src in sources:
        src_text = "\n".join(t for _, t in src)
        conc_ranges = []
        for m in CONCURRENT_BLOCK.finditer(src_text):
            open_pos = src_text.find("(", m.start())
            end = balanced_span(src_text, open_pos)
            conc_ranges.append((line_of(src_text, m.start()), line_of(src_text, end)))
        base_no = src[0][0] if src else 0
        for k, (no, t) in enumerate(src):
            m = OUTBOUND.search(t)
            if not m:
                continue
            rel_no = k + 1
            concurrent = any(a <= rel_no <= b for a, b in conc_ranges)
            vm = re.search(r"(?:const|let|var|final|val|auto)?\s*(\w+)\s*=\s*(?:await\s+)?", t)
            var = vm.group(1) if vm and vm.group(1) not in ("await", "return") and vm.start(1) < m.start() else None
            calls.append({"file": f, "line": no, "kind": _outbound_kind(m.group(0)), "text": t.strip()[:160],
                          "awaited": bool(re.search(r"\bawait\b|\.(get|join|block)\(\)|\.Result\b|GetAwaiter", t))
                          or lang_stack in ("java-spring",) or (lang_stack == "python-django" and "async" not in t),
                          "concurrent_group": concurrent, "via": via, "_var": var,
                          "_args": t[m.end():], "_src": id(src), "_idx": k})
        _ = base_no
    seq_ev = []
    by_src = {}
    for c in calls:
        by_src.setdefault(c["_src"], []).append(c)
    for group in by_src.values():
        chain = [c for c in group if c["awaited"] and not c["concurrent_group"]]
        for j in range(1, len(chain)):
            prev_vars = [c["_var"] for c in chain[:j] if c["_var"]]
            independent = not any(re.search(r"\b" + re.escape(v) + r"\b", chain[j]["_args"]) for v in prev_vars)
            if independent and 0 < chain[j]["_idx"] - chain[j - 1]["_idx"] <= 6:
                for c in (chain[j - 1], chain[j]):
                    if c["line"] not in [e["line"] for e in seq_ev]:
                        seq_ev.append({"file": c["file"], "line": c["line"]})
    for c in calls:
        for k in ("_var", "_args", "_src", "_idx"):
            c.pop(k, None)
    rec["outbound"] = {"calls": calls, "sequential": bool(seq_ev), "sequential_evidence": seq_ev}

    # response type sensitive fields
    exposed = []
    for t in type_names(rtype):
        if t in types and types[t]["sensitive_fields"]:
            exposed += [f"{t}.{f}" for f in types[t]["sensitive_fields"]]
    rec["response"]["sensitive_fields"] = exposed
    if exposed:
        rec["response"]["returns_entity_like"] = True

    # validation
    markers = sorted({m.group(0) for _, t in code for m in validation_rx.finditer(t)})
    for t in rec["request"]["types"]:
        if t in types:
            markers += [f"{t}:{v}" for v in types[t]["validation"]]
    markers = sorted(set(markers))[:8]
    rec["validation"] = {"status": ("yes" if markers else "no") if rec["request"]["has_body"] else "n/a", "evidence": markers}


def _outbound_kind(s):
    low = s.lower()
    if "sms" in low:
        return "sms"
    if "mail" in low:
        return "mail"
    if re.search(r"queue|bus|publish|producer|enqueue", low):
        return "queue"
    return "http"


def body_params_from_type(type_name, types):
    t = types.get(type_name)
    if not t:
        return []
    return [make_param(p["name"], "body", p["type"], type_name) for p in t["properties"]]


def auth_ev(no, text):
    return {"line": no, "text": (text or "").strip()[:160]}
