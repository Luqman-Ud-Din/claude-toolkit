# Python / Django reference for audit-privacy-data-flow-mapper

## Stack markers
`manage.py`, `requirements.txt`/`pyproject.toml` with `Django`; DRF
(`rest_framework`), Celery, `django-redis`, `sentry_sdk`. Flask/FastAPI: same
sections with SQLAlchemy/Pydantic instead of models/serializers.

## Where the relevant code lives
- Storage: `*/models.py` (`models.EmailField`, `CharField`), `*/migrations/*.py`
  (`migrations.AddField('customer', 'email', ...)`), `MEDIA_ROOT` uploads
  (`FileField`/`ImageField`), Celery result backend, `django.contrib.sessions`
  (session data in DB/cache), `LOGGING` file handlers.
- Collection: `views.py` (`request.POST`, `request.data`), DRF serializers
  (`ModelSerializer` with `fields = '__all__'`), `forms.py`, `urls.py` patterns,
  admin forms, management commands importing CSVs.
- Processors: `logging.getLogger(__name__)` calls, `print()`, `cache.set(key, ...)`
  (`django-redis`), `sentry_sdk` (`send_default_pii`), analytics (`segment`, `mixpanel`),
  Celery task args (stored in the broker), `django-import-export` exports, PDF/CSV reports.
- Transmission: `requests.post(...)`, `httpx`, `send_mail`/`EmailMessage` (`EMAIL_BACKEND`
  - SMTP, SES via `django-ses`, SendGrid via `anymail`), Twilio, webhooks.
- Templates: `templates/**/*.html|txt` (email bodies), `{{ user.email }}`.

## Dangerous / interesting APIs and patterns
- `logger.info(f"User {user.email} logged in")`, `logger.info("data=%s", request.data)`.
- `print(request.POST)` in views; `DEBUG=True` error pages with locals (`django.views.debug`)
  - the `sensitive_variables`/`sensitive_post_parameters` decorators absent.
- `cache.set(f"profile:{email}", ...)`; `cache_page` keyed on URLs containing PII.
- `path("users/<str:email>/", ...)`, `request.GET.get("email")`.
- `sentry_sdk.init(send_default_pii=True)`; `sentry_sdk.set_user({"email": ...})`.
- `requests.post("https://api.vendor.com/...", json=model_to_dict(user))`.
- DRF `fields = '__all__'` on a serializer over a model with PII; `depth = n`.
- Celery `task.delay(user.email, ...)` - args persisted in Redis/RabbitMQ; result backend stores return values.
- `ADMINS`/`mail_admins` error emails containing request data (`django.utils.log.AdminEmailHandler` with `include_html=True`).
- `django-axes` / login attempt logs with usernames + IPs (legitimate but inventory it).

## What "good" looks like
```python
logger.info("user %s logged in", user.pk)
cache.set(f"profile:{hashlib.sha256(email.encode()).hexdigest()}", data, timeout=3600)
@sensitive_post_parameters("password", "national_id")
class CustomerSerializer(serializers.ModelSerializer):
    class Meta: model = Customer; fields = ["id", "first_name", "email"]   # explicit
sentry_sdk.init(send_default_pii=False)
```

## Manual trace checklist
1. `LOGGING` dict in settings: handlers (file, syslog, Sentry, Datadog) and formatters; `AdminEmailHandler` contents.
2. `EMAIL_BACKEND` and `ANYMAIL`/`django-ses` settings -> vendor; templates and context variables.
3. Every `requests`/`httpx` call to an external host -> vendor and payload.
4. Celery broker/result backend and task argument contents; `task_ignore_result`.
5. `MEDIA_ROOT`/`DEFAULT_FILE_STORAGE` (S3, GCS) - uploaded documents are a storage location.
6. Session engine (`SESSION_ENGINE`) - what is stored in session data.
7. DRF serializers returning PII to every authenticated user; admin `list_display`.

## Stack-specific false positives
- `DEFAULT_FROM_EMAIL` / `SERVER_EMAIL` - sender addresses.
- `logger.debug` inside `if settings.DEBUG` - still Low.
- Fixtures under `fixtures/*.json` with `example.com`.
- `EmailField` on a `Supplier` model - business contact; note it.

## Tooling
- `python scripts/pii_scan.py <repo> ...`; `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/python-django.json`
- `python manage.py showmigrations` / `sqlmigrate` (if an environment exists) for the schema
- `grep -rn "send_default_pii\|set_user\|requests\.\(post\|get\)" --include=*.py`
- `pip list | grep -i "sentry\|segment\|mixpanel\|twilio\|sendgrid\|anymail"`

## References
GDPR Art.5(1)(c), 5(1)(e), 28, 30, 32; CWE-532, CWE-359, CWE-598; ASVS 8.3, 7.1.1;
Django docs: "Filtering error reports" (`sensitive_variables`), `LOGGING`,
`SESSION_ENGINE`; DRF serializer fields; Sentry Python `send_default_pii`.
