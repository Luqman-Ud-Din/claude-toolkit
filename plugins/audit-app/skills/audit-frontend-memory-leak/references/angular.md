# Angular reference for audit-frontend-memory-leak

## Stack markers

`package.json` with `@angular/core`, `angular.json`. Variants that change the
teardown idiom: v16+ has `DestroyRef` + `takeUntilDestroyed()`; older code uses
a `destroy$ = new Subject<void>()` + `takeUntil(this.destroy$)` + `ngOnDestroy`.
Ionic apps add `ionViewWillLeave` as a second teardown hook (components are
cached by the router outlet, so `ngOnDestroy` may never fire while navigating).

## Where the relevant code lives

`*.component.ts` (`ngOnInit`, `ngAfterViewInit`, `ngOnDestroy`), `*.directive.ts`,
`*.service.ts` (`providedIn: 'root'` singletons live for the whole session),
`core/services/` (signalr/websocket/notification/timer services), `*.guard.ts`,
`*.interceptor.ts` (`shareReplay`, refresh-token subjects), `app.component.ts`.

## Dangerous / interesting APIs and patterns

- `.subscribe(` in a component/directive without `takeUntil(`, `takeUntilDestroyed(`,
  `first()`/`take(1)`, `Subscription.add`, or an `unsubscribe()` in `ngOnDestroy`.
  `HttpClient` one-shot calls complete on their own and are usually fine (see false positives),
  but `interval`, `timer`, `fromEvent`, `valueChanges`, `router.events`, `store.select`, a
  `BehaviorSubject` from a service, and SignalR streams never complete.
- `setInterval(` / `setTimeout(` without `clearInterval`/`clearTimeout` in `ngOnDestroy`;
  `interval(` / `timer(` from RxJS without teardown.
- `addEventListener(` (on `window`, `document`, `nativeElement`) without `removeEventListener`;
  `Renderer2.listen()` return value discarded (it returns the unlisten function).
- `new ResizeObserver(` / `IntersectionObserver` / `MutationObserver` without `.disconnect()`.
- Widgets: `new Chart(`, `echarts.init(`, `Highcharts.chart(`, `L.map(`, `new mapboxgl.Map(`,
  `new google.maps.Map(`, `monaco.editor.create(`, `new Quill(`, `tinymce.init(`,
  `new Swiper(`, `new Sortable(`, `agGrid`/`gridApi` without `destroy()`/`remove()`/`dispose()`.
- `new Subject(` / `BehaviorSubject(` / `ReplaySubject(` in a component never `.complete()`d;
  `ReplaySubject` with no buffer size (unbounded).
- `shareReplay(1)` without `{ refCount: true }` on a source that never completes: the
  connection stays alive after the last subscriber leaves.
- Services holding component references: `register(component)`, `this.listeners.push(cb)`,
  `Map<string, ComponentRef>` without delete; `EventEmitter` in a service used as a bus.
- Global growth: `window.x = ...`, module-level `const cache = new Map()` written per
  navigation, `localStorage` used as an ever-growing log.
- `ViewContainerRef.createComponent` without `destroy()`; `MatDialog`/`ionModal` opened
  repeatedly without awaiting `afterClosed()`; `Overlay` refs not disposed.
- `ngOnDestroy` present but empty, or not calling `super.ngOnDestroy()` when extending a
  base class that tears down `destroy$`.
- Ionic: subscriptions started in `ionViewDidEnter` and not stopped in `ionViewWillLeave`.

## What "good" looks like

```ts
@Component({ standalone: true, ... })
export class SalesChartComponent implements AfterViewInit, OnDestroy {
  private destroyRef = inject(DestroyRef);
  private chart?: Chart;
  private ro?: ResizeObserver;
  rows$ = this.sales.rows$;                       // rendered with | async - no manual subscribe

  ngAfterViewInit() {
    this.chart = new Chart(this.canvas.nativeElement, cfg);
    this.ro = new ResizeObserver(() => this.chart?.resize());
    this.ro.observe(this.host.nativeElement);
    interval(30_000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.refresh());
    this.destroyRef.onDestroy(() => { this.ro?.disconnect(); this.chart?.destroy(); });
  }
  ngOnDestroy() { /* nothing left: DestroyRef handles it */ }
}
```
Legacy idiom: `private destroy$ = new Subject<void>()`, every subscribe gets
`takeUntil(this.destroy$)`, and `ngOnDestroy() { this.destroy$.next(); this.destroy$.complete(); }`.

## Manual trace checklist

1. Routes users cycle through most (list <-> detail, POS screens): open each component and
   pair every acquisition from `leak_scan.py` with the destroy path. Note Ionic's cached
   outlets: `ngOnDestroy` may not run; the teardown belongs in `ionViewWillLeave`.
2. `providedIn: 'root'` services: any array/Map/Set that is appended per component or per
   request (`listeners`, `cache`, `pending`) - find the remove path.
3. The SignalR/WebSocket service: one connection per session? Reconnect logic that creates a
   new `HubConnection` without stopping the old one? Handlers registered in components via
   `connection.on(...)` and removed with `connection.off(...)`?
4. Base component classes: if `BaseComponent.ngOnDestroy` completes `destroy$`, check every
   subclass that overrides `ngOnDestroy` calls `super.ngOnDestroy()`.
5. Dialogs and overlays opened in loops (notifications, confirm prompts): closed and disposed?
6. Interceptors: refresh-token `BehaviorSubject` or `shareReplay` chains that never release.

## Stack-specific false positives

- `this.http.get(...).subscribe(...)`: `HttpClient` completes after one emission. Leak-safe
  unless the component is destroyed mid-flight and the callback touches destroyed state
  (then it is a correctness smell, rated Low/Info, not a memory finding).
- `route.params`/`route.data` subscriptions inside a routed component: Angular completes them
  when the route is destroyed. Still a leak if the component outlives the route (e.g. in a
  dialog) - check where it is instantiated.
- `| async` in the template: the pipe unsubscribes; no manual teardown needed.
- `first()`, `take(1)`, `takeWhile`, `takeUntil` anywhere in the pipe: released.
- `Renderer2.listen` whose return value is stored and invoked in `ngOnDestroy`: fine.
- `setTimeout` that only defers one UI action and captures nothing heavy: Low at most.
- `subscribe` inside a `providedIn: 'root'` service that intentionally lives for the session
  (auth state): document it, no finding.

## Tooling

- Chrome DevTools heap snapshot comparison (see `heap-snapshot-procedure.md`); retainers to
  search for: the component class name, `Subscriber`, `SafeSubscriber`, `Chart`, `Map`,
  "Detached HTMLElement".
- `ng.getComponent($0)` in the console to find the component behind a DOM node.
- `@angular-eslint` has no unsubscribe rule; `eslint-plugin-rxjs-angular`
  (`rxjs-angular/prefer-takeuntil`) and `eslint-plugin-rxjs` (`rxjs/no-ignored-subscription`)
  can enforce the fix; suggest them in the remediation.
- `performance.memory` (Chrome) logged every navigation from a dev-only console snippet gives
  a coarse growth curve without snapshots.

## References

- `takeUntilDestroyed` / `DestroyRef`: https://angular.dev/api/core/rxjs-interop/takeUntilDestroyed
- Ionic lifecycle: https://ionicframework.com/docs/angular/lifecycle
- RxJS `shareReplay` refCount: https://rxjs.dev/api/operators/shareReplay
- CWE-401 (missing release of memory), CWE-772 (missing release of resource), CWE-400 (uncontrolled resource consumption).
