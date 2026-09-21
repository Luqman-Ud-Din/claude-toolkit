# .NET / ASP.NET Core reference for audit-performance-and-scalability

## Stack markers
`*.csproj`, `Program.cs`. Sub-variants: Kestrel behind Ocelot/YARP (gateway adds a hop - measure both), IIS in-process, Hangfire for background work, EF Core (query layer -> `audit-orm-query-and-data-access`), SignalR.

## Where the relevant code lives
`Program.cs`/`Startup.cs` (compression, response/output caching, session, HttpClient registrations, pool settings), `appsettings*.json` (connection string `Max Pool Size`, Kestrel limits), `ocelotconfig.json` (`QoSOptions` timeouts/circuit breaker, `FileCacheOptions`), `*Manager.cs`/`*Service.cs` (sequential awaits, sync-over-async), `Controllers/**` (payload shapes, inline background work), `Extensions/` (AutoMapper - full-entity mapping).

## Dangerous / interesting APIs and patterns
- BLOCK: `.Result`, `.Wait()`, `.GetAwaiter().GetResult()`, `Task.Run(...).Result`, `Thread.Sleep` in request paths; sync `File.ReadAllText`/`Stream.Read` on large files; `HttpClient.Send` (sync) - thread-pool starvation shows as p95 rising with low CPU.
- SEQ: two or more `await client.GetAsync(...)`/`await _manager.X.GetAsync(...)` in a row where the second does not use the first's result -> `Task.WhenAll`. Also `foreach (...) await ...` over independent items (bounded parallelism with `Parallel.ForEachAsync` or `SemaphoreSlim`).
- CACHE: no `AddResponseCaching`/`AddOutputCache`/`IMemoryCache`/`IDistributedCache` anywhere; reference data (units, currencies, tax rates, permissions) fetched per request; `[ResponseCache(NoStore = true)]` on cacheable GETs; caches with no invalidation on the write path; `HybridCache` (NET 9) absent when both local and Redis are used.
- COMPRESS: no `AddResponseCompression()`/`UseResponseCompression()`; Brotli/Gzip providers not added; `EnableForHttps` false (default - JSON over HTTPS is then never compressed); gateway does not compress either.
- PAYLOAD: controllers returning entities (`return Ok(await _db.X.ToListAsync())`) or `Include`d graphs; AutoMapper mapping entity -> DTO that copies every column; `JsonSerializerOptions` default (no `DefaultIgnoreCondition = WhenWritingNull`); Newtonsoft with `ReferenceLoopHandling.Serialize`; byte[] images in JSON.
- CHATTY: endpoints that return one record when the UI calls them in loops (`GetById` called per row); no batch endpoint; frontend `GetPaginationList` + `GetCount` + `GetFilters` on every grid load.
- POOL: `Max Pool Size` absent (default 100 per connection string - per instance, per tenant DB string in multi-tenant setups); `ThreadPool.SetMinThreads` hacks (symptom of BLOCK); `HttpClientHandler.MaxConnectionsPerServer`; Kestrel `MaxConcurrentConnections`.
- TIMEOUT: `new HttpClient()` / `AddHttpClient` without `.Timeout` or `AddStandardResilienceHandler()` (Polly); `CommandTimeout` default 30 s on long reports; SqlClient `Connect Timeout`; Ocelot route without `QoSOptions` (`TimeoutValue`, `ExceptionsAllowedBeforeBreaking`); SMS/FBR/Shopify clients with no retry/backoff.
- ALLOC: `JsonConvert.SerializeObject` of large graphs per request, `string +=` in loops, `MemoryStream.ToArray()`, `Regex` per call, LINQ `ToList()` chains, EPPlus/ImageSharp on the request thread (-> INLINE-BG).
- INLINE-BG: email/SMS/PDF/Excel/image resize/FBR submission executed inside the request before responding; `Task.Run` fire-and-forget as the "fix" (unobserved, lost on restart) - use Hangfire `BackgroundJob.Enqueue` or a queue.
- STATE: `AddSession()` with the default in-memory `IDistributedCache` (`AddDistributedMemoryCache`) - breaks with 2 instances unless sticky; `static` mutable caches of tenant data; `AddDataProtection()` without `PersistKeysTo*` (cookies/antiforgery invalid across instances); files written to local disk (`wwwroot/uploads`, `Path.GetTempPath()`) as durable state; SignalR without `AddStackExchangeRedis` backplane; Hangfire with in-memory storage.

## What "good" looks like
```csharp
builder.Services.AddResponseCompression(o => { o.EnableForHttps = true; o.Providers.Add<BrotliCompressionProvider>(); o.Providers.Add<GzipCompressionProvider>(); });
builder.Services.AddOutputCache(o => o.AddPolicy("catalog", p => p.Expire(TimeSpan.FromMinutes(5)).SetVaryByQuery("page", "pageSize").Tag("products")));
builder.Services.AddStackExchangeRedisCache(o => o.Configuration = cfg["Redis"]);       // IDistributedCache + session store
builder.Services.AddSession();                                                          // now backed by Redis
builder.Services.AddDataProtection().PersistKeysToStackExchangeRedis(redis, "dp-keys");
builder.Services.AddHttpClient("fbr", c => { c.BaseAddress = new(cfg["Fbr:Url"]); c.Timeout = TimeSpan.FromSeconds(10); })
                .AddStandardResilienceHandler();                                        // retry + circuit breaker + timeout
app.UseResponseCompression(); app.UseOutputCache();

var (customer, quote, tax) = await (custTask, quoteTask, taxTask);                       // or Task.WhenAll
[HttpPost] public async Task<IActionResult> Create(OrderDto dto, CancellationToken ct) { ...; BackgroundJob.Enqueue<IInvoiceJob>(j => j.SubmitToFbr(id)); return Accepted(); }
```
Invalidate: `await _outputCache.EvictByTagAsync("products", ct)` in the product write path.

## Manual trace checklist
1. Landing page + main list: walk controller -> manager -> DB; count awaits in series and DB round-trips; note the DTO width vs the grid columns.
2. Checkout/save flow: sequential upstream calls (FBR, SMS, pricing), inline PDF/Excel/email, transaction length.
3. `Program.cs`: compression, output/response cache, session store, data protection, HttpClient timeouts, Hangfire storage - each is a one-line yes/no for the scaling-blockers table.
4. Ocelot: `QoSOptions`, `FileCacheOptions`, `RateLimitOptions` per route; gateway compression.
5. Connection strings: `Max Pool Size`, `Min Pool Size`; multi-tenant DB-per-tenant means N pools per instance - check `Max Pool Size` x tenants x instances against the SQL Server max connections.
6. Every `new HttpClient`/`AddHttpClient`: timeout, retry, circuit breaker.

## Stack-specific false positives
- `.Result` on an already-completed `Task.FromResult` or `ValueTask` in tests/startup code.
- Sequential awaits where the second depends on the first (read the arguments).
- `AddDistributedMemoryCache` in a single-instance internal tool with sticky sessions documented - rate Low, note the constraint.
- `Task.Run` in a `BackgroundService` (not a request path).

## Tooling
- `dotnet-counters monitor -p <pid> --counters System.Runtime,Microsoft.AspNetCore.Hosting,Microsoft.AspNetCore.Http.Connections,Microsoft.Data.SqlClient.EventSource` (requests/sec, current requests, threadpool queue length - a rising queue with low CPU = BLOCK).
- `dotnet-trace collect -p <pid> --profile cpu-sampling` during the load test; open in PerfView/Visual Studio.
- `dotnet-counters ... System.Runtime[threadpool-queue-length,threadpool-thread-count]`.
- Analyzers: `Microsoft.VisualStudio.Threading.Analyzers` (VSTHRD002 sync-over-async), `AsyncFixer` (AsyncFixer02), `Meziantou.Analyzer` MA0004/MA0045.
- MiniProfiler / Application Insights dependency map for per-endpoint upstream timings.

## References
CWE-400, CWE-1050, CWE-1088, CWE-1072; Microsoft docs "ASP.NET Core Best Practices" (performance), "Response compression", "Output caching", "Distributed caching", "Session state - scaling", "HttpClient resilience (Microsoft.Extensions.Http.Resilience)", "Hangfire background jobs".
