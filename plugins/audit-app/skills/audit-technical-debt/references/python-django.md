# Python / Django reference for audit-technical-debt

## Stack markers

`manage.py`, `settings.py` / `settings/`, `pyproject.toml` or `requirements*.txt` with
`Django`, `djangorestframework`. Variants: DRF API-only, server-rendered templates,
Celery workers, FastAPI/Flask services beside Django (patterns still apply; entry-point
rules differ).

## Where the relevant code lives

- Hotspots: `views.py` / `viewsets.py`, `serializers.py` with `validate()` methods,
  `services.py`, `utils.py`, `tasks.py`, `management/commands/*.py`, model methods and
  `save()` overrides, signal receivers.
- Suppressions: `# noqa`, `# type: ignore`, `# pylint: disable=`, `# nosec`,
  `# pragma: no cover`, `[flake8] extend-ignore` / `per-file-ignores`, `[tool.ruff] ignore`,
  `mypy.ini` `ignore_errors = True` sections.
- Currency: `python_requires`, `requires-python`, `.python-version`, `runtime.txt`,
  `Dockerfile FROM python:<v>`, `Django==` pins, `celery`, `djangorestframework` majors.
- Excluded: `migrations/`, `.venv`, `site-packages`, generated `*_pb2.py`.

## Dangerous / interesting APIs and patterns

Mirrored in `scripts/patterns/python-django.json`.
- **Removed Django APIs** (they break the next upgrade): `django.conf.urls.url()`,
  `ugettext*`, `force_text`/`smart_text` (4.0); `NullBooleanField`, contrib.postgres
  `JSONField`; `index_together` (5.1); `USE_L10N`, `DEFAULT_FILE_STORAGE`,
  `STATICFILES_STORAGE` (5.1 -> `STORAGES`); `pytz` support (5.0); `default_app_config`.
- **Python removals**: `distutils` (3.12), `imp` (3.12), PEP 594 modules `cgi`, `asyncore`,
  `telnetlib`, `crypt` (3.13); `datetime.utcnow()` deprecated in 3.12; `pkg_resources`.
- **EOL markers**: Python 3.8 (2024-10-07), 3.9 (2025-10-31), 3.10 (2026-10-31); Django
  3.2 (2024-04-01), 4.2 LTS (2026-04-30); only 5.2 LTS and later are supported afterwards.
- **Suppressions**: bare `# noqa` (blanket), `# type: ignore` without an error code,
  `# nosec` (always security-related - check each), file-wide `# pylint: disable=all`.
- **Inconsistent patterns**: requests + httpx + urllib; function-based and class-based
  views in one app; `.raw()`/`cursor.execute` beside the ORM; Celery tasks beside ad-hoc
  `threading.Thread`; DRF serializers beside hand-built dicts.
- **Complexity shapes**: `if request.method == ...` ladders, serializer `validate()` with
  every business rule, `save()` overrides with side effects, 300-line management commands.

## What "good" looks like

Thin views, rules in services or model methods with tests, one HTTP client, ruff with
`C901` (mccabe) enforced at a threshold the team agreed, and specific ignores:

```python
value = legacy_client.fetch()  # type: ignore[attr-defined]  # vendor stub missing, upstream issue #412
```

## Manual trace checklist

1. Top hotspot view/serializer/task: list the branches, the rules, and the tests that pin them.
2. Run `python -Wd manage.py check` in a scratch virtualenv to list `RemovedInDjangoXXWarning`s;
   their count sizes the upgrade effort.
3. Dead-code candidates: check `urls.py` (dotted strings), `INSTALLED_APPS`, Celery
   autodiscovery, signal registration in `apps.py ready()`, admin registration, templates.
4. Every `# nosec` and every ignore of Bandit `B1xx-B7xx` codes.
5. Mixed families: pick the newest style per family and count stragglers.

## Stack-specific false positives

- Framework-discovered modules (`admin.py`, `apps.py`, `signals.py`, `tasks.py`,
  `management/commands/*`, `templatetags/`), pytest fixtures used by name, `__all__`
  re-exports, and `conftest.py` are skipped or must be confirmed by hand.
- Comprehension `if`/`for` and boolean `and`/`or` inflate the keyword-count complexity a
  little compared with radon; the ranking is still reliable.
- `# pragma: no cover` on `if TYPE_CHECKING:` and `__repr__` is routine.

## Tooling

- Complexity: `radon cc -s -a -j . > radon-cc.json`, `radon mi -s .`,
  `xenon --max-absolute B --max-modules A --max-average A .` (gate),
  `ruff check --select C901,PLR0912,PLR0915 --statistics .` (no `--fix`: read-only).
- Dead code: `vulture . --min-confidence 80 --exclude migrations,.venv`.
- Duplicates: `pylint --disable=all --enable=duplicate-code .` or jscpd.
- Currency and deprecations: `pip list --outdated --format=json` (in a venv built from
  the lockfile), `ruff check --select UP,DJ .`, `python -W error::DeprecationWarning -m pytest`,
  `django-upgrade --target-version 5.2` and `pyupgrade --py312-plus` **only in a scratch copy**
  (both rewrite files).

## References

CWE-1121, CWE-1080, CWE-561, CWE-1041, CWE-477, CWE-1104, CWE-546. Django deprecation
timeline: https://docs.djangoproject.com/en/dev/internals/deprecation/ ; Python versions:
https://devguide.python.org/versions/ ; radon: https://radon.readthedocs.io ; vulture:
https://github.com/jendrikseipp/vulture
