# React / Next.js reference for audit-production-readiness-checklist

The SPA/SSR frontend has its own readiness items: production build mode,
environment injection, debug artefacts, error reporting, degraded-mode
behaviour, and the rollback path. Next.js server code (route handlers, server
actions) is a backend: apply `node-express.md` to it as well.

## Stack markers
`package.json` with `react`/`next`; Vite (`vite.config.*`), CRA (`react-scripts`), Next (`next.config.*`); `.env*` with `NEXT_PUBLIC_*`/`VITE_*`/`REACT_APP_*`.

## Where each checklist item lives
- **Env config:** build-time public vars (`NEXT_PUBLIC_*`, `VITE_*`) from CI, not committed `.env.production` with real values; runtime config for Next.js server (`process.env` read on the server only); `next.config.js` `env`/`publicRuntimeConfig`. Fail: production API URL hard-coded, or `.env.production` committed with secrets.
- **Secrets:** any non-`NEXT_PUBLIC_` secret referenced in client components is shipped to the browser; server-only secrets in `.env*` committed = Critical (`audit-secrets-and-config`).
- **Debug off:** `NODE_ENV=production` in the build/run; Vite `build.sourcemap` false or hidden; CRA `GENERATE_SOURCEMAP=false`; Next `productionBrowserSourceMaps: false` (or upload-only); React DevTools/why-did-you-render/`redux-devtools` guarded; `console.log` stripped (`babel-plugin-transform-remove-console`, terser `drop_console`); Next `reactStrictMode` fine; `next dev` never used in the container.
- **Health checks:** static bundle: host/CDN probe; Next.js server: an unauthenticated route handler `app/api/health/route.ts` that pings dependencies (Prisma `$queryRaw`, Redis) - apply the Node checklist; Dockerfile `HEALTHCHECK` targets it.
- **Graceful degradation / shutdown:** error boundaries (`error.tsx`, `global-error.tsx`, `react-error-boundary`) reporting to Sentry; fetch wrapper mapping 5xx/timeouts; React Query `retry` only for queries, not mutations; Next server: SIGTERM handling is built into `next start` (confirm custom servers handle it).
- **Timeouts/retries:** `AbortSignal.timeout()` on `fetch`, axios `timeout`; React Query `retry`/`retryDelay` with backoff; SWR `errorRetryCount`.
- **Caching:** Next.js `fetch` cache/`revalidate`/ISR strategy documented; CDN cache headers; hashed assets and `index.html`/HTML routes with `no-cache` so releases and rollbacks propagate; React Query `staleTime`.
- **Load test:** API load tests; Lighthouse CI budgets (`lighthouserc.js`), `next build` bundle analysis.
- **Feature flags:** `@vercel/flags`, LaunchDarkly/Unleash/GrowthBook/OpenFeature React SDKs, or runtime config flags; route-level gating for risky screens.
- **Runbook / rollback:** static hosts keep previous builds (Vercel promote/rollback, S3 versioned + CloudFront invalidation, Netlify rollback); document the command; Next server rollback via image tag.
- **Alerting:** Sentry/Datadog RUM alert rules with release tags; Vercel/host monitoring.

## What "good" looks like
```js
// next.config.js
module.exports = { productionBrowserSourceMaps: false, reactStrictMode: true, compiler: { removeConsole: { exclude: ['error', 'warn'] } } };
// app/api/health/route.ts
export async function GET() { await prisma.$queryRaw`SELECT 1`; return Response.json({ status: 'ok' }); }
// lib/api.ts
export const api = (path, init) => fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, { ...init, signal: AbortSignal.timeout(15_000) });
```
```tsx
// app/global-error.tsx
'use client'; export default function GlobalError({ error }) { Sentry.captureException(error); return <FallbackPage />; }
```

## Manual trace checklist
1. Build pipeline: production mode, env injection, no committed `.env.production` secrets.
2. Error boundary + reporter configured with release version.
3. Next.js server: health route, SIGTERM, timeouts on server-side fetches (Node checklist).
4. Cache headers on HTML vs hashed assets; rollback command documented.

## Stack-specific false positives
- `.env.development`/`.env.local` with localhost values.
- `NEXT_PUBLIC_*` public keys (Firebase, Stripe publishable) in `.env.production`.
- Source maps uploaded to Sentry but not served (`hidden`).

## Tooling
- `ANALYZE=true next build` (`@next/bundle-analyzer`), `npx vite build --mode production` + `rollup-plugin-visualizer`.
- `npx lhci autorun` for budgets.

## References
- Next.js docs: Deploying, Going to production checklist, Environment variables, Error handling; Vite production build docs; Sentry React docs.
