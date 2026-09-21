# Angular reference for audit-concurrency-and-race-condition

## Stack markers
`package.json` with `@angular/core`, `angular.json`. Variants: NgModules vs standalone; RxJS-heavy services; NgRx/signals stores; Ionic/Capacitor (mobile networks retry more, offline queues replay).

## Where the relevant code lives
The server owns every race fix; the frontend's role here is (a) evidence of how a double submit happens in practice and (b) client-side mitigations that reduce, but never replace, server guards. Look in `*.component.ts` submit handlers, `core/interceptors/*` (retry logic), `core/services/api.service.ts` (`retry`, `retryWhen`, `timeout`), feature services with `switchMap`/`mergeMap` on mutations, offline/sync services, and templates with submit buttons (`[disabled]`, `(click)`).

## Dangerous / interesting APIs and patterns
- Submit handlers with no in-flight guard: `onPay() { this.api.post('/pay', ...).subscribe(...) }` and a button without `[disabled]="submitting"`; forms where Enter and click both trigger submit.
- `retry(n)` / `retryWhen` / interceptor-level retry applied to POST/PUT/DELETE (each retry is a replay; if the server has no idempotency key this doubles charges); `timeout()` followed by user-visible error while the first request still completes server-side.
- `mergeMap` on a mutation stream (parallel submits) where `exhaustMap` (ignore while in flight) or `switchMap` (cancel client-side only; the server still processes the first) is intended. `switchMap` on POST is a common misconception: cancelling the subscription does not cancel the server work.
- Polling/refresh (`interval().pipe(switchMap(() => load()))`) racing with an edit: stale data overwrites a form in progress; PUT sends stale fields (lost update) when the server has no version/ETag.
- Optimistic UI updates without reconciliation: local state updated before the server responds, and no rollback or refetch on 409.
- Offline queues (Ionic/Capacitor, service worker background sync) that replay mutations without a client-generated idempotency key.
- Multiple tabs: `localStorage` state shared across tabs; two tabs submitting the same cart; `BroadcastChannel` absent.
- Double-click on `(click)` without `debounceTime` or a `submitting` flag; `ngSubmit` plus `(click)` on the submit button (fires twice).

## What "good" looks like
```ts
// one in-flight mutation at a time, key generated client-side
submitting = signal(false);
pay() {
  if (this.submitting()) return;
  this.submitting.set(true);
  const key = crypto.randomUUID();                        // reused if the user retries the same intent
  this.api.post('/orders/pay', body, { headers: { 'Idempotency-Key': key } })
    .pipe(finalize(() => this.submitting.set(false))).subscribe(...);
}
// streams: exhaustMap for submits
this.submit$.pipe(exhaustMap(() => this.api.post(...)))
// retries only on idempotent methods
intercept(req, next) { return next.handle(req).pipe(req.method === 'GET' ? retry(2) : tap()); }
// optimistic concurrency at the edge
this.api.put(url, dto, { headers: { 'If-Match': etag } })  // handle 409/412 by reloading
```
`[disabled]="submitting()"` on the button; a client key sent with every mutation the server treats as idempotent; 409 handling that reloads and asks the user to retry.

## Manual trace checklist
1. For each money/stock/uniqueness mutation the backend audit flagged, find the client trigger: is there an in-flight guard, a client key, and is retry disabled for it.
2. `grep -rn "retry(\|retryWhen(" src/app`: what methods do the retries wrap.
3. `grep -rn "mergeMap\|switchMap" src/app | grep -i "post\|put\|delete\|save\|submit\|pay"`: parallel/cancelled submits.
4. Offline/sync services: keys on queued mutations; replay order.
5. Edit forms: ETag/version sent on PUT; behaviour on 409.

## Stack-specific false positives
- `retry` on GET/HEAD only.
- `switchMap` on search/autocomplete (idempotent GETs).
- Optimistic UI with refetch on error.
- Button disabling alone is UX, not a fix: record it as "client mitigation present" in the inventory, not as closing the finding.

## Tooling
`grep -rn "\[disabled\]" src/app --include=*.html | grep -i "submit\|pay\|save"`; Angular DevTools / Network tab with throttling to reproduce a double click; `scripts/double_submit.sh` against the API with the client's exact payload.

## References
CWE-362, ASVS 11.1.4 (anti-automation / double submit); RxJS `exhaustMap` docs; Stripe idempotent requests (client-generated keys). The backend reference for this stack pair owns the server-side finding.
