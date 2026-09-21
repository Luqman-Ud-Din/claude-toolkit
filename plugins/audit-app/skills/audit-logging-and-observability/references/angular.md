# Angular reference for audit-logging-and-observability

The frontend owns three pieces of this topic: it is the **first hop** of the
correlation chain (frontend -> backend -> downstream), it decides what browser
errors reach a monitoring tool, and it must not write tokens or form secrets to
the console or to that tool. What the backend logs is owned by the backend stack
file (`dotnet.md`, `node-express.md`, ...); token storage belongs to
`audit-client-auth-and-storage`; CSP/security headers to
`audit-security-headers-and-middleware`.

## Stack markers

`angular.json`, `package.json` with `@angular/core`. Monitoring libraries:
`@sentry/angular`, `@microsoft/applicationinsights-web` (+ `-angularplugin-js`),
`@opentelemetry/sdk-trace-web`, `@datadog/browser-rum` / `browser-logs`,
`@newrelic/browser-agent`, `ngx-logger`.

## Where the relevant code lives

- `src/app/core/interceptors/*.interceptor.ts` - where a correlation header is
  (or is not) added; functional `HttpInterceptorFn` registered in `provideHttpClient(withInterceptors([...]))`
  or class interceptors in `HTTP_INTERCEPTORS`.
- `src/app/core/*error-handler*.ts` - custom `ErrorHandler` provider.
- `src/main.ts`, `app.config.ts`, `app.module.ts` - Sentry/App Insights/OTel init.
- `src/environments/environment*.ts` - DSNs, instrumentation keys, log level flags.
- Services and components - `console.*` calls.

## Dangerous / interesting APIs and patterns

- `console.log(token)`, `console.log(this.authService.user)`, `console.log(form.value)`
  on login/register/change-password forms, `console.error(err)` where `err` is an
  `HttpErrorResponse` (includes request URL with query tokens and the response body).
- `console.*` left in production builds with no `environment.production` guard or
  build-time stripping (Terser `drop_console`, esbuild `drop: ['console']`).
- `Sentry.init({ ... })` without `beforeSend` / `beforeBreadcrumb` scrubbing, or
  with `sendDefaultPii: true`; breadcrumbs capture XHR URLs and console output.
- App Insights `enableAutoRouteTracking` plus `trackPageView` with query strings
  carrying reset tokens; `addTelemetryInitializer` absent.
- Interceptor that sets `Authorization` but no `X-Correlation-Id` / `traceparent` -
  the backend cannot tie a user-reported error to a request.
- `ErrorHandler` that only `console.error`s - production errors never leave the browser.
- `ngx-logger` with `serverLoggingUrl` and `NgxLoggerLevel.DEBUG` in production.

## What "good" looks like

```ts
// correlation.interceptor.ts - first hop of the chain
export const correlationInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith(environment.apiBaseUrl)) return next(req);   // own API only
  return next(req.clone({ setHeaders: { 'X-Correlation-Id': crypto.randomUUID() } }));
};

// app.config.ts
Sentry.init({
  dsn: environment.sentryDsn, environment: environment.name, tracesSampleRate: 0.1,
  tracePropagationTargets: [environment.apiBaseUrl],       // adds sentry-trace + baggage
  beforeSend(event) { delete event.request?.cookies; if (event.request?.data) event.request.data = '[redacted]'; return event; },
});
providers: [{ provide: ErrorHandler, useValue: Sentry.createErrorHandler({ showDialog: false }) }]
```

OpenTelemetry web: `WebTracerProvider` with `FetchInstrumentation` and
`XMLHttpRequestInstrumentation` configured with
`propagateTraceHeaderCorsUrls: [/^https:\/\/api\.example\.com/]` so `traceparent`
reaches the backend (the backend CORS policy must allow the header). Show the
correlation id in the user-facing error toast so support can quote it.

## Manual trace checklist

1. Interceptor chain: is a correlation/trace header added to API calls, only to
   the app's own origin, and read back from the response on errors?
2. `ErrorHandler`: errors shipped to a monitoring tool with release/environment tags.
3. Scrubbing: `beforeSend`/telemetry initializer removes tokens, cookies, form data, query tokens.
4. Login/register/reset components: no `console.*` of form values or tokens.
5. Production build config: console stripped or guarded; source maps uploaded to the
   monitoring tool, not served publicly.
6. RUM: page-load and API latency collected (Web Vitals) so latency alerts have client data.

## Stack-specific false positives

- `console.*` in `*.spec.ts`, `environment.ts` (dev), Storybook stories.
- `console.warn` for deprecation notices with no data arguments.
- `Authorization` in an interceptor - that is attaching, not logging.
- DSN / instrumentation key in environment files - public by design (not a secret).

## Tooling

```bash
npm ls @sentry/angular @microsoft/applicationinsights-web @opentelemetry/sdk-trace-web ngx-logger
grep -rnE "console\.(log|debug|info|warn|error)\(" src --include=*.ts | grep -v "\.spec\.ts"
grep -rnE "X-Correlation-Id|traceparent|propagateTraceHeaderCorsUrls|tracePropagationTargets" src
grep -rn "beforeSend\|addTelemetryInitializer" src
```
ESLint `no-console` (error in production lint config).

## References

- Angular `ErrorHandler`, `HttpInterceptorFn`; Sentry Angular data scrubbing.
- OpenTelemetry JS web: `@opentelemetry/sdk-trace-web`, fetch/XHR instrumentation.
- W3C Trace Context; CWE-532, CWE-778; ASVS 7.1; OWASP A09:2021.
