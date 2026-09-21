# Angular reference for audit-system-design

The frontend is one component in the system diagram, but its structure reveals
coupling that the backend cannot: how many services it calls directly, where
it holds state that the backend also holds, and how far the module boundaries
in the SPA mirror (or contradict) the backend's. Component-level quality
belongs to `audit-frontend-best-practices`; API shapes to `audit-api-contract`.

## Stack markers
`package.json` with `@angular/core`; `angular.json` (projects: one app or a workspace with libs); Nx (`nx.json`, `project.json` per lib) means the TS import graph is the module graph.

## Where the architecture is visible
- `angular.json` projects and `tsconfig.json` `paths` (`@core`, `@shared`, `@env/*`) - the intended module boundaries.
- `src/app/features/*` (lazy-loaded modules/routes), `core/` (singletons), `shared/` - run `module_graph.py --ts-root src/app --ts-depth 2` to get feature-to-feature imports; features importing each other directly is coupling the routes were supposed to prevent.
- `environment*.ts` and `proxy.conf.json`: how many backend base URLs the client talks to (`/accountapi`, `/productapi`, `/api`, `/ws`) - one gateway vs direct-to-service (each direct edge is a trust boundary the gateway does not see).
- `core/interceptors/*` - where the JWT is attached, which endpoints are public, how 401 is handled (client-side view of the authn boundary).
- `core/services/*` - `WebSocket`/SignalR clients (stateful edge), `storage.service.ts` (what state lives in the browser), offline/PWA (`ngsw-config.json`) - state duplicated between client and server.
- Capacitor config - mobile builds are a second client with the same edges.

## Design smells to grep (mirrored in `scripts/patterns/angular.json`)
- Feature module importing another feature's components/services (`from '../../purchase/...'` inside `sale/`) - cross-feature coupling; `import ... from 'src/app/features/...'` deep paths bypassing barrels.
- Services `providedIn: 'root'` holding mutable business state that the backend also owns (cart, stock counts) without a sync strategy - dual source of truth.
- Multiple `HttpClient` base URLs hard-coded in components; calls to services that bypass the gateway; websocket URL pointing at a specific service instance (breaks with replicas unless the backend has a backplane).
- Business rules (pricing, tax, stock validation) implemented in the client and posted as results - the backend must be the owner.
- Polling loops (`interval(…).pipe(switchMap(...))`) against list endpoints - integration style mismatch (should be push or longer intervals).
- `localStorage` holding tokens/tenant selection that the backend trusts (delegate to `audit-client-auth-and-storage`; keep the boundary note).
- Route guards as the only authorization (cosmetic) - note as boundary; `audit-authz-and-access-control` owns the check.

## What "good" looks like
- One gateway base URL (or a BFF); feature modules communicate through `core` services or route parameters, never by importing each other.
- Server state fetched via a data-access layer (`core/services/api.service.ts`) with a single place to set headers, correlation ids and retries (`retry({ count: 2, delay: backoff })` only for idempotent GETs).
- Realtime through a hub URL that the backend load-balances with a backplane.
- The client computes for display only; totals are recomputed server-side.

## Manual trace checklist
1. Count backend base URLs and websocket endpoints; add each as an edge in the system diagram with the auth it carries.
2. Run the TS import graph at feature depth; list cross-feature edges and cycles.
3. Find state the client owns that the server also owns; decide who is the source of truth.
4. Check what the SPA does when a backend service is down (graceful degradation: error toast, retry, offline queue).

## Stack-specific false positives
- `shared/` and `core/` with high fan-in - expected.
- Feature -> feature imports of pure types/interfaces (should move to `shared/models`, Low).
- Polling on a dashboard with a long interval and a documented reason.

## Tooling
- `npx madge --circular --extensions ts src/app`, `npx dependency-cruiser --validate .dependency-cruiser.js src`, `nx graph` for Nx workspaces.
- `grep -rn "environment\.\(api\|base\)" src/app` to enumerate base URLs.

## References
- Angular architecture guide (feature/core/shared), Nx "Enforce module boundaries" lint rule, BFF pattern (Sam Newman).
