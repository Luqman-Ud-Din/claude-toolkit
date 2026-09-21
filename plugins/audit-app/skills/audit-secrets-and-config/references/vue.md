# Vue reference for audit-secrets-and-config

The frontend rule: **everything you ship is public**. Any bundled value - and any
`VITE_*` / `VUE_APP_*` env var - is inlined into the client bundle and readable by
anyone. Frontend scope here: no server-side secret in the bundle. CORS/headers
are the server's job (backend stack file); token storage is the sibling skill
`audit-client-auth-and-storage`.

## Stack markers
`package.json` with `vue`/`nuxt`, `.env`/`.env.*`, `vite.config.*`.

## Where the relevant code lives
`.env*` files, components/composables with inline keys, `nuxt.config.ts` (`runtimeConfig` - `public` is client-exposed, the rest is server-only), Nuxt `server/` code (may hold secrets legitimately).

## What to look for
- A secret in a `VITE_*` or `VUE_APP_*` variable, or a literal in client code - High; it ships to the browser.
- Nuxt `runtimeConfig.public.*` holding a secret - exposed; the non-public `runtimeConfig` is server-only and fine.
- Source maps enabled in prod.

## What "good" looks like
Client env vars hold only public values. Secrets live in Nuxt `runtimeConfig` (non-public) or server-only env, sourced from a secret manager.

## Manual trace checklist
1. Grep `.env*` and client code for `VITE_`/`VUE_APP_` secrets.
2. Confirm secrets are only in non-public runtimeConfig / `server/`.
3. CORS/HSTS -> backend file.

## Stack-specific false positives
Publishable keys and public URLs in client env vars; secrets in non-public runtimeConfig.

## Tooling
Inspect the production bundle for secrets. See `references/tool-candidates.md`.

## References
CWE-798. OWASP A05:2021, A02:2021. Server-side config is in the backend stack file.
