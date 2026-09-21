# Python / Django (and DRF, Flask, FastAPI) reference for audit-finding-writer

## Stack markers
`manage.py`, `settings.py`, `requirements.txt`/`pyproject.toml` with `django`, `djangorestframework`, `flask`, or `fastapi`.

## Where the relevant code lives
`settings/*.py`, `urls.py`, `views.py`/`viewsets.py`, `serializers.py`, `models.py`, `migrations/`, `tasks.py` (Celery), `middleware.py`.

## Remediation idioms
- Secrets: `os.environ["SECRET_KEY"]` / `django-environ`; `DEBUG = False`, `ALLOWED_HOSTS` explicit, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` in production settings.
- AuthZ: `permission_classes = [IsAuthenticated, IsOwner]` with `has_object_permission`, `get_queryset()` filtered by `request.user` (never `Model.objects.all()` in a per-user view); `@login_required`/`@permission_required`.
- Input: DRF serializers with explicit `fields = [...]` (never `"__all__"` on models with role/price fields), `read_only_fields` for server-set columns.
- Data: ORM querysets with parameters, `.raw()`/`cursor.execute()` only with `%s` params; `select_related`/`prefetch_related` for N+1; `Paginator`/DRF pagination classes; `transaction.atomic()` for multi-write; `select_for_update()` for check-then-act.
- Async/tasks: Celery tasks idempotent with explicit `tenant_id` argument; `requests`/`httpx` with `timeout=`.
- Headers: `SecurityMiddleware` first, `django-csp`, `X_FRAME_OPTIONS = "DENY"`, `CORS_ALLOWED_ORIGINS` explicit, `DATA_UPLOAD_MAX_MEMORY_SIZE`, `django-ratelimit` on login.
- Command/path: `subprocess.run([...])` list form, `shell=False`; `pathlib` + `resolve()` + `is_relative_to()`.
- Multi-tenancy: `django-tenants` schemas or a `TenantManager` default manager filtering by `tenant_id`; tenant from `request.user.tenant`, not the payload.
- Logging: `structlog`/`python-json-logger`, `logging.getLogger(__name__)`, no `logger.info(request.data)`.
- Dates: `USE_TZ = True`, `timezone.now()`, `DateTimeField` (never naive `datetime.now()`), `TIME_ZONE = "UTC"`.

## Recurring references
CWE-798, CWE-89, CWE-78, CWE-22, CWE-502 (pickle/yaml.load), CWE-639, CWE-915, CWE-352, ASVS 4.x, 5.x, 14.x; OWASP A01, A02, A03, A05, A08.

## Stack-specific false positives
`yaml.safe_load`, `csrf_exempt` on a webhook that verifies a signature, `DEBUG = env.bool("DEBUG", False)` reading from env.

## Tooling
`pip-audit`, `safety check`, `bandit -r .`, `semgrep --config p/django`, `python manage.py check --deploy`, `tracemalloc` for leaks.
