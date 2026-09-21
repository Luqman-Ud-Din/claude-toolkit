# .NET / ASP.NET Core reference for audit-production-readiness-checklist

## Stack markers
`*.csproj`, `Program.cs`/`Startup.cs`, `appsettings*.json`, `launchSettings.json` (dev only), `Dockerfile` with `ASPNETCORE_ENVIRONMENT`. Variants: several MicroAPI hosts behind Ocelot (check each host), worker services (health via `Microsoft.Extensions.Diagnostics.HealthChecks` + a tiny HTTP listener or file probe), Hangfire job hosts.

## Where each checklist item lives
- **Env config:** `appsettings.json` + `appsettings.{Environment}.json`; `ASPNETCORE_ENVIRONMENT` in Dockerfile/compose/k8s; `builder.Configuration.AddEnvironmentVariables()` (default in `WebApplication.CreateBuilder`); `AddAzureKeyVault`/`AddUserSecrets` (dev). Fail when `appsettings.json` alone holds production values or `appsettings.Production.json` holds literals.
- **Secrets:** `ConnectionStrings` with `Password=`/`Pwd=`, `Jwt:Key`, `ApiKey`, SMS/Shopify/Google credentials in any `appsettings*.json` or `.cs`. `Server=localhost` in `appsettings.Development.json` is fine; a real host in `appsettings.Production.json` with a password is Critical.
- **Debug off:** `app.UseDeveloperExceptionPage()` outside `if (app.Environment.IsDevelopment())`; `UseSwagger()/UseSwaggerUI()` unguarded (Medium unless auth); `EnableSensitiveDataLogging()`, `EnableDetailedErrors()`; `"DetailedErrors": true`; Serilog `MinimumLevel: Debug` in production config; `<DebugType>full</DebugType>` for release; `launchSettings.json` is dev-only (ignore).
- **Health checks:** `builder.Services.AddHealthChecks()` + `app.MapHealthChecks("/health")`. Dependency verification needs `AspNetCore.HealthChecks.SqlServer/NpgSql/MySql/Redis/RabbitMQ/Uris` packages: `.AddSqlServer(cs, name: "db")`, `.AddRabbitMQ(...)`, `.AddRedis(...)`, or custom `IHealthCheck` classes. Separate `/health/live` (no deps) and `/health/ready` (deps) via `Predicate`/tags. Must be `[AllowAnonymous]`/outside the auth middleware and excluded from Ocelot auth. Compose `healthcheck:` / k8s probes must target them.
- **Graceful shutdown:** default host handles SIGTERM with `HostOptions.ShutdownTimeout` (5 s default - often too short for Hangfire); check `builder.Services.Configure<HostOptions>(o => o.ShutdownTimeout = ...)`, `IHostApplicationLifetime.ApplicationStopping` used by background services, `BackgroundService.ExecuteAsync` honouring the `CancellationToken`, Hangfire `ServerShutdownTimeout`. Kestrel drains connections automatically. Unknown -> note the 5 s default vs orchestrator grace period.
- **Timeouts/retries:** `AddHttpClient(...)` with `c.Timeout` and `.AddStandardResilienceHandler()` (Microsoft.Extensions.Http.Resilience) or Polly `AddTransientHttpErrorPolicy`; `new HttpClient()` = fail; SQL `CommandTimeout`/`EnableRetryOnFailure()` in `UseSqlServer`; RabbitMQ `RequestedConnectionTimeout`, `AutomaticRecoveryEnabled`.
- **Caching:** `AddMemoryCache`/`AddStackExchangeRedisCache`/`AddOutputCache`/`AddResponseCaching`; strategy documented? Per-instance `IMemoryCache` for authoritative data behind >1 replica = fail.
- **Load test:** `k6/`, `*.jmx`, NBomber projects, `docs/perf*`, Azure Load Testing yaml.
- **Feature flags:** `Microsoft.FeatureManagement` (`AddFeatureManagement`, `IFeatureManager`, `"FeatureManagement"` config section), LaunchDarkly/Unleash/Flagsmith SDKs, `[FeatureGate]`.
- **Runbook / on-call / rollback / launch checklist:** docs folders; deploy scripts (`*.ps1`, `*.sh`, `azure-pipelines.yml`, `.github/workflows/*.yml`) with a rollback step (`helm rollback`, `kubectl rollout undo`, slot swap `az webapp deployment slot swap`); EF migrations reversible (`audit-db-schema`).
- **Alerting:** Application Insights alert rules (`*.bicep`/`*.tf` `azurerm_monitor_metric_alert`), Prometheus rules, Grafana provisioning, Seq alerts; Serilog sinks show where logs go.

## What "good" looks like
```csharp
var builder = WebApplication.CreateBuilder(args);   // env vars + appsettings.{Env}.json
builder.Services.AddHealthChecks()
    .AddSqlServer(builder.Configuration.GetConnectionString("Default")!, name: "sql", tags: new[] { "ready" })
    .AddRabbitMQ(rabbitConnectionString: builder.Configuration["RabbitMQ:Url"]!, name: "rabbit", tags: new[] { "ready" });
builder.Services.AddHttpClient<IFbrClient, FbrClient>(c => c.Timeout = TimeSpan.FromSeconds(10)).AddStandardResilienceHandler();
builder.Services.Configure<HostOptions>(o => o.ShutdownTimeout = TimeSpan.FromSeconds(25));
var app = builder.Build();
if (app.Environment.IsDevelopment()) { app.UseDeveloperExceptionPage(); app.UseSwagger(); app.UseSwaggerUI(); }
app.MapHealthChecks("/health/live", new() { Predicate = _ => false }).AllowAnonymous();
app.MapHealthChecks("/health/ready", new() { Predicate = r => r.Tags.Contains("ready") }).AllowAnonymous();
```
`appsettings.Production.json` contains only non-secret overrides; secrets arrive as `ConnectionStrings__Default` env vars or Key Vault.

## Manual trace checklist
1. For each host project: Dockerfile `ENV ASPNETCORE_ENVIRONMENT` -> which appsettings file wins -> literals in it.
2. `Program.cs` middleware order: is `/health` before `UseAuthentication`/`UseAuthorization` or marked anonymous; is it routed through Ocelot without auth?
3. Grep every `AddHttpClient`/`new HttpClient` and every `UseSqlServer` for timeout/retry.
4. Hangfire/BackgroundService: cancellation honoured, shutdown timeout set.
5. Deploy pipeline: rollback step present; last EF migration `Down()` non-empty.

## Stack-specific false positives
- `Server=localhost` / `(localdb)` in `appsettings.Development.json` or `launchSettings.json`.
- `UseDeveloperExceptionPage()` inside `if (app.Environment.IsDevelopment())`.
- `UseSwaggerUI()` in production when behind `[Authorize]` or an IP allow-list (downgrade to Low, note it).
- `AddHealthChecks()` without dependency checks on a stateless gateway (Ocelot) is acceptable if downstream services have readiness checks.

## Tooling
- `dotnet publish -c Release` then `dotnet <app>.dll --environment Production` locally with env vars to see which config wins (read-only for the repo).
- `curl -s localhost:PORT/health/ready` on a running instance; `docker inspect --format '{{json .State.Health}}' <container>`.
- `dotnet list package` to confirm `AspNetCore.HealthChecks.*`, `Microsoft.Extensions.Http.Resilience`, `Microsoft.FeatureManagement`.

## References
- Microsoft docs: Health checks in ASP.NET Core, Use multiple environments, Safe storage of app secrets, Building resilient HTTP apps, Host shutdown timeout.
- CWE-798 (hard-coded credentials), CWE-489 (active debug code), CWE-215 (debug info exposure), ASVS 14.1/14.2/14.3 (build, dependency, unintended security disclosure), OWASP A05:2021.
