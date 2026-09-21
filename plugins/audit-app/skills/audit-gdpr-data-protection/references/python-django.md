# Python / Django reference for audit-gdpr-data-protection

## Stack markers
`manage.py`, `Django` in requirements; DRF, Celery, `django-redis`, `sentry_sdk`.
Flask/FastAPI: same checks with SQLAlchemy models, Pydantic schemas, APScheduler.

## Where the relevant code lives
- Consent: `models.BooleanField` on `User`/`Profile`/`Customer`; signup forms/serializers; `allauth` signup adapters.
- Rights endpoints: DRF viewset `destroy`/`perform_destroy`, `DeleteView`, `path('users/me/...')`, `export`/`download` views, management commands (`anonymize_user`).
- Retention: Celery beat schedule (`CELERY_BEAT_SCHEDULE`), `@periodic_task`, management commands run by cron (`purge_inactive`), `django-cleanup`.
- Minimisation: `logger.*`, `print`, `LOGGING` handlers, `AdminEmailHandler`, `sentry_sdk.init(send_default_pii=...)`, `request.GET['email']`, DRF `fields='__all__'`.
- Encryption: `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, DB `OPTIONS: {'sslmode': 'require'}`, `django-fernet-fields`/`django-encrypted-model-fields`, `make_password` (PBKDF2/Argon2).
- Audit: `django-auditlog`, `django-simple-history`, `pghistory`, admin `LogEntry` (admin only).
- Breach signals: `user_login_failed` signal handlers, `django-axes` lockouts, `LOGGING` to syslog/Datadog, alert integrations.

## Dangerous / interesting APIs and patterns
- `marketing_consent = models.BooleanField(default=False)` alone; `default=True` (pre-checked).
- `is_deleted = True` soft delete without purge; `on_delete=models.SET_NULL` leaving orphaned PII in related tables.
- `logger.info(f"User {user.email} logged in")`; `print(request.POST)`.
- `sentry_sdk.init(send_default_pii=True)`.
- `DEBUG = True` in production settings (error pages with locals and POST data); missing `@sensitive_post_parameters`.
- `SECURE_SSL_REDIRECT = False`, DB `sslmode` absent/`disable`.
- `fields = '__all__'` on serializers over models with PII.
- Erasure that calls `user.delete()` but not Celery result backend entries, `MEDIA_ROOT` files, session table, third parties.

## What "good" looks like
```python
class Consent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE); purpose = models.CharField(max_length=64)
    policy_version = models.CharField(max_length=32); given_at = models.DateTimeField()
    withdrawn_at = models.DateTimeField(null=True); source = models.CharField(max_length=32)
class MeViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["delete"]) def erase(self, request): erasure.anonymise(request.user); return Response(status=202)
    @action(detail=False, methods=["get"]) def export(self, request): return Response(exporter.for_user(request.user))
CELERY_BEAT_SCHEDULE = {"purge-inactive": {"task": "accounts.tasks.purge_inactive", "schedule": crontab(hour=3)}}
logger.info("user %s logged in", user.pk)
sentry_sdk.init(send_default_pii=False)
SECURE_SSL_REDIRECT = True; DATABASES["default"]["OPTIONS"] = {"sslmode": "require"}
```

## Manual trace checklist
1. Erasure: from the destroy/erase view, follow related models (`on_delete`), files (`FileField.delete`), sessions, Celery results, caches, vendors.
2. Consent: field, writers (form/serializer), readers (mail sends, analytics), withdrawal view.
3. Retention: beat schedule and cron-run management commands vs data category; `LOGGING` rotation.
4. Settings per environment: `DEBUG`, `SECURE_*`, `send_default_pii`, `EMAIL_BACKEND`.
5. DRF serializers returning PII to every authenticated user.

## Stack-specific false positives
- `destroy` on product/order viewsets is not erasure.
- `DEBUG = True` in `settings/dev.py` only: Low; confirm `settings/prod.py`.
- Admin `LogEntry` records admin actions only - not an access trail for PII reads.
- `logger.debug` with PII: still list, rate Low.

## Tooling
- `python scripts/gdpr_check.py <repo> --out ... --md ...`
- `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/python-django.json`
- `python manage.py check --deploy` (if an environment exists) for `SECURE_*`
- `grep -rn "BooleanField\|def destroy\|beat_schedule\|send_default_pii" --include=*.py`

## References
GDPR Art.5, 7, 12-22, 25, 28, 30, 32-35; CWE-532, CWE-359, CWE-312, CWE-319; ASVS 8.3, 7.1, 9.1;
Django deployment checklist; Django "Filtering error reports"; django-auditlog docs.
