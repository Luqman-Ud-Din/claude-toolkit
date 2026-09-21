# .NET / C# reference for audit-backend-resource-leak

## Stack markers
`*.csproj`, `*.sln`, `Program.cs`, `appsettings*.json`. Sub-variants: ASP.NET Core controllers vs minimal APIs; Hangfire vs `BackgroundService`/`IHostedService`; EF Core vs Dapper; Ocelot/YARP gateway processes (long-lived, high fan-out, worth a separate trace).

## Where the relevant code lives
`Program.cs`/`Startup.cs` (every `AddSingleton`, `AddMemoryCache`, `AddHostedService`), `BackgroundJobs/`, `*Worker.cs`, `*Manager.cs`/`*Service.cs`, `*DbContext.cs`, anything with `static` fields, `Extensions/` helpers that build `HttpClient`, `Stream`, `SqlConnection`.

## Dangerous / interesting APIs and patterns
- Disposal: `new FileStream`, `new StreamReader/Writer`, `new MemoryStream` held in fields, `new SqlConnection/NpgsqlConnection/MySqlConnection`, `new SqlCommand`, `ExecuteReaderAsync` result, `new HttpClient()`, `HttpResponseMessage` from `SendAsync` not disposed, `new XyzDbContext(` outside DI, `Image.Load` (ImageSharp) without `using`, `new CancellationTokenSource` without `using`/`Dispose`, `Timer`/`PeriodicTimer` created per request, `IServiceScope` from `CreateScope()` not disposed.
- Growth: `static List<>/Dictionary<>/ConcurrentDictionary<>` with `.Add`/`TryAdd`/indexer set and no `Remove`/`Clear`/`TryRemove`; `ConcurrentQueue` never dequeued; singleton services with instance collections.
- Cache: `services.AddMemoryCache()` with no `SizeLimit`; `MemoryCacheEntryOptions` lacking `SetSize` when a limit exists, or lacking `AbsoluteExpiration`/`SlidingExpiration`; hand-rolled `static Dictionary` caches; `IDistributedCache` entries with no `AbsoluteExpirationRelativeToNow`.
- Subscriptions: `+=` to an event on a singleton/static publisher (`AppDomain.CurrentDomain.UnhandledException`, `ChangeToken.OnChange`, `IOptionsMonitor.OnChange` return token discarded, `PropertyChanged`) with no matching `-=`.
- Hot-path allocation: `new byte[large]` per request, `string.Concat` in loops, `MemoryStream.ToArray()` on large payloads, `JsonSerializer.Serialize` of full entity graphs, `Regex` constructed per call (no `static readonly`/`RegexOptions.Compiled`/`GeneratedRegex`), EPPlus `ExcelPackage` without `using`.
- Background workers: `BackgroundService.ExecuteAsync` with `while (!stoppingToken.IsCancellationRequested)` and `catch { }` / `catch (Exception) { }` with no log; a scope created once outside the loop (captive `DbContext` grows its change tracker forever); `Task.Run` fire-and-forget; Hangfire jobs that resolve a `DbContext` and never dispose (they do if resolved from scope; check `JobActivator`).

## What "good" looks like
```csharp
services.AddMemoryCache(o => o.SizeLimit = 10_000);
_cache.Set(key, value, new MemoryCacheEntryOptions { Size = 1, SlidingExpiration = TimeSpan.FromMinutes(10) });

protected override async Task ExecuteAsync(CancellationToken ct)
{
    using var timer = new PeriodicTimer(TimeSpan.FromSeconds(30));
    while (await timer.WaitForNextTickAsync(ct))
    {
        try
        {
            using var scope = _scopes.CreateScope();            // fresh scope per iteration
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
            await ProcessAsync(db, ct);
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
        catch (Exception ex) { _logger.LogError(ex, "Sync iteration failed"); }
    }
}

await using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 4096, useAsync: true);
using var response = await _httpClientFactory.CreateClient("fbr").SendAsync(req, ct);
```
`ArrayPool<byte>.Shared.Rent/Return` for large temporary buffers; `RecyclableMemoryStreamManager` for many `MemoryStream`s.

## Manual trace checklist
1. Every `AddSingleton<...>` and every `static` field: list collection-typed members, find all writers, prove a remover exists or the key space is bounded (for example keyed by tenant id, max a few hundred).
2. Every `BackgroundService`/`IHostedService`/Hangfire recurring job: scope-per-iteration? exceptions logged? state reset between iterations? `stoppingToken` honoured?
3. Every `DbContext` obtained outside DI (`new XDbContext(options)`, `CustomConnectionString` swaps): disposed? Multi-tenant apps that pick the DB per request often build contexts by hand.
4. `HttpResponseMessage` / `Stream` returned from a service to a controller: who disposes it? `File(stream, ...)` disposes; returning `stream.ToArray()` after `using` is fine; storing the stream in a field is not.
5. `CancellationTokenSource.CreateLinkedTokenSource` in middleware/filters: disposed in `finally`?
6. `IOptionsMonitor.OnChange` and `ChangeToken.OnChange` in singletons: the returned `IDisposable` kept and disposed?
7. Image/Excel processing paths (`SixLabors.ImageSharp`, `EPPlus`): `using` on `Image`, `ExcelPackage`; `Image.Load` on user uploads bounded by `DecoderOptions.MaxFrames`/size checks.

## Stack-specific false positives
- `new HttpClient()` inside `AddHttpClient<T>(...)` configuration or a typed-client factory - the factory owns it.
- `MemoryStream` over a small in-memory buffer that is returned and disposed by `FileStreamResult`.
- `static readonly` immutable collections (initialised once, never written).
- `catch (OperationCanceledException)` that rethrows or exits the loop - intended.
- `ConcurrentDictionary` used as a bounded registry (keys are enum values, tenant ids, or route names) - note the bound in the finding and mark `false-positive`.
- `IMemoryCache` without `SizeLimit` when every entry has an absolute expiration and the key space is enumerable (config keys). Still record as Info if entries are keyed by user input.

## Tooling
- `dotnet-counters monitor --process-id <pid> --counters System.Runtime[working-set,gen-2-gc-count,gc-heap-size,threadpool-thread-count,alloc-rate]` (refresh 15 s: `--refresh-interval 15`).
- `dotnet-counters collect ... --format csv --output samples.csv` then `python scripts/leak_loadtest.py grade samples.csv --format dotnet-counters`.
- `dotnet-gcdump collect -p <pid>` before/after steady state; diff object counts in Visual Studio or `dotnet-gcdump report`.
- `dotnet-dump collect -p <pid>` + `dumpheap -stat` for retained types; `gcroot <addr>` to find the static root.
- Handles on Windows: `handle.exe -p <pid> | find /c "File"`; Linux: `ls /proc/<pid>/fd | wc -l`.
- Analyzers: `Microsoft.CodeAnalysis.NetAnalyzers` CA2000 (dispose objects before losing scope), CA1001 (types owning disposables should be disposable), CA1063; enable `<AnalysisLevel>latest-all</AnalysisLevel>` in a scratch build to list CA2000 hits.

## References
CWE-401, CWE-404, CWE-772, CWE-770, CWE-400, CWE-390; ASVS-12.1.x (resource limits); Microsoft docs "Memory management and garbage collection in ASP.NET Core", "Use HttpClientFactory", "Background tasks with hosted services", "Cache in-memory in ASP.NET Core" (SizeLimit section).
