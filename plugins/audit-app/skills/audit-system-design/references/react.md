# React / Next.js reference for audit-system-design

The React app is a client component in the system diagram; Next.js with route
handlers or server actions is also a backend and gets the `node-express.md`
treatment for its `app/api`, `pages/api` and server-action code. Component
quality belongs to `audit-frontend-best-practices`; API shapes to
`audit-api-contract`.

## Stack markers
`package.json` with `react`/`next`; monorepos via `workspaces`/Turborepo/Nx (`apps/*`, `packages/*` = module graph). Feature-sliced layouts (`src/features/*`, `src/entities/*`, `src/shared/*`) or `src/modules/*`.

## Where the architecture is visible
- Workspace packages and their mutual `dependencies`; inside an app, `src/features|modules|pages` folders and relative imports between them (`module_graph.py --ts-root src --ts-depth 1`).
- API layer: `src/api/*`, `services/*`, generated clients (`orval`, `openapi-typescript`), tRPC routers, GraphQL clients (Apollo/urql) - each base URL/endpoint set is an edge; a GraphQL gateway or BFF is a component.
- State: Redux/Zustand/Jotai stores, React Query/SWR caches, `localStorage` persistence - what state is duplicated from the server.
- Next.js: `middleware.ts` (edge auth boundary), route handlers, server actions calling ORMs directly (backend inside the frontend repo), `revalidate`/ISR (caching layer), `next.config.js` `rewrites` (proxying to services - the service map).
- Realtime: `socket.io-client`, `EventSource`, Pusher/Ably SDKs - stateful edges.
- `.env*` `NEXT_PUBLIC_*`/`VITE_*`/`REACT_APP_*` URLs - the list of backends the browser talks to.

## Design smells to grep (mirrored in `scripts/patterns/react.json`)
- Cross-feature imports (`features/orders` importing `features/billing/internal`), deep relative paths `../../../`, circular imports (`madge`).
- Multiple hard-coded backend origins; browser calling services directly instead of the gateway/BFF; websocket to a specific instance.
- Business rules duplicated on the client and trusted by the server (client-computed totals posted back).
- Global mutable singletons (`window.__state`, module-level `let` caches) used as source of truth.
- Polling (`refetchInterval`) on heavy list queries; N parallel calls per page that a BFF should aggregate.
- Next.js server actions/route handlers containing DB access with no service layer (layer skip), and `prisma` imported in components rendered on the server and in API routes across apps (shared DB between "services").
- `middleware.ts` matcher gaps leaving pages/APIs outside the auth boundary (delegate detail to authz skill; keep the boundary map).

## What "good" looks like
- One gateway/BFF origin (or tRPC/GraphQL gateway); features communicate through shared entities/hooks, not by importing each other's internals.
- Server state in React Query/SWR with the server as source of truth; client-only state in stores.
- Next.js server code layered (`app/api` -> `services` -> `repositories`), with the same resilience rules as any backend (timeouts, retries, outbox where it writes and publishes).

## Manual trace checklist
1. Enumerate backend origins and realtime endpoints; add each as an edge with the auth it carries.
2. Feature import graph: cross-feature edges and cycles.
3. State duplicated between client and server; the reconciliation strategy.
4. For Next.js: apply the backend checklist to server-side code; check whether the same DB is written by the Next app and another service.
5. Behaviour when a backend is down (error boundaries, retries, offline).

## Stack-specific false positives
- `shared/`/`packages/ui` high fan-in.
- Cross-feature type-only imports (Low, move to shared).
- `refetchInterval` on small status endpoints with documented reason.

## Tooling
- `npx madge --circular --extensions ts,tsx src`, `npx dependency-cruiser --validate`, `nx graph`, `turbo run build --graph`.
- `grep -rn "NEXT_PUBLIC_.*URL\|VITE_.*URL\|REACT_APP_.*URL" .env* src` to enumerate origins.

## References
- Feature-Sliced Design docs, Next.js docs (Middleware, Route Handlers, Server Actions, Caching), BFF pattern.
