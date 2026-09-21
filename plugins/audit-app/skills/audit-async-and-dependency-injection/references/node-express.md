# Node / Express (NestJS, Fastify, Koa) reference for audit-async-and-dependency-injection

## Stack markers
`package.json` with `express`, `@nestjs/core`, `fastify`, `koa`. Container: NestJS (`@Injectable`, `@Module` providers; default singleton, `Scope.REQUEST`/`Scope.TRANSIENT` bubble up), `tsyringe`/`inversify`/`awilix` (explicit lifetimes: `Lifecycle.Singleton`/`ContainerScoped`/`ResolutionScoped`, `inSingletonScope()`/`inRequestScope()`, `asClass().scoped()`), or none (plain Express - module scope is the singleton, closures are the scope). Single-threaded: BLOCK here means blocking the event loop, which stalls every request at once.

## Where the relevant code lives
`*.module.ts` (providers, `useFactory`, `useValue`), `*.service.ts` (`@Injectable({ scope })`, constructors), `*.controller.ts`, `main.ts`/`app.ts` (middleware, error handlers), `container.ts`/`di.ts` (tsyringe/inversify/awilix), `jobs/`, `queues/`, `lib/http.ts` (axios instances), `utils/asyncHandler.ts`.

## Dangerous / interesting APIs and patterns
- BLOCK: `deasync`, `Atomics.wait`, `execSync`/`spawnSync`, `*Sync` fs/crypto/zlib calls on request paths, busy loops `while (!done) {}`, CPU-heavy sync work (`JSON.parse` of MBs, `sort` of 100k items, `bcrypt.hashSync`) - not deadlocks but event-loop stalls with the same symptom (p99 spikes, health checks failing).
- VOID: `async` route handlers in Express 4 without a wrapper - a rejected promise never reaches `next(err)` (request hangs until timeout, error unlogged; Express 5 handles it); `async` callbacks passed to `EventEmitter.on`, `setInterval`, `setTimeout`, `forEach`, `array.map` without `Promise.all` - rejections become `unhandledRejection` (crash on Node 15+ or silent if a handler swallows); `.then(cb)` without `.catch`; Nest lifecycle hooks/guards returning promises that are not awaited.
- CANCEL: `fetch`/axios calls without `signal`; `req.on('close')`/`req.aborted`/`request.signal` ignored in streaming or long handlers (work continues after the client left); `AbortController` created but never `abort()`ed on response end; DB queries with no statement timeout.
- FIRE: `somethingAsync();` on its own line inside a handler (no `await`, no `.catch`); `void somethingAsync()` as a habit without `.catch`; `setImmediate(async () => ...)` for "background" work (lost on crash, no retry); `process.nextTick` with async work; queue jobs added without `await` (`queue.add(...)` unawaited - the enqueue itself can fail).
- HTTP: `axios.create(...)` inside a handler/service method (new instance and interceptors per request); `new https.Agent()` per request; `got.extend` per call; `new PrismaClient()` / `new Pool()` / `new MongoClient()` per request or per Nest request-scoped provider; `new Redis()` per call.
- TIMEOUT: `axios.create()` without `timeout`; bare `fetch(url)`; `http.request` without `timeout`/`setTimeout`; `undici.request` without `headersTimeout`/`bodyTimeout`; `server.setTimeout` left default; no retry/breaker (`axios-retry`, `p-retry`, `opossum`, `cockatiel`).
- DI: Nest singleton (default) injecting a `Scope.REQUEST` provider - the singleton silently becomes request-scoped (new instance per request, `onModuleInit` per request, caches reset) - and `Scope.TRANSIENT` providers injected into singletons are created once per consumer (not per use); `@Inject(REQUEST)` in a default-scoped provider (compile-fine, runtime undefined/`Scope.REQUEST` forced); `ModuleRef.get()` used for request-scoped providers without `resolve()` + `contextId` (throws or returns wrong instance); providers registered with `useValue` holding request state; global mutable module state written per request in plain Express (`let currentUser` at module scope - a race and a leak); awilix `asClass(X).singleton()` depending on `.scoped()` (captive, same as .NET); inversify singleton depending on `inRequestScope()`; `new Service()` bypassing the container (loses lifecycle hooks and shared state).

## What "good" looks like
```ts
// Express 4: wrap async handlers (or use express-async-errors / Express 5)
const wrap = (fn: RequestHandler) => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);
router.post('/orders', wrap(async (req, res) => { res.status(201).json(await orders.create(req.body, { signal: AbortSignal.timeout(5000) })); }));

// module-level clients, one per process, with timeouts
export const pricing = axios.create({ baseURL: env.PRICING_URL, timeout: 3000, httpAgent: new http.Agent({ keepAlive: true }) });
axiosRetry(pricing, { retries: 2, retryDelay: axiosRetry.exponentialDelay });

// Nest: keep singletons singleton; resolve request data per call
@Injectable() export class OrdersService {
  constructor(private readonly prisma: PrismaService, private readonly moduleRef: ModuleRef) {}
  async create(dto: OrderDto, ctx: RequestContext) { ... }          // pass request context as an argument, not as an injected REQUEST-scoped provider
}
// if a request-scoped provider is truly needed:
@Injectable({ scope: Scope.REQUEST }) export class TenantContext { constructor(@Inject(REQUEST) private req: Request) {} }
// consumers of TenantContext become request-scoped too - accept that consciously, or use ModuleRef.resolve(TenantContext, contextId)

// fire-and-forget that survives restarts and reports errors
await invoiceQueue.add('submit', { invoiceId }, { attempts: 3, backoff: { type: 'exponential', delay: 5000 } });
setInterval(() => tick().catch(err => logger.error({ err }, 'tick failed')), 30_000);
```
`process.on('unhandledRejection', (e) => { logger.fatal(e); process.exit(1); })` so lost rejections are loud, not silent.

## Manual trace checklist
1. Express version and async handling: Express 4 without a wrapper -> every `async` route is a VOID candidate; list them.
2. `di_lifetimes.py` rows: Nest providers with `Scope.REQUEST`/`TRANSIENT` and who injects them (bubbling); awilix/inversify/tsyringe singleton -> scoped edges.
3. Every `setInterval`/`EventEmitter.on`/`forEach` with an async callback: `.catch` present?
4. Every outbound client: module-level instance? timeout? keep-alive agent? retry/breaker?
5. Every `void promise` / bare `promise;` statement: business-critical? then queue it.
6. Streaming/long handlers: `req.on('close')` or `request.signal` honoured?
7. Plain Express module state: any `let` at module scope mutated per request (`currentTenant`, `cache`)?

## Stack-specific false positives
- `*Sync` calls at module load (config, templates) - startup only.
- `void this.metrics.increment()` for fire-and-forget telemetry that is non-critical and has its own error handling.
- `axios.create` in a factory function called once at module load.
- Nest `Scope.REQUEST` on a provider that is meant to be per-request (`TenantContext`) - flag only the singletons that inject it unknowingly.
- `new PrismaClient()` guarded by `globalThis` singleton pattern.

## Tooling
- ESLint: `@typescript-eslint/no-floating-promises` (FIRE/VOID), `@typescript-eslint/no-misused-promises` (async callbacks where void expected), `@typescript-eslint/require-await`, `no-sync`, `promise/catch-or-return`, `no-await-in-loop` (perf).
- Runtime: `node --trace-uncaught`, `process.on('unhandledRejection')` logging in staging, `clinic doctor` (event-loop delay under load = BLOCK), `perf_hooks.monitorEventLoopDelay`, `npx why-is-node-running` for stuck handles.
- Nest: `NEST_DEBUG=true` logs provider instantiation (request-scoped providers show as instantiated per request); `ModuleRef.introspect(Token).scope` in a test to assert scopes.

## References
CWE-833, CWE-400, CWE-390, CWE-248, CWE-1088; Node.js "Don't Block the Event Loop", "Event Loop, Timers, process.nextTick"; Express "Error handling - handling errors in async functions"; NestJS "Injection scopes" (scope hierarchy/bubbling), "Module reference - resolving scoped providers"; awilix "Lifetime management".
