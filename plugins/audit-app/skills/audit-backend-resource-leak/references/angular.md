# Angular reference for audit-backend-resource-leak

This skill is backend-only. Browser-side leaks (subscriptions, intervals,
detached DOM, third-party widgets) are owned by `audit-frontend-memory-leak`.
Use this file to spot the frontend behaviours that *create* or *expose* backend
leaks, record them for the load-test plan, then hand the rest to the sibling.

## Stack markers
`package.json` with `@angular/core`, `angular.json`, `src/app`. Ionic/Capacitor
wrappers keep the app process alive for days on a device, so a chatty client
exposes a slow backend leak faster than a browser tab would. SSR (`@angular/ssr`,
`server.ts`) is a Node process and is audited with `node-express.md`.

## Where the relevant code lives
`core/services/api.service.ts` (HTTP fan-out), `core/interceptors/` (retry,
polling, token refresh), WebSocket/SignalR services (`/ws` proxies), any
`interval()`/`timer()` polling loop, file upload/download components,
`environment.*.ts` (base URLs that decide which backend process takes the load),
`server.ts` for SSR.

## Dangerous / interesting APIs and patterns (as backend load sources)
- `interval(n).pipe(switchMap(() => this.http.get(...)))` polling that survives navigation - each tick is a backend request; if the backend leaks per request, the client sets the leak rate. Record the period.
- SignalR/WebSocket reconnect loops (`withAutomaticReconnect()` with no backoff, hand-rolled `setTimeout(connect, 0)`) - each reconnect creates a server-side connection object; a server that never disposes on close is exposed by the client's reconnect storm.
- `retry(3)` / `retryWhen` interceptors: one failing request becomes four backend allocations; mention when estimating hot-path allocation impact.
- Large uploads via `FormData` (images, Excel) - the backend side (ImageSharp, EPPlus) is where the disposal finding lives; record the client's max file size.
- Downloads with `responseType: 'blob'` - the server must dispose the stream after `File(...)`; list which endpoints stream.
- SSR `server.ts`: module-level caches, `TransferState` misuse, per-request `setInterval` - these are backend leaks; apply `node-express.md` patterns to `server.ts` and `src/server/**`.

## What "good" looks like
```ts
// polling bound to component lifetime, backend load stops with the view
interval(30_000).pipe(startWith(0), switchMap(() => this.api.get('stock')), takeUntilDestroyed()).subscribe(...);

// SignalR reconnect with backoff, so a flapping server is not hammered
new HubConnectionBuilder().withUrl(url).withAutomaticReconnect([0, 2000, 10000, 30000]).build();
```

## Manual trace checklist (for the backend audit)
1. List every polling loop with its period and endpoint - this is the real RPS for the load-test plan.
2. List WebSocket/SignalR endpoints and the reconnect policy.
3. List upload/download endpoints with payload sizes.
4. Note retry interceptors and their multipliers.
5. If SSR is present, treat `server.ts` as a Node backend and run the node-express pattern file on it.

## Stack-specific false positives
- `interval()` guarded by `takeUntilDestroyed()`/`async` pipe - bounded to the view (the client side is fine; the backend still handles each tick).
- `retry()` with `delay` and a cap - intended resilience.

## Tooling
DevTools Network tab (count requests per route over 5 minutes of idle to find polling), `ng build --configuration production` not needed here. Chrome DevTools > Memory belongs to the sibling skill.

## Hand-off
- Component/subscription/DOM leaks: `audit-frontend-memory-leak`.
- Excessive API calls per page, bundle and re-render cost: `audit-performance-and-scalability`, `audit-frontend-best-practices`.

## References
CWE-400 (client-driven resource consumption); Angular docs "HttpClient", "RxJS interop", "Server-side rendering".
