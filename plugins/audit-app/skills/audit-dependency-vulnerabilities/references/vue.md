# Vue reference for audit-dependency-vulnerabilities

## Stack markers
`package.json` with `vue` (2.x or 3.x), `nuxt`, `@vue/cli-service` (Vue CLI),
`vite` + `@vitejs/plugin-vue`. Lockfile decides the manager. Variants: Vue 2
(end of life since 2023-12-31), Nuxt 2 (EOL June 2024) vs Nuxt 3 (server routes
in `server/api` - backend-reachable code), Quasar/Vuetify component libraries.

## Where the relevant code lives
- Direct deps: `dependencies` (bundle + Nuxt server) vs `devDependencies`.
- Framework line: `vue`, `nuxt`, `vue-template-compiler` (must match `vue` 2.x exactly).
- Build: `vite.config.*` (`server.fs` settings matter for dev-server advisories),
  `vue.config.js` for Vue CLI (webpack 4/5).
- Nuxt server: `server/api/**`, `server/middleware/**`, `nitro` config.

## Dangerous / interesting APIs and patterns
- Vue 2.x / `vue-template-compiler` 2.x: EOL, XSS via runtime-compiled templates
  (CVE-2024-6783) will never be fixed - rate by whether templates are compiled
  from user input (`new Vue({ template: userString })`, `v-html` is a separate topic).
- Nuxt 2 (EOL) and Nuxt 3 < 3.12.4 (path traversal / SSR advisories 2024).
- `vite` dev server `server.fs.deny` bypasses (CVE-2025-30208 family; fixed
  6.2.3 / 5.4.15 / 4.5.10) - local dev exposure only.
- `vue-i18n` < 9.14.1 (prototype pollution in message compiler), `dompurify` < 3.1.3
  behind `v-html`, `lodash` < 4.17.21, `axios` < 1.6.0, `marked` < 4.0.10,
  `serialize-javascript` < 3.1.0 (SSR).
- Vue CLI (`@vue/cli-service` 4/5) pins webpack 4 - large dev-only advisory tail.
- `*`/`latest`, git URL deps, `.npmrc audit=false`.

## What "good" looks like
```json
{
  "dependencies": { "vue": "^3.5.12", "dompurify": "^3.1.7" },
  "devDependencies": { "vite": "^6.2.3", "@vitejs/plugin-vue": "^5.2.1" },
  "overrides": { "semver": "^7.5.4" }
}
```
CI: `npm ci --ignore-scripts && npm audit --omit=dev --audit-level=high`;
Renovate with `vue` packages grouped.

## Manual trace checklist
1. Vue 2 present: one High finding (EOL framework, unfixed CVE) with a migration
   note (`@vue/compat` path), not a per-CVE list.
2. `v-html` sites and the sanitizer library version behind them (hand the DOM
   question to `audit-frontend-xss-and-dom-safety`).
3. Nuxt server routes: server-side packages follow `node-express.md` rules.
4. Transitive dev-only advisories via `@vue/cli-service`: group as one Low.
5. Lockfile committed; CI uses frozen installs.

## Stack-specific false positives
- Vue CLI / webpack 4 dev advisories (`browserslist`, `postcss`, `nth-check`):
  build-time only.
- `vue-template-compiler` version mismatch warnings are correctness, not security.
- `vite` dev-server CVEs when the dev server is never exposed beyond localhost: Low.

## Tooling
- `npm audit --json`, `pnpm audit --json`, `yarn audit --json`
- `npx vue-cli-service inspect` / `npx vite --version`
- `npm outdated --long`, `npm view vue time --json`
- `trivy fs .`, `osv-scanner --lockfile pnpm-lock.yaml`

## References
CWE-1395, CWE-1104 (EOL framework), CWE-79, OWASP A06:2021, ASVS 14.2, Vue 2
EOL notice (v2.vuejs.org/eol), Nuxt security advisories. Sibling skills:
`audit-frontend-xss-and-dom-safety`, `audit-client-auth-and-storage`.
