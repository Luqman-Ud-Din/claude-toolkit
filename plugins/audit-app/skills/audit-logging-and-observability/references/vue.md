# Vue / Nuxt reference for audit-logging-and-observability

The frontend owns the **first hop** of the correlation chain (frontend ->
backend -> downstream), the client error pipeline, and keeping tokens and form
secrets out of the console and the monitoring vendor. Nuxt server routes
(`server/api/*`) are backend code and follow `node-express.md`. Token storage
belongs to `audit-client-auth-and-storage`; headers/CSP to
`audit-security-headers-and-middleware`.

## Stack markers

`package.json` with `vue` (and `nuxt` for Nuxt 3). Monitoring: `@sentry/vue`,
`@sentry/nuxt`, `@datadog/browser-rum`, `@opentelemetry/sdk-trace-web`,
`nuxt-logrocket`. State: `pinia`, `pinia-plugin-persistedstate`, Vuex `createLogger`.

## Where the relevant code lives

- `src/main.(ts|js)` - `createApp`, `app.config.errorHandler`, `app.config.warnHandler`, Sentry init.
- `src/api/*.ts`, `src/plugins/axios.ts` - axios instance and interceptors.
- Nuxt: `plugins/*.ts` (`$fetch` / `ofetch` `onRequest` hooks), `app.vue`,
  `error.vue`, `nuxt.config.ts` (`runtimeConfig.public`), `server/` (Nitro logs).
- `src/stores/*` and `src/store/index` - Pinia plugins, Vuex `plugins: [createLogger()]`.
- Login/register components - `console.*` of `v-model` form state.

## Dangerous / interesting APIs and patterns

- `console.log(form)` / `console.log(this.password)` / `console.log(authStore.token)`;
  `console.error(error)` for an axios error (includes headers and request data).
- Vuex `createLogger()` or a Pinia `$subscribe` / `$onAction` logging plugin active in
  production - every mutation prints the auth store including tokens.
- `app.config.errorHandler = (err) => console.error(err)` only - errors never
  leave the browser; or no handler at all.
- `Sentry.init({ app, ... })` with no `beforeSend`, `sendDefaultPii: true`,
  or Session Replay without `maskAllInputs` / `maskAllText`.
- axios / `ofetch` hooks that add `Authorization` but no `X-Correlation-Id` / `traceparent`.
- Nuxt Nitro handlers using `console.log(await readBody(event))`.

## What "good" looks like

```ts
// main.ts
const app = createApp(App);
Sentry.init({
  app, dsn: import.meta.env.VITE_SENTRY_DSN, tracesSampleRate: 0.1,
  tracePropagationTargets: [/^https:\/\/api\.example\.com/],
  beforeSend: (e) => { if (e.request) { delete e.request.data; delete e.request.cookies; } return e; },
});
app.config.errorHandler = (err, _instance, info) => Sentry.captureException(err, { extra: { info } });

// api/http.ts - first hop
http.interceptors.request.use((cfg) => { cfg.headers['X-Correlation-Id'] = crypto.randomUUID(); return cfg; });

// Nuxt plugins/api.ts
export default defineNuxtPlugin(() => ({ provide: { api: $fetch.create({
  onRequest({ options }) {
    options.headers = new Headers(options.headers);
    options.headers.set('X-Correlation-Id', crypto.randomUUID());
  },
}) } }));

// store - development only
const plugins = import.meta.env.DEV ? [createLogger()] : [];
```

Vite production build: `esbuild: { drop: ['console', 'debugger'] }`. OTel web:
`FetchInstrumentation` / `XMLHttpRequestInstrumentation` with `propagateTraceHeaderCorsUrls`.

## Manual trace checklist

1. HTTP layer: correlation / trace header on every API call to the app's own origin.
2. `app.config.errorHandler` plus `window.addEventListener('unhandledrejection')` ship errors.
3. Scrubbing: `beforeSend`, Replay masking, no request bodies or tokens.
4. Store plugins: no logger or action-tracing plugin in production.
5. Auth components: no `console.*` of credentials; console dropped in the production build.
6. Nuxt server routes: logger, request id and body logging per `node-express.md`.

## Stack-specific false positives

- `console.*` in `*.spec.ts`, vitest setup, Storybook.
- `createLogger` imported but only registered when `import.meta.env.DEV`.
- `runtimeConfig.public.sentryDsn` - a public identifier, not a secret.
- `app.config.warnHandler` logging Vue warnings in development.

## Tooling

```bash
npm ls @sentry/vue @sentry/nuxt pinia @opentelemetry/sdk-trace-web
grep -rnE "console\.(log|debug|info|error)\(" src --include=*.ts --include=*.js --include=*.vue
grep -rnE 'createLogger\(|\$subscribe|\$onAction' src
grep -rnE "errorHandler|X-Correlation-Id|traceparent|beforeSend" src
```
ESLint `no-console` (eslint-plugin-vue projects inherit it).

## References

- Vue `app.config.errorHandler`; Nuxt error handling; Sentry Vue data scrubbing.
- OpenTelemetry JS web; W3C Trace Context.
- CWE-532, CWE-778; ASVS 7.1; OWASP A09:2021.
