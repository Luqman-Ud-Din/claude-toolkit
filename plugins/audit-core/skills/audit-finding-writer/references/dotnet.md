# .NET / C# reference for audit-finding-writer

## Stack markers
`*.csproj`, `*.sln`, `Program.cs`, `appsettings*.json`. Variants: ASP.NET Core controllers vs minimal APIs; EF Core vs Dapper; Ocelot/YARP gateways in front.

## Where the relevant code lives
`Controllers/`, `Program.cs` / `Startup.cs` (pipeline), `appsettings.*.json`, `*Manager.cs` / `*Service.cs` (business logic), `*DbContext.cs`, `BackgroundJobs/`, `Hangfire` registrations.

## Remediation idioms (write fixes in these terms)
- Config/secrets: `builder.Configuration["Section:Key"]`, `IOptions<T>`, user-secrets in dev, Key Vault / env vars in prod. Never `new ConfigurationBuilder()` with literals.
- AuthZ: `[Authorize(Roles = ...)]`, `[Authorize(Policy = ...)]`, `IAuthorizationService.AuthorizeAsync(user, resource, requirement)` for ownership; `[AllowAnonymous]` must be deliberate.
- Input binding: `[FromBody]` DTOs with `[Required]`/`[Range]`; separate request DTOs from entities to stop mass assignment (`[BindNever]` as a last resort).
- Data access: `FromSqlInterpolated` / parameters instead of `FromSqlRaw($"...")`; `AsNoTracking()` for reads; `Include()` for eager loading; `Skip/Take` paging.
- Async: `await` all the way; `CancellationToken` parameter on every async action; `IHttpClientFactory` not `new HttpClient()`.
- Disposal: `await using` / `using`; `IAsyncDisposable`.
- Headers: `app.UseHsts()`, `app.UseHttpsRedirection()`, header middleware or `NWebsec`; `CookieOptions { HttpOnly = true, Secure = true, SameSite = SameSiteMode.Strict }`.
- Multi-tenancy: `HasQueryFilter(e => e.TenantId == _tenant.Id)` on the DbContext; tenant id from `HttpContext.User` claims, never from the DTO.
- Logging: `ILogger<T>` structured templates (`{OrderId}`), `LogLevel.Error` for exceptions, no `LogInformation(JsonSerializer.Serialize(request))`.
- Dates: `DateTimeOffset`/`DateTime.UtcNow`, `TimeProvider` for testability; SQL `datetimeoffset`.

## Recurring references for this stack
CWE-798 (hard-coded credentials), CWE-89 (SQL), CWE-639 (IDOR), CWE-915 (mass assignment), CWE-352 (CSRF), CWE-400 (resource exhaustion), CWE-772 (missing release), ASVS 2.10 (service auth), 4.1/4.2 (access control), 5.3 (output encoding/injection), 14.4 (HTTP headers). OWASP A01 (access control), A02 (crypto/secrets), A03 (injection), A05 (misconfig).

## Stack-specific false positives
`FromSqlRaw` with `{0}` placeholders and parameter arguments is parameterized; `[AllowAnonymous]` on health/login/register endpoints is expected; `HttpClient` created inside a typed-client factory registration is fine.

## Tooling
`dotnet list package --vulnerable --include-transitive`, `dotnet format --verify-no-changes`, Roslyn analyzers (`Microsoft.CodeAnalysis.NetAnalyzers`, `SecurityCodeScan`), `dotnet-counters` for leak confirmation.
