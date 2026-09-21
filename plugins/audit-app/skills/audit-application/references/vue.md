# Vue reference for audit-application

What the orchestrator needs to know about a Vue codebase (Vite, Vue CLI, Nuxt, Quasar)
before it plans and runs the children. Topic detail lives in each child's own
`references/vue.md`.

## Stack markers

- `package.json` depending on `vue` or `nuxt` (detect_stack id `vue`).
- `nuxt`: server code exists (`server/api/**`, `server/routes/**`, `server/middleware/**`,
  Nitro). It is backend code even though detect_stack reports no backend id.
- `quasar` + `src-capacitor` / `src-cordova`: mobile builds. client-auth reviews native storage.
- Build tool: `vite.config.*`, `vue.config.js` (Vue CLI), `nuxt.config.*`.

## Where the relevant code lives

- `src/` (components `*.vue`, composables, `stores/` Pinia or `store/` Vuex, `router/`,
  `api/` clients), `.env*` (`VITE_*` / `VUE_APP_*` / `NUXT_PUBLIC_*` values ship in the bundle),
  `index.html` (inline scripts, CSP meta), `src/locales` or `i18n/` (vue-i18n messages).
- Build output: `dist/` (Vite/Vue CLI), `.output/` (Nuxt 3).

## Dangerous / interesting APIs and patterns

Setup signals:

- **Server code in Nuxt:** `server/api` handlers querying databases (Prisma, Drizzle,
  `useStorage`). Treat them as backend for authz, injection, orm, tenant isolation and
  secrets. `plan.py` cannot see this, so add the backend children explicitly.
- **Where the backend is:** base URLs in `.env*`, axios/ofetch instances, `vite.config` proxy.
  For a SPA-only repo, ask for the backend root at setup.
- **Multi-tenant hints on the client:** tenant/org switchers in the layout, tenant ids in
  request headers, subdomain parsing in router guards or Nuxt middleware.
- **Token handling:** `localStorage` in Pinia persist plugins (`pinia-plugin-persistedstate`),
  axios interceptors, Nuxt `useCookie` flags.

## What "good" looks like

- Node version from `engines`/`.nvmrc` and a lockfile.
- `npm ci` possible; `npm run build` succeeds, so the bundle exists for frontend-best-
  practices and client-auth.
- For Nuxt with server routes: a read-only DB connection or committed migrations for db-schema
  and orm.
- A running app (and backend) with a test account for accessibility and frontend-memory-leak.

## Manual trace checklist

Prerequisites to confirm at setup:

1. Node + lockfile -> dependency-vulnerabilities, licensing.
2. Production build possible -> frontend-best-practices, client-auth. Missing:
   `--limited "no production build"`.
3. Nuxt server routes present? If yes, plan the backend children as well and confirm DB access.
4. Backend root for a SPA-only repo -> authz, tenant isolation, injection, api-contract.
5. Running app + account -> accessibility (axe), frontend-memory-leak (heap snapshots),
   performance.
6. Locales and RTL requirements -> accessibility and i18n.

## Stack-specific false positives

Wrong applicability calls to avoid:

- **Nuxt detected as frontend only:** `plan.py` marks async, orm and backend-resource-leak n/a.
  If `server/` exists, override with a custom list or `--skill` and state why in the run.
- **Vite SPA with no server:** async, orm, backend-resource-leak and api-contract are genuinely n/a.
  Injection and authz still run on the client side (URL building, cosmetic guards).
- **`v-html` in a static docs component** is not a setup concern. Let XSS rate it.

## Tooling

```bash
node -v && npm -v
npm ci --ignore-scripts                     # ask first
npm run build
npx vitest run --coverage
npm audit --json
npx nuxi info                               # Nuxt version and modules, read-only
npx @axe-core/cli http://localhost:5173     # optional, served build
```

## Child applicability for Vue repos

| Repo shape | n/a children |
|---|---|
| SPA only (Vite/Vue CLI) | async-and-dependency-injection, orm-query-and-data-access, backend-resource-leak, api-contract (unless a backend root is added) |
| Nuxt with server routes | none; add the backend children the plan skipped |
| Quasar/Capacitor mobile | none of the frontend children; record DevTools-only steps as limited access |

## References

- Child references: `../audit-client-auth-and-storage/references/vue.md`,
  `../audit-frontend-xss-and-dom-safety/references/vue.md`, `../audit-frontend-best-practices/references/vue.md`.
- Vue security guide, Nuxt server directory docs, Pinia persisted state docs.
