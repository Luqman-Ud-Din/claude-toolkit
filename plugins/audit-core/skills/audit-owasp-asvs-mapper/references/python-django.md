# Python / Django (and Flask, FastAPI) reference for audit-owasp-asvs-mapper

Django ships more ASVS controls enabled by default than any other stack here; the risk
is settings that switch them off. Flask/FastAPI provide almost none by default, so treat
them like Node/Express (evidence must be visible in code).

## Stack markers
`manage.py`, `settings.py` / `settings/*.py`, `requirements.txt` or `pyproject.toml` with
`django`, `djangorestframework`, `flask`, `fastapi`. Variants: Django templates vs DRF
JSON API; session auth vs token/JWT (`djangorestframework-simplejwt`).

## Where the relevant code lives
- `settings.py`: `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `MIDDLEWARE`, `SECURE_*`, `SESSION_COOKIE_*`,
  `CSRF_COOKIE_*`, `CORS_*` (django-cors-headers), `REST_FRAMEWORK` defaults, `LOGGING`.
- Views/viewsets: `permission_classes`, `get_queryset()` (ownership filter), `@login_required`.
- ORM: `.raw()`, `.extra()`, `cursor.execute()` with `%` formatting, `RawSQL`.
- Templates: `|safe`, `mark_safe`, `{% autoescape off %}`, `format_html` misuse.
- Flask/FastAPI: `app.py`/`main.py` middleware, `Depends()` auth, `flask-talisman`, `CORSMiddleware`.

## Django controls satisfied by default (confirm the setting was not changed)
| ASVS | Django default | Fails when |
|---|---|---|
| 4.2.2 CSRF | `CsrfViewMiddleware` in `MIDDLEWARE`; DRF enforces it for SessionAuthentication | `@csrf_exempt`, middleware removed; N/A for pure token auth |
| 5.3.3 output encoding | Template autoescape on | `|safe`, `mark_safe(user_input)`, `autoescape off` |
| 5.3.4 parameterized queries | ORM and `.raw(sql, params)` | `cursor.execute("..." % x)`, f-string SQL, `.extra(where=[...])` |
| 14.4.7 clickjacking | `XFrameOptionsMiddleware` -> `DENY` | Middleware removed, `@xframe_options_exempt` |
| 14.4.4 nosniff | `SECURE_CONTENT_TYPE_NOSNIFF = True` (default since 3.0) | Set to False |
| 14.4.6 referrer | `SECURE_REFERRER_POLICY = 'same-origin'` (default since 3.1) | Set to None |
| 2.4.1 password storage | PBKDF2-SHA256 hasher, Argon2 optional | `UnsaltedMD5PasswordHasher` in `PASSWORD_HASHERS` |
| 2.1.1 password length | `MinimumLengthValidator` (8 by default; ASVS wants 12) | `AUTH_PASSWORD_VALIDATORS = []` |
| 3.4.2 HttpOnly | `SESSION_COOKIE_HTTPONLY = True` | Set to False |
| 3.2.1 session rotation | `login()` rotates the session key | Custom login bypassing `django.contrib.auth.login` |
| 5.1.2 mass assignment | `ModelForm`/serializer `fields = [...]` | `fields = '__all__'` on a model with role/owner columns |
| 7.4.1 generic error | `DEBUG = False` gives generic 500 | `DEBUG = True` in production settings |

## Controls that always need explicit settings or code
- 14.4.5 HSTS: `SECURE_HSTS_SECONDS = 31536000`, `SECURE_HSTS_INCLUDE_SUBDOMAINS = True` (default 0 = Failed unless the proxy sets it).
- 9.1.1 TLS: `SECURE_SSL_REDIRECT = True`, `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`.
- 14.4.3 CSP: `django-csp` middleware and `CSP_DEFAULT_SRC`; not present by default.
- 14.5.3 CORS: `CORS_ALLOW_ALL_ORIGINS = True` with `CORS_ALLOW_CREDENTIALS = True` fails.
- 4.1.1 / 4.2.1: DRF `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` and `get_queryset()` filtered by `request.user`; `AllowAny` on a viewset fails 4.1.1.
- 2.10.4 / 6.4.1: `SECRET_KEY` and DB password from `os.environ` / `django-environ`, not literals.
- 14.3.2: `DEBUG = False`, `ALLOWED_HOSTS` not `['*']`.
- 7.1.1: `LOGGING` filters do not dump `request.POST`; `sensitive_post_parameters` decorator on login views.
- 12.1.1: `DATA_UPLOAD_MAX_MEMORY_SIZE`, `FILE_UPLOAD_MAX_MEMORY_SIZE` set.

## What "good" looks like
```python
# settings/production.py
DEBUG = False                                 # ASVS 14.3.2
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]  # 2.10.4
SECURE_HSTS_SECONDS = 31536000                # 14.4.5
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True                    # 9.1.1
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True   # 3.4.1
REST_FRAMEWORK = {"DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"]}  # 4.1.1

class OrderViewSet(ModelViewSet):
    def get_queryset(self):
        return Order.objects.filter(owner=self.request.user)   # 4.2.1
```

## Manual trace checklist
1. Run `python manage.py check --deploy` and copy the output into `audit/evidence/` (covers 14.3.2, 14.4.x, 3.4.x, 9.1.1).
2. Every viewset's `permission_classes` and `get_queryset` (V4.1, V4.2).
3. All `|safe` / `mark_safe` call sites (V5.3.3).
4. All `.raw(` / `cursor.execute(` call sites (V5.3.4).
5. Settings module actually used in production (`DJANGO_SETTINGS_MODULE` in the Dockerfile).

## Stack-specific false positives
- `@csrf_exempt` on a webhook endpoint that verifies an HMAC signature is fine (document the check).
- `mark_safe` on a constant string is fine; only user-derived input fails 5.3.3.
- `SECURE_HSTS_SECONDS = 0` when nginx/ingress sets HSTS: cite that config; Not assessed if it is not in the repo.

## Tooling
- `python manage.py check --deploy` (settings-level ASVS evidence).
- `bandit -r . -f json` (test ids carry CWE: B608 = CWE-89, B105 = CWE-259, B301 = CWE-502).
- `pip-audit` / `safety check` (V14.2.1).

## References
- Django "Deployment checklist" and "Security in Django"; DRF permissions docs.
- ASVS 4.0.3 V2.1, V3.4, V4, V5.3, V14.3, V14.4; CWE-79, CWE-89, CWE-352, CWE-639, CWE-798.
