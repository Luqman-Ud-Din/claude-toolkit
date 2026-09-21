# React reference for audit-application

What the orchestrator needs to know about a React codebase (Vite, CRA, Next.js, React
Native/Expo) before it plans and runs the children. Topic detail lives in each child's
own `references/react.md`.

## Stack markers

- `package.json` depending on `react` or `next` (detect_stack id `react`).
- `next`: server code exists (`app/api/**/route.ts`, `pages/api/**`, server actions,
  `middleware.ts`). It is backend code even though detect_stack reports no backend id.
- `react-native` / `expo`: a mobile app. client-auth reviews `AsyncStorage` vs
  `expo-secure-store`/Keychain; accessibility uses mobile semantics; licensing treats
  distribution as `proprietary`.
- Build tool: `vite.config.*`, `react-scripts` (CRA), `next.config.*`.

## Where the relevant code lives

- `src/` (components, hooks, `api/` clients, context/store), `app/` or `pages/` (Next),
  `.env*` files (`VITE_*`, `REACT_APP_*` and `NEXT_PUBLIC_*` values are compiled into the
  bundle), `public/index.html` / `index.html` (inline scripts, CSP meta).
- Build output: `dist/` (Vite), `build/` (CRA), `.next/` + `out/` (Next).

## Dangerous / interesting APIs and patterns

Setup signals:

- **Server code in Next.js:** API routes and server actions query databases directly (Prisma,
  Drizzle). Treat them as the backend for authz, injection, orm, tenant isolation and
  secrets. `plan.py` cannot see this, so add the backend children explicitly (see false
  positives).
- **Where the backend is:** API base URLs in `.env*` and fetch/axios clients. For a SPA-only
  repo, ask for the backend root at setup.
- **Multi-tenant hints on the client:** org/workspace switchers, tenant ids in request
  headers, subdomain-based tenant routing in `middleware.ts`.
- **Token handling:** `localStorage`, `next-auth` session cookies, `AsyncStorage` in React
  Native.

## What "good" looks like

- Node version from `engines`/`.nvmrc` and a lockfile.
- `npm ci` possible; `npm run build` succeeds, so the bundle exists for frontend-best-
  practices and client-auth.
- For Next.js: a read-only `DATABASE_URL` or committed migrations (Prisma/Drizzle) for
  db-schema and orm.
- A running app (and backend) with a test account for accessibility (axe) and
  frontend-memory-leak (heap snapshots).

## Manual trace checklist

Prerequisites to confirm at setup:

1. Node + lockfile -> dependency-vulnerabilities, licensing.
2. Production build possible -> frontend-best-practices (bundle, source maps), client-auth
   (secrets in the bundle). Missing: `--limited "no production build"`.
3. Next.js or Remix server code present? If yes, plan the backend children as well (custom
   list) and confirm DB access for db-schema and orm.
4. Backend root for a SPA-only repo -> authz, tenant isolation, injection, api-contract.
5. Running app + account -> accessibility, frontend-memory-leak, performance.
6. React Native: the target platforms and the storage library in use -> client-auth.

## Stack-specific false positives

Wrong applicability calls to avoid:

- **Next.js detected as frontend only:** `plan.py` marks async, orm and backend-resource-leak n/a
  because detect_stack has no backend id for Next. If `app/api`, `pages/api` or server actions
  exist, override: `--profile custom --skills ...` including them, or run each with `--skill`,
  and state the reason in the run.
- **Vite SPA with no server:** async, orm, backend-resource-leak and api-contract are genuinely
  n/a. Injection and authz still run: client-built URLs, and guards shown to be cosmetic.
- **React Native:** frontend-memory-leak's DevTools heap procedure does not apply as written.
  Expect `limited access` on the confirmation step, not a skip.

## Tooling

```bash
node -v && npm -v
npm ci --ignore-scripts                     # ask first
npm run build
npx vitest run --coverage | npx jest --coverage
npm audit --json
npx next info                               # Next.js version and config, read-only
npx @axe-core/cli http://localhost:5173     # optional, served build
```

## Child applicability for React repos

| Repo shape | n/a children |
|---|---|
| SPA only (Vite/CRA) | async-and-dependency-injection, orm-query-and-data-access, backend-resource-leak, api-contract (unless a backend root is added) |
| Next.js with API routes / server actions | none; add the backend children the plan skipped |
| React Native / Expo | frontend-best-practices partially (no web bundle budgets); record gaps as limited access |

## References

- Child references: `../audit-client-auth-and-storage/references/react.md`,
  `../audit-frontend-xss-and-dom-safety/references/react.md`, `../audit-frontend-best-practices/references/react.md`.
- React docs (security notes on `dangerouslySetInnerHTML`), Next.js security and data-fetching docs, Expo SecureStore docs.
