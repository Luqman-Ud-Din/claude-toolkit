# Python / Django reference for audit-test-coverage-and-ci

## Stack markers

`manage.py`, `pytest.ini` / `pyproject.toml [tool.pytest.ini_options]` / `setup.cfg`,
`pytest-django` (`DJANGO_SETTINGS_MODULE`), `tests/`, `test_*.py`, Django `TestCase` /
`TransactionTestCase` / `APITestCase` (DRF), `factory_boy`, `model_bakery`, `faker`.
Integration: `pytest-django` uses a *real* database (the same engine as `DATABASES`, prefixed
`test_`) - the substitute risk here is `sqlite3` in the test settings when production is
PostgreSQL. `testcontainers[postgres]` for pinned engines. E2E: Playwright (`pytest-playwright`),
Selenium, `django.test.Client` / `LiveServerTestCase`.

## Where the relevant code lives

`tests/**`, `app/tests.py`, `app/tests/**`, `conftest.py` (fixtures, DB setup), `settings/test.py`
(`DATABASES`), `.coveragerc` / `[tool.coverage]`, `tox.ini`, `noxfile.py`, `.github/workflows/*.yml`,
`.gitlab-ci.yml`. Production units: `views.py`/`viewsets.py`, `services.py`, `serializers.py`
(validation), `models.py` (save/clean logic), `tasks.py` (Celery), `signals.py`, `permissions.py`,
`middleware.py`.

## Dangerous / interesting APIs and patterns

- Skipped: `@pytest.mark.skip(reason=...)`, `@pytest.mark.skipif(...)`, `@unittest.skip("...")`,
  `@skip`, `@skipIf`, `pytest.skip("...")` inside the body, `self.skipTest("...")`,
  `@pytest.mark.xfail` (expected failure - hides a real bug when `strict=False`), `@expectedFailure`.
  Markers excluded by `-m "not slow"` in CI.
- Substitute engine: `DATABASES["default"]["ENGINE"] = "django.db.backends.sqlite3"` in test
  settings while production is PostgreSQL/MySQL - JSONField lookups, `SELECT ... FOR UPDATE`,
  constraints, and raw SQL differ.
- Tests against shared infrastructure: `DATABASE_URL` for a real host in `settings/test.py`
  or `.env.test`; `--reuse-db` with a manually created DB.
- Hygiene: `time.sleep(`, `@override_settings` of `DEBUG`, tests depending on fixture order,
  `TransactionTestCase` everywhere (slow), `datetime.now()` in assertions without `freezegun`,
  `random` data without a seed, `mock.patch` of the function under test, `--nomigrations`
  (schema drift from migrations never tested).
- Auth: no test calls a view without login / with another user's object and asserts 403/404;
  `permission_classes` patched to `AllowAny` in tests; `force_authenticate` used for every
  request including the ones meant to test denial.
- CI: no `pytest` step, `pytest || true`, `-x` fine but `--maxfail` hiding, `-p no:cacheprovider`
  irrelevant; no `ruff`/`flake8`/`mypy`; no `pip-audit`/`safety`/`bandit`; `pip install` without
  a lockfile (`requirements.txt` unpinned, no `pip-tools`/`poetry.lock`/`uv.lock`); no `--cov-fail-under`;
  artifacts (wheels/images) without version or signature.

## What "good" looks like

```python
# conftest.py
@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):          # real PostgreSQL via testcontainers
    with PostgresContainer("postgres:16-alpine") as pg:
        settings.DATABASES["default"] = dj_database_url.parse(pg.get_connection_url())
        with django_db_blocker.unblock():
            call_command("migrate")
        yield

# tests/test_orders_api.py
@pytest.mark.django_db
def test_customer_cannot_read_other_tenant_order(api_client, tenant_b_user, order_tenant_a):
    api_client.force_authenticate(tenant_b_user)
    assert api_client.get(f"/api/orders/{order_tenant_a.id}/").status_code == 404
```
```toml
# pyproject.toml
[tool.pytest.ini_options]
addopts = "--strict-markers --cov=app --cov-report=term-missing --cov-fail-under=75"
[tool.coverage.run]
omit = ["*/migrations/*", "*/tests/*"]
```
```yaml
- run: pip install -r requirements.lock   # or: uv sync --frozen / poetry install --no-root
- run: ruff check . && mypy app
- run: pytest --cov --cov-fail-under=75
- run: pip-audit && bandit -r app -ll
```

## Manual trace checklist

1. Auth/permissions: tests for anonymous access, wrong user, wrong tenant on the main viewsets;
   `permissions.py` classes tested directly.
2. Money: pricing/invoice/payment services and serializers - `Decimal` scale, rounding,
   negative quantities, webhook idempotency.
3. Data mutation: engine in test settings matches production; migrations run (`--nomigrations`
   absent); signals/`save()` overrides tested.
4. Celery tasks: tested with `CELERY_TASK_ALWAYS_EAGER` or direct calls.
5. CI: pytest gated, coverage threshold, lint/type checks, `pip-audit`, lockfile.

## Stack-specific false positives

- `@pytest.mark.skipif(sys.platform == "win32")` with a Linux CI: runs in CI; Info.
- `xfail(strict=True)` is a legitimate "known bug, must still fail" marker: Info.
- `sqlite3` for a *pure* unit test suite of forms/utilities with a separate Postgres integration
  job: fine; the finding is sqlite as the only DB test engine.
- `--reuse-db` for speed with `--create-db` on schema change in CI: fine.

## Tooling

`pytest --collect-only -q` (inventory), `pytest --cov=app --cov-report=xml` + `coverage report -m`,
`pytest -m "not slow" --co` to see what CI excludes, `pip-audit`, `bandit -r app`, `mutmut run --paths-to-mutate app/payments`.

## References

- pytest skip/xfail: https://docs.pytest.org/en/stable/how-to/skipping.html
- pytest-django database access: https://pytest-django.readthedocs.io/en/latest/database.html
- Django testing tools: https://docs.djangoproject.com/en/stable/topics/testing/tools/
- CWE-1120, ASVS-1.14.4, ASVS-14.1.x.
