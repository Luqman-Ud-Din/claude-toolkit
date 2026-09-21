# Angular reference for audit-async-and-dependency-injection

This skill is backend-focused, but Angular has a real DI container with the
same captive-dependency shape, and its async layer (RxJS + `HttpClient`) has the
same "unobserved error" and "no cancellation" mistakes. Use this file for the
frontend half when the audited repo is Angular; component/subscription leaks
stay with `audit-frontend-memory-leak`, and runtime cost with
`audit-performance-and-scalability` / `audit-frontend-best-practices`.

## Stack markers
`package.json` with `@angular/core`; `angular.json`. Container: Angular DI (`providedIn: 'root'` = app singleton; component/route `providers: [...]` = per component tree / per lazy module injector; `providedIn: 'any'` = per lazy module). SSR (`@angular/ssr`) adds a per-request platform injector - the classic captive bug on the server is a root singleton caching per-user data across requests.

## Where the relevant code lives
`core/services/*.ts` (`@Injectable({ providedIn: 'root' })`), `core/interceptors/*.ts` (token, retry, error), feature `providers: [...]` arrays, `app.config.ts`/`app.module.ts` (`provideHttpClient(withInterceptors(...))`), `*.component.ts` (`subscribe(...)` without error handler, `firstValueFrom`), `server.ts` for SSR.

## Dangerous / interesting APIs and patterns
- DI: root singleton service injecting a component-provided (short-lived) service - impossible by construction (Angular throws `NullInjectorError`) but the *reverse* smell exists: a component-level provider that should be shared is re-created per component (duplicate HTTP calls, state divergence). SSR: root services holding per-request user/tenant state (`currentUser` field on a `providedIn: 'root'` service) - shared across concurrent SSR requests; must be `REQUEST`-token based or per-request provided. `inject()` outside an injection context; manual `new Service()` bypassing DI; services that read `localStorage`/`window` in constructors (breaks SSR).
- VOID (errors lost): `.subscribe(next)` with no error callback - HTTP errors surface only as console noise; `subscribe()` inside a service method returning nothing (caller cannot observe failure); `firstValueFrom(obs)` in an `async` method whose promise the caller does not await; `catchError(() => EMPTY)` blanket swallows.
- CANCEL: HTTP calls not tied to component lifetime (`takeUntilDestroyed`), typeahead without `switchMap` (stale responses race), route change not cancelling in-flight requests, `AbortSignal` unavailable in `HttpClient` - cancellation is unsubscribe; resolvers that cannot be cancelled by navigation.
- FIRE: `this.api.post(...).subscribe()` with no handler for a save/pay action (user gets no feedback on failure); `void this.doAsync()`.
- BLOCK: `async` pipe misuse is not blocking, but synchronous XHR (`xhr.open(..., false)`), `while` loops waiting on flags, and heavy sync work in `ngOnInit` (parsing MBs of JSON) block the UI thread - INP impact, hand to performance skill.
- HTTP/TIMEOUT: no `timeout()` operator on requests; retry interceptor without backoff (`retry(3)` hammering a failing backend); no global error interceptor.

## What "good" looks like
```ts
@Injectable({ providedIn: 'root' })
export class InvoiceService {
  private readonly http = inject(HttpClient);
  submit(dto: InvoiceDto): Observable<InvoiceResult> {
    return this.http.post<InvoiceResult>('/api/invoices', dto).pipe(timeout(10_000), retry({ count: 2, delay: (e, n) => timer(n * 1000) }));
  }
}
// component: errors observed, cancelled on destroy
this.invoices.submit(dto).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({ next: r => this.done(r), error: e => this.toast.error(e) });
// typeahead: stale responses cancelled
this.search.valueChanges.pipe(debounceTime(300), switchMap(q => this.api.search(q)), takeUntilDestroyed());
// SSR: per-request state
providers: [{ provide: REQUEST_CONTEXT, useFactory: () => inject(REQUEST)?.headers['x-tenant'] }]
```

## Manual trace checklist
1. Root services with mutable per-user/per-tenant fields - fine in the browser, a cross-request leak under SSR.
2. Component-level `providers` for services that hold shared state - duplicated instances.
3. `subscribe(` calls: error callback or global interceptor?
4. Save/pay actions: result observed and shown?
5. Interceptors: timeout and retry-with-backoff present?

## Stack-specific false positives
- `subscribe()` with no args on a fire-and-forget telemetry call that has its own `catchError`.
- Component-level providers for genuinely per-component state (form scope).

## Tooling
`@angular-eslint` rules `rxjs/no-ignored-subscription`, `rxjs/no-ignored-error`, `rxjs-angular/prefer-takeuntil` (via `eslint-plugin-rxjs`); Angular DevTools Injector tree (see where a service is provided); `ng build --configuration production` warnings for `inject()` misuse.

## Hand-off
Subscription/DOM leaks: `audit-frontend-memory-leak`. Duplicate calls, render cost: `audit-performance-and-scalability`, `audit-frontend-best-practices`.

## References
CWE-390, CWE-400; Angular docs "Dependency injection in Angular - provider scopes", "HttpClient - interceptors", "Server-side rendering - request context"; RxJS docs `timeout`, `retry`, `switchMap`.
