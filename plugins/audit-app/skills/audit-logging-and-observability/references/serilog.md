# Serilog reference for audit-logging-and-observability

## Message templates, not interpolation

```csharp
_log.LogInformation($"Order {order.Id} for {user.Email}");                      // bad: no properties, PII in text, CA2254
_log.LogInformation("Order {OrderId} placed by {UserId}", order.Id, user.Id);    // good
```
Interpolated or concatenated messages create a unique template per call, break
grouping and searching, and bake values into the text where redaction cannot see
them. Enable analyzer `CA2254` as a warning in `.editorconfig`.

## Destructuring

- `{@Request}` serialises every public property; `{Request}` calls `ToString()`
  for complex types; `{$Request}` forces `ToString()`. Any `{@...}` on a DTO with
  `Password`, `Token` or `CardNumber` is a leak.
- Control it centrally:
  - `.Destructure.ByTransforming<LoginRequest>(r => new { r.Email })`
  - Destructurama.Attributed: `.Destructure.UsingAttributes()` then
    `[NotLogged] public string Password { get; set; }` and
    `[LogMasked(ShowFirst = 0, ShowLast = 4)] public string CardNumber { get; set; }`
  - `.Destructure.ToMaximumDepth(4)`, `.ToMaximumStringLength(1024)`, `.ToMaximumCollectionCount(20)`.

## Context and request logging

```csharp
Log.Logger = new LoggerConfiguration().WriteTo.Console().CreateBootstrapLogger();   // catches startup failures
builder.Host.UseSerilog((ctx, sp, cfg) => cfg.ReadFrom.Configuration(ctx.Configuration)
    .ReadFrom.Services(sp).Enrich.FromLogContext());

app.UseSerilogRequestLogging(o =>
{
    o.EnrichDiagnosticContext = (diag, http) =>
    {
        diag.Set("CorrelationId", http.TraceIdentifier);
        diag.Set("UserId", http.User.FindFirst("sub")?.Value);          // an id, never the token
    };
    o.GetLevel = (http, _, ex) => ex != null || http.Response.StatusCode >= 500
        ? LogEventLevel.Error : LogEventLevel.Information;
});
```
`Enrich.FromLogContext()` is required for `LogContext.PushProperty("CorrelationId", ...)`
to appear. Without it, correlation middleware "works" but the property never
reaches a sink. `UseSerilogRequestLogging` must come after the correlation
middleware and before the endpoints it should time.

## appsettings keys

```json
"Serilog": {
  "Using": ["Serilog.Sinks.Console", "Serilog.Sinks.OpenTelemetry"],
  "MinimumLevel": { "Default": "Information",
    "Override": { "Microsoft.AspNetCore": "Warning", "Microsoft.EntityFrameworkCore.Database.Command": "Warning", "System.Net.Http.HttpClient": "Warning" } },
  "WriteTo": [ { "Name": "Console", "Args": { "formatter": "Serilog.Formatting.Compact.CompactJsonFormatter, Serilog.Formatting.Compact" } },
               { "Name": "OpenTelemetry", "Args": { "endpoint": "http://otel-collector:4317" } } ],
  "Enrich": ["FromLogContext", "WithMachineName"]
}
```
Audit points: `Default` of `Debug`/`Verbose` in production; EF Core command logger
at `Information` (logs SQL, and parameter values if `EnableSensitiveDataLogging`);
no `Override` block, so framework noise floods the sink.

## Sinks

- `Console` with `CompactJsonFormatter` / `RenderedCompactJsonFormatter` - the right default in containers; a collector ships stdout.
- `Seq`, `Elasticsearch`, `Datadog.Logs`, `OpenTelemetry` (`Serilog.Sinks.OpenTelemetry`, OTLP) - centralised.
- `File` - acceptable on VMs with `rollingInterval: Day` and `retainedFileCountLimit: 31` (the default is 31; `null` means unlimited disk growth); lost on container restart.
- `MSSqlServer` - caveats: logs compete with the application database for IO, a database outage takes the logs with it, retention needs a purge job, and anyone with read access to the database reads the logs. Flag as Medium when it is the only sink.
- `Async` wrapper without `Log.CloseAndFlush()` on shutdown - the last events (often the crash) are lost.

## Exceptions

`_log.LogError(ex, "Payment capture failed for {OrderId}", id)` - exception as the
first argument. `LogError(ex.Message)` loses the stack trace; `LogWarning` /
`LogDebug` in a catch hides the failure at production levels.

## Grep recipes

```bash
grep -rnE 'Log(Information|Debug|Warning|Error|Trace|Critical)\(\$"' --include=*.cs .      # interpolated
grep -rnE '\{@[A-Za-z]+\}' --include=*.cs .                                              # destructured objects
grep -rnE 'catch[^{]*\{[^}]*Log(Debug|Trace)\(' --include=*.cs .                          # same-line low-level catch
grep -rn "Enrich.FromLogContext\|UseSerilogRequestLogging\|CreateBootstrapLogger" --include=*.cs .
grep -rn '"MinimumLevel"' --include=appsettings*.json .
grep -rn "NotLogged\|LogMasked\|Destructure\." --include=*.cs .
```
