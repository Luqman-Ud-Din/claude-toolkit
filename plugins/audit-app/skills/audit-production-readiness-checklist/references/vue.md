# Vue / Nuxt reference for audit-production-readiness-checklist

The Vue SPA or Nuxt app has its own readiness items: production build mode,
environment injection, debug artefacts, error reporting, degraded-mode
behaviour, and the rollback path. Nuxt `server/` code is a backend: apply
`node-express.md` to it as well.

## Stack markers
`package.json` with `vue`/`nuxt`; `vite.config.*`, `nuxt.config.*`; `.env*` with `VITE_*`/`NUXT_PUBLIC_*`/`NUXT_*`.

## Where each checklist item lives
- **Env config:** Nuxt `runtimeConfig` (server) and `runtimeConfig.public` (client) overridden by `NUXT_*` env vars at runtime - the right pattern; Vite `VITE_*` build-time vars from CI. Fail: production URLs hard-coded in `nuxt.config`/services, or `.env.production` committed with real values.
- **Secrets:** anything under `runtimeConfig.public` or `VITE_*` is public; server secrets committed in `.env*` = Critical (`audit-secrets-and-config`).
- **Debug off:** `NODE_ENV=production` for `nuxt build`/`nuxt start`; `sourcemap: { client: false }` (or hidden), `vite.build.sourcemap` false; Vue Devtools (`devtools: { enabled: false }` in prod, `app.config.performance` off); `console.log` stripped (`esbuild.drop: ['console']`); `nuxt dev` never used in the container; Nitro `debug` off.
- **Health checks:** static SPA: host/CDN probe; Nuxt server: `server/api/health.get.ts` pinging dependencies, unauthenticated, targeted by `HEALTHCHECK`/probes (Node checklist).
- **Graceful degradation / shutdown:** `app.config.errorHandler`/`onErrorCaptured`, Nuxt `error.vue` + `useError`, reporting to Sentry; `$fetch`/`ofetch` `timeout` and `retry` options (retry only GETs); Nitro handles SIGTERM in `nuxt start` (confirm for custom servers/presets).
- **Timeouts/retries:** `$fetch(url, { timeout: 15000, retry: 2, retryDelay: 500 })`, `useFetch` options; axios `timeout`.
- **Caching:** Nuxt `routeRules` (`swr`, `isr`, `cache`), Nitro storage/cache; CDN headers; hashed assets and HTML `no-cache` for release propagation; Pinia persisted state versioning.
- **Load test:** API load tests; Lighthouse CI budgets; `nuxt analyze`.
- **Feature flags:** Unleash/LaunchDarkly/GrowthBook/OpenFeature JS SDKs, `runtimeConfig.public.features`; route middleware gating risky pages.
- **Runbook / rollback:** static host rollback (Netlify/Vercel/S3 version), Nuxt server via image tag; documented command.
- **Alerting:** Sentry/Datadog RUM alert rules with release tags.

## What "good" looks like
```ts
// nuxt.config.ts
export default defineNuxtConfig({
  runtimeConfig: { apiSecret: '', public: { apiBase: '' } },   // filled by NUXT_API_SECRET / NUXT_PUBLIC_API_BASE
  sourcemap: { server: true, client: false },
  devtools: { enabled: process.env.NODE_ENV !== 'production' },
  routeRules: { '/dashboard/**': { swr: 60 } },
});
// server/api/health.get.ts
export default defineEventHandler(async () => { await db.raw('select 1'); return { status: 'ok' }; });
// plugins/api.ts
const api = $fetch.create({ baseURL: config.public.apiBase, timeout: 15000, retry: 1 });
```

## Manual trace checklist
1. Build/run pipeline: production mode, `NUXT_*`/`VITE_*` injection, no committed secrets.
2. Error handler + reporter with release version.
3. Nuxt server: health route, timeouts on server-side fetches, SIGTERM (Node checklist).
4. Cache headers on HTML vs hashed assets; rollback command documented.

## Stack-specific false positives
- `.env.development`/`.env.local` with localhost values.
- `runtimeConfig.public` holding public keys.
- `devtools: { enabled: true }` guarded by environment.

## Tooling
- `npx nuxi analyze`, `npx vite build --mode production` + visualizer; `npx lhci autorun`.

## References
- Nuxt docs: Runtime config, Deployment, Error handling, Route rules; Vite production build; Sentry Vue/Nuxt docs.
