# .NET / C# reference for audit-gdpr-data-protection

## Stack markers
`*.csproj`, `Program.cs`, `appsettings*.json`; EF Core `DbContext`,
`[ApiController]` controllers, Hangfire (`RecurringJob`), Serilog. Variants:
multi-tenant with per-tenant databases (erasure and retention must run per
tenant DB), Ocelot gateway in front (rights endpoints must be routed there too).

## Where the relevant code lives
- Consent: entity properties on `User`/`Customer`/`Company` (`MarketingOptIn`,
  `TermsAccepted`), registration DTOs in `HostModel/`, `Account.MicroAPI` auth controllers.
- Rights endpoints: `Controllers/**` - look for `[HttpDelete]`, `Export*`, `Anonymi[sz]e*`,
  `GetMyData`; gateway routes in `WebHost/ocelotconfig.json`.
- Retention: `BackgroundJobs/*`, `RecurringJob.AddOrUpdate(...)` in `Program.cs`/`Startup.cs`,
  `IHostedService`, SQL Agent scripts if committed.
- Minimisation: `ILogger` calls, Serilog `WriteTo` sinks in appsettings, `TelemetryClient`,
  `[FromQuery]` PII, AutoMapper profiles that map entities straight to responses.
- Encryption: connection strings (`Encrypt=`, `TrustServerCertificate=`), `UseHttpsRedirection`,
  `UseHsts`, EF `ValueConverter` for field encryption, `IDataProtector`, Key Vault references.
- Audit: temporal tables (`IsTemporal()` in `OnModelCreating`), `AuditLog` entities,
  `ChangeTracker` interceptors, `SaveChangesInterceptor`.
- Breach signals: failed-login logging in the auth manager, lockout (`Identity` `LockoutEnabled`),
  Serilog sinks to a central store, alerting webhooks.

## Dangerous / interesting APIs and patterns
- `public bool MarketingOptIn { get; set; }` with no `MarketingOptInAt`/`ConsentVersion`.
- `IsDeleted = true` soft delete with no purge job -> erasure never completes.
- `_logger.LogInformation("... {Email} ...", user.Email)`; `{@Request}` destructuring.
- `[HttpGet("{email}")]`, `[FromQuery] string email`.
- `Encrypt=False;TrustServerCertificate=True` in connection strings.
- No `app.UseHttpsRedirection()`/`UseHsts()` in `Program.cs` (may be at the gateway - check `WebHost`).
- `RecurringJob` list with no purge/anonymise job; Hangfire job arguments containing PII persisted in the job store.
- AutoMapper `CreateMap<User, UserDto>()` returning `NationalId`/`Salary` to every role.
- Erasure that deletes the row but leaves `wwwroot/uploads/<id>/*`, Redis keys, Google Drive files, Serilog SQL log rows, and vendor records (SMS provider, Shopify).

## What "good" looks like
```csharp
public class Consent { public Guid UserId; public string Purpose; public string PolicyVersion;
                       public DateTime GivenAtUtc; public DateTime? WithdrawnAtUtc; public string Source; }
[HttpDelete("me")] public async Task<IActionResult> EraseMe(CancellationToken ct)
    => await _erasure.AnonymiseAsync(User.GetUserId(), ct) is var r ? Accepted(r) : Problem();
RecurringJob.AddOrUpdate<RetentionJob>("purge-inactive", j => j.RunAsync(), Cron.Daily);
_logger.LogInformation("Customer {CustomerId} registered", customer.Id);
"Default": "Server=...;Encrypt=True;TrustServerCertificate=False;"
modelBuilder.Entity<Customer>().ToTable(t => t.IsTemporal());   // history for audit
```

## Manual trace checklist
1. Erasure: from the DELETE/anonymise entry point, list every table (`Include`
   graph), file store, cache key scheme, Hangfire job store, log sink and vendor
   the customer appears in (from the inventory); tick each one the code reaches.
2. Consent: which columns exist, where they are written (registration DTO ->
   entity), what reads them before a marketing send / analytics call.
3. Retention: enumerate `RecurringJob.AddOrUpdate` and hosted services; map each
   to a data category; note logs (Serilog `retainedFileCountLimit`, SQL sink purge).
4. Gateway: are the rights endpoints reachable through `ocelotconfig.json`?
5. Multi-tenant: does erasure iterate tenant databases (`CustomConnectionString.DbName`)?
6. Transport: `UseHttpsRedirection`/`UseHsts` in every host or at the gateway; DB `Encrypt=True`.

## Stack-specific false positives
- `[HttpDelete]` on `Product`, `Batch`, `Voucher` controllers is not erasure.
- `IsDeleted` soft delete plus a documented purge job is fine - cite the job.
- `Encrypt=False` in `appsettings.Development.json` only: Low, but confirm production config source.
- `LogInformation("... {UserId}", id)` - id only, good pattern.

## Tooling
- `python scripts/gdpr_check.py <repo> --out ... --md ...`
- `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/dotnet.json`
- `grep -rn "HttpDelete\|Anonymi\|RecurringJob" --include=*.cs`
- `grep -rn "Encrypt=\|TrustServerCertificate" --include=*.json`

## References
GDPR Art.5, 7, 12-22, 25, 28, 30, 32-35; CWE-532, CWE-359, CWE-312 (cleartext storage),
CWE-319 (cleartext transmission); ASVS 8.3, 7.1, 9.1; EF Core temporal tables docs;
ASP.NET Core Data Protection docs; Serilog destructuring policies.
