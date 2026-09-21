# .NET / ASP.NET Core reference for audit-system-design

## Stack markers
`*.sln`, `*.csproj`, `Program.cs`. Variants: single web project (monolith); several `*.MicroAPI`/`*.Host` projects behind Ocelot/YARP (services sharing a solution); worker services (`Microsoft.NET.Sdk.Worker`, Hangfire, Quartz); MassTransit/NServiceBus/RabbitMQ.Client/Azure.Messaging.ServiceBus for messaging; `Microsoft.Extensions.Http.Resilience`/Polly for resilience.

## Where the architecture is visible
- `*.sln` + `ProjectReference` in every `.csproj` - the build-unit graph (`module_graph.py`). Naming tells the intended layer: `*.MicroAPI`/`WebHost` (presentation), `*.Managers`/`*.Services`/`*.Application` (application), `*.Entity`/`*.Domain` (domain), `*.Dto`, `*.IServices` (contracts), `*.Configuration` (DI wiring), `Shared*`.
- `Program.cs`/`Startup.cs`: DI registrations (`AddScoped/AddSingleton`), `AddDbContext` (how many contexts, which connection), `AddHttpClient` (outbound edges), `AddHangfireServer` (job host), `AddSignalR` (+ `AddStackExchangeRedis` backplane?), `AddAuthentication().AddJwtBearer` (where authn is), `UseOcelot()`/`MapReverseProxy()`.
- `ocelotconfig.json` / `yarp` section: route -> downstream host:port table = the service map and the edge boundary; `AuthenticationOptions` per route = where auth is enforced.
- `appsettings*.json`: `ConnectionStrings` (data stores, one per service or shared?), `RabbitMQ`/`ServiceBus`/`Redis` sections (queues, caches), external base URLs (FBR, Shopify, SMS, Google Drive).
- `docker-compose*.yml`, `k8s/`, `Dockerfile` per project - runtime units and replicas.
- `BackgroundJobs/`, `IHostedService` implementations, `[AutomaticRetry]` attributes - async work and its retry policy.

## Design smells to grep (mirrored in `scripts/patterns/dotnet.json`)
- `public static` mutable fields/properties used as per-request state (`CustomConnectionString.DbName = ...`) - process-wide state that races across concurrent requests and breaks with async flows; a tenancy decision made in a static.
- `new HttpClient()` in a method, `HttpClient` without `Timeout`, typed clients without `AddStandardResilienceHandler`/Polly.
- `IMemoryCache`, `static Dictionary`, `ConcurrentDictionary` as shared state; `AddDistributedMemoryCache()` in production; `AddSession()` without a distributed store.
- `AddSignalR()` without a Redis/Azure backplane; `IHubContext` used from jobs.
- `DbContext` injected into a controller; controllers with `using Microsoft.EntityFrameworkCore` and LINQ queries inline (layer skip).
- Two projects each with `DbSet<Invoice>` or `[Table("Invoices")]` - shared table; `TransactionScope` spanning HTTP calls; `Publish(...)`/`BasicPublish(` inside a request handler right after `SaveChanges` without an outbox table.
- `.Result`, `.Wait()`, `GetAwaiter().GetResult()` (sync over async - thread-pool starvation under load), `Task.Run` in controllers, `Thread.Sleep` as retry delay.
- `catch (Exception) { }` around external calls (silent degradation without a breaker), retries in `for` loops without backoff.
- Hangfire `RecurringJob.AddOrUpdate` in every instance without a leader/`DisableConcurrentExecution` - duplicate runs when scaled.
- Local disk writes (`File.WriteAllBytes("wwwroot/uploads")`) - breaks with two instances.
- `[AllowAnonymous]` on internal endpoints meant to be called service-to-service; services listening on published ports that bypass the gateway; `TrustServerCertificate=True` in connection strings (delegate detail to secrets/infra skills, keep the boundary note).
- God classes: `CommonFunction`, `Helper`, `Utils` with thousands of lines and fan-in from every project.

## What "good" looks like
```csharp
// Program.cs - outbound edge with timeout, retry, breaker
builder.Services.AddHttpClient<IFbrClient, FbrClient>(c => { c.BaseAddress = new Uri(cfg["Fbr:BaseUrl"]); c.Timeout = TimeSpan.FromSeconds(10); })
                .AddStandardResilienceHandler();
// tenancy per request, not static
builder.Services.AddScoped<ITenantContext, ClaimsTenantContext>();
builder.Services.AddDbContext<TenantDbContext>((sp, o) => o.UseSqlServer(sp.GetRequiredService<ITenantContext>().ConnectionString));
// events via outbox (MassTransit EF outbox or a hand-rolled Outbox table + dispatcher)
x.AddEntityFrameworkOutbox<TenantDbContext>(o => { o.UseSqlServer(); o.UseBusOutbox(); });
// shared state in a backplane
builder.Services.AddSignalR().AddStackExchangeRedis(cfg["Redis"]);
builder.Services.AddStackExchangeRedisCache(o => o.Configuration = cfg["Redis"]);
```
Layering: `Domain` has no `PackageReference` to EF/ASP.NET; `Application` depends on `Domain` and defines interfaces; `Infrastructure` implements them; `Api` depends on both and wires DI.

## Manual trace checklist
1. Gateway route table -> each downstream service -> its DbContext(s) -> connection string names: draw it. Note which services share a connection string or DB name.
2. Static/tenant holders: find where the per-request DB is chosen and confirm it cannot leak between requests (scoped service vs static).
3. Every `AddHttpClient`/`new HttpClient`: timeout? retry? breaker? what does the caller do when it fails?
4. Every publish/consume: broker instance count, publisher confirms, consumer idempotency (`MessageId` de-dup), DLQ.
5. Hangfire/hosted services: single job host? what if it dies mid-job? are jobs idempotent?
6. SignalR/websocket, `IMemoryCache`, `Session`, local files: what breaks at 2 replicas.
7. Compare with README/ADR claims.

## Stack-specific false positives
- `static readonly` immutable configuration and `static` pure helper methods are fine.
- `IMemoryCache` for reference data with TTL, where staleness across instances is acceptable, is fine - note it.
- `new HttpClient()` inside a typed-client factory or a one-off CLI tool.
- `.Result` in `Main` of a console app or in tests.
- A shared `SharedLibrary` with only DTOs/helpers having high fan-in is expected, not a god module - check it has no business rules and no DB access.

## Tooling
- `dotnet list <proj> reference` / `dotnet sln list` for the graph; `dotnet list package --include-transitive` for infra leakage into Domain.
- `ArchUnitNET` (`dotnet add package TngTech.ArchUnitNET.xUnit`) to encode layer rules as tests; NDepend or `dotnet-depends` for visual graphs.
- `dotnet-counters monitor --process-id <pid> System.Runtime` for thread-pool starvation evidence when sync-over-async is suspected.
- `docker compose config` to render the effective topology.

## References
- Microsoft docs: "Common web application architectures", ".NET microservices: Architecture for containerized .NET applications" (resilience, outbox with MassTransit), "Building resilient HTTP apps".
- ASVS 1.x (architecture), 1.4 (access control architecture), 1.9 (communications architecture), 1.14 (configuration architecture); CWE-770 (unbounded resources), CWE-362 (race via shared state), CWE-306 (missing authn on internal endpoints).
