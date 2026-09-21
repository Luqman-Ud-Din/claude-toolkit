# Vue reference for audit-soc2-controls-evidence

## Stack markers

`package.json` with `vue`; variants: Vite SPA (`vite.config.*`), Vue CLI
(`vue.config.js`), Nuxt 3 (`nuxt.config.ts`, `server/api/`). Nuxt has a server
side (`server/api/**`, `server/middleware/**`) - treat it like the Node backend file
for CC6/PI1. A pure SPA contributes only the SSO client, build pipeline and bundle
hygiene; `router.beforeEach` guards and `v-if="isAdmin"` are UX, not access control.

## Where the relevant code lives

- `src/auth/`, `src/main.ts`, `src/router/index.ts` - OIDC client, route guards.
- Nuxt: `nuxt.config.ts` (`runtimeConfig` vs `runtimeConfig.public`),
  `server/api/**`, `server/middleware/**`, `middleware/*.global.ts`.
- `.env*`, `vite.config.ts` - `VITE_*` variables, `build.sourcemap`.
- `index.html` - external scripts.
- `.github/workflows/`, `vitest.config.*`, `netlify.toml`, `vercel.json`.

## Dangerous / interesting APIs and patterns

- CC6.1 SSO evidence: `oidc-client-ts` `UserManager({ authority, client_id,
  response_type: 'code' })`, `nuxt-auth-utils` (`defineOAuthMicrosoftEventHandler`,
  `defineOAuthAuth0EventHandler`), `@sidebase/nuxt-auth`, `keycloak-js`.
  Bad: `response_type: 'token'` (implicit flow).
- Nuxt server authz: `server/api/admin/*.ts` handlers without `requireUserSession(event)`
  and a role check; relying on a client `middleware/` redirect.
- C1: `VITE_*` values are compiled into the bundle; Nuxt `runtimeConfig.public.*` is
  sent to the browser. Secrets belong in private `runtimeConfig` keys set via
  `NUXT_*` env vars at runtime.
- Production build: `build.sourcemap: true` in `vite.config.ts`, Nuxt
  `sourcemap: { client: true }` - public source.
- CC8.1 / CC7.1: `npm ci`, `npm audit`, `vitest run`, `vue-tsc --noEmit`,
  `nuxi build` / `vite build`.
- CC7.2: `app.config.errorHandler` reporting to Sentry (`@sentry/vue`) with PII
  scrubbing vs `console.error` only.
- Supply chain: external scripts without `integrity`; `v-html` belongs to
  audit-frontend-xss-and-dom-safety.

## What "good" looks like

```ts
export const userManager = new UserManager({
  authority: import.meta.env.VITE_OIDC_AUTHORITY, client_id: import.meta.env.VITE_OIDC_CLIENT_ID,
  redirect_uri: `${location.origin}/callback`, response_type: 'code', scope: 'openid profile api',
});
```

```ts
// Nuxt server route - enforced on the server
export default defineEventHandler(async (event) => {
  const { user } = await requireUserSession(event);
  if (user.role !== 'admin') throw createError({ statusCode: 403 });
  ...
});
```

```ts
// vite.config.ts
export default defineConfig({ build: { sourcemap: false } });
```

Pipeline shape: `npm ci` -> `npx vue-tsc --noEmit` -> `npx vitest run` ->
`npm audit --audit-level=high --omit=dev` -> `npm run build` -> artefact tagged with
the commit SHA -> deploy job gated by a protected environment.

## Manual trace checklist

1. `VITE_*` and `runtimeConfig.public` values: nothing secret.
2. OIDC client configuration: code flow + PKCE, corporate IdP authority.
3. Nuxt: every `server/api/**` handler touching admin or tenant data checks the session.
4. Build config: source maps off for production.
5. CI: tests, type check and audit required on PRs; no CLI deploys from laptops.
6. Depth on token storage and logout: audit-client-auth-and-storage.

## Stack-specific false positives

- Public identifiers: OIDC client id, Sentry DSN, analytics ids in `VITE_*`.
- `sourcemap: 'hidden'` with upload to an error tracker and no public serving.
- `npm audit` hits limited to devDependencies.

## Tooling

```bash
npm ci && npm audit --audit-level=high --omit=dev
grep -rnE "VITE_[A-Z_]*(SECRET|KEY|TOKEN|PASSWORD)" .env* src
grep -rnE "sourcemap" vite.config.* nuxt.config.*
grep -rnE "UserManager|nuxt-auth-utils|requireUserSession|keycloak-js" src server
```

## References

- Vue security guide; Nuxt runtime config docs; oidc-client-ts; nuxt-auth-utils.
- Sibling skills: audit-client-auth-and-storage, audit-security-headers-and-middleware,
  audit-dependency-vulnerabilities.
- SOC2-CC6.1, CC7.1, CC8.1, C1.1; CWE-540, CWE-829.
