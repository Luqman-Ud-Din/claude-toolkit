#!/usr/bin/env python3
"""Meta-framework server handler extractors for inventory_endpoints.py.

React stack roots (Next.js and Remix report as react):
  - Next.js App Router route handlers: app/**/route.(ts|js) exporting GET, POST, PUT,
    PATCH, DELETE, HEAD or OPTIONS (framework nextjs-route).
  - Next.js Pages Router API routes: pages/api/** default exports, one record per
    req.method branch, else ANY (framework nextjs-pages-api).
  - Next.js server actions: exports of a "use server" module and inline functions
    containing "use server" (kind server-action, framework nextjs-server-action).
  - Next.js middleware.(ts|js) at the project root or src/ (kind middleware).
  - Remix / React Router framework mode: app/routes/** modules exporting loader (GET)
    and action (POST, or one record per request.method branch) (framework remix-route).
Vue stack roots (Nuxt reports as vue):
  - Nuxt server routes: server/api/** and server/routes/** with defineEventHandler or
    eventHandler; the method comes from a .get/.post/... filename suffix, else ANY
    (framework nuxt-server-route).
  - Nuxt server/middleware/** (kind middleware, framework nuxt-server-middleware).

Usage (module):
    import ep_metaframeworks as mf
    mf.scan_metaframeworks(ctx, ["react", "vue"], out)

Records facts only, through the same ep_common helpers as every other extractor.
Files come from ctx.files, which inventory_endpoints.py fills through audit-code-scan's
repo_walk. SvelteKit is not covered. Read-only.
"""
import re

import ep_backends as b
import ep_common as c

JS_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
VERBS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")

# Auth evidence inside a handler body (calls, session reads) and auth-named wrappers around it.
AUTH_CALL = re.compile(
    r"\b(?:unstable_)?getServer(?:Auth)?Session\s*\(|(?<![\w.])auth\s*\(\s*\)|"
    r"(?<![\w.])auth\s*\(\s*(?:async\b|function\b|\([^)]*\)\s*=>|\w+\s*=>)|\bNextAuth\s*\(|"
    r"\bwith(?:Api|Page)?Auth(?:Required)?\s*\(|\bgetSession\s*\(|\bgetToken\s*\(|\b(?:get)?[cC]urrentUser\s*\(|"
    r"\bgetAuth\s*\(|\buseSession\s*\(|\brequire(?:User|Auth|Session|Login)\w*\s*\(|\bgetUserSession\s*\(|"
    r"\bgetUser(?:Id)?\s*\(\s*request\b|\bgetKindeServerSession\s*\(|\bvalidateRequest\s*\(|"
    r"\bauthenticator\.isAuthenticated\s*\(|\bauth\.getUser\s*\(|\bevent\.context\.(?:user|auth|session)\b|"
    r"\bensureAuth\w*\s*\(|\bisAuthenticated\s*\(")
AUTH_WRAPPER = re.compile(r"^(?:auth|with\w*Auth\w*|require\w*Auth\w*|define\w*(?:Auth|Protected)\w*|protect\w*|"
                          r"clerkMiddleware|authMiddleware)$")
ROLE_REF = re.compile(r"\.roles?\s*(?:[!=]==?|\.includes\()\s*['\"`](\w[\w-]*)['\"`]|"
                      r"\b(?:requireRoles?|hasRole|hasAnyRole|checkRole|authorize)\s*\(\s*(?:\w+\s*,\s*)?['\"`](\w[\w-]*)['\"`]")
# Caller identity for the ownership fact: the shared list plus meta-framework session reads.
IDENTITY = re.compile(c.CALLER_IDENTITY.pattern + "|" + AUTH_CALL.pattern +
                      r"|\bsession\??\.user\b|\blocals\.user\b|\btoken\??\.sub\b")
# Validation markers: the shared list plus valibot and framework validated readers.
VALIDATION = re.compile(c.VALIDATION.pattern +
                        r"|\bv\.(?:parse|safeParse|parseAsync|object)\s*\(|(?<![\w.])(?:safeParse|parseAsync|safeParseAsync)\s*\(|"
                        r"\bvalibot\b|readValidatedBody\s*\(|getValidatedQuery\s*\(|getValidatedRouterParams\s*\(|\bzfd\.|"
                        r"parseWithZod\s*\(|parseWithValibot\s*\(")
BODY_READ = re.compile(r"\b(?:request|req)\.(?:json|formData|text|arrayBuffer|blob)\s*\(|\breq\.body\b|"
                       r"\b(?:readBody|readValidatedBody|readFormData|readMultipartFormData|readRawBody)\s*\(")
FORM_READ = re.compile(r"\.formData\s*\(|\breadFormData\s*\(|\breadMultipartFormData\s*\(")
EVENT_HANDLER = re.compile(r"\b(?:define\w*EventHandler|eventHandler)\s*\(")


# ============================================================================ paths
def _stack_rel(ctx, stack, rel):
    """(path below the longest matching stack root, that root prefix)."""
    best = ""
    for rt in ctx.roots.get(stack, ["."]):
        rt = rt.replace("\\", "/").strip("/")
        if rt not in (".", "") and (rel == rt or rel.startswith(rt + "/")) and len(rt) > len(best):
            best = rt
    return (rel[len(best) + 1:] if best else rel), best


def _file_route(segs):
    """File-system segments -> (path, path_raw, catch-all names). [id] -> {id}, [...slug] and [[...slug]] -> {slug*}."""
    parts, catch = [], []
    for s in segs:
        m = re.fullmatch(r"\[\[\.\.\.(\w+)\]\]|\[\.\.\.(\w+)\]", s)
        if m:
            name = m.group(1) or m.group(2)
            parts.append("{" + name + "*}")
            catch.append(name)
        else:
            parts.append(re.sub(r"\[(\w+)\]", r"{\1}", s))
    return c.norm_path("/" + "/".join(p for p in parts if p)), "/" + "/".join(s for s in segs if s), catch


def next_app_route(sub):
    """app/**/route.(ts|js) or src/app/** -> (path, raw, catch) or None. (group) and @slot folders are dropped."""
    segs = sub.split("/")
    if not re.fullmatch(r"route\.(ts|js)", segs[-1]):
        return None
    k = 0 if segs[0] == "app" else (1 if segs[:2] == ["src", "app"] else None)
    if k is None:
        return None
    dirs = segs[k + 1:-1]
    if any(d.startswith("_") for d in dirs):          # private folders are not routable
        return None
    return _file_route([d for d in dirs if not (d.startswith("(") and d.endswith(")")) and not d.startswith("@")])


def next_pages_api(sub):
    """pages/api/** or src/pages/api/** -> (path, raw, catch) or None. index is dropped."""
    segs = sub.split("/")
    k = 0 if segs[:2] == ["pages", "api"] else (1 if segs[:3] == ["src", "pages", "api"] else None)
    if k is None or len(segs) < k + 3 or not re.search(r"\.(tsx?|jsx?)$", segs[-1]) or segs[-1].endswith(".d.ts"):
        return None
    stem = re.sub(r"\.(tsx?|jsx?)$", "", segs[-1])
    return _file_route(segs[k + 1:-1] + ([] if stem == "index" else [stem]))


def nuxt_route(sub):
    """server/{api,routes,middleware}/** (also layers/<x>/server/...) -> (area, (path, raw, catch) or None, method) or None."""
    segs = sub.split("/")
    k = 0 if segs[0] == "server" else (2 if len(segs) > 2 and segs[0] == "layers" and segs[2] == "server" else None)
    if k is None or len(segs) < k + 3 or segs[k + 1] not in ("api", "routes", "middleware"):
        return None
    if not re.search(r"\.(ts|js|mjs|cjs)$", segs[-1]) or segs[-1].endswith(".d.ts"):
        return None
    area = segs[k + 1]
    stem = re.sub(r"\.(ts|js|mjs|cjs)$", "", segs[-1])
    method = "ANY"
    mm = re.search(r"\.(get|post|put|patch|delete|head|options)$", stem, re.I)
    if mm:
        method, stem = mm.group(1).upper(), stem[:mm.start()]
    if area == "middleware":
        return area, None, method
    parts = (["api"] if area == "api" else []) + segs[k + 2:-1] + ([] if stem == "index" else [stem])
    return area, _file_route(parts), method


def _split_flat(name):
    """Split a flat-routes name on dots outside [] escapes; escaped text is kept literally."""
    parts, cur, depth = [], "", 0
    for ch in name:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        elif ch == "." and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def remix_route(ctx, rel, sub):
    """app/routes/** flat-routes file -> (path, raw, catch) or None.

    Dots separate segments, $param -> {param}, a bare $ -> {splat*}, _index and pathless _layout
    segments are dropped, a trailing _ is removed, (optional) parentheses are dropped.
    Folder routes use the folder name for route.* ; other files in such a folder are colocated modules.
    """
    segs = sub.split("/")
    if len(segs) < 3 or segs[:2] != ["app", "routes"] or not re.search(r"\.(tsx?|jsx?|mjs)$", segs[-1]):
        return None
    stem = re.sub(r"\.(tsx?|jsx?|mjs)$", "", segs[-1])
    if re.search(r"\.(server|client)$", stem) or segs[-1].endswith(".d.ts"):
        return None
    dirs = segs[2:-1]
    if dirs and stem == "route":
        names = dirs
    elif dirs:
        folder = rel.rsplit("/", 1)[0]
        if any(re.fullmatch(re.escape(folder) + r"/route\.(tsx?|jsx?|mjs)", r) for r in ctx.text_by_rel):
            return None
        names = dirs + [stem]
    else:
        names = [stem]
    url, raw, catch = [], [], []
    for p in (x for n in names for x in _split_flat(n)):
        if p in ("_index", "index", "") or (p.startswith("_") and len(p) > 1):
            continue
        raw.append(p)
        p = p[:-1] if p.endswith("_") and len(p) > 1 else p
        opt = re.fullmatch(r"\((.+)\)", p)
        p = opt.group(1) if opt else p
        if p == "$":
            url.append("{splat*}")
            catch.append("splat")
        elif p.startswith("$"):
            url.append("{" + p[1:] + "}")
        else:
            url.append(p)
    return c.norm_path("/" + "/".join(url)), "/" + "/".join(raw), catch


# ============================================================================ JS module parsing
_EXPORT_FN = (r"^[ \t]*export\s+(?:async\s+)?function\s*\*?\s*({names})\s*[(<]|"
              r"^[ \t]*export\s+(?:const|let|var)\s+({names})\b\s*(?::[^=\n]+)?=")


def _local_def(text, name):
    m = re.search(r"^[ \t]*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*" + re.escape(name) + r"\s*[(<]|"
                  r"^[ \t]*(?:export\s+)?(?:const|let|var)\s+" + re.escape(name) + r"\b\s*(?::[^=\n]+)?=", text, re.M)
    return m.start() if m else None


def _exports(text, names):
    """[(exported name, declaration offset)] for exported functions or consts, incl. `export { local as NAME }`."""
    alt = "|".join(re.escape(n) for n in names)
    found = [(m.group(1) or m.group(2), m.start()) for m in re.finditer(_EXPORT_FN.format(names=alt), text, re.M)]
    have = {n for n, _ in found}
    for m in re.finditer(r"^[ \t]*export\s*\{([^}]*)\}", text, re.M):
        for part in m.group(1).split(","):
            local, _, alias = part.strip().partition(" as ")
            exported = (alias or local).strip()
            pos = _local_def(text, local.strip()) if exported in names and exported not in have and local.strip() else None
            if pos is not None:
                found.append((exported, pos))
                have.add(exported)
    return sorted(found, key=lambda x: x[1])


def _default_export(text):
    """(declaration offset, wrapper name or None, wrapper line, symbol) of the default export, or None."""
    m = re.search(r"^[ \t]*export\s+default\s+(?:async\s+)?function\b\s*\*?\s*(\w*)", text, re.M)
    if m:
        return m.start(), None, None, m.group(1) or "default"
    m = re.search(r"^[ \t]*export\s+default\s+([A-Za-z_][\w.]*)\s*\(\s*([A-Za-z_]\w*)\s*\)\s*;?[ \t]*$", text, re.M)
    if m and _local_def(text, m.group(2)) is not None:
        return _local_def(text, m.group(2)), m.group(1), (c.line_of(text, m.start()), m.group(0)), m.group(2)
    m = re.search(r"^[ \t]*export\s+default\s+([A-Za-z_]\w*)\s*;?[ \t]*$", text, re.M)
    if m and _local_def(text, m.group(1)) is not None:
        return _local_def(text, m.group(1)), None, None, m.group(1)
    m = re.search(r"^[ \t]*export\s+default\s+", text, re.M)
    return (m.start(), None, None, "default") if m else None


def _expr_parts(text, start):
    end = c.statement_end(text, start)
    expr = text[start:end]
    wm = re.match(r"\s*(?!async\b|function\b)([A-Za-z_][\w.]*)\s*\(", expr)
    wrapper = wm.group(1) if wm else None
    inner = expr[wm.end():] if wm else expr
    params, rtype = "", None
    pm = re.search(r"\(", inner)
    if pm:
        close = c.balanced_span(inner, pm.start())
        params = inner[pm.start() + 1:close - 1]
        rt = re.match(r"\s*:\s*([^=]+?)\s*=>", inner[close:])
        rtype = rt.group(1).strip() if rt else None
    else:
        am = re.match(r"\s*(?:async\s+)?(\w+)\s*=>", inner)
        params = am.group(1) if am else ""
    return end, params, rtype, wrapper


def handler_at(text, pos, depth=0):
    """Declaration at offset pos -> (decl offset, end offset, params text, return type, wrapper name)."""
    nl = text.find("\n", pos)
    nl = len(text) if nl < 0 else nl
    head = text[pos:nl]
    fm = re.match(r"[ \t]*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\b", head)
    if fm:
        open_p = text.find("(", pos + fm.end())
        if open_p < 0:
            return pos, nl, "", None, None
        close = c.balanced_span(text, open_p)
        brace, angle, i = -1, 0, close
        while i < len(text):
            ch = text[i]
            if ch == "<":
                angle += 1
            elif ch == ">" and text[i - 1] != "=":
                angle = max(0, angle - 1)
            elif ch == "{" and angle == 0:
                brace = i
                break
            elif ch == ";" and angle == 0:
                break
            i += 1
        if brace < 0:
            return pos, close, text[open_p + 1:close - 1], None, None
        rtype = text[close:brace].strip().lstrip(":").strip() or None
        return pos, c.balanced_span(text, brace), text[open_p + 1:close - 1], rtype, None
    em = re.match(r"[ \t]*export\s+default\s+", head) or re.search(r"=(?![=>])[ \t]*", head)
    if not em:
        return pos, nl, "", None, None
    start = pos + em.end()
    bare = re.match(r"([A-Za-z_]\w*)\s*;?[ \t]*(?:\n|$)", text[start:])
    if bare and depth < 2 and _local_def(text, bare.group(1)) not in (None, pos):
        return handler_at(text, _local_def(text, bare.group(1)), depth + 1)
    end, params, rtype, wrapper = _expr_parts(text, start)
    return pos, end, params, rtype, wrapper


def _lines_between(ctx, rel, text, start, end):
    first = c.line_of(text, start) - 1
    last = c.line_of(text, max(start, end - 1)) - 1
    return c.numbered(ctx.lines(rel)[first:last + 1], first)


def method_branches(body, req_var):
    """[(METHOD, numbered lines)] when the body branches on <req_var>.method; [] when it does not.

    if (<req>.method === 'X') {...} and switch (<req>.method) { case 'X': ... } give the prelude before the
    first branch plus that branch. Guards (<req>.method !== 'X') and ['X'].includes(<req>.method) give the
    whole body for each named method.
    """
    text = "\n".join(t for _, t in body)
    rv = r"\b" + re.escape(req_var) + r"\??\.method\b"
    if not re.search(rv, text):
        return []
    spans = []
    for m in re.finditer(r"\bif\s*\(\s*" + rv + r"\s*===?\s*['\"`](\w+)['\"`]\s*\)\s*\{", text):
        spans.append((m.group(1).upper(), m.start(), c.balanced_span(text, m.end() - 1)))
    sw = re.search(r"\bswitch\s*\(\s*" + rv + r"\s*\)\s*\{", text)
    if sw:
        blk_end = c.balanced_span(text, sw.end() - 1)
        block = text[sw.end():blk_end]
        labels = list(re.finditer(r"\b(?:case\s*['\"`](\w+)['\"`]|default)\s*:", block))
        for k, lm in enumerate(labels):
            if not lm.group(1):
                continue
            j = k + 1
            while j < len(labels) and not block[labels[j - 1].end():labels[j].start()].strip():   # case 'PUT': case 'PATCH': shares a body
                j += 1
            e = labels[j].start() if j < len(labels) else len(block)
            spans.append((lm.group(1).upper(), sw.end() + lm.start(), sw.end() + e))
    out, seen = [], set()
    if spans:
        first_line = min(text.count("\n", 0, s) for _, s, _ in spans)
        prelude = body[:first_line]
        for verb, s, e in sorted(spans, key=lambda x: x[1]):
            if verb in VERBS and verb not in seen:
                seen.add(verb)
                out.append((verb, prelude + body[text.count("\n", 0, s):text.count("\n", 0, e) + 1]))
        return out
    named = re.findall(rv + r"\s*!==?\s*['\"`](\w+)['\"`]", text) + re.findall(r"['\"`](\w+)['\"`]\s*!==?\s*" + rv, text)
    for im in re.finditer(r"\[([^\]]*)\]\s*\.includes\(\s*" + rv, text):
        named += re.findall(r"['\"`](\w+)['\"`]", im.group(1))
    for verb in (v.upper() for v in named):
        if verb in VERBS and verb not in seen:
            seen.add(verb)
            out.append((verb, body))
    return out


def _first_param_name(params, default):
    args = c.split_args(params or "")
    m = re.match(r"\s*\{?\s*(\w+)", args[0]) if args else None
    return m.group(1) if m else default


# ============================================================================ facts
def _params_from_text(text, placeholders, form_vars=()):
    params = [p for p in b._node_params_from_body(text, []) if not (p["in"] in ("route", "query") and p["name"] in placeholders)]

    def add(name, where):
        if name and not (where in ("route", "query") and name in placeholders):
            params.append(c.make_param(name, where))

    for m in re.finditer(r"\bsearchParams\??\.get(?:All)?\(\s*['\"`]([\w-]+)", text):
        add(m.group(1), "query")
    for m in re.finditer(r"\bgetRouterParam\(\s*\w+\s*,\s*['\"`](\w+)", text):
        add(m.group(1), "route")
    for m in re.finditer(r"\b(?:headers\??\.get|getHeader|getRequestHeader)\(\s*(?:\w+\s*,\s*)?['\"`]([\w-]+)", text):
        add(m.group(1), "header")
    for var in form_vars:
        for m in re.finditer(r"\b" + re.escape(var) + r"\.get(?:All)?\(\s*['\"`]([\w-]+)", text):
            add(m.group(1), "form")
    sources = {"query": r"(?:getQuery|getValidatedQuery)\(", "body": r"(?:readBody|readValidatedBody|(?:request|req)\.json)\(",
               "form": r"(?:readFormData|(?:request|req)\.formData)\("}
    for where, src in sources.items():
        for m in re.finditer(r"(?:const|let|var)\s*\{([^}]*)\}\s*=\s*(?:await\s+)?" + src, text):
            for n in m.group(1).split(","):
                add(n.split(":")[0].split("=")[0].strip(), where)
        for m in re.finditer(r"(?:const|let|var)\s+(\w+)\s*(?::[^=\n]+)?=\s*(?:await\s+)?" + src, text):
            for pm in re.finditer(r"\b" + re.escape(m.group(1)) + r"\??\.(?:get\(\s*['\"`]([\w-]+)['\"`]|(\w+)\b(?!\s*\())", text):
                add(pm.group(1) or pm.group(2), where)
    return params


def _signature_params(params_text, ctx):
    """Server action arguments -> (params, request types, FormData argument names read through <name>.get)."""
    params, types, form_vars = [], [], []
    for a in c.split_args(params_text or ""):
        m = re.match(r"(\w+)\s*\??\s*(?::\s*([^=]+))?(?:=.*)?$", a.strip())
        if not m or m.group(1) in ("prevState", "_prevState", "state"):
            continue
        typ = (m.group(2) or "").strip() or None
        if typ and re.search(r"\bFormData\b", typ):
            form_vars.append(m.group(1))
            continue
        params.append(c.make_param(m.group(1), "body", typ))
        for t in c.type_names(typ):
            if t in ctx.types and t not in types:
                types.append(t)
                params += c.body_params_from_type(t, ctx.types)
    return params, types, form_vars


def build_record(ctx, *, kind, stack, framework, method, path, path_raw, rel, text, body, decl_line, symbol,
                 params_text="", rtype=None, wrapper=None, wrapper_ev=None, catch=(), notes=()):
    """One contract record for a meta-framework handler, filled through the shared ep_common facts."""
    rec = c.new_record(kind=kind, stack=stack, framework=framework, method=method, path=path, path_raw=path_raw,
                       file=rel, line=decl_line, handler_line=decl_line, symbol=symbol, handler=symbol)
    code = [(no, c.strip_comment(t, "c")) for no, t in body]
    btxt = "\n".join(t for _, t in code)
    a = rec["auth"]
    hook = re.search(r"\bonRequest\s*:\s*([^\n]+)", btxt)
    if wrapper and AUTH_WRAPPER.match(wrapper.split(".")[-1]):
        ln, tx = wrapper_ev or (decl_line, wrapper + "(...)")
        a.update(required="yes", source="handler wrapper", evidence=[c.auth_ev(ln, tx)])
    elif c.evidence(code, AUTH_CALL, 1):
        a.update(required="yes", source="handler call", evidence=c.evidence(code, AUTH_CALL, 3))
    elif hook and b.AUTH_MW.search(hook.group(1)):
        a.update(required="yes", source="handler hook", evidence=c.evidence(code, re.compile(r"\bonRequest\s*:"), 1))
    else:
        a.update(required="no", source="none")
    a["roles"] = list(dict.fromkeys(g for m in ROLE_REF.finditer(btxt) for g in m.groups() if g))

    placeholders = c.route_placeholders(path) if kind == "http" else []
    params = [c.make_param(p, "route") for p in placeholders] + [c.make_param(n, "route") for n in catch]
    req_types, form_vars = [], []
    if kind == "server-action":
        sp, req_types, form_vars = _signature_params(params_text, ctx)
        params += sp
    params += _params_from_text(btxt, placeholders, form_vars)
    rec["params"] = c.dedupe_params(params)
    rec["id_params"] = c.id_params_for(path) if kind == "http" else {}

    bt = re.search(r"(?:const|let)\s+\w+\s*:\s*([A-Z]\w*)\s*=\s*await\s+(?:request|req)\.json\(|"
                   r"(?:request|req)\.json\(\)\s*\)?\s*as\s+([A-Z]\w*)|\b([A-Z]\w*)\.(?:safe)?[pP]arse(?:Async)?\(", btxt)
    body_type = next((g for g in bt.groups() if g), None) if bt else None
    req_types += [t for t in c.type_names(body_type) if t in ctx.types and t not in req_types]
    has_body = method in c.BODY_METHODS or bool(BODY_READ.search(btxt)) or (kind == "server-action" and bool(req_types or params_text.strip()))
    if has_body and not body_type:
        body_type = req_types[0] if req_types else ("form" if FORM_READ.search(btxt) or form_vars else ("json" if BODY_READ.search(btxt) else None))
    b._set_body_request(rec, req_types, body_type, has_body)

    if not rtype:
        jm = re.search(r"\b(?:json|typedjson|NextResponse\.json|Response\.json)\s*<\s*([^>(]+?)\s*>\s*\(", btxt)
        rtype = jm.group(1) if jm else None
    rec["response"]["type"] = rtype
    if kind == "http":
        b._version_fact(rec)
    extra = b.callee_bodies(ctx, rel, btxt, "node-express")
    c.fill_body_facts(rec, body, "node-express", ctx.types, extra, identity_rx=IDENTITY, validation_rx=VALIDATION,
                      selector_in=("route", "query", "body", "form") if kind == "server-action" else ("route", "query"))
    rec["notes"] += list(notes)
    return rec


# ============================================================================ extractors
def _next_app(ctx, rel, sub, text, skip, emit):
    route = next_app_route(sub)
    if not route:
        return
    path, raw, catch = route
    for verb, pos in _exports(text, VERBS):
        if (rel, verb) in skip:
            continue
        decl, end, params, rtype, wrapper = handler_at(text, pos)
        emit(build_record(ctx, kind="http", stack="react", framework="nextjs-route", method=verb, path=path, path_raw=raw, rel=rel,
                          text=text, body=_lines_between(ctx, rel, text, pos, end), decl_line=c.line_of(text, pos), symbol=verb,
                          params_text=params, rtype=rtype, wrapper=wrapper, catch=catch))


def _pages_api(ctx, rel, sub, text, emit):
    route = next_pages_api(sub)
    exp = _default_export(text) if route else None
    if not exp:
        return
    path, raw, catch = route
    pos, wrap_name, wrap_ev, symbol = exp
    decl, end, params, rtype, wrapper = handler_at(text, pos)
    body = _lines_between(ctx, rel, text, decl, end)
    wrapper = wrap_name or wrapper
    branches = method_branches(body, _first_param_name(params, "req"))
    notes = [] if branches else ["body does not branch on req.method; every method reaches this handler"]
    for verb, lines in branches or [("ANY", body)]:
        emit(build_record(ctx, kind="http", stack="react", framework="nextjs-pages-api", method=verb, path=path, path_raw=raw,
                          rel=rel, text=text, body=lines, decl_line=c.line_of(text, decl), symbol=symbol, params_text=params,
                          rtype=rtype, wrapper=wrapper, wrapper_ev=wrap_ev, catch=catch, notes=notes))


USE_SERVER_FILE = re.compile(r"\A(?:\s|//[^\n]*\n|/\*.*?\*/)*['\"]use server['\"]", re.S)
USE_CLIENT_FILE = re.compile(r"\A(?:\s|//[^\n]*\n|/\*.*?\*/)*['\"]use client['\"]", re.S)


def _server_actions(ctx, rel, text, emit):
    if "use server" not in text or USE_CLIENT_FILE.match(text):
        return
    found = []
    if USE_SERVER_FILE.match(text):
        rx = re.compile(r"^[ \t]*export\s+(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w*)\s*[(<]|"
                        r"^[ \t]*export\s+(?:const|let)\s+(\w+)\s*(?::[^=\n]+)?=\s*(?:async\b|function\b|\(|\w+\s*\()", re.M)
        for m in rx.finditer(text):
            found.append((m.group(1) or m.group(2) or "default", m.start(), "module"))
    for m in re.finditer(r"^[ \t]*['\"]use server['\"]", text, re.M):
        if USE_SERVER_FILE.match(text) and not text[:m.start()].strip(" \t\n;"):
            continue
        window_start = max(0, m.start() - 800)
        decls = list(re.finditer(r"^[ \t]*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(|^[ \t]*(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*async\b",
                                 text[window_start:m.start()], re.M))
        if not decls:
            continue
        d = decls[-1]
        pos = window_start + d.start()
        if handler_at(text, pos)[1] > m.start():
            found.append((d.group(1) or d.group(2), pos, "inline"))
    seen = set()
    for name, pos, where in found:
        if name in seen:
            continue
        seen.add(name)
        decl, end, params, rtype, wrapper = handler_at(text, pos)
        emit(build_record(ctx, kind="server-action", stack="react", framework="nextjs-server-action", method="POST",
                          path=f"{rel}#{name}", path_raw=f"{rel}#{name}", rel=rel, text=text,
                          body=_lines_between(ctx, rel, text, pos, end), decl_line=c.line_of(text, pos), symbol=name,
                          params_text=params, rtype=rtype, wrapper=wrapper,
                          notes=["server action: no URL, invoked by POST to the page that renders it; not in the probe file",
                                 "declared in a 'use server' module" if where == "module" else "inline 'use server' function"]))


def _next_middleware(ctx, rel, sub, text, emit):
    if sub not in ("middleware.ts", "middleware.js", "src/middleware.ts", "src/middleware.js"):
        return
    exp = _exports(text, ("middleware",))
    alias = re.search(r"^[ \t]*export\s*\{\s*(\w+)\s+as\s+middleware\s*\}", text, re.M)
    dflt = _default_export(text)
    if exp:
        pos = exp[0][1]
    elif dflt:
        pos = dflt[0]
    elif alias:
        pos = alias.start()
    else:
        return
    decl, end, params, rtype, wrapper = handler_at(text, pos)
    if alias and not exp and not dflt:
        wrapper = alias.group(1)
    matcher = re.search(r"matcher\s*:\s*(\[[^\]]*\]|['\"`][^'\"`]+['\"`])", text)
    scopes = re.findall(r"['\"`]([^'\"`]+)['\"`]", matcher.group(1)) if matcher else ["*"]
    for scope in scopes:
        emit(build_record(ctx, kind="middleware", stack="react", framework="nextjs-middleware", method="ANY", path=scope, path_raw=scope,
                          rel=rel, text=text, body=_lines_between(ctx, rel, text, pos, end), decl_line=c.line_of(text, pos),
                          symbol="middleware", wrapper=wrapper, wrapper_ev=(c.line_of(text, pos), text[pos:text.find("\n", pos)]),
                          notes=["middleware scope is the config.matcher entry, or * when none is declared"]))


def _remix(ctx, rel, sub, proj, text, emit):
    route = remix_route(ctx, rel, sub)
    if not route:
        return
    path, raw, catch = route
    cfg = (proj + "/" if proj else "") + "app/routes.ts"
    notes = []
    if cfg in ctx.text_by_rel and "flatRoutes" not in ctx.text_by_rel[cfg]:
        notes.append("app/routes.ts declares routes; path derived from the file name and may differ")
    for name, pos in _exports(text, ("loader", "action")):
        decl, end, params, rtype, wrapper = handler_at(text, pos)
        body = _lines_between(ctx, rel, text, pos, end)
        if name == "loader":
            variants = [("GET", body, notes)]
        else:
            branches = method_branches(body, "request")
            variants = [(v, ln, notes) for v, ln in branches] or \
                [("POST", body, notes + ["action receives every non-GET method and does not branch on request.method; recorded as POST"])]
        for verb, lines, nts in variants:
            emit(build_record(ctx, kind="http", stack="react", framework="remix-route", method=verb, path=path, path_raw=raw, rel=rel,
                              text=text, body=lines, decl_line=c.line_of(text, pos), symbol=name, params_text=params, rtype=rtype,
                              wrapper=wrapper, catch=catch, notes=nts))


def _nuxt(ctx, rel, sub, text, emit):
    info = nuxt_route(sub)
    if not info or not EVENT_HANDLER.search(text):
        return
    area, route, method = info
    exp = _default_export(text)
    if not exp:
        return
    pos = exp[0]
    decl, end, params, rtype, wrapper = handler_at(text, pos)
    body = _lines_between(ctx, rel, text, decl, end)
    if area == "middleware":
        emit(build_record(ctx, kind="middleware", stack="vue", framework="nuxt-server-middleware", method="ANY", path="*", path_raw="*",
                          rel=rel, text=text, body=body, decl_line=c.line_of(text, decl), symbol="default export", wrapper=wrapper,
                          notes=["Nitro server middleware runs before every server route; path conditions inside it are not evaluated"]))
        return
    path, raw, catch = route
    emit(build_record(ctx, kind="http", stack="vue", framework="nuxt-server-route", method=method, path=path, path_raw=raw, rel=rel,
                      text=text, body=body, decl_line=c.line_of(text, decl), symbol="default export", params_text=params,
                      rtype=rtype, wrapper=wrapper, catch=catch,
                      notes=[] if method != "ANY" else ["no method suffix in the file name; every method reaches this handler"]))


def scan_metaframeworks(ctx, stacks, out):
    """Append meta-framework records for the react and vue stacks in `stacks` to `out`.

    App Router handlers already recorded by the node-express extractor (framework nextjs-route, same file and
    method) are left as they are, so their ids do not change.
    """
    skip = {(r["file"], r["method"]) for r in out if r["framework"] == "nextjs-route"}
    new, project = [], {}

    def emitter(proj):
        def emit(rec):
            project[id(rec)] = proj
            new.append(rec)
        return emit

    if "react" in stacks:
        for rel, text in ctx.files("react", JS_EXT):
            sub, proj = _stack_rel(ctx, "react", rel)
            emit = emitter(proj)
            _next_app(ctx, rel, sub, text, skip, emit)
            _pages_api(ctx, rel, sub, text, emit)
            _next_middleware(ctx, rel, sub, text, emit)
            _server_actions(ctx, rel, text, emit)
            _remix(ctx, rel, sub, proj, text, emit)
    if "vue" in stacks:
        for rel, text in ctx.files("vue", JS_EXT):
            sub, proj = _stack_rel(ctx, "vue", rel)
            _nuxt(ctx, rel, sub, text, emitter(proj))

    # A middleware with auth evidence in the same project makes an otherwise undeclared handler "unknown", not "no".
    guards = [r for r in new if r["kind"] == "middleware" and r["auth"]["required"] == "yes"]
    for r in new:
        if r["kind"] not in ("http", "server-action") or r["auth"]["source"] != "none":
            continue
        family = r["framework"].split("-")[0]
        mw = next((m for m in guards if project[id(m)] == project[id(r)] and m["framework"].split("-")[0] == family), None)
        if mw:
            label = "next middleware" if family == "nextjs" else "server middleware"
            r["auth"].update(required="unknown", source=f"{label} ({mw['file']})",
                             evidence=[{"line": e["line"], "text": f"{mw['file']}: {e['text']}"[:160]} for e in mw["auth"]["evidence"][:1]])
    out.extend(new)
