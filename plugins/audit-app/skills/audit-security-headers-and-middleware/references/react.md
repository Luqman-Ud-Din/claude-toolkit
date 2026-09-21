# React (CRA/Vite SPA, Next.js) reference for audit-security-headers-and-middleware

Headers and middleware are set by whatever serves the app. For a Vite/CRA SPA
that is the host (nginx, Netlify, Vercel, S3/CloudFront); for Next.js it is
`next.config.js` `headers()` and `middleware.ts`, which is a real server
pipeline. The API is audited with the backend stack file.

## Stack markers
`package.json` with `react` (+ `vite`/`react-scripts`) or `next`. Hosting configs: `nginx.conf`, `_headers` (Netlify/Cloudflare), `vercel.json`, `netlify.toml`, `firebase.json`, `staticwebapp.config.json`, `public/_headers`; Next.js: `next.config.js|mjs|ts` (`headers()`, `poweredByHeader`), `middleware.ts` (edge pipeline), `app/api/**`/`pages/api/**` (API routes - apply `node-express.md` rules for cookies, CORS, body limits).

## Where the relevant code lives
`public/index.html` / `index.html` (meta CSP fallback), `vite.config.ts` (`server.proxy` dev only, `build.sourcemap`), `next.config.js` (`headers()`, `poweredByHeader: false`, `images.remotePatterns`, `experimental.serverActions.bodySizeLimit`), `middleware.ts` (auth redirects, header injection, matcher gaps), `app/layout.tsx`/`pages/_document.tsx` (inline scripts that force `'unsafe-inline'`), `src/api/**` (`withCredentials`/`credentials: 'include'` and CSRF header), API route handlers (`res.setHeader('Set-Cookie')`, `cookies().set`, `NextResponse` CORS headers).

## What this skill checks on the frontend
- **Hosting headers** (SPA): host config must emit CSP, HSTS, X-Content-Type-Options, X-Frame-Options/`frame-ancestors`, Referrer-Policy, Permissions-Policy; `Cache-Control: no-store` for `index.html`, immutable for hashed assets. No config in the repo = headers from host defaults (Vercel/Netlify set a few, not CSP) - Medium, live check required.
- **Next.js headers()**: present for `/(.*)`; CSP with nonces via `middleware.ts` (`x-nonce` header + `nonce` on `<Script>`) is the supported strict pattern; `'unsafe-inline'` in `script-src` is common because of hydration scripts - Medium unless nonce-based; `'unsafe-eval'` needed only in dev (`next dev`) - flag if in the prod policy. `poweredByHeader: false` to drop `X-Powered-By: Next.js`.
- **Next.js middleware order**: `middleware.ts` runs before routing for paths in `config.matcher`; gaps in the matcher (e.g. `/dashboard/:path*` but not `/api/:path*`) mean API routes rely solely on per-handler checks (cross-reference authz); header injection in middleware must use `NextResponse.next({ headers })`, not mutate the request.
- **API routes** (Next): `res.setHeader('Access-Control-Allow-Origin', '*')` with credentials; `cookies().set` without `httpOnly/secure/sameSite`; `export const config = { api: { bodyParser: { sizeLimit: '50mb' } } }`; Server Actions `bodySizeLimit`; no rate limiting on `api/auth/*` (use `@upstash/ratelimit` or edge middleware).
- **CSRF**: cookie sessions (`next-auth`/`iron-session`) - `next-auth` has CSRF tokens built in for its own routes; custom API routes with cookie auth need Origin checks or tokens; Server Actions check `Origin` vs `Host` by default (Next 14+) - note.
- **Meta CSP** in `index.html`: fallback only; no `frame-ancestors`.
- **Dev artefacts**: `vite.config.ts` `server.proxy` targets, `build.sourcemap: true` for prod, `.env.production` `http://` origins.

## What "good" looks like
```js
// next.config.js
const csp = "default-src 'self'; script-src 'self' 'nonce-__NONCE__'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.example.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none'";
module.exports = {
  poweredByHeader: false,
  async headers() { return [{ source: '/(.*)', headers: [
    { key: 'Content-Security-Policy', value: csp },
    { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    { key: 'X-Frame-Options', value: 'DENY' },
    { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
    { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' } ] }]; },
};
```
Nonce pattern: `middleware.ts` generates `crypto.randomUUID()`, sets `Content-Security-Policy` with `'nonce-<value>'` on the response and `x-nonce` on the request; `app/layout.tsx` reads `headers().get('x-nonce')` and passes `nonce` to `<Script>`. Netlify `_headers`: `/*` block with the same six headers plus `/index.html  Cache-Control: no-store`.

## Manual trace checklist
1. Locate the header source (host config or `next.config.js`); if none, record it and rely on the live check.
2. CSP directives vs the app's real needs (`grep -rho "https://[a-z0-9.-]*" src`), nonce usage, `'unsafe-eval'`.
3. Next.js `middleware.ts` matcher coverage and what it enforces.
4. API route handlers: cookies, CORS headers, body size, rate limiting on auth routes.
5. `poweredByHeader`, `sourcemap` for production builds.
6. Cookie-auth apps: CSRF header sent by the client (`credentials: 'include'` + token header) or `next-auth` reliance.

## Stack-specific false positives
- `style-src 'unsafe-inline'` for CSS-in-JS libraries (styled-components, emotion) without nonce setup - Low note.
- `'unsafe-eval'` only inside `process.env.NODE_ENV !== 'production'` branches.
- Vercel/Netlify default headers (`X-Frame-Options`, `X-Content-Type-Options`) are emitted even without config on some plans - the live check decides.

## Tooling
- `python scripts/check_headers.py https://app.example.com` (bundled) - authoritative for SPA headers.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/react.json` (hosting configs, `next.config.js`, meta CSP, API route cookies/CORS).
- `npx next build` output lists middleware matchers; browser console CSP violations in staging.

## References
Next.js "Content Security Policy", "headers", "Middleware" docs; Vite build docs (`sourcemap`); MDN CSP; Netlify/Vercel header docs. CWE-693, CWE-1021, CWE-16, CWE-352; ASVS 14.4.x, 14.5.x; OWASP A05:2021. Sibling skills: `audit-frontend-xss-and-dom-safety` (inline scripts), `audit-client-auth-and-storage` (credentials scope), `audit-authz-and-access-control` (middleware matcher gaps).
