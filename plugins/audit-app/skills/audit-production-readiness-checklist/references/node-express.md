# Node / Express (NestJS, Fastify, Koa) reference for audit-production-readiness-checklist

## Stack markers
`package.json` with `express`/`fastify`/`koa`/`@nestjs/core`; `.env*` files; `Dockerfile` with `NODE_ENV`; `ecosystem.config.js` (pm2), `Procfile`, `serverless.yml`.

## Where each checklist item lives
- **Env config:** `dotenv` loaded only in development (`if (process.env.NODE_ENV !== 'production') require('dotenv').config()`), `.env.example` committed with placeholders, `.env`/`.env.production` in `.gitignore`; validated at boot (`zod`/`envalid`/`@nestjs/config` `validationSchema`); `config/` (node-config) with `production.json` holding no secrets. Fail: committed `.env.production` with real values; `NODE_ENV` unset in Dockerfile (express defaults to development behaviour).
- **Secrets:** `DATABASE_URL=postgres://user:pass@host`, `JWT_SECRET=`, `*_API_KEY=` with real values in committed `.env*` or in `config/*.json`, `src/config.ts` defaults like `process.env.JWT_SECRET || 'changeme'`.
- **Debug off:** `NODE_ENV=development` in Dockerfile/compose; `app.use(errorhandler())`; `morgan('dev')`; `DEBUG=*`; Nest `logger: ['debug','verbose']` in prod; `synchronize: true` (TypeORM) / `sequelize.sync({ alter: true })`; Swagger UI unauthenticated in prod; `express.static` serving source maps; `res.status(500).json({ stack: err.stack })`.
- **Health checks:** an unauthenticated `/health`/`/healthz` route; readiness must touch dependencies: Nest `@nestjs/terminus` (`TypeOrmHealthIndicator`, `MongooseHealthIndicator`, `MicroserviceHealthIndicator` for Redis/RabbitMQ, `HttpHealthIndicator`), or hand-rolled `await prisma.$queryRaw\`SELECT 1\`` / `redis.ping()` / `channel.checkQueue()`. Mounted before auth middleware. Dockerfile `HEALTHCHECK`/compose `healthcheck`/k8s probes must target it; `lightship`/`@godaddy/terminus` also handle shutdown.
- **Graceful shutdown:** `process.on('SIGTERM', ...)` calling `server.close()`, closing DB pools, `queue.close()`/`worker.close()` (BullMQ), `channel.close()`; Nest `app.enableShutdownHooks()`; pm2 `kill_timeout`; `stoppable`/`http-terminator` for keep-alive connections. Fail: no handler at all (Node exits immediately, dropping in-flight requests). Note Node ignores SIGTERM in some containers when not PID 1 without `tini`/`--init`.
- **Timeouts/retries:** `axios.create({ timeout })`, `fetch` with `AbortSignal.timeout(ms)`, `got` `timeout`, `undici` `bodyTimeout/headersTimeout`; pg `connectionTimeoutMillis`/`statement_timeout`, Prisma `connect_timeout`/`pool_timeout` in `DATABASE_URL`; retries via `p-retry`/`axios-retry`, breakers via `opossum`/`cockatiel`; `server.requestTimeout`/`headersTimeout` set on the HTTP server.
- **Caching:** `cache-manager` (+ redis store), `ioredis`, `node-cache`/`lru-cache` (per-instance), `apicache`; strategy documented?
- **Load test:** `k6/*.js`, `artillery*.yml`, `autocannon` scripts, `*.jmx`, `docs/perf*`.
- **Feature flags:** `unleash-client`, `launchdarkly-node-server-sdk`, `flagsmith-nodejs`, `@openfeature/server-sdk`, `growthbook`, or a `FEATURES` config with documented kill switches.
- **Runbook / rollback / launch checklist:** docs; deploy pipeline with rollback (`helm rollback`, `kubectl rollout undo`, Heroku `releases:rollback`, Vercel promote); Knex/TypeORM/Prisma reversibility (`audit-db-schema`).
- **Alerting:** Prometheus rules (`prom-client` metrics), Datadog/New Relic monitors in IaC, Sentry alert rules (`@sentry/node` presence shows error tracking, not alerting).

## What "good" looks like
```ts
// main.ts (Nest)
const app = await NestFactory.create(AppModule, { logger: env.NODE_ENV === 'production' ? ['error', 'warn', 'log'] : ['debug', 'verbose', 'log'] });
app.enableShutdownHooks();
// health.controller.ts
@Get('ready') @Public() ready() { return this.health.check([() => this.db.pingCheck('db'), () => this.ms.pingCheck('redis', { transport: Transport.REDIS, options: { url: env.REDIS_URL } })]); }
// http client
const fbr = axios.create({ baseURL: env.FBR_URL, timeout: 10_000 });
// express server
process.on('SIGTERM', async () => { server.close(); await pool.end(); await worker.close(); process.exit(0); });
```
Dockerfile: `ENV NODE_ENV=production`, `HEALTHCHECK CMD wget -qO- http://localhost:3000/health/ready || exit 1`, `ENTRYPOINT ["tini","--","node","dist/main.js"]`.

## Manual trace checklist
1. Dockerfile/compose: `NODE_ENV`, how `.env` reaches the container, any committed `.env.production`.
2. Health route: mounted before auth; does readiness touch DB/Redis/broker; probes target it.
3. Every outbound client and pool: timeout; retries only on idempotent calls.
4. SIGTERM handler closes server, pools, queues; PID 1 handling.
5. Pipeline rollback step; last migration has a working `down`.

## Stack-specific false positives
- `.env.example` / `.env.sample` with placeholders; `.env.test` with local values.
- `synchronize: true` only in a test DataSource.
- `morgan('dev')` guarded by `NODE_ENV`.
- `console.log` debugging is a logging-skill concern, not readiness.

## Tooling
- `NODE_ENV=production node -e "require('./dist/config')"` to see effective config (read-only); `curl localhost:3000/health/ready`.
- `npm ls @nestjs/terminus opossum p-retry unleash-client` to confirm libraries.

## References
- Node.js docs: "Health checks and graceful shutdown" (Express production best practices), NestJS Terminus docs, Twelve-Factor config.
- CWE-798, CWE-489, CWE-215, ASVS 14.x, OWASP A05:2021.
