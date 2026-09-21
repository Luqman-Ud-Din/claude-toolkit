# .NET / C# reference for audit-privacy-data-flow-mapper

## Stack markers
`*.csproj`, `*.sln`, `Program.cs`, `appsettings*.json`. Variants: EF Core
entities (`DbContext`, `DbSet<T>`) vs Dapper (SQL strings), Serilog vs
`ILogger` default providers, `IDistributedCache` (Redis) vs `IMemoryCache`,
Hangfire background jobs, Razor email templates vs plain string templates.

## Where the relevant code lives
- Storage: `*.Entity/` projects, `Entities/`, `Models/`, `*DbContext.cs`
  (`OnModelCreating` column names), `Migrations/*.cs` (`table.Column<string>(name: "Email")`)
  if present, `*.sql` scripts, `wwwroot/uploads`, file/Drive/S3 upload services.
- Collection: `Controllers/**` (`[FromBody]` DTOs in `HostModel/`, `*.Dto`),
  minimal API `MapPost`, SignalR hubs, Hangfire job arguments (serialised to the job store).
- Processors: `ILogger<T>` calls, Serilog sinks in `appsettings` (`WriteTo`),
  `IDistributedCache`/`IMemoryCache`/`StackExchange.Redis` keys, AutoMapper
  profiles (`Extensions/MapperFactory`) show which fields flow into responses,
  `TelemetryClient` / `Sentry`, EPPlus exports, report generators.
- Transmission: `HttpClient`/`IHttpClientFactory` typed clients, `RestSharp`,
  `SmtpClient`/`MailKit`/SendGrid, SMS providers (`SMSLibrary`), Shopify/FBR/ZATCA
  integrations, Google Drive uploads, SignalR/WebSocket broadcasts.
- Templates: `Templates/`, `EmailTemplates/`, `*.cshtml` rendered by
  RazorLight/`IRazorViewEngine`, string templates in resources.

## Dangerous / interesting APIs and patterns
- `_logger.LogInformation("... {Email} ...", user.Email)` - structured placeholder still ships the value.
- `LogInformation(JsonConvert.SerializeObject(request))` / `{@Request}` destructuring - whole DTO logged.
- Serilog `Enrich.FromLogContext()` + `LogContext.PushProperty("User", email)`.
- Global exception middleware logging `context.Request.Body` or query string.
- `_cache.SetStringAsync($"customer:{email}", ...)`, `IMemoryCache.Set(email, ...)`.
- `[HttpGet("{email}")]`, `[FromQuery] string email` - PII in URL.
- `TelemetryClient.TrackEvent("Login", new Dictionary<string,string>{{"email", ...}})`.
- `PostAsJsonAsync("https://...", payload)` with anonymous payload built from an entity.
- Hangfire `BackgroundJob.Enqueue(() => Send(customer.Email))` - argument persisted in the job store (a storage location).
- AutoMapper `CreateMap<Customer, CustomerDto>()` with no `.Ignore()` - everything flows to the API response.
- `OnModelCreating` without `HasQueryFilter`/`IsEncrypted` on PII columns; SQL Server Always Encrypted or `ValueConverter` for at-rest encryption.

## What "good" looks like
```csharp
_logger.LogInformation("Customer {CustomerId} registered", customer.Id);          // id, not value
var key = $"customer:{Sha256Hex(customer.Email)}";                                 // hashed cache key
services.AddHttpClient<MailchimpClient>(c => c.BaseAddress = new Uri(cfg["Mailchimp:BaseUrl"]));
// one typed client per vendor makes the processor list greppable
builder.Host.UseSerilog((ctx, lc) => lc.Destructure.ByTransforming<Customer>(c => new { c.Id }));
```

## Manual trace checklist
1. Every `ILogger` call with a PII placeholder: which sinks are configured
   (`Serilog:WriteTo` - MSSqlServer, File, Seq, Application Insights)? Name the
   sink and its retention (if set) in the finding.
2. Cache keys: open the Redis key scheme; anything containing email/phone/CNIC is
   visible in `KEYS *` and monitoring.
3. Each typed HttpClient / RestSharp client: base URL -> vendor; find the payload
   class; list fields sent.
4. Email/SMS: which provider (SMTP host, SendGrid key, SMS provider in
   `SMSLibrary`), which template, which fields are merged.
5. Exports and reports (EPPlus, PDF): generated files containing customer data
   are storage locations - where are they written (`wwwroot`, temp, Drive)?
6. Hangfire job arguments and the SQL job store: serialised PII persists there.
7. Multi-tenant apps: the inventory is per tenant DB; note `CompanyId`/`BranchId`
   scoping does not change *what* is stored, only *where*.

## Stack-specific false positives
- `{Email}` placeholder in a log template where the argument is actually an id
  or a masked value - read the argument list.
- `Email` on `Company`/`Branch` entities - business contact; note the ambiguity.
- `ILogger` calls inside `catch` that log `ex.Message` only - fine unless the
  exception message embeds the input (EF validation messages can).
- Test projects and seed data with `example.com` addresses - excluded by the scanner.

## Tooling
- Scanner: `python scripts/pii_scan.py <repo> --out ... --md ... --mermaid ...`
- Patterns: `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/dotnet.json`
- Column list from a live DB (if allowed): `SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME LIKE '%email%' OR COLUMN_NAME LIKE '%phone%'`
- `dotnet ef dbcontext script` (if EF tools present) to get the schema without a DB
- Roslyn analyzer `Microsoft.CodeAnalysis.BannedApiAnalyzers` to ban `Console.WriteLine` in services

## References
GDPR Art.5(1)(c) minimisation, Art.5(1)(e) storage limitation, Art.28 processors,
Art.30 records of processing, Art.32 security; CWE-532 (log exposure), CWE-359
(privacy violation), CWE-598 (query string), ASVS 8.3 (sensitive private data),
ASVS 7.1.1 (no sensitive data in logs). Serilog destructuring docs; Microsoft
"Safe storage of app secrets" is `audit-secrets-and-config`'s topic, not this one.
