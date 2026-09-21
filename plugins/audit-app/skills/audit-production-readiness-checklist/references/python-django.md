# Python / Django (also Flask, FastAPI) reference for audit-production-readiness-checklist

## Stack markers
`manage.py`, `settings.py` or `settings/{base,dev,prod}.py`, `requirements*.txt`/`pyproject.toml`, `gunicorn.conf.py`/`uvicorn` command in Dockerfile, `celery.py`. Flask/FastAPI: `app.py`/`main.py`, `config.py`.

## Where each checklist item lives
- **Env config:** `DJANGO_SETTINGS_MODULE` set per environment (Dockerfile/compose/CI), `settings/prod.py` reading `os.environ`/`django-environ`/`pydantic-settings`; `.env.example` committed, `.env` ignored. Fail: single `settings.py` with `DEBUG = True` and production hosts, or `.env.production` committed with values.
- **Secrets:** `SECRET_KEY = 'django-insecure-...'` or any literal, `DATABASES['default']['PASSWORD']` literal, `AWS_SECRET_ACCESS_KEY`, `EMAIL_HOST_PASSWORD`, `CELERY_BROKER_URL='amqp://user:pass@host'` literals in settings; Flask `app.config['SECRET_KEY'] = '...'`.
- **Debug off:** `DEBUG = True` in the production settings module; `ALLOWED_HOSTS = ['*']`; `django-debug-toolbar` in `INSTALLED_APPS` unconditionally; `TEMPLATE_DEBUG`; DRF browsable API enabled in prod (`DEFAULT_RENDERER_CLASSES` includes `BrowsableAPIRenderer`); `LOGGING` root at `DEBUG`; Flask `app.run(debug=True)`; FastAPI `debug=True`, `/docs` unauthenticated in prod (Medium).
- **Health checks:** `django-health-check` (`health_check`, `health_check.db`, `health_check.cache`, `health_check.contrib.celery`, `health_check.contrib.rabbitmq`, `health_check.contrib.redis` in `INSTALLED_APPS`, `path('health/', include('health_check.urls'))`), or a custom view that runs `connection.cursor().execute('SELECT 1')` and `cache.set/get`; FastAPI `/healthz` with DB ping; excluded from auth middleware and `ALLOWED_HOSTS` allows the probe host (`HEALTHCHECK`/k8s use the pod IP - common failure). Probes must target it.
- **Graceful shutdown:** gunicorn `--graceful-timeout` (default 30 s) and `timeout`; uvicorn `--timeout-graceful-shutdown`; Celery `worker_prefetch_multiplier`, `acks_late`, `task_reject_on_worker_lost`, `--soft-time-limit`; k8s `terminationGracePeriodSeconds` >= graceful timeout. Fail: gunicorn `--timeout 0` or workers killed mid-task without `acks_late`.
- **Timeouts/retries:** `requests.*(timeout=...)` everywhere (no default timeout in `requests`), `httpx.Timeout`, `tenacity` retries on idempotent calls, `pybreaker`; `DATABASES['default']['OPTIONS']['connect_timeout']`/`statement_timeout`; `CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP`, `broker_connection_max_retries`; Celery task `autoretry_for`, `retry_backoff`.
- **Caching:** `CACHES` backend (`RedisCache`/`Memcached` vs `LocMemCache`), `CACHE_MIDDLEWARE_*`, `@cache_page`, `django-cachalot`; strategy documented? `LocMemCache` behind >1 replica for authoritative data = fail.
- **Load test:** `locustfile.py`, `k6/`, `*.jmx`, `docs/perf*`.
- **Feature flags:** `django-waffle` (`waffle.flag_is_active`), `django-flags`, `unleash-client`, `ldclient`, `flagsmith`, `growthbook`; settings `FEATURES = {...}` with documented switches.
- **Runbook / rollback / launch checklist:** docs; deploy pipeline with rollback (`helm rollback`, `kubectl rollout undo`, `heroku releases:rollback`); `migrate <app> <previous>` documented; migrations reversible (`audit-db-schema`).
- **Alerting:** Prometheus rules (`django-prometheus`), Sentry alert rules, Datadog monitors in IaC.

## What "good" looks like
```python
# settings/prod.py
DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
SECRET_KEY = env("SECRET_KEY")
DATABASES = {"default": env.db("DATABASE_URL", engine="django.db.backends.postgresql")}
DATABASES["default"]["OPTIONS"] = {"connect_timeout": 5, "options": "-c statement_timeout=30000"}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("REDIS_URL")}}
INSTALLED_APPS += ["health_check", "health_check.db", "health_check.cache", "health_check.contrib.celery_ping", "health_check.contrib.rabbitmq"]
# urls.py
path("health/", include("health_check.urls")),   # excluded from auth middleware
# gunicorn.conf.py
workers = 4; timeout = 60; graceful_timeout = 30; preload_app = True
# services/fbr.py
resp = session.post(url, json=payload, timeout=(3.05, 10))
```
Dockerfile: `ENV DJANGO_SETTINGS_MODULE=config.settings.prod`, `CMD ["gunicorn", "-c", "gunicorn.conf.py", "config.wsgi"]`, `HEALTHCHECK CMD curl -f http://localhost:8000/health/ || exit 1`.

## Manual trace checklist
1. Dockerfile/compose: `DJANGO_SETTINGS_MODULE`; which settings module is production; literals in it; `DEBUG` value there.
2. Health URL: in `urls.py`, outside auth, `ALLOWED_HOSTS` compatible with probes; readiness touches DB/cache/broker; probes target it.
3. Every `requests`/`httpx` call: timeout; Celery task retry config.
4. gunicorn/uvicorn graceful timeout vs orchestrator grace period; Celery `acks_late`.
5. Pipeline rollback step; last migration reversible.

## Stack-specific false positives
- `settings/dev.py`/`local.py` with `DEBUG = True` and local passwords.
- `ALLOWED_HOSTS = ['*']` behind a reverse proxy that validates Host (note, Low).
- `django-insecure-` key in `settings/dev.py` only.
- `/docs` (FastAPI) in prod behind auth or IP allow-list.

## Tooling
- `python manage.py check --deploy --settings=config.settings.prod` (read-only) lists debug/security misconfigurations.
- `python manage.py diffsettings --settings=...`; `curl localhost:8000/health/?format=json`.
- `pip list | grep -i "health\|waffle\|tenacity\|locust"`.

## References
- Django deployment checklist (`check --deploy`), django-health-check docs, gunicorn settings (graceful_timeout), Celery "Workers guide" (shutdown), Twelve-Factor config.
- CWE-798, CWE-489, CWE-215, ASVS 14.x, OWASP A05:2021.
