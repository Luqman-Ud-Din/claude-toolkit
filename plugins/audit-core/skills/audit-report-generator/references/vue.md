# Vue (and Nuxt) reference for audit-report-generator

How findings from a Vue SPA or Nuxt app should appear in the final report: scope
enumeration, executive wording for client-side risks, and which frontend findings block
launch. Nuxt server code (`server/api`, `server/middleware`, `routeRules`) is backend for
report purposes - list it in scope as such.

## Stack markers
`package.json` with `vue`, `nuxt`; `src/` or `pages/`, `nuxt.config.ts`, `vite.config.ts`,
`server/` (Nuxt). Report Vue 2 vs 3, Options vs Composition API, SPA vs SSR/static, and
hosting target if known.

## Where the relevant code lives (what "Scope" must enumerate)
- SPA: build config (`vite.config.ts` sourcemap), `VITE_*` vars, auth/token module (Pinia store), router guards.
- Nuxt: `nuxt.config.ts` (`runtimeConfig`, `routeRules` headers, `app.head.script`), `server/api/**`, `server/middleware/*`, page middleware.
- Rendering hot spots: `v-html` sites, markdown renderers, `<component :is>` from user data.
- Out-of-repo for "Not checked": CDN/edge headers, hosting dashboard env, tag-manager scripts.

## Findings that are typical launch blockers (and how to phrase them)
| Engineering finding | Executive wording |
|---|---|
| `v-html="userContent"`, `:href` built from user input | "Content entered by one user can run code in another user's browser and take over their session." |
| Token in `localStorage` / non-HttpOnly cookie set client-side | "A single injected script can steal every user's login and reuse it from anywhere." |
| Nuxt `server/api` handler without auth or ownership predicate | "Anyone can read or change other customers' data by calling the API directly." (backend-class blocker) |
| Secret in `runtimeConfig.public` / `VITE_*` | "Keys that should be private are downloadable by every visitor." |
| Nuxt server `$fetch(userUrl)` | "The server can be made to call internal systems on an attacker's behalf." |
| `router.push(route.query.redirect)` | "A login link can send users to a look-alike site after they sign in." (Medium unless chained) |

Hygiene (post-launch): watchers/intervals not cleared in `onUnmounted`, large reactive
objects in global stores, source maps in production, oversized bundles.

## What "good" looks like (remediation plan wording)
- "Sanitize with DOMPurify before `v-html` in `RichText.vue`; document the source."
- "Store the access token in memory in the auth store; use an HttpOnly cookie set by `server/api/auth/login`."
- "Add `event.context.user.id` to the query in `server/api/orders/[id].get.ts`; return 404 on miss."
- "Move the secret to `runtimeConfig` (server-only); remove it from `public`; rotate."
- "Add `routeRules['/**'].headers` for CSP, HSTS, nosniff, frame-ancestors, or install `nuxt-security`."
Group tickets by component set (XSS), by auth store (storage), by `nuxt.config.ts` (headers/build/config), by `server/api` folder (ownership).

## Report review checklist (manual trace)
1. Scope table separates client bundle from Nuxt server code with their own checked/not-checked items.
2. Client-only guard findings are paired with the server-side finding that is the real blocker.
3. `runtimeConfig.public` / `VITE_*` inventory is in the evidence appendix.
4. Hosting/edge header ownership stated.
5. Dependency findings cite `npm audit --json` and distinguish build-time-only packages.

## Stack-specific false positives
- `v-html` with team-owned i18n strings.
- `localStorage` for locale/theme.
- `runtimeConfig.public` holding public keys by design (state which).
- Missing `routeRules` headers when `nuxt-security` is installed with defaults.

## Tooling (evidence to expect in Appendix B)
`npm audit --json`, `eslint-plugin-vue` (`vue/no-v-html`), `nuxt analyze` bundle report,
Lighthouse/axe output, DevTools Application tab screenshots.
Export: `pandoc audit/audit-report.md -o audit/audit-report.docx --toc --from gfm`.

## References
Vue Security guide; Nuxt Security docs and `nuxt-security` module;
ASVS 4.0.3 V3.2.3, V4.2.1, V5.3.3, V12.6, V14.4; CWE-79, CWE-922, CWE-639, CWE-918, CWE-601.
Sibling skills: `audit-frontend-xss-and-dom-safety`, `audit-client-auth-and-storage`, `audit-authz-and-access-control`.
