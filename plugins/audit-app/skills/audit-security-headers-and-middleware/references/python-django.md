# Python / Django (also Flask, FastAPI) reference for audit-security-headers-and-middleware

## Stack markers
`manage.py`, `settings.py`/`settings/*.py` (`MIDDLEWARE` list is the pipeline), `requirements.txt` with `django`, `djangorestframework`, `django-cors-headers`, `django-csp`, `django-ratelimit`, `whitenoise`; Flask: `app.py` with `flask`, `flask-talisman`, `flask-cors`, `flask-limiter`, `flask-wtf` (CSRF); FastAPI: `main.py` with `app.add_middleware(...)` order, `slowapi`, `secure`.

## Where the relevant code lives
Django: `settings*.py` (`MIDDLEWARE`, `SECURE_*`, `SESSION_COOKIE_*`, `CSRF_*`, `CORS_*`, `CSP_*`, `DATA_UPLOAD_MAX_MEMORY_SIZE`, `FILE_UPLOAD_MAX_MEMORY_SIZE`, `DEBUG`, `ALLOWED_HOSTS`, `SECURE_PROXY_SSL_HEADER`), `urls.py`, views with `@csrf_exempt`, DRF `REST_FRAMEWORK` (`DEFAULT_THROTTLE_CLASSES`, `DEFAULT_THROTTLE_RATES`, `DEFAULT_AUTHENTICATION_CLASSES` - `SessionAuthentication` implies cookies + CSRF), `nginx.conf`/`gunicorn.conf.py` in front. Flask: `app.py` (`Talisman(app, ...)`, `CORS(app)`, `Limiter`, `CSRFProtect`, `app.config['SESSION_COOKIE_*']`, `MAX_CONTENT_LENGTH`). FastAPI: `main.py` (`add_middleware(CORSMiddleware, ...)`, `HTTPSRedirectMiddleware`, `TrustedHostMiddleware`, custom header middleware, `slowapi` limiter).

## Dangerous / interesting APIs and patterns
- Headers (Django): `SecurityMiddleware` missing from `MIDDLEWARE` or not near the top; `SECURE_HSTS_SECONDS = 0`/unset (no HSTS), `< 15552000`; `SECURE_HSTS_INCLUDE_SUBDOMAINS = False`; `SECURE_CONTENT_TYPE_NOSNIFF = False` (default True since 3.0); `X_FRAME_OPTIONS = 'ALLOWALL'` or `XFrameOptionsMiddleware` missing; `SECURE_REFERRER_POLICY = 'unsafe-url'`/`None` (default `same-origin` - pass); no `django-csp` (`CSP_DEFAULT_SRC`, `CSP_SCRIPT_SRC` with `'unsafe-inline'`), no `Permissions-Policy` (needs `django-permissions-policy` or custom middleware); `SECURE_SSL_REDIRECT = False` behind a proxy without `SECURE_PROXY_SSL_HEADER` (all cookies non-Secure); `DEBUG = True` in prod (stack traces, settings dump). Flask: no `Talisman`; `Talisman(app, content_security_policy=None)`, `force_https=False`. FastAPI: no header middleware at all (framework sets none).
- Order (Django `MIDDLEWARE`): `SecurityMiddleware` not first (or after `WhiteNoiseMiddleware` is fine); `CorsMiddleware` **below** `CommonMiddleware` (must be above); `SessionMiddleware` after `AuthenticationMiddleware`; `CsrfViewMiddleware` absent or after views that need it; `AuthenticationMiddleware` before `SessionMiddleware`; `XFrameOptionsMiddleware` missing. FastAPI: `add_middleware` order is reverse of execution (last added runs first) - `CORSMiddleware` should be added last so it runs first.
- CORS: `CORS_ALLOW_ALL_ORIGINS = True` (or legacy `CORS_ORIGIN_ALLOW_ALL`) with `CORS_ALLOW_CREDENTIALS = True`; `CORS_ALLOWED_ORIGIN_REGEXES = [r".*"]`; `CORS_ALLOWED_ORIGINS` with `http://localhost` in prod; Flask `CORS(app)` (all origins) with `supports_credentials=True`; FastAPI `allow_origins=["*"]` with `allow_credentials=True`.
- Cookies: `SESSION_COOKIE_HTTPONLY = False`, `SESSION_COOKIE_SECURE = False`, `CSRF_COOKIE_SECURE = False`, `SESSION_COOKIE_SAMESITE = None`/`'None'`, `CSRF_COOKIE_HTTPONLY` (False is intended for JS double-submit - fine), `response.set_cookie(...)` without `httponly=True, secure=True, samesite=`; Flask `SESSION_COOKIE_SECURE` unset (False default), `SESSION_COOKIE_SAMESITE` unset; FastAPI `set_cookie` defaults (httponly False, secure False).
- CSRF: `CsrfViewMiddleware` removed; `@csrf_exempt` on state-changing views with session auth; DRF `SessionAuthentication` (enforces CSRF only for authenticated session users - fine) replaced by a custom class that skips `enforce_csrf`; `CSRF_TRUSTED_ORIGINS` with wildcards; Flask without `CSRFProtect` while using `flask-login` sessions; FastAPI with cookie sessions and no CSRF (nothing built in).
- Rate limiting: DRF `DEFAULT_THROTTLE_CLASSES` unset; login/OTP/password-reset views without `@ratelimit` / `throttle_classes` / `flask-limiter` `@limiter.limit` / `slowapi`; `django-axes` absent (lockout - cross-check authz skill); throttling keyed on `REMOTE_ADDR` behind a proxy without `X-Forwarded-For` handling (all one IP).
- Body limits: `DATA_UPLOAD_MAX_MEMORY_SIZE = None`, `FILE_UPLOAD_MAX_MEMORY_SIZE` huge, `DATA_UPLOAD_MAX_NUMBER_FIELDS = None`; Flask `MAX_CONTENT_LENGTH` unset (unlimited); FastAPI has no built-in body limit (rely on proxy `client_max_body_size` or a middleware) - note.
- Errors: `DEBUG = True`; `ALLOWED_HOSTS = ['*']`; Flask `app.run(debug=True)` / `FLASK_DEBUG=1`; FastAPI `debug=True`; custom handlers returning `traceback.format_exc()`.

## What "good" looks like
```python
# settings/prod.py
DEBUG = False
ALLOWED_HOSTS = ["app.example.com"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",        # headers, HSTS, SSL redirect - first
    "whitenoise.middleware.WhiteNoiseMiddleware",           # static
    "corsheaders.middleware.CorsMiddleware",                # cors - above CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware", # session
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",            # csrf
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # authn (after session)
    "csp.middleware.CSPMiddleware",                         # headers (CSP)
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
SECURE_SSL_REDIRECT = True; SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000; SECURE_HSTS_INCLUDE_SUBDOMAINS = True; SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"; X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True; SESSION_COOKIE_HTTPONLY = True; SESSION_COOKIE_SAMESITE = "Lax"
CSP_DEFAULT_SRC = ("'self'",); CSP_SCRIPT_SRC = ("'self'",); CSP_OBJECT_SRC = ("'none'",); CSP_FRAME_ANCESTORS = ("'none'",)
CORS_ALLOWED_ORIGINS = ["https://app.example.com"]; CORS_ALLOW_CREDENTIALS = True
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
REST_FRAMEWORK = {"DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle", "rest_framework.throttling.UserRateThrottle"],
                  "DEFAULT_THROTTLE_RATES": {"anon": "60/min", "user": "600/min", "login": "5/min"}}
```
Flask: `Talisman(app, content_security_policy={...}, force_https=True, strict_transport_security_max_age=31536000)`, `CSRFProtect(app)`, `Limiter(key_func=get_remote_address)` with `@limiter.limit("5/minute")` on login, `MAX_CONTENT_LENGTH = 5 * 1024 * 1024`. FastAPI: custom `SecurityHeadersMiddleware`, `CORSMiddleware` with explicit origins, `slowapi`.

## Manual trace checklist
1. Which settings module runs in production (`DJANGO_SETTINGS_MODULE`, `settings/__init__.py`, env switches); read that one.
2. `MIDDLEWARE` order (extractor) and the `SECURE_*`/cookie settings.
3. Auth model: session (cookies -> CSRF required) vs JWT header (`SimpleJWT`); custom authentication classes skipping `enforce_csrf`.
4. Every `set_cookie` call and the session/CSRF cookie settings; `SECURE_PROXY_SSL_HEADER` if behind a proxy.
5. CORS settings and origin lists.
6. Throttling/ratelimit on auth views; DRF throttle scopes.
7. Upload/body limits; `DEBUG`, `ALLOWED_HOSTS`, error handlers.

## Stack-specific false positives
- `CSRF_COOKIE_HTTPONLY = False` - intended so JS can read the token for double-submit.
- `SECURE_SSL_REDIRECT = False` when nginx redirects and sets `X-Forwarded-Proto` with `SECURE_PROXY_SSL_HEADER` configured.
- `@csrf_exempt` on a webhook endpoint that verifies a signature - Info.
- DRF `SessionAuthentication` already enforces CSRF for session users.
- FastAPI `add_middleware` reverse order is by design; judge execution order, not statement order.

## Tooling
- `python manage.py check --deploy` (Django's own security checklist - run it and attach the output).
- `python scripts/extract_middleware.py <repo> --stack python-django` (bundled; parses `MIDDLEWARE`).
- `python scripts/check_headers.py https://host` (bundled) when a URL is supplied.
- `bandit -r <dir>` (B201 flask debug, B104 bind all, B105/B106 hard-coded secrets), `semgrep --config p/django --config p/flask`.

## References
Django "Security in Django", "Deployment checklist", `SecurityMiddleware` settings; django-cors-headers and django-csp docs; Flask-Talisman; FastAPI middleware docs; OWASP HTTP Headers and CSRF cheat sheets. CWE-306, CWE-1004, CWE-614, CWE-352, CWE-942, CWE-307, CWE-400, CWE-209; ASVS 1.4.4, 3.4.x, 4.2.2, 13.2.x, 14.4.x, 14.5.x; OWASP A01/A05/A07:2021.
