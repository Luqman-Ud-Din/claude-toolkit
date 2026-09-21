# Date-driven decision flows to trace

For every flow the app has, answer the five questions and record the result
in the "Date-driven decision flows traced" table. A flow is *verified* only
when the zone it assumes is the zone the user expects and the code still
gives the right answer at 23:30 on a DST-change day.

The five questions:
1. What instant or date does the decision read, and from which field (see the date-field map)?
2. What zone does the code assume (server local, UTC, user, branch, none)?
3. What zone does the business expect (user, branch/store, legal jurisdiction, UTC)?
4. Is the boundary inclusive/exclusive as the business expects, and does it survive DST (23h/25h days) and leap days?
5. Is "now" injectable (TimeProvider, Clock, fake timers) so a test can pin it?

## 1. "Today" and day boundaries
Reports "for today", dashboards "sales today", daily counters, "orders placed today" lists.
- Smell: `DateTime.Today`, `LocalDate.now()`, `new Date().setHours(0,0,0,0)`, `date.today()`, `timezone.now().date()` compared to UTC columns.
- Correct: pick the zone (user or branch, stored), compute local midnight, convert to UTC, query UTC.
- Edge: a zone at UTC+5 has "today" starting at 19:00 UTC yesterday.

## 2. Cutoffs and expiry
Trial ends, token/OTP expiry, "cancel within 24 h", return window, coupon valid until, invoice due date, quote validity.
- Smell: `ExpiresAt < DateTime.Now` where `ExpiresAt` is UTC; date-only `ValidUntil` compared as midnight (expires at 00:00, not end of day); `AddDays(1)` for "24 hours" across DST.
- Correct: instants compared as instants in UTC; date-only expiry means end of that day in the *customer's* zone (`< nextDay 00:00 local`).
- Edge: end-of-day expiry evaluated by a cron in another zone.

## 3. Billing periods and proration
Monthly renewal, period start/end, proration on plan change, "days remaining", usage aggregation per period.
- Smell: `AddMonths(1)` from Jan 31 (Feb 28/29 drift), period boundaries at server midnight, `(end - start).TotalDays` across DST giving 29.96, storing period start as local date.
- Correct: anchor day stored, periods computed in the customer's billing zone or in UTC consistently, durations from instants.
- Edge: subscription created 31 Jan; DST day in the period; customer moves zone.

## 4. Scheduling and cron
Nightly jobs, reminders "at 9am", statement generation, retention purges, rate resets.
- Smell: cron expression with no zone (k8s `timeZone`, Hangfire `TimeZoneInfo`, Quartz `inTimeZone`, node-cron `timezone`, Celery `timezone`/`CELERY_TIMEZONE`, crontab `CRON_TZ`); "run at 02:30 local" (does not exist / runs twice on DST days); `setTimeout` for long delays.
- Correct: explicit IANA zone on the schedule, idempotent job (hand overlap to RACE), avoid 01:00-03:00 local in DST zones.
- Edge: DST spring-forward skips 02:00-03:00; fall-back repeats it.

## 5. Durations, SLAs and timers
Response time, "hours until delivery", session length, rate-limit windows, age calculation.
- Smell: subtracting local wall-clock times; `TotalHours` on `DateTime` with mixed Kind; age from `Year - Year`; storing durations as end-of-day timestamps.
- Correct: subtract UTC instants; calendar math (age, business days) in the relevant zone with a date library.

## 6. Reporting and aggregation
Group by day/week/month, charts, exports, tax periods.
- Smell: SQL `CAST(CreatedUtc AS DATE)` / `DATE(created_at)` / `date_trunc('day', ts)` on UTC columns with no `AT TIME ZONE`; week starting on the wrong day for the locale; month-end at server midnight.
- Correct: `AT TIME ZONE 'Asia/Karachi'` (Postgres/SQL Server), `CONVERT_TZ` (MySQL), or group in the app after converting; zone recorded on the export.

## 7. Sorting, comparison and equality
Ordering lists by date, "latest", dedupe by day.
- Smell: sorting on `dd/MM/yyyy` strings; comparing formatted strings; `==` between naive and aware datetimes (Python raises, JS coerces silently); `DateTime` with `Kind=Unspecified` compared to `UtcNow`.
- Correct: sort on the instant (epoch or ISO string with fixed offset `Z`, which sorts lexically), compare typed values.

## 8. Input and output at the edges
API request/response dates, CSV/Excel import, provider webhooks, UI pickers.
- Smell: `yyyy-MM-dd HH:mm:ss` without offset in JSON; `new Date("2024-03-10")` (UTC midnight) vs `new Date("2024-03-10T00:00")` (local); Excel serials converted in server zone; `DateTime.Parse` with current culture; user zone inferred from browser instead of stored profile/branch.
- Correct: ISO 8601 with offset (`2024-03-10T14:30:00+05:00` or `Z`) for instants, plain `YYYY-MM-DD` for date-only, and a stored user/branch zone used for conversion.

## 9. Display
Timestamps shown without a zone label; times shown in server zone; relative times ("2 hours ago") computed from naive values.
- Correct: show in the viewer's zone with a label or offset, or state the zone once on the page.

## 10. Tests
Tests that call `DateTime.Now`/`Date.now()` directly, that pass only in one zone, or that never cover DST or month-end.
- Correct: injectable clock (`TimeProvider`, `Clock`, `jest.useFakeTimers`, `freezegun`), CI with `TZ` set to a non-UTC zone at least once, explicit DST and Feb 29 cases.
