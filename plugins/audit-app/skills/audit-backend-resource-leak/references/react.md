# React (and Next.js) reference for audit-backend-resource-leak

This skill is backend-only. Browser-side leaks (effects without cleanup,
listeners, timers, detached nodes) belong to `audit-frontend-memory-leak`.
Next.js blurs the line: `app/api/*` route handlers, server actions,
`middleware.ts`, and `getServerSideProps` run on the server and are audited
here with the `node-express.md` rules.

## Stack markers
`package.json` with `react`, `react-dom`, optionally `next` or `remix`. If
`next` is present, treat `app/api/**/route.ts`, `pages/api/**`, `middleware.ts`,
`instrumentation.ts`, and any file with `'use server'` as backend code. Remix:
`app/routes/**` loaders/actions and `server.ts`.

## Where the relevant code lives (server side)
`app/api/**/route.ts`, `pages/api/*.ts`, `lib/db.ts` / `lib/prisma.ts` (client
singletons), `instrumentation.ts` (runs once per server instance), server
actions, `next.config.js` (`serverExternalPackages`), any module-level
`Map`/array in a file imported by a route.

## Dangerous / interesting APIs and patterns (server side)
- `new PrismaClient()` in a route file without the `globalThis` guard - one client and pool per hot reload and per lambda instance (`DISP-DBCLIENT-PER-REQUEST` in node-express patterns).
- Module-level caches in route files without `max`/TTL; Next's `unstable_cache`/`revalidate` is bounded, a hand-rolled `Map` is not.
- `setInterval` in `instrumentation.ts` or route modules that runs per import; per-request `setInterval` in a streaming route.
- Streaming responses (`new ReadableStream`) whose upstream is never cancelled when the client disconnects (`request.signal` ignored) - the server keeps producing into a dead stream.
- Server actions that append to module-level arrays (audit logs, "recent uploads").
- `fetch` responses in route handlers not consumed on error paths (undici keeps the socket).

## Frontend behaviours that feed backend leaks
- React Query / SWR `refetchInterval` polling and `refetchOnWindowFocus` - sets the real RPS for the load-test plan.
- `useEffect` fetch without `AbortController` cleanup: the server still processes the request; StrictMode double-invokes effects in dev, doubling load on a dev backend.
- WebSocket hooks that reconnect on every render (missing dependency array) - a reconnect storm against the server's connection registry.
- Upload components: record max file size and endpoint.

## What "good" looks like
```ts
// lib/prisma.ts - one client per process
const g = globalThis as unknown as { prisma?: PrismaClient };
export const prisma = g.prisma ?? new PrismaClient();
if (process.env.NODE_ENV !== 'production') g.prisma = prisma;

// route handler honouring client disconnect
export async function GET(req: Request) {
  const stream = new ReadableStream({ start(c) { const t = setInterval(() => c.enqueue('tick'), 1000);
    req.signal.addEventListener('abort', () => { clearInterval(t); c.close(); }); } });
  return new Response(stream);
}
```

## Manual trace checklist (for the backend audit)
1. Run the node-express pattern file over `app/api`, `pages/api`, `lib`, `instrumentation.ts`, `middleware.ts`.
2. List polling hooks (`refetchInterval`, `useSWR` `refreshInterval`) with period and endpoint.
3. List WebSocket hooks and reconnect policy.
4. List streaming routes and confirm `request.signal` handling.

## Stack-specific false positives
- `globalThis`-guarded Prisma singleton (above).
- `unstable_cache` / `revalidateTag` - bounded by Next's data cache.
- `setInterval` in `instrumentation.ts` `register()` with a single-instance guard.

## Tooling
Server side: same as node-express.md (`NODE_OPTIONS=--inspect next start`, `--trace-gc`, `process.memoryUsage()`). Vercel/serverless: watch per-invocation memory in the platform dashboard - a module-level leak shows as rising memory across warm invocations of the same instance.

## Hand-off
Client-side leaks: `audit-frontend-memory-leak`. Re-render and over-fetch cost: `audit-performance-and-scalability` / `audit-frontend-best-practices`.

## References
CWE-401, CWE-772, CWE-400; Next.js docs "Route Handlers", "Instrumentation", "Streaming"; Prisma "Best practice for instantiating PrismaClient with Next.js".
