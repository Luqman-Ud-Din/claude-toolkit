# Python / Django (and FastAPI, Flask) reference for audit-infra-and-deployment

## Stack markers
- `manage.py`, `settings.py` or `settings/{base,prod}.py`, `wsgi.py` / `asgi.py`; `requirements*.txt`, `pyproject.toml` (+ `uv.lock`, `poetry.lock`), `Pipfile`.
- FastAPI and Flask use the same container and server guidance below (`main.py` with `FastAPI()`, `app = Flask(__name__)`).
- Deployment markers: `Dockerfile`, `Procfile` (`web: gunicorn ...`), `gunicorn.conf.py`, `uwsgi.ini`, `celery` workers, `zappa_settings.json`, Kubernetes/Helm.

## Where the relevant code lives
- `Dockerfile`, `docker-compose*.yml`, and `entrypoint.sh`, which often runs `migrate` and `collectstatic` on every start.
- `settings` modules: `DEBUG`, `ALLOWED_HOSTS`, `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, `CSRF_TRUSTED_ORIGINS`, `STATIC_ROOT`, database and cache URLs.
- `celery.py` and `beat` schedules: the worker and scheduler deployments.

## Dangerous / interesting APIs and patterns
Images:
- `FROM python:3.12` (full image) as the runtime. Prefer `python:3.12-slim-bookworm`; alpine often breaks wheels for psycopg or numpy and gains little.
- Compilers in the runtime image, e.g. `apt-get install build-essential gcc libpq-dev` in the final stage. Build wheels in a builder stage (`pip wheel --wheel-dir /wheels -r requirements.txt`), then install from `/wheels` in a runtime stage that only has `libpq5`.
- `pip install` without `--no-cache-dir` (DL3042); `apt-get install` without `--no-install-recommends` and `rm -rf /var/lib/apt/lists/*`.
- No `USER`. Add `RUN useradd --system --uid 10001 --no-create-home app` and `USER 10001`; a numeric uid lets Kubernetes `runAsNonRoot` verify it.
- Missing `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1`: logs are buffered and `.pyc` files are written to what should be a read-only root filesystem.

Servers:
- `python manage.py runserver 0.0.0.0:8000`, `flask run`, or `uvicorn main:app --reload` in a Dockerfile, compose file or manifest used for production. These are dev servers.
- Good: `gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 30`. For ASGI: `gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker`, or `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers` with `--forwarded-allow-ips` restricted to the proxy.
- Size the worker count to the CPU limit, not the node. `multiprocessing.cpu_count()` sees all node CPUs.

Settings that depend on deployment:
- `DEBUG = True`, or `DEBUG = os.environ.get("DEBUG", True)`.
- TLS terminated upstream without `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`: `SECURE_SSL_REDIRECT` loops, `request.is_secure()` is false, and CSRF origin checks fail.
- A literal `SECRET_KEY` in settings, `ENV DJANGO_SECRET_KEY=...` in the Dockerfile, or a DB password in `docker-compose.yml`.

Release steps:
- `python manage.py migrate` in `entrypoint.sh` runs on every replica. Run it once instead, as a Kubernetes Job, Helm hook or pipeline step. Django migrations can be reversed (`migrate app 0041`) only if every migration has a reverse. Look for `RunPython` without a reverse function and `RunSQL` without `reverse_sql`.
- Run `collectstatic` at image build time (`RUN python manage.py collectstatic --noinput` with a dummy settings env) and serve the files with WhiteNoise or nginx/CDN.
- Celery beat running in more than one replica duplicates scheduled jobs.

Backups:
- `pg_dump -Fc` CronJobs, `django-dbbackup` (`dbbackup`/`dbrestore`), or managed-DB automated backups. Media files (`MEDIA_ROOT`) on a volume or bucket need their own backup.

## What "good" looks like
```dockerfile
FROM python:3.12-slim-bookworm@sha256:<digest> AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim-bookworm@sha256:<digest>
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --no-create-home app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
WORKDIR /app
COPY --chown=app:app . .
USER 10001
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
```

## Manual trace checklist
1. The process started in production (gunicorn/uvicorn, not runserver or `--reload`) and its worker count against the CPU limit.
2. `DEBUG`, `ALLOWED_HOSTS` and `SECURE_PROXY_SSL_HEADER` as they resolve in the production environment.
3. Where `SECRET_KEY` and DB credentials come from at runtime.
4. Where migrations run, and whether the last few can be reversed (rollback path).
5. A health endpoint (`django-health-check`, or a `/healthz` view) behind the probes; readiness checks DB and cache.
6. Celery worker/beat deployments: limits, replicas, and graceful shutdown (`terminationGracePeriodSeconds` longer than task timeouts).
7. Backups for both the database and user-uploaded media, and the date of the last restore.

## Stack-specific false positives
- `runserver` in `docker-compose.override.yml` or a `dev` compose profile.
- `build-essential` in a builder stage.
- `DEBUG=True` in `settings/dev.py` or `local.py` that production never imports. Confirm via `DJANGO_SETTINGS_MODULE`.

## Tooling
- `python manage.py check --deploy --settings=config.settings.prod`.
- `python manage.py showmigrations`, `python manage.py sqlmigrate app 0042 --backwards`.
- `hadolint Dockerfile` (DL3008/DL3013/DL3042), `trivy config .`, `checkov -d .`.

## References
- Django "Deployment checklist" and "How to deploy with WSGI/ASGI"; Gunicorn "Deploying"; Uvicorn "Deployment" (proxy headers).
- CIS Docker Benchmark 4.1/4.3; CWE-489 (debug), CWE-250, CWE-798.
