# React (and Next.js) reference for audit-async-and-dependency-injection

This skill is backend-focused. React has no DI container (context and hooks
play the role), so the "lifetime" half here is about server-side code in
Next.js/Remix - route handlers, server components, server actions - which is a
Node backend and is audited with `node-express.md`. The async half applies to
the client: unobserved promise rejections, missing cancellation on unmount,
fire-and-forget saves.

## Stack markers
`package.json` with `react`; `next` or `remix` marks server-side code (`app/api/**`, `app/**/page.tsx` server components, `'use server'` actions, `middleware.ts`, `app/routes/*.tsx` loaders/actions).

## Where the relevant code lives
- Client: hooks (`useEffect` with async work, custom `useXxx` data hooks), data layer (`@tanstack/react-query`, `swr`, RTK Query), `api/*.ts` client modules, form submit handlers.
- Server (Next/Remix): `app/api/**/route.ts`, server actions, `lib/db.ts` (client singletons), `instrumentation.ts`, `middleware.ts` (edge runtime - no Node APIs, no long-lived state).

## Dangerous / interesting APIs and patterns
- DI-equivalent (server): module-level singletons in route files capturing per-request data (`let currentUser` at module scope in a route handler - shared across concurrent requests on the same instance); `globalThis` caches keyed by nothing; `new PrismaClient()` per request (see node-express HTTP class); server actions storing request state in module variables; React `cache()` misuse for per-user data across requests (it is per-request by design - fine) vs `unstable_cache` keyed without user id (shared - a leak).
- VOID: `useEffect(async () => ...)` (returns a promise where a cleanup function is expected - React warns; the async work is unobserved); `useEffect(() => { fetchData(); }, [])` where `fetchData` is async with no `.catch` - rejection unhandled; event handlers `onClick={async () => await save()}` with no try/catch (error boundary does not catch async errors); server actions that throw without `try` in the caller (`useActionState`/`useTransition` handle some).
- CANCEL: `useEffect` fetch without `AbortController` + cleanup (`return () => controller.abort()`) - state set after unmount, stale responses win races; React Query without `signal` passed to `fetch` (`queryFn: ({ signal }) => fetch(url, { signal })`); server route handlers ignoring `request.signal`.
- FIRE: `void mutate()`; `saveDraft()` without awaiting or observing; `router.push()` after an unawaited save; Next `after()`/`waitUntil` used for business-critical work (best-effort).
- BLOCK: synchronous heavy work in render or `useMemo` (blocks the main thread - INP; hand to performance); on the server, sync fs/crypto in route handlers (node-express BLOCK class).
- TIMEOUT: client `fetch` without `AbortSignal.timeout`; server-side `fetch` in route handlers/server components without timeout (Next `fetch` has none by default).

## What "good" looks like
```tsx
// client: cancellable, errors observed
useEffect(() => {
  const ac = new AbortController();
  fetch(`/api/orders/${id}`, { signal: ac.signal }).then(r => r.json()).then(setOrder).catch(e => { if (e.name !== 'AbortError') setError(e); });
  return () => ac.abort();
}, [id]);
// or with React Query
useQuery({ queryKey: ['order', id], queryFn: ({ signal }) => api.get(`/orders/${id}`, { signal }) });

// submit: awaited, failure shown
const onSubmit = async (dto) => { try { await save(dto); toast.success('Saved'); } catch (e) { toast.error(String(e)); } };

// server (Next): no per-request state at module scope; timeouts on upstream
export async function GET(req: Request) {
  const res = await fetch(PRICING_URL, { signal: AbortSignal.timeout(3000), next: { revalidate: 60 } });
  ...
}
```

## Manual trace checklist
1. Server code (Next/Remix): run `node-express.md` checks - module-level state, clients per request, timeouts, unawaited promises.
2. `useEffect` bodies with fetch: abort on cleanup? `.catch`?
3. Submit/pay/save handlers: awaited with error handling?
4. React Query `queryFn`s: pass `signal`?
5. `unstable_cache`/`cache()` keys include user/tenant where data is per-user?

## Stack-specific false positives
- `void queryClient.invalidateQueries()` - non-critical, has internal handling.
- `useEffect` fetch in a component that never unmounts (root layout) - abort still recommended, rate Low.

## Tooling
ESLint `react-hooks/exhaustive-deps`, `@typescript-eslint/no-floating-promises`, `@typescript-eslint/no-misused-promises` (async in `onClick`/`useEffect`), `eslint-plugin-react` `jsx-no-leaked-render`; React StrictMode (double-invokes effects - exposes missing cleanup); Next `experimental.instrumentationHook` for server errors.

## Hand-off
Client leaks: `audit-frontend-memory-leak`. Render/INP cost: `audit-performance-and-scalability`, `audit-frontend-best-practices`.

## References
CWE-390, CWE-248, CWE-1088; React docs "useEffect - fetching data" (cleanup/ignore flag), "Synchronizing with Effects"; TanStack Query "Query Cancellation"; Next.js "Route Handlers", "Server Actions - error handling", "Caching".
