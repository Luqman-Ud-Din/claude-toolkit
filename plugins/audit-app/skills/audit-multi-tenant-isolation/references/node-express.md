# Node / Express reference for audit-multi-tenant-isolation

## Stack markers
`package.json` with `express`/`@nestjs/core` plus an ORM (`sequelize`, `typeorm`, `prisma`, `mongoose`). Tenancy via a Sequelize default scope / global `where`, TypeORM subscriber, Prisma extension, or an explicit `tenantId` on every query.

## Where the relevant code lives
`models/` (scopes, hooks), `routes/`/`controllers/`, `middleware/tenant*.js` (resolves tenant from token), workers/queues (`bull`, `agenda`, `bee-queue`, cron), cache (`ioredis`/`node-cache`), file/S3 code.

## Dangerous / interesting APIs and patterns
- Raw queries: `sequelize.query(...)`, `knex.raw(...)`, Prisma `$queryRaw` - ORM scopes/hooks do not apply; add `WHERE tenantId = ?`.
- `Model.unscoped()` / `withoutGlobalScope` - default tenant scope removed.
- `Model.findByPk(id)` / `findOne({ id })` with no `tenantId` in the where clause.
- Tenant id from `req.body.tenantId` / `req.query.tenantId` / a client header trusted directly (resolve it from `req.user`).
- Workers/cron jobs process rows across tenants with no per-tenant scoping.
- Cache keys without tenant; S3/file keys without a tenant prefix.

## What "good" looks like
```js
// tenant resolved once from the token, attached to req
app.use((req, _res, next) => { req.tenantId = req.user.tenantId; next(); });
const inv = await Invoice.findOne({ where: { id, tenantId: req.tenantId } });
await Invoice.create({ ...fields, tenantId: req.tenantId });   // never req.body.tenantId
const key = `tenant:${req.tenantId}:invoice:${id}`;
const s3Key = `${req.tenantId}/documents/${id}.pdf`;
```

## Manual trace checklist
1. Every raw query and `unscoped()` - tenant predicate present?
2. Every `findByPk`/`findOne`/`find` in a route - `tenantId` in the where?
3. Writes set `tenantId` from `req.user`, not the body.
4. Queue consumers / cron - tenant scope per job?
5. Cache keys and object-store keys include tenant.

## Stack-specific false positives
Raw query with a bound `tenantId` parameter; a Sequelize `defaultScope`/global hook that injects `tenantId` (then per-call omission is fine - verify the hook exists); admin dashboards that span tenants and are authorized.

## Tooling
`eslint-plugin-security`, `semgrep`, `scripts/data_access_paths.py`, `scripts/tenant_probe.py`.

## References
CWE-284, CWE-639, CWE-524, CWE-668. ASVS 4.1/4.2, 8.1. OWASP A01:2021.
