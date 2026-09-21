# Angular reference for audit-performance-and-scalability

Scope here is *runtime* behaviour of the deployed app: render-blocking
resources, API calls per page (and duplicates), client-side caching, image
loading, re-render cost, Core Web Vitals. Bundle size, lazy routes, `OnPush`
hygiene and build config are owned by `audit-frontend-best-practices` - read
its findings, do not repeat them.

## Stack markers
`package.json` with `@angular/core`; `angular.json`; Ionic/Capacitor (`@ionic/angular`, `capacitor.config.ts`) - mobile webview, slower CPU, so INP matters more; `@angular/ssr` for server rendering; `ngsw-config.json` for the service worker.

## Where the relevant code lives
`src/index.html` (blocking `<script>`/`<link>`, fonts), `angular.json` (`styles`/`scripts` arrays = render-blocking by default), `app.routes.ts` (resolvers run before navigation), `core/services/api.service.ts` (single HTTP entry - where caching/dedup belongs), feature services (`shareReplay`, store), dashboard/landing components (`ngOnInit` fan-out), `core/interceptors/` (caching interceptor?), `ngsw-config.json` (`dataGroups` for API caching), templates (`<img>` without `ngSrc`, `*ngFor` without `trackBy`, function calls in bindings).

## Dangerous / interesting APIs and patterns
- RENDER-BLOCK: `<script src>` in `index.html` `<head>` without `defer`/`async` (analytics, maps, chat widgets); `<link rel="stylesheet">` to third-party CSS/fonts without `preconnect`/`font-display: swap`; large `angular.json` `styles` (whole Bootstrap/Ionic theme); no `preload`/`preconnect` for the API origin; SSR absent on a public landing page (LCP waits for JS).
- CALLS-PER-PAGE: several components on one route each calling the same service method (`this.api.get('products')` in five widgets) -> duplicates; `ngOnInit` firing a list call *and* a count call *and* a filters call; resolvers plus component calls for the same data; polling with `interval()` at high frequency; `valueChanges` search without `debounceTime`/`distinctUntilChanged`/`switchMap`.
- CLIENT-CACHE: reference data (units, currencies, roles) refetched on every route; no `shareReplay(1)` / store / `HttpContext` cache token / caching interceptor; `ngsw-config` `dataGroups` absent for GET APIs; `HttpClient` calls with `cache: 'no-store'` semantics forced by server headers (cross-check with backend `Cache-Control`).
- RERENDER: `Default` change detection with function calls or `| async` pipes recreated in templates (`getTotal()` in a binding), `*ngFor` without `trackBy`/`@for` without `track`, `[ngStyle]`/`[ngClass]` with new objects per cycle, large tables without virtual scroll (`cdk-virtual-scroll-viewport`), `ChangeDetectorRef.detectChanges()` in `setInterval`, `zone.js` events from `mousemove`/`scroll` listeners without `runOutsideAngular`.
- IMAGE: `<img src>` without `NgOptimizedImage` (`ngSrc`), no `width`/`height` (CLS), no `loading="lazy"` below the fold, product thumbnails served full-size, no `srcset`/WebP/AVIF, base64 images in API JSON.
- CWV: LCP element is an image without `priority`; fonts without `font-display`; layout shift from late-loading toolbars/ads; INP from heavy `(click)` handlers running synchronously (Excel export in the browser).

## What "good" looks like
```ts
// one fetch per page, shared
readonly products$ = this.api.get<Product[]>('products').pipe(shareReplay({ bufferSize: 1, refCount: true }));
// reference data cached for the session
private units$?: Observable<Unit[]>;
getUnits() { return this.units$ ??= this.api.get<Unit[]>('units').pipe(shareReplay(1)); }
// search
this.search.valueChanges.pipe(debounceTime(300), distinctUntilChanged(), switchMap(q => this.api.search(q)));
```
```html
<img ngSrc="/img/hero.webp" width="1200" height="600" priority>      <!-- LCP image -->
<img ngSrc="{{p.thumb}}" width="80" height="80" loading="lazy">
@for (row of rows; track row.id) { ... }
```
`index.html`: `<link rel="preconnect" href="https://api.example.com">`, third-party scripts with `defer`; `ngsw-config.json` `dataGroups: [{ name: 'ref', urls: ['/productapi/Unit/**'], cacheConfig: { maxAge: '1d', strategy: 'performance' } }]`.

## Manual trace checklist
1. Landing route: list every HTTP call in `ngOnInit`/resolvers/child components; count duplicates (same URL) -> "Frontend runtime" table.
2. `index.html` + `angular.json` `styles`/`scripts`: render-blocking inventory.
3. Reference-data services: cached or refetched per route?
4. Largest list/grid: `track`, virtual scroll, function calls in bindings.
5. Images: `ngSrc`, dimensions, lazy, format.
6. Run Lighthouse (desktop + mobile) on landing + dashboard if a URL exists; record LCP/INP(TBT)/CLS.

## Stack-specific false positives
- Multiple calls to the same endpoint with different query params (paging) - not duplicates.
- `angular.json` `styles` containing only the app's own compiled SCSS - expected.
- `Default` change detection in small leaf components with no bindings to functions.

## Tooling
`npx lighthouse <url> --output=json`, Chrome DevTools Performance panel (Interactions track for INP), Network > XHR count on reload, Angular DevTools Profiler (change detection cycles per interaction), `ng build --stats-json` (delegated to best-practices skill), `web-vitals` library for field data.

## References
web.dev "Core Web Vitals", "Optimize LCP/INP/CLS"; Angular docs "NgOptimizedImage", "Service worker - data groups", "Zoneless / OnPush change detection", "SSR and hydration"; RxJS `shareReplay`.
