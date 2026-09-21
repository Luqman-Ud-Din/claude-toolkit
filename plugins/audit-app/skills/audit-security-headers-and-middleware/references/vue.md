# Vue (Vite SPA, Nuxt, Quasar) reference for audit-security-headers-and-middleware

Headers and middleware are set by whatever serves the app. For a Vite SPA that
is the host (nginx, Netlify, Vercel, Firebase); for Nuxt it is Nitro
(`nuxt.config.ts` `routeRules` headers, `server/middleware/**`), which is a
real server pipeline. The API is audited with the backend stack file.

## Stack markers
`package.json` with `vue` (+ `vite`), `nuxt`, `quasar`. Hosting configs: `nginx.conf`, `_headers`, `vercel.json`, `netlify.toml`, `firebase.json`, `staticwebapp.config.json`; Nuxt: `nuxt.config.ts` (`routeRules: { '/**': { headers } }`, `nitro.routeRules`, `security` module `nuxt-security`), `server/middleware/*.ts` (runs on every request, order = filename order), `server/api/**` (API routes - apply `node-express.md` rules: `setCookie`, CORS via `setResponseHeaders`, `readBody` limits); Quasar: `quasar.config.js` `devServer`, `ssr` config.

## Where the relevant code lives
`index.html` (meta CSP fallback), `vite.config.ts` (`server.proxy` dev only, `build.sourcemap`), `nuxt.config.ts` (`routeRules`, `app.head.meta` CSP, `runtimeConfig.public.apiBase`), `server/middleware/**` (auth checks, header injection via `setResponseHeader`), `server/api/**` (`setCookie(event, name, value, { httpOnly, secure, sameSite })`, `handleCors`, `readBody`/`readMultipartFormData`), `composables/useApi.ts` (`credentials: 'include'` and CSRF header), `plugins/**`.

## What this skill checks on the frontend
- **Hosting headers** (SPA): host config must emit CSP, HSTS, X-Content-Type-Options, X-Frame-Options/`frame-ancestors`, Referrer-Policy, Permissions-Policy; `Cache-Control: no-store` for `index.html`, immutable for hashed assets. No config in the repo = Medium and live check required.
- **Nuxt headers**: `routeRules['/**'].headers` or `nuxt-security` module present; CSP: Vue/Nuxt production builds do not need `'unsafe-eval'`; hydration payload is JSON (no inline script needed since Nuxt 3 uses `<script type="application/json">`), so `script-src 'self'` is achievable; `style-src 'unsafe-inline'` may be needed for scoped styles in SSR (Low note); `nuxt-security` defaults are strict - check overrides (`headers: { contentSecurityPolicy: false }`).
- **Nuxt server middleware order**: `server/middleware/*.ts` run alphabetically for every request before routes - an auth middleware named `zz-auth.ts` after a `cors.ts` is fine; a `01-auth.ts` before `02-cors.ts` blocks preflights; header middleware must set headers on the response, not throw.
- **API routes** (Nuxt): `setResponseHeader(event, 'Access-Control-Allow-Origin', '*')` with credentials; `setCookie` without `httpOnly/secure/sameSite`; `readBody` has no size limit (Nitro `bodyLimit`? - none built in; rely on proxy or check `Content-Length` in middleware) - note; rate limiting on `server/api/auth/*` (`nuxt-security` `rateLimiter`, or `h3` + `unstorage` counter).
- **CSRF**: cookie sessions (`nuxt-auth-utils`, `@sidebase/nuxt-auth`, `h3` sessions) - `nuxt-security` provides `csrf`; otherwise Origin checks; client must send the CSRF header when `credentials: 'include'`.
- **Meta CSP** in `index.html`/`app.head.meta`: fallback only; no `frame-ancestors`.
- **Dev artefacts**: `vite.config.ts` `server.proxy`, `build.sourcemap: true` in prod, `runtimeConfig.public.apiBase` with `http://`.

## What "good" looks like
```ts
// nuxt.config.ts
export default defineNuxtConfig({
  routeRules: {
    '/**': { headers: {
      'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.example.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
      'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
      'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'strict-origin-when-cross-origin', 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()' } },
    '/index.html': { headers: { 'Cache-Control': 'no-store' } },
    '/_nuxt/**': { headers: { 'Cache-Control': 'public, max-age=31536000, immutable' } },
  },
});
// server/api/auth/refresh.post.ts
setCookie(event, 'refresh_token', rt, { httpOnly: true, secure: true, sameSite: 'strict', path: '/api/auth/refresh', maxAge: 14 * 86400 });
```
Or `modules: ['nuxt-security']` with its defaults (CSP, HSTS, rate limiter, CSRF, request size limits) and documented overrides. Vite SPA on nginx: same `add_header ... always;` block as in `angular.md`.

## Manual trace checklist
1. Locate the header source (host config, `routeRules`, `nuxt-security`); if none, record it and rely on the live check.
2. CSP directives vs real third-party hosts; `'unsafe-eval'`/`*` presence.
3. Nuxt `server/middleware` order and behaviour; `server/api` cookies, CORS, body handling, rate limiting on auth routes.
4. Cookie-auth apps: CSRF strategy and client header.
5. `sourcemap` and `http://` origins in production config.

## Stack-specific false positives
- `style-src 'unsafe-inline'` for SSR scoped styles - Low note.
- `nuxt-security` present with defaults - most headers pass without explicit config; verify overrides only.
- `server.proxy` in `vite.config.ts` - dev only.

## Tooling
- `python scripts/check_headers.py https://app.example.com` (bundled) - authoritative for SPA/Nuxt headers.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/vue.json` (hosting configs, `nuxt.config.ts`, meta CSP, server routes).
- `npx nuxi build` + `node .output/server/index.mjs` then the live check against localhost (only if the user asks to run it).

## References
Nuxt "Route Rules" and "Server" docs; `nuxt-security` docs; Vite build docs; MDN CSP; nginx `add_header`. CWE-693, CWE-1021, CWE-16, CWE-352; ASVS 14.4.x, 14.5.x; OWASP A05:2021. Sibling skills: `audit-frontend-xss-and-dom-safety`, `audit-client-auth-and-storage`, `audit-authz-and-access-control`.
