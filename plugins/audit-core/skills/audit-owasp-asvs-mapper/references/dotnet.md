# .NET / C# reference for audit-owasp-asvs-mapper

This file answers one question for ASP.NET Core projects: which ASVS 4.0 controls
does the framework satisfy by default, which need a visible line of code or config
to count as "Verified", and where that evidence lives. Use it when deciding whether
a section with no findings is really Verified or only Not assessed.

## Stack markers
`*.csproj` (`Microsoft.NET.Sdk.Web`), `Program.cs` / `Startup.cs`, `appsettings*.json`,
`ocelotconfig.json` (gateway). Variants: MVC controllers vs minimal APIs; Identity vs
custom JWT; Ocelot/YARP in front (headers may be set there, not in the service).

## Where the relevant code lives
- Pipeline order and headers: `Program.cs` (`app.UseHsts`, `UseHttpsRedirection`,
  `UseAuthentication`, `UseAuthorization`, `UseCors`, custom header middleware).
- AuthN/AuthZ: `AddAuthentication().AddJwtBearer(...)` options, `[Authorize]` /
  `[AllowAnonymous]` attributes, `AddAuthorization(o => o.AddPolicy(...))`.
- Data access: `*DbContext.cs`, `FromSqlRaw` / `FromSqlInterpolated`, Dapper calls.
- Secrets: `appsettings.*.json`, `secrets.json` (user-secrets id in csproj), Key Vault wiring.
- Logging: Serilog config in `appsettings.json` (`Serilog:MinimumLevel`, sinks), `ILogger<T>` calls.

## Controls the framework satisfies by default (mark Verified only after confirming nothing disabled them)
| ASVS | Default in ASP.NET Core | What disables it / what to look for |
|---|---|---|
| 5.3.3 output encoding (Razor) | Razor HTML-encodes `@model.X` | `@Html.Raw`, `HtmlString`, `IHtmlContent` built from user input |
| 5.3.4 parameterized queries | EF Core LINQ is always parameterized | `FromSqlRaw($"...")` interpolation, `ExecuteSqlRaw` with concatenation, Dapper with string-built SQL |
| 4.2.2 anti-CSRF (Razor Pages/MVC forms) | Antiforgery auto-validated on Razor Pages; `[AutoValidateAntiforgeryToken]` for MVC | Pure JWT APIs: not applicable if no cookie auth - record as N/A, not Verified |
| 5.1.2 mass assignment | Model binding binds only DTO members | Binding EF entities directly, `[Bind]` missing on entity types, `TryUpdateModel(entity)` |
| 14.3.2 debug disabled | `UseDeveloperExceptionPage` only when `IsDevelopment()` | `ASPNETCORE_ENVIRONMENT=Development` in a prod compose file; `DeveloperExceptionPage` unconditional |
| 14.4.4 / 14.4.6 / 14.4.7 headers | NOT set by default | Look for `app.Use(async (ctx, next) => { ctx.Response.Headers[...]` or NWebsec; may live in the gateway or reverse proxy |
| 14.4.5 HSTS | `UseHsts()` template default in non-dev branch, 30 days | Removed line, or `HstsOptions.MaxAge` < 1 year without justification |
| 3.4.1-3.4.3 cookie flags | `CookiePolicyOptions` defaults: `Secure=SameAsRequest`, `HttpOnly=false` for app cookies; Identity cookie is HttpOnly | `CookieOptions` built by hand in login code |
| 2.4.1 password storage | ASP.NET Core Identity uses PBKDF2 (V3) | Custom `UserManager`, `SHA256.ComputeHash(password)`, `MD5` |
| 6.3.1 CSPRNG | `RandomNumberGenerator` | `new Random()` for tokens or reset codes |
| 7.4.1 generic errors | `UseExceptionHandler("/error")` in template | Returning `ex.ToString()` from a filter or middleware |

## Controls that always need explicit evidence (never Verified by default)
- 4.1.1 / 4.2.1: every controller has `[Authorize]` and ownership filters (`CompanyId`,
  `BranchId`, `UserId`) in the query, not in the DTO.
- 2.10.4 / 6.4.1: secrets come from env / Key Vault (`builder.Configuration.AddAzureKeyVault`,
  `AddUserSecrets` only in dev). `appsettings.Production.json` with keys = Failed.
- 14.5.3 CORS: `AllowAnyOrigin()` combined with `AllowCredentials()` fails; an allow list passes.
- 7.1.1 / 7.1.2: `LogInformation("{@Request}", dto)` destructuring a DTO with passwords fails.
- 3.5.3 JWT: `TokenValidationParameters` has `ValidateIssuer`, `ValidateAudience`,
  `ValidateLifetime`, `ValidateIssuerSigningKey` all true and `ClockSkew` reasonable.

## What "good" looks like
```csharp
if (!app.Environment.IsDevelopment()) { app.UseExceptionHandler("/error"); app.UseHsts(); }
app.UseHttpsRedirection();
app.Use(async (ctx, next) => {
    ctx.Response.Headers["X-Content-Type-Options"] = "nosniff";      // ASVS 14.4.4
    ctx.Response.Headers["Referrer-Policy"] = "no-referrer";         // ASVS 14.4.6
    ctx.Response.Headers["Content-Security-Policy"] = "default-src 'self'"; // 14.4.3
    await next();
});
app.UseCors(p => p.WithOrigins(allowed).AllowCredentials());         // ASVS 14.5.3
app.UseAuthentication(); app.UseAuthorization();
```
A finding whose remediation is one of these lines maps cleanly to the control shown.

## Manual trace checklist (what proves a "Verified" claim)
1. Gateway vs service: if Ocelot/YARP or nginx terminates TLS and sets headers, V14.4 evidence
   is in the gateway config, not `Program.cs`. Record which file was checked in `scope.checked`.
2. `[AllowAnonymous]` inventory: each one is deliberate (login, register, health) - V4.1.1.
3. One ownership query per aggregate root traced end to end - V4.2.1.
4. Token validation parameters opened and read - V3.5.3.
5. Serilog enrichers / destructuring policies reviewed for PII - V7.1.

## Stack-specific false positives
- `FromSqlRaw("... {0}", id)` with positional args is parameterized (not a 5.3.4 failure).
- `[AllowAnonymous]` on `/health` and `/login` is expected.
- Missing `UseHsts()` in a service that only ever sits behind a TLS-terminating gateway that
  sets HSTS itself: downgrade to Low and cite the gateway config as the compensating control.
- `Secure=SameAsRequest` is fine when HTTPS redirection is enforced.

## Tooling
- `dotnet list package --vulnerable --include-transitive` (V14.2.1 evidence).
- `SecurityCodeScan.VS2019` analyzer: its SCS ids map to CWE (SCS0002 = CWE-89, SCS0029 = CWE-79,
  SCS0005 = CWE-338, SCS0018 = CWE-22); feed the CWE into `references` before running the mapper.
- `dotnet-counters`, `curl -I https://host` for live header checks (goes in `audit/evidence/`).

## References
- OWASP ASVS 4.0.3 chapters V3, V4, V5, V14; OWASP Top 10 2021 CWE mapping (A01-A10).
- ASP.NET Core security docs: "Enforce HTTPS", "Prevent XSRF", "Data protection", "Safe storage of app secrets".
- CWE-89, CWE-79, CWE-639, CWE-798, CWE-352, CWE-942, CWE-319, CWE-532.
