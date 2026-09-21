# .NET / C# reference for audit-logging-and-observability

## Stack markers

`*.csproj`, `Program.cs`, `Startup.cs`. Sub-variants worth distinguishing:
Serilog (`Serilog.AspNetCore`, `UseSerilog()`) vs plain `Microsoft.Extensions.Logging`,
minimal APIs vs controllers, and whether `OpenTelemetry.Extensions.Hosting` is
referenced. Check the `.csproj` PackageReference list first - it tells you in
ten seconds which logger, which sink and whether telemetry exists at all.

## Where the relevant code lives

- `Program.cs` / `Startup.cs` - logger bootstrap, middleware order, OTel setup.
- `appsettings*.json` - `Serilog` section (`MinimumLevel`, `WriteTo`, `Enrich`,
  `Destructure`), `Logging:LogLevel`, `ApplicationInsights` connection string.
- `Middleware/`, `Filters/` - request logging, exception filters, correlation id.
- Controllers and Managers - the `_logger.Log*` calls themselves.
- `BackgroundJobs/`, `HostedService` classes - the logs nobody reads until an
  incident; also where correlation ids are usually lost.

## Dangerous / interesting APIs and patterns

- `LogInformation($"...{user.Email}")` - interpolated string: destroys structure
  *and* bakes PII into the message template.
- `Log*("{@Model}", dto)` - `@` destructures the whole object; any password,
  token, card number or address on the DTO lands in the log.
- `LogInformation("body {Body}", await Request.ReadFromJsonAsync<T>())`, or any
  logging of `HttpContext.Request.Body`, `Request.Headers` (carries
  `Authorization`), `Response.Content`.
- `catch (Exception ex) { _logger.LogDebug(...) }` / `LogInformation` /
  `LogWarning` for a real failure; `catch { }` or `catch { return null; }`.
- `_logger.LogError(ex.Message)` - loses the stack trace; pass the exception:
  `LogError(ex, "template")`.
- `Console.WriteLine`, `Debug.WriteLine`, `Trace.Write` in service code.
- `optionsBuilder.EnableSensitiveDataLogging()` - EF Core then logs parameter
  values, including credentials and personal data, at Information.
- `"MinimumLevel": "Debug"|"Verbose"` in `appsettings.Production.json`.
- Absence markers: no `ILogger` injected into the auth controller at all; no
  `AddOpenTelemetry()`, no `AddW3CLogging`, no correlation middleware.
- `Serilog.Sinks.File` / `MSSqlServer` only, with no stdout/collector sink - the
  logs die with the container or compete with the app for the database.

## What "good" looks like

```csharp
// Program.cs
builder.Host.UseSerilog((ctx, cfg) => cfg
    .ReadFrom.Configuration(ctx.Configuration)
    .Enrich.FromLogContext()
    .Enrich.WithProperty("service", "Product.MicroAPI")
    .Destructure.ByTransforming<LoginRequest>(r => new { r.Email })   // never the password
    .WriteTo.Console(new CompactJsonFormatter()));                    // collector scrapes stdout

builder.Services.AddOpenTelemetry()
    .WithTracing(t => t.AddAspNetCoreInstrumentation().AddHttpClientInstrumentation()
                       .AddEntityFrameworkCoreInstrumentation().AddOtlpExporter())
    .WithMetrics(m => m.AddAspNetCoreInstrumentation().AddRuntimeInstrumentation().AddOtlpExporter());

app.Use(async (ctx, next) =>                      // correlation id, before everything that logs
{
    var cid = ctx.Request.Headers["X-Correlation-Id"].FirstOrDefault() ?? Activity.Current?.TraceId.ToString() ?? Guid.NewGuid().ToString("N");
    ctx.Response.Headers["X-Correlation-Id"] = cid;
    using (LogContext.PushProperty("CorrelationId", cid)) await next();
});
```

Structured call with no PII, exception passed, right level:

```csharp
_logger.LogError(ex, "Stock reservation failed for order {OrderId} in company {CompanyId}", orderId, companyId);
_logger.LogInformation("Login failed for {EmailHash} from {Ip}", Hash(email), ip);   // security event
```

Outbound propagation: `HttpClient` created via `AddHttpClient` with
`AddHttpMessageHandler<CorrelationIdHandler>()` so `X-Correlation-Id` and
`traceparent` are forwarded; Hangfire jobs take the id as a job argument and
push it into `LogContext` on start.

## Manual trace checklist

1. `Program.cs`: is the correlation middleware registered **before**
   `UseRouting`/`UseSerilogRequestLogging`, and does it flow into `LogContext`?
2. The auth controller: login success, failure, lockout, token refresh - each
   logged once, at the right level, with no password or token argument.
3. Any `Log*` call whose argument is a request DTO, `Request.Headers`, a
   `ClaimsPrincipal`, or an entity with personal columns.
4. Every `catch` in the payment/stock/tenant paths: level, exception passed,
   rethrown or handled.
5. Background jobs and `IHostedService`: do they set a correlation id, and is
   a failed job logged at Error and surfaced (Hangfire dashboard is not an alert).
6. `appsettings.Production.json`: minimum level, sinks, retention, and whether
   `EnableSensitiveDataLogging` is on anywhere.

## Stack-specific false positives

- `Log*` with `{@Dto}` where the DTO is a small, already-public projection
  (ids and names) - confirm the type's properties before rating.
- `LogDebug` inside a `catch` that is genuinely an expected control-flow case
  (cache miss, optimistic-concurrency retry) and is handled immediately after -
  Info/Low at most; say so in the finding.
- `Console.WriteLine` in a `Program.cs` startup banner or a console tool project.
- `EnableSensitiveDataLogging()` guarded by `if (env.IsDevelopment())`.

## Tooling

```bash
dotnet list package | findstr /I "serilog opentelemetry applicationinsights nlog"
grep -rn "LogInformation\|LogDebug\|LogError\|LogWarning\|LogTrace\|LogCritical" --include=*.cs .
grep -rn "{@" --include=*.cs .                 # destructured objects
grep -rn "EnableSensitiveDataLogging\|Console.WriteLine" --include=*.cs .
```
Roslyn analyzer `CA2254` (template should be a static expression) catches
interpolated log messages; enable it in `.editorconfig` as a warning.

## References

- Serilog: message templates, `Destructure.ByTransforming`, `LogContext`.
- .NET: `ILogger` semantics, log levels, `Activity`/`ActivitySource`, W3C trace context.
- CWE-532, CWE-778, CWE-117; ASVS 7.1.1-7.3.4, 8.3.4; OWASP A09:2021.
