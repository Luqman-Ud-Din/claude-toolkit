#!/usr/bin/env python3
"""Server-side endpoint extractors for inventory_endpoints.py.

Stacks: dotnet (MVC/API controllers, minimal APIs, SignalR hubs), java-spring
(@RestController, Spring MVC), node-express (Express routers, NestJS, Fastify,
Next.js route handlers), python-django (Django urls, DRF views/viewsets, Flask,
FastAPI, Channels websockets).

Usage (module):
    import ep_backends
    ep_backends.SCANNERS["dotnet"](ctx, out)

Each scanner appends contract records (see references/endpoint-inventory-contract.md)
to `out`. Regex heuristics over source text; read-only.
"""
import os
import re

import ep_common as c

HTTP_WORDS = ("Get", "Post", "Put", "Delete", "Patch", "Head", "Options")
KEYWORDS = {"if", "for", "foreach", "while", "switch", "catch", "return", "new", "using", "lock", "function", "else", "await",
            "typeof", "sizeof", "nameof", "base", "this", "super", "throw"}


# ============================================================================ one-hop callee bodies
def callee_bodies(ctx, rec_file, body_text, stack, own_names=(), limit=3):
    """Resolve receiver.method( calls in a handler body to method bodies elsewhere (one hop)."""
    out, seen = [], set()
    for m in re.finditer(r"(?:\b|this\.)(\w+)\s*\.\s*(\w+)\s*\(", body_text):
        recv, meth = m.group(1), m.group(2)
        if recv in ("req", "res", "request", "response", "console", "Math", "JSON", "Object", "Promise", "Task", "_db", "db",
                    "prisma", "context", "_context", "self", "this", "User", "Ok", "string", "String", "int") or meth in KEYWORDS:
            continue
        stem = re.sub(r"(service|manager|repository|repo|client|handler|controller|provider|store)s?$", "", recv.lower().lstrip("_"))
        if len(stem) < 3:
            continue
        for cand in ctx.methods.get(meth, []):
            owner = (cand["class"] or os.path.splitext(os.path.basename(cand["file"]))[0]).lower()
            if stem in owner or c.singular(stem) in owner:
                key = (cand["file"], cand["start"])
                if key in seen or (cand["file"] == rec_file and cand["class"] in own_names):
                    continue
                seen.add(key)
                lines = ctx.lines(cand["file"])
                out.append((cand["file"], f"{cand['class'] or os.path.basename(cand['file'])}.{meth}",
                            c.numbered(lines[cand["start"]:cand["end"] + 1], cand["start"])))
                break
        if len(out) >= limit:
            break
    return out


def resolve_named_function(ctx, name):
    for cand in ctx.methods.get(name, []):
        lines = ctx.lines(cand["file"])
        return cand, c.numbered(lines[cand["start"]:cand["end"] + 1], cand["start"])
    return None, []


def _version_fact(rec, extra_marker=None):
    raw = rec["path_raw"] or ""
    m = re.search(r"/v\d+(/|$)", raw) or re.search(r"\{version", raw, re.I)
    parts = (["route " + raw] if m else []) + ([extra_marker] if extra_marker else [])
    if parts:
        rec["versioned"] = {"status": "yes", "evidence": "; ".join(parts)}


# ============================================================================ .NET
DOTNET_FALLBACK = re.compile(r"FallbackPolicy\s*=|RequireAuthenticatedUser\(\)\s*\.Build\(\)|MapControllers\(\)\s*\.RequireAuthorization|"
                             r"Filters\.Add\(\s*new\s+AuthorizeFilter")
DOTNET_SIG = re.compile(r"^\s*(?:\[[^\]]*\]\s*)*(?:public|protected|internal)\s+(?:(?:async|virtual|override|static|new|sealed)\s+)*"
                        r"([\w<>\[\],.?\s]+?)\s+(\w+)\s*(?:<[^>]*>)?\s*\(")
DOTNET_CLASS = re.compile(r"\bclass\s+(\w+)(?:<[^>]*>)?(?:\s*\([^)]*\))?\s*(?::\s*([^{\n]+))?")


def _leading_attrs(line):
    """Split '[A][B(x)] rest' into (['[A]','[B(x)]'], 'rest')."""
    s = line.strip()
    attrs = []
    while s.startswith("["):
        end = c.balanced_span(s, 0)
        attrs.append(s[:end])
        s = s[end:].strip()
    return attrs, s


def _dotnet_class_table(ctx, files):
    table = {}
    for rel, text in files:
        lines = text.splitlines()
        pending = []
        for i, line in enumerate(lines):
            attrs, rest = _leading_attrs(line)
            pending += [(i + 1, a) for a in attrs]
            if not rest or rest.startswith("//"):
                continue
            cm = DOTNET_CLASS.search(rest)
            if cm and not rest.startswith(("return", "var ")):
                bases = [b.strip().split("<")[0] for b in (cm.group(2) or "").split(",") if b.strip()]
                table.setdefault(cm.group(1), {"file": rel, "attrs": pending, "bases": bases})
            pending = []
    return table


def _dotnet_auth_attrs(attrs):
    """(authorize_attrs, anonymous_attrs, roles, policies) from [(line, text)]."""
    authz, anon, roles, policies = [], [], [], []
    for no, a in attrs:
        if re.search(r"\bAllowAnonymous\b", a):
            anon.append((no, a))
        if re.search(r"\bAuthorize\b|\w*Authorize\w*\(|HasPermission|RequirePermission|\w*Permission\w*Attribute", a) and \
                not re.search(r"\bAllowAnonymous\b", a):
            authz.append((no, a))
        for grp in re.findall(r"Roles\s*=\s*\"([^\"]+)\"", a):
            roles += [r.strip() for r in grp.split(",") if r.strip()]
        for grp in re.findall(r"Roles\s*=\s*((?:[A-Za-z_][\w.]*)(?:\s*\+\s*(?:\"[^\"]*\"|[A-Za-z_][\w.]*))*)", a):
            roles += [x for x in re.findall(r"[A-Za-z_][\w.]*", grp)]
        policies += re.findall(r"Policy\s*=\s*\"([^\"]+)\"", a)
        pm = re.search(r"\[\s*Authorize\s*\(\s*\"([^\"]+)\"", a)
        if pm:
            policies.append(pm.group(1))
        cm = re.search(r"\[\s*(\w*(?:Permission|Authorize)\w*)\s*\(\s*([^)]*)\)", a)
        if cm and cm.group(1) != "Authorize":
            policies.append(f"{cm.group(1)}({cm.group(2).strip()})")
    return authz, anon, list(dict.fromkeys(roles)), list(dict.fromkeys(policies))


def _dotnet_params(sig_params, placeholders, method, ctx):
    params, req_types, body_type, explicit_body = [], [], None, False
    for a in c.split_args(sig_params):
        if not a:
            continue
        attrs = re.findall(r"\[\s*(From\w+)(?:\(([^)]*)\))?\s*\]", a)
        bare = re.sub(r"\[[^\]]*\]", "", a).strip()
        bare = re.sub(r"=.*$", "", bare).strip()
        bare = re.sub(r"^(this|params|ref|out|in)\s+", "", bare)
        pm = re.match(r"([\w<>\[\],.?]+(?:\s*<[^>]*>)?)\s+(\w+)$", bare)
        if not pm:
            continue
        typ, name = pm.group(1), pm.group(2)
        base = typ.rstrip("?").split("<")[0].split(".")[-1]
        src = attrs[0][0] if attrs else None
        if src == "FromServices" or (not src and (c.SERVICE_TYPE.search(typ) or base in ("CancellationToken",))):
            continue
        hdr = re.search(r"Name\s*=\s*\"([^\"]+)\"", attrs[0][1]) if attrs and attrs[0][1] else None
        simple = base.lower() in c.SIMPLE_TYPES or typ.endswith("[]") and typ[:-2].lower() in c.SIMPLE_TYPES
        where = {"FromRoute": "route", "FromQuery": "query", "FromBody": "body", "FromHeader": "header", "FromForm": "form"}.get(src)
        if not where:
            if name in placeholders or name.lower() in [p.lower() for p in placeholders]:
                where = "route"
            elif simple:
                where = "query"
            else:
                where = "body" if method in c.WRITE_METHODS else "query"
        if where in ("body", "form"):
            explicit_body = explicit_body or src in ("FromBody", "FromForm")
        pname = hdr.group(1) if hdr else name
        params.append(c.make_param(pname, where, typ))
        for t in c.type_names(typ):
            if t in ctx.types and t not in req_types:
                req_types.append(t)
                if where in ("body", "form"):
                    body_type = body_type or t
                    params += c.body_params_from_type(t, ctx.types)
                elif where == "query" and not simple:
                    params += [dict(p, **{"in": "query"}) for p in c.body_params_from_type(t, ctx.types)]
        if where in ("body", "form") and body_type is None:
            body_type = typ
    has_body = explicit_body or (method in c.BODY_METHODS and any(p["in"] in ("body", "form") and p["source_type"] is None
                                                                    for p in params))
    return c.dedupe_params(params), req_types, body_type, has_body


def _set_body_request(rec, req_types, body_type, has_body):
    rec["request"] = {"types": req_types, "has_body": bool(has_body), "body_type": body_type if has_body else None,
                      "body_type_named_as_dto": (bool(re.search(r"(Dto|Request|Model|Command|Input|Payload|Form|ViewModel|Query)\b",
                                                                body_type or "")) if has_body and body_type else None)}


def scan_dotnet(ctx, out):
    files = ctx.files("dotnet", (".cs",))
    fallback = None
    for rel, text in files:
        m = DOTNET_FALLBACK.search(text)
        if m:
            fallback = (rel, c.line_of(text, m.start()), text[m.start():m.start() + 80].splitlines()[0])
            break
    classes = _dotnet_class_table(ctx, files)
    for rel, text in files:
        lines = text.splitlines()
        _dotnet_controllers(ctx, rel, lines, classes, fallback, out)
        _dotnet_minimal(ctx, rel, text, classes, fallback, out)


def _inherited_attrs(classes, name, depth=0):
    info = classes.get(name)
    if not info or depth > 4:
        return [], None
    for b in info["bases"]:
        if b in ("ControllerBase", "Controller", "ApiController", "Hub"):
            continue
        if b in classes:
            attrs = classes[b]["attrs"]
            more, _ = _inherited_attrs(classes, b, depth + 1)
            return attrs + more, b
    return [], None


def _dotnet_controllers(ctx, rel, lines, classes, fallback, out):
    pending, cls, cls_attrs, cls_route, cls_version = [], None, [], "", None
    for i, line in enumerate(lines):
        attrs, rest = _leading_attrs(line)
        pending += [(i + 1, a) for a in attrs]
        if not rest:
            continue
        if rest.startswith(("//", "/*", "*")):
            continue
        cm = DOTNET_CLASS.search(rest)
        if cm and not rest.startswith(("return", "var ")) and "(" not in rest.split("class")[0]:
            name, bases = cm.group(1), cm.group(2) or ""
            is_ctrl = name.endswith("Controller") or re.search(r"Controller", bases) or \
                any(re.search(r"ApiController|\bRoute\(", a) for _, a in pending)
            if is_ctrl:
                cls, cls_attrs = name, pending
                inh, _ = _inherited_attrs(classes, name)
                rt = next((re.search(r"Route\(\s*\"([^\"]*)\"", a) for _, a in cls_attrs if "Route(" in a), None)
                if not rt:
                    rt = next((re.search(r"Route\(\s*\"([^\"]*)\"", a) for _, a in inh if "Route(" in a), None)
                cls_route = rt.group(1) if rt else ""
                cls_version = next((a for _, a in cls_attrs if "ApiVersion" in a), None)
            else:
                cls = None
            pending = []
            continue
        mm = DOTNET_SIG.match(rest)
        verb_attrs = [(no, a) for no, a in pending if re.search(r"\[\s*(?:Http(?:Get|Post|Put|Delete|Patch|Head|Options)|Route)\b", a)]
        if mm and cls and verb_attrs and mm.group(2) not in KEYWORDS:
            method_attrs = pending
            pending = []
            rtype, name = mm.group(1).strip(), mm.group(2)
            sig_start = i
            sig = rest
            j = i
            while sig.count("(") > sig.count(")") and j + 1 < len(lines) and j < i + 12:
                j += 1
                sig += " " + lines[j].strip()
            ps = sig.find("(", sig.find(name) + len(name))
            sig_params = sig[ps + 1:c.balanced_span(sig, ps) - 1] if ps >= 0 else ""
            end = c.brace_body_end(lines, sig_start)
            body = c.numbered(lines[sig_start:end + 1], sig_start)
            verbs = []
            method_route = next((re.search(r"\[\s*Route\(\s*\"([^\"]*)\"", a) for _, a in method_attrs if re.search(r"\[\s*Route\(", a)), None)
            for no, a in method_attrs:
                for vm in re.finditer(r"Http(Get|Post|Put|Delete|Patch|Head|Options)\b(?:\(\s*(?:template\s*:\s*)?(?:\"([^\"]*)\")?[^)]*\))?", a):
                    verbs.append((vm.group(1).upper(), vm.group(2), no))
            if not verbs:
                verbs = [("ANY", None, method_route and verb_attrs[0][0])]
            inh, inh_base = _inherited_attrs(classes, cls)
            for verb, tmpl, vline in verbs:
                template = tmpl if tmpl is not None else (method_route.group(1) if method_route else "")
                ctrl = re.sub(r"Controller$", "", cls)
                base = cls_route.replace("[controller]", ctrl.lower()).replace("[action]", name.lower())
                template = template.replace("[action]", name.lower()).replace("[controller]", ctrl.lower())
                raw = c.join_path(template) if template.startswith(("/", "~")) else c.join_path(base, template)
                path = c.norm_path(raw)
                rec = c.new_record(kind="http", stack="dotnet", framework="aspnet-controller", method=verb, path=path, path_raw=raw,
                                   file=rel, line=vline or (i + 1), handler_line=i + 1, symbol=f"{cls}.{name}", handler=name)
                rec["class"] = cls
                _dotnet_apply_auth(rec, method_attrs, cls_attrs, inh, inh_base, fallback)
                params, req_types, body_type, has_body = _dotnet_params(sig_params, c.route_placeholders(raw), verb, ctx)
                rec["params"] = params
                rec["id_params"] = c.id_params_for(path)
                _set_body_request(rec, req_types, body_type, has_body)
                rec["response"]["type"] = rtype
                _version_fact(rec, "attribute " + cls_version if cls_version else None)
                extra = callee_bodies(ctx, rel, "\n".join(t for _, t in body), "dotnet", own_names=(cls,))
                c.fill_body_facts(rec, body, "dotnet", ctx.types, extra)
                out.append(rec)
            continue
        if rest and not rest.startswith("//"):
            pending = []


def _dotnet_apply_auth(rec, method_attrs, cls_attrs, inh_attrs, inh_base, fallback):
    m_authz, m_anon, m_roles, m_pol = _dotnet_auth_attrs(method_attrs)
    c_authz, c_anon, c_roles, c_pol = _dotnet_auth_attrs(cls_attrs)
    i_authz, i_anon, i_roles, i_pol = _dotnet_auth_attrs(inh_attrs)
    a = rec["auth"]
    a["roles"] = list(dict.fromkeys(c_roles + i_roles + m_roles))
    a["policies"] = list(dict.fromkeys(c_pol + i_pol + m_pol))
    if m_anon or ((c_anon or i_anon) and not m_authz):
        src = (m_anon or c_anon or i_anon)[0]
        a.update(required="no", source="explicit-anonymous", anonymous_marker="[AllowAnonymous]",
                 evidence=[c.auth_ev(*src)])
    elif m_authz:
        a.update(required="yes", source="method attribute", evidence=[c.auth_ev(*x) for x in m_authz[:3]])
    elif c_authz:
        a.update(required="yes", source="class attribute", evidence=[c.auth_ev(*x) for x in c_authz[:3]])
    elif i_authz:
        a.update(required="yes", source=f"base class attribute ({inh_base})", evidence=[c.auth_ev(*x) for x in i_authz[:3]])
    elif fallback:
        a.update(required="yes", source="global fallback", evidence=[{"line": fallback[1], "text": f"{fallback[0]}: {fallback[2]}"}])
    else:
        a.update(required="no", source="none", evidence=[])


def _dotnet_minimal(ctx, rel, text, classes, fallback, out):
    groups = {}
    for m in re.finditer(r"(\w+)\s*=\s*(\w+)\.MapGroup\(\s*\"([^\"]*)\"\s*\)", text):
        end = c.statement_end(text, m.start())
        stmt = text[m.start():end]
        parent = groups.get(m.group(2), {"prefix": "", "auth": None})
        auth = parent["auth"]
        if ".AllowAnonymous(" in stmt:
            auth = ("no", c.line_of(text, m.start()), stmt.strip()[:120])
        elif ".RequireAuthorization(" in stmt:
            auth = ("yes", c.line_of(text, m.start()), stmt.strip()[:120])
        groups[m.group(1)] = {"prefix": c.join_path(parent["prefix"], m.group(3)), "auth": auth}
    for m in re.finditer(r"\b(\w+)\s*\.\s*Map(Get|Post|Put|Delete|Patch|Methods|Hub)\s*(?:<\s*(\w+)\s*>)?\s*\(\s*\"([^\"]*)\"", text):
        recv, verb, hub, tmpl = m.group(1), m.group(2), m.group(3), m.group(4)
        end = c.statement_end(text, m.start())
        stmt = text[m.start():end]
        line = c.line_of(text, m.start())
        grp = groups.get(recv, {"prefix": "", "auth": None})
        raw = c.join_path(grp["prefix"], tmpl)
        path = c.norm_path(raw)
        open_pos = text.find("(", m.start() + len(m.group(0)) - len(tmpl) - 3)
        args = c.split_args(text[open_pos + 1:c.balanced_span(text, open_pos) - 1])
        if verb == "Hub":
            rec = c.new_record(kind="websocket", stack="dotnet", framework="signalr-hub", method="WS", path=path, path_raw=raw,
                               file=rel, line=line, handler_line=line, symbol=hub, handler=hub)
            rec["class"] = hub
            hub_attrs = classes.get(hub, {}).get("attrs", [])
            h_authz, h_anon, roles, pol = _dotnet_auth_attrs(hub_attrs)
            rec["auth"]["roles"], rec["auth"]["policies"] = roles, pol
            if ".RequireAuthorization(" in stmt or h_authz:
                rec["auth"].update(required="yes", source="hub attribute" if h_authz else "endpoint",
                                   evidence=[c.auth_ev(*h_authz[0])] if h_authz else [c.auth_ev(line, stmt)])
            elif fallback:
                rec["auth"].update(required="yes", source="global fallback")
            else:
                rec["auth"].update(required="no", source="none")
            out.append(rec)
            continue
        methods = [verb.upper()]
        if verb == "Methods":
            methods = [x.upper() for x in re.findall(r"\"(\w+)\"", args[1] if len(args) > 1 else "")] or ["ANY"]
        handler_arg = args[2] if verb == "Methods" and len(args) > 2 else (args[1] if len(args) > 1 else "")
        body = c.numbered(stmt.splitlines(), line - 1)
        symbol, sig_params, extra = "minimal-api", "", []
        lm = re.match(r"(?:\[[^\]]*\]\s*)*(?:async\s+)?\(([^)]*)\)\s*=>", handler_arg.strip()) or \
            re.match(r"(?:async\s+)?(\w+)\s*=>", handler_arg.strip())
        if lm:
            sig_params = lm.group(1) if "(" in handler_arg.strip()[:handler_arg.strip().find("=>")] else ""
        elif re.fullmatch(r"[\w.]+", handler_arg.strip() or "-"):
            symbol = handler_arg.strip()
            cand, fbody = resolve_named_function(ctx, symbol.split(".")[-1])
            if cand:
                sig_line = ctx.lines(cand["file"])[cand["start"]]
                pm = re.search(r"\((.*)\)", sig_line)
                sig_params = pm.group(1) if pm else ""
                extra = [(cand["file"], symbol, fbody)]
        for verb_u in methods:
            rec = c.new_record(kind="http", stack="dotnet", framework="aspnet-minimal-api", method=verb_u, path=path, path_raw=raw,
                               file=rel, line=line, handler_line=line, symbol=symbol, handler=symbol)
            a = rec["auth"]
            a["policies"] = re.findall(r"RequireAuthorization\(\s*\"([^\"]+)\"", stmt)
            a["roles"] = re.findall(r"RequireRole\(\s*\"([^\"]+)\"", stmt)
            if ".AllowAnonymous(" in stmt or "[AllowAnonymous]" in handler_arg:
                a.update(required="no", source="explicit-anonymous", anonymous_marker=".AllowAnonymous()",
                         evidence=[c.auth_ev(line, stmt.splitlines()[0])])
            elif ".RequireAuthorization(" in stmt or "[Authorize" in handler_arg:
                a.update(required="yes", source="endpoint", evidence=[c.auth_ev(line, stmt.splitlines()[0])])
            elif grp["auth"]:
                a.update(required=grp["auth"][0], source="group " + ("anonymous" if grp["auth"][0] == "no" else "RequireAuthorization"),
                         evidence=[{"line": grp["auth"][1], "text": grp["auth"][2]}])
                if grp["auth"][0] == "no":
                    a["anonymous_marker"] = ".AllowAnonymous()"
                    a["source"] = "explicit-anonymous"
            elif fallback:
                a.update(required="yes", source="global fallback", evidence=[{"line": fallback[1], "text": f"{fallback[0]}: {fallback[2]}"}])
            else:
                a.update(required="no", source="none")
            params, req_types, body_type, has_body = _dotnet_params(sig_params, c.route_placeholders(raw), verb_u, ctx)
            rec["params"], rec["id_params"] = params, c.id_params_for(path)
            _set_body_request(rec, req_types, body_type, has_body)
            _version_fact(rec)
            extra2 = extra + callee_bodies(ctx, rel, stmt, "dotnet")
            c.fill_body_facts(rec, body + (extra[0][2] if extra else []), "dotnet", ctx.types, extra2[len(extra):])
            out.append(rec)
    for m in re.finditer(r"\b\w+\s*\.\s*Map\(\s*\"([^\"]*)\"", text):
        end = c.statement_end(text, m.start())
        stmt = text[m.start():end]
        if "WebSocket" in stmt:
            line = c.line_of(text, m.start())
            rec = c.new_record(kind="websocket", stack="dotnet", framework="aspnet-websocket", method="WS", path=c.norm_path(m.group(1)),
                               path_raw=m.group(1), file=rel, line=line, handler_line=line, symbol="Map", handler="Map")
            rec["auth"].update(required="yes" if (".RequireAuthorization(" in stmt or fallback) else "no",
                               source="endpoint" if ".RequireAuthorization(" in stmt else ("global fallback" if fallback else "none"))
            out.append(rec)


# ============================================================================ Java / Spring
SPRING_SIG = re.compile(r"^\s*(?:(?:public|protected|private|static|final|suspend|override|open)\s+)*(?:<[^>]+>\s+)?"
                        r"(?:([\w<>\[\],.?\s]+?)\s+(\w+)\s*\(|fun\s+(\w+)\s*\()")


def _spring_config(files):
    matchers, default = [], None
    for rel, t in files:
        if "SecurityFilterChain" not in t and "HttpSecurity" not in t:
            continue
        for m in re.finditer(r"(?:requestMatchers|antMatchers|mvcMatchers)\(([^)]*)\)\s*\.\s*(permitAll|authenticated|hasRole|hasAnyRole|"
                             r"hasAuthority|hasAnyAuthority|denyAll|access)\(([^)]*)\)", t):
            for pat in re.findall(r"\"([^\"]+)\"", m.group(1)):
                matchers.append((pat, m.group(2), m.group(3), rel, c.line_of(t, m.start())))
        dm = re.search(r"anyRequest\(\)\s*\.\s*(authenticated|hasRole|hasAuthority|access|permitAll)\(", t)
        if dm:
            default = (dm.group(1), rel, c.line_of(t, dm.start()))
    return matchers, default


def _ant_match(pattern, path):
    rx = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.fullmatch(rx, path) is not None or re.fullmatch(rx, path.rstrip("/") + "/") is not None


def scan_java_spring(ctx, out):
    files = ctx.files("java-spring", (".java", ".kt"))
    matchers, default = _spring_config(files)
    for rel, text in files:
        if not re.search(r"@(RestController|Controller)\b", text) and "Mapping(" not in text:
            continue
        lines = text.splitlines()
        head = text.split("class ", 1)[0] if "class " in text else ""
        cm = re.search(r"@RequestMapping\(\s*(?:(?:value|path)\s*=\s*)?\{?\s*\"([^\"]*)\"", head)
        cls_route = cm.group(1) if cm else ""
        cls_sec = re.findall(r"@(?:PreAuthorize|Secured|RolesAllowed)\([^)]*\)", head)
        cls_name_m = re.search(r"class\s+(\w+)", text)
        cls_name = cls_name_m.group(1) if cls_name_m else None
        annos = []
        i = 0
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith("@"):
                a, j = s, i
                while a.count("(") > a.count(")") and j + 1 < len(lines):
                    j += 1
                    a += " " + lines[j].strip()
                annos.append((i + 1, a))
                i = j + 1
                continue
            mm = SPRING_SIG.match(lines[i])
            name = (mm.group(2) or mm.group(3)) if mm else None
            if mm and name not in KEYWORDS and any(re.search(r"@(Get|Post|Put|Delete|Patch|Request)Mapping", a) for _, a in annos):
                m_annos, annos = annos, []
                sig, j = lines[i], i
                while sig.count("(") > sig.count(")") and j + 1 < len(lines) and j < i + 15:
                    j += 1
                    sig += " " + lines[j].strip()
                ps = sig.find("(", sig.find(name) + len(name))
                sig_params = sig[ps + 1:c.balanced_span(sig, ps) - 1]
                rtype = (mm.group(1) or "").strip()
                if mm.group(3):
                    rt = re.search(r"\)\s*:\s*([\w<>?,. ]+)", sig)
                    rtype = rt.group(1).strip() if rt else ""
                end = c.brace_body_end(lines, i)
                body = c.numbered(lines[i:end + 1], i)
                verbs = []
                for no, a in m_annos:
                    vm = re.search(r"@(Get|Post|Put|Delete|Patch|Request)Mapping(?:\((.*)\))?", a)
                    if not vm:
                        continue
                    args = vm.group(2) or ""
                    verb = vm.group(1).upper() if vm.group(1) != "Request" else "ANY"
                    rmm = re.findall(r"RequestMethod\.(\w+)", args)
                    pv = re.search(r"(?:value|path)\s*=\s*(\{[^}]*\}|\"[^\"]*\")", args) or re.match(r"\s*(\{[^}]*\}|\"[^\"]*\")", args)
                    templates = re.findall(r"\"([^\"]*)\"", pv.group(1)) if pv else [""]
                    for vv in ([x.upper() for x in rmm] or [verb]):
                        for t in templates or [""]:
                            verbs.append((vv, t, no))
                sec = [(no, a) for no, a in m_annos if re.search(r"@(PreAuthorize|Secured|RolesAllowed|PermitAll|DenyAll|PostAuthorize)", a)]
                for verb, tmpl, vline in verbs:
                    raw = c.join_path(cls_route, tmpl)
                    path = c.norm_path(raw)
                    rec = c.new_record(kind="http", stack="java-spring", framework="spring-mvc", method=verb, path=path, path_raw=raw,
                                       file=rel, line=vline, handler_line=i + 1, symbol=f"{cls_name}.{name}" if cls_name else name,
                                       handler=name)
                    rec["class"] = cls_name
                    a = rec["auth"]
                    texts = [x for _, x in sec] + cls_sec
                    for t in texts:
                        a["roles"] += re.findall(r"has(?:Any)?Role\(\s*'([^']+)'", t) + re.findall(r"\"(ROLE_\w+)\"", t)
                        a["policies"] += re.findall(r"has(?:Any)?Authority\(\s*'([^']+)'", t)
                    a["roles"] = list(dict.fromkeys(a["roles"]))
                    match = next((mt for mt in matchers if _ant_match(mt[0], path)), None)
                    if any("@PermitAll" in x for _, x in sec) or any("permitAll()" in x for _, x in sec):
                        a.update(required="no", source="explicit-anonymous", anonymous_marker="@PermitAll", evidence=[c.auth_ev(*sec[0])])
                    elif sec:
                        a.update(required="yes", source="method annotation", evidence=[c.auth_ev(*x) for x in sec[:3]])
                    elif cls_sec:
                        a.update(required="yes", source="class annotation", evidence=[{"line": 1, "text": cls_sec[0]}])
                    elif match:
                        req = "no" if match[1] == "permitAll" else "yes"
                        a.update(required=req, source=f"config: {match[0]} {match[1]}", evidence=[{"line": match[4], "text": f"{match[3]}: {match[0]} -> {match[1]}"}])
                        if req == "no":
                            a.update(source="explicit-anonymous", anonymous_marker="permitAll()")
                    elif default:
                        req = "no" if default[0] == "permitAll" else "yes"
                        a.update(required=req, source=f"config: anyRequest().{default[0]}()", evidence=[{"line": default[2], "text": default[1]}])
                    else:
                        a.update(required="unknown", source="config not found (check SecurityFilterChain)")
                    params, req_types, body_type, has_body = _spring_params(sig_params, c.route_placeholders(raw), ctx)
                    rec["params"], rec["id_params"] = params, c.id_params_for(path)
                    _set_body_request(rec, req_types, body_type, has_body)
                    rec["response"]["type"] = rtype
                    _version_fact(rec)
                    extra = callee_bodies(ctx, rel, "\n".join(t for _, t in body), "java-spring", own_names=(cls_name,))
                    c.fill_body_facts(rec, body, "java-spring", ctx.types, extra)
                    out.append(rec)
                i = end + 1
                continue
            if s and not s.startswith(("//", "*", "/*")):
                annos = []
            i += 1


def _spring_params(sig_params, placeholders, ctx):
    params, req_types, body_type, has_body = [], [], None, False
    for a in c.split_args(sig_params):
        am = re.findall(r"@(\w+)(?:\(([^)]*)\))?", a)
        bare = re.sub(r"@\w+(?:\([^)]*\))?", "", a).strip()
        bare = re.sub(r"^final\s+", "", bare)
        kt = re.match(r"(\w+)\s*:\s*([\w<>?,. ]+)", bare)
        pm = re.match(r"([\w<>\[\],.?]+)\s+(\w+)$", bare)
        if kt:
            name, typ = kt.group(1), kt.group(2).strip()
        elif pm:
            typ, name = pm.group(1), pm.group(2)
        else:
            continue
        kinds = {k for k, _ in am}
        if kinds & {"AuthenticationPrincipal", "CurrentUser"} or re.search(r"Principal|Authentication|HttpServletRe|Pageable|BindingResult|Model$", typ):
            if "Pageable" in typ:
                params.append(c.make_param("page", "query", "Pageable"))
            continue
        explicit = next((v for k, v in am if k in ("PathVariable", "RequestParam", "RequestHeader")), "")
        nm = re.search(r"\"([^\"]+)\"", explicit or "")
        pname = nm.group(1) if nm else name
        if "RequestBody" in kinds:
            where, has_body = "body", True
        elif "PathVariable" in kinds or name in placeholders:
            where = "route"
        elif "RequestHeader" in kinds:
            where = "header"
        else:
            where = "query"
        params.append(c.make_param(pname, where, typ))
        for t in c.type_names(typ):
            if t in ctx.types and t not in req_types:
                req_types.append(t)
                if where == "body":
                    body_type = body_type or t
                    params += c.body_params_from_type(t, ctx.types)
    return c.dedupe_params(params), req_types, body_type, has_body


# ============================================================================ Node (Express, NestJS, Fastify, Next.js)
AUTH_MW = re.compile(r"auth|authenticate|passport|jwt|protect|requireLogin|ensureLogged|isAuthenticated|verifyToken|checkAuth|requireUser", re.I)
ROLE_MW = re.compile(r"(role|admin|permit|authorize|can|allow|hasRole|restrictTo|requireRole|permission)\w*\s*\(([^)]*)\)", re.I)
ANON_MW = re.compile(r"\bpublic\w*|noAuth|skipAuth|anonymous|optionalAuth", re.I)
NODE_EXT = (".js", ".ts", ".mjs", ".cjs")


def _resolve_import(ctx, from_rel, spec):
    if not spec.startswith("."):
        return None
    base = os.path.normpath(os.path.join(os.path.dirname(from_rel), spec)).replace(os.sep, "/")
    for cand in (base, *(base + e for e in NODE_EXT), *(base + "/index" + e for e in NODE_EXT)):
        if cand in ctx.text_by_rel:
            return cand
    stem = re.sub(r"\.(js|ts|mjs|cjs)$", "", base)
    for e in NODE_EXT:
        if stem + e in ctx.text_by_rel:
            return stem + e
    return None


def _node_mounts(ctx, files):
    """{child_file: (prefix, [(line, mw_text, parent_file)])} resolved through import statements, nested once or more."""
    edges = []
    for rel, text in files:
        imports = {}
        for m in re.finditer(r"import\s+(?:(\w+)\s*,?\s*)?(?:\{([^}]*)\})?\s*from\s*['\"]([^'\"]+)['\"]", text):
            names = ([m.group(1)] if m.group(1) else []) + [n.split(" as ")[-1].strip() for n in (m.group(2) or "").split(",") if n.strip()]
            for n in names:
                imports[n] = m.group(3)
        for m in re.finditer(r"(?:const|let|var)\s+(?:(\w+)|\{([^}]*)\})\s*=\s*require\(\s*['\"]([^'\"]+)['\"]\s*\)", text):
            for n in ([m.group(1)] if m.group(1) else [x.split(":")[-1].strip() for x in (m.group(2) or "").split(",")]):
                imports[n] = m.group(3)
        for m in re.finditer(r"\b(\w+)\.(?:use|register)\(\s*", text):
            open_pos = text.find("(", m.start())
            args = c.split_args(text[open_pos + 1:c.balanced_span(text, open_pos) - 1])
            if not args:
                continue
            prefix, rest = "", args
            if re.match(r"^['\"`]", args[0]):
                prefix, rest = args[0].strip("'\"`"), args[1:]
            if m.group(0).startswith(m.group(1) + ".register"):
                opt = next((a for a in args if "prefix" in a), "")
                pm = re.search(r"prefix\s*:\s*['\"`]([^'\"`]+)", opt)
                prefix = pm.group(1) if pm else ""
                rest = args[:1]
            if not rest:
                continue
            target = rest[-1]
            rq = re.match(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)", target)
            spec = rq.group(1) if rq else imports.get(re.sub(r"\.default$", "", target))
            child = _resolve_import(ctx, rel, spec) if spec else None
            if child:
                edges.append((rel, prefix, child, [(c.line_of(text, m.start()), x) for x in rest[:-1]]))
    mounts = {}
    for _ in range(6):
        changed = False
        for parent, prefix, child, mws in edges:
            p_prefix, p_mws = mounts.get(parent, ("", []))
            val = (c.join_path(p_prefix, prefix) if (p_prefix or prefix) else "", p_mws + [(ln, mw, parent) for ln, mw in mws])
            if mounts.get(child) != val and child not in [e[0] for e in edges if e[2] == child and e[0] == child]:
                if child not in mounts or len(val[0]) > len(mounts[child][0]):
                    mounts[child] = val
                    changed = True
        if not changed:
            break
    return mounts


def _node_params_from_body(text, placeholders):
    params = [c.make_param(p, "route") for p in placeholders]
    for m in re.finditer(r"\b(?:req|request|ctx\.request)\.(query|body|params|headers)\.(\w+)", text):
        params.append(c.make_param(m.group(2), {"params": "route", "headers": "header"}.get(m.group(1), m.group(1))))
    for m in re.finditer(r"\b(?:req|request)\.(query|body|params|headers)\[\s*['\"]([^'\"]+)['\"]\s*\]", text):
        params.append(c.make_param(m.group(2), {"params": "route", "headers": "header"}.get(m.group(1), m.group(1))))
    for m in re.finditer(r"(?:const|let|var)\s*\{([^}]*)\}\s*=\s*(?:req|request)\.(query|body|params)", text):
        for n in m.group(1).split(","):
            n = n.split(":")[0].split("=")[0].strip()
            if n:
                params.append(c.make_param(n, {"params": "route"}.get(m.group(2), m.group(2))))
    return c.dedupe_params(params)


def scan_node(ctx, out):
    files = [(r, t) for r, t in ctx.files("node-express", NODE_EXT) if not re.search(r"\.(spec|test)\.[cm]?[jt]s$", r)]
    mounts = _node_mounts(ctx, files)
    global_prefix = ""
    app_guard = None
    for rel, text in files:
        gm = re.search(r"setGlobalPrefix\(\s*['\"]([^'\"]+)['\"]", text)
        if gm:
            global_prefix = gm.group(1)
        am = re.search(r"provide\s*:\s*APP_GUARD", text)
        if am:
            app_guard = (rel, c.line_of(text, am.start()))
    for rel, text in files:
        lines = text.splitlines()
        prefix, mount_mws = mounts.get(rel, ("", []))
        router_auth = None
        route_rx = re.compile(r"\b(\w*[Rr]outer|app|server|fastify|api|routes?)\s*\.\s*(get|post|put|delete|patch|all|options|head)\s*\(\s*(['\"`])([^'\"`]+)\3")
        for m in re.finditer(r"\b(\w*[Rr]outer|app)\s*\.\s*use\(\s*([^'\"`\s][^)]*)\)", text):
            if AUTH_MW.search(m.group(2)):
                router_auth = (c.line_of(text, m.start()), m.group(0), m.start())
                break
        found = list(route_rx.finditer(text))
        for m in re.finditer(r"\b(\w+)\s*\.\s*route\(\s*['\"`]([^'\"`]+)['\"`]\s*\)", text):
            end = c.statement_end(text, m.start())
            chain = text[m.end():end]
            for vm in re.finditer(r"\.\s*(get|post|put|delete|patch|all)\s*\(", chain):
                found.append(("chain", m, vm, chain))
        for item in found:
            if isinstance(item, tuple):
                _, m, vm, chain = item
                verb, tmpl = vm.group(1).upper(), m.group(2)
                open_pos = m.end() + vm.end() - 1
                start = m.start()
            else:
                m = item
                verb, tmpl = m.group(2).upper(), m.group(4)
                open_pos = text.find("(", m.start() + len(m.group(1)))
                start = m.start()
            close = c.balanced_span(text, open_pos)
            args = c.split_args(text[open_pos + 1:close - 1])
            if not isinstance(item, tuple):
                args = args[1:]
            handler = args[-1] if args else ""
            mws = args[:-1]
            line = c.line_of(text, start)
            raw = c.join_path(prefix, tmpl)
            path = c.norm_path(raw)
            body_text = text[start:close]
            body = c.numbered(body_text.splitlines(), line - 1)
            symbol = "inline handler"
            extra = []
            if re.fullmatch(r"[\w.]+", handler.strip() or "-"):
                symbol = handler.strip()
                cand, fbody = resolve_named_function(ctx, symbol.split(".")[-1])
                if cand:
                    body = body + fbody
                    body_text += "\n" + "\n".join(t for _, t in fbody)
            framework = "fastify" if m.group(1) in ("fastify", "server") else "express"
            rec = c.new_record(kind="http", stack="node-express", framework=framework, method="ANY" if verb == "ALL" else verb,
                               path=path, path_raw=raw, file=rel, line=line, handler_line=line, symbol=symbol, handler=symbol)
            mw_text = ", ".join(mws)
            a = rec["auth"]
            for rmw in ROLE_MW.finditer(mw_text):
                a["roles"] += [r.strip(" '\"`") for r in rmw.group(2).split(",") if r.strip()]
            mount_auth = [(ln, mw) for ln, mw, _ in mount_mws if AUTH_MW.search(mw)]
            if ANON_MW.search(mw_text):
                a.update(required="no", source="explicit-anonymous", anonymous_marker=ANON_MW.search(mw_text).group(0),
                         evidence=[c.auth_ev(line, mw_text)])
            elif AUTH_MW.search(mw_text):
                a.update(required="yes", source="route middleware", evidence=[c.auth_ev(line, mw_text)])
            elif router_auth and router_auth[2] < start:
                a.update(required="yes", source=f"router.use ({router_auth[1][:60]})", evidence=[c.auth_ev(router_auth[0], router_auth[1])])
            elif mount_auth:
                a.update(required="yes", source="mount middleware", evidence=[c.auth_ev(*mount_auth[0])])
            else:
                a.update(required="no", source="none")
            rec["params"] = _node_params_from_body(body_text, c.route_placeholders(raw))
            rec["id_params"] = c.id_params_for(path)
            has_body = verb in c.BODY_METHODS or bool(re.search(r"\breq\.body\b", body_text))
            rec["request"] = {"types": [], "has_body": has_body, "body_type": None, "body_type_named_as_dto": None}
            _version_fact(rec)
            extra = callee_bodies(ctx, rel, body_text, "node-express")
            c.fill_body_facts(rec, body, "node-express", ctx.types, extra)
            out.append(rec)
        for m in re.finditer(r"\b(?:fastify|server|app)\s*\.\s*route\(\s*\{", text):
            open_pos = text.find("{", m.start())
            obj = text[open_pos:c.balanced_span(text, open_pos)]
            mm = re.search(r"method\s*:\s*\[?\s*['\"](\w+)['\"]", obj)
            um = re.search(r"url\s*:\s*['\"]([^'\"]+)['\"]", obj)
            if not um:
                continue
            line = c.line_of(text, m.start())
            raw = c.join_path(prefix, um.group(1))
            rec = c.new_record(kind="http", stack="node-express", framework="fastify", method=(mm.group(1).upper() if mm else "ANY"),
                               path=c.norm_path(raw), path_raw=raw, file=rel, line=line, handler_line=line, symbol="route handler",
                               handler="route handler")
            pre = re.search(r"(preHandler|onRequest|preValidation)\s*:\s*([^\n]+)", obj)
            if pre and AUTH_MW.search(pre.group(2)):
                rec["auth"].update(required="yes", source="route hook", evidence=[c.auth_ev(line, pre.group(0))])
            else:
                rec["auth"].update(required="no", source="none")
            rec["params"] = _node_params_from_body(obj, c.route_placeholders(raw))
            rec["id_params"] = c.id_params_for(rec["path"])
            rec["request"]["has_body"] = rec["method"] in c.BODY_METHODS
            if re.search(r"schema\s*:", obj):
                rec["validation"]["evidence"].append("schema:")
            c.fill_body_facts(rec, c.numbered(obj.splitlines(), line - 1), "node-express", ctx.types)
            out.append(rec)
        if "@Controller(" in text:
            _nest(ctx, rel, text, lines, global_prefix, app_guard, out)
        if os.path.basename(rel) in ("route.ts", "route.js") and "/app/" in "/" + rel:
            route = "/" + rel.split("app/", 1)[-1].rsplit("/", 1)[0]
            route = re.sub(r"/\([^)]*\)", "", route)
            for m in re.finditer(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\b", text):
                i = c.line_of(text, m.start()) - 1
                end = c.brace_body_end(lines, i)
                body = c.numbered(lines[i:end + 1], i)
                rec = c.new_record(kind="http", stack="node-express", framework="nextjs-route", method=m.group(1), path=c.norm_path(route),
                                   path_raw=route, file=rel, line=i + 1, handler_line=i + 1, symbol=m.group(1), handler=m.group(1))
                btxt = "\n".join(t for _, t in body)
                auth = re.search(r"getServerSession|auth\(\)|getToken|currentUser|clerk|verify", btxt)
                rec["auth"].update(required="yes" if auth else "no", source="handler call" if auth else "none",
                                   evidence=[c.auth_ev(i + 1, auth.group(0))] if auth else [])
                rec["params"] = [c.make_param(p, "route") for p in c.route_placeholders(route)]
                rec["id_params"] = c.id_params_for(rec["path"])
                rec["request"]["has_body"] = m.group(1) in c.BODY_METHODS
                c.fill_body_facts(rec, body, "node-express", ctx.types)
                out.append(rec)


def _nest(ctx, rel, text, lines, global_prefix, app_guard, out):
    cm = re.search(r"@Controller\(\s*(?:['\"]([^'\"]*)['\"]|\{[^}]*path\s*:\s*['\"]([^'\"]*)['\"][^}]*\})?", text)
    cls_route = (cm.group(1) or cm.group(2) or "") if cm else ""
    head = text[:text.find("export class")] if "export class" in text else text[:cm.end()] if cm else ""
    cls_guards = re.search(r"@UseGuards\(([^)]*)\)", head)
    cls_public = re.search(r"@(Public|SkipAuth|AllowAnonymous)\(", head)
    cls_roles = re.findall(r"@Roles\(([^)]*)\)", head)
    cls_version = re.search(r"version\s*:\s*['\"]([^'\"]+)['\"]|@Version\(\s*['\"]([^'\"]+)", head)
    cls_name_m = re.search(r"export\s+class\s+(\w+)", text)
    cls_name = cls_name_m.group(1) if cls_name_m else None
    decos = []
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("@") and "class " not in s:
            decos.append((i + 1, s))
            continue
        mm = re.match(r"^\s*(?:public\s+|private\s+|protected\s+)?(?:async\s+)?(\w+)\s*\(", line)
        if mm and mm.group(1) not in KEYWORDS and any(re.search(r"@(Get|Post|Put|Delete|Patch|All|Options|Head)\(", d) for _, d in decos):
            md, decos = decos, []
            name = mm.group(1)
            sig, j = line, i
            while sig.count("(") > sig.count(")") and j + 1 < len(lines) and j < i + 15:
                j += 1
                sig += " " + lines[j].strip()
            ps = sig.find("(", sig.find(name) + len(name))
            close = c.balanced_span(sig, ps)
            sig_params = sig[ps + 1:close - 1]
            rt = re.match(r"\s*:\s*([^{]+)", sig[close:])
            rtype = rt.group(1).strip() if rt else ""
            end = c.brace_body_end(lines, i)
            body = c.numbered(lines[i:end + 1], i)
            for no, d in md:
                vm = re.search(r"@(Get|Post|Put|Delete|Patch|All|Options|Head)\((?:\s*['\"]([^'\"]*)['\"])?", d)
                if not vm:
                    continue
                verb = "ANY" if vm.group(1) == "All" else vm.group(1).upper()
                raw = c.join_path(global_prefix, cls_route, vm.group(2) or "")
                path = c.norm_path(raw)
                rec = c.new_record(kind="http", stack="node-express", framework="nestjs", method=verb, path=path, path_raw=raw, file=rel,
                                   line=no, handler_line=i + 1, symbol=f"{cls_name}.{name}" if cls_name else name, handler=name)
                rec["class"] = cls_name
                guards = [(n, d2) for n, d2 in md if "@UseGuards" in d2]
                public = next(((n, d2) for n, d2 in md if re.search(r"@(Public|SkipAuth|AllowAnonymous)\(", d2)), None)
                roles = [r for d2 in [d3 for _, d3 in md] for grp in re.findall(r"@Roles\(([^)]*)\)", d2) for r in grp.split(",")]
                roles += [r for grp in cls_roles for r in grp.split(",")]
                a = rec["auth"]
                a["roles"] = [r.strip(" '\"`") for r in roles if r.strip(" '\"`")]
                a["policies"] = [g for _, d2 in guards for g in re.findall(r"@UseGuards\(([^)]*)\)", d2)]
                if public or cls_public:
                    a.update(required="no", source="explicit-anonymous", anonymous_marker="@Public()",
                             evidence=[c.auth_ev(*public)] if public else [])
                elif guards:
                    a.update(required="yes", source="method guard", evidence=[c.auth_ev(*guards[0])])
                elif cls_guards:
                    a.update(required="yes", source="class guard", evidence=[{"line": c.line_of(text, cls_guards.start()), "text": cls_guards.group(0)}])
                elif app_guard:
                    a.update(required="yes", source="global APP_GUARD", evidence=[{"line": app_guard[1], "text": app_guard[0]}])
                else:
                    a.update(required="unknown", source="none (check APP_GUARD)")
                params, req_types, body_type, has_body = [], [], None, False
                for arg in c.split_args(sig_params):
                    dm = re.match(r"@(Param|Query|Body|Headers|Req|Request|User|CurrentUser)\(\s*(?:['\"]([^'\"]+)['\"])?[^)]*\)\s*(\w+)\s*[?]?\s*(?::\s*(.+))?", arg.strip())
                    if not dm:
                        continue
                    kind, pname, var, typ = dm.group(1), dm.group(2), dm.group(3), (dm.group(4) or "").strip()
                    if kind in ("Req", "Request", "User", "CurrentUser"):
                        continue
                    where = {"Param": "route", "Query": "query", "Body": "body", "Headers": "header"}[kind]
                    if where == "body":
                        has_body = True
                    params.append(c.make_param(pname or var, where, typ))
                    for t in c.type_names(typ):
                        if t in ctx.types and t not in req_types:
                            req_types.append(t)
                            params += [dict(p, **{"in": where}) for p in c.body_params_from_type(t, ctx.types)]
                            if where == "body":
                                body_type = body_type or t
                rec["params"] = c.dedupe_params(params + [c.make_param(p, "route") for p in c.route_placeholders(raw)])
                rec["id_params"] = c.id_params_for(path)
                _set_body_request(rec, req_types, body_type, has_body)
                rec["response"]["type"] = rtype
                vmark = re.search(r"@Version\(", " ".join(d2 for _, d2 in md))
                _version_fact(rec, "version decorator" if (vmark or cls_version) else None)
                extra = callee_bodies(ctx, rel, "\n".join(t for _, t in body), "node-express", own_names=(cls_name,))
                c.fill_body_facts(rec, body, "node-express", ctx.types, extra)
                out.append(rec)
        elif s and not s.startswith("//"):
            decos = []


# ============================================================================ Python (Django, DRF, Flask, FastAPI)
DRF_ACTIONS = {"list": ("GET", False), "create": ("POST", False), "retrieve": ("GET", True), "update": ("PUT", True),
               "partial_update": ("PATCH", True), "destroy": ("DELETE", True)}
GENERIC_VIEWS = {"ListAPIView": ["GET"], "CreateAPIView": ["POST"], "RetrieveAPIView": ["GET"], "DestroyAPIView": ["DELETE"],
                 "UpdateAPIView": ["PUT", "PATCH"], "ListCreateAPIView": ["GET", "POST"],
                 "RetrieveUpdateAPIView": ["GET", "PUT", "PATCH"], "RetrieveDestroyAPIView": ["GET", "DELETE"],
                 "RetrieveUpdateDestroyAPIView": ["GET", "PUT", "PATCH", "DELETE"], "ListView": ["GET"], "DetailView": ["GET"],
                 "TemplateView": ["GET"], "CreateView": ["GET", "POST"], "UpdateView": ["GET", "POST"], "DeleteView": ["GET", "POST"],
                 "FormView": ["GET", "POST"]}
VIEWSET_ACTIONS = {"ModelViewSet": list(DRF_ACTIONS), "ReadOnlyModelViewSet": ["list", "retrieve"]}


def _py_module_file(ctx, dotted, from_rel=None):
    tail = dotted.replace(".", "/")
    for rel in ctx.text_by_rel:
        if rel.endswith(tail + ".py") or rel.endswith(tail + "/__init__.py"):
            return rel
    if from_rel and dotted.startswith("."):
        base = os.path.normpath(os.path.join(os.path.dirname(from_rel), dotted.lstrip(".").replace(".", "/") + ".py")).replace(os.sep, "/")
        if base in ctx.text_by_rel:
            return base
    return None


def _py_defs(ctx, files):
    """{name: (rel, line_index, kind)} for top-level classes and functions."""
    defs = {}
    for rel, text in files:
        for m in re.finditer(r"^(class|def|async def)\s+(\w+)", text, re.M):
            defs.setdefault(m.group(2), (rel, c.line_of(text, m.start()) - 1, m.group(1)))
    return defs


def _py_auth(seg_text, drf_default, rec, line_no):
    a = rec["auth"]
    perm = re.search(r"permission_classes\s*=\s*[\[(]([^\])]*)[\])]|@permission_classes\(\s*[\[(]([^\])]*)[\])]", seg_text)
    perms = (perm.group(1) or perm.group(2)) if perm else ""
    auth_m = re.search(r"login_required|LoginRequiredMixin|IsAuthenticated\w*|IsAdminUser|permission_required|PermissionRequiredMixin|"
                       r"jwt_required|auth\.login_required|Depends\(\s*(?:get_current\w*|require\w*|auth\w*|verify\w*)|"
                       r"Security\(|roles?_required", seg_text)
    a["roles"] = list(dict.fromkeys(re.findall(r"IsAdminUser", seg_text) +
                                    [r.strip(" '\"") for grp in re.findall(r"roles?_required\(([^)]*)\)", seg_text) for r in grp.split(",")]))
    a["policies"] = list(dict.fromkeys(re.findall(r"permission_required\(\s*['\"]([^'\"]+)", seg_text) +
                                       [p.strip() for p in perms.split(",") if p.strip() and p.strip() not in ("IsAuthenticated", "AllowAny")]))
    if "AllowAny" in perms or re.search(r"@(public|anonymous)\w*|authentication_classes\s*=\s*[\[(]\s*[\])]", seg_text, re.I):
        a.update(required="no", source="explicit-anonymous", anonymous_marker="AllowAny" if "AllowAny" in perms else "public",
                 evidence=[{"line": line_no, "text": (perm.group(0) if perm else "public")[:160]}])
    elif auth_m:
        a.update(required="yes", source="view decorator/mixin/dependency", evidence=[{"line": line_no, "text": auth_m.group(0)}])
    elif drf_default == "IsAuthenticated" and rec["framework"].startswith(("drf", "django")):
        a.update(required="yes", source="DRF default", evidence=[])
    elif drf_default is None and rec["framework"].startswith("drf"):
        a.update(required="unknown", source="DRF DEFAULT_PERMISSION_CLASSES not found")
    else:
        a.update(required="no", source="none")


def _py_params(text, placeholders, sig="", ctx=None):
    params = [c.make_param(p, "route") for p in placeholders]
    for m in re.finditer(r"request\.(GET|query_params|args)\.get\(\s*['\"]([^'\"]+)['\"]|request\.(GET|query_params|args)\[\s*['\"]([^'\"]+)['\"]", text):
        params.append(c.make_param(m.group(2) or m.group(4), "query"))
    for m in re.finditer(r"request\.(data|POST|json|form)\.get\(\s*['\"]([^'\"]+)['\"]|request\.(data|POST|json|form)\[\s*['\"]([^'\"]+)['\"]|"
                         r"get_json\(\)\s*(?:\.get\(\s*|\[\s*)['\"]([^'\"]+)['\"]", text):
        params.append(c.make_param(m.group(2) or m.group(4) or m.group(5), "body"))
    for m in re.finditer(r"request\.(?:headers|META)\.get\(\s*['\"]([^'\"]+)['\"]", text):
        params.append(c.make_param(m.group(1), "header"))
    req_types, body_type = [], None
    for a in c.split_args(sig):
        am = re.match(r"(\w+)\s*(?::\s*([^=]+))?(?:=\s*(.+))?$", a.strip())
        if not am or am.group(1) in ("self", "request", "cls", "db", "session", "background_tasks", "response"):
            continue
        name, typ, default = am.group(1), (am.group(2) or "").strip(), (am.group(3) or "").strip()
        if "Depends(" in default or "Security(" in default or re.search(r"Session|Request|BackgroundTasks|Response", typ):
            continue
        if name in placeholders:
            continue
        if default.startswith("Header("):
            where = "header"
        elif default.startswith(("Body(", "Form(", "File(")):
            where = "body"
        elif default.startswith(("Query(", "Path(")):
            where = "route" if default.startswith("Path(") else "query"
        elif ctx and typ.split("[")[0] in ctx.types and not typ.lower() in c.SIMPLE_TYPES:
            where = "body"
        else:
            where = "query"
        params.append(c.make_param(name, where, typ or None))
        if ctx and where == "body":
            for t in c.type_names(typ):
                if t in ctx.types:
                    req_types.append(t)
                    body_type = body_type or t
                    params += c.body_params_from_type(t, ctx.types)
    return c.dedupe_params(params), req_types, body_type


def scan_python(ctx, out):
    files = [(r, t) for r, t in ctx.files("python-django", (".py",)) if not re.search(r"(^|/)test_\w+\.py$|_tests?\.py$", r)]
    drf_default = None
    for rel, t in files:
        if "REST_FRAMEWORK" in t and "DEFAULT_PERMISSION_CLASSES" in t:
            drf_default = "IsAuthenticated" if "IsAuthenticated" in t else ("AllowAny" if "AllowAny" in t else "custom")
    defs = _py_defs(ctx, files)
    # Django include() prefixes: urls module file -> prefix
    include_prefix = {}
    router_prefix = {}
    for _ in range(3):
        for rel, t in files:
            own = include_prefix.get(rel, "")
            for m in re.finditer(r"(?:re_)?path\(\s*r?['\"]([^'\"]*)['\"]\s*,\s*include\(\s*(?:\(\s*)?['\"]?([\w.]+)['\"]?", t):
                target = m.group(2)
                if target.endswith(".urls") and target.split(".")[0] in ("router",):
                    router_prefix[(rel, target.split(".")[0])] = c.join_path(own, m.group(1))
                    continue
                if re.fullmatch(r"\w+\.urls", target) and re.search(r"\b" + target.split(".")[0] + r"\s*=\s*\w*Router\(", t):
                    router_prefix[(rel, target.split(".")[0])] = c.join_path(own, m.group(1))
                    continue
                f = _py_module_file(ctx, target, rel)
                if f:
                    include_prefix[f] = c.join_path(own, m.group(1))
    for rel, text in files:
        lines = text.splitlines()
        own_prefix = include_prefix.get(rel, "")
        # Django path()/re_path()
        for m in re.finditer(r"(?:re_)?path\(\s*r?['\"]([^'\"]*)['\"]\s*,\s*([\w.]+)(\.as_view\(\))?(?:\s*\.as_asgi\(\))?", text):
            if m.group(2) == "include":
                continue
            view = m.group(2).split(".")[-1]
            raw = c.join_path(own_prefix, m.group(1))
            if "websocket" in text[:m.start()].rsplit("=", 1)[0][-80:] or ".as_asgi()" in text[m.start():m.start() + 200].split("\n")[0]:
                line = c.line_of(text, m.start())
                rec = c.new_record(kind="websocket", stack="python-django", framework="django-channels", method="WS", path=c.norm_path(raw),
                                   path_raw=raw, file=rel, line=line, handler_line=line, symbol=view, handler=view)
                rec["auth"].update(required="unknown", source="check AuthMiddlewareStack in asgi.py")
                out.append(rec)
                continue
            _django_view_records(ctx, rel, text, m, view, raw, defs, drf_default, out)
        # DRF routers
        for m in re.finditer(r"(\w+)\.register\(\s*r?['\"]([^'\"]*)['\"]\s*,\s*([\w.]+)", text):
            prefix = router_prefix.get((rel, m.group(1)), own_prefix)
            vs = m.group(3).split(".")[-1]
            vf, vi, _ = defs.get(vs, (rel, None, None))
            vtext = ctx.text_by_rel.get(vf, "")
            vlines = vtext.splitlines()
            if vi is None:
                continue
            vend = c.indent_body_end(vlines, vi)
            seg = "\n".join(vlines[vi:vend + 1])
            bases = re.match(r"class\s+\w+\s*\(([^)]*)\)", vlines[vi])
            base_names = bases.group(1) if bases else ""
            actions = [a for a in DRF_ACTIONS if re.search(r"^\s{4}def\s+" + a + r"\s*\(", seg, re.M)]
            for bn, acts in VIEWSET_ACTIONS.items():
                if bn in base_names:
                    actions = list(dict.fromkeys(actions + acts))
            for mixin, act in (("ListModelMixin", "list"), ("CreateModelMixin", "create"), ("RetrieveModelMixin", "retrieve"),
                               ("UpdateModelMixin", "update"), ("DestroyModelMixin", "destroy")):
                if mixin in base_names and act not in actions:
                    actions.append(act)
            for act in actions:
                verb, detail = DRF_ACTIONS[act]
                raw = c.join_path(prefix, m.group(2), "{pk}" if detail else "") + "/"
                am = re.search(r"^\s{4}def\s+" + act + r"\s*\(", seg, re.M)
                start = vi + (seg[:am.start()].count("\n") if am else 0)
                end = c.indent_body_end(vlines, start) if am else vend
                _py_record(ctx, rec_args=dict(kind="http", stack="python-django", framework="drf-viewset", method=verb, path=c.norm_path(raw),
                                              path_raw=raw, file=vf, line=c.line_of(text, m.start()), handler_line=start + 1,
                                              symbol=f"{vs}.{act}", handler=act),
                           cls=vs, seg=seg, body=c.numbered(vlines[start:end + 1], start), drf_default=drf_default, out=out,
                           route_file=rel)
            for am in re.finditer(r"@action\(([^)]*)\)\s*\n\s*def\s+(\w+)", seg):
                methods = re.findall(r"['\"](\w+)['\"]", re.search(r"methods\s*=\s*\[([^\]]*)\]", am.group(1)).group(1)) \
                    if "methods" in am.group(1) else ["get"]
                detail = "detail=True" in am.group(1).replace(" ", "")
                upm = re.search(r"url_path\s*=\s*['\"]([^'\"]+)", am.group(1))
                start = vi + seg[:am.start()].count("\n")
                end = c.indent_body_end(vlines, start + 1)
                for meth in methods:
                    raw = c.join_path(prefix, m.group(2), "{pk}" if detail else "", upm.group(1) if upm else am.group(2)) + "/"
                    _py_record(ctx, rec_args=dict(kind="http", stack="python-django", framework="drf-viewset-action", method=meth.upper(),
                                                  path=c.norm_path(raw), path_raw=raw, file=vf, line=c.line_of(text, m.start()),
                                                  handler_line=start + 1, symbol=f"{vs}.{am.group(2)}", handler=am.group(2)),
                               cls=vs, seg=seg + "\n" + am.group(0), body=c.numbered(vlines[start:end + 1], start),
                               drf_default=drf_default, out=out, route_file=rel)
        # Flask / FastAPI decorators
        prefix_m = re.search(r"APIRouter\([^)]*prefix\s*=\s*['\"]([^'\"]+)['\"]|Blueprint\([^)]*url_prefix\s*=\s*['\"]([^'\"]+)['\"]", text)
        file_prefix = (prefix_m.group(1) or prefix_m.group(2)) if prefix_m else ""
        mount_prefix = ctx.py_mounts.get(rel, "")
        decos = []
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith("@"):
                decos.append((i + 1, s))
                continue
            dm = re.match(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(", line)
            if dm and decos:
                rt = None
                for no, d in decos:
                    rt = re.search(r"@\w+\.(route|get|post|put|delete|patch|websocket|api_route)\(\s*['\"]([^'\"]*)['\"](.*)", d)
                    if rt:
                        rt_line = no
                        break
                if rt:
                    sig, j = line, i
                    while sig.count("(") > sig.count(")") and j + 1 < len(lines) and j < i + 20:
                        j += 1
                        sig += " " + lines[j].strip()
                    ps = sig.find("(")
                    sig_params = sig[ps + 1:c.balanced_span(sig, ps) - 1]
                    rtm = re.search(r"\)\s*->\s*([^:]+):", sig)
                    verb = rt.group(1).upper()
                    methods = [verb]
                    if verb in ("ROUTE", "API_ROUTE"):
                        mv = re.search(r"methods\s*=\s*[\[(]([^\])]*)[\])]", rt.group(3))
                        methods = [x.upper() for x in re.findall(r"['\"](\w+)['\"]", mv.group(1))] if mv else ["GET"]
                    end = c.indent_body_end(lines, i)
                    body = c.numbered(lines[i:end + 1], i)
                    is_fastapi = "fastapi" in text.lower() or "APIRouter" in text
                    raw = c.join_path(mount_prefix, file_prefix, rt.group(2))
                    dtext = " ".join(d for _, d in decos) + " " + sig
                    rm = re.search(r"response_model\s*=\s*([\w\[\]., ]+)", rt.group(3))
                    for verb_u in methods:
                        kind = "websocket" if verb_u == "WEBSOCKET" else "http"
                        rec = c.new_record(kind=kind, stack="python-django", framework="fastapi" if is_fastapi else "flask",
                                           method="WS" if kind == "websocket" else verb_u, path=c.norm_path(raw), path_raw=raw, file=rel,
                                           line=rt_line, handler_line=i + 1, symbol=dm.group(1), handler=dm.group(1))
                        _py_auth(dtext, None, rec, rt_line)
                        if ctx.py_mount_auth.get(rel) and rec["auth"]["required"] == "no" and rec["auth"]["source"] == "none":
                            rec["auth"].update(required="yes", source="router dependencies", evidence=[ctx.py_mount_auth[rel]])
                        btxt = "\n".join(t for _, t in body)
                        params, req_types, body_type = _py_params(btxt, c.route_placeholders(raw), sig_params if is_fastapi else "", ctx)
                        rec["params"], rec["id_params"] = params, c.id_params_for(rec["path"])
                        has_body = bool(body_type) or bool(re.search(r"request\.(json|form|data)|get_json\(", btxt))
                        _set_body_request(rec, req_types, body_type or ("json" if has_body else None), has_body)
                        rec["response"]["type"] = (rm.group(1).strip() if rm else (rtm.group(1).strip() if rtm else None))
                        _version_fact(rec)
                        extra = callee_bodies(ctx, rel, btxt, "python-django")
                        c.fill_body_facts(rec, body, "python-django", ctx.types, extra)
                        out.append(rec)
                decos = []
            elif s and not s.startswith("#"):
                decos = []


def _django_view_records(ctx, rel, text, m, view, raw, defs, drf_default, out):
    vf, vi, kind = defs.get(view, (rel, None, None))
    line = c.line_of(text, m.start())
    if vi is None:
        rec = c.new_record(kind="http", stack="python-django", framework="django-url", method="ANY", path=c.norm_path(raw), path_raw=raw,
                           file=rel, line=line, handler_line=None, symbol=view, handler=view)
        rec["auth"].update(required="unknown", source="view not found")
        rec["params"] = [c.make_param(p, "route") for p in c.route_placeholders(raw)]
        rec["id_params"] = c.id_params_for(rec["path"])
        out.append(rec)
        return
    vlines = ctx.lines(vf)
    vend = c.indent_body_end(vlines, vi)
    pre = "\n".join(vlines[max(0, vi - 6):vi])
    seg = pre + "\n" + "\n".join(vlines[vi:vend + 1])
    if kind == "class":
        bases = re.match(r"class\s+\w+\s*\(([^)]*)\)", vlines[vi])
        base_names = bases.group(1) if bases else ""
        framework = "drf-apiview" if re.search(r"APIView|GenericAPIView|ViewSet|\w+APIView", base_names) else "django-cbv"
        methods = []
        for hm in re.finditer(r"^\s{4}(?:async\s+)?def\s+(get|post|put|patch|delete)\s*\(", "\n".join(vlines[vi:vend + 1]), re.M):
            methods.append((hm.group(1).upper(), vi + "\n".join(vlines[vi:vend + 1])[:hm.start()].count("\n")))
        if not methods:
            gv = next((v for g, v in GENERIC_VIEWS.items() if re.search(r"\b" + g + r"\b", base_names)), None)
            methods = [(x, vi) for x in (gv or ["ANY"])]
        for verb, start in methods:
            end = c.indent_body_end(vlines, start) if start != vi else vend
            _py_record(ctx, dict(kind="http", stack="python-django", framework=framework, method=verb, path=c.norm_path(raw), path_raw=raw,
                                 file=vf, line=line, handler_line=start + 1, symbol=f"{view}.{verb.lower()}" if start != vi else view,
                                 handler=verb.lower() if start != vi else view),
                       cls=view, seg=seg, body=c.numbered(vlines[start:end + 1], start), drf_default=drf_default, out=out, route_file=rel)
    else:
        av = re.search(r"@api_view\(\s*\[([^\]]*)\]", pre)
        hm = re.search(r"@require_http_methods\(\s*\[([^\]]*)\]|@require_(GET|POST|safe)\b", pre)
        framework = "drf-api-view" if av else "django-fbv"
        if av:
            methods = [x.upper() for x in re.findall(r"['\"](\w+)['\"]", av.group(1))]
        elif hm:
            methods = [x.upper() for x in re.findall(r"['\"](\w+)['\"]", hm.group(1) or "")] or [("GET" if hm.group(2) == "safe" else hm.group(2))]
        else:
            methods = ["ANY"]
        for verb in methods:
            _py_record(ctx, dict(kind="http", stack="python-django", framework=framework, method=verb, path=c.norm_path(raw), path_raw=raw,
                                 file=vf, line=line, handler_line=vi + 1, symbol=view, handler=view),
                       cls=None, seg=seg, body=c.numbered(vlines[vi:vend + 1], vi), drf_default=drf_default, out=out, route_file=rel)


def _py_record(ctx, rec_args, cls, seg, body, drf_default, out, route_file):
    rec = c.new_record(**rec_args)
    rec["class"] = cls
    if route_file != rec["file"]:
        rec["route_location"] = {"file": route_file, "line": rec["line"]}
        rec["line"] = rec["handler_line"] or rec["line"]
    _py_auth(seg, drf_default, rec, rec["handler_line"] or rec["line"])
    btxt = "\n".join(t for _, t in body)
    sm = re.search(r"serializer_class\s*=\s*(\w+)|(\w+Serializer)\(", seg)
    ser = (sm.group(1) or sm.group(2)) if sm else None
    params, req_types, body_type = _py_params(btxt, c.route_placeholders(rec["path_raw"]), "", ctx)
    has_body = rec["method"] in c.BODY_METHODS or bool(re.search(r"request\.(data|POST)", btxt))
    if ser and ser in ctx.types:
        req_types.append(ser)
        if has_body:
            params += c.body_params_from_type(ser, ctx.types)
            body_type = ser
    rec["params"], rec["id_params"] = c.dedupe_params(params), c.id_params_for(rec["path"])
    _set_body_request(rec, req_types, body_type, has_body)
    if ser:
        rec["response"]["type"] = ser + ("(many=True)" if re.search(r"many\s*=\s*True", btxt) else "")
    _version_fact(rec)
    extra = callee_bodies(ctx, rec["file"], btxt, "python-django", own_names=(cls,))
    full = body if "pagination_class" not in seg else body + [(0, ln) for ln in seg.splitlines() if "pagination_class" in ln]
    c.fill_body_facts(rec, full, "python-django", ctx.types, extra)
    out.append(rec)


SCANNERS = {"dotnet": scan_dotnet, "java-spring": scan_java_spring, "node-express": scan_node, "python-django": scan_python}
