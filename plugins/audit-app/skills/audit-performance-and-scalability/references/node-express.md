# Node / Express (NestJS, Fastify, Koa) reference for audit-performance-and-scalability

## Stack markers
`package.json` with `express`, `@nestjs/core`, `fastify`, `koa`. Single-threaded event loop: one blocking call stalls every request; horizontal scaling is `cluster`/PM2/containers - anything in process memory is per worker. Sub-variants: Nest (interceptors for caching/compression, `@nestjs/throttler`), Fastify (built-in `@fastify/compress`), serverless (Lambda/Vercel - cold start and per-invocation state).

## Where the relevant code lives
`app.ts`/`main.ts`/`server.ts` (middleware order: `compression()`, `express-session`, body limits), `*.service.ts` (sequential awaits, sync calls), `*.controller.ts`/`routes/*.ts` (payload shapes, inline work), `config/*.ts` (pool sizes, timeouts), `lib/http.ts`/`clients/*.ts` (axios/fetch instances), `Dockerfile`/`ecosystem.config.js` (cluster mode).

## Dangerous / interesting APIs and patterns
- BLOCK: `fs.readFileSync`/`writeFileSync`/`existsSync` in handlers, `child_process.execSync`, `crypto.pbkdf2Sync`/`bcrypt.hashSync`/`scryptSync` (CPU on the loop), `JSON.parse` of multi-MB bodies, `zlib.gzipSync`, sync loops over big arrays (`sort`/`map` on 100k items), `await` inside `for` over independent items, `deasync`.
- SEQ: `const a = await x(); const b = await y(); const c = await z();` with independent inputs -> `Promise.all`/`Promise.allSettled`; `for (const i of items) await fetch(...)` -> `p-limit`/`Promise.all` with a cap.
- CACHE: no cache layer (`cache-manager`, `ioredis`, `lru-cache`, Nest `CacheModule`/`CacheInterceptor`, `apicache`) while reference data is fetched per request; no `Cache-Control`/ETag on public GETs (`res.set('Cache-Control', ...)`, `etag` is on by default in Express but only helps with 304); cache with no invalidation in write handlers; `lru-cache` per worker for tenant data that must be coherent.
- COMPRESS: no `compression()` (Express/Koa `koa-compress`) or `@fastify/compress` or Nest `app.use(compression())`; compression applied after routes; reverse proxy (nginx `gzip on`) not confirmed either.
- PAYLOAD: `res.json(await prisma.x.findMany())` / `repo.find()` (full entities, `include` graphs); no `select`; `class-transformer` `@Exclude` missing; base64 images in JSON; `JSON.stringify` of large graphs per request.
- CHATTY: `GET /x/:id` used per row by the client; no batch endpoint; GraphQL resolvers without DataLoader (N calls per list).
- POOL: `pg` `Pool({ max })` default 10 per worker; Prisma `connection_limit` default `num_cpus*2+1` per instance (x cluster workers x instances vs DB max); `http.Agent` `maxSockets` default Infinity (fine) but `keepAlive` false on Node < 19 (new TCP per upstream call - set `keepAlive: true`); `undici` `Agent` `connections`.
- TIMEOUT: `axios.create()` without `timeout`; `fetch` without `AbortSignal.timeout()`; `http.request` without `timeout`; no retry/backoff (`axios-retry`, `p-retry`) or circuit breaker (`opossum`, `cockatiel`); `server.timeout`/`headersTimeout`/`keepAliveTimeout` defaults behind ALBs (must exceed the LB idle timeout).
- ALLOC: `Buffer.concat` of whole uploads, `array.concat` in loops, `lodash.cloneDeep` per request, `new RegExp` per call, `moment()` per row, template compilation per request (`handlebars.compile`).
- INLINE-BG: sending email (`nodemailer`), PDF (`puppeteer`, `pdfkit`), image resize (`sharp`) or third-party submissions inside the request; "fixed" with un-awaited promises (lost on crash) instead of `bullmq`/SQS.
- STATE: `express-session` with the default `MemoryStore` (or `cookie-session` OK; `connect-redis` OK); `socket.io` without `@socket.io/redis-adapter`; module-level `Map` caches of tenant data; uploads written to local disk (`multer.diskStorage` to a non-shared path); `node-cron` in every worker (duplicate runs); rate limiter with in-memory store (`express-rate-limit` default) - per worker, not per user.

## What "good" looks like
```ts
app.use(compression({ threshold: 1024 }));                              // before routes
app.use(session({ store: new RedisStore({ client: redis }), ... }));    // shared store
const http = axios.create({ baseURL, timeout: 3000 }); axiosRetry(http, { retries: 2, retryDelay: axiosRetry.exponentialDelay });
const breaker = new CircuitBreaker(() => http.get('/rates'), { timeout: 2000, errorThresholdPercentage: 50, resetTimeout: 30000 });

const [customer, quote, tax] = await Promise.all([customers.get(id), pricing.quote(items), tax.rate(region)]);
const products = await prisma.product.findMany({ where, take, skip, select: { id: true, name: true, price: true } });
await queue.add('invoice.submit', { orderId });                          // bullmq, not inline
res.set('Cache-Control', 'public, max-age=300'); 
```
Rate limiter and cache with Redis stores; `pg` `Pool({ max: 20 })` sized against `max_connections / (workers x instances)`.

## Manual trace checklist
1. Middleware order in `app.ts`: compression, session store, body limits, rate limiter store.
2. Landing/main list handler: awaits in series, `select` on ORM calls, payload width.
3. Checkout/save: upstream calls (timeouts? parallel?), inline email/PDF/image work.
4. Every axios/fetch/http client: timeout, retry, breaker; `keepAlive` agent.
5. Process model: `cluster`/PM2 instances? Then every in-memory store is per worker - list them.
6. `server.keepAliveTimeout` > LB idle timeout (ALB 60 s -> set 65 s) to avoid 502s under load.

## Stack-specific false positives
- `readFileSync` at module load (startup) - fine.
- Sequential awaits where the second uses the first.
- `MemoryStore` in a dev-only server file.
- `bcrypt.hash` (async) - fine; only `*Sync` variants block.

## Tooling
- `clinic doctor -- node dist/main.js` (event-loop delay, CPU, active handles under load); `clinic flame`; `node --cpu-prof`; `0x`.
- `perf_hooks.monitorEventLoopDelay()` or `@nestjs/terminus` event-loop indicator; `prom-client` default metrics (`nodejs_eventloop_lag_seconds`).
- `autocannon` for quick per-endpoint p99; `npx why-is-node-running` for stuck handles.
- ESLint: `no-sync`, `@typescript-eslint/no-floating-promises`, `no-await-in-loop`.

## References
CWE-400, CWE-1050, CWE-1088, CWE-1072; Node.js "Don't Block the Event Loop"; Express "Production best practices: performance"; NestJS "Caching", "Compression"; Prisma "Connection pool".
