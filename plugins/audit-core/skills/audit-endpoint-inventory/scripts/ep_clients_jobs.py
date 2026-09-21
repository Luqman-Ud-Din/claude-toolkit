#!/usr/bin/env python3
"""Client-route and background-job extractors for inventory_endpoints.py.

Client routes: Angular route tables, React Router (JSX and object routes), Vue Router.
Background jobs: Hangfire (RecurringJob/BackgroundJob), .NET hosted services and
Quartz jobs, job/worker classes by name, Spring @Scheduled and message listeners,
node-cron/cron/NestJS @Cron, BullMQ/Bull workers, Agenda, Celery tasks and beat
schedules, APScheduler, schedule, and Kubernetes CronJob manifests.

Usage (module):
    import ep_clients_jobs as cj
    cj.scan_client_routes(ctx, "angular", out)
    cj.scan_jobs(ctx, ["dotnet"], out)

Records only; a client guard is recorded as a client guard, and a job's identity
context is recorded as seen or not seen. Read-only.
"""
import os
import re

import ep_common as c

JOB_CONTEXT = re.compile(c.CALLER_IDENTITY.pattern + "|" + c.OWNER_KEY.pattern + r"|\btenant\w*|CustomConnectionString|DbName\s*=", re.I)


# ============================================================================ client routes
def _route_objects(text):
    """[(start, end, path)] for every `{ path: '...' }` object literal."""
    objs = []
    for m in re.finditer(r"\{\s*path\s*:\s*(['\"`])(.*?)\1", text, re.S):
        end = c.balanced_span(text, m.start())
        objs.append((m.start(), end, m.group(2)))
    return objs


def _own_text(text, obj, objs):
    s, e, _ = obj
    own = text[s:e]
    for cs, ce, _ in sorted(objs, reverse=True):
        if s < cs and ce <= e:
            own = own[:cs - s] + " " * (ce - cs) + own[ce - s:]
    return own


def _parent(obj, objs):
    s, e, _ = obj
    enclosing = [o for o in objs if o[0] < s and e <= o[1]]
    return min(enclosing, key=lambda o: o[1] - o[0]) if enclosing else None


def scan_client_routes(ctx, stack, out):
    exts = (".ts", ".tsx", ".js", ".jsx", ".mjs")
    for rel, text in ctx.files(stack, exts):
        if re.search(r"\.(spec|test|stories)\.[jt]sx?$", rel):
            continue
        if stack == "angular" and re.search(r"path\s*:\s*['\"]", text) and \
                re.search(r"\bRoutes\b|RouterModule|provideRouter|loadChildren|loadComponent", text):
            _object_routes(rel, text, stack, "angular-router", out)
        elif stack == "vue" and re.search(r"path\s*:\s*['\"]", text) and re.search(r"createRouter|VueRouter|RouteRecordRaw|routes\s*[:=]", text):
            _object_routes(rel, text, stack, "vue-router", out)
        elif stack == "react":
            if re.search(r"<Route\b", text):
                _jsx_routes(rel, text, out)
            if re.search(r"createBrowserRouter|createHashRouter|createMemoryRouter|useRoutes|RouteObject", text) and \
                    re.search(r"path\s*:\s*['\"]", text):
                _object_routes(rel, text, stack, "react-router", out)


def _object_routes(rel, text, stack, framework, out):
    objs = _route_objects(text)
    full = {}
    global_guard = re.search(r"router\.beforeEach\(|router\.beforeResolve\(", text)
    for obj in sorted(objs, key=lambda o: o[0]):
        par = _parent(obj, objs)
        parent_path, parent_guards = full.get(par, ("", [])) if par else ("", [])
        own = _own_text(text, obj, objs)
        guards = []
        for gm in re.finditer(r"(can(?:Activate|Match|ActivateChild|Load|Deactivate))\s*:\s*\[([^\]]*)\]", own):
            guards += [f"{gm.group(1)}:{g.strip()}" for g in gm.group(2).split(",") if g.strip()]
        if re.search(r"beforeEnter\s*:", own):
            guards.append("beforeEnter")
        meta = re.search(r"requiresAuth\s*:\s*(true|false)", own)
        if meta:
            guards.append(f"meta.requiresAuth:{meta.group(1)}")
        if framework == "react-router":
            el = re.search(r"element\s*:\s*(<[^,}]*)", own)
            if el and re.search(r"RequireAuth|Private\w*|Protected\w*|AuthGuard|withAuth", el.group(1)):
                guards.append("element wrapper:" + re.search(r"RequireAuth|Private\w*|Protected\w*|AuthGuard|withAuth", el.group(1)).group(0))
        inherited = [g if g.startswith("inherited ") else "inherited " + g for g in parent_guards
                     if not g.startswith(("canDeactivate", "inherited canDeactivate"))]
        roles = []
        rm = re.search(r"roles?\s*:\s*\[([^\]]*)\]", own)
        if rm:
            roles = [r.strip(" '\"`") for r in rm.group(1).split(",") if r.strip(" '\"`")]
        path = c.join_path(parent_path, obj[2])
        full[obj] = (path, guards + inherited)
        target = re.search(r"(component|loadComponent|loadChildren|redirectTo|element|lazy)\s*:\s*([^,\n}]+)", own)
        line = c.line_of(text, obj[0])
        rec = c.new_record(kind="client-route", stack=stack, framework=framework, method="ROUTE", path=c.norm_path(path), path_raw=path,
                           file=rel, line=line, handler_line=line, symbol=(target.group(2).strip()[:80] if target else None),
                           handler=(target.group(1) if target else None))
        all_guards = guards + inherited
        if global_guard:
            all_guards.append("global router.beforeEach")
        rec["auth"].update(required="unknown", source=("client guard: " + ", ".join(all_guards)) if all_guards else "no client guard",
                           client_guards=all_guards, roles=roles,
                           evidence=[{"line": line, "text": g} for g in guards[:3]])
        rec["params"] = [c.make_param(p, "route") for p in c.route_placeholders(path)]
        rec["notes"].append("client-side route; guards here run in the browser, server enforcement is on the http records")
        out.append(rec)


def _jsx_tags(text):
    """Yield (start, attrs, selfclose, is_close) for <Route ...> and </Route>, braces in attributes respected."""
    for m in re.finditer(r"<Route\b|</Route\s*>", text):
        if m.group(0).startswith("</"):
            yield m.start(), "", False, True
            continue
        i, depth, n = m.end(), 0, len(text)
        while i < n:
            ch = text[i]
            if ch in "\"'`" and depth == 0:
                q = ch
                i += 1
                while i < n and text[i] != q:
                    i += 1
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif ch == ">" and depth == 0:
                break
            i += 1
        attrs = text[m.end():i]
        yield m.start(), attrs.rstrip().rstrip("/"), attrs.rstrip().endswith("/"), False


def _jsx_routes(rel, text, out):
    stack = []
    for pos, attrs, selfclose, is_close in _jsx_tags(text):
        if is_close:
            if stack:
                stack.pop()
            continue
        pm = re.search(r"path\s*=\s*(?:\{\s*)?['\"`]([^'\"`]*)['\"`]", attrs)
        idx = re.search(r"\bindex\b", attrs)
        own = pm.group(1) if pm else ("" if idx else None)
        parent_path, parent_guards = (stack[-1] if stack else ("", []))
        el = re.search(r"element\s*=\s*\{(.*)\}", attrs, re.S)
        guards = []
        if el and re.search(r"RequireAuth|Private\w*|Protected\w*|AuthGuard|withAuth", el.group(1)):
            guards.append("element wrapper:" + re.search(r"RequireAuth|Private\w*|Protected\w*|AuthGuard|withAuth", el.group(1)).group(0))
        around = text[max(0, pos - 200):pos]
        if re.search(r"<(RequireAuth|Private\w*|Protected\w*|AuthGuard)\b[^/]*>\s*$", around):
            guards.append("wrapping element")
        path = c.join_path(parent_path, own or "")
        inherited = ["inherited " + g if not g.startswith("inherited ") else g for g in parent_guards]
        if own is not None:
            line = c.line_of(text, pos)
            rec = c.new_record(kind="client-route", stack="react", framework="react-router", method="ROUTE", path=c.norm_path(path),
                               path_raw=path, file=rel, line=line, handler_line=line,
                               symbol=(el.group(1).strip()[:80] if el else None), handler="element" if el else None)
            allg = guards + inherited
            rec["auth"].update(required="unknown", source=("client guard: " + ", ".join(allg)) if allg else "no client guard",
                               client_guards=allg, evidence=[{"line": line, "text": g} for g in guards[:3]])
            rec["params"] = [c.make_param(p, "route") for p in c.route_placeholders(path)]
            rec["notes"].append("client-side route; guards here run in the browser, server enforcement is on the http records")
            out.append(rec)
        if not selfclose:
            stack.append((path, guards + inherited))


# ============================================================================ jobs
def _job_record(ctx, stack, framework, rel, text, pos, name, trigger, schedule=None, target=None, target_body=None, target_file=None,
                target_line=None, window=2500):
    line = c.line_of(text, pos)
    rec = c.new_record(kind="job", stack=stack, framework=framework, method="JOB", path=name or target or trigger, path_raw=name,
                       file=rel, line=line, handler_line=target_line or line, symbol=target or trigger, handler=target)
    if target and "." in target:
        rec["class"] = target.split(".")[0]
    rec["auth"].update(required="unknown", source="n/a (no HTTP auth)")
    lang = "python" if stack == "python-django" else "c"
    if target_body:
        src = [(no, c.strip_comment(t, lang)) for no, t in target_body]
    else:
        win = text[pos:pos + window]
        src = [(line + k, c.strip_comment(t, lang)) for k, t in enumerate(win.splitlines())]
    src = [(no, t) for no, t in src if not t.lstrip().startswith(("*", "/*", "#"))]
    ev = c.evidence(src, JOB_CONTEXT, 3)
    rec["job"] = {"trigger": trigger, "name": name, "schedule": schedule, "target": target, "target_file": target_file or rel,
                  "target_line": target_line or line, "identity_context": "yes" if ev else "no", "evidence": ev}
    body = target_body or [(line + k, t) for k, t in enumerate(text[pos:pos + window].splitlines())]
    c.fill_body_facts(rec, body, stack, ctx.types)
    rec["ownership"]["check"] = "n/a"
    return rec


def _method_body(ctx, cls, meth):
    for cand in ctx.methods.get(meth, []):
        if cls is None or cand["class"] == cls:
            lines = ctx.lines(cand["file"])
            return cand, c.numbered(lines[cand["start"]:cand["end"] + 1], cand["start"])
    return None, None


def scan_jobs(ctx, stacks, out):
    registered = set()
    if "dotnet" in stacks:
        for rel, text in ctx.files("dotnet", (".cs",)):
            for m in re.finditer(r"\b(RecurringJob\.AddOrUpdate|\w*[Rr]ecurringJob\w*\.AddOrUpdate|BackgroundJob\.(?:Enqueue|Schedule|ContinueJobWith)|"
                                 r"\w*[Bb]ackgroundJob\w*\.(?:Enqueue|Schedule))\s*(?:<\s*(\w+)\s*>)?\s*\(", text):
                open_pos = text.find("(", m.end() - 1)
                args = c.split_args(text[open_pos + 1:c.balanced_span(text, open_pos) - 1])
                name = next((a.strip('"') for a in args if re.fullmatch(r"\"[^\"]*\"", a.strip())), None)
                lam = next((a for a in args if "=>" in a), "")
                tm = re.search(r"=>\s*(?:await\s+)?(\w+)\.(\w+)\s*\(", lam)
                cls = m.group(2)
                meth = tm.group(2) if tm else None
                if not cls and tm:
                    cls = next((k for k, v in ctx.types.items() if tm.group(1).lower().lstrip("_") in k.lower()), None)
                sched = next((a for a in args[1:] if re.search(r"Cron\.|\"[\d*/ ,\-?LW#]+\"|TimeSpan", a)), None)
                cand, body = _method_body(ctx, cls, meth) if meth else (None, None)
                registered.add(cls)
                out.append(_job_record(ctx, "dotnet", "hangfire", rel, text, m.start(), name, m.group(1), sched,
                                       f"{cls}.{meth}" if cls and meth else (cls or meth), body,
                                       cand["file"] if cand else None, cand["start"] + 1 if cand else None))
        for rel, text in ctx.files("dotnet", (".cs",)):
            for m in re.finditer(r"\bclass\s+(\w+)\s*(?:<[^>]*>)?\s*(?::\s*([^{\n]+))?", text):
                cls, bases = m.group(1), m.group(2) or ""
                fw = None
                if re.search(r"\bBackgroundService\b|\bIHostedService\b", bases):
                    fw, meth = "hosted-service", "ExecuteAsync" if "BackgroundService" in bases else "StartAsync"
                elif re.search(r"\bIJob\b", bases):
                    fw, meth = "quartz", "Execute"
                elif re.search(r"(Job|Worker)$", cls) and cls not in registered:
                    fw, meth = "job-class-by-name", None
                if not fw or cls in registered:
                    continue
                if meth is None:
                    mm = re.search(r"public\s+(?:async\s+)?[\w<>]+\s+(Run|Execute|ExecuteAsync|RunAsync|Process|ProcessAsync|Handle|HandleAsync)\s*\(",
                                   text[m.end():])
                    meth = mm.group(1) if mm else None
                cand, body = _method_body(ctx, cls, meth) if meth else (None, None)
                out.append(_job_record(ctx, "dotnet", fw, rel, text, m.start(), cls, fw, None, f"{cls}.{meth}" if meth else cls, body,
                                       cand["file"] if cand else None, cand["start"] + 1 if cand else None))
    if "java-spring" in stacks:
        for rel, text in ctx.files("java-spring", (".java", ".kt")):
            lines = text.splitlines()
            for m in re.finditer(r"@(Scheduled|KafkaListener|RabbitListener|JmsListener|SqsListener|StreamListener)\b(\([^)]*\))?", text):
                i = c.line_of(text, m.start()) - 1
                j = next((k for k in range(i + 1, min(len(lines), i + 6)) if re.search(r"\w+\s*\(", lines[k]) and not lines[k].strip().startswith("@")), i)
                nm = re.search(r"(\w+)\s*\(", lines[j])
                end = c.brace_body_end(lines, j)
                cls = re.search(r"class\s+(\w+)", text)
                args = m.group(2) or ""
                sched = re.search(r"(cron|fixedRate|fixedDelay)\s*=\s*(\"[^\"]*\"|\d+)", args)
                topic = re.search(r"(topics|queues|destination)\s*=\s*\{?\s*\"([^\"]+)", args)
                out.append(_job_record(ctx, "java-spring", "spring-scheduled" if m.group(1) == "Scheduled" else "message-listener", rel, text,
                                       m.start(), topic.group(2) if topic else (nm.group(1) if nm else None), "@" + m.group(1),
                                       sched.group(0) if sched else None,
                                       f"{cls.group(1)}.{nm.group(1)}" if cls and nm else None, c.numbered(lines[j:end + 1], j), rel, j + 1))
    if "node-express" in stacks:
        for rel, text in ctx.files("node-express", (".js", ".ts", ".mjs", ".cjs")):
            if re.search(r"\.(spec|test)\.[cm]?[jt]s$", rel):
                continue
            pats = [
                (r"\bcron\.schedule\(\s*['\"`]([^'\"`]+)['\"`]", "node-cron"),
                (r"new\s+CronJob\(\s*['\"`]([^'\"`]+)['\"`]", "cron"),
                (r"@Cron\(\s*(['\"`][^'\"`]+['\"`]|[\w.]+)", "nestjs-schedule"),
                (r"@Interval\(\s*([^)]*)\)", "nestjs-schedule"),
                (r"new\s+Worker\(\s*['\"`]([^'\"`]+)['\"`]", "bullmq"),
                (r"\b\w+\.process\(\s*(?:['\"`]([^'\"`]+)['\"`])?", "bull"),
                (r"@Processor\(\s*['\"`]([^'\"`]+)['\"`]", "bullmq-nest"),
                (r"\bagenda\.define\(\s*['\"`]([^'\"`]+)['\"`]", "agenda"),
            ]
            for rx, fw in pats:
                for m in re.finditer(rx, text):
                    if fw == "bull" and not re.search(r"bull|queue", text, re.I):
                        continue
                    val = (m.group(1) or "").strip("'\"`") if m.lastindex else None
                    sched = val if fw in ("node-cron", "cron", "nestjs-schedule") else None
                    name = None if sched else val
                    target = None
                    if fw in ("nestjs-schedule", "bullmq-nest"):
                        nm = re.search(r"\n\s*(?:(?:public|private|async)\s+)*(\w+)\s*\(", text[m.end():m.end() + 300])
                        target = nm.group(1) if nm else None
                    out.append(_job_record(ctx, "node-express", fw, rel, text, m.start(), name or target or sched,
                                           m.group(0).split("(")[0].strip(), sched, target, None, None, None, 1500))
    if "python-django" in stacks:
        for rel, text in ctx.files("python-django", (".py",)):
            lines = text.splitlines()
            for m in re.finditer(r"^\s*@(shared_task|app\.task|celery\.task|\w+\.task|periodic_task|scheduler\.scheduled_job)\b(\([^)]*\))?", text, re.M):
                i = c.line_of(text, m.start()) - 1
                j = next((k for k in range(i + 1, min(len(lines), i + 6)) if re.match(r"\s*(async\s+)?def\s", lines[k])), None)
                if j is None:
                    continue
                nm = re.search(r"def\s+(\w+)", lines[j])
                end = c.indent_body_end(lines, j)
                sched = re.search(r"run_every\s*=\s*([^,)]+)|['\"](cron|interval)['\"]", m.group(2) or "")
                fw = "celery" if "task" in m.group(1) else "apscheduler"
                out.append(_job_record(ctx, "python-django", fw, rel, text, m.start(), nm.group(1), "@" + m.group(1),
                                       sched.group(0) if sched else None, nm.group(1), c.numbered(lines[j:end + 1], j), rel, j + 1))
            for m in re.finditer(r"['\"]([\w\-. ]+)['\"]\s*:\s*\{\s*['\"]task['\"]\s*:\s*['\"]([\w.]+)['\"]\s*,\s*['\"]schedule['\"]\s*:\s*([^,}]+)", text):
                out.append(_job_record(ctx, "python-django", "celery-beat", rel, text, m.start(), m.group(1), "beat_schedule", m.group(3).strip(),
                                       m.group(2), None, None, None, 300))
            for m in re.finditer(r"\bschedule\.every\([^)]*\)[\w.()]*\.do\(\s*(\w+)|\.add_job\(\s*(\w+)\s*,\s*['\"](\w+)['\"]", text):
                target = m.group(1) or m.group(2)
                cand, body = _method_body(ctx, None, target)
                out.append(_job_record(ctx, "python-django", "schedule" if m.group(1) else "apscheduler", rel, text, m.start(), target,
                                       m.group(0)[:40], m.group(0) if m.group(1) else m.group(3), target, body,
                                       cand["file"] if cand else None, cand["start"] + 1 if cand else None))
    for rel, text in ctx.all_files((".yaml", ".yml")):
        for m in re.finditer(r"^kind:\s*CronJob\s*$", text, re.M):
            doc_end = text.find("\n---", m.end())
            doc = text[m.start():doc_end if doc_end > 0 else len(text)]
            nm = re.search(r"^\s*name:\s*([\w\-.]+)", doc, re.M)
            sm = re.search(r"^\s*schedule:\s*['\"]?([^'\"\n]+)", doc, re.M)
            out.append(_job_record(ctx, "containers", "k8s-cronjob", rel, text, m.start(), nm.group(1) if nm else None, "kind: CronJob",
                                   sm.group(1).strip() if sm else None, None, None, None, None, 1))


def job_window_note():
    return os.linesep.join(["Job identity context is searched in the resolved target method body, or in the text window",
                            "after the registration when the target cannot be resolved."])
