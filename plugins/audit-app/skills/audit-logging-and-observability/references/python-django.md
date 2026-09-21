# Python / Django reference for audit-logging-and-observability

## Stack markers

`manage.py`, `settings.py` / `settings/`, `requirements*.txt` / `pyproject.toml`
with `Django`, `djangorestframework`, `flask` or `fastapi`. Loggers: stdlib
`logging` (the `LOGGING` dict in Django settings, `dictConfig` elsewhere),
`structlog`, `loguru`. Correlation: `django-structlog`, `django-guid`,
`asgi-correlation-id`, `django-log-request-id`. Telemetry:
`opentelemetry-distro` / `opentelemetry-instrument`, `sentry-sdk`,
`ddtrace`, `newrelic`, `prometheus-client` / `django-prometheus`.

## Where the relevant code lives

- `settings.py` / `settings/production.py` - `LOGGING` dict (handlers,
  formatters, `loggers`, `root`), `DEBUG`, `MIDDLEWARE` order, `sentry_sdk.init`.
- `*/middleware.py` - request id / correlation middleware, request logging.
- `*/signals.py`, `apps.py` `ready()` - `user_logged_in`, `user_login_failed`,
  `user_logged_out` receivers (security events).
- `views.py`, `viewsets.py`, `api/*.py`, FastAPI `routers/` - the log calls.
- `tasks.py` (Celery), management commands - where the request id is lost.
- `gunicorn.conf.py` / `uvicorn` flags / `Procfile` - access log format, whether
  `opentelemetry-instrument` wraps the process.

## Dangerous / interesting APIs and patterns

- `logger.info(f"login {request.data}")`, `logger.debug("body %s" % request.body)`,
  `logger.info(request.POST)`, `logger.info(serializer.validated_data)` - request
  payloads (passwords, tokens) in the log, and f-strings / `%` / `.format` destroy
  structure and defeat lazy formatting.
- `except Exception as e: logger.debug(...)` / `logger.info(str(e))` /
  `logger.warning(e)` / bare `except: pass` - failures invisible at the default
  WARNING/INFO level and no traceback. Use `logger.exception(...)` (ERROR + traceback).
- `print(` in views, services, tasks - goes to stdout without level, time or id.
- `DEBUG = True` in production settings; `'django.db.backends': {'level': 'DEBUG'}`
  - every SQL statement with parameter values (credentials, PII) is logged.
- `sentry_sdk.init(send_default_pii=True)` or `include_local_variables=True`
  without a `before_send` scrubber - cookies, user email, IP and local variables
  (including passwords) shipped to a third party.
- `request.META` / `request.headers` logged whole (carries `HTTP_AUTHORIZATION`,
  `HTTP_COOKIE`).
- `'handlers': {'file': {'class': 'logging.FileHandler'}}` only - logs die with
  the container; `RotatingFileHandler` without `backupCount` means no retention.
- Absence markers: no `user_login_failed` receiver and no `django-axes`, no
  correlation middleware in `MIDDLEWARE`, no OTel/Sentry init anywhere.

## What "good" looks like

```python
# settings/production.py
LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "log_request_id.filters.RequestIDFilter"},
                "redact": {"()": "core.logging.RedactFilter"}},
    "formatters": {"json": {"()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                            "fmt": "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s"}},
    "handlers": {"stdout": {"class": "logging.StreamHandler", "formatter": "json",
                            "filters": ["request_id", "redact"]}},
    "root": {"handlers": ["stdout"], "level": "INFO"},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}
MIDDLEWARE = ["log_request_id.middleware.RequestIDMiddleware", *MIDDLEWARE]
LOG_REQUEST_ID_HEADER = "HTTP_X_CORRELATION_ID"; GENERATE_REQUEST_ID_IF_NOT_IN_HEADER = True
REQUEST_ID_RESPONSE_HEADER = "X-Correlation-Id"

# accounts/signals.py - security events
@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kw):
    logger.warning("auth.login_failed", extra={"username": credentials.get("username"), "ip": request.META.get("REMOTE_ADDR")})
```

Error path: `except StockError: logger.exception("stock reservation failed order_id=%s", order_id); raise`.
Outbound calls: `requests`/`httpx` session with a hook adding `X-Correlation-Id`, or
`opentelemetry-instrumentation-requests` so `traceparent` propagates. Celery:
pass the id in task headers (`django-guid` Celery integration, `asgi-correlation-id` celery extension).

## Manual trace checklist

1. `MIDDLEWARE`: correlation middleware first; the id appears in the formatter and
   in the response header.
2. Login, logout, password reset, token refresh views: what reaches the logger;
   are `user_login_failed` and permission-denied (DRF `PermissionDenied`
   exception handler) logged?
3. Every `except` in payment/stock/tenant code: `logger.exception` or `logger.error(..., exc_info=True)`, then re-raise or a handled failure.
4. Production settings: `DEBUG`, `django.db.backends` level, root level, handlers.
5. `sentry_sdk.init`: `send_default_pii`, `before_send`, `traces_sample_rate`.
6. Celery tasks and management commands: id bound per task, failures logged at error.

## Stack-specific false positives

- `print(` in `manage.py` commands, migrations, `scripts/`, `tests/`.
- `"password"` inside a constant message (`"password reset email sent"`) with no value argument.
- `logger.debug` in `except` that immediately re-raises; the caller logs it.
- `DEBUG = True` in `settings/local.py` / `settings/dev.py` only - confirm which module production loads (`DJANGO_SETTINGS_MODULE`).
- `logger.info(request.data)` on a route whose serializer has no sensitive fields - read the serializer.

## Tooling

```bash
pip show structlog django-structlog django-guid asgi-correlation-id sentry-sdk opentelemetry-distro
grep -rnE "logger\.(debug|info|warning|error|exception|critical)\(|logging\.(info|debug)\(" --include=*.py .
grep -rnE "print\(" --include=*.py . | grep -v -E "tests?/|migrations/"
grep -rnE "request\.(body|data|POST|META)" --include=*.py . | grep -iE "log|print"
ruff check --select G,LOG,T20 .        # G001-G004 format/concat/f-string in logging, LOG rules, print
```
flake8 equivalents: `flake8-logging-format` (G001-G004, G200 exception
in message), `flake8-print` (T201). Bandit has no logging-PII rule; use Semgrep
`python.lang.security.audit.logging` rules.

## References

- Django docs: Logging, `django.contrib.auth.signals`; DRF exception handling.
- structlog, django-structlog, asgi-correlation-id; OpenTelemetry Python instrumentation.
- Sentry Python: `send_default_pii`, `before_send`.
- CWE-532, CWE-117, CWE-778; ASVS 7.1-7.3; OWASP Logging Cheat Sheet; OWASP A09:2021.
