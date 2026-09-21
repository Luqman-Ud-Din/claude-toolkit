# React (and Next.js) reference for audit-orm-query-and-data-access

This skill audits backend data access. For a React client, build the hot-endpoint
inventory (which list calls fire on page load, which send paging) and hand the
client-side work to `audit-performance-and-scalability` and
`audit-frontend-best-practices`. For Next.js, server-side code (`app/api/**`,
server components, server actions, `getServerSideProps`) calls the ORM directly
and is audited here with `node-express.md`.

## Stack markers
`package.json` with `react`, `react-dom`; `next` marks server-side data access in `app/**` (server components run ORM queries at render time), `pages/api/**`, `lib/db.ts`, `prisma/`.

## Where the relevant code lives
- Client: data hooks (`useQuery`/`useSWR`/`useEffect` + `fetch`), API client modules (`src/api/*.ts`, `services/*.ts`), table components (`react-table`/`TanStack Table` with `manualPagination`, MUI `DataGrid` `paginationMode="server"`), dashboard pages.
- Server (Next): `app/**/page.tsx` server components (`await prisma.x.findMany()` inline - unbounded and un-projected is common), `app/api/**/route.ts`, `actions.ts` (`'use server'`), `lib/*.ts` data helpers.

## What to inventory (feeds the backend trace)
- Every list hook: params sent (`page`, `pageSize`, `cursor`, `limit`)? `useInfiniteQuery` with `getNextPageParam` implies server paging; `useQuery(['products'])` with no params implies an unbounded endpoint.
- Endpoints fired on the landing/dashboard route mount (`useQuery` in page components, `loader`s in Remix/React Router).
- Search inputs -> `q`/`search` param -> backend column.
- Next server components: every `findMany`/`find`/`findAll` inline in `page.tsx` - paged? `select`ed? These are backend findings (ORM prefix) located in the React repo.

## Client-side signs that the backend is unbounded or over-fetching
- `.slice((page-1)*size, page*size)` / `.filter()` on API results in components; `TanStack Table` without `manualPagination` on API data.
- Response types with nested arrays never rendered.
- The same `useQuery` key fetched in several components without a shared cache config (chatty - hand to performance skill).

## What "good" looks like
```ts
const { data } = useQuery({ queryKey: ['products', page, pageSize, q],
  queryFn: () => api.get('/products', { params: { page, pageSize, q } }), placeholderData: keepPreviousData });

// Next server component - paged and projected
const products = await prisma.product.findMany({ where: { companyId }, take: 20, skip: (page - 1) * 20,
  select: { id: true, name: true, price: true } });
```

## Manual trace checklist
1. Tabulate list hooks: endpoint, paging params, page.
2. Landing/dashboard mount calls.
3. Next and Remix: run `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/node-express.json` over `app/`, `pages/api/`, `lib/`, `actions`, then use `audit-endpoint-inventory` (`endpoints.json`). It records Next.js App Router `route.ts` handlers (`nextjs-route`), Pages Router API routes (`nextjs-pages-api`, one record per `req.method` branch) and Remix / React Router loaders and actions (`remix-route`) as `kind: http`, so the unbounded-handler filter in SKILL.md step 2 selects them without a manual list. Server actions have no URL: they are `kind: server-action` records, which that filter's `kind == "http"` condition leaves out, so check their materialising calls in the "Server actions" table of `endpoints.md`, or add the kind to the filter. Still trace by hand: server components (`page.tsx`, `layout.tsx`), `getServerSideProps`, and data helpers more than one call away from the handler.
4. Hand the inventory to the backend trace (step 3a).

## Stack-specific false positives
- Client slicing of a small cached reference list.
- Next `generateStaticParams` / build-time `findMany` for static pages - bounded by build, but note growth.

## Tooling
React Query Devtools (see every query key and its params); DevTools Network on the landing route; for Next, `DEBUG="prisma:query" next dev` to see server-component queries per render.

## Hand-off
Re-renders, bundle, client caching: `audit-frontend-best-practices` / `audit-performance-and-scalability`; API shape: `audit-api-contract`.

## References
CWE-770, CWE-400; TanStack Query "Paginated queries", "Infinite queries"; Next.js "Data Fetching"; Prisma "Pagination".
