# Angular reference for audit-production-readiness-checklist

The frontend has its own readiness items: production build configuration,
environment files, debug artefacts, error reporting, degraded-mode behaviour
when the API is down, and the release/rollback path for a static bundle or a
Capacitor app. Security details of the client belong to
`audit-client-auth-and-storage` and `audit-frontend-xss-and-dom-safety`.

## Stack markers
`angular.json`, `package.json` with `@angular/core`, `src/environments/environment*.ts`, `ngsw-config.json` (PWA), `capacitor.config.ts` (mobile).

## Where each checklist item lives
- **Env config:** `fileReplacements` in `angular.json` per configuration (`environment.prod.ts` replaces `environment.ts`), or runtime config (`assets/config.json` fetched at boot, `APP_INITIALIZER`). Fail: production API URL hard-coded in services, or `ng build` without `--configuration production` in the pipeline.
- **Secrets:** anything in `environment*.ts` is public - Firebase keys are fine, server API keys/secrets are not (`audit-secrets-and-config`); note it here as a blocker only if a server secret is present.
- **Debug off:** production configuration has `optimization: true`, `sourceMap: false` (or hidden source maps uploaded to the error tracker only), `namedChunks: false`; `enableProdMode()`/`isDevMode()` guards; `console.log` stripped or `LoggerService` level set; `ng serve` proxy files not used in prod; Angular DevTools/`ng.probe` not exposed.
- **Health checks:** a static bundle has no health endpoint; the CDN/host probe and the API `/health` matter. For Capacitor apps: a startup connectivity check with a friendly offline screen.
- **Graceful degradation (instead of shutdown):** global `ErrorHandler` reporting to Sentry/AppInsights; HTTP interceptor mapping 5xx/timeout to user messages; retry only for idempotent GETs; offline handling for PWA (`ngsw-config.json` `dataGroups` strategies).
- **Timeouts/retries:** `timeout()` operator on HTTP calls or interceptor-level timeout; `retry({ count, delay })` with backoff on GETs only.
- **Caching:** service-worker caching strategy (`ngsw-config.json` `assetGroups`/`dataGroups`), cache-busting via hashed filenames (`outputHashing: all`), `index.html` served with no-cache so new releases roll out.
- **Load test:** not for the bundle; Lighthouse/bundle-size budgets (`budgets` in `angular.json`) and API load tests.
- **Feature flags:** runtime config flags or a flag SDK on the client mirroring the server's; route-level toggles for risky screens.
- **Runbook / rollback:** how to roll back a static deploy (previous build artefact, CDN version) and a mobile release (store rollback is slow - flag-based kill switch needed); `buildApps.js`/Capacitor release notes.
- **Alerting:** client error tracker configured with release/version tags and alert rules (Sentry, AppInsights).

## What "good" looks like
```json
// angular.json (production)
"optimization": true, "sourceMap": { "scripts": false, "styles": false, "hidden": true }, "outputHashing": "all",
"budgets": [{ "type": "initial", "maximumWarning": "2mb", "maximumError": "3mb" }],
"fileReplacements": [{ "replace": "src/environments/environment.ts", "with": "src/environments/environment.prod.ts" }]
```
```ts
// core/interceptors/timeout.interceptor.ts
return next.handle(req).pipe(timeout(15_000), catchError(err => this.notify.mapAndReport(err)));
// app.config.ts
{ provide: ErrorHandler, useClass: SentryErrorHandler }
```

## Manual trace checklist
1. CI build command uses the production configuration; `environment.prod.ts` points at the production gateway only.
2. Global `ErrorHandler` and HTTP error interceptor exist and report somewhere monitored.
3. `index.html` cache headers and hashed assets: a rollback or new release actually reaches users.
4. Mobile: kill switch/forced-update mechanism for a bad release.

## Stack-specific false positives
- `sourceMap: true` in the development configuration.
- Firebase/public API keys in `environment.prod.ts`.
- `console.log` inside a `LoggerService` gated by environment.

## Tooling
- `ng build --configuration production --stats-json` then `npx webpack-bundle-analyzer dist/**/stats.json` (read-only on the repo).
- `npx lighthouse <staging-url>` for performance budgets.

## References
- Angular deployment guide (production builds, budgets), Angular service worker config, Sentry Angular docs.
