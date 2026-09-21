# .NET / ASP.NET Core reference for audit-async-and-dependency-injection

## Stack markers
`*.csproj`, `Program.cs` / `Startup.cs`. Container: `Microsoft.Extensions.DependencyInjection` (or Autofac/Scrutor on top - `RegisterAssemblyTypes`, `Scan(...)` registrations are invisible to the parser; list them in not_checked). Sub-variants: controllers vs minimal APIs, Hangfire (`JobActivator` resolves from a scope per job), `BackgroundService`/`IHostedService` (singletons), gRPC, SignalR hubs (transient per invocation).

## Where the relevant code lives
`Program.cs`/`Startup.cs` and `*Configuration/ConfigureServicesExtensions.cs` (all `Add*` registrations), `Controllers/**`, `*Manager.cs`/`*Service.cs`, `BackgroundJobs/`, `Middleware/`, `Filters/`, `Extensions/` (HttpClient helpers), `Hubs/`.

## Dangerous / interesting APIs and patterns
- BLOCK: `.Result` (not `Task.FromResult`), `.Wait()`, `.GetAwaiter().GetResult()`, `Task.WaitAll`, `Task.Run(...).Result`, `.RunSynchronously()`, `Thread.Sleep`, `SemaphoreSlim.Wait()` (vs `WaitAsync`), `lock` around an `await` (compile error) or `.Result` inside `lock`; `AsyncHelper.RunSync` helpers; sync-over-async inside constructors and property getters.
- VOID: `async void` (any method that is not an event handler `(object sender, EventArgs e)`); `async` lambdas passed to `Action` parameters (`Task.Run(async () => ...)` is fine, `list.ForEach(async x => ...)` is `async void`); `Timer` callbacks that are `async void`.
- CANCEL: controller actions without a `CancellationToken ct` parameter; `ToListAsync()`/`SaveChangesAsync()`/`SendAsync(req)`/`Task.Delay(ms)`/`ReadAsync(buf)` without the token; `CancellationToken.None`/`default` passed; `BackgroundService.ExecuteAsync` loops using `Task.Delay(x)` without `stoppingToken`; `HttpContext.RequestAborted` unused for streaming.
- FIRE: `_ = FooAsync();`, `FooAsync();` on its own line (CS4014 warning), `Task.Run(() => FooAsync())` not stored, `Task.Factory.StartNew` with async lambda (returns `Task<Task>` - the inner is unobserved), `ThreadPool.QueueUserWorkItem`, `TaskScheduler.UnobservedTaskException` handler as the "fix".
- HTTP: `new HttpClient()` anywhere outside `AddHttpClient` configuration; `new HttpClientHandler()` per call; `HttpClient` as a `static` without `PooledConnectionLifetime` (DNS staleness); `WebClient`/`HttpWebRequest` (legacy, sync); `RestSharp` `new RestClient()` per call.
- TIMEOUT: `AddHttpClient` without `c.Timeout` or `AddStandardResilienceHandler()`; `SqlCommand.CommandTimeout = 0`; `CommandTimeout(0)` in EF; Ocelot routes without `QoSOptions`; `SmtpClient` default; `HttpClient.Timeout = Timeout.InfiniteTimeSpan`.
- DI: `AddSingleton<X>` where `X`'s constructor takes a type registered Scoped (`AddDbContext`, `AddScoped`, `IHttpContextAccessor` is fine - singleton) or Transient+`IDisposable`; `AddHostedService<X>` with scoped constructor parameters; `services.BuildServiceProvider()` inside `ConfigureServices`; `IServiceProvider` injected into services and `GetService` called per method (service locator - hides lifetimes); `static` fields holding services; `new SomeManager(dbContext)` manual construction; `HttpContextAccessor.HttpContext` read in a singleton constructor (null or stale); `AddDbContext` + `AddSingleton<IRepositoryWrapper>` (the wrapper captures the context); Hangfire jobs resolving from the root provider (`JobActivator` not configured for scopes).

## What "good" looks like
```csharp
// registrations
builder.Host.UseDefaultServiceProvider(o => { o.ValidateScopes = true; o.ValidateOnBuild = true; });   // container rejects captive scoped deps at startup
builder.Services.AddDbContext<AppDbContext>(...);                    // scoped
builder.Services.AddScoped<IProductManager, ProductManager>();       // same lifetime as DbContext
builder.Services.AddSingleton<ITaxRateCache, TaxRateCache>();        // depends only on singletons
builder.Services.AddHttpClient<IFbrClient, FbrClient>(c => { c.BaseAddress = new(cfg["Fbr:Url"]); c.Timeout = TimeSpan.FromSeconds(10); })
                .AddStandardResilienceHandler();

// singleton that needs scoped work
public class TaxRateCache(IServiceScopeFactory scopes)
{
    public async Task RefreshAsync(CancellationToken ct)
    {
        using var scope = scopes.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        _rates = await db.TaxRates.AsNoTracking().ToListAsync(ct);
    }
}

// action: async all the way, token threaded through
[HttpPost] public async Task<IActionResult> Submit(InvoiceDto dto, CancellationToken ct)
{
    var result = await _fbr.SubmitAsync(dto, ct);
    return Ok(result);
}

// background loop honours stoppingToken; errors observed
while (!stoppingToken.IsCancellationRequested) { try { await Work(stoppingToken); } catch (OperationCanceledException) { break; } catch (Exception ex) { _log.LogError(ex, "tick failed"); } await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken); }

// fire-and-forget that survives restarts
BackgroundJob.Enqueue<IInvoiceJob>(j => j.SubmitAsync(invoiceId, CancellationToken.None));
```

## Manual trace checklist
1. `di_lifetimes.py` MISMATCH rows: open each consumer; captive in a field? Multi-tenant context (connection string chosen per request) captured by a singleton = Critical.
2. Every `BackgroundService`/`IHostedService`/Hangfire job: scoped services resolved through a scope per iteration; `stoppingToken` in every await; exceptions logged.
3. Every `.Result`/`.Wait()` hit: request path or startup? Inside a `lock`? Called from a controller via a sync interface (`IFoo.Get()` implemented with `.Result`) - the interface is the root cause.
4. Every `HttpClient` construction: factory? timeout? disposal? DNS (`PooledConnectionLifetime` on `SocketsHttpHandler` for long-lived clients)?
5. Controllers: `CancellationToken` parameter present and passed to EF/HTTP calls on list/export endpoints.
6. `async void` and discarded tasks: what is lost if they throw? Money/stock/invoice paths are High.
7. `IServiceProvider`/`GetService` in services: which lifetimes does it resolve, from which scope (root provider from a singleton = captive again).

## Stack-specific false positives
- `.Result` on `Task.FromResult` / already-completed `ValueTask` / in `Main` of console tools and in xUnit tests.
- `async void` on genuine event handlers (`+= async (s, e) =>`) with try/catch inside.
- `new HttpClient(handler)` inside `AddHttpClient(...).ConfigurePrimaryHttpMessageHandler` or a `static readonly HttpClient` with `SocketsHttpHandler { PooledConnectionLifetime = ... }` - intentional long-lived client.
- `CancellationToken.None` in shutdown/cleanup code that must complete.
- `AddSingleton` consuming `IOptions<T>`, `ILogger<T>`, `IHttpClientFactory`, `IMemoryCache`, `IConfiguration`, `IHttpContextAccessor` - all singletons.
- `Task.Run` in a `BackgroundService` for CPU-bound work whose task is awaited.

## Tooling
- Analyzers: `Microsoft.VisualStudio.Threading.Analyzers` (VSTHRD002 avoid sync-over-async, VSTHRD100 avoid async void, VSTHRD110 observe result of async calls, VSTHRD103 call async methods when in async), `AsyncFixer` (AsyncFixer01-05), `Meziantou.Analyzer` (MA0004 ConfigureAwait, MA0032/MA0040 CancellationToken forwarding, MA0045 no blocking), CA2007, CA2008, CS4014 (treat as error).
- Container validation: `UseDefaultServiceProvider(o => { o.ValidateScopes = true; o.ValidateOnBuild = true; })` - run the app once in Development; captive scoped dependencies throw at startup.
- Runtime: `dotnet-counters monitor -p <pid> --counters System.Runtime[threadpool-queue-length,threadpool-thread-count,threadpool-completed-items-count]` - a growing queue with low CPU under load = BLOCK; `dotnet-stack report -p <pid>` shows threads parked in `Monitor.Wait`/`ManualResetEventSlim.Wait` (the `.Result` signature); `dotnet-dump analyze` + `clrstack -all`.
- `dotnet build -warnaserror:CS4014,CS1998`.

## References
CWE-833, CWE-400, CWE-390, CWE-1088, CWE-362; Microsoft docs "Dependency injection in ASP.NET Core - Scope validation", "Service lifetimes", "Background tasks with hosted services - consuming a scoped service", "Async guidance" (David Fowler, aspnetcore/AsyncGuidance.md), "Use IHttpClientFactory", Stephen Cleary "Async/Await - Best Practices" (async void, sync-over-async).
