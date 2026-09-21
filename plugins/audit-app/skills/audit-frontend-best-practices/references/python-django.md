# Python / Django reference for audit-frontend-best-practices

This skill audits frontend code. A Django (or Flask/FastAPI) backend in the
same repo owns only how the SPA's static assets are collected and served, and
whether Django templates are the frontend (server-rendered) - in which case the
frontend categories mostly do not apply and the report must say so.

## Stack markers

`manage.py`, `requirements.txt` / `pyproject.toml` with `django`; `whitenoise`,
`django-webpack-loader`, `django-vite` mark SPA integration. Flask: `send_from_directory`,
`static_folder`. FastAPI: `StaticFiles` mount.

## Where the relevant code lives

`settings.py` (`STATIC_URL`, `STATIC_ROOT`, `STATICFILES_DIRS`, `STATICFILES_STORAGE` /
`STORAGES["staticfiles"]`, `WHITENOISE_*`, `DEBUG`, `WEBPACK_LOADER`, `DJANGO_VITE`);
`urls.py` (catch-all `TemplateView.as_view(template_name="index.html")`, `re_path(r"^(?!api/).*$")`);
`templates/index.html` (or the Vite-injected template); `Dockerfile` / `Procfile` for
`collectstatic` and the frontend build step.

## Dangerous / interesting APIs and patterns (this skill's slice only)

- `DEBUG = True` in the production settings module (Django serves static with no caching and
  exposes tracebacks) - report here for the static-serving effect; `audit-secrets-and-config`
  owns the secret-exposure angle.
- Static files served by Django itself in production (`django.views.static.serve`, `static()`
  helper in `urls.py` outside `if settings.DEBUG`) without WhiteNoise or a proxy: no compression,
  no cache headers.
- `STATICFILES_STORAGE` / `STORAGES` without a manifest storage
  (`ManifestStaticFilesStorage` or `CompressedManifestStaticFilesStorage`): no cache busting.
- WhiteNoise without `WHITENOISE_MAX_AGE` or with `WHITENOISE_AUTOREFRESH = True` in prod.
- SPA catch-all route placed before `api/` or `admin/` (API responses become `index.html`).
- `*.map` files collected into `STATIC_ROOT` (`collectstatic` copies everything in the dist dir).
- Frontend build in `Dockerfile`/CI run without the production configuration; `npm start`
  used as a service.
- `django-webpack-loader` `CACHE: False` in production settings.

## What "good" looks like

```python
# settings/production.py
DEBUG = False
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware",
              "whitenoise.middleware.WhiteNoiseMiddleware", ...]
STORAGES = {"staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}
WHITENOISE_MAX_AGE = 31536000      # hashed files only; index.html is a template, never cached
STATIC_ROOT = BASE_DIR / "staticfiles"
```
```python
# urls.py
urlpatterns = [path("api/", include("api.urls")), path("admin/", admin.site.urls),
               re_path(r"^(?!api/|admin/|static/).*$", TemplateView.as_view(template_name="index.html"))]
```

## Manual trace checklist

1. Server-rendered templates or SPA? If Django templates are the UI, mark the frontend
   scorecard categories "not applicable (server-rendered)" except lint/type-checking of any
   bundled JS.
2. Who serves static in production: WhiteNoise, nginx, S3/CloudFront? Compression and cache
   headers belong to that layer; verify with `curl -I --compressed`.
3. `collectstatic` inputs: does the frontend `dist/` include `.map` files?
4. URL ordering: API and admin before the SPA catch-all.

## Stack-specific false positives

- `DEBUG = True` only in `settings/local.py` or gated by env var with a `False` default: fine.
- `static()` helper inside `if settings.DEBUG:` in `urls.py`: fine.
- Django admin's own static files are not hashed by default; ignore.

## Tooling

`python manage.py collectstatic --noinput --dry-run` (lists what would be collected, including
maps); `python manage.py check --deploy`; `curl -I --compressed https://host/static/app.[hash].js`.

## Deferred to sibling skills

`SECURE_*` settings, CSP, HSTS: `audit-security-headers-and-middleware`. Secret exposure via
`DEBUG`: `audit-secrets-and-config`. Query performance: `audit-orm-query-and-data-access`.

## References

Django static files deployment: https://docs.djangoproject.com/en/stable/howto/static-files/deployment/;
WhiteNoise docs: https://whitenoise.readthedocs.io; CWE-540, CWE-215 (debug info), ASVS-14.3.2.
