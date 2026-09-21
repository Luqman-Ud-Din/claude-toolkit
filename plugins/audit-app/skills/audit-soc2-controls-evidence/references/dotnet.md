# .NET / C# reference for audit-soc2-controls-evidence

## Stack markers

`*.csproj`, `*.sln`, `Program.cs`, `Startup.cs`, `appsettings*.json`. Sub-variants
worth distinguishing: ASP.NET Core Identity (local accounts) vs an external IdP
(`Microsoft.Identity.Web`, `AddOpenIdConnect`), controllers vs minimal APIs,
EF Core vs Dapper, containers vs App Service. The `.csproj` PackageReference list
tells you in a minute which auth, logging, secrets and health packages exist -
read it before grepping.

## Where the relevant code lives

- `Program.cs` / `Startup.cs` - authentication, authorization policies, health
  checks, Key Vault configuration, HTTPS/HSTS, Serilog bootstrap.
- `appsettings*.json` - `Serilog` sinks, `ConnectionStrings` (`Encrypt=True`),
  `AzureAd` / `Authentication` sections, `KeyVault` URIs.
- `Controllers/`, `Endpoints/` - `[Authorize]`, `[AllowAnonymous]`, admin actions.
- `Data/*DbContext.cs`, `Interceptors/` - `SaveChangesInterceptor` audit trail,
  temporal tables (`IsTemporal()`), `[Timestamp]` rowversion, unique indexes.
- `Migrations/` or an external schema folder; `BackgroundJobs/`, `IHostedService`.
- `.github/workflows/`, `azure-pipelines.yml` - build, test, scan, deploy.

## Dangerous / interesting APIs and patterns

- CC6.1 auth: `AddAuthentication`, `AddJwtBearer`, `AddOpenIdConnect`,
  `AddMicrosoftIdentityWebApi`, `AddIdentity<...>`. Bad: `ValidateIssuer = false`,
  `ValidateLifetime = false`, `RequireHttpsMetadata = false` outside Development.
- MFA: `TwoFactorEnabled`, `SignInManager.TwoFactorSignInAsync`,
  `RequireClaim("amr", "mfa")`. No MFA in code usually means "enforced at the IdP" -
  that is organisational evidence (Conditional Access policy export), not a pass.
- CC6.1 rbac: `[Authorize(Roles = ...)]`, `[Authorize(Policy = ...)]`, `AddPolicy`,
  `RequireRole`, `FallbackPolicy`. Bad: controllers with no `[Authorize]` and no
  fallback policy; `[AllowAnonymous]` on admin routes.
- Lockout: `options.Lockout.MaxFailedAccessAttempts`, `LockoutEnabled`.
- CC6.1 admin-log / PI1.3: `SaveChangesInterceptor`, `ChangeTracker.Entries()` writing
  an `AuditLog` table, `IsTemporal()` / `SYSTEM_VERSIONING`, Audit.NET.
- CC6.3 deprovisioning: `IsActive = false`, `LockoutEnd = DateTimeOffset.MaxValue`,
  `UpdateSecurityStampAsync` (invalidates cookies), refresh-token revocation table.
- CC7.2: Serilog `WriteTo.Seq|ApplicationInsights|Elasticsearch|OpenTelemetry`
  (central) vs `WriteTo.Console()` only; `ILogger` calls on login failure and denial.
- A1.1: `AddHealthChecks().AddSqlServer(...)`, `MapHealthChecks("/health")`.
- C1: `AddAzureKeyVault`, `AddUserSecrets` (dev only), `IDataProtector`,
  `PersistKeysToAzureBlobStorage().ProtectKeysWithAzureKeyVault(...)`, Always
  Encrypted (`Column Encryption Setting=Enabled`). Bad: secret literals in
  `appsettings.json`.
- PI1: DataAnnotations (`[Required]`, `[Range]`), FluentValidation
  `AbstractValidator<T>`, `ModelState.IsValid`, `[Timestamp] byte[] RowVersion`,
  `HasIndex(...).IsUnique()`.

## What "good" looks like

```csharp
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddMicrosoftIdentityWebApi(builder.Configuration.GetSection("AzureAd"));   // SSO; MFA via Conditional Access
builder.Services.AddAuthorization(o =>
{
    o.FallbackPolicy = new AuthorizationPolicyBuilder().RequireAuthenticatedUser().Build();
    o.AddPolicy("Admin", p => p.RequireRole("Admin"));
});
builder.Configuration.AddAzureKeyVault(new Uri(builder.Configuration["KeyVault:Uri"]!), new DefaultAzureCredential());
builder.Services.AddDbContext<AppDb>((sp, o) => o.UseSqlServer(cs).AddInterceptors(sp.GetRequiredService<AuditInterceptor>()));
builder.Services.AddHealthChecks().AddSqlServer(cs);
app.MapHealthChecks("/health");
```

Pipeline shape: `dotnet build` -> `dotnet test` -> `dotnet list package --vulnerable
--include-transitive` failing on output -> `dotnet ef migrations bundle` artefact
applied by the deploy job in a protected `production` environment with reviewers.

## Manual trace checklist

1. `Program.cs`: authentication scheme, token validation parameters, fallback policy;
   every `[AllowAnonymous]` endpoint and why.
2. Admin endpoints (role change, user deactivate, export): policy enforced
   server-side and an audit row written with actor, target and timestamp.
3. Deactivation path: does it revoke refresh tokens / update the security stamp, or
   can a disabled user keep using an issued JWT until it expires?
4. Pipeline: scan step present and blocking; migrations applied only by the pipeline.
5. Backups of SQL Server / Azure SQL: `BACKUP DATABASE` job or LTR policy in IaC
   (`azurerm_mssql_database` `long_term_retention_policy`), plus a dated restore test.
6. Secrets: every connection string and signing key resolved from Key Vault or env.

## Stack-specific false positives

- `AddUserSecrets` and `RequireHttpsMetadata = false` inside `if (env.IsDevelopment())`.
- `WriteTo.Console()` in a container whose platform ships stdout to a central store -
  mark partial and ask for the platform evidence rather than failing the control.
- Literal `Password=` in `appsettings.Development.json` pointing at localhost.
- `[AllowAnonymous]` on `/health`, login and token-refresh endpoints.

## Tooling

```bash
dotnet list package --vulnerable --include-transitive
dotnet list package --outdated
grep -rnE "AddAuthentication|AddJwtBearer|AddOpenIdConnect|AddMicrosoftIdentityWebApi" --include=*.cs .
grep -rnE "\[Authorize|\[AllowAnonymous|RequireRole|AddPolicy" --include=*.cs .
grep -rnE "SaveChangesInterceptor|IsTemporal|AuditLog|MapHealthChecks|AddAzureKeyVault" --include=*.cs .
```
SAST options: GitHub CodeQL (`csharp`), `SecurityCodeScan.VS2019`, SonarAnalyzer.CSharp.

## References

- ASP.NET Core security docs (authentication, authorization policies, Data Protection).
- Microsoft.Identity.Web; EF Core interceptors and temporal tables; ASP.NET Core health checks.
- SOC2-CC6.1, CC6.3, CC7.1, CC7.2, CC8.1, A1.2, C1.1, PI1.3; CWE-284, CWE-778, CWE-1104.
