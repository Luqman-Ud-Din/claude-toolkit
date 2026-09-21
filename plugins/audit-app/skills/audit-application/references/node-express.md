# Node / Express reference for audit-application

What the orchestrator needs to know about a Node backend (Express, Fastify, Koa, NestJS,
Hapi) before it plans and runs the children. Topic detail lives in each child's own
`references/node-express.md`.

## Stack markers

- `package.json` depending on `express`, `fastify`, `koa`, `@nestjs/core`, `hapi` /
  `@hapi/hapi` (detect_stack id `node-express`).
- Server templates: `ejs`, `pug`, `handlebars`/`hbs`, `nunjucks` dependencies with `views/`
  folders. XSS and accessibility then apply without an SPA.
- Monorepos: `pnpm-workspace.yaml`, `workspaces` in the root `package.json`, `nx.json`,
  `turbo.json`, `lerna.json`. detect_stack walks four directory levels; list each app package
  root explicitly when the tree is deeper.

## Where the relevant code lives

- Entry: `src/main.ts` (Nest), `src/app.(js|ts)`, `server.(js|ts)`, `index.js`.
- Routes: `routes/`, `controllers/`, Nest `*.controller.ts`, Fastify plugins.
- Data: `prisma/schema.prisma` + `prisma/migrations`, `knexfile` + `migrations/`, TypeORM
  `entities/` + `migrations/`, Mongoose `models/`.
- Config: `.env.example`, `config/`, `src/config/`. Jobs: BullMQ/Bull queues, `node-cron`,
  Agenda.

## Dangerous / interesting APIs and patterns

Setup signals:

- **Multi-tenant hints:** `tenantId`/`organizationId`/`workspaceId` on `req.user` or in the JWT,
  `AsyncLocalStorage` tenant context, Prisma client extensions/middleware adding a tenant
  `where`, Mongoose tenant plugins, Postgres `SET search_path` per request (schema-per-tenant),
  `CREATE POLICY` (RLS) in migrations, `x-tenant-id` headers.
- **Background work:** BullMQ workers, `node-cron` expressions (zones), `setInterval` loops.
  These concern concurrency, datetime and leak.
- **Real-time:** `socket.io`, `ws`, SSE. They pair with frontend-memory-leak and leak.
- **Next.js / Nuxt server code:** see the react/vue references. API routes there are backend
  code even without Express.

## What "good" looks like

- Node version from `engines` / `.nvmrc` installed: `node -v`.
- A lockfile (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`). `npm audit` refuses to run
  without one, and dependency-vulnerabilities never creates it.
- `npm ci` possible (network or cache) -> licensing reads `node_modules/*/package.json` licences.
- `npm run build` / `tsc --noEmit` succeeds; `npm test -- --coverage` runs.
- A read-only `DATABASE_URL` for a non-production DB, or migrations in the repo.
- Test URL + two users, two tenants, staging URL, running instance for load tests. Full git
  history.

## Manual trace checklist

Prerequisites to confirm at setup:

1. Node installed at the required version and a lockfile committed -> dependency-vulnerabilities,
   licensing. Missing lockfile: `--limited "no lockfile; npm audit not possible"`.
2. `node_modules` present or installable (ask first) -> licensing licence resolution, frontend
   bundle checks for full-stack repos.
3. Build and tests runnable -> test-coverage, technical-debt.
4. Migrations/schema present or read-only DB -> db-schema, orm, concurrency.
5. Which env file or secret source production uses (`.env.production`, platform env, Vault)
   -> secrets, readiness.
6. Test/staging URLs and accounts for the authz, tenant and headers probes; instance count in
   production (concurrency assumes N > 1 when unknown).

## Stack-specific false positives

Wrong applicability calls to avoid:

- **API-only Node service:** frontend-best-practices, frontend-memory-leak and client-auth are n/a.
  XSS and accessibility are n/a only without server templates.
- **NestJS with a `client/` Angular or React folder:** detect_stack finds both if the nested
  `package.json` is within depth 4. If not, add the frontend children explicitly.
- **Serverless functions** (`serverless.yml`, `netlify/functions`, `api/` on Vercel) with no
  Express dependency: detect_stack reports no backend, so `plan.py` would skip async, orm and
  leak as n/a. Override with `--profile custom` including them, and record why.

## Tooling

```bash
node -v && npm -v
npm ci --ignore-scripts            # ask first; writes node_modules only
npm audit --json                   # needs a lockfile
pnpm audit --json | yarn npm audit --json
npx tsc --noEmit
npm test -- --coverage
npx prisma validate                # schema sanity, read-only
git rev-parse --is-shallow-repository
```

## Child applicability for Node repos

| Repo shape | n/a children |
|---|---|
| API only | frontend-best-practices, frontend-memory-leak, client-auth-and-storage; XSS and accessibility unless templates exist |
| Full-stack monorepo (API + SPA) | none, but pass each package root |
| Worker / queue consumer only | expect api-contract and headers to record "no HTTP surface" |

## References

- Child references: `../audit-authz-and-access-control/references/node-express.md`,
  `../audit-multi-tenant-isolation/references/node-express.md`, `../audit-dependency-vulnerabilities/references/node-express.md`.
- Express security best practices, NestJS security docs, npm audit docs.
