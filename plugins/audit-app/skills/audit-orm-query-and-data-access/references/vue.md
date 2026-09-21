# Vue (and Nuxt) reference for audit-orm-query-and-data-access

This skill audits backend data access. For a Vue client, build the hot-endpoint
inventory (which list calls fire on page load, which send paging) and hand
client-side work to `audit-performance-and-scalability` and
`audit-frontend-best-practices`. For Nuxt, `server/api/**` and `server/utils/**`
call the ORM directly and are audited here with `node-express.md`.

## Stack markers
`package.json` with `vue` or `nuxt`; `nuxt` marks server-side data access in `server/**` (Nitro handlers) and `nuxt.config.ts` (`nitro`, `routeRules`).

## Where the relevant code lives
- Client: composables (`useFetch`/`useAsyncData`/`useQuery` from `@tanstack/vue-query`, Pinia store actions), API modules (`src/api/*.ts`, `services/*.ts`), tables (`v-data-table-server` in Vuetify, `el-table` + `el-pagination`, PrimeVue `DataTable lazy`), dashboard pages.
- Server (Nuxt): `server/api/**/*.ts` (`defineEventHandler(async () => prisma.x.findMany())`), `server/utils/db.ts`, `server/routes/**`.

## What to inventory (feeds the backend trace)
- Every list composable/store action: params sent (`page`, `pageSize`, `limit`, `cursor`)? A store action `fetchAll()` with no params implies an unbounded endpoint.
- Endpoints fired on landing/dashboard `setup()`/`onMounted`/`useAsyncData` (SSR runs them on the server per request).
- Search inputs -> query param -> backend column.
- Nuxt server handlers: every ORM list call - paged? projected? These are backend findings (ORM prefix) located in the Vue repo.

## Client-side signs that the backend is unbounded or over-fetching
- `computed(() => items.value.slice(...))` / `.filter()` for paging in the component; `v-data-table` (non-server variant) fed with a full API response.
- Response types with nested arrays never rendered.
- Same endpoint fetched by several components on one page without a shared store (chatty - hand to performance skill).

## What "good" looks like
```ts
const { data } = await useFetch('/api/products', { query: { page, pageSize: 20, q }, watch: [page, q] });

// server/api/products.get.ts - paged and projected
export default defineEventHandler(async (e) => {
  const { page = 1, pageSize = 20 } = getQuery(e);
  return prisma.product.findMany({ where: { companyId }, take: Math.min(+pageSize, 100), skip: (+page - 1) * +pageSize,
    select: { id: true, name: true, price: true } });
});
```

## Manual trace checklist
1. Tabulate list composables/store actions: endpoint, paging params, page.
2. Landing/dashboard mount calls (and SSR - they run per request on the server).
3. Nuxt: run `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/node-express.json` over `server/`, then use `audit-endpoint-inventory` (`endpoints.json`). It records `server/api/**` and `server/routes/**` handlers (`defineEventHandler`/`eventHandler`) as `kind: http` records with framework `nuxt-server-route`, the verb taken from the `.get.ts`/`.post.ts` suffix, so the unbounded-handler filter in SKILL.md step 2 lists those with a materialising call and no paging. `server/middleware/**` is `kind: middleware`, outside that filter. Still trace by hand: `server/utils/**` helpers more than one call away from the handler, SSR `useAsyncData`/`useFetch` calls, Nitro scheduled tasks, and SvelteKit `+server.ts` endpoints if the repo has any (the inventory does not read SvelteKit).
4. Hand the inventory to the backend trace (step 3a).

## Stack-specific false positives
- Client slicing of a small cached reference list.
- `routeRules` with `prerender: true` for static lists - bounded at build.

## Tooling
Vue Devtools (Pinia state size hints at unbounded lists), DevTools Network on the landing route; for Nuxt, `DEBUG="prisma:query" nuxt dev`.

## Hand-off
Re-renders, bundle, client caching: `audit-frontend-best-practices` / `audit-performance-and-scalability`; API shape: `audit-api-contract`.

## References
CWE-770, CWE-400; Nuxt "Data fetching", "Server routes"; Vuetify `v-data-table-server`; Prisma "Pagination".
