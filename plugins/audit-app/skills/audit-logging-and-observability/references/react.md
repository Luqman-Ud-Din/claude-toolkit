# React reference for audit-logging-and-observability

The frontend owns the **first hop** of the correlation chain (frontend ->
backend -> downstream), the client error pipeline, and keeping tokens and form
secrets out of the console and out of the monitoring vendor. What the backend
logs is owned by the backend stack file; token storage by
`audit-client-auth-and-storage`; CSP and headers by
`audit-security-headers-and-middleware`.

## Stack markers

`package.json` with `react` / `react-dom`, often `next`, `vite`, `react-scripts`.
Monitoring: `@sentry/react` / `@sentry/nextjs`, `@datadog/browser-rum`,
`@microsoft/applicationinsights-react-js`, `@opentelemetry/sdk-trace-web`,
`logrocket`, `web-vitals`. State loggers: `redux-logger`, Redux DevTools.

## Where the relevant code lives

- `src/api/client.(ts|js)`, `src/lib/http*`, `src/services/api*` - axios instance
  and interceptors, or a `fetch` wrapper.
- `src/main.tsx` / `index.tsx` / `_app.tsx` / `instrumentation-client.ts` (Next) -
  monitoring init, `ErrorBoundary`, `reportWebVitals`.
- `src/store/*` - middleware list (`redux-logger`, persistence).
- `components/ErrorBoundary*`, `app/error.tsx` / `global-error.tsx` (Next App Router).
- Login/register/reset pages - `console.*` of form state.

## Dangerous / interesting APIs and patterns

- `console.log(token)`, `console.log(user)`, `console.log(values)` in a Formik /
  react-hook-form `onSubmit` for login or password change; `console.error(error)`
  for an axios error (contains `config.headers.Authorization` and `config.data`).
- `applyMiddleware(logger)` / `middleware: [logger]` without a
  `process.env.NODE_ENV !== 'production'` guard - the whole store, including
  `auth.accessToken`, printed on every action.
- `componentDidCatch` / `ErrorBoundary onError` that only `console.error`s -
  production errors never leave the browser.
- `Sentry.init` without `beforeSend` / `beforeBreadcrumb`, `sendDefaultPii: true`,
  or LogRocket without `network.requestSanitizer` / `dom.inputSanitizer`.
- axios interceptor that sets `Authorization` but no `X-Correlation-Id`, or a
  `fetch` wrapper with no header at all - support cannot tie a user report to a request.
- `window.onerror` / `unhandledrejection` never handled.

## What "good" looks like

```ts
// api/client.ts - first hop of the chain
api.interceptors.request.use((cfg) => {
  cfg.headers['X-Correlation-Id'] = crypto.randomUUID();
  return cfg;
});
api.interceptors.response.use(undefined, (err) => {
  const cid = err.config?.headers?.['X-Correlation-Id'];
  Sentry.captureException(err, { tags: { correlationId: cid } });   // never config.data
  return Promise.reject(err);
});

// main.tsx
Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN, tracesSampleRate: 0.1,
  tracePropagationTargets: [/^https:\/\/api\.example\.com/],
  beforeSend: (e) => { if (e.request) { delete e.request.cookies; delete e.request.data; } return e; },
});
<Sentry.ErrorBoundary fallback={<ErrorPage />}><App /></Sentry.ErrorBoundary>

// store.ts - state logger in development only
middleware: (gDM) => (import.meta.env.DEV ? gDM().concat(logger) : gDM()),
```

Web Vitals: `onLCP/onINP/onCLS(sendToAnalytics)` so client-side latency is measured.
OTel web: `FetchInstrumentation({ propagateTraceHeaderCorsUrls: [/api\.example\.com/] })`
so `traceparent` reaches the backend (its CORS policy must allow the header).

## Manual trace checklist

1. HTTP client: correlation or `traceparent` header on every API call, own origin only.
2. Error boundary and global handlers ship errors with release and correlation id.
3. Scrubbing hooks remove request bodies, cookies, tokens and input values.
4. Store middleware: no state logger in production builds.
5. Auth pages: no `console.*` of credentials; production build drops console
   (`esbuild.drop`, Terser `drop_console`, `babel-plugin-transform-remove-console`).
6. Next.js server components / route handlers: their logs follow `node-express.md`.

## Stack-specific false positives

- `console.*` in `*.test.tsx`, `*.stories.tsx`, `setupTests`.
- `redux-logger` imported but only added in a `DEV` branch.
- Sentry DSN / RUM client token in env files - public identifiers, not secrets.
- `console.warn` from a development-only `propTypes` check.
- `Authorization` set in an interceptor - that is attaching a credential, not logging it.

## Tooling

```bash
npm ls @sentry/react @datadog/browser-rum redux-logger web-vitals @opentelemetry/sdk-trace-web
grep -rnE "console\.(log|debug|info|error)\(" src --include=*.ts --include=*.tsx --include=*.js --include=*.jsx
grep -rnE "redux-logger|createLogger\(" src
grep -rnE "X-Correlation-Id|traceparent|tracePropagationTargets|beforeSend" src
```
ESLint `no-console`; check `vite.config` / `next.config` for console stripping.

## References

- React error boundaries; Sentry React data scrubbing; web-vitals.
- OpenTelemetry JS web instrumentation; W3C Trace Context.
- CWE-532, CWE-778; ASVS 7.1; OWASP A09:2021.
