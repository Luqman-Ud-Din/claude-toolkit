# .NET / C# reference for audit-datetime-and-timezone

## Stack markers
`*.csproj`, `*.sln`, `Program.cs`. Variants: EF Core (SQL Server / PostgreSQL via Npgsql / MySQL), Dapper; Hangfire / Quartz.NET jobs; `System.Text.Json` vs Newtonsoft; NodaTime present or not.

## Where the relevant code lives
- Entities: `*.Entity/*.cs`, `*DbContext.cs` (`HasColumnType`, value converters), migrations (`*.Designer.cs`, `.sql` scripts).
- Business: `*Manager.cs`, `*Service.cs`, report/query code with `.Date`, `DateTime.Today`.
- Edges: controllers and DTOs (`DateTime` vs `DateTimeOffset` properties), `JsonSerializerOptions`, `JsonConverter<DateTime>`, `CultureInfo`.
- Jobs: `BackgroundJobs/`, `RecurringJob.AddOrUpdate`, `IHostedService` timers.
- Tests: `*.Tests` for `DateTime.Now`, `Thread.Sleep`, `TimeProvider`/`ISystemClock` fakes.

## Dangerous / interesting APIs and patterns
- `DateTime.Now`, `DateTime.Today`, `DateTime.Now.Date`, `TimeZoneInfo.Local`, `DateTimeOffset.Now` (local offset) in server code; `GETDATE()` / `SYSDATETIME()` in SQL strings or column defaults.
- `DateTime` (not `DateTimeOffset`) on entities storing instants; `Kind` unspecified after EF materialisation (SQL Server `datetime2` returns `Kind=Unspecified`, then `ToUniversalTime()` shifts it by the server offset).
- `new DateTime(y, m, d)` for a cutoff compared to a UTC column; `DateTime.Parse(str)` / `Convert.ToDateTime` with current culture; `ToString("dd/MM/yyyy")` / `"yyyy-MM-dd HH:mm:ss"` written into JSON, CSV, or query strings.
- `.AddDays(1)` used as "24 hours" or `AddMonths(1)` from the 31st for billing periods; `(a - b).TotalDays` where one side is local.
- `DateTime.SpecifyKind(x, DateTimeKind.Utc)` scattered through business code (conversion not at the edge); `TimeZoneInfo.ConvertTime` inside LINQ-to-entities (not translatable, or translated to server zone).
- `TimeZoneInfo.FindSystemTimeZoneById("Pakistan Standard Time")` (Windows id; fails on Linux without ICU/tzdata mapping) or the reverse.
- Hangfire cron without `TimeZone` in `RecurringJobOptions`; Quartz `WithCronSchedule(...)` without `.InTimeZone`.
- `OrderBy(x => x.CreatedDate.ToString(...))`, string comparison of formatted dates.
- Tests using `DateTime.UtcNow` directly, `Thread.Sleep` for expiry, no `FakeTimeProvider`.
- Npgsql 6+: writing `DateTime` with `Kind=Local`/`Unspecified` to `timestamptz` throws or (legacy switch `Npgsql.EnableLegacyTimestampBehavior`) silently shifts.

## What "good" looks like
```csharp
// entity
public DateTimeOffset CreatedAt { get; set; }         // SQL Server datetimeoffset / PG timestamptz
public DateOnly InvoiceDate { get; set; }             // date column, no midnight timestamp
// now is injectable
public sealed class TrialService(TimeProvider clock) {
    public bool IsExpired(Subscription s) => s.TrialEndsAt <= clock.GetUtcNow();
}
// day boundary in the branch zone, compared in UTC
var tz = TimeZoneInfo.FindSystemTimeZoneById(branch.IanaZone);  // .NET 6+ accepts IANA ids on Windows too
var startUtc = new DateTimeOffset(localDate.ToDateTime(TimeOnly.MinValue), tz.GetUtcOffset(localDate.ToDateTime(TimeOnly.MinValue))).ToUniversalTime();
// JSON: DateTimeOffset serialises with offset; configure a converter for DateTime to force "Z"
```
EF: `HasColumnType("datetimeoffset")`, or a value converter that asserts `Kind == Utc` on write and sets `Kind=Utc` on read for `datetime2` columns. Tests: `FakeTimeProvider` (Microsoft.Extensions.TimeProvider.Testing).

## Manual trace checklist
1. Date-field map: every `DateTime`/`DateTimeOffset`/`DateOnly` property, its column type in `OnModelCreating`/migrations, naming (`*Utc`) and whether a converter enforces Kind.
2. Every `DateTime.Now`/`Today`: what decision it feeds (report window, expiry, cutoff, invoice date) and which zone the user expects.
3. Serialisation: `JsonSerializerOptions`, Newtonsoft `DateTimeZoneHandling`, DTO property types; sample a response for offset presence.
4. Hangfire/Quartz registrations: zone option present; job body uses `UtcNow` and stored zone.
5. Reports: SQL/LINQ grouping by `.Date` on UTC columns without zone conversion.
6. Tests: search for `DateTime.Now|UtcNow` in test projects; presence of `TimeProvider` fakes.

## Stack-specific false positives
- `DateTime.UtcNow` for `CreatedUtc` fields is correct; flag only if the column is `datetimeoffset` and Kind is lost, or the value is later treated as local.
- `DateTime.Now` in logging templates or file names (display only).
- `TimeZoneInfo.Local` in a desktop/Blazor WASM client rendering for the user (that *is* the edge).
- `DateOnly` compared to `DateOnly.FromDateTime(clock.GetUtcNow().Date)` when the business explicitly wants a UTC calendar day (confirm and record).

## Tooling
`grep -rn "DateTime\.Now\|DateTime\.Today\|TimeZoneInfo\.Local" --include=*.cs`; `grep -rn "HasColumnType(\"datetime\|timestamp" --include=*.cs`; Roslyn analyzers: `Meziantou.Analyzer` MA0132/MA0133 (do not use DateTime.Now), `NodaTime` adoption check (`grep -rn "NodaTime" *.csproj`).

## References
.NET docs "DateTime, DateTimeOffset, TimeSpan, and TimeZoneInfo: choosing"; Npgsql timestamp mapping (6.0 breaking change); Hangfire `RecurringJobOptions.TimeZone`; ISO 8601; CWE-682, CWE-704.
