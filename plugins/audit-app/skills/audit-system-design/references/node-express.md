# Node / Express (NestJS, Fastify, Koa) reference for audit-system-design

## Stack markers
`package.json` with `express`/`fastify`/`koa`/`@nestjs/core`. Variants: single app; monorepo with `workspaces` (npm/yarn/pnpm), Nx, Turborepo, Lerna; NestJS modules (`@Module` imports graph); serverless (`serverless.yml`, `netlify/functions`); BullMQ/Bull (Redis queues), `amqplib`, `kafkajs`, `@aws-sdk/client-sqs`; `cockatiel`/`opossum`/`p-retry`/`axios-retry` for resilience.

## Where the architecture is visible
- `package.json` `workspaces` / `pnpm-workspace.yaml` / `nx.json` / `turbo.json`: packages and their `dependencies` on each other = module graph. Single app: top-level folders under `src/` (`modules/`, `features/`, `domain/`, `infra/`) and the relative-import graph between them (`module_graph.py --ts-root src`).
- NestJS: `@Module({ imports: [...] })` graph, `forwardRef(() => X)` = a circular module reference the team already noticed.
- `app.ts`/`main.ts`: middleware order (where auth runs), `app.listen` ports, `helmet`, proxy trust.
- `.env*`, `config/*.ts`: `DATABASE_URL` (one per service?), `REDIS_URL`, `RABBITMQ_URL`/`AMQP_URL`, `KAFKA_BROKERS`, external API base URLs.
- `docker-compose*.yml`, `k8s/`, `Procfile`, `serverless.yml` - runtime units and replicas.
- Queues: `new Queue('name')`/`new Worker('name')` (BullMQ), `channel.assertQueue`, `consumer.subscribe` - async edges. `axios.create({ baseURL })`, `fetch(` to other services - sync edges.

## Design smells to grep (mirrored in `scripts/patterns/node-express.json`)
- Module-level mutable state used across requests (`let cache = {}`, `const sessions = new Map()`), `global.` assignments, `express-session` with `MemoryStore` (default), `socket.io` without a Redis adapter, `node-cache`/`lru-cache` as source of truth.
- `axios`/`fetch`/`got` without `timeout`/`AbortSignal.timeout`; no retry/breaker (`opossum`, `cockatiel`) around external calls; `setTimeout` retry loops without backoff; `catch (e) {}` swallowing.
- Controllers/route handlers importing `prisma`/`knex`/`mongoose` models directly while a `services/` or `repositories/` layer exists (layer skip); `domain/` importing from `infra/` or `express`.
- `forwardRef(` in NestJS; relative imports crossing module roots (`../../orders/internal/...`).
- Two packages/services with Prisma models or Knex tables of the same name; `prisma.$transaction` mixed with `queue.add`/`fetch` inside (dual write) with no outbox.
- `setInterval`/`node-cron` schedulers in every instance without a lock (Redis `SET NX` / BullMQ repeatable jobs).
- `fs.writeFile('uploads/...')`, `multer({ dest: 'uploads/' })` - local disk state.
- Sync CPU work in request handlers (`zlib.gzipSync`, `bcrypt.hashSync`, big JSON parsing) blocking the event loop.
- Unauthenticated internal routes (`/internal/`, `/admin/` without middleware); services with `PORT` published in compose bypassing the gateway; `app.set('trust proxy', true)` on an exposed service.
- `process.on('uncaughtException', () => {})` swallowing crashes; no graceful shutdown (`server.close` on SIGTERM).
- God modules: `utils/index.ts` or `helpers.js` > 1000 lines imported everywhere.

## What "good" looks like
```ts
// outbound edge with timeout + breaker + retry
const fbr = axios.create({ baseURL: env.FBR_URL, timeout: 10_000 });
const breaker = new CircuitBreaker((inv) => fbr.post('/invoice', inv), { timeout: 12_000, errorThresholdPercentage: 50, resetTimeout: 30_000 });
await pRetry(() => breaker.fire(invoice), { retries: 3, factor: 2 });
// outbox: insert event row in the same transaction; a worker relays to the queue
await prisma.$transaction([prisma.sale.create({ data }), prisma.outbox.create({ data: { type: 'SaleCreated', payload } })]);
// shared state in Redis; socket.io with @socket.io/redis-adapter; sessions in connect-redis
// graceful shutdown
process.on('SIGTERM', async () => { server.close(); await worker.close(); await prisma.$disconnect(); });
```
NestJS layering: `domain` module has no imports from `infrastructure`; providers bound to interfaces via tokens.

## Manual trace checklist
1. Gateway/reverse proxy -> services -> `DATABASE_URL`s: draw; note shared DBs.
2. Every outbound HTTP client: timeout, retry, breaker, fallback.
3. Every queue producer/consumer: Redis/broker instance count and persistence (`appendonly`), job `attempts`/`backoff`, idempotency by job id, failed-job handling.
4. Schedulers: single-runner guarantee.
5. Process state: sessions, sockets, caches, uploads vs replicas; sticky sessions assumed?
6. Where auth middleware is mounted relative to routes; internal routes reachable without it.
7. ADR/README claims vs the above.

## Stack-specific false positives
- Module-level `const` immutable config; memoised pure functions.
- `MemoryStore` in a dev-only server file; `setInterval` health pings.
- Workspace packages with DTO/types only and high fan-in.
- `forwardRef` between two NestJS modules that are deliberately one bounded context (still note it).

## Tooling
- `npx madge --circular --extensions ts src` (import cycles), `npx dependency-cruiser --validate` with layer rules, `nx graph`, `pnpm -r list --depth 1`.
- `npx clinic doctor -- node dist/main.js` for event-loop blocking evidence.
- `docker compose config`; `redis-cli info replication` (read-only) if a live Redis is offered.

## References
- NestJS docs (Modules, Circular dependency), Node.js "Don't block the event loop", microservices.io patterns (outbox, saga, circuit breaker), BullMQ docs (repeatable jobs, retries).
- ASVS 1.x, CWE-306, CWE-362, CWE-770, CWE-400.
