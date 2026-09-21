# Vue (and Nuxt) reference for audit-owasp-asvs-mapper

Frontend half of the ASVS mapping for Vue 2/3 SPAs and Nuxt apps. Nuxt server routes
(`server/api/*`) and `nuxt.config` `routeRules` headers are server-side and count
toward V4 and V14.4 directly.

## Stack markers
`package.json` with `vue`, `nuxt`; `src/`, `pages/`, `server/` (Nuxt), `nuxt.config.ts`,
`vite.config.ts`. Variants: Options API vs Composition API; Pinia/Vuex stores; Nuxt SSR
vs static generation.

## Where the relevant code lives
- Rendering: `v-html`, `:href` bound to user input, `render()` functions building `innerHTML`, `<component :is>` with user-chosen names.
- Auth/storage: `localStorage`/`useCookie` for tokens, `@sidebase/nuxt-auth`, router `beforeEach` guards, Nuxt `middleware/auth.ts`.
- Server (Nuxt): `server/api/**.ts` (`defineEventHandler`), `server/middleware/*`, `nuxt.config.ts` `routeRules[...].headers`.
- Env: `runtimeConfig.public.*` (shipped) vs `runtimeConfig.*` (server only); `VITE_*`.

## Controls Vue satisfies by default
| ASVS | Default | Fails when |
|---|---|---|
| 5.3.3 escaping | Mustache `{{ }}` and `v-bind` escape | `v-html="userValue"`; `:href="'javascript:' + x"`; SSR string templates |
| 5.2.4 dynamic code | Compiled templates | Runtime template compilation from user strings (`template: userString`), `eval` |

## Controls that need explicit evidence
- 3.2.3 / 8.2.2: token in `localStorage` = Failed (CWE-922); `useCookie` with `httpOnly: true` set server-side, or in-memory, = Verified.
- 4.1.1: `router.beforeEach` and Nuxt page middleware are UX only; tag `client-side-check`. Nuxt `server/api` handlers that check `event.context.user` are server-side and can Verify.
- 4.2.1 (Nuxt server routes): queries without the owner/tenant predicate = Failed.
- 14.4.3-14.4.7 (Nuxt): `routeRules: { '/**': { headers: { 'Content-Security-Policy': ... } } }` or `nuxt-security` module; absent = Not assessed unless hosting config is in the repo.
- 14.2.3 SRI: CDN scripts in `nuxt.config.ts` `app.head.script` without `integrity`.
- 2.10.4: secrets in `runtimeConfig.public` or `VITE_*`.
- 14.3.2: `sourcemap: true` for client production build.
- 5.1.5: `router.push(route.query.redirect)` without allow-list = open redirect (CWE-601).
- 12.6.1: Nuxt server `$fetch(userUrl)` = SSRF (A10).

## What "good" looks like
```vue
<!-- rich text -->
<div v-html="DOMPurify.sanitize(description)"></div>   <!-- ASVS 5.3.3, reason documented -->
```
```ts
// nuxt.config.ts
export default defineNuxtConfig({
  routeRules: { '/**': { headers: {
    'Content-Security-Policy': "default-src 'self'",                 // 14.4.3
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains', // 14.4.5
    'X-Content-Type-Options': 'nosniff' } } },                        // 14.4.4
  runtimeConfig: { apiSecret: '', public: { apiBase: '/api' } }       // 2.10.4: secret server-only
})
// server/api/orders/[id].get.ts
const order = await db.order.findFirst({ where: { id, ownerId: event.context.user.id } }) // 4.2.1
```

## Manual trace checklist
1. Grep `v-html`; classify each binding's source (V5.3.3).
2. Follow login -> token storage (V3.2.3, V8.2.2).
3. Nuxt only: `server/api` handlers for auth and ownership (V4.1.1, V4.2.1) and `routeRules` headers (V14.4).
4. `runtimeConfig.public` and `VITE_*` inventory (V2.10.4).
5. Router guards vs backend authorization inventory (V4.1.1).

## Stack-specific false positives
- `v-html` with i18n strings owned by the team (Info at most).
- `localStorage` for locale/theme only.
- Missing `routeRules` headers when `nuxt-security` module is installed with defaults (it sets HSTS, nosniff, frame-ancestors, referrer-policy).

## Tooling
- `npm audit --json`; `eslint-plugin-vue` rule `vue/no-v-html`; `eslint-plugin-security`.
- `nuxt-security` module report; DevTools Application tab for storage evidence.

## References
- Vue "Security" guide; Nuxt "Security" docs and `nuxt-security` module.
- ASVS 4.0.3 V3.2.3, V5.3.3, V8.2, V14.4, V14.2.3, V12.6; CWE-79, CWE-922, CWE-602, CWE-601, CWE-918.
- Sibling skills: `audit-frontend-xss-and-dom-safety`, `audit-client-auth-and-storage`, `audit-security-headers-and-middleware`.
