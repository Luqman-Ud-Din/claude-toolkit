# Python / Django reference for audit-application

What the orchestrator needs to know about a Python backend (Django first; Flask and
FastAPI through the generic sections) before it plans and runs the children. Topic
detail lives in each child's own `references/python-django.md`.

## Stack markers

- `manage.py`, or `requirements*.txt` / `pyproject.toml` / `Pipfile` / `setup.py` mentioning
  `django` (detect_stack id `python-django`). Flask or FastAPI are detected under the same id
  with a "generic sections" note.
- Server templates: `templates/**/*.html` (Django, Jinja2), `*.jinja2`. XSS and accessibility
  apply without an SPA.
- Django REST Framework (`rest_framework` in `INSTALLED_APPS`) makes api-contract central.
  `drf-spectacular` / `drf-yasg` provide the spec.

## Where the relevant code lives

- `settings.py` or `settings/{base,prod}.py` (`DEBUG`, `ALLOWED_HOSTS`, `DATABASES`,
  `MIDDLEWARE`, `LOGGING`), `urls.py`, `views.py` / `viewsets.py`, `serializers.py`,
  `models.py`, `*/migrations/*.py`, `tasks.py` (Celery), `admin.py`.
- FastAPI: `main.py`, `routers/`, `models.py` (SQLAlchemy), `alembic/versions/`.

## Dangerous / interesting APIs and patterns

Setup signals:

- **Multi-tenant hints:** `django-tenants` / `django-tenant-schemas` (`TENANT_MODEL`,
  `SHARED_APPS`/`TENANT_APPS`, schema-per-tenant), an `organization`/`tenant` FK on most models,
  custom managers filtering by `request.user.organization`, middleware setting a tenant
  thread-local, Postgres RLS policies in migrations.
- **Background work:** Celery + `celery beat` schedules (zones: `CELERY_TIMEZONE`), APScheduler,
  `django-q`. They concern concurrency, datetime and logging.
- **Admin surface:** `django.contrib.admin` URL exposure, which authz and headers review.
- **Settings split by environment variable** (`DJANGO_SETTINGS_MODULE`). Confirm which module
  production uses before secrets and readiness run.

## What "good" looks like

- The Python version from `pyproject.toml` / `runtime.txt` / Dockerfile available: `python -V`.
- A virtualenv where requirements install. `pip-audit` works from `requirements.txt` without
  installing, but licence metadata needs installed packages (`site-packages`).
- `python manage.py check --deploy --settings=<prod module>` can import settings (needs env
  vars; use dummy values, never real secrets).
- `python manage.py makemigrations --check --dry-run` runs (read-only drift check for db-schema).
- `pytest --cov` or `manage.py test` runs.
- Test URL + two users, two tenants, staging URL; full git history.

## Manual trace checklist

Prerequisites to confirm at setup:

1. Python version and an importable project (settings load) -> readiness (`check --deploy`),
   db-schema (migration drift), test-coverage. Missing: `--limited "settings not importable"`.
2. Requirements pinned (`requirements.txt` with `==`, `poetry.lock`, `uv.lock`) ->
   dependency-vulnerabilities (`pip-audit -r`), licensing.
3. Migrations present (they usually are) or read-only DB access -> db-schema, orm, concurrency
   (`select_for_update`, unique constraints).
4. Production settings module and secret source (env, Vault, `.env`) -> secrets, readiness,
   logging.
5. Celery broker/beat configuration visible -> concurrency, datetime.
6. Test/staging URLs and accounts for the probes.

## Stack-specific false positives

Wrong applicability calls to avoid:

- **DRF API only:** frontend-best-practices, frontend-memory-leak and client-auth are n/a. XSS and
  accessibility still apply when `templates/` exists: the browsable API, admin customisations,
  and email templates rendered to HTML.
- **Flask/FastAPI detected as `python-django`:** do not skip db-schema or orm for lack of Django
  models. SQLAlchemy/Alembic are covered by the generic sections.
- **Jupyter notebooks or data scripts** in the repo are not a backend. Keep them out of scope and
  record that in `not_checked` rather than auditing them.

## Tooling

```bash
python -V
python -m venv .venv-audit && .venv-audit/bin/pip install -r requirements.txt   # scratch venv; ask first
pip-audit -r requirements.txt --format json
python manage.py check --deploy --settings=config.settings.prod
python manage.py makemigrations --check --dry-run
pytest --cov --cov-report=json
git rev-parse --is-shallow-repository
```

## Child applicability for Python repos

| Repo shape | n/a children |
|---|---|
| API only (DRF/FastAPI), no templates | frontend-best-practices, frontend-memory-leak, client-auth-and-storage, XSS, accessibility |
| Django with templates | frontend-best-practices, frontend-memory-leak; client-auth applies only if tokens reach browser storage |
| Worker only (Celery) | expect api-contract and headers to record "no HTTP surface" |

## References

- Child references: `../audit-authz-and-access-control/references/python-django.md`,
  `../audit-multi-tenant-isolation/references/python-django.md`, `../audit-db-schema/references/python-django.md`.
- Django deployment checklist, django-tenants docs, pip-audit docs.
