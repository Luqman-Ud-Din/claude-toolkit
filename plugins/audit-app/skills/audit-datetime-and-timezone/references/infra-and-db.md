# Infrastructure and database checks (stack-independent)

Read this for every audit in addition to the stack files. These are the
places where a zone assumption is made outside application code.

## Cron and schedulers: where the zone must be explicit

| Scheduler | Where the zone goes | Without it |
|---|---|---|
| crontab / `cron.d` | `CRON_TZ=Asia/Karachi` line above the entry (cronie, Vixie 4+) | system zone of the host |
| Kubernetes `CronJob` | `spec.timeZone: "Asia/Karachi"` (GA in 1.27) | kube-controller-manager's zone, usually UTC |
| GitHub Actions `schedule` | none available; always UTC | UTC |
| Hangfire | `RecurringJob.AddOrUpdate(..., cron, new RecurringJobOptions { TimeZone = TimeZoneInfo.FindSystemTimeZoneById(...) })` | UTC |
| Quartz (Java/.NET) | `CronScheduleBuilder.cronSchedule(...).inTimeZone(tz)` / `.InTimeZone(tz)` | JVM/process default |
| Spring `@Scheduled` | `@Scheduled(cron = "...", zone = "Asia/Karachi")` | JVM default (`user.timezone`) |
| node-cron / cron (npm) | `cron.schedule(expr, fn, { timezone: "Asia/Karachi" })` / `new CronJob(expr, fn, null, true, "Asia/Karachi")` | process zone (`TZ`) |
| BullMQ repeat | `repeat: { pattern: "...", tz: "Asia/Karachi" }` | UTC |
| Celery beat | `app.conf.timezone = "Asia/Karachi"`, `enable_utc = True`; `crontab(...)` uses that zone | UTC |
| APScheduler | `CronTrigger(..., timezone="Asia/Karachi")` | local |
| Django-Q / django-crontab | settings `TIME_ZONE` | settings `TIME_ZONE` |
| Windows Task Scheduler / systemd timers | host zone; `systemd` `OnCalendar=... Asia/Karachi` (v256+) | host zone |
| Azure Functions timer | `WEBSITE_TIME_ZONE` app setting | UTC |
| AWS EventBridge | `ScheduleExpressionTimezone` (Scheduler) or UTC (Rules) | UTC |

Questions for each schedule: does the job represent a *local* wall-clock
event (statements at end of business day) or an *elapsed* interval (every 6 h)?
Local events need a zone and must avoid 01:00-03:00 in DST zones; intervals
should use fixed-rate expressions or UTC.

## Process and container zone

- Dockerfile: `ENV TZ=...` present? `tzdata` installed (Alpine/Debian slim images lack it; `TimeZoneInfo.FindSystemTimeZoneById` throws)? Prefer no `TZ` (UTC) and convert in code.
- .NET: `TZ` env, `InvariantGlobalization` (breaks zone names), `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT`.
- JVM: `-Duser.timezone=UTC` in `JAVA_TOOL_OPTIONS`/`JAVA_OPTS`; without it the JVM uses the host zone.
- Node: `process.env.TZ`; Docker images default UTC; developer machines do not.
- Python: `TZ` env, Django `TIME_ZONE` and `USE_TZ = True`.
- Compose/k8s: `environment: - TZ=...` on each service; DB container zone separately.

## Database column types and session zone

| Database | Zone-aware type | Zone-less type (needs a convention) | Session zone setting |
|---|---|---|---|
| PostgreSQL | `timestamptz` (stored UTC, rendered in session zone) | `timestamp` (`timestamp without time zone`) | `SHOW TimeZone;` set via `postgresql.conf` or `ALTER ROLE ... SET timezone` |
| SQL Server | `datetimeoffset` | `datetime`, `datetime2`, `smalldatetime` | none per session; `SYSDATETIMEOFFSET()` vs `GETDATE()` (server local) |
| MySQL/MariaDB | `TIMESTAMP` (converted to/from session zone, 2038 limit) | `DATETIME` | `SELECT @@global.time_zone, @@session.time_zone;` |
| Oracle | `TIMESTAMP WITH TIME ZONE` | `DATE`, `TIMESTAMP` | `SESSIONTIMEZONE` |
| SQLite | none (text/int) | everything | none |
| MongoDB | BSON Date is UTC instant | strings | none |

Checks:
- Every instant column is either zone-aware or zone-less *with a documented UTC convention* (name suffix `Utc`, EF value converter, JPA `@Column(columnDefinition = "timestamptz")`, Prisma `DateTime` maps to `timestamp(3)` in Postgres which is zone-less).
- Defaults: `DEFAULT GETDATE()`/`NOW()`/`CURRENT_TIMESTAMP` are server/session-local in SQL Server/MySQL; prefer `GETUTCDATE()`/`SYSUTCDATETIME()`/`UTC_TIMESTAMP()` or `now() AT TIME ZONE 'UTC'`.
- Date-only concepts use `date` columns, not midnight timestamps.
- Grouping SQL: `CAST(x AS DATE)`, `DATE(x)`, `date_trunc('day', x)` on UTC columns must apply `AT TIME ZONE` / `CONVERT_TZ` first.
- Migrations: look for `timestamp` without `tz` and `datetime` where instants are stored.

## Wire formats

- Instants: ISO 8601 / RFC 3339 with offset: `2024-03-10T14:30:00Z` or `+05:00`. Reject `2024-03-10T14:30:00` (ambiguous), `10/03/2024`, epoch seconds vs milliseconds mix.
- Date-only: `YYYY-MM-DD` and typed as a date, never `T00:00:00`.
- Serializers: .NET `System.Text.Json` writes `DateTime` `Kind=Unspecified` without offset; Jackson needs `WRITE_DATES_AS_TIMESTAMPS=false` and a zone; Django REST `DATETIME_FORMAT`; JS `toISOString()` (always `Z`) vs `toString()` (local).
- Excel/CSV import: serial numbers and locale formats; state the zone in the template.

## What to record in the Environment table

Container TZ, tzdata present, JVM/Node/Python zone flags, DB column defaults, DB session zone (ask the user to run the query if not in repo), CI `TZ`, scheduler zones.
