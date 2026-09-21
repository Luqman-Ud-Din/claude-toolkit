# Python / Django (also SQLAlchemy + Alembic) reference for audit-db-schema

## Stack markers
`manage.py`, `requirements.txt`/`pyproject.toml` with `django`. Flask/FastAPI projects usually carry `sqlalchemy` + `alembic` (`alembic.ini`, `alembic/versions/`); use the SQLAlchemy sections below for those.

## Where the relevant code lives
- Django: `<app>/models.py` (or `models/` package), `<app>/migrations/0001_initial.py ...`, `settings.py` (`USE_TZ`, `DATABASES`, `DEFAULT_AUTO_FIELD`), fixtures `<app>/fixtures/*.json`, `<app>/management/commands/seed*.py`.
- SQLAlchemy: `models.py`/`models/`, `alembic/versions/<rev>_<slug>.py` (`upgrade()`/`downgrade()`), `alembic/env.py`.
- Loose DDL: `sql/`, `db/*.sql`.

## Dangerous / interesting APIs and patterns
- `models.FloatField()` on `price|amount|total|balance|tax|cost|rate` - money in float; use `DecimalField(max_digits=18, decimal_places=4)`.
- `DecimalField` with `decimal_places=2` on unit costs/rates that need more.
- `DateTimeField` with `USE_TZ = False` in settings - naive timestamps; `USE_TZ = True` (default since 5.0) stores UTC. `auto_now`/`auto_now_add` are fine for audit columns.
- `CharField` without `max_length` (validation error) vs `TextField` used for codes, names, emails - unbounded and unindexable on some engines; `EmailField` is bounded (254).
- `ForeignKey(..., on_delete=models.CASCADE)` to shared reference models (Company, Product, User) - Django requires `on_delete`, and CASCADE is what tutorials paste. Prefer `PROTECT`/`RESTRICT` for references, `CASCADE` only for owned children.
- `ForeignKey(..., db_index=False)` or `db_constraint=False` - drops the automatic FK index/constraint.
- Django creates an index for every FK and a PK (`id`) for every model automatically; a model with `managed = False` or `class Meta: db_table` pointing at a legacy table needs the DDL checked instead.
- `Meta.indexes`/`Meta.constraints` absent on models whose views filter/sort by non-FK columns (`status`, `created_at`, `code`); `unique_together`/`UniqueConstraint` absent on natural keys; `UniqueConstraint(condition=Q(is_deleted=False))` needed for soft delete.
- No `updated_at`, `created_by`, `updated_by` (Django gives nothing automatically).
- Soft delete via `is_deleted`/`deleted_at` without a custom `Manager` filtering it and without an index.
- No concurrency token: Django has none built in; look for `django-concurrency` or a `version` field with `F()` updates; `select_for_update()` as the alternative.
- Migration files: `migrations.RunPython(forward)` without `reverse_code` (or `RunPython.noop`), `migrations.RunSQL(sql)` without `reverse_sql`, `RemoveField`/`DeleteModel`/`AlterField` narrowing a type -> data loss; `--fake` instructions in READMEs.
- `makemigrations` drift: model changes without a migration (CI should run `makemigrations --check`).
- Fixtures/seeds containing real emails, phone numbers, `pbkdf2_sha256$` hashes copied from production.
- `password = models.CharField(...)` on a non-`AbstractBaseUser` model (plaintext), `ssn`, `national_id`, `card_number` without `django-encrypted-model-fields`/`django-fernet-fields`.
- SQLAlchemy: `Column(Float)` for money (use `Numeric(18, 4)`), `DateTime` vs `DateTime(timezone=True)`, `String` without length (Postgres OK, MySQL error), `ForeignKey` without `index=True`, `relationship(cascade="all, delete-orphan")` on shared references, `__table_args__` without `Index(...)`, `version_id_col` absent; Alembic `def downgrade(): pass`.

## What "good" looks like
```python
class OrderLine(models.Model):
    order = models.ForeignKey("Order", on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("Product", on_delete=models.PROTECT)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    sku = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["order", "created_at"])]
        constraints = [
            models.UniqueConstraint(fields=["order", "sku"], condition=Q(is_deleted=False), name="uq_orderline_sku_live"),
            models.CheckConstraint(check=Q(unit_price__gte=0), name="ck_orderline_price_nonneg"),
        ]
```
Migration with data step: `migrations.RunPython(forward, reverse)` where `reverse` really undoes the change, or `RunPython.noop` with a comment saying why nothing is needed.

## Manual trace checklist
1. `python manage.py makemigrations --check --dry-run` (read-only) - non-zero exit means model/migration drift.
2. `python manage.py sqlmigrate <app> <n>` on the newest migrations to see the real DDL (types, indexes) for the configured engine.
3. Money models: `DecimalField` everywhere a value is summed; check views use `Decimal`, not `float()`.
4. Hot views/querysets (`.filter(...).order_by(...)` in list views, DRF `filterset_fields`, `ordering_fields`) -> `Meta.indexes`.
5. Delete flow: `obj.delete()` cascades in Python (Django emulates CASCADE, so `PROTECT` raises) - confirm the chosen `on_delete` per FK matches business intent.
6. `USE_TZ`, `TIME_ZONE`, and DB session zone (`DATABASES[...]['TIME_ZONE']`) in `settings.py`.
7. `AUTH_USER_MODEL` and `PASSWORD_HASHERS`; any custom user model storing passwords must call `set_password`.

## Stack-specific false positives
- `on_delete=CASCADE` from a root to owned children is right; `SET_NULL` on nullable audit references (`created_by`) is right.
- `TextField` for genuinely free text (notes, descriptions).
- `RunPython` for a one-way backfill with `reverse_code=RunPython.noop` and a comment is acceptable (Info).
- Missing `Down` on Alembic/Django initial migration: Info.

## Tooling
- `manage.py makemigrations --check`, `manage.py showmigrations`, `manage.py sqlmigrate`, `manage.py inspectdb` (read-only dump of a live DB into models).
- `alembic history`, `alembic check` (1.9+) for model/migration drift, `alembic upgrade --sql head` to print DDL.
- `django-extensions` `graph_models` for an ER diagram; `django-migration-linter` for backward-incompatible migrations.
- Postgres: `pg_stat_user_indexes`, `pg_indexes`.

## References
- Django docs: Model field reference, Migrations (data migrations, `RunPython`), Database constraints, `USE_TZ`; SQLAlchemy ORM docs; Alembic tutorial.
- CWE-682, CWE-311, CWE-916, CWE-20; ASVS 2.4, 6.2, 8.3.
