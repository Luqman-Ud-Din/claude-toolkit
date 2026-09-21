# React (and Next.js) reference for audit-concurrency-and-race-condition

## Stack markers
`package.json` with `react` or `next`. Variants: SPA (Vite/CRA) vs Next.js; React Query / SWR / RTK Query / Apollo for mutations; Next.js route handlers and server actions (`'use server'`) are backend code: audit them with `node-express.md`, including module-level state in route files (shared across requests within one server instance).

## Where the relevant code lives
- Client: `useMutation` / `mutate` call sites, form `onSubmit` handlers, `services/api.ts` (axios interceptors, `axios-retry`), optimistic update code (`onMutate`/`onError` rollbacks), offline/background-sync code.
- Server (Next.js): `app/api/**/route.ts`, `pages/api/**`, server actions; `globalThis`/module-level caches (`const cache = new Map()` at module scope in a route file survives across requests).

## Dangerous / interesting APIs and patterns
- Submit handlers without an in-flight guard: `onClick={() => mutate(body)}` with no `disabled={isPending}`; forms firing `onSubmit` and a button `onClick` both.
- React Query `retry: 3` (default is 3 for queries, 0 for mutations; a global `defaultOptions.mutations.retry` makes every POST replay); `axios-retry` on all methods; SWR `mutate` with `revalidate` racing a pending write.
- `Promise.all([mutateA(), mutateB()])` on dependent mutations; rapid `setState` + submit in a `useEffect` that re-fires on dependency change (double POST on re-render).
- React 18 Strict Mode double-invoking effects in dev: `useEffect(() => { createOrder() }, [])` posts twice in dev and hides the missing server guard.
- Optimistic updates without rollback (`onError` missing) or without `invalidateQueries` on settle; local state mutated before server confirmation for money/stock.
- Stale edits: form initialised from a cached query, PUT sends the full stale object; no ETag/version; server "last write wins".
- Server actions called from a `<form action={fn}>` re-submitted on refresh; no key; `revalidatePath` racing another action.
- Multiple tabs sharing `localStorage` cart state, both checking out.

## What "good" looks like
```tsx
const key = useRef(crypto.randomUUID());               // one intent, one key; regenerate after success
const pay = useMutation({
  mutationFn: (body) => api.post('/orders/pay', body, { headers: { 'Idempotency-Key': key.current } }),
  retry: 0,
  onSuccess: () => { key.current = crypto.randomUUID(); qc.invalidateQueries({ queryKey: ['order', id] }); },
});
<button disabled={pay.isPending} onClick={() => pay.mutate(body)}>Pay</button>
// edits: send the version, handle 409
api.put(url, { ...dto, version }, { headers: { 'If-Match': etag } })
// server (route handler): see node-express.md for the atomic update / key table
```
Global `QueryClient` defaults with `mutations: { retry: 0 }`; `axios-retry` configured with `retryCondition: isIdempotentRequestError` only.

## Manual trace checklist
1. For each money/stock/uniqueness mutation the backend audit flagged: client trigger, in-flight guard, client key, retry config.
2. `grep -rn "retry" src | grep -i "mutation\|axios-retry\|defaultOptions"`.
3. `grep -rn "useEffect" src | grep -i "post\|create\|submit\|pay"`: mutations fired from effects.
4. Optimistic update sites: rollback and invalidation present.
5. Edit forms: version/ETag on PUT; 409 handling.
6. Next.js route handlers / server actions: apply `node-express.md` (module-level state, check-then-act, keys).

## Stack-specific false positives
- `retry` on queries (GET) only.
- `useEffect` fetches (GET) double-invoked in Strict Mode.
- Optimistic UI with rollback and refetch.
- `disabled={isPending}` alone is UX; record as "client mitigation present", not as closing the server finding.

## Tooling
`grep -rn "isPending\|isLoading" src | grep disabled` vs the list of mutation buttons; React Query Devtools to see retries; Network tab throttling to reproduce; `scripts/double_submit.sh` against the API with the client's exact payload.

## References
CWE-362, ASVS 11.1.4; TanStack Query mutation retry docs; Next.js server actions caveats; Stripe idempotent requests. The backend reference owns the server-side finding.
