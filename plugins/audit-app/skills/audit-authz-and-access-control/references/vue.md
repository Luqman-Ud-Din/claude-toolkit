# Vue reference for audit-authz-and-access-control

Frontend authorization is **cosmetic**. Router guards (`beforeEach`,
`meta.requiresAuth`) and `v-if="isAdmin"` only hide UI; the API must enforce the
rule. Put the finding on the endpoint. Token storage is the sibling skill
`audit-client-auth-and-storage`.

## Stack markers
`package.json` with `vue`/`nuxt`. Routing via `vue-router` (`router.beforeEach`, `meta: { requiresAuth, roles }`) or Nuxt route middleware.

## Where the relevant code lives
`router/index.ts` (global `beforeEach`, per-route `meta`), `middleware/` (Nuxt), Pinia/Vuex auth store, components with `v-if` role checks, the API/fetch wrapper that attaches the token. Nuxt `server/` routes are real server code.

## Dangerous / interesting patterns
- `beforeEach`/`beforeEnter` guards and `v-if="isAdmin"` - Info; verify the backend re-checks.
- Nuxt `server/api/*` handlers fetching by id without an owner filter - audit as backend code.
- Role from a decoded JWT trusted beyond display.

## What "good" looks like
Guards for UX; the API enforces role + ownership. Name the verified server file in the finding.

## Manual trace checklist
1. Map each guarded route to its API call; confirm the server enforces the same rule.
2. Audit Nuxt `server/` handlers as backend code (ownership on id lookups).

## Stack-specific false positives
Router guards and `v-if` role checks are expected; not findings alone.

## Tooling
Inspect the built bundle. Server checks: backend reference + `scripts/authz_probe.py`.

## References
CWE-602. OWASP A01:2021. See the backend stack file for the fix.
