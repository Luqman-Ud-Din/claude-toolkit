# Heap-snapshot confirmation procedure

Static analysis says "this acquisition has no release". A heap snapshot
comparison says "and it actually accumulates". Run this for every High finding
before the report goes out; record the numbers under
`audit/evidence/audit-frontend-memory-leak/heap-<route>.md`. It is manual: it
needs a running build and a Chromium browser, which this skill cannot bundle.

## Setup (once)

1. Build the production bundle (dev builds keep extra debug objects alive and inflate
   deltas): Angular `ng build --configuration production`, Vite `vite build`, Next `next build`.
   Serve it (`npx serve -s dist/<app>` or the real backend). Do not use the dev server.
2. Open Chrome (or Edge) in a fresh profile or Incognito so extensions do not add retainers.
3. Log in and land on the route to test. Let it settle (all requests finished).
4. Open DevTools > Memory. Tick "Include numerical values in capture" off (smaller snapshots).

## Procedure (per route or per dialog)

1. Click the trash-can icon (collect garbage). Take **Snapshot 1** (baseline). Note its size
   in the left list.
2. Perform the cycle **10 times**: navigate away and back (list -> detail -> list), or open
   and close the dialog, or switch the tab that mounts the widget. Use the app's own links,
   not the browser back button, unless the finding is about back navigation.
3. Return to the exact starting state. Click the trash-can again. Take **Snapshot 2**.
4. Optional but decisive: cycle 10 more times, collect, take **Snapshot 3**. A leak grows
   linearly (delta 2->3 about equals delta 1->2); a warm-up cache grows once and stops.
5. Select Snapshot 2. In the dropdown that says "Summary", pick **Comparison**, and compare
   with Snapshot 1. Sort by **# Delta** descending, then by **Size Delta**.
6. In the class filter box type, one at a time, the names below for your framework and the
   component/widget under test. A `# Delta` of about +10 (one per cycle) or a multiple of 10
   confirms the leak. A delta of +1 or +2 is noise or a first-visit cache.
7. Click a leaked object; the **Retainers** pane at the bottom shows what holds it. Walk up
   until you hit a `Subscriber`, a listener array on `Window`/`HTMLDocument`, a timer, an
   observer, a widget instance, or a module-level Map. That retainer is the Location of the
   finding if static analysis pointed elsewhere.

## What to search for in the Comparison view

| Framework | Retained object names that indicate the leak |
|---|---|
| Angular | the component class name (e.g. `ReportsComponent`), `SafeSubscriber`, `Subscriber`, `Subscription`, `BehaviorSubject`, `LView`/`TView` counts, `Detached HTMLDivElement` |
| React | `FiberNode` (count climbs), the component function name, `Detached HTMLElement`, closures named after the effect's handler |
| Vue | `ComponentInternalInstance`, `ReactiveEffect`, `VueElement`, the component name from `__name`, `Detached HTMLElement` |
| Any | `Chart`, `Map` (Leaflet `Map`/Mapbox `Map`), `StandaloneEditor` (Monaco), `Quill`, `Swiper`, `ResizeObserver`, `IntersectionObserver`, `MutationObserver`, `WebSocket`, `EventSource`, `HubConnection`, `Timer`, `XMLHttpRequest` |

"Detached" nodes are DOM elements no longer in the document but still reachable; a growing
count means something (a listener, a widget, a subscription callback) still references the
old view.

## Reading the result

- **Confirmed leak**: `# Delta` for the component or widget class is close to the cycle count
  and Snapshot 3 keeps growing. Set `confidence: confirmed`, put the delta rows in Evidence.
- **Not a leak**: delta near 0 after GC, or growth stops at Snapshot 3 (a bounded cache).
  Mark the static finding `false-positive` with the snapshot numbers, or downgrade to Info if
  the acquisition is still unhygienic.
- **Growth without a matching class**: search "Detached" and `(closure)`; check the Retainers
  pane; then look for module-level Maps/arrays in the retainer chain (global-state growth).

## Recording

Write `audit/evidence/audit-frontend-memory-leak/heap-<route>.md` with: build command,
browser version, the cycle performed, snapshot sizes (1, 2, 3), the top 5 `# Delta` rows with
class name and size delta, and the retainer chain for one leaked instance. Screenshots are
optional; the numbers are what the report cites.

## Alternatives when a browser session is not available

- `performance.memory.usedJSHeapSize` (Chrome only) logged from the console after each cycle
  gives a coarse curve; a monotonic rise over 20 cycles supports `likely`, not `confirmed`.
- Playwright/Puppeteer: `page.metrics()` (`JSHeapUsedSize`) or the CDP `HeapProfiler`
  domain can automate the 10-cycle loop in CI; keep the script under
  `audit/evidence/`, never in the repo.
- Angular: `ng.getComponent(node)` on a detached node from the snapshot's retainers pane
  identifies the leaking component when class names are minified.

## Common false positives

- The first visit to a route allocates lazily-loaded chunks, i18n bundles, icon sets: a big
  delta between Snapshot 1 and 2 that does not repeat at Snapshot 3.
- DevTools itself retains console-logged objects; clear the console before snapshots and avoid
  logging the rows array.
- Browser extensions (React/Vue DevTools included) add retainers; use a clean profile.
- `shareReplay`/store caches that are *bounded* by design show one-time growth.
