#!/usr/bin/env python3
"""Acquisition/release pairing for audit-frontend-memory-leak.

Usage:
    python leak_scan.py <repo_root> [--out leaks.json] [--md leaks.md] [--all]

For every component / hook / composable / service file (.ts .tsx .js .jsx .vue) it
finds resource ACQUISITIONS and checks whether a matching RELEASE exists in the
same file (React: in the same useEffect's returned cleanup):

  kind          acquisition                                     release
  subscription  .subscribe(                                     takeUntil/takeUntilDestroyed/first/take(1)
                                                                on the same chain, or unsubscribe()/destroy$.next()
  listener      addEventListener('evt'                          removeEventListener('evt'
  interval      setInterval(                                    clearInterval(
  timeout       setTimeout(                                     clearTimeout(   (Low: only matters if long-lived)
  observer      new ResizeObserver|IntersectionObserver|Mutation disconnect(
  widget        new Chart( echarts.init( L.map( new mapboxgl.Map( destroy( remove( dispose( tinymce.remove(
                monaco.editor.create( new Quill( tinymce.init(
                new Swiper( new Sortable( Highcharts.chart(
  subject       new Subject|BehaviorSubject|ReplaySubject(        complete(
  socket        socket|connection|hub|emitter.on('evt'           .off('evt'  (or .off( )
  rxjs-timer    interval( / timer( / fromEvent(                  same as subscription

Each unpaired acquisition is reported with file:line, the enclosing hook/method,
and a verdict: leak | likely-ok (one-shot HttpClient, take operators) | released.
Every row is a candidate for the manual pass. Read-only.
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

EXTS = (".ts", ".tsx", ".js", ".jsx", ".vue", ".mjs")

ACQ = [
    ("subscription", re.compile(r"\.subscribe\(")),
    ("listener", re.compile(r"\baddEventListener\(\s*['\"]([\w-]+)['\"]")),
    ("interval", re.compile(r"\bsetInterval\(")),
    ("timeout", re.compile(r"\bsetTimeout\(")),
    ("observer", re.compile(r"\bnew\s+(ResizeObserver|IntersectionObserver|MutationObserver|PerformanceObserver)\(")),
    ("widget", re.compile(r"\bnew\s+(Chart|Quill|Swiper|Sortable|Cropper|Viewer|Grid|Tabulator)\b\s*\(|echarts\.init\(|Highcharts\.chart\(|\bL\.map\(|new\s+mapboxgl\.Map\(|new\s+google\.maps\.Map\(|monaco\.editor\.create\(|tinymce\.init\(|new\s+Editor\(|agGrid\.createGrid\(")),
    ("subject", re.compile(r"\bnew\s+(Subject|BehaviorSubject|ReplaySubject|AsyncSubject)\s*(<[^>]*>)?\s*\(")),
    ("socket", re.compile(r"\b(socket|connection|hubConnection|hub|emitter|bus|eventBus|io|ws|channel)\.on\(\s*['\"]([\w:.-]+)['\"]")),
]
RELEASE = {
    "listener": lambda evt, t: re.search(r"removeEventListener\(\s*['\"]" + re.escape(evt) + r"['\"]", t) is not None,
    "interval": lambda _, t: "clearInterval(" in t,
    "timeout": lambda _, t: "clearTimeout(" in t,
    "observer": lambda _, t: ".disconnect(" in t or ".unobserve(" in t,
    "widget": lambda _, t: re.search(r"\.(destroy|dispose|remove|off)\(|tinymce\.remove\(", t) is not None,
    "subject": lambda _, t: ".complete(" in t,
    "socket": lambda evt, t: re.search(r"\.off\(\s*['\"]" + re.escape(evt) + r"['\"]", t) is not None or re.search(r"\.off\(\s*\)|\.removeAllListeners\(|\.disconnect\(|\.stop\(|\.close\(", t) is not None,
}
CHAIN_GUARD = re.compile(r"takeUntil(Destroyed)?\(|\bfirst\(|\btake\(\s*1\s*\)|\btakeWhile\(|\btoPromise\(|\blastValueFrom\(|\bfirstValueFrom\(")
ONE_SHOT = re.compile(r"\b(http|httpClient|apiService|api|_http|apiSvc)\.(get|post|put|delete|patch|request)\b|HttpClient")
TEARDOWN_HOOKS = re.compile(r"ngOnDestroy\s*\(|ionViewWillLeave\s*\(|componentWillUnmount\s*\(|onUnmounted\(|onBeforeUnmount\(|onScopeDispose\(|onDeactivated\(|\bbeforeUnmount\s*\(|\bunmounted\s*\(|\bbeforeDestroy\s*\(|\bdestroyed\s*\(|DestroyRef|\.onDestroy\(")
HOOK_NAMES = re.compile(r"\b(constructor|ngOnInit|ngAfterViewInit|ngAfterContentInit|ngOnChanges|ionViewDidEnter|ionViewWillEnter|ngOnDestroy|componentDidMount|componentWillUnmount|useEffect|useLayoutEffect|onMounted|onBeforeMount|onActivated|onUnmounted|mounted|created|setup|beforeUnmount|unmounted|connectedCallback|disconnectedCallback|init|start|connect|open|show|render)\b\s*(\(|=|:)")


def read(p):
    return repo_walk.read_text(p)


def enclosing_hook(text, pos):
    last = None
    for m in HOOK_NAMES.finditer(text, 0, pos):
        last = m.group(1)
    return last or "(module/other)"


def statement_before(text, pos):
    """Text of the current statement/chain up to pos (bounded), to look for pipe guards."""
    start = max(0, pos - 600)
    chunk = text[start:pos]
    cut = max(chunk.rfind(";"), chunk.rfind("\n\n"))
    return chunk[cut + 1:] if cut >= 0 else chunk


def effect_bodies(text):
    """Yield (start, end, body, has_cleanup) for each useEffect/useLayoutEffect call."""
    for m in re.finditer(r"\buse(Layout)?Effect\(", text):
        i = m.end(); depth = 1; in_str = None
        while i < len(text) and depth:
            ch = text[i]
            if in_str:
                if ch == "\\": i += 1
                elif ch == in_str: in_str = None
            elif ch in "'\"`": in_str = ch
            elif ch == "(": depth += 1
            elif ch == ")": depth -= 1
            i += 1
        body = text[m.end():i - 1]
        has_cleanup = re.search(r"\breturn\s*(\(\s*\)\s*=>|function\b|\w+\s*;|\w+\s*\))", body) is not None
        yield m.start(), i, body, has_cleanup


def scan_file(path, root):
    text = read(path)
    if not text or re.search(r"\.(spec|test|stories|d)\.[tj]sx?$", path):
        return None
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    is_react = bool(re.search(r"from\s+['\"]react['\"]|useEffect\(|extends\s+(React\.)?Component", text))
    is_vue = path.endswith(".vue") or bool(re.search(r"from\s+['\"]vue['\"]", text))
    is_angular = bool(re.search(r"@(Component|Directive|Injectable|Pipe)\(", text))
    singleton = bool(re.search(r"providedIn\s*:\s*['\"]root['\"]", text))
    has_teardown = TEARDOWN_HOOKS.search(text) is not None
    effects = list(effect_bodies(text)) if is_react else []
    rows = []
    for kind, rx in ACQ:
        for m in rx.finditer(text):
            line = text[:m.start()].count("\n") + 1
            evt = None
            if kind == "listener":
                evt = m.group(1)
            elif kind == "socket":
                evt = m.group(2)
            hook = enclosing_hook(text, m.start())
            verdict, note = "leak", ""
            if kind == "subscription":
                stmt = statement_before(text, m.start())
                if CHAIN_GUARD.search(stmt):
                    verdict, note = "released", "guarded on the chain"
                elif ONE_SHOT.search(stmt):
                    verdict, note = "likely-ok", "one-shot HTTP call; completes by itself"
                elif "async" in stmt and "pipe" not in stmt and "| async" in stmt:
                    verdict = "released"
                elif re.search(r"\.unsubscribe\(\)|destroy\$\.next\(|subscriptions?\.add\(|this\.subs?\b.*=|Subscription\(\)", text) and has_teardown:
                    verdict, note = "likely-released", "file keeps Subscription bookkeeping and has a teardown hook; confirm this one is added"
            elif kind in RELEASE:
                scope = text
                if is_react:
                    eff = next((e for e in effects if e[0] <= m.start() < e[1]), None)
                    if eff is not None:
                        scope = eff[2]
                        if not eff[3]:
                            verdict, note = "leak", "useEffect has no returned cleanup"
                            rows.append(dict(kind=kind, file=rel, line=line, hook=hook, event=evt, verdict=verdict, note=note, snippet=text.splitlines()[line - 1].strip()[:160]))
                            continue
                if RELEASE[kind](evt, scope):
                    verdict, note = "released", ""
                elif kind == "timeout":
                    note = "only a leak if the callback captures the component and the delay is long or repeated"
            if verdict == "leak" and singleton:
                note = (note + "; " if note else "") + "providedIn root singleton: lives for the session - a leak only if it grows per use"
            if verdict == "leak" and has_teardown and kind != "subscription":
                note = (note + "; " if note else "") + "teardown hook exists but does not release this resource"
            rows.append(dict(kind=kind, file=rel, line=line, hook=hook, event=evt, verdict=verdict, note=note,
                             snippet=text.splitlines()[line - 1].strip()[:160]))
    if not rows:
        return None
    return {"file": rel, "framework": "react" if is_react else "vue" if is_vue else "angular" if is_angular else "unknown",
            "has_teardown_hook": has_teardown, "singleton_service": singleton, "acquisitions": rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--out"); ap.add_argument("--md")
    ap.add_argument("--all", action="store_true", help="also list released acquisitions")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    files = []
    for path in repo_walk.iter_files(root, exts=set(EXTS), names=frozenset()):
        r = scan_file(path, root)
        if r:
            files.append(r)
    unpaired = [dict(a_, **{}) for f in files for a_ in f["acquisitions"] if a_["verdict"] in ("leak", "likely-released")]
    counts = {}
    for u in unpaired:
        counts[u["kind"]] = counts.get(u["kind"], 0) + 1
    result = {"root": root, "files_with_acquisitions": len(files), "unpaired_count": len(unpaired),
              "counts_by_kind": counts, "unpaired": unpaired, "files": files if a.all else None}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    lines = ["| Kind | Location | Acquired in | Verdict | Note |", "|---|---|---|---|---|"]
    for f in files:
        for r in f["acquisitions"]:
            if a.all or r["verdict"] in ("leak", "likely-released"):
                lines.append(f"| {r['kind']}{(' ' + r['event']) if r['event'] else ''} | `{r['file']}:{r['line']}` | {r['hook']} | {r['verdict']} | {r['note']} |")
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    print(json.dumps({"files_with_acquisitions": len(files), "unpaired": len(unpaired), "by_kind": counts}, indent=2))
    print("\n".join(lines))
    if a.out:
        print(f"written: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
