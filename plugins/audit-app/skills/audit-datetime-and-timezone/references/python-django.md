# Python / Django (and Flask, FastAPI) reference for audit-datetime-and-timezone

## Stack markers
`manage.py`, `requirements.txt`/`pyproject.toml` with `django`, `djangorestframework`, `flask`, `fastapi`. Variants: Django with `USE_TZ` on/off; SQLAlchemy vs Django ORM; Celery beat / APScheduler / django-crontab; `pytz` vs `zoneinfo`; `freezegun`/`time-machine` in tests.

## Where the relevant code lives
- Settings: `settings.py` (`USE_TZ`, `TIME_ZONE`, `CELERY_TIMEZONE`, `REST_FRAMEWORK["DATETIME_FORMAT"]`), `celery.py` (`app.conf.timezone`, `beat_schedule`).
- Models: `models.py` (`DateTimeField` vs `DateField`, `auto_now`, `default=timezone.now` vs `datetime.now`), migrations (`0001_initial.py`), SQLAlchemy `Column(DateTime(timezone=True))`.
- Business: `services.py`, views, `utils/dates.py` with `datetime.now()`, `date.today()`, `.date()`, `localtime()`.
- Edges: serializers (`DateTimeField(format=...)`, `input_formats`), Pydantic models (`datetime` accepts naive), templates (`{{ x|date:"d/m/Y" }}`), CSV exports.
- Tests: `freezegun`, `time_machine`, `override_settings(TIME_ZONE=...)`, `datetime.now()` in fixtures.

## Dangerous / interesting APIs and patterns
- `datetime.now()`, `datetime.today()`, `date.today()`, `datetime.utcnow()` (naive UTC, deprecated in 3.12), `datetime.fromtimestamp(ts)` (local) in server code; `time.localtime()`.
- `USE_TZ = False` (all datetimes naive in `TIME_ZONE`); `TIME_ZONE` not `UTC` with `USE_TZ = True` but `timezone.now().date()` used for "today" (that is the UTC date, not the local date).
- `timezone.now().date()` / `timezone.now().replace(hour=0, minute=0)` for day boundaries (UTC midnight); `timezone.localdate()` without an explicit zone (uses `TIME_ZONE`, not the user's).
- Naive/aware mixing: `datetime(2024, 3, 10)` compared to an aware field (`TypeError` at runtime, or `RuntimeWarning: received a naive datetime` from the ORM which then assumes `TIME_ZONE`); `make_aware` sprinkled through business code.
- `DateTimeField` for date-only concepts (due date, invoice date) with `auto_now_add`; `DateField` compared to `timezone.now()`.
- `strftime("%d/%m/%Y")` / `"%Y-%m-%d %H:%M:%S"` in API output; `strptime` of client input without `%z`; `dateutil.parser.parse` accepting anything; `isoformat()` on naive values (no offset).
- `timedelta(days=1)` as "tomorrow" across DST with `pytz` localized values; `pytz.timezone(...)` used via `datetime(..., tzinfo=tz)` (wrong LMT offset) instead of `tz.localize()` or `zoneinfo`; `relativedelta(months=1)` from the 31st.
- Celery `beat_schedule` with `crontab(hour=2)` and `timezone` unset (UTC) while the business wants local; `enable_utc = False`; APScheduler `CronTrigger` without `timezone`.
- SQL: `DATE(created_at)`, `TruncDay('created_at')` without `tzinfo=`, `created_at__date=today` (uses current zone from `TIME_ZONE`/`activate()`, not the user's).
- Sorting: `sorted(rows, key=lambda r: r["date_str"])`; comparing `str(dt)`.
- Tests: `datetime.now()` in tests, no `freezegun`, `@override_settings(USE_TZ=False)` to make tests pass.

## What "good" looks like
```python
# settings.py
USE_TZ = True; TIME_ZONE = "UTC"
CELERY_TIMEZONE = "Asia/Karachi"; CELERY_ENABLE_UTC = True
# models.py
created_at = models.DateTimeField(default=timezone.now)   # aware UTC
invoice_date = models.DateField()                          # date-only
# day window in the branch zone
tz = ZoneInfo(branch.iana_zone)
start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
qs = Order.objects.filter(created_at__gte=start, created_at__lt=end)
# grouping in a zone
.annotate(day=TruncDay("created_at", tzinfo=tz))
# clock injection for tests
def is_expired(sub, now=None): now = now or timezone.now(); return sub.trial_ends_at <= now
```
DRF: `DATETIME_FORMAT = "iso-8601"` (default) and aware values so output carries `+00:00`/`Z`; Pydantic `AwareDatetime` for inputs. Tests: `freezegun.freeze_time("2024-03-10T01:30:00Z")` or `time_machine.travel`; a CI run with `TZ=Asia/Karachi`.

## Manual trace checklist
1. `USE_TZ`, `TIME_ZONE`, Celery zone settings; SQLAlchemy `DateTime(timezone=True)` usage.
2. Date-field map from models and migrations: aware vs naive vs date-only; `auto_now` on date-only concepts.
3. Every `datetime.now()`/`date.today()`/`timezone.now().date()`: what decision it feeds and in which zone.
4. Serializer/Pydantic input: naive strings accepted; output format includes offset.
5. Celery/APScheduler schedules: zone explicit; task bodies use aware UTC and the stored zone.
6. Reports: `__date`, `TruncDay`, raw `DATE()` without `tzinfo`.
7. Tests: freezing present; `USE_TZ` overridden in tests.

## Stack-specific false positives
- `timezone.now()` for `created_at` defaults: correct.
- `date.today()` in a management command that only names a log file.
- `localtime()`/`localdate()` in template tags or views that render for the user *and* `activate(user_tz)` is called in middleware (confirm the middleware exists).
- `DateField` compared to `timezone.localdate(tz)` with an explicit zone: correct.

## Tooling
`grep -rn "datetime.now()\|date.today()\|utcnow()\|fromtimestamp(\|strftime(" --include=*.py`; `grep -rn "USE_TZ\|TIME_ZONE\|CELERY_TIMEZONE\|enable_utc" settings*.py celery.py`; `python -W error::RuntimeWarning manage.py test` to turn naive-datetime warnings into failures; `ruff` rule set `DTZ` (flake8-datetimez) catches naive constructors; run tests with `TZ=Asia/Karachi`.

## References
Django "Time zones" docs; `zoneinfo` (PEP 615); flake8-datetimez rules DTZ001-DTZ012; Celery `timezone`/`enable_utc`; ISO 8601; CWE-682, CWE-704.
