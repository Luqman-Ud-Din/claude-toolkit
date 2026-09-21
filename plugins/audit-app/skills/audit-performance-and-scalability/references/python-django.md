# Python / Django (also Flask, FastAPI) reference for audit-performance-and-scalability

## Stack markers
`manage.py`, `django`/`flask`/`fastapi` in requirements. Process model decides everything: gunicorn sync workers (one request per worker - blocking is per worker, concurrency = workers), gevent/uvicorn async (blocking calls stall the loop), Celery for background. Horizontal scaling: more processes/containers; anything in process memory is per worker.

## Where the relevant code lives
`settings.py` (`CACHES`, `SESSION_ENGINE`, `MIDDLEWARE` order incl. `GZipMiddleware`, `DATABASES.CONN_MAX_AGE`, `DEFAULT_FILE_STORAGE`), `gunicorn.conf.py`/Procfile (workers, worker class, timeout), `views.py`/`api/*.py` (sequential calls, inline work), `services/*.py`, `clients/*.py` (`requests` sessions), `tasks.py` (Celery), `urls.py`.

## Dangerous / interesting APIs and patterns
- BLOCK: `requests.get` / `time.sleep` / `subprocess.run` / heavy `pandas` inside `async def` views (FastAPI/ASGI) - stalls the loop; in sync Django it stalls the worker (fine only if workers are many); CPU-heavy work (PDF via `weasyprint`, image via `PIL`, `openpyxl`) in views; `run_in_executor` absent.
- SEQ: consecutive `requests.get(...)` / `client.x()` / `httpx` calls with independent inputs -> `ThreadPoolExecutor` / `asyncio.gather` / `httpx.AsyncClient`; loops calling a remote per item.
- CACHE: `CACHES` unset (defaults to `LocMemCache`, per worker) or absent; no `cache_page`/`cache.get_or_set` on reference data; `@cache_page` without `key_prefix` per tenant; no `Cache-Control` (`@cache_control`, `ConditionalGetMiddleware` for ETags); no invalidation (`cache.delete`) in write views/signals; DRF without `ETag` support (`drf-extensions`).
- COMPRESS: `django.middleware.gzip.GZipMiddleware` missing from `MIDDLEWARE` (and nginx `gzip` not confirmed); FastAPI without `GZipMiddleware`; Flask without `flask-compress`.
- PAYLOAD: `ModelSerializer` with `fields = '__all__'` and nested serializers; `depth = n`; `JsonResponse(list(qs.values()))` of whole tables; base64 images; `.all()` serialised.
- CHATTY: per-row detail endpoints used in loops by the client; dashboard with one endpoint per counter.
- POOL: `CONN_MAX_AGE` 0 (default - new DB connection per request; set 60-600 or use `pgbouncer`); `CONN_HEALTH_CHECKS`; gunicorn `workers` vs DB `max_connections` (workers x instances x threads); `requests` without a `Session` (new TCP per call); `httpx` limits.
- TIMEOUT: `requests.get(url)` with no `timeout=` (blocks forever); `httpx.Client()` default 5 s (OK, but verify); no retry/backoff (`urllib3.Retry`, `tenacity`) or breaker (`pybreaker`); gunicorn `--timeout` 30 s default killing long reports (symptom, not fix); `statement_timeout` absent for reports.
- ALLOC: `list(qs)` of big sets, `json.dumps` of large graphs, `str +=` in loops, `re.compile` per call, `pandas.DataFrame` per request, template rendering of 10k rows.
- INLINE-BG: `send_mail`, PDF/Excel generation, third-party submissions, image processing in views instead of Celery/RQ/Django-Q (`.delay()`); `threading.Thread(...).start()` as the fix (lost on restart, no retry).
- STATE: `SESSION_ENGINE` = `django.contrib.sessions.backends.file` or `signed_cookies` with large payloads, or `cache` backed by `LocMemCache` (per worker -> logouts across instances); `LocMemCache` for anything shared; `DEFAULT_FILE_STORAGE` = local `FileSystemStorage` for user uploads (not shared across instances); module-level dict caches; `celery beat` on every instance; `django-ratelimit` with `LocMemCache`.

## What "good" looks like
```python
MIDDLEWARE = ["django.middleware.gzip.GZipMiddleware", "django.middleware.http.ConditionalGetMiddleware", ...]
CACHES = {"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": env("REDIS_URL"), "TIMEOUT": 300}}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"; SESSION_CACHE_ALIAS = "default"
DATABASES["default"]["CONN_MAX_AGE"] = 300
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

session = requests.Session(); session.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.3)))
with ThreadPoolExecutor(max_workers=3) as ex:
    customer, quote, tax = ex.map(lambda f: f(), [lambda: customers.get(id), lambda: pricing.quote(items), lambda: tax.rate(region)])
rates = cache.get_or_set(f"tax:{region}", lambda: tax.rate(region), 60 * 60 * 24)
submit_invoice.delay(order.id)                                            # Celery, not inline
```
`gunicorn -w $((2*CPU+1)) -k gthread --threads 4 --timeout 30 --keep-alive 65`.

## Manual trace checklist
1. `settings.py`: middleware (gzip, conditional get), CACHES backend, SESSION_ENGINE, CONN_MAX_AGE, file storage - each a yes/no for the scaling table.
2. Landing/main list view + serializer: sequential remote calls, serializer width/depth, queryset materialisation.
3. Save/checkout view: remote calls (timeouts? parallel?), inline mail/PDF/third-party.
4. Every `requests`/`httpx` call site: `timeout=`, session reuse, retry.
5. Process model: gunicorn workers/threads vs DB connections; async views with sync calls inside.
6. Celery: beat singleton? task time limits? result backend?

## Stack-specific false positives
- `requests.get` in management commands/tests without timeout - Low.
- `LocMemCache` for a single-process internal tool - Low with constraint noted.
- Sequential calls where the second uses the first's result.
- `FileSystemStorage` pointing at a mounted shared volume (NFS/EFS) - verify, then not a blocker.

## Tooling
- `django-silk` (per-request time, query count), `django-debug-toolbar` (staging), `py-spy top --pid <pid>` / `py-spy record -o prof.svg` during load, `scalene`.
- `gunicorn --statsd-host` or `prometheus_client` (`django-prometheus`: request latency histograms per view).
- `locust` for load; `nplusone`/`assertNumQueries` for query counts (delegated skill).
- Static: `ruff` `ASYNC` rules (blocking calls in async functions: ASYNC100/ASYNC210), `bandit` B113 (requests without timeout).

## References
CWE-400, CWE-1050, CWE-1088, CWE-1072; Django docs "Performance and optimization", "Cache framework", "Sessions - using cached sessions", "Persistent connections"; gunicorn "Design - how many workers"; Celery "Tasks - best practices".
