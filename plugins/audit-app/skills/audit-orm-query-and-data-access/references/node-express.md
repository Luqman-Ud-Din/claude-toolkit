# Node / Express (Prisma, TypeORM, Sequelize, Mongoose, Knex) reference for audit-orm-query-and-data-access

## Stack markers
`package.json` with `@prisma/client`, `typeorm`, `sequelize`, `mongoose`, `knex`, `drizzle-orm`, `objection`. NestJS wraps them in `@InjectRepository`/`PrismaService`. Tracking is N/A for all of these; the TRACKING class becomes "full entity loaded where a `select` projection would do".

## Where the relevant code lives
`prisma/schema.prisma` (`@@index`, relations), `src/**/entities/*.ts` (TypeORM `@Entity`, `@Index`, `eager: true`), `models/*.ts` (Sequelize/Mongoose schemas, `index: true`), `*.service.ts` / `*.repository.ts` / `controllers/` / `routes/`, `migrations/`.

## Dangerous / interesting APIs and patterns
- NPLUS1: `for (const x of rows) { await prisma.y.findUnique(...) }`, `await Promise.all(rows.map(r => repo.findOne(...)))` (parallel N+1 - still N queries), `for ... await x.getChildren()` (Sequelize), `for ... await Model.findById(x.ref)` (Mongoose); TypeORM `relations` missing so `entity.children` is undefined and the code fetches per row; Sequelize `include` missing; Mongoose `populate` missing; GraphQL resolvers without DataLoader.
- UNBOUNDED: `prisma.x.findMany()` with no `take`; `repo.find()` / `find({ where })` with no `take`/`skip` (TypeORM); `Model.findAll()` with no `limit` (Sequelize); `Model.find()` with no `.limit()` (Mongoose); `knex('t').select()` with no `.limit()`; `res.json(await ...findMany())` straight from a route.
- TRACKING/over-fetch: `findMany` with no `select` on wide tables; TypeORM `find` returning full entities with `eager` relations; Mongoose docs returned without `.lean()` (hydration cost) or `.select()`.
- INDEX: `where: { companyId, status }` / `orderBy: { createdAt }` with no `@@index([companyId, status])` in `schema.prisma`, no `@Index()` in TypeORM entity, no `index: true`/`schema.index()` in Mongoose; `contains` with no `mode`/index; `$regex` with leading `.*`.
- TXN: two `create`/`update` calls on different models in one handler without `prisma.$transaction([...])` or `$transaction(async tx => ...)`; TypeORM `save` x2 without `dataSource.transaction(...)`/`QueryRunner`; Sequelize without `sequelize.transaction(async t => ...)` and `{ transaction: t }` passed to each call; Mongoose multi-document writes without `session.withTransaction`; a `$transaction` opened but an inner call uses the global `prisma` not `tx`.
- INEFFICIENT: `(await findMany()).length > 0` / `count() > 0` (use `findFirst` / `exists` semantics); `findMany()` then `.filter()` in JS; `include` of large relations never used; `findMany({ include: { everything } })`; Mongoose `.populate()` deep chains; `SELECT *` via Knex `select()` without columns; `Promise.all` over thousands of queries with no concurrency cap.

## What "good" looks like
```ts
// paged, projected, bounded
const pageSize = Math.min(Number(req.query.pageSize ?? 20), 100);
const [items, total] = await Promise.all([
  prisma.product.findMany({ where: { companyId, deleted: false }, orderBy: { name: 'asc' },
    skip: (page - 1) * pageSize, take: pageSize, select: { id: true, name: true, price: true } }),
  prisma.product.count({ where: { companyId, deleted: false } }),
]);

// N+1 fix: one IN query, then map
const products = await prisma.product.findMany({ where: { id: { in: lines.map(l => l.productId) } } });
const byId = new Map(products.map(p => [p.id, p]));

// multi-table write
await prisma.$transaction(async tx => { await tx.sale.create(...); await tx.stockMovement.createMany(...); await tx.ledger.create(...); });

const exists = (await prisma.product.findFirst({ where: { sku }, select: { id: true } })) !== null;
```
Mongoose: `Model.find(q).select('name price').limit(n).lean()`; Sequelize: `findAndCountAll({ where, limit, offset, attributes })`.

## Manual trace checklist
1. Every route/controller that returns the result of `findMany`/`find`/`findAll` directly: paged? projected? entity growth class?
2. Every `for`/`map` with `await` on an ORM call in the body; parallel `Promise.all` N+1 counts as N+1 (rate one level lower if bounded by `p-limit`).
3. Multi-model writes in services: transaction present and *passed through* (`tx`, `{ transaction }`, `session`)?
4. `schema.prisma` `@@index` / TypeORM `@Index` / Mongoose indexes vs the `where`/`orderBy` columns on the top endpoints -> `audit-db-schema`.
5. GraphQL: resolvers for list fields use DataLoader or `include`?
6. Exports/reports: streaming (`cursor`, `stream()`, `findMany` in `take`-sized batches with `cursor`) or full load?

## Stack-specific false positives
- `findMany` on reference tables (currencies, roles) - bounded.
- `count()` used for `total` alongside a paged query - correct.
- `for` loops writing in a transaction (batch insert) - write-side loops are not read N+1; still note if `createMany` would do.
- Prisma `include` - batched (one query per relation), not per row; only flag if the included relation is unused or huge.
- Mongoose `.populate()` - batched per path; flag only deep chains on list endpoints.

## Tooling
- Logging blocks in `references/query-logging.md` (Prisma `$on('query')`, TypeORM `logging`, Sequelize `logging`, Mongoose `debug`).
- `prisma` CLI: `npx prisma validate`; `npx prisma format`; look for models with relations but no `@@index` on FK columns (Prisma does not auto-index FKs on PostgreSQL).
- ESLint: `@typescript-eslint/no-floating-promises` (catches unawaited ORM calls), custom `no-restricted-syntax` for `findMany()` with no `take` in `controllers/**`.
- `typeorm` `maxQueryExecutionTime` slow log; `mongoose` `explain()` for index use.

## References
CWE-1049, CWE-770, CWE-662; ASVS-12.1.1; Prisma docs "Query optimization / performance", "Transactions"; TypeORM "Find Options", "Transactions"; Sequelize "Eager Loading"; Mongoose "populate", "lean".
