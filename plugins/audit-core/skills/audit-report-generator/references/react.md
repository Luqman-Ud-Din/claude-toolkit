# React (and Next.js) reference for audit-report-generator

How findings from a React SPA or Next.js app should appear in the final report: scope
enumeration, executive wording for client-side risks, and which frontend findings block
launch. Next.js server code (API routes, middleware, server actions) is backend for
report purposes - list it in scope as such.

## Stack markers
`package.json` with `react`, `react-dom`, `next`; `src/`, `pages/` or `app/`,
`next.config.js|mjs|ts`, `middleware.ts`, `vite.config.ts`. Report whether it is a pure
SPA (CRA/Vite) or Next.js with server-side code, and the hosting target if known (Vercel,
static bucket + CDN, Node server).

## Where the relevant code lives (what "Scope" must enumerate)
- SPA: build config (`vite.config.ts`, `productionBrowserSourceMaps`), env vars shipped to the browser (`VITE_*`, `NEXT_PUBLIC_*`), auth/token handling module, routing guards.
- Next.js: `middleware.ts`, `app/**/route.ts` or `pages/api/*`, server actions, `next.config.js` `headers()`.
- Rendering hot spots: `dangerouslySetInnerHTML` sites, markdown/HTML renderers.
- Out-of-repo for "Not checked": CDN/edge headers, Vercel project env, third-party script tags injected by a tag manager.

## Findings that are typical launch blockers (and how to phrase them)
| Engineering finding | Executive wording |
|---|---|
| `dangerouslySetInnerHTML` with user content, `href="javascript:..."` | "Content entered by one user can run code in another user's browser and take over their session." |
| Token in `localStorage` | "A single injected script can steal every user's login and reuse it from anywhere." |
| Next API route without session check or ownership predicate | "Anyone can read or change other customers' data by calling the API directly." (backend-class blocker) |
| Secret in `NEXT_PUBLIC_*` / `VITE_*` | "Keys that should be private are downloadable by every visitor." |
| Server-side `fetch(userUrl)` in a Next route | "The server can be made to call internal systems on an attacker's behalf." |
| `router.push(searchParams.get('returnTo'))` | "A login link can send users to a look-alike site after they sign in." (Medium unless chained) |

Hygiene (post-launch): missing memoization on hot lists, effect cleanup leaks, source maps
in production, oversized bundles, missing `key` props.

## What "good" looks like (remediation plan wording)
- "Sanitize with DOMPurify before `dangerouslySetInnerHTML` in `RichText.tsx`; document the source."
- "Use `next-auth` HttpOnly session cookies (or a BFF) instead of `localStorage` tokens."
- "Add `session.user.id` to the Prisma `where` in `app/api/orders/[id]/route.ts`; return 404 on miss."
- "Move the key to a server-only env var; remove the `NEXT_PUBLIC_` prefix; rotate."
- "Add `headers()` in `next.config.js` for CSP, HSTS, nosniff, frame-ancestors."
Group tickets by rendering component set (XSS), by auth module (storage), by `next.config.js` (headers/build), by route folder (ownership).

## Report review checklist (manual trace)
1. Scope table separates client bundle from Next server code; each has its own checked/not-checked items.
2. Client-only guard findings are paired with the server finding that is the real blocker.
3. Env var inventory (`NEXT_PUBLIC_*` / `VITE_*`) is in the evidence appendix.
4. Hosting/edge header ownership is stated (repo config vs dashboard).
5. Dependency findings cite `npm audit --json` and distinguish build-time-only packages.

## Stack-specific false positives
- `dangerouslySetInnerHTML` on trusted CMS content sanitized on save and again on render.
- `localStorage` for UI preferences.
- `VITE_*` holding public keys (Firebase web config, Stripe publishable key) - state that they are public by design.
- Missing CSP in `next.config.js` when a `vercel.json` in the repo sets it.

## Tooling (evidence to expect in Appendix B)
`npm audit --json`, `eslint-plugin-react` (`react/no-danger`), `@next/bundle-analyzer`,
Lighthouse/axe output for accessibility findings, DevTools Application tab screenshots.
Export: `pandoc audit/audit-report.md -o audit/audit-report.docx --toc --from gfm`.

## References
React docs (dangerouslySetInnerHTML), Next.js docs (Security Headers, CSP, Server Actions security);
ASVS 4.0.3 V3.2.3, V4.2.1, V5.3.3, V12.6, V14.4; CWE-79, CWE-922, CWE-639, CWE-918, CWE-601.
Sibling skills: `audit-frontend-xss-and-dom-safety`, `audit-client-auth-and-storage`, `audit-authz-and-access-control`.
