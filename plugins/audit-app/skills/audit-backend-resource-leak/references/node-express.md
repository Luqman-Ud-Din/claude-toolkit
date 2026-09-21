# Node / Express (NestJS, Fastify, Koa) reference for audit-backend-resource-leak

## Stack markers
`package.json` depending on `express`, `fastify`, `koa`, `@nestjs/core`, `hapi`. Sub-variants: NestJS (DI - providers are singletons by default, so instance fields are process-lifetime state), plain Express (module-level `let`/`const` collections are the singleton equivalent), worker processes (`bull`, `bullmq`, `agenda`, `node-cron`).

## Where the relevant code lives
`app.ts`/`server.ts`/`main.ts`, `middleware/`, `services/` or `*.service.ts`, `jobs/`, `workers/`, `queues/`, `utils/cache*.ts`, any module with top-level `const x = []`/`new Map()`, WebSocket servers (`ws`, `socket.io`), file upload handlers (`multer`, `busboy`).

## Dangerous / interesting APIs and patterns
- Disposal: `fs.createReadStream`/`createWriteStream` without `pipeline()` or `.destroy()` on error; `fs.open`/`fs.promises.open` without `close()`; `new Pool()`/`createConnection()` per request (pg, mysql2, mongodb `MongoClient` per call); `pool.connect()` client never `release()`d; `axios` responses with `responseType: 'stream'` not consumed; `fetch` response body never read or cancelled (undici keeps the socket); `new PrismaClient()` per request; `new Worker()` (worker_threads) per request; `net.connect`/`tls.connect` without `end()`; `zlib` streams not ended; `sharp()` pipelines not consumed.
- Timers: `setInterval` in a request handler or in a class constructed per request, no `clearInterval`; `setTimeout` referenced from a closure holding `req`/`res`; `AbortController` timers never cleared.
- Growth: module-level arrays/maps with `push`/`set` and no `splice`/`delete`/`clear`; `Map` keyed by session/user/request id; `EventEmitter` listeners added per request (`emitter.on(...)` inside a handler - Node warns at 11 listeners, then keeps adding); `process.on('unhandledRejection')` inside a function called repeatedly; socket.io rooms/user maps never cleaned on `disconnect`.
- Cache: `node-cache` without `stdTTL`/`maxKeys`; `lru-cache` without `max`; hand-rolled `Map` cache; NestJS `CacheModule.register()` without `ttl`/`max`; `memoizee`/`lodash.memoize` on functions with unbounded argument space.
- Hot-path allocation: `Buffer.concat` on unbounded uploads, `JSON.parse` of full bodies without `limit`, `Array.from(bigSet)` per request, `Buffer.alloc(large)` per request, regex construction per call.
- Background workers: `setInterval(async () => { try { ... } catch {} })`; `bull` processors with `catch (e) {}`; queue jobs that append to a module-level array; unhandled promise in `setInterval` callback (unlogged since Node 15 crashes the process only for unhandledRejection, not for swallowed catch).

## What "good" looks like
```ts
import { pipeline } from 'node:stream/promises';
await pipeline(fs.createReadStream(path), res);              // closes both on error

const cache = new LRUCache<string, Product>({ max: 5000, ttl: 10 * 60_000 });

@Injectable()
export class SyncWorker implements OnModuleDestroy {
  private timer = setInterval(() => this.tick().catch(e => this.log.error(e)), 30_000);
  onModuleDestroy() { clearInterval(this.timer); }
}

const client = await pool.connect();
try { await client.query(...); } finally { client.release(); }
```
One `PrismaClient`/`MongoClient`/`Pool` per process, created at module scope or as a Nest provider.

## Manual trace checklist
1. Module-level and provider-level mutable collections: list all writers, prove a remover or a bound (`max`, TTL, keyed by a small enum).
2. Every `setInterval`/`setTimeout`/`EventEmitter.on`/`process.on`: is it at module scope (once) or inside a function that runs per request/connection? Per-request means leak unless cleared/removed on completion.
3. WebSocket servers: on `close`/`disconnect`, are the user/room maps, intervals, and listeners removed?
4. DB clients and pools: exactly one per process? `release()` in `finally`? Prisma `$disconnect` in shutdown hooks?
5. Streams: `pipeline()` used, or `on('error')` plus `destroy()` on every branch? Upload handlers enforce `limits.fileSize`?
6. Queue/cron workers: exceptions logged; per-job state discarded; `concurrency` bounded; `removeOnComplete`/`removeOnFail` set (Redis growth is a leak too).
7. `fetch`/`undici`: every response either consumed (`.json()`, `.text()`, `.body.cancel()`) or the request aborted.

## Stack-specific false positives
- `setInterval` at module scope in a long-lived singleton with `.unref()` or cleared in `onModuleDestroy` - intended.
- `new Map()` at module scope keyed by route or enum - bounded.
- `emitter.on` registered once inside a class constructor of a singleton provider.
- `fs.createReadStream(...).pipe(res)` in Express - `res` end destroys the source in modern Node; still prefer `pipeline` for error paths but do not rate above Low.
- `new PrismaClient()` guarded by a `globalThis` singleton pattern (common in Next.js).

## Tooling
- `node --inspect app.js`, Chrome DevTools > Memory > take heap snapshot before and after 15 min; compare "Objects allocated between snapshots", sort by retained size.
- `node --trace-gc app.js 2>&1 | grep Mark-sweep` - heap after each mark-sweep should plateau.
- `node --heapsnapshot-signal=SIGUSR2 app.js` then `kill -USR2 <pid>` to write snapshots without an inspector.
- Sampling script for `leak_loadtest.py`: `setInterval(() => { const m = process.memoryUsage(); console.log([Date.now(), m.rss, m.heapUsed, process.getActiveResourcesInfo().length].join(',')); }, 15000)` or `ps -o rss= -p <pid>` from the shell.
- FDs: `lsof -p <pid> | wc -l` (Linux/macOS); handles: `process.getActiveResourcesInfo()` (Node 17+), `process._getActiveHandles().length`.
- `clinic doctor -- node app.js` / `clinic heapprofiler`; `npx autocannon` as the load driver if k6 is not installed.
- ESLint: `no-restricted-syntax` rules for `new PrismaClient`, `eslint-plugin-node` `no-sync`.

## References
CWE-401, CWE-404, CWE-772, CWE-770, CWE-390; Node.js docs "Diagnostics - Memory", "stream.pipeline", "Events - maxListeners"; undici "Garbage collection" note on unconsumed bodies; Prisma "Connection management" guide.
