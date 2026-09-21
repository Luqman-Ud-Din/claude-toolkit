# Node / Express (and NestJS, Fastify, Koa) reference for audit-finding-writer

## Stack markers
`package.json` depending on `express`, `fastify`, `koa`, `@nestjs/core`. TypeScript if `tsconfig.json` present.

## Where the relevant code lives
`routes/`, `controllers/`, `middleware/`, `app.ts`/`server.ts` (pipeline order), `.env*`, `prisma/` or `typeorm` entities, `jobs/`/`workers/`, `bull`/`agenda` queues.

## Remediation idioms
- Secrets: `process.env.X` loaded by `dotenv` in dev only, validated at boot (`zod`/`envalid`); `.env` in `.gitignore`; `.env.example` with placeholders.
- AuthZ: `passport`/custom JWT middleware applied per router (`router.use(requireAuth)`), ownership check in the handler (`where: { id, userId: req.user.id }`); NestJS `@UseGuards(AuthGuard, RolesGuard)` + `@Roles()`.
- Input: `zod`/`joi`/`class-validator` DTOs with `whitelist: true, forbidNonWhitelisted: true` (Nest `ValidationPipe`); never spread `req.body` into an ORM `create`.
- Data: Prisma/TypeORM/Knex parameter binding, no template-string SQL; `take`/`skip` paging; `include`/`relations` for N+1; `$transaction` for multi-write.
- Async: `async` handlers wrapped (`express-async-errors` or try/catch), `AbortSignal.timeout()` on `fetch`/`axios` `timeout`, `p-limit` for concurrency.
- Headers: `helmet()` first, `cors({ origin: [...], credentials: true })` with explicit list, `express-rate-limit` on auth routes, `express.json({ limit: '1mb' })`, `csurf`/double-submit for cookie sessions, `cookie: { httpOnly: true, secure: true, sameSite: 'strict' }`.
- Command/path: `execFile` with arg arrays instead of `exec`; `path.resolve` + prefix check for user-supplied paths.
- Multi-tenancy: tenant from `req.user.tenantId`, Prisma client extension adding `where: { tenantId }`, queue job payload carries `tenantId` and the worker re-validates it.
- Logging: `pino`/`winston` JSON, redact paths (`redact: ['req.headers.authorization', 'body.password']`), `pino-http` with request id.
- Dates: store ISO 8601 UTC strings or `Date` in UTC, `luxon`/`date-fns-tz` for zone math at the edge.

## Recurring references
CWE-798, CWE-89/943 (NoSQL), CWE-78 (command), CWE-22 (path), CWE-918 (SSRF), CWE-639, CWE-915, CWE-1321 (prototype pollution), CWE-352, ASVS 4.x, 5.x, 13.x, 14.4; OWASP A01, A03, A05, A08, A10.

## Stack-specific false positives
`eval` inside a bundler shim or test file; `cors()` with no options on a dev-only server; `exec` with a fully literal command string.

## Tooling
`npm audit --json`, `pnpm audit`, `yarn npm audit`, `npx eslint-plugin-security`, `npx semgrep --config p/nodejs`, `node --inspect` + heap snapshots for leaks.
