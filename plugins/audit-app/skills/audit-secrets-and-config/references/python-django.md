# Python / Django reference for audit-secrets-and-config

## Stack markers
`manage.py`, `settings.py` (or a `settings/` package), `.env`, `requirements.txt`/`pyproject.toml`.

## Where the relevant code lives
`settings.py`/`settings/*.py` (`SECRET_KEY`, `DATABASES`, `DEBUG`, `ALLOWED_HOSTS`, CORS, security middleware), `.env` files, `Dockerfile`/compose (`DJANGO_SETTINGS_MODULE`).

## Dangerous / interesting keys and patterns
- Secrets: `SECRET_KEY = '...'` literal, `DATABASES[...]['PASSWORD'] = '...'`, DB URLs with credentials, `*_API_KEY`. Use `os.environ`/`django-environ`/a secret manager.
- Debug/prod: `DEBUG = True` (leaks stack traces and settings), `ALLOWED_HOSTS = ['*']`, missing `SECURE_SSL_REDIRECT`/`SECURE_HSTS_SECONDS`/`SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`.
- Settings module: confirm the prod deploy points `DJANGO_SETTINGS_MODULE` at the production settings.
- CORS (`django-cors-headers`): `CORS_ORIGIN_ALLOW_ALL = True` / `CORS_ALLOW_ALL_ORIGINS = True` together with `CORS_ALLOW_CREDENTIALS = True`.

## What "good" looks like
```python
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]     # never a literal
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"   # False in prod
DATABASES["default"]["PASSWORD"] = os.environ["DB_PASSWORD"]
CORS_ALLOWED_ORIGINS = ["https://app.example.com"]   # explicit; not ALLOW_ALL with credentials
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
```

## Manual trace checklist
1. `SECRET_KEY`, DB password - literal or from env?
2. Production settings: `DEBUG = False`, `ALLOWED_HOSTS` explicit, HTTPS/HSTS/secure-cookie flags on.
3. CORS allow-all + credentials?
4. `python manage.py check --deploy` mirrors many of these.
5. `git_secret_scan.py` over history.

## Stack-specific false positives
`DEBUG = True` in a `settings/dev.py` never used in prod; `SECRET_KEY` read via `env()` with a dev default that is overridden in prod (confirm the override); `.env.example` placeholders.

## Tooling
`python manage.py check --deploy`, `django-environ`, `bandit`, plus `references/tool-candidates.md`. Scripts: `git_secret_scan.py`, `config_key_inventory.py`.

## References
CWE-798, CWE-321, CWE-489, CWE-942, CWE-16. ASVS 2.10, 14.1, 14.4/14.5. OWASP A05:2021, A02:2021.
