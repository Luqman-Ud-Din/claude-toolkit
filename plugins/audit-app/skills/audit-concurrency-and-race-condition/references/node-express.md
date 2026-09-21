# Node / Express (and NestJS, Fastify, Koa) reference for audit-concurrency-and-race-condition

## Stack markers
`package.json` with `express`, `@nestjs/core`, `fastify`, `koa`. Variants: ORM (Prisma, TypeORM, Sequelize, Mongoose, Knex); queues (BullMQ, Bee, SQS consumers); schedulers (`node-cron`, `@nestjs/schedule`, BullMQ repeat); cluster mode / PM2 / k8s replicas (every module-level variable is per process, never shared).

## Where the relevant code lives
- Handlers: `router.post/put/patch/delete`, `@Post()`/`@Put()`/`@Delete()`, webhook routes, queue `Worker`/`process` callbacks.
- Data: `services/*.ts` (`findOne` then `create`; `findOne` then `update`), `prisma.$transaction`, `sequelize.transaction`, `queryRunner.startTransaction`, Mongoose `session.withTransaction`.
- Schema: `schema.prisma` (`@unique`, `@@unique`), TypeORM `@Unique`/`@Index({ unique: true })`, Sequelize `unique: true`, Mongoose `unique: true` (index, only if built), Knex `.unique()`.
- Shared state: module-level `let`/`const` objects and arrays (`const cache = {}`), NestJS providers (singletons by default), `global.*`, class static fields.
- Jobs: `cron.schedule`, `@Cron`, `queue.add(..., { repeat })`, `setInterval` loops.

## Dangerous / interesting APIs and patterns
- Check-then-act with an `await` between: `const u = await repo.findOne({ email }); if (!u) await repo.create(...)`; `const s = await Stock.findById(id); if (s.qty >= q) { s.qty -= q; await s.save(); }`; `if (order.status === 'pending') await update({ status: 'paid' })`. Node is single-threaded but every `await` yields, so two requests interleave exactly here.
- No unique index behind the check: Prisma field without `@unique`, Mongoose `unique: true` with `autoIndex: false` in production, Sequelize model without the constraint in the migration.
- Idempotency: payment/refund/webhook routes with no `Idempotency-Key` handling; `stripe.paymentIntents.create(..., { idempotencyKey })` absent; webhook handler processing before recording `event.id`; BullMQ jobs without a deterministic `jobId` (duplicates on retry/re-add); `axios-retry`/`p-retry` around POSTs that move money.
- Optimistic concurrency: no `version` field (Sequelize `version: true`, Mongoose `__v` is not checked on `save()` by default for updates via `updateOne`, TypeORM `@VersionColumn`, Prisma manual `where: { id, version }` + `count === 0`); `updateMany`/`update` without a status/version condition.
- Transactions: multi-model writes without `$transaction`/`transaction()`; Mongoose multi-document writes without a session; Prisma interactive transaction with a long `await` on an external call inside it (lock held across HTTP).
- Shared state: module-level `Map`/object mutated per request (`const sessions = {}`), in-memory rate limiters (`express-rate-limit` default MemoryStore in a multi-replica deployment), counters (`let requestCount = 0`), request data cached on a singleton provider.
- Collections: plain objects/arrays/`Map` with a read, an `await`, then a write (`if (!cache[k]) { cache[k] = await load(k); }` double-loads; usually harmless, but for "claim" semantics it is a race).
- Jobs: `cron.schedule` in a module loaded by every replica (N copies run); `setInterval` where the async callback overruns; no Redis lock (`SET key val NX PX`, `redlock`); BullMQ repeatable jobs added on every boot with different options (duplicates).

## What "good" looks like
```ts
// uniqueness: constraint + handled violation
// schema.prisma: @@unique([companyId, email])
try { await prisma.user.create({ data }); } catch (e) { if (e.code === 'P2002') throw new ConflictError('email exists'); throw e; }
// atomic conditional update
const { count } = await prisma.stock.updateMany({ where: { id, qty: { gte: q } }, data: { qty: { decrement: q } } });
if (count === 0) throw new InsufficientStockError();
// optimistic version
const { count } = await prisma.order.updateMany({ where: { id, version: order.version }, data: { status: 'paid', version: { increment: 1 } } });
if (count === 0) return res.status(409).send('order changed, retry');
// idempotency key stored first
const inserted = await keys.tryInsert(req.header('Idempotency-Key'), req.body);
if (!inserted) return res.json(await keys.storedResponse(key));
await stripe.paymentIntents.create(params, { idempotencyKey: key });
// jobs: one leader or a lock
const lock = await redlock.acquire(['locks:expire-trials'], 60_000); try { await expireTrials(); } finally { await lock.release(); }
// shared state: Redis, not memory
const limiter = rateLimit({ store: new RedisStore({ client }) });
```

## Manual trace checklist
1. Every mutating route/consumer on money, stock, uniqueness: find the `await`ed read and the later write; is there a transaction, conditional update, or version check.
2. `grep -rn "findOne\|findFirst\|findUnique\|exists(" src` followed within 10 lines by `create(`/`save(`/`insert(`: check schema for `@unique`.
3. Module-level mutable state: `grep -rn "^const \w\+ = \(new Map\|{}\|\[\]\)\|^let " src`, NestJS provider fields; who writes them; replica count.
4. Payment/webhook/queue handlers: key or event-id dedupe; deterministic `jobId`; retry wrappers on side effects.
5. Version fields and 409 handling.
6. Cron/interval/repeat jobs: lock or leader election; overrun protection; body idempotent per item.
7. `$transaction`/`transaction()` coverage of multi-model writes; external calls inside transactions.

## Stack-specific false positives
- Module-level `const` config objects never mutated; `new Map()` filled at startup only.
- In-memory caches that are pure performance caches (double-load is harmless) - note but do not rate above Info.
- Single-process deployments documented as such (`pm2` with `instances: 1` and no k8s replicas) reduce job and memory-store findings to Low, not zero.
- Mongoose `save()` on a document loaded with `findOne` does check `__v` when `optimisticConcurrency: true` is set on the schema (confirm).

## Tooling
`grep -rn "@unique\|@@unique\|unique: true\|\.unique(" src prisma`; `npx prisma validate`; `eslint-plugin-node`/`require-atomic-updates` rule (flags read-await-write on shared variables); `autocannon -c 2 -a 2` or `scripts/double_submit.sh` against a test environment; `redis-cli monitor` for lock usage.

## References
CWE-362, CWE-367, CWE-662, CWE-820; Prisma transactions and P2002; Stripe idempotent requests; BullMQ repeatable jobs and `jobId`; ESLint `require-atomic-updates`; ASVS 11.1.4.
