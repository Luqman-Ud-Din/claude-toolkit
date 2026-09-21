# Vue (and Nuxt) reference for audit-backend-resource-leak

This skill is backend-only. Browser-side leaks (watchers, `setInterval` in
`onMounted` without `onUnmounted`, listeners, detached nodes) belong to
`audit-frontend-memory-leak`. Nuxt server routes (`server/api/**`,
`server/middleware/**`, Nitro plugins) run on the server and are audited here
with the `node-express.md` rules.

## Stack markers
`package.json` with `vue` or `nuxt`. If `nuxt` is present, treat `server/**`
and the `nitro` section of `nuxt.config.ts` as backend code. Plain Vue + Vite
has no server side; only the "feeds backend leaks" section applies.

## Where the relevant code lives (server side)
`server/api/**/*.ts`, `server/routes/**`, `server/middleware/*.ts`,
`server/plugins/*.ts` (run once per Nitro instance - anything registered here
lives for the process), `server/utils/*.ts` (shared DB clients, caches),
`nuxt.config.ts` (`nitro.storage`, `routeRules` cache settings).

## Dangerous / interesting APIs and patterns (server side)
- DB clients (`new PrismaClient()`, `createPool()`, `MongoClient`) created inside `defineEventHandler` instead of a `server/utils` singleton.
- Module-level `Map`/array caches in `server/utils` without `max`/TTL; prefer `cachedEventHandler({ maxAge })` or `useStorage()` with a TTL-capable driver.
- `setInterval` in a Nitro plugin without `nitroApp.hooks.hook('close', ...)` cleanup.
- Streams returned with `sendStream(event, stream)` whose source is not destroyed on `event.node.req.on('close')`.
- `readMultipartFormData(event)` buffering whole uploads in memory with no size check.
- `defineEventHandler` middleware that pushes into a module-level array (request logs).

## Frontend behaviours that feed backend leaks
- `useFetch`/`useAsyncData` with `refresh()` on an interval, or `watch` on route params triggering refetches - sets the real RPS.
- `useWebSocket` (VueUse) with `autoReconnect` and no backoff - reconnect storm against the server's connection registry.
- Pinia stores that poll in `onMounted` of a layout (layouts are rarely unmounted) - permanent polling.
- Upload components: record max file size and endpoint.

## What "good" looks like
```ts
// server/utils/db.ts - one client per Nitro instance
export const prisma = new PrismaClient();

// server/plugins/sync.ts - interval with cleanup
export default defineNitroPlugin((nitroApp) => {
  const t = setInterval(() => sync().catch(console.error), 30_000);
  nitroApp.hooks.hook('close', () => clearInterval(t));
});

// cached route with a bound
export default cachedEventHandler(handler, { maxAge: 60, swr: true });
```

## Manual trace checklist (for the backend audit)
1. Run the node-express pattern file over `server/**`.
2. List polling composables with period and endpoint.
3. List WebSocket usage and reconnect policy.
4. List streaming and multipart routes; confirm close handling and size limits.

## Stack-specific false positives
- `server/utils` singletons (module scope is per Nitro instance - intended).
- `cachedEventHandler` / `routeRules` caching - bounded by the storage driver; note the driver.

## Tooling
Server side: same as node-express.md; `NODE_OPTIONS=--inspect node .output/server/index.mjs`. Nitro `cachedEventHandler` cache size is driver-dependent - check the configured `storage` driver's limits.

## Hand-off
Client-side leaks: `audit-frontend-memory-leak`. Over-fetching and re-render cost: `audit-performance-and-scalability` / `audit-frontend-best-practices`.

## References
CWE-401, CWE-772, CWE-400; Nuxt docs "Server directory", "Nitro plugins", "Caching"; h3 docs `sendStream`, `readMultipartFormData`.
