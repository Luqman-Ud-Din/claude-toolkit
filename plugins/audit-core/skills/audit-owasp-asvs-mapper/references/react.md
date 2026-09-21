# React (and Next.js) reference for audit-owasp-asvs-mapper

Frontend half of the ASVS mapping for React SPAs and Next.js apps. Next.js blurs the
line: API routes, middleware and `next.config.js` headers are server-side and count
toward V4, V14.4 and V14.5 directly.

## Stack markers
`package.json` with `react`, `react-dom`, `next`; `src/`, `pages/` or `app/` (Next),
`next.config.js|mjs|ts`, `middleware.ts`. Variants: CRA/Vite SPA vs Next.js SSR/RSC;
Redux/Zustand stores; `react-router` vs Next routing.

## Where the relevant code lives
- Rendering: `dangerouslySetInnerHTML`, `href={userValue}` (javascript: URLs), `createPortal` with raw HTML.
- Auth/storage: `localStorage.setItem('token')`, `js-cookie`, `next-auth` config, `middleware.ts` route protection.
- Server side (Next): `pages/api/*` or `app/**/route.ts`, `getServerSideProps`, `next.config.js` `headers()`.
- Build: `vite.config.ts` / `next.config.js` (`productionBrowserSourceMaps`), `index.html` CDN scripts.
- Env: `NEXT_PUBLIC_*` / `VITE_*` variables (shipped to the browser) vs server-only env.

## Controls React satisfies by default
| ASVS | Default | Fails when |
|---|---|---|
| 5.3.3 escaping | JSX escapes `{value}` | `dangerouslySetInnerHTML={{ __html: userValue }}`; `href={"javascript:" ...}`; SSR string concatenation into HTML |
| 5.2.4 dynamic code | No eval in idiomatic React | `eval`, `new Function`, `setTimeout(string)` |
| 4.2.2 CSRF (Next server actions) | Origin check on server actions (Next 14+) | Custom API routes with cookie auth and no token/`SameSite` |

## Controls that need explicit evidence
- 3.2.3 / 8.2.2 token storage: JWT in `localStorage`/`sessionStorage` = Failed (CWE-922); HttpOnly cookie via `next-auth` or BFF = Verified.
- 4.1.1: `react-router` `<ProtectedRoute>` and Next `middleware.ts` redirects are UX; the API must enforce. Tag findings `client-side-check`. For Next API routes, the check inside the handler *is* server-side and can Verify 4.1.1.
- 4.2.1 (Next API routes): `prisma.order.findUnique({ where: { id } })` without `userId` = Failed.
- 14.4.3-14.4.7 (Next): `next.config.js` `async headers()` returning CSP, nosniff, frame-ancestors, referrer-policy, HSTS; absent = Not assessed (may be on the CDN/edge) unless the deployment config is in the repo.
- 14.4.3 CSP compatibility: Next requires nonces for inline scripts; `'unsafe-inline'` in the policy is a weak CSP (Low, CWE-693).
- 14.2.3 SRI: `<Script src="https://...">` / `<script>` tags without `integrity`.
- 2.10.4: secrets in `NEXT_PUBLIC_*` or `VITE_*` are shipped to every visitor = Failed.
- 14.3.2: `productionBrowserSourceMaps: true`, `sourcemap: true` in Vite prod build.
- 5.1.5: `router.push(searchParams.get('returnTo'))` without allow-list = open redirect.
- 12.6.1 (Next `fetch` on the server with a user URL) = SSRF, A10.

## What "good" looks like
```tsx
// Rendering rich text
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }} />   // ASVS 5.3.3 with documented reason
// next.config.js
async headers() { return [{ source: '/(.*)', headers: [
  { key: 'Content-Security-Policy', value: "default-src 'self'; script-src 'self' 'nonce-...'" }, // 14.4.3
  { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },            // 14.4.5
  { key: 'X-Content-Type-Options', value: 'nosniff' } ] }]; }                                     // 14.4.4
// app/api/orders/[id]/route.ts
const order = await prisma.order.findFirst({ where: { id, userId: session.user.id } });          // 4.2.1
```

## Manual trace checklist
1. Grep `dangerouslySetInnerHTML`; classify each source (V5.3.3).
2. Follow the login response to where the token is stored (V3.2.3).
3. Next only: read `middleware.ts` and every `route.ts` for auth + ownership (V4.1.1, V4.2.1).
4. `next.config.js` / hosting config for headers (V14.4); note if hosting config is outside the repo.
5. `NEXT_PUBLIC_*` / `VITE_*` inventory (V2.10.4).

## Stack-specific false positives
- `dangerouslySetInnerHTML` with content from a trusted CMS that sanitizes on save and is re-sanitized here: Info.
- `localStorage` for UI preferences only.
- Missing CSP in `next.config.js` when Vercel/Cloudflare config in the repo sets it (cite the file).

## Tooling
- `npm audit --json`, `npx eslint-plugin-react` rule `react/no-danger`, `eslint-plugin-security`.
- `npx @next/bundle-analyzer` to see what env values ship; DevTools Application tab for storage evidence.

## References
- React docs "Dangerously setting the inner HTML"; Next.js "Security Headers", "Content Security Policy".
- ASVS 4.0.3 V3.2.3, V5.3.3, V8.2, V14.4, V14.2.3, V12.6; CWE-79, CWE-922, CWE-602, CWE-601, CWE-918.
- Sibling skills: `audit-frontend-xss-and-dom-safety`, `audit-client-auth-and-storage`, `audit-security-headers-and-middleware`.
