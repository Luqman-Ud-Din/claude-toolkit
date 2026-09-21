# .NET / C# reference for audit-concurrency-and-race-condition

## Stack markers
`*.csproj`, `*.sln`, `Program.cs`. Variants: EF Core (SQL Server / Npgsql), Dapper; Hangfire / Quartz.NET / `IHostedService` timers; Ocelot/YARP gateway; multiple MicroAPIs each with their own DbContext.

## Where the relevant code lives
- Handlers: `Controllers/*Controller.cs` (`[HttpPost]`, `[HttpPut]`, `[HttpDelete]`), minimal API `MapPost`, webhook controllers.
- Data: `*Manager.cs`/`*Repository.cs` (`Any()`, `FirstOrDefault()` followed by `Add()`/`Update()`), `SaveChanges`, `Database.BeginTransaction`, `ExecuteUpdate`/`ExecuteSql`.
- Schema: `OnModelCreating` (`HasIndex(...).IsUnique()`, `IsRowVersion()`, `IsConcurrencyToken()`), migrations, `.sql` scripts.
- Shared state: `static` fields in any class, `AddSingleton` registrations in `Program.cs`/`ConfigureServices`, `IMemoryCache` usage, `OptionsModel`-style static holders.
- Jobs: `BackgroundJobs/`, `RecurringJob.AddOrUpdate`, `BackgroundService.ExecuteAsync` loops.

## Dangerous / interesting APIs and patterns
- Check-then-act: `if (!_db.Users.Any(u => u.Email == email)) _db.Users.Add(...)`; `var stock = ...FirstOrDefault(); if (stock.Qty >= q) { stock.Qty -= q; }`; `if (order.Status == Pending) order.Status = Paid;` then `SaveChanges()` with no rowversion and no `WHERE Status = Pending`.
- No unique index behind an "exists" check: `HasIndex(x => x.Email)` without `.IsUnique()`, or no index at all; `[Index(IsUnique = true)]` absent.
- Idempotency: payment/refund/webhook actions with no `Idempotency-Key` header read, no `WebhookEvents` table, no `Stripe` `RequestOptions.IdempotencyKey`; retry via Polly (`AddTransientHttpErrorPolicy`) on POSTs that move money.
- Optimistic concurrency: entity has `byte[] RowVersion` but no `IsRowVersion()`; `DbUpdateConcurrencyException` not caught anywhere (`grep`); `ExecuteUpdate` used without a conditional `Where`.
- Transactions: multi-entity writes with separate `SaveChanges()` calls and no `BeginTransaction`/`TransactionScope`; `IsolationLevel` never set (SQL Server default ReadCommitted allows the check-then-act interleave); `TransactionScope` without `TransactionScopeAsyncFlowOption.Enabled` in async code.
- Shared state: `static Dictionary<,>`, `static List<>`, `static int` counters, `static string CurrentTenant/DbName` set per request (cross-tenant race), singleton services holding `HttpContext` or per-request values, `Lazy<T>` without thread safety mode, `static HttpClient` is fine but `static` mutable caches are not.
- Collections: `Dictionary`, `List`, `HashSet`, `Queue` shared across requests; `lock(this)`/`lock(typeof(T))`; `Parallel.ForEach` mutating a `List`.
- Jobs: Hangfire recurring jobs without `[DisableConcurrentExecution(timeoutInSeconds)]` and with more than one server; `BackgroundService` loops with `Timer` where the callback can overlap; Quartz jobs without `[DisallowConcurrentExecution]` or with `RAMJobStore` in a cluster.
- `async void`, `.Result`/`.Wait()` (deadlocks under load, owned by the async skill but note them).

## What "good" looks like
```csharp
// uniqueness: constraint + handled violation
modelBuilder.Entity<User>().HasIndex(u => new { u.CompanyId, u.Email }).IsUnique();
try { _db.Users.Add(user); await _db.SaveChangesAsync(ct); }
catch (DbUpdateException e) when (e.IsUniqueViolation()) { return Conflict("email already registered"); }
// atomic conditional update (no read-modify-write)
var rows = await _db.Stock.Where(s => s.Id == id && s.Qty >= q)
                          .ExecuteUpdateAsync(s => s.SetProperty(x => x.Qty, x => x.Qty - q), ct);
if (rows == 0) throw new InsufficientStockException();
// optimistic concurrency
modelBuilder.Entity<Order>().Property(o => o.RowVersion).IsRowVersion();
try { await _db.SaveChangesAsync(ct); } catch (DbUpdateConcurrencyException) { /* reload, re-check, retry or 409 */ }
// idempotency key stored before the side effect
if (!await _keys.TryInsertAsync(key, ct)) return Ok(await _keys.GetResponseAsync(key, ct));
// job lock
[DisableConcurrentExecution(timeoutInSeconds: 300)] public async Task ExpireTrials() { ... }
// shared state
static readonly ConcurrentDictionary<string,int> _hits = new();  _hits.AddOrUpdate(k, 1, (_, v) => v + 1);
```
Tenant/DB selection: resolve from claims into a scoped service (`AddScoped<ITenantContext>`), never a static.

## Manual trace checklist
1. Every `[HttpPost]`/`[HttpPut]`/`[HttpDelete]` that touches money, stock, or uniqueness: find the read and the write; is there a transaction, a conditional update, or a version check between them.
2. `grep -rn "\.Any(\|\.Exists(\|FirstOrDefault(" --include=*.cs` followed within 15 lines by `.Add(`/`Update(`: list them and check migrations for a unique index.
3. `grep -rn "static " --include=*.cs | grep -v "readonly\|const\|static class\|static void\|static async\|static \w* \w*("`: every static mutable field and who writes it.
4. Payment/refund/webhook handlers: idempotency key or event-id table present; gateway called with a key.
5. `grep -rn "RowVersion\|IsRowVersion\|IsConcurrencyToken\|DbUpdateConcurrencyException"`: token defined and exception handled.
6. `RecurringJob.AddOrUpdate` / `BackgroundService`: concurrency attribute, server count, per-item idempotency in the body.
7. `BeginTransaction`/`TransactionScope`: which multi-step writes lack one; isolation level.

## Stack-specific false positives
- `static readonly` immutable data (arrays never mutated, `ImmutableDictionary`, `FrozenDictionary`); `static` loggers/`HttpClient`/`JsonSerializerOptions`.
- `ConcurrentDictionary` used correctly (`GetOrAdd`/`AddOrUpdate`, not `if (!ContainsKey) Add`).
- `Any()` check that is a UX pre-check *and* a unique index exists with the violation handled.
- Single `SaveChanges()` covering all entities in one unit of work (EF wraps it in a transaction).
- Hangfire jobs with `[DisableConcurrentExecution]` and a single job server.

## Tooling
Roslyn analyzers: `Microsoft.VisualStudio.Threading.Analyzers` (VSTHRD), `Meziantou.Analyzer` MA0116 (ConcurrentDictionary), `CA2002`; `grep -rn "IsUnique()" --include=*.cs` vs the exists-checks list; `dotnet ef migrations script` where migrations exist; `k6`/`bombardier` two-request burst against a test environment; `scripts/double_submit.sh`.

## References
CWE-362, CWE-367, CWE-662, CWE-820; EF Core "Handling Concurrency Conflicts"; Hangfire `DisableConcurrentExecution`; Stripe idempotent requests; ASVS 11.1.4.
