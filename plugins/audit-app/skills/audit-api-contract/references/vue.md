# Vue (and Nuxt) reference for audit-api-contract

## Stack markers
`package.json` with `vue` or `nuxt`. Variants: SPA calling a separate API vs Nuxt with `server/api/**` (Nitro) routes - those are backend code: audit them with `node-express.md`; data layer via `$fetch`/`useFetch`, axios, Pinia actions, or a generated client (`openapi-typescript`, `orval`, `nuxt-open-fetch`).

## Where the relevant code lives
- Client: `src/services/api.ts` or `composables/useApi.ts` (base URL, version prefix, `onResponseError` normalisation), Pinia stores (`stores/*.ts`), `types/*.ts` or generated `api.d.ts`, `.env*` / `nuxt.config.ts` `runtimeConfig.public.apiBase`.
- Server (Nuxt): `server/api/**/*.ts` (`defineEventHandler`, `readBody`, `getQuery`, `createError`, `setResponseStatus`), `server/utils/*`, `nuxt.config.ts` (`nitro.openAPI`, experimental spec exposure).

## Dangerous / interesting APIs and patterns
- Several error normalisers: `error.data.message`, `.error`, `.detail`, `.statusMessage`, `.errors` handled in different stores or one `onResponseError` with fallbacks - each branch is a distinct server shape.
- Base URL without a version; stores mixing `/api/orders` and `/api/v2/orders`.
- Client types with fields the server should not send (`passwordHash`, `isDeleted`, other-tenant ids, `costPrice` on customer views).
- Client-side pagination of a full array (computed `slice`, `v-data-table` on the full list) - proof of an unpaginated endpoint.
- Nuxt server routes: `return await prisma.user.findMany()` (entity leak), `createError({ statusMessage })` in one route and `{ error }` object in another, no `setResponseStatus(event, 201)` on create, `readBody(event)` used without validation (`zod`, `h3-zod`, `valibot`), `getQuery(event).limit` uncapped, `nitro.openAPI` enabled in production (`/_nitro/openapi.json`, `/_nitro/scalar`) without auth.
- Dates parsed from offset-less strings, `DD/MM/YYYY` posted back (hand to the datetime skill).
- Generated types committed but stale.

## What "good" looks like
```ts
// one API client, one error shape
export const api = $fetch.create({
  baseURL: `${useRuntimeConfig().public.apiBase}/v1`,
  onResponseError({ response }) { throw new ApiError(response._data as ProblemDetails); },
});
// Nuxt server route: validate, project, status
export default defineEventHandler(async (event) => {
  const body = CreateOrderSchema.parse(await readBody(event));          // zod .strict()
  const order = await createOrder(body);
  setResponseStatus(event, 201);
  return toOrderDto(order);
});
export default defineEventHandler(async (event) => {
  const q = getQuery(event); const size = Math.min(Number(q.pageSize ?? 20), 100); ...
  return { items, total, page, pageSize: size };
});
```
`nitro: { openAPI: { production: false } }` (or auth in front); types generated from the spec in CI.

## Manual trace checklist
1. Error normalisers: enumerate shapes; map to server controllers.
2. Endpoints the client calls (grep `$fetch(`, `useFetch(`, `axios.`) vs the server endpoint table: stale calls and unused routes.
3. Client types vs server DTOs: sensitive/internal fields.
4. Client-side pagination sites.
5. Nuxt server routes: apply `node-express.md` (spec exposure via `nitro.openAPI`, entity returns, validation, error shape, status codes, uncapped limits).
6. Version prefix consistency.
7. List filters and sort keys the stores send (`params`, `query`) exist in the server's list-query schema; a filter the server ignores is silent contract drift.

## Stack-specific false positives
- Nuxt `server/api` routes that only proxy to the real API (`proxyRequest`, `$fetch(upstream)` returned unchanged): audit the upstream API, not the proxy.
- A single `onResponseError` handling `ProblemDetails` plus a network-error fallback.
- Client-side paging of a small bounded list.
- h3's default error shape (`statusCode`, `statusMessage`, `message`) if it is the only shape and `stack` is stripped (`debug: false`).
- Generated types regenerated in CI.

## Tooling
`grep -rn "error\.data\.\(message\|error\|detail\|errors\|statusMessage\)" src | sort | uniq -c`; `grep -rn "createError(\|setResponseStatus(" server`; `grep -rn "openAPI" nuxt.config.ts`; `npx openapi-typescript openapi.json -o /tmp/api.d.ts` and diff; `$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py`.

## References
ASVS 13.1, OWASP API Security Top 10 2023 (API3, API9), RFC 9457, Nuxt server routes / Nitro OpenAPI docs. The backend reference owns the server-side findings.
