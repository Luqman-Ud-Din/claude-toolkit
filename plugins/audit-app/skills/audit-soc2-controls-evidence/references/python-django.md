# Python / Django reference for audit-soc2-controls-evidence

## Stack markers

`manage.py`, `settings.py` or `settings/` package, `requirements*.txt`,
`pyproject.toml`, `Pipfile`. Sub-variants: Django + DRF vs Flask/FastAPI (same
controls, different APIs), session auth vs token/JWT (`djangorestframework-simplejwt`),
local accounts vs OIDC/SAML.

## Where the relevant code lives

- `settings*.py` - `AUTHENTICATION_BACKENDS`, `REST_FRAMEWORK` defaults,
  `AUTH_PASSWORD_VALIDATORS`, `LOGGING`, `DATABASES` (`sslmode`), `SECURE_*`.
- `*/permissions.py`, `*/views.py` - DRF `permission_classes`, `@permission_required`.
- `*/models.py` - `HistoricalRecords`, `unique=True`, `UniqueConstraint`.
- `*/migrations/` - schema changes; `*/management/commands/` - purge jobs.
- `celery.py` / `beat_schedule` - scheduled retention and backup jobs.
- `.github/workflows/`, `Dockerfile`, `docker-compose*.yml`.

## Dangerous / interesting APIs and patterns

- CC6.1 auth: `AUTHENTICATION_BACKENDS` with `mozilla_django_oidc.auth.OIDCAuthenticationBackend`,
  `allauth` social/SAML providers, `djangosaml2`. Local `ModelBackend` only means no SSO.
- MFA: `django_otp` + `OTPMiddleware`, `django-two-factor-auth`, `allauth.mfa`,
  `@otp_required`; absent means IdP-enforced (organisational) or missing.
- CC6.1 rbac: `REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']` (bad: `AllowAny`),
  `IsAdminUser`, `DjangoModelPermissions`, `@permission_required`, `has_perm`,
  `UserPassesTestMixin`. Bad: `permission_classes = []` on admin views.
- Brute force: `django-axes` (`AXES_FAILURE_LIMIT`), DRF throttling.
- CC6.1 admin-log / PI1.3: `django-simple-history` (`HistoricalRecords()`),
  `django-auditlog` (`auditlog.register(Model)`), admin `LogEntry` (covers only
  changes made through Django admin - not API writes).
- CC6.3 deprovisioning: `user.is_active = False`, simplejwt `BLACKLIST_AFTER_ROTATION`
  / `OutstandingToken` blacklisting, `Session.objects.filter(...).delete()`.
- CC7.1: `pip-audit`, `safety check`, `bandit -r`, Dependabot for pip.
- CC7.2: `LOGGING` handlers to a collector (`watchtower` CloudWatch, `logging.handlers.SysLogHandler`,
  OTLP) vs `StreamHandler` only; `user_login_failed` signal receivers.
- A1.1: `django-health-check` (`health_check.db`), `/healthz` view.
- C1: `django-environ` / `os.environ` sourcing from a secret manager (boto3
  `secretsmanager`, `azure-keyvault-secrets`, `hvac`); bad: `SECRET_KEY = '...'`
  literal, `DEBUG = True` in production settings. Field encryption:
  `django-cryptography` `encrypt(models.CharField())`, `django-fernet-fields`, `cryptography.fernet`.
- PI1: DRF serializers `is_valid(raise_exception=True)`, `ModelForm.clean()`,
  pydantic models (FastAPI), `UniqueConstraint`, `select_for_update()`.

## What "good" looks like

```python
AUTHENTICATION_BACKENDS = ["mozilla_django_oidc.auth.OIDCAuthenticationBackend"]
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_RATES": {"anon": "20/min"},
}
SECRET_KEY = env("DJANGO_SECRET_KEY")          # injected from the secret manager
MIDDLEWARE += ["django_otp.middleware.OTPMiddleware", "axes.middleware.AxesMiddleware"]

class Invoice(models.Model):
    number = models.CharField(max_length=32, unique=True)
    history = HistoricalRecords()
```

Pipeline shape: `pip install -r requirements.txt` -> `pytest` -> `pip-audit -r
requirements.txt` and `bandit -r app -ll` -> image build -> `python manage.py
migrate --noinput` in the deploy job for a protected environment ->
`python manage.py check --deploy` as a gate.

## Manual trace checklist

1. `settings` for production: `DEBUG`, `ALLOWED_HOSTS`, `SECRET_KEY` source,
   default permission classes, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`.
2. Staff/admin endpoints and Django admin exposure (URL, MFA, IP restriction).
3. History/audit coverage for user, role and money models - including API writes.
4. Deactivation blacklists outstanding tokens and deletes sessions.
5. CI: `pip-audit`/`safety` and `bandit` present and failing; tests required.
6. PostgreSQL backups (RDS/Cloud SQL retention in IaC or `pg_dump` cron) and a dated
   restore-test record; `django-dbbackup` configuration if used.

## Stack-specific false positives

- `DEBUG = True` and literal `SECRET_KEY` in `settings/dev.py` or `local.py`.
- `AllowAny` on login, registration, password reset and health views.
- `StreamHandler` logging in containers with a platform log shipper (partial).
- `LogEntry` hits - evidence only for admin-site changes; do not over-credit.

## Tooling

```bash
pip-audit -r requirements.txt
safety check -r requirements.txt
bandit -r . -x tests -ll
python manage.py check --deploy
grep -rnE "AUTHENTICATION_BACKENDS|DEFAULT_PERMISSION_CLASSES|HistoricalRecords|auditlog\.register|django_otp" .
```

## References

- Django deployment checklist; DRF permissions; django-axes, django-otp, simple-history docs.
- OWASP Django cheat sheet.
- SOC2-CC6.1, CC6.3, CC7.1, CC7.2, CC8.1, A1.2, C1.1, PI1.1, PI1.3; CWE-284, CWE-307.
