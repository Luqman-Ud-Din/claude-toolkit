# Vue / Nuxt reference for audit-system-design

The Vue app is a client component in the system diagram; Nuxt `server/` code
(Nitro routes, server middleware, server utils with an ORM) is a backend and
gets the `node-express.md` treatment. Component quality belongs to
`audit-frontend-best-practices`; API shapes to `audit-api-contract`.

## Stack markers
`package.json` with `vue`/`nuxt`; monorepos via `workspaces`/Turborepo/Nx; layouts `src/modules/*`, `src/features/*`, `pages/`, `stores/` (Pinia), `composables/`, Nuxt `layers/`.

## Where the architecture is visible
- Workspace packages and Nuxt layers (`extends` in `nuxt.config`) - module graph; inside an app, top-level folders under `src/` and relative imports (`module_graph.py --ts-root src --ts-depth 1`).
- API layer: `composables/useApi*.ts`, `services/*`, `$fetch`/`ofetch` instances with `baseURL`, generated clients, GraphQL clients - each origin is an edge; `nuxt.config` `routeRules` with `proxy` and `nitro.devProxy` - the service map.
- State: Pinia stores (persisted via `pinia-plugin-persistedstate`?), `useState`, `localStorage` - duplicated server state.
- Nuxt server: `server/api/*`, `server/middleware/*` (auth boundary), `server/utils/db.ts` (ORM in the frontend repo), `nitro` storage/cache - backend components.
- Realtime: `socket.io-client`, SSE, WebSocket composables.
- `.env*` `NUXT_PUBLIC_*`/`VITE_*` URLs - backends the browser talks to.

## Design smells to grep (mirrored in `scripts/patterns/vue.json`)
- Cross-module imports (`modules/orders` importing `modules/billing/internal`), deep relative paths, circular imports.
- Multiple hard-coded backend origins; direct-to-service calls bypassing the gateway; websocket to a specific instance.
- Business rules duplicated on the client and trusted by the server.
- Module-level mutable singletons (`let cache = {}`), `window.` globals as shared state.
- Polling (`refresh` on `setInterval`, `useIntervalFn`) on heavy list endpoints.
- Nuxt `server/api` handlers with direct DB access and no service layer; ORM writes to tables another service also writes; server middleware matcher gaps leaving API routes outside auth (delegate detail; keep the map).

## What "good" looks like
- One gateway/BFF origin (or Nuxt server routes acting as the BFF); modules communicate via stores/composables in `shared`, not by importing each other's internals.
- Server state via `useAsyncData`/`useFetch` with the server as the source of truth; Pinia for client-only state.
- Nuxt server code layered (`server/api` -> `server/services` -> `server/repositories`) with timeouts/retries on outbound calls and an outbox where it writes and publishes.

## Manual trace checklist
1. Enumerate backend origins and realtime endpoints; add each as an edge with the auth it carries.
2. Module import graph: cross-module edges and cycles.
3. State duplicated between client and server; reconciliation strategy.
4. Nuxt server code: apply the backend checklist; shared DB with other services?
5. Behaviour when a backend is down.

## Stack-specific false positives
- `shared/`/`packages/ui` high fan-in.
- Type-only cross-module imports (Low, move to shared).
- Short polling on small status endpoints with a documented reason.

## Tooling
- `npx madge --circular --extensions ts,vue src`, `npx dependency-cruiser --validate`, `nx graph`.
- `grep -rn "NUXT_PUBLIC_.*URL\|VITE_.*URL" .env* src nuxt.config.*` to enumerate origins.

## References
- Nuxt docs (Server, Layers, Route rules), Pinia docs, BFF pattern.
