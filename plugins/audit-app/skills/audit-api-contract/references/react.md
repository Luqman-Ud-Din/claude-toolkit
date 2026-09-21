# React (and Next.js) reference for audit-api-contract

## Stack markers
`package.json` with `react` or `next`. Variants: SPA calling a separate API vs Next.js with its own route handlers (`app/api/**/route.ts`, `pages/api/**`) and server actions - those are backend code: audit them with `node-express.md`; data layer via fetch/axios, React Query, SWR, RTK Query, tRPC (typed end to end, so contract drift is a compile error), or a generated client (`openapi-typescript`, `orval`).

## Where the relevant code lives
- Client: `src/services/api.ts` / `lib/api.ts` (base URL, version prefix, error normalisation), `hooks/use*.ts` (React Query keys and fetchers), `types/*.ts` or generated `api.d.ts` (client DTOs), `.env*` (`NEXT_PUBLIC_API_URL`).
- Server (Next.js): `app/api/**/route.ts` (`NextResponse.json(...)`, status codes), `zod` schemas next to handlers, `middleware.ts`.

## Dangerous / interesting APIs and patterns
- Several error normalisers: `error.response.data.message`, `.error`, `.detail`, `.errors`, `.title` handled in different hooks or one `normalizeError` with fallbacks - each branch is a distinct server shape (evidence for the consistency finding).
- Base URL without a version; hooks mixing `/api/orders` and `/api/v2/orders`.
- Client types containing fields the server should not send (`passwordHash`, `isDeleted`, other-tenant ids, `costPrice` on customer screens) - evidence for over-exposure.
- Client-side pagination of a full array (`data.slice(...)`, `useMemo` paging) - proof of an unpaginated list endpoint; `useInfiniteQuery` without a `nextCursor` from the server.
- Next.js route handlers: `NextResponse.json(await prisma.user.findMany())` (entity leak), `return NextResponse.json({ error })` in one route and `{ message }` in another, no `status` on create (200), `req.json()` used without a zod/yup parse, `searchParams.get('limit')` uncapped, Swagger/`openapi.json` served from `public/` in production.
- Server actions returning ORM objects to the client (serialised into the RSC payload).
- Dates parsed from offset-less strings, `dd/MM/yyyy` posted back (hand to the datetime skill).
- Generated types committed but stale relative to the server spec.

## What "good" looks like
```ts
// one error shape, one normaliser
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}/v1${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } });
  if (!res.ok) { const problem: ProblemDetails = await res.json(); throw new ApiError(problem); }
  return res.json();
}
// route handler (Next.js): validate, project, status code
export async function POST(req: Request) {
  const body = CreateOrderSchema.parse(await req.json());          // zod, .strict()
  const order = await createOrder(body);
  return NextResponse.json(toOrderDto(order), { status: 201 });
}
export async function GET(req: Request) {
  const size = Math.min(Number(new URL(req.url).searchParams.get('pageSize') ?? 20), 100); ...
  return NextResponse.json({ items, total, page, pageSize: size });
}
```
Types generated from the spec in CI (`openapi-typescript`) so drift fails the build.

## Manual trace checklist
1. Error normalisers: enumerate shapes; map to server controllers.
2. Endpoints the client calls (grep `fetch(`, `axios.`, `useQuery`/`useMutation` fetchers) vs the server endpoint table: stale calls and unused server routes.
3. Client types vs server DTOs: sensitive/internal fields.
4. Client-side pagination sites.
5. Next.js route handlers/server actions: apply `node-express.md` (spec exposure, entity returns, validation, error shape, status codes, uncapped limits).
6. Version prefix consistency.
7. List filters and sort keys the client sends (`searchParams`, React Query keys) exist in the server's list-query schema; a filter the server ignores is silent contract drift.

## Stack-specific false positives
- A single normaliser handling `ProblemDetails` plus a network-error fallback.
- Client-side paging of a small bounded list.
- tRPC or generated types regenerated in CI (contract enforced by the build).
- Next.js route handlers that only proxy to the real API (`fetch(BACKEND + path)` and return the response unchanged): audit the upstream API, not the proxy.

## Tooling
`grep -rn "\.data\.\(message\|error\|detail\|errors\|title\)" src | sort | uniq -c`; `grep -rn "NextResponse\.json(" app | grep -i "error\|message"`; `npx openapi-typescript openapi.json -o /tmp/api.d.ts` and diff against the committed types; `$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py` (also covers Next.js `route.ts` handlers).

## References
ASVS 13.1, OWASP API Security Top 10 2023 (API3, API9), RFC 9457, Next.js route handler docs. The backend reference owns the server-side findings.
