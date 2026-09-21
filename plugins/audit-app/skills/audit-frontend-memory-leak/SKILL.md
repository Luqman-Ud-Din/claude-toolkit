---
name: audit-frontend-memory-leak
description: Finds memory leaks in frontend code (Angular, React, Vue) - observable/stream subscriptions without teardown (bare subscribe without takeUntil, takeUntilDestroyed or the async pipe), setInterval/setTimeout and addEventListener not cleared on destroy, ResizeObserver/IntersectionObserver/MutationObserver never disconnected, services holding references to destroyed components, Subjects never completed, third-party widgets (charts, maps, editors) never destroyed, and global state that grows per navigation - and reports file:line for every uncleaned resource plus a DevTools heap-snapshot procedure to confirm. Use it whenever the user asks about frontend memory leaks, subscription leaks, unsubscribe, growing memory in the browser, the tab getting slower over time, detached DOM nodes, component cleanup/teardown, ngOnDestroy/useEffect cleanup/onUnmounted, or frontend stability, even when they do not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit frontend memory leak

Finds the places where a single-page app acquires a resource in a component or
service and never releases it. In an SPA the page never reloads, so every leaked
subscription, timer, listener, observer or widget instance survives navigation
and accumulates; the app gets slower, then the tab crashes. Each finding must
name the acquisition (file:line), show that no release exists on the destroy
path, and say what grows.

Read-only rule: never modify the audited code. Write only under `audit/`.

## Inputs and prerequisites

- Repo root (defaults to `.`). Standalone runs read `audit/stack.json` if
  present, else run `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`
  (without `--write`, so a standalone run does not create `audit/stack.json`).
- Python 3 (stdlib only). A Chromium browser with DevTools for the confirmation
  procedure (manual; cannot be bundled).
- Sibling skills: `audit-backend-resource-leak` owns server-side leaks
  (connections, streams, hubs); `audit-frontend-best-practices` owns change
  detection and bundle size; `audit-performance-and-scalability` owns runtime
  speed. The backend reference files here only cover the server end of
  long-lived client connections (SignalR, socket.io, SSE) and defer the rest.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack detection), `audit-code-scan` (grep pass, and the shared `repo_walk.py` walker the bundled scripts import) and `audit-finding-writer` (`$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`). A missing one stops the scripts with an error naming it.

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`; open only
   `references/<primary_frontend>.md`. If the repo also has a backend that
   pushes to the client (SignalR hub, socket.io, SSE), open that backend file
   for the server-side pairing checks. No frontend detected: write
   `audit/status/audit-frontend-memory-leak.json` with `status: skipped`.
2. **Automated pass.** Save everything under `audit/evidence/audit-frontend-memory-leak/`:
   - `python scripts/leak_scan.py <repo> --out audit/evidence/audit-frontend-memory-leak/leaks.json`
     pairs every acquisition with a release *in the same file* and lists the
     unpaired ones with file:line: `subscribe(` without `takeUntil`/`takeUntilDestroyed`/
     `unsubscribe`/`Subscription` bookkeeping; `addEventListener` without
     `removeEventListener`; `setInterval`/`setTimeout` without `clear*`;
     observers without `disconnect()`; chart/map/editor constructors without
     `destroy()`/`remove()`/`dispose()`; `Subject`s never `complete()`d;
     React `useEffect` bodies that acquire without a returned cleanup; Vue
     `onMounted` acquisitions without `onUnmounted`/`onBeforeUnmount`.
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-frontend-memory-leak/hits.json`
     catches the shapes `leak_scan.py` cannot pair (module-level caches,
     services keeping component refs, `window.x =` globals, `shareReplay()`
     without `refCount`).
   Every hit is a candidate. A release in a parent class, a directive, or a
   framework helper (`async` pipe, `takeUntilDestroyed`) makes it a false positive.
3. **Manual trace of the highest-risk flows.** In this order: (a) the routes
   users cycle through most (list -> detail -> list): open each component's
   destroy path and confirm every acquisition from step 2 is released;
   (b) singleton services (`providedIn: 'root'`, module-level stores, React
   contexts, Pinia stores) that hold arrays/maps keyed by something that grows
   (rows, sockets, callbacks) - look for `push`/`set` without a matching remove;
   (c) long-lived connections (SignalR/socket.io/SSE/WebSocket) - one per app,
   closed on logout; (d) third-party widgets (charts, maps, editors, grids) -
   constructor in `ngOnInit`/`useEffect`/`onMounted`, `destroy` in the teardown.
   Use the "Manual trace checklist" in the stack file.
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (`init`, `add`, `validate`,
   `md`). Prefix `FELEAK`. One finding per root cause: "11 components subscribe
   in `ngOnInit` without teardown" is one finding whose Evidence lists all 11
   locations. Severity per the rubric read as production risk: a leak on a
   route visited every few seconds (POS, dashboard polling) = High; a leak in
   a singleton that grows per navigation = High; a leak on a rarely visited
   admin page = Medium; a timer that fires once = Low.
5. **Produce outputs**: `audit/findings/audit-frontend-memory-leak.json`,
   `audit/reports/audit-frontend-memory-leak.md` (template below, includes the
   heap-snapshot procedure from `references/heap-snapshot-procedure.md`),
   evidence files, and `audit/status/audit-frontend-memory-leak.json`
   (`{"skill","status":"completed|failed|skipped","reason","started_at","finished_at"}`).
6. **List what was not checked**: the heap-snapshot procedure not executed
   (needs a running app and a browser), third-party library internals,
   Web Workers, service worker caches, native (Capacitor) plugins, etc.
   Also list what the automated pass did not read: folders skipped by the shared walker (`repo_walk.SKIP_DIRS` in `audit-code-scan`: `.git`, `node_modules`, `bin`, `obj`, `dist`, `build`, `target`, `coverage`, `.angular`, `.next`, the `audit` workspace and similar) and files over 2 MB.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `FELEAK`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Evidence:**

```lang
<the acquisition line and the destroy hook (or its absence)>
```

- **Impact:** Plain language. What grows, on which user action, how fast it becomes visible.
- **Remediation:** The concrete teardown in this stack, with a short example.
- **Reference:** CWE-401, CWE-772, framework doc (see references/<stack>.md)


## Output template - `audit/reports/audit-frontend-memory-leak.md`

````markdown
## audit-frontend-memory-leak

**Target:** <repo> @ <commit> | **Stack:** <framework + version> | **Date:** <ISO>

### Summary
| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| 0 | 2 | 4 | 1 | 0 |

### Uncleaned resources (from leak_scan.py, confirmed by hand)
| Kind | Location | Acquired in | Released in | Verdict |
|---|---|---|---|---|
| subscription | `src/app/pos/pos.component.ts:41` | ngOnInit | - | leak |
| listener | `src/app/shared/resize.directive.ts:18` | constructor | ngOnDestroy | ok |
| chart | `src/app/dashboard/sales-chart.component.ts:27` | ngAfterViewInit | - | leak |

### Findings
<finding blocks, highest severity first>

### Confirmation procedure (DevTools heap snapshot)
1. Build and serve the production bundle; open the app in Chrome, log in, land on the route under test.
2. DevTools > Memory > "Heap snapshot" > Take snapshot (baseline). Note the size.
3. Navigate away and back to the route 10 times (list -> detail -> list, or open/close the dialog).
4. Click the trash-can (collect garbage), then take snapshot 2.
5. Select snapshot 2, switch "Summary" to "Comparison" against snapshot 1; sort by "# Delta".
6. Leak confirmed when component class names, `Subscriber`, `Subscription`, `HTMLDivElement`/"Detached", or the widget class (`Chart`, `Map`) show a positive delta close to 10 (or a multiple).
7. Record snapshot sizes and the delta rows in `audit/evidence/audit-frontend-memory-leak/heap-<route>.md`.
Full procedure, per-framework retainer names and false positives: `references/heap-snapshot-procedure.md`.

### Not checked
- <item> - <reason>
````

## Examples

**Input (leak_scan.py row):**
`subscription  src/app/features/reports/reports.component.ts:22  acquired=ngOnInit released=-`

**Output:**
````markdown
### [High] FELEAK-001 - Reports list subscribes on init and never unsubscribes
- **Location:** `src/app/features/reports/reports.component.ts:22` (ngOnInit)
- **Confidence:** confirmed
- **Evidence:**

```ts
ngOnInit() { this.reports.list().subscribe(d => this.rows = d); }   // no ngOnDestroy in this class
```

- **Impact:** Every visit to Reports keeps the previous component alive through the subscription callback; after 30 visits the tab holds 30 copies of the rows array and the list re-renders 30 times per refresh tick. Users on the POS shift who open Reports repeatedly will see the app slow down until they reload.
- **Remediation:** Use `takeUntilDestroyed()` (inject `DestroyRef` in a standalone component): `this.reports.list().pipe(takeUntilDestroyed(this.destroyRef)).subscribe(...)`, or expose `rows$ = this.reports.list()` and render with `| async`.
- **Reference:** CWE-401, angular.dev/api/core/rxjs-interop/takeUntilDestroyed
````

**Input (grep hit):** `src/app/core/services/notification.service.ts:31: this.listeners.push(cb);`
with no `splice`/`delete` in the file.

**Output:** `[High] FELEAK-003 - NotificationService keeps every registered callback forever`,
Evidence shows `register(cb)` with no `unregister`, Impact explains that each
component that registers keeps itself reachable after destroy, Remediation
returns an unsubscribe function or uses a `Subject` with `takeUntilDestroyed`.

## Bundled files

- `references/angular.md`, `react.md`, `vue.md` - acquisition/release pairs, framework helpers, false positives, tooling.
- `references/dotnet.md`, `java-spring.md`, `node-express.md`, `python-django.md` - server end of long-lived client connections (SignalR, socket.io, SSE) and what to defer to `audit-backend-resource-leak`.
- `references/heap-snapshot-procedure.md` - the manual DevTools procedure, retainer names per framework, and how to read the comparison view.
- `scripts/leak_scan.py` - per-file acquisition/release pairing; emits unpaired resources with file:line.
- `scripts/patterns/{angular,react,vue}.json` - shapes the pairing cannot see, run by `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- Atomic scripts called: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`, `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` (and `repo_walk.py`, imported by `leak_scan.py`), `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`. To add a stack, start from `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `evals/` - prompts and sample components with a bare subscribe, an addEventListener with no removal, a chart never destroyed, and a clean negative.
