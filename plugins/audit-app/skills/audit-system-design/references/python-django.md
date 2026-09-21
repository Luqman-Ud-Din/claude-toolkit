# Python / Django (also Flask, FastAPI) reference for audit-system-design

## Stack markers
`manage.py`, `settings.py` with `INSTALLED_APPS`; `requirements.txt`/`pyproject.toml` with `django`, `celery`, `channels`, `djangorestframework`. Flask/FastAPI: `app = Flask(...)`/`FastAPI()`, blueprints/routers as modules. Async work: Celery (RabbitMQ/Redis broker), RQ, Dramatiq, Huey, `django-q`; schedulers: `celery beat`, `django-crontab`, APScheduler. Resilience: `tenacity`, `httpx` timeouts, `pybreaker`.

## Where the architecture is visible
- `INSTALLED_APPS`: the module list; imports between app packages = the module graph (`module_graph.py`). Naming: `api/`/`views` (presentation), `services/`/`use_cases/` (application), `domain/`/`models.py` (domain), `infrastructure/`/`adapters/`/`integrations/` (infrastructure), `core/`/`common/`/`utils/` (shared).
- `settings.py`: `DATABASES` (one DB? `DATABASE_ROUTERS` for read replicas or per-app DBs), `CACHES` (locmem = per-process, redis/memcached = shared), `SESSION_ENGINE`, `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`, `CHANNEL_LAYERS` (in-memory vs redis), `MEDIA_ROOT` (local disk), `STORAGES`, external service URLs/keys names.
- `celery.py`, `tasks.py` (`@shared_task`, `@app.task(bind=True, autoretry_for=..., retry_backoff=True, acks_late=True)`) - async edges and their retry policy; `beat_schedule` - scheduled work.
- `urls.py` hierarchy and DRF routers - HTTP surface; middleware order (`AuthenticationMiddleware`, tenant middleware) - where identity is set.
- `docker-compose*.yml`, `Procfile`, `k8s/`, `gunicorn.conf.py` (`workers`, `preload_app`) - runtime units and replicas.
- `django-tenants`/`django-tenant-schemas` (`TENANT_MODEL`, schema-per-tenant) or custom tenant middleware using `threading.local()` - tenancy architecture.

## Design smells to grep (mirrored in `scripts/patterns/python-django.json`)
- Module-level mutable globals (`_cache = {}`, `CURRENT_TENANT = None`), `threading.local()` tenant/user without cleanup in middleware `finally`, `settings` mutated at runtime.
- `CACHES` `LocMemCache` or `SESSION_ENGINE` `cache`/`file` in production settings; `CHANNEL_LAYERS` `InMemoryChannelLayer`; `MEDIA_ROOT` on local disk with multiple replicas.
- `requests.get/post` without `timeout=`; `httpx` without `timeout`; no `tenacity`/`pybreaker` on external calls; `time.sleep` retry loops; bare `except Exception: pass` around integrations.
- Views importing models from other apps and writing them (`OtherApp.objects.create` from `orders/views.py`); cross-app imports both ways (cycle); `domain`/`models` importing `requests`/`boto3`/`views`.
- `.delay()`/`apply_async()` inside `transaction.atomic()` before commit (task may run before the row exists) - use `transaction.on_commit`; DB write + external POST in one view without outbox/saga.
- Celery tasks without `acks_late`/`autoretry_for`/`max_retries`, without idempotency keys; results stored in DB backend on hot paths; one worker queue for everything (no bulkheads: `-Q default` only).
- `celery beat` started in every replica (duplicate schedules) without `django-celery-beat` single-scheduler discipline or a lock.
- Long CPU/IO work in request handlers (report generation, PDF) instead of tasks; `gunicorn` sync workers with few processes and long external calls.
- `ALLOWED_HOSTS = ['*']`, internal admin/`/internal/` URLs without auth, service ports published in compose bypassing the proxy (delegate specifics; keep the boundary).
- God modules: `utils.py`/`helpers.py` > 1000 lines, `core` app importing everything.
- Signals (`post_save`) doing cross-app side effects and external calls - hidden coupling.

## What "good" looks like
```python
# settings.py (prod)
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("REDIS_URL")}}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
CHANNEL_LAYERS = {"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [env("REDIS_URL")]}}}
STORAGES = {"default": {"BACKEND": "storages.backends.s3.S3Storage"}}

# services/fbr.py - outbound edge
@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(), retry=retry_if_exception_type(httpx.TransportError))
def submit_invoice(inv):  # wrapped by a pybreaker.CircuitBreaker
    return client.post("/invoice", json=inv, timeout=httpx.Timeout(10.0))

# views.py - dual write avoided
with transaction.atomic():
    sale = Sale.objects.create(...)
    OutboxEvent.objects.create(type="SaleCreated", payload=...)
transaction.on_commit(lambda: relay_outbox.delay())

# tasks.py
@shared_task(bind=True, acks_late=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def sync_stock(self, sale_id):  # idempotent: checks Sale.stock_synced before acting
```
Layering: `domain` packages import only stdlib and each other; adapters import the domain; views import services.

## Manual trace checklist
1. Reverse proxy -> Django/ASGI processes -> `DATABASES`: draw; routers, replicas.
2. Tenant resolution: middleware sets and clears context; Celery tasks receive the tenant explicitly.
3. Every outbound call: timeout, retry, breaker, fallback.
4. Celery: broker replicas and persistence, `acks_late`, retries, idempotency, dead-letter (`task_reject_on_worker_lost`), beat single instance.
5. Process state: cache/session/channels/media vs replicas.
6. Where auth middleware and DRF permission classes sit; internal URLs.
7. ADR/README claims vs the above.

## Stack-specific false positives
- Module-level constants and compiled regexes; `functools.lru_cache` on pure functions.
- `LocMemCache` in `settings/dev.py` only.
- `requests` without timeout in management commands run by hand (still note).
- `core` app with abstract models/mixins only having high fan-in.

## Tooling
- `pydeps <package> --show-cycles`, `import-linter` (`.importlinter` contracts for layers), `pylint --disable=all --enable=cyclic-import`.
- `python manage.py show_urls` (django-extensions), `celery -A proj inspect registered` (read-only on a live worker), `celery -A proj inspect active_queues`.
- `docker compose config`.

## References
- Django docs (Caching, Sessions, Channels, Databases/multi-db), Celery docs (Task retries, acks_late, Beat), "Transactional outbox", import-linter docs.
- ASVS 1.x, CWE-306, CWE-362, CWE-770.
