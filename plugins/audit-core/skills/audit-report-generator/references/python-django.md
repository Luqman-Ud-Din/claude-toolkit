# Python / Django (Flask, FastAPI) reference for audit-report-generator

What the report should enumerate and how to phrase findings when the backend is Python.
The generator is stack-agnostic; this file guides the scope table, executive wording and
remediation grouping for Django/DRF, Flask and FastAPI services.

## Stack markers
`manage.py`, `settings.py` or `settings/{base,production}.py`, `requirements*.txt` /
`pyproject.toml` / `Pipfile`, `wsgi.py` / `asgi.py`; Flask `app.py`; FastAPI `main.py`;
`celery.py` / `tasks.py` for workers. State which settings module is production.

## Where the relevant code lives (what "Scope" must enumerate)
- Apps: each Django app directory with `views.py` / `viewsets.py` / `urls.py`; FastAPI routers; Flask blueprints.
- Entry points: URL conf, DRF routers, Celery tasks, management commands run by cron, admin site (`/admin`).
- Settings: `DEBUG`, `ALLOWED_HOSTS`, `SECRET_KEY` source, `SECURE_*`, `REST_FRAMEWORK` defaults, `CORS_*`, `LOGGING`.
- Config surfaces: `.env`, `django-environ`, secret manager wiring.
- Out-of-repo for "Not checked": gunicorn/uvicorn flags, nginx/ingress headers, database grants.

## Findings that are typical launch blockers (and how to phrase them)
| Engineering finding | Executive wording |
|---|---|
| `DEBUG = True` in the production settings module | "Error pages show source code, settings and secrets to visitors." |
| `permission_classes = [AllowAny]` on a data viewset; `@csrf_exempt` on a state-changing session view | "Anyone can read or change data without logging in." |
| `get_queryset` returns `Model.objects.all()` on a per-user resource | "One customer can read or change another customer's records." |
| `cursor.execute("..." % x)` / f-string SQL / `.extra()` | "A crafted input can read or delete the whole database." |
| `SECRET_KEY = 'django-insecure-...'` committed | "Anyone with repository access can forge sessions and password-reset links." |
| `fields = '__all__'` on a serializer exposing `is_staff`/`owner` | "A user can make themselves an administrator through a normal edit form." |
| `pickle.loads` / `yaml.load` on request data | "A crafted request can run arbitrary code on the server." |

## What "good" looks like (remediation plan wording)
- "Set `DEBUG = False`, `ALLOWED_HOSTS = ['app.example.com']` in `settings/production.py`; run `manage.py check --deploy` in CI."
- "Set `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`; override per view only with justification."
- "Filter in `get_queryset`: `Order.objects.filter(owner=self.request.user)`."
- "Pass params: `cursor.execute(sql, [x])`; remove `%` formatting."
- "Load `SECRET_KEY` from `os.environ`; rotate; invalidate sessions."
- "Set `SECURE_HSTS_SECONDS = 31536000`, `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`."
Group tickets by settings module (all `SECURE_*`/`DEBUG` items), by app (ownership items), by serializer (mass-assignment items).

## Report review checklist (manual trace)
1. Scope table names the production settings module and whether `manage.py check --deploy` output is in the evidence.
2. Celery tasks / management commands listed as checked or not checked.
3. Admin site exposure (`/admin` reachable, 2FA) is stated.
4. Dependency findings cite `pip-audit` output with CVE ids.
5. Every Critical/High cites a file in the project, not `site-packages` or a virtualenv.

## Stack-specific false positives
- `@csrf_exempt` on a webhook that verifies an HMAC signature (document the check).
- `mark_safe` on constant strings.
- `SECURE_HSTS_SECONDS = 0` when the ingress sets HSTS and its config is in the repo.
- `DEBUG = True` in `settings/local.py` only.

## Tooling (evidence to expect in Appendix B)
`python manage.py check --deploy`, `bandit -r . -f json`, `pip-audit --format json`,
`safety check`, `curl -sI` header dumps, `tracemalloc` snapshots for leak findings.
Export: `pandoc audit/audit-report.md -o audit/audit-report.pdf --toc --from gfm --pdf-engine=xelatex`.

## Executive glossary (translate before the summary goes out)
- "DEBUG mode" -> "developer error pages switched on".
- "viewset / permission class" -> "an API endpoint and its login rule".
- "queryset" -> "the set of records a request is allowed to see".
- "settings module" -> "the production configuration file".

## References
Django deployment checklist; DRF permissions and throttling docs; FastAPI security docs;
ASVS 4.0.3 V4, V5.3, V14.3, V14.4; CWE-306, CWE-639, CWE-89, CWE-798, CWE-502.
